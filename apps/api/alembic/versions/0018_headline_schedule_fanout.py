"""Same fan-out redesign as 0017 (story_schedules) applied to
headline_schedules: replace the single (platform, publishing_connection_id)
pair with facebook_connection_id + instagram_connection_id, so one daily
batch of Headline photos fans out to every configured platform at once
instead of needing a separate cycle/upload per platform. Existing rows
already only ever have one platform each, so this is a straight column
migration — no row consolidation needed (unlike 0017).

Revision ID: 0018_headline_schedule_fanout
Revises: 0017_story_schedule_fanout
Create Date: 2026-08-03

"""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0018_headline_schedule_fanout"
down_revision = "0017_story_schedule_fanout"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "headline_schedules",
        sa.Column("facebook_connection_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "headline_schedules",
        sa.Column("instagram_connection_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_headline_schedules_facebook_connection",
        "headline_schedules",
        "publishing_connections",
        ["facebook_connection_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_headline_schedules_instagram_connection",
        "headline_schedules",
        "publishing_connections",
        ["instagram_connection_id"],
        ["id"],
        ondelete="SET NULL",
    )

    conn = op.get_bind()
    conn.execute(
        sa.text(
            "UPDATE headline_schedules SET facebook_connection_id = publishing_connection_id "
            "WHERE platform = 'FACEBOOK' AND publishing_connection_id IS NOT NULL"
        )
    )
    conn.execute(
        sa.text(
            "UPDATE headline_schedules SET instagram_connection_id = publishing_connection_id "
            "WHERE platform = 'INSTAGRAM' AND publishing_connection_id IS NOT NULL"
        )
    )

    op.drop_constraint("fk_headline_schedules_connection", "headline_schedules", type_="foreignkey")
    op.drop_column("headline_schedules", "platform")
    op.drop_column("headline_schedules", "publishing_connection_id")


def downgrade() -> None:
    op.add_column(
        "headline_schedules",
        sa.Column("platform", sa.String(length=32), nullable=False, server_default="FACEBOOK"),
    )
    op.add_column(
        "headline_schedules",
        sa.Column("publishing_connection_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_headline_schedules_connection",
        "headline_schedules",
        "publishing_connections",
        ["publishing_connection_id"],
        ["id"],
        ondelete="SET NULL",
    )
    conn = op.get_bind()
    conn.execute(
        sa.text(
            "UPDATE headline_schedules SET platform = 'FACEBOOK', "
            "publishing_connection_id = COALESCE(facebook_connection_id, instagram_connection_id)"
        )
    )
    op.drop_constraint(
        "fk_headline_schedules_facebook_connection", "headline_schedules", type_="foreignkey"
    )
    op.drop_constraint(
        "fk_headline_schedules_instagram_connection", "headline_schedules", type_="foreignkey"
    )
    op.drop_column("headline_schedules", "facebook_connection_id")
    op.drop_column("headline_schedules", "instagram_connection_id")
