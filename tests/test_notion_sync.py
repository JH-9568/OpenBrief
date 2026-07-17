from teampulse.config import Settings
from teampulse.integrations.notion import sync_notion_integration
from teampulse.models import Integration, Project, Provider, Workspace


class FakeNotionClient:
    async def retrieve_page(self, *, access_token: str, page_id: str) -> dict:
        assert access_token == "notion-token"
        assert page_id == "page-1"
        return {
            "id": page_id,
            "url": "https://www.notion.so/page-1",
            "last_edited_time": "2026-07-18T10:00:00Z",
            "last_edited_by": {"id": "user-1"},
            "properties": {
                "Name": {
                    "title": [{"plain_text": "Sprint plan"}],
                }
            },
        }

    async def retrieve_block_children(
        self,
        *,
        access_token: str,
        block_id: str,
        page_size: int = 100,
    ) -> list[dict]:
        assert access_token == "notion-token"
        assert block_id == "page-1"
        assert page_size == 100
        return [
            {
                "type": "paragraph",
                "paragraph": {"rich_text": [{"plain_text": "Decision: ship v1"}]},
            },
            {"type": "to_do", "to_do": {"rich_text": [{"plain_text": "TODO: QA checklist"}]}},
        ]


async def test_sync_notion_integration_fetches_page_and_blocks(session):
    workspace = Workspace(name="Acme")
    session.add(workspace)
    await session.flush()
    project = Project(workspace_id=workspace.id, name="Launch")
    session.add(project)
    await session.flush()
    integration = Integration(
        project_id=project.id,
        provider=Provider.NOTION,
        external_id="page-1",
        name="Sprint plan",
        config={"page_ids": ["page-1"]},
    )
    session.add(integration)
    await session.commit()

    result = await sync_notion_integration(
        session,
        integration.id,
        Settings(notion_access_token="notion-token"),
        FakeNotionClient(),
    )

    assert result.page_ids == ["page-1"]
    assert result.fetched == 1
    assert result.stored == 1
    assert result.duplicates == 0

    duplicate_result = await sync_notion_integration(
        session,
        integration.id,
        Settings(notion_access_token="notion-token"),
        FakeNotionClient(),
    )

    assert duplicate_result.fetched == 1
    assert duplicate_result.stored == 0
    assert duplicate_result.duplicates == 1
