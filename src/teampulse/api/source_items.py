import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from teampulse.db import get_session
from teampulse.models import Provider, SourceItemKind
from teampulse.schemas import SourceItemCreate, SourceItemRead
from teampulse.sources.service import list_source_items, store_source_item

router = APIRouter(prefix="/api/v1", tags=["source-items"])


@router.post("/source-items", response_model=SourceItemRead, status_code=status.HTTP_201_CREATED)
async def create_source_item(
    payload: SourceItemCreate, session: AsyncSession = Depends(get_session)
) -> SourceItemRead:
    item, _ = await store_source_item(session, payload)
    return SourceItemRead.model_validate(item)


class IngestAccepted(SourceItemRead):
    duplicate: bool


@router.post(
    "/source-items/ingest",
    response_model=IngestAccepted,
    status_code=status.HTTP_202_ACCEPTED,
)
async def ingest_source_item(
    payload: SourceItemCreate, session: AsyncSession = Depends(get_session)
) -> IngestAccepted:
    item, duplicate = await store_source_item(session, payload)
    data = SourceItemRead.model_validate(item).model_dump()
    return IngestAccepted(**data, duplicate=duplicate)


@router.get("/projects/{project_id}/source-items", response_model=list[SourceItemRead])
async def list_project_source_items(
    project_id: uuid.UUID,
    since: datetime | None = None,
    until: datetime | None = None,
    provider: Provider | None = None,
    kind: SourceItemKind | None = None,
    session: AsyncSession = Depends(get_session),
) -> list[SourceItemRead]:
    items = await list_source_items(
        session,
        project_id,
        since=since,
        until=until,
        provider=provider,
        kind=kind,
    )
    return [SourceItemRead.model_validate(item) for item in items]
