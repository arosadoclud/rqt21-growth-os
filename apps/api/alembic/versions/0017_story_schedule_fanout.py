"""Replace StorySchedule's single (platform, publishing_connection_id)
pair with two dedicated connection columns (facebook_connection_id,
instagram_connection_id) — a brand's Historias cycle now generates ONE
daily batch and fans out to every configured platform at once (one photo
upload publishes to both simultaneously), instead of running two
completely independent per-platform cycles (0016) that each needed their
own separate photo upload.

Consolidates any existing per-platform rows for the same
(organization, brand) into a single row (the earliest-created one is
kept), copying each platform's connection onto its new column before the
extra rows are deleted and the old org+brand+platform uniqueness is
replaced with plain org+brand again.

Revision ID: 0017_story_schedule_fanout
Revises: 0016_story_schedule_platform
Create Date: 2026-08-03

"""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0017_story_schedule_fanout"
down_revision = "0016_story_schedule_platform"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "story_schedules",
        sa.Column("facebook_connection_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "story_schedules",
        sa.Column("instagram_connection_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_story_schedules_facebook_connection",
        "story_schedules",
        "publishing_connections",
        ["facebook_connection_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_story_schedules_instagram_connection",
        "story_schedules",
        "publishing_connections",
        ["instagram_connection_id"],
        ["id"],
        ondelete="SET NULL",
    )

    conn = op.get_bind()
    conn.execute(
        sa.text(
            """
            WITH keepers AS (
                SELECT DISTINCT ON (organization_id, brand_id) id, organization_id, brand_id
                FROM story_schedules
                ORDER BY organization_id, brand_id, created_at ASC
            )
            UPDATE story_schedules
            SET facebook_connection_id = src.publishing_connection_id
            FROM story_schedules src
            JOIN keepers ON keepers.organization_id = src.organization_id
                AND keepers.brand_id = src.brand_id
            WHERE story_schedules.id = keepers.id AND src.platform = 'FACEBOOK'
            """
        )
    )
    conn.execute(
        sa.text(
            """
            WITH keepers AS (
                SELECT DISTINCT ON (organization_id, brand_id) id, organization_id, brand_id
                FROM story_schedules
                ORDER BY organization_id, brand_id, created_at ASC
            )
            UPDATE story_schedules
            SET instagram_connection_id = src.publishing_connection_id
            FROM story_schedules src
            JOIN keepers ON keepers.organization_id = src.organization_id
                AND keepers.brand_id = src.brand_id
            WHERE story_schedules.id = keepers.id AND src.platform = 'INSTAGRAM'
            """
        )
    )
    conn.execute(
        sa.text(
            """
            WITH keepers AS (
                SELECT DISTINCT ON (organization_id, brand_id) id
                FROM story_schedules
                ORDER BY organization_id, brand_id, created_at ASC
            )
            DELETE FROM story_schedules WHERE id NOT IN (SELECT id FROM keepers)
            """
        )
    )

    op.drop_constraint("uq_story_schedules_org_brand_platform", "story_schedules", type_="unique")
    op.create_unique_constraint(
        "uq_story_schedules_org_brand", "story_schedules", ["organization_id", "brand_id"]
    )
    op.drop_column("story_schedules", "platform")
    op.drop_column("story_schedules", "publishing_connection_id")


def downgrade() -> None:
    op.add_column(
        "story_schedules",
        sa.Column("platform", sa.String(length=32), nullable=False, server_default="INSTAGRAM"),
    )
    op.add_column(
        "story_schedules",
        sa.Column("publishing_connection_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_story_schedules_connection",
        "story_schedules",
        "publishing_connections",
        ["publishing_connection_id"],
        ["id"],
        ondelete="SET NULL",
    )
    conn = op.get_bind()
    conn.execute(
        sa.text(
            "UPDATE story_schedules SET platform = 'INSTAGRAM', "
            "publishing_connection_id = COALESCE(instagram_connection_id, facebook_connection_id)"
        )
    )
    op.drop_constraint("uq_story_schedules_org_brand", "story_schedules", type_="unique")
    op.create_unique_constraint(
        "uq_story_schedules_org_brand_platform",
        "story_schedules",
        ["organization_id", "brand_id", "platform"],
    )
    op.drop_constraint("fk_story_schedules_facebook_connection", "story_schedules", type_="foreignkey")
    op.drop_constraint("fk_story_schedules_instagram_connection", "story_schedules", type_="foreignkey")
    op.drop_column("story_schedules", "facebook_connection_id")
    op.drop_column("story_schedules", "instagram_connection_id")
