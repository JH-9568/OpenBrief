import uuid
from datetime import UTC, datetime
from typing import Any, Protocol

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from openbrief.config import Settings
from openbrief.connectors.github import GitHubClient, parse_github_dt
from openbrief.integrations.discord import decrypt_credentials
from openbrief.models import Integration, Provider, SourceItemKind
from openbrief.schemas import SourceItemCreate
from openbrief.sources.service import store_source_item


class GitHubApiClient(Protocol):
    async def fetch_repo_activity(
        self,
        *,
        access_token: str | None,
        owner: str,
        repo: str,
        since: str | None = None,
        limit: int = 50,
    ) -> dict[str, list[dict[str, Any]]]: ...


class GitHubSyncResult(BaseModel):
    integration_id: uuid.UUID
    repository: str
    fetched: int
    stored: int
    duplicates: int
    last_synced_at: str


async def sync_github_integration(
    session: AsyncSession,
    integration_id: uuid.UUID,
    settings: Settings,
    client: GitHubApiClient | None = None,
) -> GitHubSyncResult:
    integration = await session.get(Integration, integration_id)
    if integration is None:
        raise ValueError("Integration not found")
    if integration.provider != Provider.GITHUB:
        raise ValueError("Integration is not a GitHub integration")

    config = dict(integration.config)
    owner, repo = parse_repository(config.get("repository") or integration.external_id)
    credentials = (
        decrypt_credentials(integration, settings) if integration.encrypted_credentials else {}
    )
    access_token = credentials.get("access_token")
    since = config.get("last_synced_at")
    limit = int(config.get("sync_limit", 50))

    github_client = client or GitHubClient()
    activity = await github_client.fetch_repo_activity(
        access_token=access_token,
        owner=owner,
        repo=repo,
        since=since,
        limit=limit,
    )
    items = github_source_items(integration, owner, repo, activity)

    stored = 0
    duplicates = 0
    for item in items:
        _, duplicate = await store_source_item(session, item)
        stored += int(not duplicate)
        duplicates += int(duplicate)

    last_synced_at = datetime.now(UTC).isoformat()
    checkpoint = await session.get(Integration, integration_id)
    if checkpoint is None:
        raise ValueError("Integration not found")
    checkpoint.config = {
        **config,
        "repository": f"{owner}/{repo}",
        "last_synced_at": last_synced_at,
    }
    await session.commit()

    return GitHubSyncResult(
        integration_id=integration_id,
        repository=f"{owner}/{repo}",
        fetched=len(items),
        stored=stored,
        duplicates=duplicates,
        last_synced_at=last_synced_at,
    )


def parse_repository(value: str) -> tuple[str, str]:
    normalized = value.strip().removeprefix("https://github.com/").removesuffix(".git")
    parts = [part for part in normalized.split("/") if part]
    if len(parts) < 2:
        raise ValueError("GitHub repository must be owner/repo or a GitHub repository URL")
    return parts[0], parts[1]


def github_source_items(
    integration: Integration,
    owner: str,
    repo: str,
    activity: dict[str, list[dict[str, Any]]],
) -> list[SourceItemCreate]:
    items: list[SourceItemCreate] = []
    for issue in activity.get("issues", []):
        number = issue.get("number")
        items.append(
            SourceItemCreate(
                project_id=integration.project_id,
                integration_id=integration.id,
                provider=Provider.GITHUB,
                external_id=f"github:issue:{owner}/{repo}:{number}:{issue.get('updated_at')}",
                kind=SourceItemKind.TASK_CHANGE,
                title=f"GitHub issue #{number}: {issue.get('title', '')}",
                body=issue.get("body") or "",
                source_url=issue.get("html_url"),
                occurred_at=parse_github_dt(issue.get("updated_at") or issue.get("created_at")),
                actor=issue.get("user") or {},
                metadata={
                    "repository": f"{owner}/{repo}",
                    "number": number,
                    "state": issue.get("state"),
                },
                raw_payload=issue,
            )
        )
    for pull in activity.get("pulls", []):
        number = pull.get("number")
        items.append(
            SourceItemCreate(
                project_id=integration.project_id,
                integration_id=integration.id,
                provider=Provider.GITHUB,
                external_id=f"github:pull:{owner}/{repo}:{number}:{pull.get('updated_at')}",
                kind=SourceItemKind.TASK_CHANGE,
                title=f"GitHub PR #{number}: {pull.get('title', '')}",
                body=pull.get("body") or "",
                source_url=pull.get("html_url"),
                occurred_at=parse_github_dt(pull.get("updated_at") or pull.get("created_at")),
                actor=pull.get("user") or {},
                metadata={
                    "repository": f"{owner}/{repo}",
                    "number": number,
                    "state": pull.get("state"),
                },
                raw_payload=pull,
            )
        )
    for commit in activity.get("commits", []):
        sha = str(commit.get("sha", ""))[:12]
        payload = commit.get("commit") or {}
        items.append(
            SourceItemCreate(
                project_id=integration.project_id,
                integration_id=integration.id,
                provider=Provider.GITHUB,
                external_id=f"github:commit:{owner}/{repo}:{commit.get('sha')}",
                kind=SourceItemKind.TASK_CHANGE,
                title=f"GitHub commit {sha}",
                body=payload.get("message") or "",
                source_url=commit.get("html_url"),
                occurred_at=parse_github_dt(
                    (payload.get("committer") or {}).get("date")
                    or (payload.get("author") or {}).get("date")
                ),
                actor=commit.get("author") or payload.get("author") or {},
                metadata={"repository": f"{owner}/{repo}", "sha": commit.get("sha")},
                raw_payload=commit,
            )
        )
    for run in activity.get("workflow_runs", []):
        run_id = run.get("id")
        items.append(
            SourceItemCreate(
                project_id=integration.project_id,
                integration_id=integration.id,
                provider=Provider.GITHUB,
                external_id=f"github:workflow_run:{owner}/{repo}:{run_id}:{run.get('updated_at')}",
                kind=SourceItemKind.TASK_CHANGE,
                title=(
                    f"GitHub CI {run.get('name', 'workflow')}: "
                    f"{run.get('conclusion') or run.get('status')}"
                ),
                body=f"Branch: {run.get('head_branch')}, event: {run.get('event')}",
                source_url=run.get("html_url"),
                occurred_at=parse_github_dt(run.get("updated_at") or run.get("created_at")),
                actor=run.get("actor") or {},
                metadata={
                    "repository": f"{owner}/{repo}",
                    "run_id": run_id,
                    "status": run.get("status"),
                    "conclusion": run.get("conclusion"),
                },
                raw_payload=run,
            )
        )
    return items
