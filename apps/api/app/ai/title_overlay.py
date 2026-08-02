"""Renders the headline TITLE as legible text directly onto the flyer with
Pillow, instead of trusting the image model to draw it.

Confirmed unreliable in production (2026-08-02): a detailed prompt asking
for a specific title in ALL CAPS, in a clean text block, produced an
illegible scribble of gibberish glyphs instead — the same class of problem
``apply_brand_logo`` (app.ai.logo_overlay) already solved for the logo
itself, for the same reason: an image model asked to draw a specific
string of text has no guarantee of reproducing it correctly. The image
model is now asked to generate a clean, text-free photo/background only
(see the no-text override appended in ``app.ai.runner._brand_visual_directives``);
this module is what actually puts the real words on the flyer, guaranteed
legible because it's real typography, not a hallucinated drawing of text.

Brands not in ``_ENABLED_BRAND_SLUGS`` are left untouched — same "optional
enhancement layer, never a hard requirement" convention as
``apply_brand_logo``; this only activates for the brand it's tuned for.
"""

from __future__ import annotations

import io
import re
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

_FONTS_DIR = Path(__file__).parent / "fonts"
_TITLE_FONT_PATH = _FONTS_DIR / "Anton-Regular.ttf"

_WHITE = (255, 255, 255, 255)
_BACKDROP_COLOR = (10, 10, 10, 235)

# Same slug convention as logo_overlay._WORDMARKS — extend both together if
# a second brand gets this treatment.
_ENABLED_BRAND_SLUGS = {"recetas-que-transforman-21"}

# Band geometry as fractions of the flyer's own dimensions, so proportions
# stay consistent whether the provider generated 1024x1024 or 1024x1536.
_BAND_HEIGHT_RATIO = 0.30
_SIDE_MARGIN_RATIO = 0.06
_MAX_FONT_RATIO = 0.085  # relative to image height
_MIN_FONT_RATIO = 0.032
_LINE_SPACING_RATIO = 1.12
_MAX_LINES = 4

# Strips emoji/pictographs before rendering — Anton/Montserrat have no
# glyphs for them, so they'd otherwise draw as empty tofu boxes. The emoji
# stays in the real Facebook caption; this only affects the flyer image.
_EMOJI_PATTERN = re.compile(
    "["
    "\U0001f300-\U0001faff"
    "\U00002600-\U000027bf"
    "\U0001f1e6-\U0001f1ff"
    "\U00002190-\U000021ff"
    "\U00002b00-\U00002bff"
    "️"
    "]+",
    flags=re.UNICODE,
)


def _clean_title(title: str) -> str:
    stripped = _EMOJI_PATTERN.sub("", title).strip()
    return " ".join(stripped.split()).upper()


def _wrap_to_width(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    words = text.split()
    if not words:
        return []
    lines: list[str] = []
    current = words[0]
    for word in words[1:]:
        candidate = f"{current} {word}"
        if draw.textbbox((0, 0), candidate, font=font)[2] <= max_width:
            current = candidate
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


def _fit_title(
    draw: ImageDraw.ImageDraw, text: str, max_width: int, max_height: int
) -> tuple[ImageFont.FreeTypeFont, list[str], int]:
    """Binary-search-free descent: try progressively smaller font sizes
    until the wrapped text fits within max_lines and max_height. Always
    returns something (falls back to the smallest size, truncated to
    _MAX_LINES) — never raises, since a flyer with a slightly-too-small
    or truncated title is always better than one that crashes the job."""
    max_font_size = round(max_height * (_MAX_FONT_RATIO / _BAND_HEIGHT_RATIO))
    min_font_size = round(max_height * (_MIN_FONT_RATIO / _BAND_HEIGHT_RATIO))
    min_font_size = max(min_font_size, 10)

    best: tuple[ImageFont.FreeTypeFont, list[str], int] | None = None
    for size in range(max_font_size, min_font_size - 1, -2):
        font = ImageFont.truetype(str(_TITLE_FONT_PATH), size)
        lines = _wrap_to_width(draw, text, font, max_width)
        line_height = round(size * _LINE_SPACING_RATIO)
        total_height = line_height * len(lines)
        if len(lines) <= _MAX_LINES and total_height <= max_height:
            return font, lines, line_height
        best = (font, lines[:_MAX_LINES], line_height)

    assert best is not None  # loop always runs at least once
    return best


def apply_headline_title(content: bytes, title: str, brand_slug: str) -> bytes:
    if brand_slug not in _ENABLED_BRAND_SLUGS:
        return content
    clean_title = _clean_title(title)
    if not clean_title:
        return content

    base = Image.open(io.BytesIO(content)).convert("RGBA")
    width, height = base.size

    band_height = round(height * _BAND_HEIGHT_RATIO)
    side_margin = round(width * _SIDE_MARGIN_RATIO)
    text_max_width = width - 2 * side_margin
    band_top = height - band_height

    composed = base.copy()
    draw = ImageDraw.Draw(composed)
    draw.rectangle((0, band_top, width, height), fill=_BACKDROP_COLOR)

    text_max_height = round(band_height * 0.86)
    font, lines, line_height = _fit_title(draw, clean_title, text_max_width, text_max_height)

    total_text_height = line_height * len(lines)
    text_top = band_top + (band_height - total_text_height) // 2
    for index, line in enumerate(lines):
        line_bbox = draw.textbbox((0, 0), line, font=font)
        line_width = line_bbox[2] - line_bbox[0]
        x = (width - line_width) // 2
        y = text_top + index * line_height
        draw.text((x, y), line, font=font, fill=_WHITE)

    buffer = io.BytesIO()
    composed.convert("RGB").save(buffer, format="PNG")
    return buffer.getvalue()
