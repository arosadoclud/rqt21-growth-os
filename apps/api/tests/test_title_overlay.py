"""app.ai.title_overlay: renders the headline title with real Pillow
typography instead of trusting the image model to draw it — confirmed
unreliable in production (illegible scribble instead of real text)."""

from __future__ import annotations

import io

from PIL import Image

from app.ai.title_overlay import _clean_title, _wrap_to_width, apply_headline_title

_ENABLED_SLUG = "recetas-que-transforman-21"


def _blank_png(width: int = 1024, height: int = 1536) -> bytes:
    image = Image.new("RGB", (width, height), color=(20, 20, 20))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def test_clean_title_strips_emoji_and_uppercases():
    assert _clean_title("El aguacate: tu aliado keto 🥑") == "EL AGUACATE: TU ALIADO KETO"


def test_clean_title_collapses_whitespace():
    assert _clean_title("  Muchos   espacios   \n\n aqui  ") == "MUCHOS ESPACIOS AQUI"


def test_apply_headline_title_noop_for_unconfigured_brand():
    content = _blank_png()
    result = apply_headline_title(content, "UN TITULO CUALQUIERA", "otra-marca-sin-config")
    assert result == content


def test_apply_headline_title_noop_for_empty_title():
    content = _blank_png()
    result = apply_headline_title(content, "   🥑🥑🥑   ", _ENABLED_SLUG)
    assert result == content


def test_apply_headline_title_renders_visible_text_band():
    content = _blank_png()
    result = apply_headline_title(content, "EL ERROR NÚMERO UNO AL EMPEZAR KETO", _ENABLED_SLUG)
    assert result != content

    before = Image.open(io.BytesIO(content)).convert("RGB")
    after = Image.open(io.BytesIO(result)).convert("RGB")
    assert before.size == after.size

    # The bottom band must have changed (backdrop + text drawn there);
    # a blank solid-color source image makes this a reliable, simple check
    # without needing real OCR to prove legibility.
    width, height = after.size
    band_pixel_before = before.getpixel((width // 2, height - 10))
    band_pixel_after = after.getpixel((width // 2, height - 10))
    assert band_pixel_before != band_pixel_after


def test_apply_headline_title_handles_very_long_title_without_crashing():
    content = _blank_png()
    long_title = "ESTE ES UN TITULO EXTREMADAMENTE LARGO QUE NUNCA DEBERIA CABER EN UNA SOLA LINEA NI SIQUIERA CON UNA FUENTE MUY PEQUENA PORQUE TIENE DEMASIADAS PALABRAS JUNTAS"
    result = apply_headline_title(content, long_title, _ENABLED_SLUG)
    after = Image.open(io.BytesIO(result)).convert("RGB")
    assert after.size == Image.open(io.BytesIO(content)).size


def test_wrap_to_width_never_returns_empty_line_for_nonempty_text():
    from PIL import ImageDraw, ImageFont

    from app.ai.title_overlay import _TITLE_FONT_PATH

    image = Image.new("RGB", (10, 10))
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype(str(_TITLE_FONT_PATH), 40)
    lines = _wrap_to_width(draw, "UNA FRASE DE PRUEBA PARA ENVOLVER", font, max_width=200)
    assert lines
    assert all(line.strip() for line in lines)
