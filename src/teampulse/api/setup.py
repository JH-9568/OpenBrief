from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from teampulse.config import Settings, get_settings
from teampulse.models import Provider

router = APIRouter(prefix="/api/v1/integration-setup", tags=["integration-setup"])


class IntegrationSetupRead(BaseModel):
    provider: Provider
    install_url: str | None = None
    required_permissions: list[str]
    required_config: list[str]
    notes: list[str]
    docs_url: str


@router.get("/{provider}", response_model=IntegrationSetupRead)
async def get_integration_setup(
    provider: Provider,
    settings: Settings = Depends(get_settings),
) -> IntegrationSetupRead:
    builders: dict[Provider, Any] = {
        Provider.DISCORD: discord_setup,
        Provider.FIGMA: figma_setup,
        Provider.NOTION: notion_setup,
    }
    if provider not in builders:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Provider setup is not available")
    return builders[provider](settings)


def discord_setup(settings: Settings) -> IntegrationSetupRead:
    install_url = None
    if settings.discord_application_id:
        permissions = 68608  # VIEW_CHANNEL, SEND_MESSAGES, READ_MESSAGE_HISTORY
        install_url = (
            "https://discord.com/oauth2/authorize"
            f"?client_id={settings.discord_application_id}"
            f"&permissions={permissions}&scope=bot%20applications.commands"
        )
    return IntegrationSetupRead(
        provider=Provider.DISCORD,
        install_url=install_url,
        required_permissions=["VIEW_CHANNEL", "READ_MESSAGE_HISTORY", "SEND_MESSAGES"],
        required_config=["channel_id", "bot_token"],
        notes=[
            "Message content may require Discord's privileged Message Content access.",
            "Only connect opted-in project channels.",
        ],
        docs_url="https://docs.discord.com/developers/resources/message",
    )


def figma_setup(settings: Settings) -> IntegrationSetupRead:
    del settings
    return IntegrationSetupRead(
        provider=Provider.FIGMA,
        required_permissions=["file_content:read", "file_comments:read", "webhooks:write"],
        required_config=["file_key", "access_token", "webhook_passcode"],
        notes=[
            "Webhook creation requires sufficient file/project/team permissions.",
            "PING events verify connectivity and are not stored as source evidence.",
        ],
        docs_url="https://developers.figma.com/docs/rest-api/scopes/",
    )


def notion_setup(settings: Settings) -> IntegrationSetupRead:
    del settings
    return IntegrationSetupRead(
        provider=Provider.NOTION,
        required_permissions=["Read content", "Read comments"],
        required_config=["page_ids", "access_token", "webhook_verification_token"],
        notes=[
            "The Notion connection must be shared with selected pages/databases.",
            "Webhook signatures should be verified with X-Notion-Signature.",
        ],
        docs_url="https://developers.notion.com/reference/capabilities",
    )
