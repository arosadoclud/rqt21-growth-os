from __future__ import annotations

import uuid as _u
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.models.audit_log import AuditLog
from app.models.editorial import EditorialCalendarItem
from app.models.enums import EditorialStatus
from app.models.membership import Role


def _brand_content(client):
    slug = f"brand-{_u.uuid4().hex[:6]}"
    brand_id = client.post(
        "/api/v1/brands", json={"name": slug, "slug": slug}
    ).json()["id"]
    r = client.post(
        "/api/v1/content-items",
        json={"brand_id": brand_id, "title": "T"},
    )
    return brand_id, r.json()["id"]


def _make_item(client, extra=None):
    brand_id, content_id = _brand_content(client)
    body = {
        "content_item_id": content_id,
        "brand_id": brand_id,
        "platform": "INSTAGRAM",
        "content_format": "REEL",
    }
    body.update(extra or {})
    return client.post("/api/v1/editorial-calendar", json=body)


def test_marketer_can_create_item(bootstrap, db):
    client, _, _ = bootstrap(Role.MARKETER, "edit-mkt@example.com")
    r = _make_item(client)
    assert r.status_code == 201, r.text
    assert r.json()["public_id"].startswith("eci_")

    audits = db.execute(
        select(AuditLog).where(AuditLog.action == "editorial_item.created")
    ).scalars().all()
    assert len(audits) == 1


def test_sales_cannot_create_item(bootstrap):
    client, _, _ = bootstrap(Role.SALES, "edit-sales@example.com")
    # SALES can't create brands/content, so post directly with fake UUIDs — the
    # RBAC gate must fire before FK validation.
    fake = "00000000-0000-0000-0000-000000000000"
    r = client.post(
        "/api/v1/editorial-calendar",
        json={"content_item_id": fake, "brand_id": fake},
    )
    assert r.status_code == 403


def test_scheduled_requires_scheduled_for(bootstrap):
    client, _, _ = bootstrap(Role.OWNER, "sched@example.com")
    r = _make_item(client, {"status": "SCHEDULED"})
    assert r.status_code == 400


def test_schedule_endpoint_sets_status(bootstrap):
    client, _, _ = bootstrap(Role.OWNER, "sched2@example.com")
    r = _make_item(client)
    item = r.json()
    when = (datetime.now(UTC) + timedelta(days=2)).isoformat()
    resp = client.post(
        f"/api/v1/editorial-calendar/{item['id']}/schedule",
        json={"scheduled_for": when, "timezone": "UTC"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "SCHEDULED"
    assert resp.json()["scheduled_for"] is not None


def test_mark_published_sets_url(bootstrap, db):
    client, _, _ = bootstrap(Role.OWNER, "pub@example.com")
    item = _make_item(client).json()
    resp = client.post(
        f"/api/v1/editorial-calendar/{item['id']}/mark-published",
        json={"publication_url": "https://instagram.com/p/x"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "PUBLISHED"
    assert resp.json()["publication_url"].startswith("https://instagram.com")


def test_delete_published_archives(bootstrap, db):
    client, _, _ = bootstrap(Role.OWNER, "arch@example.com")
    item = _make_item(client).json()
    client.post(
        f"/api/v1/editorial-calendar/{item['id']}/mark-published",
        json={"publication_url": "https://x.com/p"},
    )
    r = client.delete(f"/api/v1/editorial-calendar/{item['id']}")
    assert r.status_code == 204
    row = db.execute(
        select(EditorialCalendarItem).where(EditorialCalendarItem.id == item["id"])
    ).scalar_one()
    assert row.status == EditorialStatus.ARCHIVED


def test_delete_non_published_cancels(bootstrap, db):
    client, _, _ = bootstrap(Role.OWNER, "canc@example.com")
    item = _make_item(client).json()
    r = client.delete(f"/api/v1/editorial-calendar/{item['id']}")
    assert r.status_code == 204
    row = db.execute(
        select(EditorialCalendarItem).where(EditorialCalendarItem.id == item["id"])
    ).scalar_one()
    assert row.status == EditorialStatus.CANCELLED


def test_range_filter(bootstrap):
    client, _, _ = bootstrap(Role.OWNER, "range@example.com")
    item = _make_item(client).json()
    when = (datetime.now(UTC) + timedelta(days=1)).isoformat()
    client.post(
        f"/api/v1/editorial-calendar/{item['id']}/schedule",
        json={"scheduled_for": when, "timezone": "UTC"},
    )
    r = client.get(
        "/api/v1/editorial-calendar/range",
        params={
            "start": datetime.now(UTC).isoformat(),
            "end": (datetime.now(UTC) + timedelta(days=3)).isoformat(),
        },
    )
    assert r.status_code == 200
    assert len(r.json()) == 1


def test_editorial_isolated_across_orgs(bootstrap):
    client_a, _, _ = bootstrap(Role.OWNER, "iso-e1@example.com")
    item = _make_item(client_a).json()
    client_b, _, _ = bootstrap(Role.OWNER, "iso-e2@example.com")
    r = client_b.get(f"/api/v1/editorial-calendar/{item['id']}")
    assert r.status_code == 404
