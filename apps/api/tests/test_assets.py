from __future__ import annotations

import base64
import uuid as _u

from app.models.membership import Role

_PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 200
_JPEG = b"\xff\xd8\xff" + b"\x00" * 200
_GARBAGE = b"not a real file" * 20
_SVG = b"<svg xmlns='http://www.w3.org/2000/svg'></svg>" + b" " * 100


def _brand(client):
    slug = f"brand-{_u.uuid4().hex[:6]}"
    return client.post("/api/v1/brands", json={"name": slug, "slug": slug}).json()["id"]


def _init(client, brand_id, filename="photo.png", mime="image/png", asset_type="IMAGE", size=len(_PNG)):
    return client.post(
        "/api/v1/assets/init-upload",
        json={
            "filename": filename,
            "mime_type": mime,
            "size_bytes": size,
            "asset_type": asset_type,
            "brand_id": brand_id,
        },
    )


def test_init_and_complete_upload_ready(bootstrap):
    client, _, _ = bootstrap(Role.MARKETER, "asset-ok@example.com")
    brand_id = _brand(client)
    r = _init(client, brand_id)
    assert r.status_code == 201, r.text
    asset_id = r.json()["asset_id"]

    r2 = client.post(
        "/api/v1/assets/complete-upload",
        json={"asset_id": asset_id, "content_base64": base64.b64encode(_PNG).decode()},
    )
    assert r2.status_code == 200, r2.text
    body = r2.json()
    assert body["status"] == "READY"
    assert body["mime_type"] == "image/png"
    assert body["checksum_sha256"]
    assert body["public_id"].startswith("as_")


def test_upload_invalid_mime_rejected(bootstrap):
    client, _, _ = bootstrap(Role.MARKETER, "asset-badmime@example.com")
    brand_id = _brand(client)
    asset_id = _init(client, brand_id).json()["asset_id"]
    r = client.post(
        "/api/v1/assets/complete-upload",
        json={"asset_id": asset_id, "content_base64": base64.b64encode(_GARBAGE).decode()},
    )
    assert r.status_code == 422
    row = client.get(f"/api/v1/assets/{asset_id}").json()
    assert row["status"] == "REJECTED"


def test_upload_svg_rejected(bootstrap):
    client, _, _ = bootstrap(Role.MARKETER, "asset-svg@example.com")
    brand_id = _brand(client)
    asset_id = _init(client, brand_id, filename="evil.svg", mime="image/svg+xml").json()["asset_id"]
    r = client.post(
        "/api/v1/assets/complete-upload",
        json={"asset_id": asset_id, "content_base64": base64.b64encode(_SVG).decode()},
    )
    assert r.status_code == 422


def test_upload_oversized_rejected(bootstrap, monkeypatch):
    client, _, _ = bootstrap(Role.MARKETER, "asset-oversize@example.com")
    brand_id = _brand(client)
    from app.core.config import settings

    monkeypatch.setattr(settings, "asset_max_image_mb", 0)
    asset_id = _init(client, brand_id).json()["asset_id"]
    r = client.post(
        "/api/v1/assets/complete-upload",
        json={"asset_id": asset_id, "content_base64": base64.b64encode(_PNG).decode()},
    )
    assert r.status_code == 422
    assert "exceeds" in r.json()["detail"]


def test_duplicate_checksum_detected(bootstrap):
    client, _, _ = bootstrap(Role.MARKETER, "asset-dup@example.com")
    brand_id = _brand(client)

    id1 = _init(client, brand_id, filename="a.png").json()["asset_id"]
    client.post(
        "/api/v1/assets/complete-upload",
        json={"asset_id": id1, "content_base64": base64.b64encode(_PNG).decode()},
    )
    id2 = _init(client, brand_id, filename="b.png").json()["asset_id"]
    r2 = client.post(
        "/api/v1/assets/complete-upload",
        json={"asset_id": id2, "content_base64": base64.b64encode(_PNG).decode()},
    )
    assert r2.status_code == 200
    body = r2.json()
    meta = body.get("metadata") or body.get("asset_metadata") or {}
    assert meta.get("duplicate_of")


