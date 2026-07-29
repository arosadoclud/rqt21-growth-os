"""AI-generated branded thumbnails for manually-uploaded video assets.

Reuses the same flyer pipeline as IMAGE_ASSET generation jobs — the brand's
visual_style directives, a DALL-E-rendered headline/benefit/CTA layout, and
the real logo composited via Pillow (app.ai.logo_overlay) — but takes
explicit user-supplied copy instead of an AI-brainstormed topic, since a
manual video upload has no GenerationJob/brief driving it.

Two formats:
- "vertical" (1024x1536): Reels/Stories cover, matches IMAGE_ASSET's default.
- "facebook_horizontal" (1200x630 exact): Facebook feed link/thumbnail size —
  generated at the closest OpenAI portrait-less preset (1536x1024) then
  center-cropped to the exact pixel size, since gpt-image-1 only accepts a
  fixed set of size presets, not arbitrary dimensions.
"""

from __future__ import annotations

import io
from typing import Literal

from PIL import Image

from app.ai.image_providers import ImageGenerationRequest, resolve_image_provider
from app.ai.logo_overlay import apply_brand_logo
from app.ai.runner import _brand_visual_directives
from app.core.config import settings

ThumbnailFormat = Literal["vertical", "facebook_horizontal"]
ContentStyle = Literal[
    "receta", "curiosidad", "encuesta", "antes_despues", "receta_rapida", "educativo"
]

_FACEBOOK_SIZE = (1200, 630)

_CONTENT_STYLE_DIRECTIVES: dict[str, str] = {
    "receta": "Highlight the dish name and its single strongest benefit.",
    "curiosidad": "Use a question, comparison, or visual mystery to spark curiosity — don't reveal the full answer.",
    "encuesta": "Show 2-3 clear labeled options (A/B/C or short labels), styled as a poll.",
    "antes_despues": "Split the frame into a before and an after version of the food, divided by a thin lime-green line.",
    "receta_rapida": "Include a small clock icon near the title to signal speed.",
    "educativo": "Use simple check, cross, or question-mark symbols to signal right/wrong/quiz framing.",
}

_BASE_STYLE = (
    "Premium dark culinary background — matte black with a subtle stone or "
    "slate texture, dramatic cinematic lighting. Palette: black, white, "
    "emerald green, lime green, with subtle green paint-stroke or light-"
    "particle accents. High contrast, instantly readable, modern premium "
    "food-brand aesthetic. Split the composition into two zones: a clean "
    "text zone and a food zone where the dish is the hero, hyperrealistic, "
    "freshly plated, hot, glossy, with visible texture (melted cheese, "
    "golden crust, fresh herbs, juiciness) — never more than one dish, "
    "never a cluttered composition. Bold condensed sans-serif typography, "
    "titles in ALL CAPS, the single most important word or phrase of the "
    "headline in lime green, the rest of the headline in white, maximum "
    "three separate text blocks total, no tiny hard-to-read text, correct "
    "spelling and accents. Never render the words 'Facebook', 'Instagram', "
    "'miniatura', 'thumbnail', or any technical instruction as visible text."
)


def build_thumbnail_prompt(
    title: str,
    subtitle: str | None,
    benefits: list[str],
    cta_banner: str | None,
    content_style: ContentStyle | None,
    directives: list[str],
) -> str:
    parts = [
        f'Branded social media thumbnail. Headline text reading exactly: "{title}".'
    ]
    if subtitle:
        parts.append(f'Below the headline, smaller subtitle text reading exactly: "{subtitle}".')
    if benefits:
        trimmed = benefits[:3]
        joined = "; ".join(trimmed)
        parts.append(
            f"Down one side, {len(trimmed)} small icon badge(s) with a short label "
            f"each, reading exactly: {joined}."
        )
    if cta_banner:
        parts.append(
            f'Near the bottom, a small banner/ribbon with text reading exactly: "{cta_banner}".'
        )
    parts.append(_BASE_STYLE)
    if content_style and content_style in _CONTENT_STYLE_DIRECTIVES:
        parts.append(_CONTENT_STYLE_DIRECTIVES[content_style])
    parts.extend(directives)
    return ". ".join(p.strip().rstrip(".") for p in parts if p.strip())


def _crop_to_facebook_size(content: bytes) -> bytes:
    """Center-crop+resize to the exact 1200x630 Facebook thumbnail size —
    generation presets don't include that exact aspect ratio, so this fills
    the target frame from the nearest wide preset without distorting it."""
    img = Image.open(io.BytesIO(content)).convert("RGB")
    target_w, target_h = _FACEBOOK_SIZE
    src_ratio = img.width / img.height
    target_ratio = target_w / target_h
    if src_ratio > target_ratio:
        new_height = img.height
        new_width = int(new_height * target_ratio)
    else:
        new_width = img.width
        new_height = int(new_width / target_ratio)
    left = (img.width - new_width) // 2
    top = (img.height - new_height) // 2
    cropped = img.crop((left, top, left + new_width, top + new_height))
    resized = cropped.resize(_FACEBOOK_SIZE, Image.LANCZOS)
    buf = io.BytesIO()
    resized.save(buf, format="PNG")
    return buf.getvalue()


async def generate_thumbnail_image(
    *,
    title: str,
    subtitle: str | None,
    benefits: list[str],
    cta_banner: str | None,
    content_style: ContentStyle | None,
    fmt: ThumbnailFormat,
    brand_voice,
    brand_slug: str,
) -> bytes:
    directives = _brand_visual_directives(brand_voice)
    prompt = build_thumbnail_prompt(title, subtitle, benefits, cta_banner, content_style, directives)
    provider = resolve_image_provider()
    size = "1536x1024" if fmt == "facebook_horizontal" else settings.ai_image_size
    request = ImageGenerationRequest(
        prompt=prompt, size=size, timeout_seconds=settings.ai_request_timeout_seconds
    )
    result = await provider.generate(request)
    content = result.content
    if fmt == "facebook_horizontal":
        content = _crop_to_facebook_size(content)
    return apply_brand_logo(content, brand_slug) if brand_slug else content
