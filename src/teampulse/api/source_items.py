from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from teampulse.db import get_session
from teampulse.schemas import SourceItemCreate, SourceItemRead
from teampulse.sources.service import store_source_item

router = APIRouter(prefix="/api/v1/source-items", tags=["source-items"])


@router.post("", response_model=SourceItemRead, status_code=status.HTTP_201_CREATED)
async def create_source_item(
    payload: SourceItemCreate, session: AsyncSession = Depends(get_session)
) -> SourceItemRead:
    item, _ = await store_source_item(session, payload)
    return SourceItemRead.model_validate(item)


class IngestAccepted(SourceItemRead):
    duplicate: bool


@router.post("/ingest", response_model=IngestAccepted, status_code=status.HTTP_202_ACCEPTED)
async def ingest_source_item(
    payload: SourceItemCreate, session: AsyncSession = Depends(get_session)
) -> IngestAccepted:
    item, duplicate = await store_source_item(session, payload)
    data = SourceItemRead.model_validate(item).model_dump()
    return IngestAccepted(**data, duplicate=duplicate)
