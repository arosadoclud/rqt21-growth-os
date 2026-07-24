from __future__ import annotations

import uuid as _u

from sqlalchemy import select

from app.models.audit_log import AuditLog
from app.models.enums import LeadActivityType, LeadStatus
from app.models.lead import Lead, LeadActivity
from app.models.membership import Role


def _brand(client):
    slug = f"brand-{_u.uuid4().hex[:6]}"
    return client.post("/api/v1/brands", json={"name": slug, "slug": slug}).json()["id"]


def _link(client, brand_id):
    return client.post(
        "/api/v1/tracking-links",
        json={
            "brand_id": brand_id,
            "destination_url": "https://checkout.example.com/x",
            "utm_source": "instagram",
            "utm_campaign": "seed",
        },
    ).json()


def test_create_lead_requires_contact(bootstrap):
    client, _, _ = bootstrap(Role.OWNER, "ld-nc@example.com")
    r = client.post("/api/v1/leads", json={"first_name": "X"})
    assert r.status_code == 422


def test_create_lead_email_lowercased(bootstrap):
    client, _, _ = bootstrap(Role.OWNER, "ld-em@example.com")
    r = client.post(
        "/api/v1/leads",
        json={"first_name": "Ana", "email": "Ana.R@Example.COM"},
    )
    assert r.status_code == 201
    assert r.json()["email"] == "ana.r@example.com"


def test_sales_can_create_lead(bootstrap):
    client, _, _ = bootstrap(Role.SALES, "sales-ld@example.com")
    r = client.post("/api/v1/leads", json={"first_name": "S", "phone": "+51 987 654 321"})
    assert r.status_code == 201
    assert r.json()["phone"].startswith("+")


def test_viewer_cannot_create(bootstrap):
    client, _, _ = bootstrap(Role.VIEWER, "view-ld@example.com")
    r = client.post("/api/v1/leads", json={"first_name": "V", "email": "v@example.com"})
    assert r.status_code == 403


def test_activity_created_on_lead_creation(bootstrap, db):
    client, _, _ = bootstrap(Role.OWNER, "act@example.com")
    r = client.post(
        "/api/v1/leads", json={"first_name": "A", "email": "a@example.com"}
    )
    lead_id = r.json()["id"]
    acts = db.execute(
        select(LeadActivity).where(LeadActivity.lead_id == lead_id)
    ).scalars().all()
    assert len(acts) == 1
    assert acts[0].activity_type == LeadActivityType.CREATED


def test_status_change_creates_activity_and_audit(bootstrap, db):
    client, _, _ = bootstrap(Role.OWNER, "st@example.com")
    r = client.post(
        "/api/v1/leads", json={"first_name": "A", "email": "a2@example.com"}
    )
    lead_id = r.json()["id"]
    r2 = client.post(
        f"/api/v1/leads/{lead_id}/status", json={"status": "WON", "note": "closed"}
    )
    assert r2.status_code == 200
    assert r2.json()["status"] == "WON"

    acts = db.execute(
        select(LeadActivity).where(
            LeadActivity.lead_id == lead_id,
            LeadActivity.activity_type == LeadActivityType.WON,
        )
    ).scalars().all()
    assert len(acts) == 1

    audits = db.execute(
        select(AuditLog).where(AuditLog.action == "lead.status_changed")
    ).scalars().all()
    assert len(audits) == 1


def test_import_is_idempotent(bootstrap, db):
    client, _, _ = bootstrap(Role.OWNER, "imp-ld@example.com")
    payload = {
        "first_name": "Meta",
        "email": "meta.lead@example.com",
        "external_id": "ext-1",
        "source_system": "KINGDOM_STUDIO",
    }
    r1 = client.post("/api/v1/leads/import", json=payload)
    payload["first_name"] = "Meta Updated"
    r2 = client.post("/api/v1/leads/import", json=payload)
    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r1.json()["id"] == r2.json()["id"]
    rows = db.execute(select(Lead)).scalars().all()
    assert len(rows) == 1
    assert rows[0].first_name == "Meta Updated"


