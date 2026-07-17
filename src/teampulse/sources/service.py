import uuid
from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import Select, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from teampulse.models import Provider, SourceItem, SourceItemKind
from teampulse.schemas import SourceItemCreate


async def store_source_item(
    session: AsyncSession, item_in: SourceItemCreate
) -> tuple[SourceItem, bool]:
    item = SourceItem(
        project_id=item_in.project_id,
        integration_id=item_in.integration_id,
        provider=item_in.provider,
        external_id=item_in.external_id,
        kind=item_in.kind,
        title=item_in.title,
        body=item_in.body,
        source_url=str(item_in.source_url) if item_in.source_url else None,
        occurred_at=item_in.occurred_at,
        actor=item_in.actor,
        source_metadata=item_in.metadata,
        raw_payload=item_in.raw_payload,
    )
    session.add(item)
    try:
        await session.commit()
        await session.refresh(item)
        return item, False
    except IntegrityError:
        await session.rollback()
        result = await session.execute(
            select(SourceItem).where(
                SourceItem.provider == item_in.provider,
                SourceItem.external_id == item_in.external_id,
            )
        )
        return result.scalar_one(), True


async def list_source_items(
    session: AsyncSession,
    project_id: uuid.UUID,
    since: datetime | None = None,
    until: datetime | None = None,
    provider: Provider | None = None,
    kind: SourceItemKind | None = None,
) -> Sequence[SourceItem]:
    query: Select[tuple[SourceItem]] = select(SourceItem).where(SourceItem.project_id == project_id)
    if since:
        query = query.where(SourceItem.occurred_at >= since)
    if until:
        query = query.where(SourceItem.occurred_at <= until)
    if provider:
        query = query.where(SourceItem.provider == provider)
    if kind:
        query = query.where(SourceItem.kind == kind)
    result = await session.execute(query.order_by(SourceItem.occurred_at.asc()))
    return result.scalars().all()
