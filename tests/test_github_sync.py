from teampulse.config import Settings
from teampulse.integrations.github import parse_repository, sync_github_integration
from teampulse.models import Integration, Project, Provider, Workspace


class FakeGitHubClient:
    async def fetch_repo_activity(
        self,
        *,
        access_token: str | None,
        owner: str,
        repo: str,
        since: str | None = None,
        limit: int = 50,
    ) -> dict:
        assert access_token is None
        assert owner == "JH-9568"
        assert repo == "TeamPulse"
        assert since is None
        assert limit == 50
        return {
            "issues": [
                {
                    "number": 1,
                    "title": "Setup TeamPulse",
                    "body": "Track project context",
                    "updated_at": "2026-07-18T10:00:00Z",
                    "html_url": "https://github.com/JH-9568/TeamPulse/issues/1",
                    "state": "open",
                    "user": {"login": "jh"},
                }
            ],
            "pulls": [
                {
                    "number": 2,
                    "title": "Add dashboard",
                    "body": "UI work",
                    "updated_at": "2026-07-18T11:00:00Z",
                    "html_url": "https://github.com/JH-9568/TeamPulse/pull/2",
                    "state": "open",
                    "user": {"login": "jh"},
                }
            ],
            "commits": [
                {
                    "sha": "abcdef1234567890",
                    "html_url": "https://github.com/JH-9568/TeamPulse/commit/abcdef",
                    "commit": {
                        "message": "Initial commit",
                        "committer": {"date": "2026-07-18T12:00:00Z"},
                    },
                    "author": {"login": "jh"},
                }
            ],
            "workflow_runs": [
                {
                    "id": 100,
                    "name": "CI",
                    "status": "completed",
                    "conclusion": "success",
                    "updated_at": "2026-07-18T13:00:00Z",
                    "html_url": "https://github.com/JH-9568/TeamPulse/actions/runs/100",
                    "head_branch": "main",
                    "event": "push",
                    "actor": {"login": "jh"},
                }
            ],
        }


async def test_sync_github_integration_fetches_repo_activity(session):
    workspace = Workspace(name="Acme")
    session.add(workspace)
    await session.flush()
    project = Project(workspace_id=workspace.id, name="Launch")
    session.add(project)
    await session.flush()
    integration = Integration(
        project_id=project.id,
        provider=Provider.GITHUB,
        external_id="JH-9568/TeamPulse",
        name="TeamPulse repo",
        config={"repository": "JH-9568/TeamPulse"},
    )
    session.add(integration)
    await session.commit()

    result = await sync_github_integration(
        session,
        integration.id,
        Settings(),
        FakeGitHubClient(),
    )

    assert result.repository == "JH-9568/TeamPulse"
    assert result.fetched == 4
    assert result.stored == 4
    assert result.duplicates == 0


def test_parse_repository_accepts_url_and_owner_repo():
    assert parse_repository("JH-9568/TeamPulse") == ("JH-9568", "TeamPulse")
    assert parse_repository("https://github.com/JH-9568/TeamPulse.git") == (
        "JH-9568",
        "TeamPulse",
    )
