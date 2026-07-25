"""Add VIDEO_ASSET to prompt_templates.generation_type check constraint —
the new "Video" card on /generate (script via Claude, one image per scene
via DALL-E, voiceover via OpenAI TTS, assembled into an MP4 with ffmpeg).

Revision ID: 0009_video_generation
Revises: 0008_brand_voice_visual_style
Create Date: 2026-07-25

"""
from __future__ import annotations

from alembic import op

revision = "0009_video_generation"
down_revision = "0008_brand_voice_visual_style"
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
        "'STORY','VIDEO_ASSET')",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_prompt_templates_generation_type_valid", "prompt_templates", type_="check"
    )
    op.create_check_constraint(
        "ck_prompt_templates_generation_type_valid",
        "prompt_templates",
        "generation_type IN ('SOCIAL_POST','REEL_SCRIPT','CAROUSEL','EMAIL',"
        "'BLOG_OUTLINE','BLOG_ARTICLE','CTA_VARIATIONS','CONTENT_IDEAS','IMAGE_ASSET','STORY')",
    )
