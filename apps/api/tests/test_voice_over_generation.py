"""GenerationType.VOICE_OVER: script (MockAIProvider) -> narration only
(MockTTSProvider, real silent audio via the bundled ffmpeg binary) -> Asset,
skipping the scene/image/ffmpeg-assembly steps VIDEO_ASSET does. Covered
end-to-end through the API — never a real OpenAI/ElevenLabs call in tests."""

from __future__ import annotations

import uuid as _u

from app.models.assets import Asset
from app.models.enums import AssetStatus, AssetType
from app.models.membership import Role


def _brand(client):
    slug = f"brand-{_u.uuid4().hex[:6]}"
    return client.post("/api/v1/brands", json={"name": slug, "slug": slug}).json()["id"]


def _voice_over_payload(brand_id: str, topic: str = "una receta de bowl keto de pollo") -> dict:
    return {
        "brand_id": brand_id,
        "generation_type": "VOICE_OVER",
        "input": {
            "objective": "engagement",
            "platform": "INSTAGRAM",
            "topic": topic,
            "audience": "adultos 30-50",
        },
    }


def test_create_voice_over_job_completes_and_creates_audio_asset(bootstrap, db):
    client, _, _ = bootstrap(Role.OWNER, "voice-over-create@example.com")
    brand_id = _brand(client)
    r = client.post("/api/v1/generation-jobs", json=_voice_over_payload(brand_id))
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["status"] == "COMPLETED", body
    assert body["provider"] == "MOCK"
    assert body["output_payload"]["asset_id"]
    assert body["output_payload"]["script"]
    assert body["stage"] is None

    asset_id = _u.UUID(body["output_payload"]["asset_id"])
    asset = db.get(Asset, asset_id)
    assert asset is not None
    assert asset.asset_type == AssetType.AUDIO
    assert asset.status == AssetStatus.READY
    assert asset.mime_type == "audio/mpeg"
    assert asset.brand_id == _u.UUID(brand_id)
    assert asset.size_bytes > 0
    assert asset.checksum_sha256


def test_voice_over_job_does_not_create_video_or_image_assets(bootstrap, db):
    client, _, _ = bootstrap(Role.OWNER, "voice-over-scope@example.com")
    brand_id = _brand(client)
    r = client.post("/api/v1/generation-jobs", json=_voice_over_payload(brand_id))
    assert r.status_code == 201, r.text
    body = r.json()
    assert "scene_count" not in body["output_payload"]

    asset_id = _u.UUID(body["output_payload"]["asset_id"])
    asset = db.get(Asset, asset_id)
    assert asset.asset_type == AssetType.AUDIO
