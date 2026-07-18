import json
import uuid
from datetime import UTC, datetime
from typing import Protocol

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from openbrief.config import Settings
from openbrief.connectors.base import NormalizedSourceItem
from openbrief.connectors.discord import DiscordClient
from openbrief.models import Integration, Provider
from openbrief.schemas import SourceItemCreate
from openbrief.security import CredentialCipher
from openbrief.sources.service import store_source_item


class DiscordMessageClient(Protocol):
    async def fetch_channel_messages(
        self,
        *,
        bot_token: str,
        project_id: str,
        integration_id: str | None,
        channel_id: str,
        after: str | None = None,
        limit: int = 50,
    ) -> list[NormalizedSourceItem]: ...


class DiscordPollResult(BaseModel):
    integration_id: uuid.UUID
    channel_id: str
    fetched: int
    stored: int
    duplicates: int
    last_message_id: str | None


async def poll_discord_integration(
    session: AsyncSession,
    integration_id: uuid.UUID,
    settings: Settings,
    client: DiscordMessageClient | None = None,
) -> DiscordPollResult:
    integration = await session.get(Integration, integration_id)
    if integration is None:
        raise ValueError("Integration not found")
    if integration.provider != Provider.DISCORD:
        raise ValueError("Integration is not a Discord integration")

    integration_id_value = integration.id
    project_id_value = integration.project_id
    config = dict(integration.config)
    channel_id = config.get("channel_id")
    if not channel_id:
        raise ValueError("Discord integration config.channel_id is required")

    credentials = decrypt_credentials(integration, settings)
    bot_token = credentials.get("bot_token")
    if not bot_token and settings.discord_bot_token:
        bot_token = settings.discord_bot_token.get_secret_value()
    if not bot_token:
        raise ValueError("Discord bot token is required")

    after = config.get("last_message_id")
    limit = int(config.get("poll_limit", 50))
    discord_client = client or DiscordClient()
    items = await discord_client.fetch_channel_messages(
        bot_token=bot_token,
        project_id=str(project_id_value),
        integration_id=str(integration_id_value),
        channel_id=channel_id,
        after=after,
        limit=limit,
    )

    stored = 0
    duplicates = 0
    for item in items:
        data = item.model_dump(exclude={"project_id", "integration_id"})
        _, duplicate = await store_source_item(
            session,
            SourceItemCreate(
                **data,
                project_id=uuid.UUID(item.project_id),
                integration_id=uuid.UUID(item.integration_id) if item.integration_id else None,
            ),
        )
        stored += int(not duplicate)
        duplicates += int(duplicate)

    last_message_id = max_discord_snowflake(items) or after
    checkpoint_integration = await session.get(Integration, integration_id_value)
    if checkpoint_integration is None:
        raise ValueError("Integration not found")
    checkpoint_integration.config = {
        **config,
        "last_message_id": last_message_id,
        "last_polled_at": datetime.now(UTC).isoformat(),
    }
    await session.commit()

    return DiscordPollResult(
        integration_id=integration_id_value,
        channel_id=channel_id,
        fetched=len(items),
        stored=stored,
        duplicates=duplicates,
        last_message_id=last_message_id,
    )


def decrypt_credentials(integration: Integration, settings: Settings) -> dict:
    if not integration.encrypted_credentials:
        return {}
    if settings.token_encryption_key is None:
        raise ValueError("TOKEN_ENCRYPTION_KEY is required to decrypt credentials")
    cipher = CredentialCipher(settings.token_encryption_key.get_secret_value())
    return json.loads(cipher.decrypt(integration.encrypted_credentials))


def max_discord_snowflake(items: list[NormalizedSourceItem]) -> str | None:
    message_ids = [
        str(item.metadata["message_id"])
        for item in items
        if item.metadata.get("message_id") and str(item.metadata["message_id"]).isdigit()
    ]
    if not message_ids:
        return None
    return max(message_ids, key=int)
