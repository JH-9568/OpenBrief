from datetime import datetime
from typing import Any, Protocol

from pydantic import BaseModel, Field

from openbrief.models import Provider, SourceItemKind


class NormalizedSourceItem(BaseModel):
    project_id: str
    integration_id: str | None = None
    provider: Provider
    external_id: str
    kind: SourceItemKind
    title: str
    body: str = ""
    source_url: str | None = None
    occurred_at: datetime
    actor: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    raw_payload: dict[str, Any] = Field(default_factory=dict)


class WebhookConnector(Protocol):
    provider: Provider

    def verify(self, body: bytes, headers: dict[str, str], secret: str) -> bool: ...

    def normalize_webhook(
        self,
        *,
        project_id: str,
        integration_id: str | None,
        body: bytes,
        headers: dict[str, str],
    ) -> list[NormalizedSourceItem]: ...


class PollingConnector(Protocol):
    provider: Provider

    async def fetch_updates(
        self, *, credentials: dict[str, Any], config: dict[str, Any]
    ) -> list[NormalizedSourceItem]: ...
