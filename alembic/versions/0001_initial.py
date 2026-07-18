"""initial OpenBrief schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-07-18
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

provider_enum = sa.Enum("FIGMA", "NOTION", "DISCORD", "GITHUB", "SLACK", native_enum=False)


def upgrade() -> None:
    op.create_table(
        "workspaces",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("timezone", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "projects",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("workspace_id", sa.Uuid(), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("daily_report_channel_id", sa.String(length=255), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_projects_workspace_id", "projects", ["workspace_id"])
    op.create_table(
        "project_members",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("display_name", sa.String(length=120), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=80), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("project_id", "email", name="uq_project_member_email"),
    )
    op.create_index("ix_project_members_project_id", "project_members", ["project_id"])
    op.create_table(
        "integrations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("provider", provider_enum, nullable=False),
        sa.Column("external_id", sa.String(length=255), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("encrypted_credentials", sa.LargeBinary(), nullable=True),
        sa.Column("config", sa.JSON(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("ACTIVE", "PAUSED", "ERROR", native_enum=False),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "project_id",
            "provider",
            "external_id",
            name="uq_project_provider_ext",
        ),
    )
    op.create_index("ix_integrations_project_id", "integrations", ["project_id"])
    op.create_index("ix_integrations_provider", "integrations", ["provider"])
    op.create_index("ix_integrations_status", "integrations", ["status"])
    op.create_table(
        "source_items",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("integration_id", sa.Uuid(), sa.ForeignKey("integrations.id"), nullable=True),
        sa.Column("provider", provider_enum, nullable=False),
        sa.Column("external_id", sa.String(length=500), nullable=False),
        sa.Column(
            "kind",
            sa.Enum(
                "DESIGN_UPDATE",
                "DESIGN_COMMENT",
                "PLANNING_DOC",
                "TASK_CHANGE",
                "MEETING_MESSAGE",
                "COMMAND",
                "UNKNOWN",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("actor", sa.JSON(), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("raw_payload", sa.JSON(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("RAW", "NORMALIZED", "FAILED", native_enum=False),
            nullable=False,
        ),
        sa.Column("error", sa.Text(), nullable=True),
        sa.UniqueConstraint("provider", "external_id", name="uq_source_provider_external"),
    )
    op.create_index("ix_source_items_project_id", "source_items", ["project_id"])
    op.create_index("ix_source_items_integration_id", "source_items", ["integration_id"])
    op.create_index("ix_source_items_provider", "source_items", ["provider"])
    op.create_index("ix_source_items_occurred_at", "source_items", ["occurred_at"])
    op.create_index("ix_source_items_status", "source_items", ["status"])
    op.create_table(
        "brief_revisions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("revision_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "status",
            sa.Enum("DRAFT", "PENDING_APPROVAL", "CONFIRMED", "SUPERSEDED", native_enum=False),
            nullable=False,
        ),
        sa.Column("content", sa.JSON(), nullable=False),
        sa.Column("approver_snapshot", sa.JSON(), nullable=False),
        sa.Column("source_item_ids", sa.JSON(), nullable=False),
        sa.Column("created_by", sa.String(length=120), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("project_id", "revision_hash", name="uq_project_revision_hash"),
    )
    op.create_index("ix_brief_revisions_project_id", "brief_revisions", ["project_id"])
    op.create_index("ix_brief_revisions_revision_hash", "brief_revisions", ["revision_hash"])
    op.create_index("ix_brief_revisions_status", "brief_revisions", ["status"])
    op.create_table(
        "brief_approvals",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "brief_revision_id",
            sa.Uuid(),
            sa.ForeignKey("brief_revisions.id"),
            nullable=False,
        ),
        sa.Column(
            "project_member_id",
            sa.Uuid(),
            sa.ForeignKey("project_members.id"),
            nullable=False,
        ),
        sa.Column("revision_hash", sa.String(length=64), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("brief_revision_id", "project_member_id", name="uq_revision_member"),
    )
    op.create_index(
        "ix_brief_approvals_brief_revision_id",
        "brief_approvals",
        ["brief_revision_id"],
    )
    op.create_table(
        "notification_deliveries",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column(
            "brief_revision_id",
            sa.Uuid(),
            sa.ForeignKey("brief_revisions.id"),
            nullable=False,
        ),
        sa.Column("channel", sa.String(length=80), nullable=False),
        sa.Column("external_channel_id", sa.String(length=255), nullable=False),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.UniqueConstraint("project_id", "brief_revision_id", "channel", name="uq_daily_notice"),
    )
    op.create_index(
        "ix_notification_deliveries_project_id",
        "notification_deliveries",
        ["project_id"],
    )


def downgrade() -> None:
    op.drop_table("notification_deliveries")
    op.drop_table("brief_approvals")
    op.drop_table("brief_revisions")
    op.drop_table("source_items")
    op.drop_table("integrations")
    op.drop_table("project_members")
    op.drop_table("projects")
    op.drop_table("workspaces")
