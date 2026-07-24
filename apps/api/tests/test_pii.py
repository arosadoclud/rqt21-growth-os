from __future__ import annotations

import uuid as _u

from app.models.membership import Role
from tests.conftest import AuthedClient


def _add_org_member(app_module, make_user, add_member, org, role: Role, email: str) -> AuthedClient:
    user = make_user(email)
    add_member(user, org, role)
    c = AuthedClient(app_module)
    r = c.post("/api/v1/auth/login", json={"email": email, "password": "Password1!"})
    assert r.status_code == 200, r.text
    c.headers["X-Organization-Id"] = str(org.id)
    return c


def _second_client(bootstrap_org_id, make_user, add_member, db, role: Role, email: str) -> AuthedClient:
    from app.main import app as fastapi_app
    from app.models.organization import Organization

    org = db.get(Organization, bootstrap_org_id)
    return _add_org_member(fastapi_app, make_user, add_member, org, role, email)


def test_owner_receives_full_pii(bootstrap):
    client, _, _ = bootstrap(Role.OWNER, "pii-owner@example.com")
    r = client.post(
        "/api/v1/leads",
        json={"first_name": "Ana", "email": "ana.full@example.com", "phone": "+18092223333"},
    )
    assert r.status_code == 201
    body = r.json()
    assert body["email"] == "ana.full@example.com"
    assert body["phone"] == "+18092223333"
    assert body["pii_access"] == "full"


def test_sales_receives_full_pii(bootstrap, make_user, add_member, db):
    client, org_id, _ = bootstrap(Role.OWNER, "pii-sales-owner@example.com")
    client.post(
        "/api/v1/leads",
        json={"first_name": "Bea", "email": "bea.full@example.com"},
    )
    sales = _second_client(org_id, make_user, add_member, db, Role.SALES, "pii-sales@example.com")
    r = sales.get("/api/v1/leads")
    assert r.status_code == 200
    lead = next(x for x in r.json() if x["first_name"] == "Bea")
    assert lead["email"] == "bea.full@example.com"
    assert lead["pii_access"] == "full"


def test_analyst_gets_redacted_pii_in_list(bootstrap, make_user, add_member, db):
    client, org_id, _ = bootstrap(Role.OWNER, "pii-an-owner@example.com")
    client.post(
        "/api/v1/leads",
        json={
            "first_name": "Carla",
            "email": "carla.secret@example.com",
            "phone": "+18092223333",
            "notes": "very private note",
        },
    )
    analyst = _second_client(org_id, make_user, add_member, db, Role.ANALYST, "pii-an@example.com")
    r = analyst.get("/api/v1/leads")
    assert r.status_code == 200
    lead = next(x for x in r.json() if x["first_name"] == "Carla")
    assert lead["email"] != "carla.secret@example.com"
    assert lead["email"].startswith("c")
    assert "@example.com" in lead["email"]
    assert lead["phone"] != "+18092223333"
    assert lead["phone"].endswith("3333")
    assert "***" in lead["phone"] or "*" in lead["phone"]
    assert lead["notes"] is None
    assert lead["pii_access"] == "redacted"


def test_viewer_gets_redacted_pii_in_detail(bootstrap, make_user, add_member, db):
    client, org_id, _ = bootstrap(Role.OWNER, "pii-v-owner@example.com")
    created = client.post(
        "/api/v1/leads",
        json={
            "first_name": "Dana",
            "email": "dana.secret@example.com",
            "whatsapp": "+18092223333",
            "notes": "sensitive",
        },
    ).json()
    viewer = _second_client(org_id, make_user, add_member, db, Role.VIEWER, "pii-v@example.com")
    r = viewer.get(f"/api/v1/leads/{created['id']}")
    assert r.status_code == 200
    body = r.json()
    assert body["email"] != "dana.secret@example.com"
    assert body["whatsapp"] != "+18092223333"
    assert body["notes"] is None
    assert body["pii_access"] == "redacted"


def test_search_by_email_does_not_leak_pii_for_analyst(bootstrap, make_user, add_member, db):
    client, org_id, _ = bootstrap(Role.OWNER, "pii-search-owner@example.com")
    client.post(
        "/api/v1/leads",
        json={"first_name": "Elena", "email": "elena.unique@example.com"},
    )
    analyst = _second_client(
        org_id, make_user, add_member, db, Role.ANALYST, "pii-search@example.com"
    )
    # Searching by the full email must not act as an oracle: the query only
    # matches name fields for redacted roles, so this returns nothing.
    r = analyst.get("/api/v1/leads", params={"q": "elena.unique@example.com"})
    assert r.status_code == 200
    assert r.json() == []

    # But searching by (visible) name still works.
    r2 = analyst.get("/api/v1/leads", params={"q": "Elena"})
    assert r2.status_code == 200
    assert len(r2.json()) == 1
    assert r2.json()[0]["email"] != "elena.unique@example.com"


def test_export_forbidden_for_analyst_and_viewer(bootstrap, make_user, add_member, db):
    client, org_id, _ = bootstrap(Role.OWNER, "pii-exp-owner@example.com")
    analyst = _second_client(
        org_id, make_user, add_member, db, Role.ANALYST, "pii-exp-an@example.com"
    )
    viewer = _second_client(
        org_id, make_user, add_member, db, Role.VIEWER, "pii-exp-v@example.com"
    )
    assert analyst.get("/api/v1/leads/export").status_code == 403
    assert viewer.get("/api/v1/leads/export").status_code == 403


def test_activities_sanitized_for_redacted_roles(bootstrap, make_user, add_member, db):
    client, org_id, _ = bootstrap(Role.OWNER, "pii-act-owner@example.com")
    lead = client.post(
        "/api/v1/leads", json={"first_name": "Fabi", "email": "fabi@example.com"}
    ).json()
    client.post(
        f"/api/v1/leads/{lead['id']}/activities",
        json={
            "activity_type": "EMAIL_SENT",
            "description": "Sent a proposal to fabi@example.com with pricing details",
        },
    )
    analyst = _second_client(
        org_id, make_user, add_member, db, Role.ANALYST, "pii-act-an@example.com"
    )
    r = analyst.get(f"/api/v1/leads/{lead['id']}/activities")
    assert r.status_code == 200
    acts = r.json()
    assert len(acts) >= 1
    for a in acts:
        assert a["description"] is None
        assert a["metadata"] == {}
        # activity_type itself is fine to expose (not PII by itself)
        assert a["activity_type"]


def test_owner_activities_are_not_sanitized(bootstrap):
    client, _, _ = bootstrap(Role.OWNER, "pii-act-owner2@example.com")
    lead = client.post(
        "/api/v1/leads", json={"first_name": "Gus", "email": "gus@example.com"}
    ).json()
    client.post(
        f"/api/v1/leads/{lead['id']}/activities",
        json={"activity_type": "NOTE_ADDED", "description": "Called, left voicemail"},
    )
    r = client.get(f"/api/v1/leads/{lead['id']}/activities")
    body = r.json()
    note = next(a for a in body if a["activity_type"] == "NOTE_ADDED")
    assert note["description"] == "Called, left voicemail"


def test_mask_email_helper():
    from app.utils.pii import mask_email

    assert mask_email("andy@example.com") == "a***@example.com"
    assert mask_email(None) is None
    assert mask_email("a@example.com") == "a***@example.com"


def test_mask_phone_helper():
    from app.utils.pii import mask_phone

    assert mask_phone("+18492763532").endswith("3532")
    assert "*" in mask_phone("+18492763532")
    assert mask_phone(None) is None


_ = _u  # keep import used across helpers defined above
