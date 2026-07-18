import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from openbrief.config import Settings, get_settings
from openbrief.connectors.figma import FigmaWebhookConnector
from openbrief.connectors.notion import NotionWebhookConnector
from openbrief.db import get_session
from openbrief.schemas import SourceItemCreate
from openbrief.sources.service import store_source_item

router = APIRouter(prefix="/api/v1/webhooks", tags=["webhooks"])


class WebhookAccepted(BaseModel):
    accepted: int
    duplicates: int


@router.post(
    "/figma/{project_id}",
    response_model=WebhookAccepted,
    status_code=status.HTTP_202_ACCEPTED,
)
async def figma_webhook(
    project_id: uuid.UUID,
    request: Request,
    integration_id: uuid.UUID | None = None,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> WebhookAccepted:
    body = await request.body()
    headers = normalize_headers(request)
    connector = FigmaWebhookConnector()
    if not connector.verify(body, headers, settings.figma_webhook_passcode.get_secret_value()):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid Figma passcode")
    return await normalize_and_store(connector, project_id, integration_id, body, headers, session)


@router.post(
    "/notion/{project_id}",
    response_model=WebhookAccepted,
    status_code=status.HTTP_202_ACCEPTED,
)
async def notion_webhook(
    project_id: uuid.UUID,
    request: Request,
    integration_id: uuid.UUID | None = None,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> WebhookAccepted:
    body = await request.body()
    payload = await request.json()
    if "verification_token" in payload:
        return WebhookAccepted(accepted=0, duplicates=0)

    headers = normalize_headers(request)
    connector = NotionWebhookConnector()
    if not connector.verify(
        body, headers, settings.notion_webhook_verification_token.get_secret_value()
    ):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid Notion signature")
    return await normalize_and_store(connector, project_id, integration_id, body, headers, session)


def normalize_headers(request: Request) -> dict[str, str]:
    return {key.lower(): value for key, value in request.headers.items()}


async def normalize_and_store(
    connector,
    project_id: uuid.UUID,
    integration_id: uuid.UUID | None,
    body: bytes,
    headers: dict[str, str],
    session: AsyncSession,
) -> WebhookAccepted:
    accepted = 0
    duplicates = 0
    for normalized in connector.normalize_webhook(
        project_id=str(project_id),
        integration_id=str(integration_id) if integration_id else None,
        body=body,
        headers=headers,
    ):
        data = normalized.model_dump(exclude={"project_id", "integration_id"})
        _, duplicate = await store_source_item(
            session,
            SourceItemCreate(
                **data,
                project_id=uuid.UUID(normalized.project_id),
                integration_id=uuid.UUID(normalized.integration_id)
                if normalized.integration_id
                else None,
            ),
        )
        accepted += 1
        duplicates += int(duplicate)
    return WebhookAccepted(accepted=accepted, duplicates=duplicates)
