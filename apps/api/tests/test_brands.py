from __future__ import annotations

from sqlalchemy import select

from app.models.audit_log import AuditLog
from app.models.brand import Brand
from app.models.membership import Role


def test_marketer_can_create_brand(bootstrap, db):
    client, org_id, _ = bootstrap(Role.MARKETER, "marketer@example.com")
    r = client.post(
        "/api/v1/brands",
        json={"name": "Acme", "slug": "acme"},
    )
    assert r.status_code == 201
    body = r.json()
    assert body["public_id"].startswith("br_")
    assert body["is_active"] is True

    audits = db.execute(
        select(AuditLog).where(AuditLog.action == "brand.created")
    ).scalars().all()
    assert len(audits) == 1


def test_sales_cannot_create_brand(bootstrap):
    client, _, _ = bootstrap(Role.SALES, "sales@example.com")
    r = client.post("/api/v1/brands", json={"name": "X", "slug": "x-co"})
    assert r.status_code == 403


def test_analyst_can_list_but_not_create(bootstrap):
    client, _, _ = bootstrap(Role.ANALYST, "analyst@example.com")
    r = client.get("/api/v1/brands")
    assert r.status_code == 200
    assert r.json() == []
    r = client.post("/api/v1/brands", json={"name": "X", "slug": "x-co"})
    assert r.status_code == 403


def test_duplicate_slug_in_same_org_conflicts(bootstrap):
    client, _, _ = bootstrap(Role.OWNER, "dup@example.com")
    r1 = client.post("/api/v1/brands", json={"name": "A", "slug": "same"})
    assert r1.status_code == 201
    r2 = client.post("/api/v1/brands", json={"name": "B", "slug": "same"})
    assert r2.status_code == 409


def test_slug_reused_across_orgs(bootstrap, make_user, make_org, add_member, login):
    client_a, _, _ = bootstrap(Role.OWNER, "org-a@example.com")
    client_a.post("/api/v1/brands", json={"name": "A", "slug": "same-across"})

    u = make_user("org-b@example.com")
    o = make_org("other-org")
    add_member(u, o, Role.OWNER)
    client_b = login("org-b@example.com")
    client_b.headers["X-Organization-Id"] = str(o.id)
    r = client_b.post("/api/v1/brands", json={"name": "B", "slug": "same-across"})
    assert r.status_code == 201


def test_delete_is_soft(bootstrap, db):
    client, org_id, _ = bootstrap(Role.OWNER, "soft@example.com")
    r = client.post("/api/v1/brands", json={"name": "SD", "slug": "sd"})
    brand_id = r.json()["id"]
    r_del = client.delete(f"/api/v1/brands/{brand_id}")
    assert r_del.status_code == 204

    row = db.execute(select(Brand).where(Brand.id == brand_id)).scalar_one()
    assert row.is_active is False


def test_brand_isolated_across_orgs(bootstrap, make_user, make_org, add_member, login):
    client_a, _, _ = bootstrap(Role.OWNER, "iso-a@example.com")
    created = client_a.post("/api/v1/brands", json={"name": "A", "slug": "iso"}).json()

    u = make_user("iso-b@example.com")
    o = make_org("iso-org-b")
    add_member(u, o, Role.OWNER)
    client_b = login("iso-b@example.com")
    client_b.headers["X-Organization-Id"] = str(o.id)
    r = client_b.get(f"/api/v1/brands/{created['id']}")
    assert r.status_code == 404
