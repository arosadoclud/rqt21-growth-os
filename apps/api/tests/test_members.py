from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.models.audit_log import AuditLog
from app.models.membership import Membership, Role


def test_owner_can_add_member(client: TestClient, make_user, make_org, add_member, login, db):
    owner = make_user("boss@example.com")
    org = make_org("teamco")
    add_member(owner, org, Role.OWNER)
    login("boss@example.com")

    r = client.post(
        f"/api/v1/organizations/{org.id}/members",
        json={
            "email": "new@example.com",
            "full_name": "New Person",
            "password": "TempPass123!",
            "role": "SALES",
        },
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["role"] == "SALES"
    audits = db.execute(
        select(AuditLog).where(AuditLog.action == "membership.create")
    ).scalars().all()
    assert len(audits) == 1


def test_viewer_cannot_add_member(client: TestClient, make_user, make_org, add_member, login):
    viewer = make_user("viewer@example.com")
    org = make_org("readco")
    add_member(viewer, org, Role.VIEWER)
    login("viewer@example.com")
    r = client.post(
        f"/api/v1/organizations/{org.id}/members",
        json={
            "email": "x@example.com",
            "full_name": "X",
            "password": "Password1!",
            "role": "VIEWER",
        },
    )
    assert r.status_code == 403


def test_admin_cannot_create_owner(
    client: TestClient, make_user, make_org, add_member, login
):
    admin = make_user("admin@example.com")
    org = make_org("admco")
    add_member(admin, org, Role.ADMIN)
    login("admin@example.com")
    r = client.post(
        f"/api/v1/organizations/{org.id}/members",
        json={
            "email": "new@example.com",
            "full_name": "New",
            "password": "Password1!",
            "role": "OWNER",
        },
    )
    assert r.status_code == 403


def test_role_change_recorded_in_audit(
    client: TestClient, make_user, make_org, add_member, login, db
):
    owner = make_user("o@example.com")
    other = make_user("other@example.com")
    org = make_org("chg")
    add_member(owner, org, Role.OWNER)
    m = add_member(other, org, Role.VIEWER)
    login("o@example.com")

    r = client.patch(
        f"/api/v1/organizations/{org.id}/members/{m.id}", json={"role": "MARKETER"}
    )
    assert r.status_code == 200
    assert r.json()["role"] == "MARKETER"
    audits = db.execute(
        select(AuditLog).where(AuditLog.action == "membership.role_change")
    ).scalars().all()
    assert len(audits) == 1
    assert audits[0].payload["from"] == "VIEWER"
    assert audits[0].payload["to"] == "MARKETER"


def test_cannot_demote_last_owner(
    client: TestClient, make_user, make_org, add_member, login, db
):
    owner = make_user("solo@example.com")
    org = make_org("solo")
    m = add_member(owner, org, Role.OWNER)
    login("solo@example.com")
    r = client.patch(
        f"/api/v1/organizations/{org.id}/members/{m.id}", json={"role": "ADMIN"}
    )
    assert r.status_code == 400
    fresh = db.execute(select(Membership).where(Membership.id == m.id)).scalar_one()
    assert fresh.role == Role.OWNER


def test_list_members_forbidden_across_orgs(
    client: TestClient, make_user, make_org, add_member, login
):
    outsider = make_user("out@example.com")
    make_org("mine2")
    other = make_org("other2")
    login("out@example.com")
    r = client.get(f"/api/v1/organizations/{other.id}/members")
    assert r.status_code == 403
    _ = outsider  # keep var referenced
