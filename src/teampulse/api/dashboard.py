import html
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from teampulse.briefs.service import approval_state
from teampulse.db import get_session
from teampulse.models import BriefRevision, Project, ProjectMember, SourceItem
from teampulse.schemas import ApprovalRead

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("", response_class=HTMLResponse)
async def dashboard_home(session: AsyncSession = Depends(get_session)) -> HTMLResponse:
    result = await session.execute(select(Project).order_by(Project.created_at.desc()))
    projects = list(result.scalars().all())
    return HTMLResponse(render_dashboard_home(projects))


@router.get("/projects/{project_id}", response_class=HTMLResponse)
async def project_dashboard(
    project_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> HTMLResponse:
    project = await session.get(Project, project_id)
    if project is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found")

    brief = await latest_brief(session, project_id)
    state = await approval_state(session, brief) if brief else None
    members = await active_members(session, project_id)
    source_items = await latest_source_items(session, project_id)
    return HTMLResponse(render_project_dashboard(project, brief, state, members, source_items))


def render_dashboard_home(projects: list[Project]) -> str:
    project_rows = "\n".join(
        "<article>"
        f"<h2><a href='/dashboard/projects/{project.id}'>{html.escape(project.name)}</a></h2>"
        f"<p>{html.escape(project.description or '')}</p>"
        f"<p class='muted'>{'active' if project.active else 'inactive'}</p>"
        "</article>"
        for project in projects
    )
    if not project_rows:
        project_rows = "<p>No projects yet.</p>"
    return html_page("TeamPulse", "<h1>TeamPulse</h1><section>" + project_rows + "</section>")


async def latest_brief(session: AsyncSession, project_id: uuid.UUID) -> BriefRevision | None:
    result = await session.execute(
        select(BriefRevision)
        .where(BriefRevision.project_id == project_id)
        .order_by(BriefRevision.version.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def latest_source_items(session: AsyncSession, project_id: uuid.UUID) -> list[SourceItem]:
    result = await session.execute(
        select(SourceItem)
        .where(SourceItem.project_id == project_id)
        .order_by(SourceItem.occurred_at.desc())
        .limit(25)
    )
    return list(result.scalars().all())


async def active_members(session: AsyncSession, project_id: uuid.UUID) -> list[ProjectMember]:
    result = await session.execute(
        select(ProjectMember)
        .where(ProjectMember.project_id == project_id, ProjectMember.active.is_(True))
        .order_by(ProjectMember.display_name.asc())
    )
    return list(result.scalars().all())


def render_project_dashboard(
    project: Project,
    brief: BriefRevision | None,
    state: ApprovalRead | None,
    members: list[ProjectMember],
    source_items: list[SourceItem],
) -> str:
    brief_html = render_brief(brief, state, members) if brief else "<p>No brief revisions yet.</p>"
    sources_html = "\n".join(render_source_item(item) for item in source_items)
    if not sources_html:
        sources_html = "<p>No source evidence yet.</p>"
    body = f"""
    <p><a href="/dashboard">Projects</a></p>
    <h1>{html.escape(project.name)}</h1>
    <p class="muted">{html.escape(project.description or "")}</p>
    <section>
      <h2>Latest Brief</h2>
      {brief_html}
    </section>
    <section>
      <h2>Source Evidence</h2>
      {sources_html}
    </section>
    """
    return html_page(f"TeamPulse - {project.name}", body)


def html_page(title: str, body: str) -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(title)}</title>
  <style>
    body {{
      font-family: system-ui, sans-serif;
      margin: 32px;
      color: #17202a;
      background: #fbfcfe;
    }}
    main {{ max-width: 1080px; margin: 0 auto; }}
    section {{ border-top: 1px solid #d8dee4; padding: 24px 0; }}
    article {{
      background: white;
      border: 1px solid #d8dee4;
      border-radius: 6px;
      padding: 12px;
      margin: 10px 0;
    }}
    button, select, input {{ font: inherit; padding: 8px; }}
    button {{ cursor: pointer; }}
    .muted {{ color: #667085; }}
    .claim {{ margin: 8px 0; }}
    code {{ background: #f6f8fa; padding: 2px 4px; border-radius: 4px; }}
    .toolbar {{ display: flex; gap: 8px; flex-wrap: wrap; align-items: center; margin: 12px 0; }}
  </style>
</head>
<body>
  <main>
    {body}
  </main>
</body>
</html>"""


def render_brief(
    brief: BriefRevision,
    state: ApprovalRead | None,
    members: list[ProjectMember],
) -> str:
    approval_html = render_approval_panel(brief, state, members)
    sections = []
    for section in brief.content.get("sections", []):
        claims = "\n".join(
            "<li class='claim'>"
            f"{html.escape(claim.get('text', ''))} "
            f"<code>{html.escape(claim.get('status', ''))}</code>"
            "</li>"
            for claim in section.get("claims", [])
        )
        if not claims:
            claims = "<li class='muted'>No claims.</li>"
        sections.append(
            f"<article><h3>{html.escape(section.get('title', section.get('key', 'Section')))}</h3>"
            f"<ul>{claims}</ul></article>"
        )
    return (
        f"<p>Revision v{brief.version} "
        f"<code>{html.escape(brief.status.value)}</code></p>"
        f"{approval_html}"
        f"{''.join(sections)}"
    )


def render_approval_panel(
    brief: BriefRevision,
    state: ApprovalRead | None,
    members: list[ProjectMember],
) -> str:
    if state is None:
        return ""
    member_options = "\n".join(
        f"<option value='{member.id}'>{html.escape(member.display_name)} "
        f"({html.escape(member.email)})</option>"
        for member in members
    )
    pending_member_ids = html.escape(", ".join(state.pending_member_ids) or "none")
    return f"""
    <article>
      <h3>Approval</h3>
      <p>{state.approved_count} / {state.required_count} approvals complete.</p>
      <p class="muted">Pending member IDs: {pending_member_ids}</p>
      <div class="toolbar">
        <select id="member-id">{member_options}</select>
        <input id="api-key" placeholder="API key if configured">
        <button onclick="approveBrief()">Approve revision</button>
      </div>
      <p id="approval-result" class="muted"></p>
    </article>
    <script>
      async function approveBrief() {{
        const memberId = document.getElementById('member-id').value;
        const apiKey = document.getElementById('api-key').value;
        const headers = {{'X-TeamPulse-Member-ID': memberId}};
        if (apiKey) headers['X-TeamPulse-API-Key'] = apiKey;
        const response = await fetch(
          '/api/v1/projects/{brief.project_id}/briefs/{brief.id}/approve',
          {{method: 'POST', headers}}
        );
        document.getElementById('approval-result').textContent = response.ok
          ? 'Approved. Refresh to see the updated state.'
          : 'Approval failed: ' + await response.text();
      }}
    </script>
    """


def render_source_item(item: SourceItem) -> str:
    source_url = html.escape(item.source_url or "")
    link = f"<a href='{source_url}'>{source_url}</a>" if source_url else ""
    return (
        "<article>"
        f"<h3>{html.escape(item.title)}</h3>"
        f"<p><code>{html.escape(item.provider.value)}</code> "
        f"<code>{html.escape(item.kind.value)}</code></p>"
        f"<p>{html.escape(item.body[:500])}</p>"
        f"<p class='muted'>{link}</p>"
        "</article>"
    )