def test_archived_asset_cannot_be_updated(bootstrap):
    client, _, _ = bootstrap(Role.MARKETER, "asset-archive@example.com")
    brand_id = _brand(client)
    asset_id = _init(client, brand_id).json()["asset_id"]
    client.post(
        "/api/v1/assets/complete-upload",
        json={"asset_id": asset_id, "content_base64": base64.b64encode(_PNG).decode()},
    )
    r_archive = client.post(f"/api/v1/assets/{asset_id}/archive")
    assert r_archive.status_code == 200
    assert r_archive.json()["status"] == "ARCHIVED"

    r_update = client.patch(f"/api/v1/assets/{asset_id}", json={"caption": "nope"})
    assert r_update.status_code == 400


def test_download_url_requires_ready(bootstrap):
    client, _, _ = bootstrap(Role.MARKETER, "asset-notready@example.com")
    brand_id = _brand(client)
    asset_id = _init(client, brand_id).json()["asset_id"]  # still UPLOADING
    r = client.get(f"/api/v1/assets/{asset_id}/download-url")
    assert r.status_code == 400


def test_download_url_blocked_for_analyst_and_viewer(bootstrap, make_user, add_member, db):
    client, org_id, _ = bootstrap(Role.MARKETER, "asset-dl-owner@example.com")
    brand_id = _brand(client)
    asset_id = _init(client, brand_id).json()["asset_id"]
    client.post(
        "/api/v1/assets/complete-upload",
        json={"asset_id": asset_id, "content_base64": base64.b64encode(_PNG).decode()},
    )

    from app.models.organization import Organization

    org = db.get(Organization, org_id)
    for role, email in ((Role.ANALYST, "asset-dl-an@example.com"), (Role.VIEWER, "asset-dl-vw@example.com")):
        u = make_user(email)
        add_member(u, org, role)
        from app.main import app
        from tests.conftest import AuthedClient

        c = AuthedClient(app)
        r = c.post("/api/v1/auth/login", json={"email": email, "password": "Password1!"})
        assert r.status_code == 200
        c.headers["X-Organization-Id"] = str(org_id)
        r2 = c.get(f"/api/v1/assets/{asset_id}/download-url")
        assert r2.status_code == 403, f"{role} should be blocked"


def test_cross_org_asset_isolated(bootstrap):
    client_a, _, _ = bootstrap(Role.MARKETER, "asset-a@example.com")
    brand_id = _brand(client_a)
    asset_id = _init(client_a, brand_id).json()["asset_id"]

    client_b, _, _ = bootstrap(Role.MARKETER, "asset-b@example.com")
    r = client_b.get(f"/api/v1/assets/{asset_id}")
    assert r.status_code == 404


def test_sales_cannot_write_assets(bootstrap):
    client, _, _ = bootstrap(Role.SALES, "asset-sales@example.com")
    r = client.post(
        "/api/v1/assets/init-upload",
        json={
            "filename": "x.png",
            "mime_type": "image/png",
            "size_bytes": 10,
            "asset_type": "IMAGE",
        },
    )
    assert r.status_code == 403


def test_variant_requires_ready_asset(bootstrap):
    client, _, _ = bootstrap(Role.MARKETER, "asset-variant@example.com")
    brand_id = _brand(client)
    asset_id = _init(client, brand_id).json()["asset_id"]  # still UPLOADING
    r = client.post(
        f"/api/v1/assets/{asset_id}/variants",
        json={"platform": "INSTAGRAM", "variant_type": "STORY", "width": 1080, "height": 1920},
    )
    assert r.status_code == 400


def test_variant_created_for_ready_asset(bootstrap):
    client, _, _ = bootstrap(Role.MARKETER, "asset-variant-ok@example.com")
    brand_id = _brand(client)
    asset_id = _init(client, brand_id).json()["asset_id"]
    client.post(
        "/api/v1/assets/complete-upload",
        json={"asset_id": asset_id, "content_base64": base64.b64encode(_PNG).decode()},
    )
    r = client.post(
        f"/api/v1/assets/{asset_id}/variants",
        json={"platform": "INSTAGRAM", "variant_type": "STORY", "width": 1080, "height": 1920},
    )
    assert r.status_code == 201, r.text
    assert r.json()["public_id"].startswith("av_")
    r2 = client.get(f"/api/v1/assets/{asset_id}/variants")
    assert len(r2.json()) == 1
