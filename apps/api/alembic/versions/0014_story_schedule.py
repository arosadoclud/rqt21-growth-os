"""Add story_schedules — per-brand config + running state for the
automatic "Historias" content cycle (app.workers.story_scheduler):
short, conversational, follower-connection content (questions, polls,
behind-the-scenes) generated every interval_minutes (default 40) up to
max_per_day times. Same "human uploads the photo, publish_due fires it"
pattern as headline_schedules (0013), but a separate table since the
cadence unit (minutes, not hours) and topic bank are different in kind,
not just configuration.

Revision ID: 0014_story_schedule
Revises: 0013_headline_schedule
Create Date: 2026-08-03

"""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0014_story_schedule"
down_revision = "0013_headline_schedule"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "story_schedules",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("public_id", sa.String(length=32), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("brand_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("publishing_connection_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("platform", sa.String(length=32), nullable=False, server_default="INSTAGRAM"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("interval_minutes", sa.Integer(), nullable=False, server_default="40"),
        sa.Column("max_per_day", sa.Integer(), nullable=False, server_default="12"),
        sa.Column("topic_rotation_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("daily_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("daily_count_date", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_story_schedules"),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"],
            name="fk_story_schedules_org", ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["brand_id"], ["brands.id"],
            name="fk_story_schedules_brand", ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["publishing_connection_id"], ["publishing_connections.id"],
            name="fk_story_schedules_connection", ondelete="SET NULL",
        ),
        sa.UniqueConstraint(
            "organization_id", "brand_id", name="uq_story_schedules_org_brand"
        ),
        sa.UniqueConstraint("public_id", name="uq_story_schedules_public_id"),
    )
    op.create_index(
        "ix_story_schedules_organization_id", "story_schedules", ["organization_id"]
    )
    op.create_index("ix_story_schedules_brand_id", "story_schedules", ["brand_id"])
    op.create_index("ix_story_schedules_public_id", "story_schedules", ["public_id"])


def downgrade() -> None:
    op.drop_index("ix_story_schedules_public_id", table_name="story_schedules")
    op.drop_index("ix_story_schedules_brand_id", table_name="story_schedules")
    op.drop_index("ix_story_schedules_organization_id", table_name="story_schedules")
    op.drop_table("story_schedules")
