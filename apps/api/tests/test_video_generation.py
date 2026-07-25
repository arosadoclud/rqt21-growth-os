"""GenerationType.VIDEO_ASSET: script (MockAIProvider) -> scene images
(MockImageProvider) -> narration (MockTTSProvider, real silent audio via the
bundled ffmpeg binary) -> ffmpeg assembly, covered end-to-end through the
API — never a real OpenAI/Anthropic call in tests, same convention as every
other real-provider gate in this codebase."""

from __future__ import annotations

import uuid as _u

from app.core.config import settings
from app.models.assets import Asset
from app.models.enums import AssetStatus, AssetType
from app.models.membership import Role


def _brand(client):
    slug = f"brand-{_u.uuid4().hex[:6]}"
    return client.post("/api/v1/brands", json={"name": slug, "slug": slug}).json()["id"]


def _video_job_payload(brand_id: str, topic: str = "una receta de bowl keto de pollo") -> dict:
    return {
        "brand_id": brand_id,
        "generation_type": "VIDEO_ASSET",
        "input": {
            "objective": "engagement",
            "platform": "INSTAGRAM",
            "topic": topic,
            "audience": "adultos 30-50",
        },
    }


def test_create_video_job_completes_and_creates_video_asset(bootstrap, db):
    client, _, _ = bootstrap(Role.OWNER, "video-create@example.com")
    brand_id = _brand(client)
    r = client.post("/api/v1/generation-jobs", json=_video_job_payload(brand_id))
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["status"] == "COMPLETED", body
    assert body["provider"] == "MOCK"
    assert body["output_payload"]["asset_id"]
    assert body["output_payload"]["scene_count"] >= 1
    assert body["output_payload"]["script"]
    assert len(body["output_payload"]["hashtags"]) >= 1

    asset_id = _u.UUID(body["output_payload"]["asset_id"])
    asset = db.get(Asset, asset_id)
    assert asset is not None
    assert asset.asset_type == AssetType.VIDEO
    assert asset.status == AssetStatus.READY
    assert asset.mime_type == "video/mp4"
    assert asset.brand_id == _u.UUID(brand_id)
    assert asset.size_bytes > 0
    assert asset.checksum_sha256


def test_video_job_stock_footage_source_completes(bootstrap, db, monkeypatch):
    """AI_VIDEO_SCENE_SOURCE=STOCK_FOOTAGE: real clips of people/food prep
    instead of AI-generated stills — MockStockVideoProvider stands in for
    Pexels here (no PEXELS_API_KEY configured), same offline-but-real-bytes
    convention as every other mock in this codebase."""
    monkeypatch.setattr(settings, "ai_video_scene_source", "STOCK_FOOTAGE")
    client, _, _ = bootstrap(Role.OWNER, "video-stock@example.com")
    brand_id = _brand(client)
    r = client.post("/api/v1/generation-jobs", json=_video_job_payload(brand_id))
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["status"] == "COMPLETED", body
    assert body["output_payload"]["asset_id"]

    asset_id = _u.UUID(body["output_payload"]["asset_id"])
    asset = db.get(Asset, asset_id)
    assert asset is not None
    assert asset.asset_type == AssetType.VIDEO
    assert asset.status == AssetStatus.READY
    assert asset.size_bytes > 0


def test_video_job_mock_timeout_marks_failed(bootstrap):
    client, _, _ = bootstrap(Role.OWNER, "video-timeout@example.com")
    brand_id = _brand(client)
    r = client.post(
        "/api/v1/generation-jobs",
        json=_video_job_payload(brand_id, topic="__mock_timeout__"),
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["status"] == "FAILED"
    assert body["error_code"] == "timeout"
