"""Executes a single GenerationJob: QUEUED -> RUNNING -> COMPLETED|FAILED.

Called by the JobQueue implementation (InlineJobQueue runs it immediately,
in-process). Opens its own DB session since it may run outside the request
that created the job (true once a real distributed queue backend is wired
in place of InlineJobQueue).
"""

from __future__ import annotations

import asyncio
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
    resolve_image_provider,
)
from app.ai.logo_overlay import apply_brand_logo
from app.ai.providers import (
    AIProviderError,
    AIProviderRateLimited,
    AIProviderTimeout,
    GenerationRequest,
    get_provider,
)
from app.ai.tts_providers import (
    TTSProviderError,
    TTSProviderTimeout,
    TTSRequest,
    resolve_tts_provider,
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
from app.video.assembler import VideoAssemblyError, assemble_from_clips, assemble_slideshow
from app.video.stock_footage import (
    StockVideoError,
    StockVideoNotFound,
    StockVideoRequest,
    StockVideoTimeout,
    get_stock_video_provider,
)

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


def _extract_first_json_object(text: str) -> str | None:
    start = None
    depth = 0
    in_string = False
    escape = False

    for index, char in enumerate(text):
        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
            continue

        if char == "{":
            if depth == 0:
                start = index
            depth += 1
        elif char == "}":
            if depth > 0:
                depth -= 1
                if depth == 0 and start is not None:
                    return text[start : index + 1]
    return None


def _unwrap_json_container(data: dict) -> dict:
    if not isinstance(data, dict):
        return data

    for key in ("output", "response", "result", "data"):
        value = data.get(key)
        if isinstance(value, dict):
            return value

    if len(data) == 1:
        only_value = next(iter(data.values()))
        if isinstance(only_value, dict):
            return only_value

    return data


def _normalize_generated_content(data: dict) -> dict:
    data = _unwrap_json_container(data)

    def ensure_list(key: str) -> None:
        if key not in data:
            return
        value = data[key]
        if isinstance(value, str):
            if "," in value:
                items = [item.strip() for item in value.split(",") if item.strip()]
            else:
                items = [item.strip() for item in value.split() if item.strip()]
            data[key] = items
        elif isinstance(value, list):
            data[key] = [str(item).strip() for item in value if item is not None]

    for list_key in ("hashtags", "visual_notes", "ideas", "stock_search_terms"):
        ensure_list(list_key)

    for text_key in ("title", "hook", "script", "caption", "cta"):
        if text_key in data and data[text_key] is not None:
            data[text_key] = str(data[text_key]).strip()

    return data


def _extract_json(raw: str) -> str:
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
        text = text.strip()

    extracted = _extract_first_json_object(text)
    return extracted if extracted is not None else text


def _try_parse(text: str) -> GeneratedContent | None:
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None
    if isinstance(data, dict):
        data = _normalize_generated_content(data)
    try:
        return GeneratedContent.model_validate(data)
    except ValidationError:
        return None


def _attempt_repair(text: str) -> str | None:
    """One controlled repair attempt: trim to the first balanced {...} span.
    No retries beyond this — a job that fails here is marked FAILED."""
    return _extract_first_json_object(text)


def _fail(job: GenerationJob, db, error_code: str, message: str) -> None:
    job.status = GenerationStatus.FAILED
    job.error_code = error_code
    job.error_message = message[:500]
    job.stage = None
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
        job.stage = "Escribiendo guion…" if job.generation_type in (
            GenerationType.VIDEO_ASSET,
            GenerationType.REEL_SCRIPT,
            GenerationType.SOCIAL_POST,
            GenerationType.STORY,
            GenerationType.VOICE_OVER,
        ) else "Generando…"
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

        if job.generation_type == GenerationType.VIDEO_ASSET:
            job.input_tokens = result.input_tokens
            job.output_tokens = result.output_tokens
            await _run_video_generation(job, db, content)
            return

        if job.generation_type == GenerationType.VOICE_OVER:
            job.input_tokens = result.input_tokens
            job.output_tokens = result.output_tokens
            await _run_voice_over_generation(job, db, content)
            return

        job.output_payload = content.model_dump()
        job.input_tokens = result.input_tokens
        job.output_tokens = result.output_tokens
        job.estimated_cost = _estimate_cost(
            job.provider.value, result.input_tokens, result.output_tokens
        )
        job.status = GenerationStatus.COMPLETED
        job.stage = None
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


def _get_brand_voice(job: GenerationJob, db):
    from app.models.ai import BrandVoiceProfile

    return db.execute(
        select(BrandVoiceProfile).where(
            BrandVoiceProfile.organization_id == job.organization_id,
            BrandVoiceProfile.brand_id == job.brand_id,
        )
    ).scalar_one_or_none()


def _brand_visual_directives(brand_voice) -> list[str]:
    if brand_voice is not None and brand_voice.visual_style.strip():
        # A brand with a defined visual identity (background, palette,
        # typography, logo placement) — hand that directive to the image
        # model as-is instead of the generic clean-photo instruction below,
        # since brand flyers/thumbnails are explicitly meant to carry text
        # and a logo, unlike a bare product photo.
        return [
            brand_voice.visual_style.strip(),
            # Applies to every brand's flyer text, not just this one's
            # visual identity — a DALL-E quirk (headline text getting
            # cropped by the frame edge) rather than a brand design choice,
            # so it belongs here in code instead of duplicated inside each
            # brand's visual_style.
            "Leave a safety margin of at least 10% of the width/height on "
            "all four edges — no headline, icon, or text may touch or run "
            "past the frame border. If the title is long, shrink its font "
            "size and/or wrap it across more lines so the ENTIRE title "
            "always fits fully inside that safe area — never let it run "
            "off, get cropped, or bleed past the top or bottom edge; a "
            "smaller title that fully fits is always better than a bigger "
            "one that gets cut off. If the design reserves a corner for the "
            "brand logo (as instructed above), also leave a clear gap below "
            "or beside that logo area so headline text starts only after "
            "it, never overlapping or running behind it. Any title or "
            "headline text rendered in "
            "the image must be in ALL CAPS, plain text only — no asterisks, "
            "no dashes, no markdown, no other special text effects; simple "
            "emoji accents are fine",
        ]
    return [
        "Photorealistic, professional editorial photography, natural lighting. "
        "No text, no words, no letters, no captions, no logos, no watermarks "
        "anywhere in the image."
    ]


# Layered on top of the brand's fixed visual_style (background/palette/
# typography/logo placement never change) — these only shift composition
# energy and color intensity so the same brand identity still reads as
# "made for this platform" instead of one flyer look reused everywhere.
# Deliberately rule-based per settings.md convention (content-angles.ts,
# the DATO CURIOSO heuristic in prompts.py) rather than a second AI call
# to classify tone — cheap, deterministic, and easy to tune per platform.
_PLATFORM_VISUAL_ACCENTS: dict[str, str] = {
    "INSTAGRAM": (
        "Polished, editorial-quality composition with elegant contrast — "
        "an aspirational, scroll-stopping look suited to a curated feed"
    ),
    "FACEBOOK": (
        "Warm, approachable, community-feed composition — softer contrast "
        "than a polished ad, feels like a real moment being shared"
    ),
    "TIKTOK": (
        "Bold, high-saturation colors with energetic, slightly playful "
        "framing and strong visual contrast — built to grab attention in "
        "a fast-scrolling, youth-oriented feed"
    ),
    "YOUTUBE": (
        "Thumbnail-style composition: dramatic lighting, punchy high "
        "contrast, one unmistakable focal subject that reads instantly "
        "even at a small size"
    ),
    "WHATSAPP": (
        "Simple, friendly, uncluttered composition that still reads "
        "clearly as a small chat preview thumbnail"
    ),
    "EMAIL": (
        "Clean, minimal, print-like composition with generous whitespace "
        "— premium and easy to scan inside an inbox"
    ),
    "WEB": (
        "Editorial blog-header composition with balanced negative space "
        "left for text to be overlaid elsewhere on the page"
    ),
    "META_ADS": (
        "High-contrast, conversion-focused composition with one bold "
        "focal point and confident color blocking — built to stop the "
        "scroll in a paid ad placement"
    ),
}


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

    brand_voice = _get_brand_voice(job, db)
    parts.extend(_brand_visual_directives(brand_voice))

    platform_accent = _PLATFORM_VISUAL_ACCENTS.get(str(raw.get("platform", "")))
    if platform_accent:
        parts.append(platform_accent)

    return ". ".join(p.strip().rstrip(".") for p in parts if p.strip())


async def _run_image_generation(job: GenerationJob, db) -> None:
    prompt = _build_image_prompt(job, db)
    provider_name = "OPENAI" if job.provider.value == "OPENAI" else "MOCK"
    provider = resolve_image_provider() if provider_name == "OPENAI" else get_image_provider(provider_name)
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
    job.stage = None
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


_VIDEO_WIDTH = 1080
_VIDEO_HEIGHT = 1920
_TTS_COST_USD = Decimal("0.015")


async def _run_voice_over_generation(job: GenerationJob, db, content: GeneratedContent) -> None:
    """Same script text as REEL_SCRIPT/VIDEO_ASSET, but stops after TTS —
    no scenes, no images, no ffmpeg assembly. For when the ask is just a
    narration track to drop into an editor by hand."""
    narration_text = (content.script or content.hook or content.title or "").strip()
    if not narration_text:
        _fail(job, db, "invalid_output", "generated script has no narration text for the voice-over")
        return

    job.stage = "Generando narración…"
    db.commit()

    tts_provider = resolve_tts_provider()
    tts_request = TTSRequest(text=narration_text, timeout_seconds=settings.ai_request_timeout_seconds)
    try:
        audio_result = await tts_provider.synthesize(tts_request)
    except TTSProviderTimeout as exc:
        _fail(job, db, "timeout", f"narration synthesis timed out: {exc}")
        return
    except TTSProviderError as exc:
        _fail(job, db, "provider_error", f"narration synthesis failed: {exc}")
        return

    try:
        real_mime, real_type = validate_upload(
            declared_mime=audio_result.mime_type, asset_type=AssetType.AUDIO, content=audio_result.content
        )
    except AssetRejected as exc:
        _fail(job, db, "invalid_output", exc.reason)
        return

    job.stage = "Subiendo audio…"
    db.commit()

    original_filename = f"generated-{job.public_id}.mp3"
    safe_filename = make_safe_filename(original_filename)
    storage_key = make_storage_key(job.organization_id, safe_filename)
    storage_provider_name = settings.storage_provider.upper()
    stored = await get_storage_provider().upload(
        storage_key=storage_key, content=audio_result.content, mime_type=real_mime
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
        alt_text=(content.title or narration_text)[:500],
    )
    db.add(asset)
    db.flush()

    job.output_payload = {
        "asset_id": str(asset.id),
        "asset_public_id": asset.public_id,
        "title": content.title,
        "hook": content.hook,
        "script": content.script,
    }
    text_cost = _estimate_cost(job.provider.value, job.input_tokens or 0, job.output_tokens or 0)
    tts_cost = _TTS_COST_USD if settings.ai_tts_provider == "OPENAI" else Decimal("0")
    job.estimated_cost = text_cost + tts_cost
    job.status = GenerationStatus.COMPLETED
    job.stage = None
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


async def _run_video_generation(job: GenerationJob, db, content: GeneratedContent) -> None:
    """Script is already generated (same GeneratedContent as REEL_SCRIPT —
    the caller parsed it before branching here). From here: one branded
    image per scene (content.visual_notes), a narration track for
    content.script, then ffmpeg assembles both into an MP4 slideshow."""
    brand_voice = _get_brand_voice(job, db)
    directives = _brand_visual_directives(brand_voice)
    platform_accent = _PLATFORM_VISUAL_ACCENTS.get(
        str((job.input_payload.get("raw_input", {}) or {}).get("platform", ""))
    )
    if platform_accent:
        directives = [*directives, platform_accent]

    raw_scenes = [s.strip() for s in content.visual_notes]
    raw_queries = [q.strip() for q in content.stock_search_terms]
    paired_scenes = [
        (
            scene,
            raw_queries[i] if i < len(raw_queries) and raw_queries[i] else "cooking food kitchen",
        )
        for i, scene in enumerate(raw_scenes)
        if scene
    ][: settings.ai_video_max_scenes]
    if not paired_scenes:
        fallback = (content.hook or content.title or "").strip()
        paired_scenes = [(fallback or "Toma principal del producto", "cooking food kitchen")]
    scenes = [s for s, _ in paired_scenes]
    # English-only, short keyword queries for the stock footage search — the
    # Spanish scene descriptions in `scenes` above don't match well against
    # Pexels (predominantly English-tagged library, and full sentences with
    # scene numbers/punctuation confuse its search ranking). See templates.py
    # for the prompt instructions that produce these alongside visual_notes.
    stock_queries = [q for _, q in paired_scenes]

    narration_text = (content.script or content.hook or content.title or "").strip()
    if not narration_text:
        _fail(job, db, "invalid_output", "generated script has no narration text for the video")
        return

    job.stage = "Generando narración…"
    db.commit()

    tts_provider = resolve_tts_provider()
    tts_request = TTSRequest(text=narration_text, timeout_seconds=settings.ai_request_timeout_seconds)
    try:
        audio_result = await tts_provider.synthesize(tts_request)
    except TTSProviderTimeout as exc:
        _fail(job, db, "timeout", f"narration synthesis timed out: {exc}")
        return
    except TTSProviderError as exc:
        _fail(job, db, "provider_error", f"narration synthesis failed: {exc}")
        return

    use_stock_footage = settings.ai_video_scene_source == "STOCK_FOOTAGE"

    job.stage = "Buscando escenas…" if use_stock_footage else "Generando imágenes de marca…"
    db.commit()

    if use_stock_footage:
        # Real clips of people/food prep in motion (licensed stock, e.g.
        # Pexels) instead of AI-generated stills — one search per scene,
        # using the scene description as the query.
        stock_provider = get_stock_video_provider("PEXELS" if settings.pexels_api_key else "MOCK")

        async def _fetch_clip(query: str) -> bytes:
            request = StockVideoRequest(query=query, timeout_seconds=settings.ai_request_timeout_seconds)
            result = await stock_provider.search(request)
            return result.content

        try:
            scene_media = list(await asyncio.gather(*(_fetch_clip(q) for q in stock_queries)))
        except StockVideoTimeout as exc:
            _fail(job, db, "timeout", f"stock footage search timed out: {exc}")
            return
        except StockVideoNotFound as exc:
            _fail(job, db, "invalid_output", f"no stock footage found: {exc}")
            return
        except StockVideoError as exc:
            _fail(job, db, "provider_error", f"stock footage search failed: {exc}")
            return

        job.stage = "Ensamblando video…"
        db.commit()

        try:
            video_content = assemble_from_clips(
                scene_media,
                audio_result.content,
                width=_VIDEO_WIDTH,
                height=_VIDEO_HEIGHT,
                timeout_seconds=settings.ai_request_timeout_seconds,
            )
        except VideoAssemblyError as exc:
            _fail(job, db, "provider_error", f"video assembly failed: {exc}")
            return
    else:
        from app.models.brand import Brand

        brand = db.get(Brand, job.brand_id)
        image_provider = resolve_image_provider()

        async def _generate_scene(scene: str) -> bytes:
            prompt = ". ".join(p.strip().rstrip(".") for p in [scene, *directives] if p.strip())
            request = ImageGenerationRequest(
                prompt=prompt, size=settings.ai_image_size, timeout_seconds=settings.ai_request_timeout_seconds
            )
            result = await image_provider.generate(request)
            return apply_brand_logo(result.content, brand.slug) if brand else result.content

        # Scenes are independent — run them concurrently instead of one at a
        # time, since each real DALL-E call already takes 45-70s on its own
        # and this whole job runs synchronously inside a single HTTP request.
        try:
            scene_media = list(await asyncio.gather(*(_generate_scene(s) for s in scenes)))
        except ImageProviderTimeout as exc:
            _fail(job, db, "timeout", f"scene image generation timed out: {exc}")
            return
        except ImageProviderRateLimited as exc:
            _fail(job, db, "rate_limited", f"scene image generation rate limited: {exc}")
            return
        except ImageProviderError as exc:
            _fail(job, db, "provider_error", f"scene image generation failed: {exc}")
            return

        job.stage = "Ensamblando video…"
        db.commit()

        try:
            video_content = assemble_slideshow(
                scene_media,
                audio_result.content,
                width=_VIDEO_WIDTH,
                height=_VIDEO_HEIGHT,
                timeout_seconds=settings.ai_request_timeout_seconds,
            )
        except VideoAssemblyError as exc:
            _fail(job, db, "provider_error", f"video assembly failed: {exc}")
            return

    try:
        real_mime, real_type = validate_upload(
            declared_mime="video/mp4", asset_type=AssetType.VIDEO, content=video_content
        )
    except AssetRejected as exc:
        _fail(job, db, "invalid_output", exc.reason)
        return

    job.stage = "Subiendo video…"
    db.commit()

    original_filename = f"generated-{job.public_id}.mp4"
    safe_filename = make_safe_filename(original_filename)
    storage_key = make_storage_key(job.organization_id, safe_filename)
    storage_provider_name = settings.storage_provider.upper()
    stored = await get_storage_provider().upload(
        storage_key=storage_key, content=video_content, mime_type=real_mime
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
        alt_text=(content.title or narration_text)[:500],
    )
    db.add(asset)
    db.flush()

    job.output_payload = {
        "asset_id": str(asset.id),
        "asset_public_id": asset.public_id,
        "title": content.title,
        "hook": content.hook,
        "script": content.script,
        "caption": content.caption,
        "cta": content.cta,
        "hashtags": content.hashtags,
        "scene_count": len(scenes),
    }
    text_cost = _estimate_cost(job.provider.value, job.input_tokens or 0, job.output_tokens or 0)
    image_cost = (
        _IMAGE_COST_USD * len(scenes)
        if not use_stock_footage and settings.ai_image_provider == "OPENAI"
        else Decimal("0")
    )
    tts_cost = _TTS_COST_USD if settings.ai_tts_provider == "OPENAI" else Decimal("0")
    job.estimated_cost = text_cost + image_cost + tts_cost
    job.status = GenerationStatus.COMPLETED
    job.stage = None
    job.completed_at = datetime.now(UTC)
    db.flush()
    audit.record(
        db,
        action="generation_job.completed",
        actor_user_id=job.requested_by_user_id,
        organization_id=job.organization_id,
        target_type="generation_job",
        target_id=job.id,
        payload={"asset_id": str(asset.id), "scene_count": len(scenes)},
    )
    db.commit()
