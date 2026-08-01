"""Add headline_schedules — per-brand config + running state for the
automatic "Headline" content cycle (app.workers.headline_scheduler):
generates a keto-recipe image+text post every interval_hours and, only if
the auto-approval council clears it, publishes it to the configured
connection. Disabled by default; a human must explicitly opt in with a
real connection chosen.

Revision ID: 0013_headline_schedule
Revises: 0012_content_review_status
Create Date: 2026-07-31

"""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0013_headline_schedule"
down_revision = "0012_content_review_status"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "headline_schedules",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("public_id", sa.String(length=32), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("brand_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("publishing_connection_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("platform", sa.String(length=32), nullable=False, server_default="FACEBOOK"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("interval_hours", sa.Integer(), nullable=False, server_default="2"),
        sa.Column("max_per_day", sa.Integer(), nullable=False, server_default="12"),
        sa.Column("topic_rotation_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("daily_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("daily_count_date", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_headline_schedules"),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"],
            name="fk_headline_schedules_org", ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["brand_id"], ["brands.id"],
            name="fk_headline_schedules_brand", ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["publishing_connection_id"], ["publishing_connections.id"],
            name="fk_headline_schedules_connection", ondelete="SET NULL",
        ),
        sa.UniqueConstraint(
            "organization_id", "brand_id", name="uq_headline_schedules_org_brand"
        ),
        sa.UniqueConstraint("public_id", name="uq_headline_schedules_public_id"),
    )
    op.create_index(
        "ix_headline_schedules_organization_id", "headline_schedules", ["organization_id"]
    )
    op.create_index("ix_headline_schedules_brand_id", "headline_schedules", ["brand_id"])
    op.create_index("ix_headline_schedules_public_id", "headline_schedules", ["public_id"])


def downgrade() -> None:
    op.drop_index("ix_headline_schedules_public_id", table_name="headline_schedules")
    op.drop_index("ix_headline_schedules_brand_id", table_name="headline_schedules")
    op.drop_index("ix_headline_schedules_organization_id", table_name="headline_schedules")
    op.drop_table("headline_schedules")
