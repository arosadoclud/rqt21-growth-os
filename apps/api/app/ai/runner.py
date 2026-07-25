"""Executes a single GenerationJob: QUEUED -> RUNNING -> COMPLETED|FAILED.

Called by the JobQueue implementation (InlineJobQueue runs it immediately,
in-process). Opens its own DB session since it may run outside the request
that created the job (true once a real distributed queue backend is wired
in place of InlineJobQueue).
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from decimal import Decimal

from pydantic import ValidationError
from sqlalchemy import select

from app import audit
from app.ai.image_providers import (
    ImageGenerationRequest,
    ImageProviderError,
    ImageProviderRateLimited,
    ImageProviderTimeout,
    get_image_provider,
)
from app.ai.logo_overlay import apply_brand_logo
from app.ai.providers import (
    AIProviderError,
    AIProviderRateLimited,
    AIProviderTimeout,
    GenerationRequest,
    get_provider,
)
from app.core.config import settings
from app.core.db import SessionLocal
from app.models.ai import GenerationJob
from app.models.assets import Asset
from app.models.enums import AssetStatus, AssetType, GenerationStatus, GenerationType
from app.schemas.ai import GeneratedContent
from app.storage.provider import get_storage_provider, make_storage_key
from app.storage.validation import AssetRejected, make_safe_filename, validate_upload
from app.utils.public_id import make as make_public_id

_PRICE_PER_1K = {
    ("ANTHROPIC", "input"): Decimal("0.003"),
    ("ANTHROPIC", "output"): Decimal("0.015"),
    ("OPENAI", "input"): Decimal("0.0025"),
    ("OPENAI", "output"): Decimal("0.01"),
}

# Flat per-image cost (gpt-image-1, 1024x1024, standard quality) — token
# based pricing doesn't apply to image generation. Approximate; not billed
# to the org, purely for the AI-usage cost dashboard.
_IMAGE_COST_USD = Decimal("0.04")


def _estimate_cost(provider: str, input_tokens: int, output_tokens: int) -> Decimal:
    if provider == "MOCK":
        return Decimal("0")
    price_in = _PRICE_PER_1K.get((provider, "input"), Decimal("0.002"))
    price_out = _PRICE_PER_1K.get((provider, "output"), Decimal("0.008"))
    cost = (Decimal(input_tokens) / 1000 * price_in) + (Decimal(output_tokens) / 1000 * price_out)
    return cost.quantize(Decimal("0.000001"))


def _extract_json(raw: str) -> str:
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
    return text.strip()


def _try_parse(text: str) -> GeneratedContent | None:
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None
    try:
        return GeneratedContent.model_validate(data)
    except ValidationError:
        return None


def _attempt_repair(text: str) -> str | None:
    """One controlled repair attempt: trim to the outermost {...} span.
    No retries beyond this — a job that fails here is marked FAILED."""
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    return text[start : end + 1]


def _fail(job: GenerationJob, db, error_code: str, message: str) -> None:
    job.status = GenerationStatus.FAILED
    job.error_code = error_code
    job.error_message = message[:500]
    job.completed_at = datetime.now(UTC)
    db.flush()
    audit.record(
        db,
        action="generation_job.failed",
        actor_user_id=job.requested_by_user_id,
        organization_id=job.organization_id,
        target_type="generation_job",
        target_id=job.id,
        payload={"error_code": error_code},
    )
    db.commit()


async def run_generation_job(job_id: uuid.UUID) -> None:
    with SessionLocal() as db:
        job = db.get(GenerationJob, job_id)
        if job is None or job.status != GenerationStatus.QUEUED:
            return

        job.status = GenerationStatus.RUNNING
        job.started_at = datetime.now(UTC)
        db.flush()
        audit.record(
            db,
            action="generation_job.started",
            actor_user_id=job.requested_by_user_id,
            organization_id=job.organization_id,
            target_type="generation_job",
            target_id=job.id,
            payload={"provider": job.provider.value, "model": job.model},
        )
        db.commit()

        if job.generation_type == GenerationType.IMAGE_ASSET:
            await _run_image_generation(job, db)
            return

        system = job.input_payload.get("system", "")
        user = job.input_payload.get("user", "")
        provider = get_provider(job.provider.value)
        request = GenerationRequest(
            system_instructions=system,
            user_prompt=user,
            model=job.model,
            max_output_tokens=settings.ai_max_output_tokens,
            timeout_seconds=settings.ai_request_timeout_seconds,
        )

        try:
            result = await provider.generate(request)
        except AIProviderTimeout as exc:
            _fail(job, db, "timeout", str(exc))
            return
        except AIProviderRateLimited as exc:
            _fail(job, db, "rate_limited", str(exc))
            return
        except AIProviderError as exc:
            _fail(job, db, "provider_error", str(exc))
            return

        text = _extract_json(result.raw_text)
        content = _try_parse(text)
        if content is None:
            repaired = _attempt_repair(text)
            content = _try_parse(repaired) if repaired else None
        if content is None:
            _fail(
                job,
                db,
                "invalid_output",
                "provider output failed schema validation after one repair attempt",
            )
            return

        job.output_payload = content.model_dump()
        job.input_tokens = result.input_tokens
        job.output_tokens = result.output_tokens
        job.estimated_cost = _estimate_cost(
            job.provider.value, result.input_tokens, result.output_tokens
        )
        job.status = GenerationStatus.COMPLETED
        job.completed_at = datetime.now(UTC)
        db.flush()
        audit.record(
            db,
            action="generation_job.completed",
            actor_user_id=job.requested_by_user_id,
            organization_id=job.organization_id,
            target_type="generation_job",
            target_id=job.id,
            payload={
                "input_tokens": result.input_tokens,
                "output_tokens": result.output_tokens,
            },
        )
        db.commit()


def _build_image_prompt(job: GenerationJob, db) -> str:
    # Image models take the prompt literally — they don't "follow"
    # instructions the way a text LLM parsing job.input_payload["user"]'s
    # <user_input>-wrapped template would (that block is meant for a text
    # model to read and write ITS OWN prompt from, not to be forwarded to
    # an image API verbatim). Build a plain, focused prompt directly from
    # the raw structured input instead.
    raw = job.input_payload.get("raw_input", {})
    topic = raw.get("topic", "")
    parts = [topic] if topic else []
    audience = raw.get("audience")
    if audience:
        parts.append(f"Appeals to: {audience}")

    from app.models.ai import BrandVoiceProfile

    brand_voice = db.execute(
        select(BrandVoiceProfile).where(
            BrandVoiceProfile.organization_id == job.organization_id,
            BrandVoiceProfile.brand_id == job.brand_id,
        )
    ).scalar_one_or_none()

    if brand_voice is not None and brand_voice.visual_style.strip():
        # A brand with a defined visual identity (background, palette,
        # typography, logo placement) — hand that directive to the image
        # model as-is instead of the generic clean-photo instruction below,
        # since brand flyers/thumbnails are explicitly meant to carry text
        # and a logo, unlike a bare product photo.
        parts.append(brand_voice.visual_style.strip())
        # Applies to every brand's flyer text, not just this one's visual
        # identity — a DALL-E quirk (headline text getting cropped by the
        # frame edge) rather than a brand design choice, so it belongs here
        # in code instead of duplicated inside each brand's visual_style.
        parts.append(
            "Leave a safety margin of at least 10% of the width/height on "
            "all four edges — no headline, icon, or text may touch or run "
            "past the frame border. If the title is long, shrink its font "
            "size and/or wrap it across more lines so the ENTIRE title "
            "always fits fully inside that safe area — never let it run "
            "off, get cropped, or bleed past the top or bottom edge; a "
            "smaller title that fully fits is always better than a bigger "
            "one that gets cut off. Any title or headline text rendered in "
            "the image must be in ALL CAPS, plain text only — no asterisks, "
            "no dashes, no markdown, no other special text effects; simple "
            "emoji accents are fine"
        )
    else:
        parts.append(
            "Photorealistic, professional editorial photography, natural lighting. "
            "No text, no words, no letters, no captions, no logos, no watermarks "
            "anywhere in the image."
        )
    return ". ".join(p.strip().rstrip(".") for p in parts if p.strip())


async def _run_image_generation(job: GenerationJob, db) -> None:
    prompt = _build_image_prompt(job, db)
    provider_name = "OPENAI" if job.provider.value == "OPENAI" else "MOCK"
    provider = get_image_provider(provider_name)
    request = ImageGenerationRequest(
        prompt=prompt,
        size=settings.ai_image_size,
        timeout_seconds=settings.ai_request_timeout_seconds,
    )

    try:
        result = await provider.generate(request)
    except ImageProviderTimeout as exc:
        _fail(job, db, "timeout", str(exc))
        return
    except ImageProviderRateLimited as exc:
        _fail(job, db, "rate_limited", str(exc))
        return
    except ImageProviderError as exc:
        _fail(job, db, "provider_error", str(exc))
        return

    from app.models.brand import Brand

    brand = db.get(Brand, job.brand_id)
    image_content = apply_brand_logo(result.content, brand.slug) if brand else result.content

    try:
        real_mime, real_type = validate_upload(
            declared_mime=result.mime_type, asset_type=AssetType.IMAGE, content=image_content
        )
    except AssetRejected as exc:
        _fail(job, db, "invalid_output", exc.reason)
        return

    original_filename = f"generated-{job.public_id}.png"
    safe_filename = make_safe_filename(original_filename)
    storage_key = make_storage_key(job.organization_id, safe_filename)
    storage_provider_name = settings.storage_provider.upper()
    stored = await get_storage_provider().upload(
        storage_key=storage_key, content=image_content, mime_type=real_mime
    )

    asset = Asset(
        organization_id=job.organization_id,
        public_id=make_public_id("as"),
        brand_id=job.brand_id,
        product_id=job.product_id,
        content_item_id=None,
        uploaded_by_user_id=job.requested_by_user_id,
        asset_type=real_type,
        status=AssetStatus.READY,
        storage_provider=(
            storage_provider_name if storage_provider_name in ("LOCAL", "S3", "R2", "MOCK") else "MOCK"
        ),
        storage_key=storage_key,
        original_filename=original_filename,
        safe_filename=safe_filename,
        mime_type=real_mime,
        size_bytes=stored.size_bytes,
        checksum_sha256=stored.checksum_sha256,
        alt_text=prompt[:500],
    )
    db.add(asset)
    db.flush()

    job.output_payload = {"asset_id": str(asset.id), "asset_public_id": asset.public_id, "prompt": prompt}
    job.estimated_cost = _IMAGE_COST_USD if job.provider.value == "OPENAI" else Decimal("0")
    job.status = GenerationStatus.COMPLETED
    job.completed_at = datetime.now(UTC)
    db.flush()
    audit.record(
        db,
        action="generation_job.completed",
        actor_user_id=job.requested_by_user_id,
        organization_id=job.organization_id,
        target_type="generation_job",
        target_id=job.id,
        payload={"asset_id": str(asset.id)},
    )
    db.commit()
