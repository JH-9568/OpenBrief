from collections.abc import AsyncIterator
from datetime import UTC, datetime

import httpx

from teampulse.db import get_session
from teampulse.main import create_app
from teampulse.models import Project, Provider, SourceItemKind, Workspace
from teampulse.schemas import SourceItemCreate
from teampulse.sources.service import store_source_item


async def test_list_project_source_items_filters_by_provider_and_kind(session):
    workspace = Workspace(name="Acme")
    session.add(workspace)
    await session.flush()
    project = Project(workspace_id=workspace.id, name="Launch")
    session.add(project)
    await session.commit()

    await store_source_item(
        session,
        SourceItemCreate(
            project_id=project.id,
            provider=Provider.DISCORD,
            external_id="discord:301",
            kind=SourceItemKind.MEETING_MESSAGE,
            title="Meeting",
            body="결정: 오늘 배포",
            occurred_at=datetime.now(UTC),
        ),
    )
    await store_source_item(
        session,
        SourceItemCreate(
            project_id=project.id,
            provider=Provider.FIGMA,
            external_id="figma:301",
            kind=SourceItemKind.DESIGN_COMMENT,
            title="Design comment",
            body="CTA 확인",
            occurred_at=datetime.now(UTC),
        ),
    )

    app = create_app()

    async def override_session() -> AsyncIterator:
        yield session

    app.dependency_overrides[get_session] = override_session
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            f"/api/v1/projects/{project.id}/source-items",
            params={"provider": "figma", "kind": "design_comment"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 1
    assert payload[0]["provider"] == "figma"
    assert payload[0]["kind"] == "design_comment"
    assert payload[0]["title"] == "Design comment"
