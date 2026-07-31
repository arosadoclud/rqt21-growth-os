"""GenerationType.IMAGE_ASSET: the image-generation branch of the job
runner (app.ai.runner._run_image_generation), covered end-to-end through
the API with MockImageProvider — never a real OpenAI call in tests, same
convention as every other real-provider gate in this codebase."""

from __future__ import annotations

import uuid as _u
from types import SimpleNamespace

from sqlalchemy import select

from app.ai.runner import _build_image_prompt
from app.models.assets import Asset
from app.models.enums import AssetStatus, AssetType
from app.models.membership import Role


def _brand(client):
    slug = f"brand-{_u.uuid4().hex[:6]}"
    return client.post("/api/v1/brands", json={"name": slug, "slug": slug}).json()["id"]


def _image_job_payload(brand_id: str, topic: str = "un plato de pizza keto") -> dict:
    return {
        "brand_id": brand_id,
        "generation_type": "IMAGE_ASSET",
        "input": {
            "objective": "engagement",
            "platform": "INSTAGRAM",
            "topic": topic,
            "audience": "adultos 30-50",
        },
    }


def test_create_image_job_completes_and_creates_asset(bootstrap, db):
    client, _, _ = bootstrap(Role.OWNER, "img-create@example.com")
    brand_id = _brand(client)
    r = client.post("/api/v1/generation-jobs", json=_image_job_payload(brand_id))
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["status"] == "COMPLETED"
    assert body["provider"] == "MOCK"
    assert body["output_payload"]["asset_id"]

    asset_id = _u.UUID(body["output_payload"]["asset_id"])
    asset = db.get(Asset, asset_id)
    assert asset is not None
    assert asset.asset_type == AssetType.IMAGE
    assert asset.status == AssetStatus.READY
    assert asset.brand_id == _u.UUID(brand_id)
    assert asset.size_bytes > 0
    assert asset.checksum_sha256


def test_image_job_mock_timeout_marks_failed(bootstrap):
    client, _, _ = bootstrap(Role.OWNER, "img-timeout@example.com")
    brand_id = _brand(client)
    r = client.post(
        "/api/v1/generation-jobs",
        json=_image_job_payload(brand_id, topic="__mock_timeout__"),
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["status"] == "FAILED"
    assert body["error_code"] == "timeout"


def test_build_image_prompt_adapts_accent_per_platform(bootstrap, db):
    """Same brand, same topic, different destination platform: the prompt
    should carry a different composition/color accent for TikTok than for
    Email, layered on top of (not replacing) the brand's fixed visual
    identity."""
    client, org_id, _ = bootstrap(Role.OWNER, "img-platform-accent@example.com")
    brand_id = _brand(client)

    def _job(platform: str):
        return SimpleNamespace(
            organization_id=org_id,
            brand_id=_u.UUID(brand_id),
            input_payload={"raw_input": {"topic": "pizza keto", "platform": platform}},
        )

    tiktok_prompt = _build_image_prompt(_job("TIKTOK"), db)
    email_prompt = _build_image_prompt(_job("EMAIL"), db)
    other_prompt = _build_image_prompt(_job("OTHER"), db)

    assert "fast-scrolling" in tiktok_prompt
    assert "inbox" in email_prompt
    assert tiktok_prompt != email_prompt
    # OTHER has no accent mapped — falls back to just topic + brand directives.
    assert "fast-scrolling" not in other_prompt
    assert "inbox" not in other_prompt


def test_build_image_prompt_includes_topic_literalism_override(bootstrap, db):
    """A brand's visual_style can hard-code "show a collage of 2-3 dishes"
    (the RQT21 default does), which is wrong for a non-recipe topic like a
    food-science curiosity — the prompt must always carry the override
    telling the model to depict the literal subject instead in that case,
    and must forward the angle/objective so the model knows this isn't a
    dish showcase."""
    client, org_id, _ = bootstrap(Role.OWNER, "img-literalism@example.com")
    brand_id = _brand(client)
    r = client.put(
        f"/api/v1/brand-voice/{brand_id}",
        json={
            "brand_id": brand_id,
            "visual_style": (
                "Show a collage of 2-3 DIFFERENT finished dishes arranged neatly."
            ),
        },
    )
    assert r.status_code == 200, r.text

    job = SimpleNamespace(
        organization_id=org_id,
        brand_id=_u.UUID(brand_id),
        input_payload={
            "raw_input": {
                "topic": "Por qué lloramos al cortar cebolla",
                "objective": "Este post debe ser 100% una curiosidad o dato interesante",
                "platform": "INSTAGRAM",
            }
        },
    )

    prompt = _build_image_prompt(job, db)
    assert "literally depict" in prompt
    assert "onions actually being cut" in prompt
    assert "curiosidad" in prompt.lower()


def test_image_job_does_not_create_asset_on_failure(bootstrap, db):
    client, _, _ = bootstrap(Role.OWNER, "img-fail-noasset@example.com")
    brand_id = _brand(client)
    before = db.execute(
        select(Asset).where(Asset.brand_id == _u.UUID(brand_id))
    ).scalars().all()
    assert len(before) == 0

    client.post(
        "/api/v1/generation-jobs",
        json=_image_job_payload(brand_id, topic="__mock_provider_error__"),
    )

    after = db.execute(
        select(Asset).where(Asset.brand_id == _u.UUID(brand_id))
    ).scalars().all()
    assert len(after) == 0
