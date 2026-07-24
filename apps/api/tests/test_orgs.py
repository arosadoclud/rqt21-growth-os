from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.models.audit_log import AuditLog
from app.models.membership import Membership, Role


def test_create_org_makes_creator_owner(client: TestClient, make_user, login, db):
    make_user("owner@example.com")
    login("owner@example.com")
    r = client.post(
        "/api/v1/organizations",
        json={"name": "Acme Co", "slug": "acme-co"},
    )
    assert r.status_code == 201, r.text
    org_id = r.json()["id"]

    m = db.execute(select(Membership).where(Membership.organization_id == org_id)).scalar_one()
    assert m.role == Role.OWNER

    audits = db.execute(
        select(AuditLog).where(AuditLog.action == "organization.create")
    ).scalars().all()
    assert len(audits) == 1


def test_create_org_slug_conflict(client: TestClient, make_user, login):
    make_user("a@example.com")
    login("a@example.com")
    client.post("/api/v1/organizations", json={"name": "X", "slug": "dup"})
    r = client.post("/api/v1/organizations", json={"name": "Y", "slug": "dup"})
    assert r.status_code == 409


def test_list_orgs_only_returns_member_orgs(
    client: TestClient, make_user, make_org, add_member, login
):
    u = make_user("multi@example.com")
    mine = make_org("mine")
    add_member(u, mine, Role.ADMIN)
    make_org("theirs")  # user is not a member
    login("multi@example.com")
    r = client.get("/api/v1/organizations")
    assert r.status_code == 200
    slugs = {o["slug"] for o in r.json()}
    assert slugs == {"mine"}


def test_get_org_forbidden_for_non_member(
    client: TestClient, make_user, make_org, login
):
    make_user("z@example.com")
    other = make_org("other")
    login("z@example.com")
    r = client.get(f"/api/v1/organizations/{other.id}")
    assert r.status_code == 403
