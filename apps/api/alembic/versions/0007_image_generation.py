"""Add IMAGE_ASSET to the prompt_templates.generation_type check constraint
(GenerationType gained an IMAGE_ASSET member for real DALL-E image
generation — see app.ai.image_providers).

Revision ID: 0007_image_generation
Revises: 0006_assets_publishing_auto
Create Date: 2026-07-24

"""
from __future__ import annotations

from alembic import op

revision = "0007_image_generation"
down_revision = "0006_assets_publishing_auto"
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
        "'BLOG_OUTLINE','BLOG_ARTICLE','CTA_VARIATIONS','CONTENT_IDEAS','IMAGE_ASSET')",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_prompt_templates_generation_type_valid", "prompt_templates", type_="check"
    )
    op.create_check_constraint(
        "ck_prompt_templates_generation_type_valid",
        "prompt_templates",
        "generation_type IN ('SOCIAL_POST','REEL_SCRIPT','CAROUSEL','EMAIL',"
        "'BLOG_OUTLINE','BLOG_ARTICLE','CTA_VARIATIONS','CONTENT_IDEAS')",
    )
