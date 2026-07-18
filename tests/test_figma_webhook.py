import json

from openbrief.connectors.figma import FigmaWebhookConnector
from openbrief.models import Project, Provider, SourceItemKind, Workspace
from openbrief.schemas import SourceItemCreate
from openbrief.sources.service import store_source_item


def test_figma_webhook_verifies_passcode_and_ignores_ping():
    connector = FigmaWebhookConnector()
    body = json.dumps(
        {
            "event_type": "PING",
            "passcode": "secret",
            "timestamp": "2026-07-18T10:00:00Z",
            "webhook_id": "1",
        }
    ).encode()

    assert connector.verify(body, {}, "secret") is True
    assert connector.verify(body, {}, "wrong") is False
    assert (
        connector.normalize_webhook(
            project_id="00000000-0000-0000-0000-000000000001",
            integration_id=None,
            body=body,
            headers={},
        )
        == []
    )


async def test_figma_comment_payload_normalizes_and_stores_idempotently(session):
    workspace = Workspace(name="Acme")
    session.add(workspace)
    await session.flush()
    project = Project(workspace_id=workspace.id, name="Launch")
    session.add(project)
    await session.commit()

    connector = FigmaWebhookConnector()
    body = json.dumps(
        {
            "event_type": "FILE_COMMENT",
            "passcode": "secret",
            "file_key": "abc123",
            "file_name": "Main design",
            "comment_id": "42",
            "comment": [{"text": "TODO: "}, {"mention": "user-1"}, {"text": " CTA 확인"}],
            "timestamp": "2026-07-18T10:00:00Z",
            "created_at": "2026-07-18T09:59:00Z",
            "webhook_id": "99",
            "triggered_by": {"id": "designer-1", "handle": "Mina"},
        }
    ).encode()

    normalized = connector.normalize_webhook(
        project_id=str(project.id),
        integration_id=None,
        body=body,
        headers={},
    )[0]

    assert normalized.provider == Provider.FIGMA
    assert normalized.kind == SourceItemKind.DESIGN_COMMENT
    assert normalized.external_id == "figma:99:FILE_COMMENT:abc123:42"
    assert normalized.body == "TODO: @user-1 CTA 확인"
    assert normalized.source_url == "https://www.figma.com/file/abc123"

    data = normalized.model_dump(exclude={"project_id", "integration_id"})
    first, first_duplicate = await store_source_item(
        session,
        SourceItemCreate(**data, project_id=project.id),
    )
    second, second_duplicate = await store_source_item(
        session,
        SourceItemCreate(**data, project_id=project.id),
    )

    assert first_duplicate is False
    assert second_duplicate is True
    assert first.id == second.id
