from __future__ import annotations

import uuid as _u

from app.models.membership import Role


def _make_brand(client) -> str:
    slug = f"brand-{_u.uuid4().hex[:6]}"
    r = client.post("/api/v1/brands", json={"name": slug, "slug": slug})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def test_product_crud(bootstrap):
    client, _, _ = bootstrap(Role.OWNER, "p-crud@example.com")
    brand_id = _make_brand(client)
    r = client.post(
        "/api/v1/products",
        json={
            "brand_id": brand_id,
            "name": "Premium",
            "slug": "premium",
            "price": "49.90",
            "currency": "usd",
            "status": "ACTIVE",
        },
    )
    assert r.status_code == 201
    pid = r.json()["id"]
    assert r.json()["currency"] == "USD"
    assert r.json()["public_id"].startswith("pr_")

    r_upd = client.patch(f"/api/v1/products/{pid}", json={"status": "ARCHIVED"})
    assert r_upd.status_code == 200
    assert r_upd.json()["status"] == "ARCHIVED"

    r_list = client.get("/api/v1/products?status=ARCHIVED")
    assert len(r_list.json()) == 1


def test_product_rejects_foreign_brand(bootstrap, make_user, make_org, add_member, login):
    client_a, _, _ = bootstrap(Role.OWNER, "pa@example.com")
    other_client, _, _ = bootstrap(Role.OWNER, "pb@example.com")
    foreign_brand = other_client.post(
        "/api/v1/brands", json={"name": "F", "slug": "foreign"}
    ).json()["id"]

    r = client_a.post(
        "/api/v1/products",
        json={"brand_id": foreign_brand, "name": "X", "slug": "x-p"},
    )
    assert r.status_code == 400
    assert "brand" in r.json()["detail"]


def test_campaign_crud(bootstrap):
    client, _, _ = bootstrap(Role.MARKETER, "c-crud@example.com")
    brand_id = _make_brand(client)
    r = client.post(
        "/api/v1/campaigns",
        json={
            "brand_id": brand_id,
            "name": "IG Awareness",
            "slug": "ig-awareness",
            "objective": "AWARENESS",
            "platform": "INSTAGRAM",
            "status": "ACTIVE",
        },
    )
    assert r.status_code == 201
    assert r.json()["public_id"].startswith("cm_")

    cid = r.json()["id"]
    r_upd = client.patch(f"/api/v1/campaigns/{cid}", json={"status": "PAUSED"})
    assert r_upd.status_code == 200
    assert r_upd.json()["status"] == "PAUSED"


def test_content_crud(bootstrap):
    client, _, _ = bootstrap(Role.OWNER, "ct@example.com")
    brand_id = _make_brand(client)
    r = client.post(
        "/api/v1/content-items",
        json={
            "brand_id": brand_id,
            "title": "Hello world reel",
            "content_type": "REEL",
            "platform": "INSTAGRAM",
        },
    )
    assert r.status_code == 201
    body = r.json()
    assert body["public_id"].startswith("ct_")
    assert body["title"] == "Hello world reel"


def test_content_import_is_idempotent(bootstrap, db):
    from app.models.content import ContentItem

    client, org_id, _ = bootstrap(Role.OWNER, "imp@example.com")
    brand_id = _make_brand(client)
    payload = {
        "brand_id": brand_id,
        "external_id": "reel-42",
        "source_system": "KINGDOM_STUDIO",
        "title": "Original title",
        "content_type": "REEL",
        "platform": "INSTAGRAM",
        "status": "SCHEDULED",
    }
    r1 = client.post("/api/v1/content-items/import", json=payload)
    assert r1.status_code == 200
    id1 = r1.json()["id"]

    payload["title"] = "Refreshed title"
    payload["status"] = "PUBLISHED"
    r2 = client.post("/api/v1/content-items/import", json=payload)
    assert r2.status_code == 200
    id2 = r2.json()["id"]

    assert id1 == id2, "import must be idempotent by (org, source_system, external_id)"
    from sqlalchemy import select
    rows = db.execute(
        select(ContentItem).where(ContentItem.organization_id == org_id)
    ).scalars().all()
    assert len(rows) == 1
    assert rows[0].title == "Refreshed title"
    assert rows[0].status.value == "PUBLISHED"
