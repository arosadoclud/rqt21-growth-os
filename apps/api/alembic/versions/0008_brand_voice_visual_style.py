"""Add visual_style to brand_voice_profiles (free-text visual identity
directives injected into every IMAGE_ASSET generation for that brand —
background, palette, typography, logo placement, photography style), and
add STORY to the prompt_templates.generation_type check constraint (the
"what kind of content" selector on /generate now offers Reel, foto,
solo-texto, historia).

Revision ID: 0008_brand_voice_visual_style
Revises: 0007_image_generation
Create Date: 2026-07-24

"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0008_brand_voice_visual_style"
down_revision = "0007_image_generation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "brand_voice_profiles",
        sa.Column("visual_style", sa.String(length=4000), nullable=False, server_default=""),
    )
    op.alter_column("brand_voice_profiles", "visual_style", server_default=None)

    op.drop_constraint(
        "ck_prompt_templates_generation_type_valid", "prompt_templates", type_="check"
    )
    op.create_check_constraint(
        "ck_prompt_templates_generation_type_valid",
        "prompt_templates",
        "generation_type IN ('SOCIAL_POST','REEL_SCRIPT','CAROUSEL','EMAIL',"
        "'BLOG_OUTLINE','BLOG_ARTICLE','CTA_VARIATIONS','CONTENT_IDEAS','IMAGE_ASSET','STORY')",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_prompt_templates_generation_type_valid", "prompt_templates", type_="check"
    )
    op.create_check_constraint(
        "ck_prompt_templates_generation_type_valid",
        "prompt_templates",
        "generation_type IN ('SOCIAL_POST','REEL_SCRIPT','CAROUSEL','EMAIL',"
        "'BLOG_OUTLINE','BLOG_ARTICLE','CTA_VARIATIONS','CONTENT_IDEAS','IMAGE_ASSET')",
    )
    op.drop_column("brand_voice_profiles", "visual_style")