def test_export_returns_csv_and_audits(bootstrap, db):
    client, _, _ = bootstrap(Role.OWNER, "exp@example.com")
    client.post("/api/v1/leads", json={"first_name": "A", "email": "a3@example.com"})
    client.post("/api/v1/leads", json={"first_name": "B", "email": "b3@example.com"})
    r = client.get("/api/v1/leads/export")
    assert r.status_code == 200
    assert "text/csv" in r.headers["content-type"]
    body = r.text
    assert "a3@example.com" in body
    assert "b3@example.com" in body

    audits = db.execute(
        select(AuditLog).where(AuditLog.action == "lead.exported")
    ).scalars().all()
    assert len(audits) == 1


def test_export_escapes_csv_injection(bootstrap, db):
    client, _, _ = bootstrap(Role.OWNER, "csv@example.com")
    client.post(
        "/api/v1/leads",
        json={
            "first_name": "=SUM(A1)",
            "last_name": "+cmd|calc",
            "email": "safe@example.com",
        },
    )
    r = client.get("/api/v1/leads/export")
    # Every dangerous cell must start with a leading single-quote.
    for row in r.text.splitlines()[1:]:
        cells = row.split('","')
        for cell in cells:
            stripped = cell.replace('"', "")
            if stripped and stripped[0] in ("=", "+", "-", "@"):
                raise AssertionError(f"unescaped CSV cell: {cell!r}")


def test_analyst_cannot_export(bootstrap):
    client, _, _ = bootstrap(Role.ANALYST, "analyst-x@example.com")
    r = client.get("/api/v1/leads/export")
    assert r.status_code == 403


def test_lead_isolated_across_orgs(bootstrap):
    client_a, _, _ = bootstrap(Role.OWNER, "iso-l1@example.com")
    lead = client_a.post(
        "/api/v1/leads", json={"first_name": "X", "email": "x@example.com"}
    ).json()
    client_b, _, _ = bootstrap(Role.OWNER, "iso-l2@example.com")
    assert client_b.get(f"/api/v1/leads/{lead['id']}").status_code == 404


def test_public_lead_requires_tracking_code():
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as c:
        r = c.post("/public/leads", json={"first_name": "X", "email": "y@example.com"})
        assert r.status_code == 400


def test_public_lead_creates_with_attribution(bootstrap, db):
    from fastapi.testclient import TestClient

    from app.main import app

    client, _, _ = bootstrap(Role.OWNER, "pub-ld@example.com")
    brand_id = _brand(client)
    link = _link(client, brand_id)

    with TestClient(app) as public:
        r = public.post(
            "/public/leads",
            json={
                "first_name": "Public",
                "email": "public@example.com",
                "tracking_code": link["short_code"],
            },
        )
        assert r.status_code == 201, r.text
        assert "reference" in r.json()

    lead = db.execute(
        select(Lead).where(Lead.email == "public@example.com")
    ).scalar_one()
    assert str(lead.tracking_link_id) == link["id"]
    assert lead.utm_source == "instagram"
    assert lead.status == LeadStatus.NEW


def test_public_lead_rate_limit(bootstrap, monkeypatch):
    from fastapi.testclient import TestClient

    from app import rate_limit
    from app.core import config as config_mod
    from app.main import app

    client, _, _ = bootstrap(Role.OWNER, "rl-ld@example.com")
    brand_id = _brand(client)
    link = _link(client, brand_id)

    monkeypatch.setattr(config_mod.settings, "public_lead_rate_limit", 3, raising=True)
    monkeypatch.setattr(
        config_mod.settings, "public_lead_window_seconds", 60, raising=True
    )
    rate_limit.reset()

    with TestClient(app) as public:
        for i in range(3):
            r = public.post(
                "/public/leads",
                json={
                    "first_name": f"P{i}",
                    "email": f"p{i}@example.com",
                    "tracking_code": link["short_code"],
                },
            )
            assert r.status_code == 201, r.text
        r = public.post(
            "/public/leads",
            json={
                "first_name": "PLast",
                "email": "plast@example.com",
                "tracking_code": link["short_code"],
            },
        )
        assert r.status_code == 429
        assert "Retry-After" in r.headers


def test_public_lead_honeypot_silently_accepted():
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as public:
        r = public.post(
            "/public/leads",
            json={
                "first_name": "Bot",
                "email": "bot@example.com",
                "tracking_code": "anything",
                "website": "https://spam.example",
            },
        )
        assert r.status_code == 201
        assert r.json()["accepted"] is True
