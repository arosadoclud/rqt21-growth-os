"""Regression test for the gap found when connecting a real Meta Page:
_execute_publish and verify_connection must decrypt the PER-CONNECTION
credential and pass it into get_publishing_provider — not rely on a single
process-wide META_ACCESS_TOKEN. See app.publishing.adapters.get_publishing_provider.
"""

from __future__ import annotations

import base64
import uuid as _u

from app.models.membership import Role

_PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 200


def _brand(client) -> str:
    slug = f"brand-{_u.uuid4().hex[:6]}"
    return client.post("/api/v1/brands", json={"name": slug, "slug": slug}).json()["id"]


def test_publish_passes_connections_own_token_to_provider(bootstrap, monkeypatch, db):
    client, _, _ = bootstrap(Role.OWNER, "meta-wire@example.com")
    brand_id = _brand(client)

    cid = client.post(
        "/api/v1/content-items", json={"brand_id": brand_id, "title": "Meta wiring test"}
    ).json()["id"]
    client.post(f"/api/v1/content-items/{cid}/approve", json={"score": 90})

    conn = client.post(
        "/api/v1/publishing-connections",
        json={
            "brand_id": brand_id,
            "platform": "INSTAGRAM",
            "provider": "META",
            "account_name": "test-ig-account",
            "external_account_id": "17841400000000000",
            "credentials": {"access_token": "org-specific-page-token-abc123"},
        },
    ).json()

    # New META connections start PENDING until verified — force ACTIVE
    # directly rather than going through /verify (covered separately below).
    from app.models.publishing import PublishingConnection

    conn_row = db.get(PublishingConnection, _u.UUID(conn["id"]))
    conn_row.status = "ACTIVE"
    db.commit()

    asset = client.post(
        "/api/v1/assets/init-upload",
        json={
            "filename": "p.png", "mime_type": "image/png", "size_bytes": len(_PNG),
            "asset_type": "IMAGE", "brand_id": brand_id, "alt_text": "alt",
        },
    ).json()
    client.post(
        "/api/v1/assets/complete-upload",
        json={"asset_id": asset["asset_id"], "content_base64": base64.b64encode(_PNG).decode()},
    )

    pub = client.post(
        "/api/v1/publications",
        json={
            "content_item_id": cid, "brand_id": brand_id,
            "publishing_connection_id": conn["id"], "asset_id": asset["asset_id"],
            "platform": "INSTAGRAM", "publication_type": "POST",
            "caption": "Testing real Meta wiring",
        },
    ).json()

    captured: dict[str, str] = {}

    def _fake_get_publishing_provider(provider_name, *, access_token=""):
        captured["provider_name"] = provider_name
        captured["access_token"] = access_token

        class _StubProvider:
            async def validate(self, payload):
                from app.publishing.adapters import ValidationResult

                return ValidationResult(ok=True)

            async def publish(self, payload, idempotency_key):
                from app.publishing.adapters import PublishPermanentError

                raise PublishPermanentError("stub — not actually calling Meta in a test")

        return _StubProvider()

    monkeypatch.setattr(
        "app.api.v1.publications.get_publishing_provider", _fake_get_publishing_provider
    )

    r_val = client.post(f"/api/v1/publications/{pub['id']}/validate")
    assert r_val.status_code == 200, r_val.text

    r = client.post(f"/api/v1/publications/{pub['id']}/publish")
    assert r.status_code == 200, r.text

    assert captured["provider_name"] == "META"
    assert captured["access_token"] == "org-specific-page-token-abc123"


def test_verify_connection_passes_own_token_to_provider(bootstrap, monkeypatch):
    client, _, _ = bootstrap(Role.OWNER, "meta-verify-wire@example.com")
    brand_id = _brand(client)

    conn = client.post(
        "/api/v1/publishing-connections",
        json={
            "brand_id": brand_id,
            "platform": "INSTAGRAM",
            "provider": "META",
            "account_name": "test-ig-account",
            "external_account_id": "17841400000000000",
            "credentials": {"access_token": "verify-token-xyz789"},
        },
    ).json()

    captured: dict[str, str] = {}

    async def _fake_verify_meta_account_reachable(access_token, external_account_id, **kwargs):
        captured["access_token"] = access_token

    monkeypatch.setattr(
        "app.api.v1.publishing_connections.verify_meta_account_reachable",
        _fake_verify_meta_account_reachable,
    )

    r = client.post(f"/api/v1/publishing-connections/{conn['id']}/verify")
    assert r.status_code == 200, r.text
    assert captured["access_token"] == "verify-token-xyz789"
    assert r.json()["status"] == "ACTIVE"
