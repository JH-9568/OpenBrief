import hmac
import json
from datetime import UTC, datetime
from hashlib import sha256
from typing import Any

import httpx

from teampulse.connectors.base import NormalizedSourceItem
from teampulse.models import Provider, SourceItemKind


class NotionWebhookConnector:
    provider = Provider.NOTION

    def verify(self, body: bytes, headers: dict[str, str], secret: str) -> bool:
        signature = headers.get("x-notion-signature", "")
        expected = "sha256=" + hmac.new(secret.encode(), body, sha256).hexdigest()
        return hmac.compare_digest(signature, expected)

    def normalize_webhook(
        self,
        *,
        project_id: str,
        integration_id: str | None,
        body: bytes,
        headers: dict[str, str],
    ) -> list[NormalizedSourceItem]:
        del headers
        payload = json.loads(body)
        if "verification_token" in payload:
            return []
        event_type = payload.get("type", payload.get("event_type", "unknown"))
        entity = payload.get("entity") or payload.get("data") or {}
        entity_id = entity.get("id") or payload.get("entity_id") or payload.get("id", "unknown")
        occurred_at = parse_dt(payload.get("timestamp") or payload.get("created_time"))
        return [
            NormalizedSourceItem(
                project_id=project_id,
                integration_id=integration_id,
                provider=self.provider,
                external_id=f"notion:{payload.get('id', entity_id)}:{event_type}",
                kind=kind_for_event(event_type),
                title=f"Notion {event_type}",
                body=json.dumps(entity, ensure_ascii=False, sort_keys=True)[:2000],
                source_url=entity.get("url"),
                occurred_at=occurred_at,
                actor=payload.get("actor") or {},
                metadata={"event_type": event_type, "entity_id": entity_id},
                raw_payload=payload,
            )
        ]


def kind_for_event(event_type: str) -> SourceItemKind:
    lowered = event_type.lower()
    if "page" in lowered or "block" in lowered:
        return SourceItemKind.PLANNING_DOC
    if "database" in lowered or "data_source" in lowered:
        return SourceItemKind.TASK_CHANGE
    return SourceItemKind.UNKNOWN


def parse_dt(value: str | None) -> datetime:
    if not value:
        return datetime.now(UTC)
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


class NotionClient:
    base_url = "https://api.notion.com/v1"
    notion_version = "2022-06-28"

    async def retrieve_page(self, *, access_token: str, page_id: str) -> dict[str, Any]:
        async with httpx.AsyncClient(base_url=self.base_url, timeout=20) as client:
            response = await client.get(
                f"/pages/{page_id}",
                headers=self._headers(access_token),
            )
            response.raise_for_status()
            return response.json()

    async def retrieve_block_children(
        self,
        *,
        access_token: str,
        block_id: str,
        page_size: int = 100,
    ) -> list[dict[str, Any]]:
        async with httpx.AsyncClient(base_url=self.base_url, timeout=20) as client:
            response = await client.get(
                f"/blocks/{block_id}/children",
                params={"page_size": page_size},
                headers=self._headers(access_token),
            )
            response.raise_for_status()
            payload = response.json()
            return list(payload.get("results", []))

    def _headers(self, access_token: str) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {access_token}",
            "Notion-Version": self.notion_version,
        }
