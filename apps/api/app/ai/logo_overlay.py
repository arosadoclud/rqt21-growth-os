"""Pastes a brand's real logo onto a generated image, pixel-perfect, instead
of relying on the image model to redraw it from a text description — that
never reproduces an exact logo or exact brand-name spelling consistently
across generations (confirmed directly: asked for "RQT21 RECETAS QUE
TRANSFORMAN 21" in the prompt and the model either omitted it or misspelled
it every time).

The brand only has the circular icon as a real asset file (leaf+fork
emblem, no text) — the reference flyers the brand actually uses pair that
icon with a "RQT21 / RECETAS QUE TRANSFORMAN 21" wordmark next to it.
Rather than trust an image model to draw that text, ``_build_wordmark``
renders it with Pillow (bundled Anton + Montserrat fonts, see
app/ai/fonts/) so the spelling is always exactly right, then composites
icon + rendered text into one lockup image before pasting it onto the
flyer. Top-left placement matches every reference flyer the brand shared.

Logo files live in app/ai/brand_assets/{brand_slug}_logo.png (transparent
PNG). A brand with no matching file is left untouched — this is an
enhancement layer, never a hard requirement for image generation to work.
"""

from __future__ import annotations

import io
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

_BRAND_ASSETS_DIR = Path(__file__).parent / "brand_assets"
_FONTS_DIR = Path(__file__).parent / "fonts"

# Wordmark (icon + brand name) width as a fraction of the flyer width, and
# margin from each edge, also as a fraction of the flyer width — keeps
# proportions consistent across the different sizes the image provider can
# generate (1024x1024, 1024x1536, etc).
_WORDMARK_WIDTH_RATIO = 0.34
_MARGIN_RATIO = 0.04
_PADDING_RATIO = 0.015

# Prompting the image model to leave this corner empty is best-effort — it
# often draws its own icon/text there anyway, which would otherwise collide
# with the real logo. A solid backdrop chip guarantees a clean placement
# regardless of what the model drew underneath. Matches this brand family's
# near-black flyer background (documented as "fondo negro mate" in every
# brand's visual_style) — revisit if a brand with a lighter background ever
# needs this layer.
_BACKDROP_COLOR = (16, 16, 16, 255)
_BACKDROP_RADIUS_RATIO = 0.02

# Brand names/subtitles keyed by the same slug as the icon file — free text
# rendered with Pillow, not stored per-org, since only this one brand has a
# real logo asset today. Extend this dict (or move to BrandVoiceProfile) if
# a second brand needs the same treatment.
_WORDMARKS: dict[str, tuple[str, str, str]] = {
    # slug: (title_white, title_green, subtitle)
    "recetas-que-transforman-21": ("RQT", "21", "RECETAS QUE TRANSFORMAN 21"),
}

_LIME_GREEN = (163, 230, 53, 255)
_WHITE = (255, 255, 255, 255)
_SUBTITLE_GRAY = (200, 200, 200, 255)


def _logo_path_for_brand(brand_slug: str) -> Path | None:
    path = _BRAND_ASSETS_DIR / f"{brand_slug}_logo.png"
    return path if path.is_file() else None


def _build_wordmark(brand_slug: str, icon: Image.Image, target_height: int) -> Image.Image | None:
    """Icon + rendered brand-name text, composed left-to-right on a
    transparent canvas of the given height. Returns None if this brand has
    no configured wordmark text (icon-only compositing still applies via
    the caller)."""
    parts = _WORDMARKS.get(brand_slug)
    if parts is None:
        return None
    title_white, title_green, subtitle = parts

    title_font = ImageFont.truetype(str(_FONTS_DIR / "Anton-Regular.ttf"), round(target_height * 0.62))
    subtitle_font = ImageFont.truetype(str(_FONTS_DIR / "Montserrat-Bold.ttf"), round(target_height * 0.22))
    subtitle_font.set_variation_by_name("SemiBold")

    icon_height = target_height
    icon_width = max(1, round(icon.width * (icon_height / icon.height)))
    icon_resized = icon.resize((icon_width, icon_height), Image.LANCZOS)

    scratch = Image.new("RGBA", (10, 10))
    draw = ImageDraw.Draw(scratch)
    white_bbox = draw.textbbox((0, 0), title_white, font=title_font)
    green_bbox = draw.textbbox((0, 0), title_green, font=title_font)
    subtitle_bbox = draw.textbbox((0, 0), subtitle, font=subtitle_font)

    title_gap = round(target_height * 0.04)
    text_width = (white_bbox[2] - white_bbox[0]) + title_gap + (green_bbox[2] - green_bbox[0])
    text_width = max(text_width, subtitle_bbox[2] - subtitle_bbox[0])

    icon_text_gap = round(target_height * 0.08)
    canvas_width = icon_width + icon_text_gap + text_width
    canvas = Image.new("RGBA", (canvas_width, target_height), (0, 0, 0, 0))
    canvas.alpha_composite(icon_resized, dest=(0, 0))

    draw = ImageDraw.Draw(canvas)
    text_x = icon_width + icon_text_gap
    title_y = round(target_height * 0.05) - white_bbox[1]
    draw.text((text_x, title_y), title_white, font=title_font, fill=_WHITE)
    green_x = text_x + (white_bbox[2] - white_bbox[0]) + title_gap
    draw.text((green_x, title_y), title_green, font=title_font, fill=_LIME_GREEN)

    subtitle_y = title_y + (white_bbox[3] - white_bbox[1]) + round(target_height * 0.16) - subtitle_bbox[1]
    draw.text((text_x, subtitle_y), subtitle, font=subtitle_font, fill=_SUBTITLE_GRAY)

    return canvas


def apply_brand_logo(content: bytes, brand_slug: str) -> bytes:
    logo_path = _logo_path_for_brand(brand_slug)
    if logo_path is None:
        return content

    base = Image.open(io.BytesIO(content)).convert("RGBA")
    icon = Image.open(logo_path).convert("RGBA")

    target_width = max(1, round(base.width * _WORDMARK_WIDTH_RATIO))
    # Build at a fixed working height first (proportions come from font
    # sizing relative to height, not width) so text stays crisp, then scale
    # the whole composed lockup down/up to the flyer's target width.
    draft = _build_wordmark(brand_slug, icon, target_height=200)
    if draft is not None:
        scale = target_width / draft.width
        logo = draft.resize((target_width, max(1, round(draft.height * scale))), Image.LANCZOS)
    else:
        logo = icon.resize(
            (target_width, max(1, round(icon.height * (target_width / icon.width)))), Image.LANCZOS
        )
    logo_width, logo_height = logo.size

    margin = round(base.width * _MARGIN_RATIO)
    position = (margin, margin)

    padding = round(base.width * _PADDING_RATIO)
    backdrop_box = (
        position[0] - padding,
        position[1] - padding,
        position[0] + logo_width + padding,
        position[1] + logo_height + padding,
    )
    radius = round(base.width * _BACKDROP_RADIUS_RATIO)

    composed = base.copy()
    draw = ImageDraw.Draw(composed)
    draw.rounded_rectangle(backdrop_box, radius=radius, fill=_BACKDROP_COLOR)
    composed.alpha_composite(logo, dest=position)

    buffer = io.BytesIO()
    composed.convert("RGB").save(buffer, format="PNG")
    return buffer.getvalue()
