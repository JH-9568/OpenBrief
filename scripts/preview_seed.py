import asyncio
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import create_async_engine

from openbrief.briefs.service import build_daily_revision
from openbrief.config import get_settings
from openbrief.db import SessionFactory
from openbrief.models import Base, Project, ProjectMember, Provider, SourceItemKind, Workspace
from openbrief.schemas import SourceItemCreate
from openbrief.sources.service import store_source_item


async def reset_database() -> None:
    settings = get_settings()
    engine = create_async_engine(str(settings.database_url))
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()


async def seed() -> None:
    await reset_database()

    async with SessionFactory() as session:
        workspace = Workspace(name="OpenBrief Preview")
        session.add(workspace)
        await session.flush()

        project = Project(
            workspace_id=workspace.id,
            name="Brand Renewal Sprint",
            description=(
                "Figma, Notion, Discord에 흩어진 디자인 시안, 회의 결정, 할 일을 "
                "OpenBrief가 읽기 전용으로 모아 정리하는 데모 프로젝트입니다."
            ),
            daily_report_channel_id="discord-preview-channel",
        )
        session.add(project)
        await session.flush()

        members = [
            ProjectMember(
                project_id=project.id,
                display_name="JH",
                email="jh@example.com",
                role="owner",
            ),
            ProjectMember(
                project_id=project.id,
                display_name="Designer",
                email="designer@example.com",
                role="designer",
            ),
            ProjectMember(
                project_id=project.id,
                display_name="Planner",
                email="planner@example.com",
                role="planner",
            ),
        ]
        session.add_all(members)
        await session.commit()

        now = datetime.now(UTC)
        raw_items = [
            SourceItemCreate(
                project_id=project.id,
                provider=Provider.FIGMA,
                external_id=f"preview:figma:{project.id}:hero-v2",
                kind=SourceItemKind.DESIGN_UPDATE,
                title="Figma hero section v2 uploaded",
                body=(
                    "디자이너가 랜딩 페이지 hero v2 시안을 업데이트했습니다. "
                    "CTA는 '무료로 시작하기'와 '데모 보기' 두 안이 남아 있습니다."
                ),
                occurred_at=now - timedelta(hours=5),
                source_url="https://www.figma.com/file/preview",
            ),
            SourceItemCreate(
                project_id=project.id,
                provider=Provider.DISCORD,
                external_id=f"preview:discord:{project.id}:meeting-1",
                kind=SourceItemKind.MEETING_MESSAGE,
                title="Discord meeting decision",
                body=(
                    "회의 결정: 이번 주에는 원본 툴에 자동 반영하지 않고, "
                    "OpenBrief에서 정리본을 다 같이 승인한 뒤 각 담당자가 반영합니다. "
                    "담당자: Planner는 기획 문서 정리, Designer는 CTA 시안 확정."
                ),
                occurred_at=now - timedelta(hours=3),
                source_url="https://discord.com/channels/preview/preview/1",
            ),
            SourceItemCreate(
                project_id=project.id,
                provider=Provider.NOTION,
                external_id=f"preview:notion:{project.id}:tasks-1",
                kind=SourceItemKind.TASK_CHANGE,
                title="Notion task deadline changed",
                body=(
                    "랜딩 페이지 카피 확정 작업의 기한이 금요일로 변경되었습니다. "
                    "담당자는 Planner이며 현재 상태는 진행 중입니다."
                ),
                occurred_at=now - timedelta(hours=2),
                source_url="https://www.notion.so/preview",
            ),
            SourceItemCreate(
                project_id=project.id,
                provider=Provider.FIGMA,
                external_id=f"preview:figma:{project.id}:comment-cta",
                kind=SourceItemKind.DESIGN_COMMENT,
                title="Figma CTA copy comment",
                body="TODO: CTA 문구를 목요일 오전까지 확정해야 개발 착수가 가능합니다.",
                occurred_at=now - timedelta(minutes=40),
                source_url="https://www.figma.com/file/preview?node-id=1-2",
            ),
        ]

        source_items = []
        for item in raw_items:
            source_item, _ = await store_source_item(session, item)
            source_items.append(source_item)

        revision = await build_daily_revision(session, project.id, source_items)
        print(f"PROJECT_ID={project.id}")
        print(f"BRIEF_REVISION_ID={revision.id}")
        print(f"DASHBOARD=/dashboard/projects/{project.id}")


if __name__ == "__main__":
    asyncio.run(seed())
