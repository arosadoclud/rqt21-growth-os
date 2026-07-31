"""app.workers.cleanup_published_assets: deletes the storage bytes behind
an Asset once every Publication referencing it has actually gone out and
the configured grace period has passed — never touches an asset that's
still needed (draft/scheduled/failed publications) or that was never
actually published."""

from __future__ import annotations

import base64
import uuid as _u
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.models.assets import Asset
from app.models.audit_log import AuditLog
from app.models.enums import AssetStatus
from app.models.membership import Role
from app.models.publishing import Publication
from app.workers.cleanup_published_assets import run_once

_PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 200


def _brand(client) -> str:
    slug = f"brand-{_u.uuid4().hex[:6]}"
    return client.post("/api/v1/brands", json={"name": slug, "slug": slug}).json()["id"]


def _approve(client, brand_id: str) -> str:
    cid = client.post(
        "/api/v1/content-items", json={"brand_id": brand_id, "title": "Bowl keto"}
    ).json()["id"]
    assert client.post(f"/api/v1/content-items/{cid}/approve", json={"score": 90}).status_code == 201
    return cid


def _mock_connection(client, brand_id: str) -> str:
    r = client.post(
        "/api/v1/publishing-connections",
        json={"brand_id": brand_id, "platform": "INSTAGRAM", "provider": "MOCK", "account_name": "rqt21.mock"},
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _ready_asset(client, brand_id: str) -> str:
    init = client.post(
        "/api/v1/assets/init-upload",
        json={
            "filename": "photo.png",
            "mime_type": "image/png",
            "size_bytes": len(_PNG),
            "asset_type": "IMAGE",
            "brand_id": brand_id,
            "alt_text": "Bowl keto servido",
        },
    ).json()
    r = client.post(
        "/api/v1/assets/complete-upload",
        json={"asset_id": init["asset_id"], "content_base64": base64.b64encode(_PNG).decode()},
    )
    assert r.status_code == 200, r.text
    return init["asset_id"]


def _publication(client, *, content_id, brand_id, connection_id, asset_id):
    r = client.post(
        "/api/v1/publications",
        json={
            "content_item_id": content_id,
            "brand_id": brand_id,
            "publishing_connection_id": connection_id,
            "asset_id": asset_id,
            "platform": "INSTAGRAM",
            "publication_type": "POST",
            "caption": "Hola, prueba.",
        },
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _setup_published(client, db, *, published_days_ago: int):
    brand_id = _brand(client)
    content_id = _approve(client, brand_id)
    connection_id = _mock_connection(client, brand_id)
    asset_id = _ready_asset(client, brand_id)
    pub_id = _publication(
        client, content_id=content_id, brand_id=brand_id, connection_id=connection_id, asset_id=asset_id
    )
    assert client.post(f"/api/v1/publications/{pub_id}/validate").json()["ok"] is True
    assert client.post(f"/api/v1/publications/{pub_id}/publish").status_code == 200

    pub = db.get(Publication, _u.UUID(pub_id))
    pub.published_at = datetime.now(UTC) - timedelta(days=published_days_ago)
    db.commit()
    return _u.UUID(asset_id), _u.UUID(pub_id)


def test_deletes_asset_after_grace_period(bootstrap, db):
    client, _, _ = bootstrap(Role.OWNER, "cleanup-old@example.com")
    asset_id, _ = _setup_published(client, db, published_days_ago=3)

    counts = run_once()
    assert counts["deleted"] == 1

    db.expire_all()
    asset = db.get(Asset, asset_id)
    assert asset.status == AssetStatus.ARCHIVED

    audits = db.execute(
        select(AuditLog).where(AuditLog.action == "asset.storage_cleaned_up")
    ).scalars().all()
    assert len(audits) == 1
    assert audits[0].target_id == str(asset_id)


def test_skips_asset_within_grace_period(bootstrap, db):
    client, _, _ = bootstrap(Role.OWNER, "cleanup-recent@example.com")
    asset_id, _ = _setup_published(client, db, published_days_ago=0)

    counts = run_once()
    assert counts["deleted"] == 0
    assert counts["skipped"] >= 1

    db.expire_all()
    asset = db.get(Asset, asset_id)
    assert asset.status == AssetStatus.READY


def test_skips_asset_with_pending_publication(bootstrap, db):
    client, _, _ = bootstrap(Role.OWNER, "cleanup-pending@example.com")
    brand_id = _brand(client)
    content_id = _approve(client, brand_id)
    connection_id = _mock_connection(client, brand_id)
    asset_id = _ready_asset(client, brand_id)
    # Draft publication only — never actually published.
    _publication(client, content_id=content_id, brand_id=brand_id, connection_id=connection_id, asset_id=asset_id)

    counts = run_once()
    assert counts["deleted"] == 0

    db.expire_all()
    asset = db.get(Asset, _u.UUID(asset_id))
    assert asset.status == AssetStatus.READY


def test_skips_asset_when_any_reference_still_pending(bootstrap, db):
    """Same asset reused by two publications — one already published long
    ago, the other still a draft. Must not delete: the draft still needs
    the file."""
    client, _, _ = bootstrap(Role.OWNER, "cleanup-mixed@example.com")
    brand_id = _brand(client)
    connection_id = _mock_connection(client, brand_id)
    asset_id = _ready_asset(client, brand_id)

    content_id_1 = _approve(client, brand_id)
    pub_id_1 = _publication(
        client, content_id=content_id_1, brand_id=brand_id, connection_id=connection_id, asset_id=asset_id
    )
    assert client.post(f"/api/v1/publications/{pub_id_1}/validate").json()["ok"] is True
    assert client.post(f"/api/v1/publications/{pub_id_1}/publish").status_code == 200
    pub_1 = db.get(Publication, _u.UUID(pub_id_1))
    pub_1.published_at = datetime.now(UTC) - timedelta(days=5)
    db.commit()

    content_id_2 = _approve(client, brand_id)
    _publication(
        client, content_id=content_id_2, brand_id=brand_id, connection_id=connection_id, asset_id=asset_id
    )  # left as DRAFT

    counts = run_once()
    assert counts["deleted"] == 0

    db.expire_all()
    asset = db.get(Asset, _u.UUID(asset_id))
    assert asset.status == AssetStatus.READY


def test_unpublished_asset_is_left_alone(bootstrap, db):
    client, _, _ = bootstrap(Role.OWNER, "cleanup-unused@example.com")
    brand_id = _brand(client)
    asset_id = _ready_asset(client, brand_id)  # never attached to any publication

    counts = run_once()
    assert counts["deleted"] == 0

    db.expire_all()
    asset = db.get(Asset, _u.UUID(asset_id))
    assert asset.status == AssetStatus.READY


def test_disabled_when_no_publications_reference_asset(bootstrap):
    """Sanity: an empty org produces a clean no-op run."""
    client, _, _ = bootstrap(Role.OWNER, "cleanup-empty@example.com")
    counts = run_once()
    assert counts == {"deleted": 0, "skipped": 0}
