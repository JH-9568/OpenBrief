import uuid
from datetime import UTC, datetime
from typing import Any, Protocol

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from openbrief.config import Settings
from openbrief.connectors.notion import NotionClient
from openbrief.integrations.discord import decrypt_credentials
from openbrief.models import Integration, Provider, SourceItemKind
from openbrief.schemas import SourceItemCreate
from openbrief.sources.service import store_source_item


class NotionApiClient(Protocol):
    async def retrieve_page(self, *, access_token: str, page_id: str) -> dict[str, Any]: ...

    async def retrieve_block_children(
        self,
        *,
        access_token: str,
        block_id: str,
        page_size: int = 100,
    ) -> list[dict[str, Any]]: ...


class NotionSyncResult(BaseModel):
    integration_id: uuid.UUID
    page_ids: list[str]
    fetched: int
    stored: int
    duplicates: int
    last_synced_at: str


async def sync_notion_integration(
    session: AsyncSession,
    integration_id: uuid.UUID,
    settings: Settings,
    client: NotionApiClient | None = None,
) -> NotionSyncResult:
    integration = await session.get(Integration, integration_id)
    if integration is None:
        raise ValueError("Integration not found")
    if integration.provider != Provider.NOTION:
        raise ValueError("Integration is not a Notion integration")

    integration_id_value = integration.id
    config = dict(integration.config)
    page_ids = normalize_page_ids(config, integration.external_id)
    if not page_ids:
        raise ValueError("Notion integration config.page_ids is required")

    credentials = decrypt_credentials(integration, settings)
    access_token = credentials.get("access_token")
    if not access_token and settings.notion_access_token:
        access_token = settings.notion_access_token.get_secret_value()
    if not access_token:
        raise ValueError("Notion access token is required")

    notion_client = client or NotionClient()
    stored = 0
    duplicates = 0
    fetched = 0
    for page_id in page_ids:
        page = await notion_client.retrieve_page(access_token=access_token, page_id=page_id)
        blocks = await notion_client.retrieve_block_children(
            access_token=access_token,
            block_id=page_id,
        )
        fetched += 1
        _, duplicate = await store_source_item(
            session,
            page_source_item(integration, page_id, page, blocks),
        )
        stored += int(not duplicate)
        duplicates += int(duplicate)

    last_synced_at = datetime.now(UTC).isoformat()
    checkpoint = await session.get(Integration, integration_id_value)
    if checkpoint is None:
        raise ValueError("Integration not found")
    checkpoint.config = {
        **config,
        "page_ids": page_ids,
        "last_synced_at": last_synced_at,
    }
    await session.commit()

    return NotionSyncResult(
        integration_id=integration_id_value,
        page_ids=page_ids,
        fetched=fetched,
        stored=stored,
        duplicates=duplicates,
        last_synced_at=last_synced_at,
    )


def normalize_page_ids(config: dict[str, Any], external_id: str) -> list[str]:
    if config.get("page_ids"):
        return [str(page_id) for page_id in config["page_ids"]]
    if config.get("page_id"):
        return [str(config["page_id"])]
    if external_id:
        return [external_id]
    return []


def page_source_item(
    integration: Integration,
    page_id: str,
    page: dict[str, Any],
    blocks: list[dict[str, Any]],
) -> SourceItemCreate:
    last_edited_time = page.get("last_edited_time") or page.get("created_time")
    return SourceItemCreate(
        project_id=integration.project_id,
        integration_id=integration.id,
        provider=Provider.NOTION,
        external_id=f"notion:page:{page_id}:{last_edited_time or 'unknown'}",
        kind=SourceItemKind.PLANNING_DOC,
        title=f"Notion page: {notion_title(page) or page_id}",
        body=blocks_to_text(blocks),
        source_url=page.get("url"),
        occurred_at=parse_notion_dt(last_edited_time),
        actor={"last_edited_by": page.get("last_edited_by")},
        metadata={
            "page_id": page_id,
            "last_edited_time": last_edited_time,
            "block_count": len(blocks),
        },
        raw_payload={"page": page, "blocks": blocks},
    )


def notion_title(page: dict[str, Any]) -> str:
    for value in page.get("properties", {}).values():
        title_fragments = value.get("title") if isinstance(value, dict) else None
        if title_fragments:
            return "".join(fragment.get("plain_text", "") for fragment in title_fragments).strip()
    return ""


def blocks_to_text(blocks: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    for block in blocks:
        block_type = block.get("type")
        if not block_type:
            continue
        value = block.get(block_type)
        if not isinstance(value, dict):
            continue
        rich_text = value.get("rich_text") or []
        text = "".join(fragment.get("plain_text", "") for fragment in rich_text).strip()
        if text:
            lines.append(text)
    return "\n".join(lines)


def parse_notion_dt(value: str | None) -> datetime:
    if not value:
        return datetime.now(UTC)
    return datetime.fromisoformat(value.replace("Z", "+00:00"))
