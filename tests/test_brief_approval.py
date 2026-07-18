from datetime import UTC, datetime

from openbrief.briefs.service import approval_state, approve_revision, build_daily_revision
from openbrief.models import (
    BriefRevisionStatus,
    Project,
    ProjectMember,
    Provider,
    SourceItemKind,
    Workspace,
)
from openbrief.schemas import SourceItemCreate
from openbrief.sources.service import store_source_item


async def test_revision_requires_all_snapshotted_members(session):
    workspace = Workspace(name="Acme")
    session.add(workspace)
    await session.flush()
    project = Project(workspace_id=workspace.id, name="Launch")
    session.add(project)
    await session.flush()
    alice = ProjectMember(project_id=project.id, display_name="Alice", email="a@example.com")
    bob = ProjectMember(project_id=project.id, display_name="Bob", email="b@example.com")
    session.add_all([alice, bob])
    await session.commit()

    source_item, duplicate = await store_source_item(
        session,
        SourceItemCreate(
            project_id=project.id,
            provider=Provider.DISCORD,
            external_id="discord:1",
            kind=SourceItemKind.MEETING_MESSAGE,
            title="Decision",
            body="결정: onboarding flow는 variant B로 간다.",
            occurred_at=datetime.now(UTC),
        ),
    )

    assert duplicate is False
    revision = await build_daily_revision(session, project.id, [source_item])

    state = await approval_state(session, revision)
    assert state.required_count == 2
    assert state.approved_count == 0
    assert state.status == BriefRevisionStatus.PENDING_APPROVAL

    state = await approve_revision(session, revision.id, alice.id)
    assert state.approved_count == 1
    assert state.status == BriefRevisionStatus.PENDING_APPROVAL

    state = await approve_revision(session, revision.id, bob.id)
    assert state.approved_count == 2
    assert state.status == BriefRevisionStatus.CONFIRMED


async def test_source_item_ingest_is_idempotent(session):
    workspace = Workspace(name="Acme")
    session.add(workspace)
    await session.flush()
    project = Project(workspace_id=workspace.id, name="Launch")
    session.add(project)
    await session.commit()

    payload = SourceItemCreate(
        project_id=project.id,
        provider=Provider.FIGMA,
        external_id="figma:event:1",
        kind=SourceItemKind.DESIGN_COMMENT,
        title="Figma FILE_COMMENT",
        body="TODO: 버튼 상태 확인",
        occurred_at=datetime.now(UTC),
    )
    first, duplicate_first = await store_source_item(session, payload)
    second, duplicate_second = await store_source_item(session, payload)

    assert duplicate_first is False
    assert duplicate_second is True
    assert first.id == second.id
