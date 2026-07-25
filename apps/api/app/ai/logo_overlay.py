"""Pastes a brand's real logo file onto a generated image, pixel-perfect,
instead of relying on the image model to redraw it from a text description
(which never reproduces an exact logo consistently across generations).

Logo files live in app/ai/brand_assets/{brand_slug}_logo.png (transparent
PNG). A brand with no matching file is left untouched — this is an
enhancement layer, never a hard requirement for image generation to work.
"""

from __future__ import annotations

import io
from pathlib import Path

from PIL import Image

_BRAND_ASSETS_DIR = Path(__file__).parent / "brand_assets"

# Logo width as a fraction of the flyer width, and margin from each edge,
# also as a fraction of the flyer width — keeps proportions consistent
# across the different sizes the image provider can generate (1024x1024,
# 1024x1536, etc).
_LOGO_WIDTH_RATIO = 0.22
_MARGIN_RATIO = 0.04


def _logo_path_for_brand(brand_slug: str) -> Path | None:
    path = _BRAND_ASSETS_DIR / f"{brand_slug}_logo.png"
    return path if path.is_file() else None


def apply_brand_logo(content: bytes, brand_slug: str) -> bytes:
    logo_path = _logo_path_for_brand(brand_slug)
    if logo_path is None:
        return content

    base = Image.open(io.BytesIO(content)).convert("RGBA")
    logo = Image.open(logo_path).convert("RGBA")

    logo_width = max(1, round(base.width * _LOGO_WIDTH_RATIO))
    logo_height = max(1, round(logo.height * (logo_width / logo.width)))
    logo = logo.resize((logo_width, logo_height), Image.LANCZOS)

    margin = round(base.width * _MARGIN_RATIO)
    position = (margin, base.height - logo_height - margin)

    composed = base.copy()
    composed.alpha_composite(logo, dest=position)

    buffer = io.BytesIO()
    composed.convert("RGB").save(buffer, format="PNG")
    return buffer.getvalue()
