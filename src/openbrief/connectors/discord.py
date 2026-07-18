from datetime import UTC, datetime
from typing import Any

import httpx

from openbrief.connectors.base import NormalizedSourceItem
from openbrief.models import Provider, SourceItemKind


class DiscordClient:
    provider = Provider.DISCORD
    base_url = "https://discord.com/api/v10"

    async def fetch_channel_messages(
        self,
        *,
        bot_token: str,
        project_id: str,
        integration_id: str | None,
        channel_id: str,
        after: str | None = None,
        limit: int = 50,
    ) -> list[NormalizedSourceItem]:
        params: dict[str, Any] = {"limit": min(limit, 100)}
        if after:
            params["after"] = after
        async with httpx.AsyncClient(base_url=self.base_url, timeout=15) as client:
            response = await client.get(
                f"/channels/{channel_id}/messages",
                params=params,
                headers={"Authorization": f"Bot {bot_token}"},
            )
            response.raise_for_status()
            messages = response.json()

        return [
            NormalizedSourceItem(
                project_id=project_id,
                integration_id=integration_id,
                provider=self.provider,
                external_id=f"discord:{message['id']}",
                kind=SourceItemKind.COMMAND
                if str(message.get("content", "")).startswith("/")
                else SourceItemKind.MEETING_MESSAGE,
                title=f"Discord message in {channel_id}",
                body=message.get("content") or "",
                source_url=(
                    "https://discord.com/channels/"
                    f"{message.get('guild_id', '@me')}/{channel_id}/{message['id']}"
                ),
                occurred_at=parse_dt(message.get("timestamp")),
                actor=message.get("author") or {},
                metadata={"channel_id": channel_id, "message_id": message["id"]},
                raw_payload=message,
            )
            for message in messages
        ]

    async def send_message(
        self,
        *,
        bot_token: str,
        channel_id: str,
        content: str,
    ) -> dict[str, Any]:
        async with httpx.AsyncClient(base_url=self.base_url, timeout=15) as client:
            response = await client.post(
                f"/channels/{channel_id}/messages",
                headers={"Authorization": f"Bot {bot_token}"},
                json={"content": content, "allowed_mentions": {"parse": []}},
            )
            response.raise_for_status()
            return response.json()


def parse_dt(value: str | None) -> datetime:
    if not value:
        return datetime.now(UTC)
    return datetime.fromisoformat(value.replace("Z", "+00:00"))
