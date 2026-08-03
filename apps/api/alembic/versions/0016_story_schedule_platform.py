"""Allow more than one StorySchedule per (organization, brand) — one per
platform. A brand's Historias cycle can now run on Facebook and Instagram
at the same time, each with its own connection/cadence
(app.workers.story_scheduler.run_once already sweeps every enabled row
regardless of brand, so this is purely a uniqueness relaxation).

Revision ID: 0016_story_schedule_platform
Revises: 0015_story_topic_usage
Create Date: 2026-08-03

"""
from __future__ import annotations

from alembic import op

revision = "0016_story_schedule_platform"
down_revision = "0015_story_topic_usage"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("uq_story_schedules_org_brand", "story_schedules", type_="unique")
    op.create_unique_constraint(
        "uq_story_schedules_org_brand_platform",
        "story_schedules",
        ["organization_id", "brand_id", "platform"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_story_schedules_org_brand_platform", "story_schedules", type_="unique")
    op.create_unique_constraint(
        "uq_story_schedules_org_brand", "story_schedules", ["organization_id", "brand_id"]
    )
