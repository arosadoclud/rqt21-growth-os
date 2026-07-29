"""Add VOICE_OVER to prompt_templates.generation_type check constraint —
a "just the narration audio" generation type: writes a script (same text
pipeline as REEL_SCRIPT/VIDEO_ASSET) and synthesizes it with TTS into an
MP3 Asset, skipping the image/scene/ffmpeg assembly steps VIDEO_ASSET does.

Revision ID: 0011_voice_over_generation
Revises: 0010_generation_job_stage
Create Date: 2026-07-29

"""
from __future__ import annotations

from alembic import op

revision = "0011_voice_over_generation"
down_revision = "0010_generation_job_stage"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint(
        "ck_prompt_templates_generation_type_valid", "prompt_templates", type_="check"
    )
    op.create_check_constraint(
        "ck_prompt_templates_generation_type_valid",
        "prompt_templates",
        "generation_type IN ('SOCIAL_POST','REEL_SCRIPT','CAROUSEL','EMAIL',"
        "'BLOG_OUTLINE','BLOG_ARTICLE','CTA_VARIATIONS','CONTENT_IDEAS','IMAGE_ASSET',"
        "'STORY','VIDEO_ASSET','VOICE_OVER')",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_prompt_templates_generation_type_valid", "prompt_templates", type_="check"
    )
    op.create_check_constraint(
        "ck_prompt_templates_generation_type_valid",
        "prompt_templates",
        "generation_type IN ('SOCIAL_POST','REEL_SCRIPT','CAROUSEL','EMAIL',"
        "'BLOG_OUTLINE','BLOG_ARTICLE','CTA_VARIATIONS','CONTENT_IDEAS','IMAGE_ASSET',"
        "'STORY','VIDEO_ASSET')",
    )
