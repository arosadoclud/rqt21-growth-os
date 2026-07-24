from __future__ import annotations

import uuid as _u

from app.models.membership import Role


def _brand(client):
    slug = f"brand-{_u.uuid4().hex[:6]}"
    return client.post("/api/v1/brands", json={"name": slug, "slug": slug}).json()["id"]


def _mock_conn(client, brand_id, **overrides):
    payload = {
        "brand_id": brand_id,
        "platform": "INSTAGRAM",
        "provider": "MOCK",
        "account_name": "rqt21.mock",
        "credentials": {"access_token": "super-secret-token-1234"},
    }
    payload.update(overrides)
    return client.post("/api/v1/publishing-connections", json=payload)


def test_owner_creates_mock_connection_active(bootstrap):
    client, _, _ = bootstrap(Role.OWNER, "pcn-owner@example.com")
    brand_id = _brand(client)
    r = _mock_conn(client, brand_id)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["status"] == "ACTIVE"
    assert body["public_id"].startswith("pcn_")
    assert "credentials" not in body
    assert "credentials_encrypted" not in body
    assert body["credentials_last_four"] == "1234"


def test_marketer_cannot_administer_connections(bootstrap):
    client, _, _ = bootstrap(Role.MARKETER, "pcn-mkt@example.com")
    brand_id = _brand(client)
    r = _mock_conn(client, brand_id)
    assert r.status_code == 403


def test_marketer_sees_status_but_not_secrets(bootstrap, make_user, add_member, db):
    owner_client, org_id, _ = bootstrap(Role.OWNER, "pcn-mkt-owner@example.com")
    brand_id = _brand(owner_client)
    conn_id = _mock_conn(owner_client, brand_id).json()["id"]

    from app.main import app
    from app.models.organization import Organization
    from tests.conftest import AuthedClient

    org = db.get(Organization, org_id)
    u = make_user("pcn-mkt-view@example.com")
    add_member(u, org, Role.MARKETER)
    c = AuthedClient(app)
    r = c.post(
        "/api/v1/auth/login", json={"email": "pcn-mkt-view@example.com", "password": "Password1!"}
    )
    assert r.status_code == 200
    c.headers["X-Organization-Id"] = str(org_id)

    r2 = c.get(f"/api/v1/publishing-connections/{conn_id}")
    assert r2.status_code == 200
    body = r2.json()
    assert body["status"] == "ACTIVE"
    assert body["credentials_last_four"] is None


def test_viewer_forbidden_from_connections(bootstrap, make_user, add_member, db):
    owner_client, org_id, _ = bootstrap(Role.OWNER, "pcn-vw-owner@example.com")
    from app.main import app
    from app.models.organization import Organization
    from tests.conftest import AuthedClient

    org = db.get(Organization, org_id)
    u = make_user("pcn-vw@example.com")
    add_member(u, org, Role.VIEWER)
    c = AuthedClient(app)
    r = c.post("/api/v1/auth/login", json={"email": "pcn-vw@example.com", "password": "Password1!"})
    assert r.status_code == 200
    c.headers["X-Organization-Id"] = str(org_id)

    r2 = c.get("/api/v1/publishing-connections")
    assert r2.status_code == 403


def test_verify_mock_connection_succeeds(bootstrap):
    client, _, _ = bootstrap(Role.OWNER, "pcn-verify@example.com")
    brand_id = _brand(client)
    conn_id = _mock_conn(client, brand_id).json()["id"]
    r = client.post(f"/api/v1/publishing-connections/{conn_id}/verify")
    assert r.status_code == 200
    assert r.json()["status"] == "ACTIVE"
    assert r.json()["last_verified_at"] is not None


def test_revoke_clears_credentials_hint(bootstrap):
    client, _, _ = bootstrap(Role.OWNER, "pcn-revoke@example.com")
    brand_id = _brand(client)
    conn_id = _mock_conn(client, brand_id).json()["id"]
    r = client.post(f"/api/v1/publishing-connections/{conn_id}/revoke")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "REVOKED"
    assert body["credentials_last_four"] is None


def test_disable_connection(bootstrap):
    client, _, _ = bootstrap(Role.OWNER, "pcn-disable@example.com")
    brand_id = _brand(client)
    conn_id = _mock_conn(client, brand_id).json()["id"]
    r = client.post(f"/api/v1/publishing-connections/{conn_id}/disable")
    assert r.status_code == 200
    assert r.json()["status"] == "DISABLED"


def test_manual_connection_has_no_credentials(bootstrap):
    client, _, _ = bootstrap(Role.OWNER, "pcn-manual@example.com")
    brand_id = _brand(client)
    r = _mock_conn(
        client, brand_id, provider="MANUAL", credentials=None, account_name="Equipo social"
    )
    assert r.status_code == 201
    body = r.json()
    assert body["status"] == "ACTIVE"
    assert body["credentials_last_four"] is None


def test_cross_org_connection_isolated(bootstrap):
    client_a, _, _ = bootstrap(Role.OWNER, "pcn-a@example.com")
    brand_id = _brand(client_a)
    conn_id = _mock_conn(client_a, brand_id).json()["id"]

    client_b, _, _ = bootstrap(Role.OWNER, "pcn-b@example.com")
    r = client_b.get(f"/api/v1/publishing-connections/{conn_id}")
    assert r.status_code == 404


def test_credentials_never_logged_in_audit(bootstrap, db):
    from sqlalchemy import select

    from app.models.audit_log import AuditLog

    client, org_id, _ = bootstrap(Role.OWNER, "pcn-audit@example.com")
    brand_id = _brand(client)
    _mock_conn(client, brand_id)

    rows = db.execute(
        select(AuditLog).where(
            AuditLog.organization_id == org_id,
            AuditLog.action == "publishing_connection.created",
        )
    ).scalars().all()
    assert len(rows) == 1
    payload_str = str(rows[0].payload)
    assert "super-secret-token-1234" not in payload_str
