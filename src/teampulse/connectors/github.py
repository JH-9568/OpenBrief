from datetime import UTC, datetime
from typing import Any

import httpx


class GitHubClient:
    base_url = "https://api.github.com"

    async def fetch_repo_activity(
        self,
        *,
        access_token: str | None,
        owner: str,
        repo: str,
        since: str | None = None,
        limit: int = 50,
    ) -> dict[str, list[dict[str, Any]]]:
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if access_token:
            headers["Authorization"] = f"Bearer {access_token}"

        params: dict[str, Any] = {"per_page": min(limit, 100)}
        if since:
            params["since"] = since

        async with httpx.AsyncClient(base_url=self.base_url, timeout=20, headers=headers) as client:
            issues_response = await client.get(
                f"/repos/{owner}/{repo}/issues",
                params={**params, "state": "all"},
            )
            issues_response.raise_for_status()

            commits_response = await client.get(
                f"/repos/{owner}/{repo}/commits",
                params=params,
            )
            commits_response.raise_for_status()

            runs_response = await client.get(
                f"/repos/{owner}/{repo}/actions/runs",
                params=params,
            )
            runs_response.raise_for_status()

        issues = issues_response.json()
        workflow_runs = runs_response.json().get("workflow_runs", [])
        return {
            "issues": [issue for issue in issues if "pull_request" not in issue],
            "pulls": [issue for issue in issues if "pull_request" in issue],
            "commits": commits_response.json(),
            "workflow_runs": workflow_runs,
        }


def parse_github_dt(value: str | None) -> datetime:
    if not value:
        return datetime.now(UTC)
    return datetime.fromisoformat(value.replace("Z", "+00:00"))
