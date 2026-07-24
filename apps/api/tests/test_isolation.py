from __future__ import annotations

from fastapi.testclient import TestClient

from app.models.membership import Role


def test_organizations_are_isolated(
    client: TestClient, make_user, make_org, add_member, login
):
    alice = make_user("alice@iso.com")
    bob = make_user("bob@iso.com")
    org_a = make_org("alpha")
    org_b = make_org("beta")
    add_member(alice, org_a, Role.OWNER)
    add_member(bob, org_b, Role.OWNER)

    login("alice@iso.com")

    # Alice can see her org
    r = client.get(f"/api/v1/organizations/{org_a.id}")
    assert r.status_code == 200

    # Alice cannot see Bob's org
    r = client.get(f"/api/v1/organizations/{org_b.id}")
    assert r.status_code == 403

    # Alice cannot list Bob's members
    r = client.get(f"/api/v1/organizations/{org_b.id}/members")
    assert r.status_code == 403

    # Alice cannot add a member to Bob's org even if she claims OWNER role
    r = client.post(
        f"/api/v1/organizations/{org_b.id}/members",
        json={
            "email": "sneak@iso.com",
            "full_name": "Sneak",
            "password": "Password1!",
            "role": "ADMIN",
        },
    )
    assert r.status_code == 403


def test_org_id_from_header_requires_membership(
    client: TestClient, make_user, make_org, add_member, login
):
    """Endpoints wired to current_org must reject foreign X-Organization-Id."""
    from fastapi import Depends

    from app.deps import current_org, get_session
    from app.main import app

    @app.get("/api/v1/_test/org-guard")
    def _guarded(org=Depends(current_org)):
        return {"ok": True, "org_id": str(org.organization_id)}

    alice = make_user("iso1@iso.com")
    org_a = make_org("gamma")
    org_b = make_org("delta")
    add_member(alice, org_a, Role.OWNER)
    login("iso1@iso.com")

    r = client.get("/api/v1/_test/org-guard", headers={"X-Organization-Id": str(org_a.id)})
    assert r.status_code == 200

    r = client.get("/api/v1/_test/org-guard", headers={"X-Organization-Id": str(org_b.id)})
    assert r.status_code == 403

    r = client.get("/api/v1/_test/org-guard", headers={"X-Organization-Id": "not-a-uuid"})
    assert r.status_code == 400

    r = client.get("/api/v1/_test/org-guard")
    assert r.status_code == 400
    _ = get_session  # keep imported symbol
