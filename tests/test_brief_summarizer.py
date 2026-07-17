from datetime import UTC, datetime

from teampulse.briefs.service import build_daily_revision
from teampulse.models import Project, Provider, SourceItemKind, Workspace
from teampulse.schemas import SourceItemCreate
from teampulse.sources.service import store_source_item


async def test_structured_brief_builder_routes_key_signals_to_sections(session):
    workspace = Workspace(name="Acme")
    session.add(workspace)
    await session.flush()
    project = Project(workspace_id=workspace.id, name="Launch")
    session.add(project)
    await session.commit()

    source_items = []
    for payload in [
        SourceItemCreate(
            project_id=project.id,
            provider=Provider.DISCORD,
            external_id="discord:decision",
            kind=SourceItemKind.MEETING_MESSAGE,
            title="Meeting",
            body="Decision: onboarding uses variant B.",
            occurred_at=datetime.now(UTC),
        ),
        SourceItemCreate(
            project_id=project.id,
            provider=Provider.FIGMA,
            external_id="figma:todo",
            kind=SourceItemKind.DESIGN_COMMENT,
            title="Figma comment",
            body="TODO: CTA copy 확인",
            occurred_at=datetime.now(UTC),
        ),
        SourceItemCreate(
            project_id=project.id,
            provider=Provider.DISCORD,
            external_id="discord:blocker",
            kind=SourceItemKind.MEETING_MESSAGE,
            title="Blocker",
            body="blocked by API permission review",
            occurred_at=datetime.now(UTC),
        ),
    ]:
        source_item, _ = await store_source_item(session, payload)
        source_items.append(source_item)

    revision = await build_daily_revision(session, project.id, source_items)
    sections = {section["key"]: section for section in revision.content["sections"]}

    assert len(sections["decisions"]["claims"]) == 1
    assert len(sections["tasks"]["claims"]) == 1
    assert len(sections["schedule_risks"]["claims"]) == 1
    assert sections["tasks"]["claims"][0]["source_item_ids"] == [str(source_items[1].id)]
