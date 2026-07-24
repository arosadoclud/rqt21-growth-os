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
    "(array of strings), visual_notes (array of strings)."
)


def _default_version(generation_type: GenerationType) -> str:
    return f"system-default-{generation_type.value.lower()}-v1"


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
        return system_template

    # Lazily create the system default so a fresh DB works without seeding.
    version = _default_version(generation_type)
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

    template = PromptTemplate(
        public_id=make_public_id("pt"),
        organization_id=None,
        name=f"System default — {generation_type.value}",
        generation_type=generation_type,
        version=version,
        system_instructions=_DEFAULT_SYSTEM_INSTRUCTIONS,
        user_template=_DEFAULT_USER_TEMPLATE,
        output_schema=GeneratedContent.model_json_schema(),
        is_active=True,
    )
    db.add(template)
    db.flush()
    return template
