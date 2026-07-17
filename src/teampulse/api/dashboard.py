import html
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from teampulse.db import get_session
from teampulse.models import BriefRevision, Project, SourceItem

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/projects/{project_id}", response_class=HTMLResponse)
async def project_dashboard(
    project_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> HTMLResponse:
    project = await session.get(Project, project_id)
    if project is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found")

    brief = await latest_brief(session, project_id)
    source_items = await latest_source_items(session, project_id)
    return HTMLResponse(render_project_dashboard(project, brief, source_items))


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


def render_project_dashboard(
    project: Project,
    brief: BriefRevision | None,
    source_items: list[SourceItem],
) -> str:
    brief_html = render_brief(brief) if brief else "<p>No brief revisions yet.</p>"
    sources_html = "\n".join(render_source_item(item) for item in source_items)
    if not sources_html:
        sources_html = "<p>No source evidence yet.</p>"
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>TeamPulse - {html.escape(project.name)}</title>
  <style>
    body {{ font-family: system-ui, sans-serif; margin: 32px; color: #17202a; }}
    main {{ max-width: 1080px; margin: 0 auto; }}
    section {{ border-top: 1px solid #d8dee4; padding: 24px 0; }}
    article {{ border: 1px solid #d8dee4; border-radius: 6px; padding: 12px; margin: 10px 0; }}
    .muted {{ color: #667085; }}
    .claim {{ margin: 8px 0; }}
    code {{ background: #f6f8fa; padding: 2px 4px; border-radius: 4px; }}
  </style>
</head>
<body>
  <main>
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
  </main>
</body>
</html>"""


def render_brief(brief: BriefRevision) -> str:
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
        f"{''.join(sections)}"
    )


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
