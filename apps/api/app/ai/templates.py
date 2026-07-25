"""Prompt template lookup.

Organizations may eventually override system templates (not built in this
phase — see spec section 8: "permitir overrides organizacionales en una fase
posterior"). For now this resolves, in order:
  1. an active org-owned template for the generation_type
  2. an active system template (organization_id IS NULL) for the generation_type
  3. a lazily-created default system template, so the app works out of the
     box without requiring the seed script to have run first.

Templates are never edited in place once referenced by a job — "changing" a
template means creating a new version row and flipping is_active.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.ai import PromptTemplate
from app.models.enums import GenerationType
from app.schemas.ai import GeneratedContent
from app.utils.public_id import make as make_public_id

_DEFAULT_SYSTEM_INSTRUCTIONS = (
    "You are an editorial copywriter for a social-media marketing team. "
    "Write responsible, non-medical marketing copy about healthy habits and "
    "nutrition. Never claim guaranteed results, never present the product as "
    "a medical treatment or cure, and never make extreme weight-loss claims. "
    "Respond with ONLY a single JSON object matching the requested schema — "
    "no markdown fences, no commentary before or after it."
)

_DEFAULT_USER_TEMPLATE = (
    "Generate content for the request above. Respond with a JSON object with "
    "these exact keys: title, hook, script, caption, cta, hashtags "
    "(array of strings), visual_notes (array of strings). "
    "Formatting rules — title: ALL CAPS, plain text only, no asterisks, no "
    "dashes used as bullets or emphasis, no markdown, no other special text "
    "effects; emojis are welcome to reinforce the message. The caption and "
    "cta combined must not exceed 200 words in total, written with natural "
    "paragraph and line spacing, never a run-on wall of text. hashtags must "
    "contain exactly 5 items — the 5 most relevant hashtags specifically for "
    "this post's own topic and title, never generic filler, never more than 5."
)

_DEFAULT_IMAGE_SYSTEM_INSTRUCTIONS = (
    "You are an art director writing an image-generation brief for a "
    "social-media marketing team. Describe a single, photorealistic, "
    "brand-safe image — no text overlays, no logos, no medical claims, no "
    "guaranteed-results imagery."
)

_DEFAULT_IMAGE_USER_TEMPLATE = (
    "Write a single, vivid, self-contained image-generation prompt (plain "
    "text, not JSON) for the request above. Describe the subject, "
    "composition, lighting, and mood in a way an image model can render "
    "directly."
)


def _default_version(generation_type: GenerationType) -> str:
    return f"system-default-{generation_type.value.lower()}-v2"


def get_active_template(
    db: Session, organization_id: uuid.UUID, generation_type: GenerationType
) -> PromptTemplate:
    org_template = db.execute(
        select(PromptTemplate)
        .where(
            PromptTemplate.organization_id == organization_id,
            PromptTemplate.generation_type == generation_type,
            PromptTemplate.is_active.is_(True),
        )
        .order_by(PromptTemplate.created_at.desc())
    ).scalars().first()
    if org_template is not None:
        return org_template

    version = _default_version(generation_type)

    system_template = db.execute(
        select(PromptTemplate)
        .where(
            PromptTemplate.organization_id.is_(None),
            PromptTemplate.generation_type == generation_type,
            PromptTemplate.is_active.is_(True),
        )
        .order_by(PromptTemplate.created_at.desc())
    ).scalars().first()
    if system_template is not None:
        # A stale system default (older version string, e.g. the prompt copy
        # changed in code) is retired rather than kept forever active — a
        # hand-authored org/system template with a version outside our own
        # naming scheme is left alone.
        is_stale_default = (
            system_template.version.startswith("system-default-")
            and system_template.version != version
        )
        if not is_stale_default:
            return system_template
        system_template.is_active = False
        db.flush()

    # Lazily create the system default so a fresh DB works without seeding.
    existing = db.execute(
        select(PromptTemplate).where(
            PromptTemplate.organization_id.is_(None),
            PromptTemplate.generation_type == generation_type,
            PromptTemplate.version == version,
        )
    ).scalar_one_or_none()
    if existing is not None:
        if not existing.is_active:
            existing.is_active = True
            db.flush()
        return existing

    is_image = generation_type == GenerationType.IMAGE_ASSET
    template = PromptTemplate(
        public_id=make_public_id("pt"),
        organization_id=None,
        name=f"System default — {generation_type.value}",
        generation_type=generation_type,
        version=version,
        system_instructions=(
            _DEFAULT_IMAGE_SYSTEM_INSTRUCTIONS if is_image else _DEFAULT_SYSTEM_INSTRUCTIONS
        ),
        user_template=_DEFAULT_IMAGE_USER_TEMPLATE if is_image else _DEFAULT_USER_TEMPLATE,
        output_schema={"type": "string"} if is_image else GeneratedContent.model_json_schema(),
        is_active=True,
    )
    db.add(template)
    db.flush()
    return template
