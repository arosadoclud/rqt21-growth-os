from __future__ import annotations

import uuid as _u
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.models.ai import PublicLeadSource
from app.models.audit_log import AuditLog
from app.models.membership import Role


def _brand(client):
    slug = f"brand-{_u.uuid4().hex[:6]}"
    return client.post("/api/v1/brands", json={"name": slug, "slug": slug}).json()["id"]


def test_create_source(bootstrap, db):
    client, org_id, _ = bootstrap(Role.OWNER, "pls-create@example.com")
    brand_id = _brand(client)
    r = client.post(
        "/api/v1/public-lead-sources",
        json={"name": "Landing A", "brand_id": brand_id},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["public_id"].startswith("pls_")
    assert body["public_token"]
    assert body["is_active"] is True

    audits = db.execute(
        select(AuditLog).where(AuditLog.action == "public_lead_source.created")
    ).scalars().all()
    assert len(audits) == 1


def test_marketer_can_create_source(bootstrap):
    client, _, _ = bootstrap(Role.MARKETER, "pls-mkt@example.com")
    brand_id = _brand(client)
    r = client.post(
        "/api/v1/public-lead-sources", json={"name": "Landing B", "brand_id": brand_id}
    )
    assert r.status_code == 201


def test_sales_cannot_create_source(bootstrap):
    client, _, _ = bootstrap(Role.SALES, "pls-sales@example.com")
    r = client.post("/api/v1/public-lead-sources", json={"name": "X"})
    assert r.status_code == 403


def test_rotate_token_changes_it_and_audits(bootstrap, db):
    client, _, _ = bootstrap(Role.OWNER, "pls-rot@example.com")
    src = client.post("/api/v1/public-lead-sources", json={"name": "Rotate me"}).json()
    old_token = src["public_token"]
    r = client.post(f"/api/v1/public-lead-sources/{src['id']}/rotate-token")
    assert r.status_code == 200
    assert r.json()["public_token"] != old_token

    audits = db.execute(
        select(AuditLog).where(AuditLog.action == "public_lead_source.token_rotated")
    ).scalars().all()
    assert len(audits) == 1


def test_deactivate_source(bootstrap, db):
    client, _, _ = bootstrap(Role.OWNER, "pls-deact@example.com")
    src = client.post("/api/v1/public-lead-sources", json={"name": "Deactivate me"}).json()
    r = client.post(f"/api/v1/public-lead-sources/{src['id']}/deactivate")
    assert r.status_code == 200
    assert r.json()["is_active"] is False

    audits = db.execute(
        select(AuditLog).where(AuditLog.action == "public_lead_source.deactivated")
    ).scalars().all()
    assert len(audits) == 1


def test_capture_via_public_source_token(bootstrap, raw_client, db):
    client, org_id, _ = bootstrap(Role.OWNER, "pls-cap@example.com")
    src = client.post(
        "/api/v1/public-lead-sources",
        json={
            "name": "Capture landing",
            "default_utm_source": "landing",
            "default_utm_campaign": "spring",
        },
    ).json()

    r = raw_client.post(
        "/public/leads",
        json={
            "first_name": "Public",
            "email": "public.token@example.com",
            "public_source_token": src["public_token"],
        },
    )
    assert r.status_code == 201, r.text
    assert "reference" in r.json()

    from app.models.lead import Lead

    lead = db.execute(select(Lead).where(Lead.email == "public.token@example.com")).scalar_one()
    assert lead.organization_id == org_id
    assert lead.utm_source == "landing"
    assert lead.utm_campaign == "spring"


def test_capture_normalizes_whatsapp(bootstrap, raw_client, db):
    client, org_id, _ = bootstrap(Role.OWNER, "pls-wa@example.com")
    src = client.post("/api/v1/public-lead-sources", json={"name": "WA landing"}).json()

    r = raw_client.post(
        "/public/leads",
        json={
            "first_name": "Wanda",
            "whatsapp": "809 222 3333",
            "public_source_token": src["public_token"],
        },
    )
    assert r.status_code == 201

    from app.models.lead import Lead

    lead = db.execute(select(Lead).where(Lead.first_name == "Wanda")).scalar_one()
    assert lead.whatsapp == "+18092223333"


def test_capture_with_invalid_token_generic_error(raw_client):
    r = raw_client.post(
        "/public/leads",
        json={
            "first_name": "X",
            "email": "x@example.com",
            "public_source_token": "totally-made-up-token",
        },
    )
    assert r.status_code == 400
    # Generic error — does not reveal whether the token exists.
    assert "invalid" in r.json()["detail"].lower()


def test_capture_with_expired_source_rejected(bootstrap, raw_client, db):
    client, _, _ = bootstrap(Role.OWNER, "pls-exp@example.com")
    src = client.post("/api/v1/public-lead-sources", json={"name": "Expired"}).json()

    row = db.execute(
        select(PublicLeadSource).where(PublicLeadSource.id == src["id"])
    ).scalar_one()
    row.expires_at = datetime.now(UTC) - timedelta(days=1)
    db.commit()

    r = raw_client.post(
        "/public/leads",
        json={
            "first_name": "X",
            "email": "expired@example.com",
            "public_source_token": src["public_token"],
        },
    )
    assert r.status_code == 400


def test_capture_with_deactivated_source_rejected(bootstrap, raw_client):
    client, _, _ = bootstrap(Role.OWNER, "pls-deact2@example.com")
    src = client.post("/api/v1/public-lead-sources", json={"name": "ToDeactivate"}).json()
    client.post(f"/api/v1/public-lead-sources/{src['id']}/deactivate")

    r = raw_client.post(
        "/public/leads",
        json={
            "first_name": "X",
            "email": "deact@example.com",
            "public_source_token": src["public_token"],
        },
    )
    assert r.status_code == 400


def test_capture_requires_exactly_one_attribution_source(raw_client):
    r = raw_client.post(
        "/public/leads", json={"first_name": "X", "email": "neither@example.com"}
    )
    assert r.status_code == 400

    r2 = raw_client.post(
        "/public/leads",
        json={
            "first_name": "X",
            "email": "both@example.com",
            "tracking_code": "abc",
            "public_source_token": "def",
        },
    )
    assert r2.status_code == 400


def test_source_isolated_across_orgs(bootstrap):
    client_a, _, _ = bootstrap(Role.OWNER, "pls-iso-a@example.com")
    src = client_a.post("/api/v1/public-lead-sources", json={"name": "A"}).json()
    client_b, _, _ = bootstrap(Role.OWNER, "pls-iso-b@example.com")
    r = client_b.patch(f"/api/v1/public-lead-sources/{src['id']}", json={"name": "hijack"})
    assert r.status_code == 404


def test_origin_allowlist_rejects_unlisted_origin(bootstrap, raw_client):
    client, _, _ = bootstrap(Role.OWNER, "pls-origin@example.com")
    src = client.post(
        "/api/v1/public-lead-sources",
        json={"name": "Strict origin", "allowed_origins": ["https://allowed.example.com"]},
    ).json()

    r = raw_client.post(
        "/public/leads",
        json={
            "first_name": "X",
            "email": "bad-origin@example.com",
            "public_source_token": src["public_token"],
        },
        headers={"origin": "https://evil.example.com"},
    )
    assert r.status_code == 400


def test_origin_allowlist_accepts_listed_origin(bootstrap, raw_client):
    client, _, _ = bootstrap(Role.OWNER, "pls-origin-ok@example.com")
    src = client.post(
        "/api/v1/public-lead-sources",
        json={"name": "Strict origin ok", "allowed_origins": ["https://allowed.example.com"]},
    ).json()

    r = raw_client.post(
        "/public/leads",
        json={
            "first_name": "X",
            "email": "good-origin@example.com",
            "public_source_token": src["public_token"],
        },
        headers={"origin": "https://allowed.example.com"},
    )
    assert r.status_code == 201


def test_honeypot_silently_accepted_for_source_token(raw_client):
    r = raw_client.post(
        "/public/leads",
        json={
            "first_name": "Bot",
            "email": "bot2@example.com",
            "public_source_token": "whatever",
            "website": "https://spam.example",
        },
    )
    assert r.status_code == 201
    assert r.json()["accepted"] is True
