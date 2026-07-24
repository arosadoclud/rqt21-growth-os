from __future__ import annotations

import uuid as _u
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.models.click import ClickEvent
from app.models.membership import Role
from app.models.tracking import TrackingLink


def _brand(client, slug: str | None = None) -> str:
    slug = slug or f"brand-{_u.uuid4().hex[:6]}"
    return client.post("/api/v1/brands", json={"name": slug, "slug": slug}).json()["id"]


def _create_link(client, brand_id: str | None = None, **extra) -> dict:
    if brand_id is None:
        brand_id = _brand(client)
    payload = {
        "brand_id": brand_id,
        "destination_url": "https://checkout.example.com/product",
        "utm_source": "instagram",
        "utm_medium": "social",
        "utm_campaign": "launch",
    }
    payload.update(extra)
    r = client.post("/api/v1/tracking-links", json=payload)
    assert r.status_code == 201, r.text
    return r.json()


def test_create_link_generates_short_code_and_final_url(bootstrap):
    client, _, _ = bootstrap(Role.OWNER, "tl@example.com")
    link = _create_link(client)
    assert link["short_code"]
    assert len(link["short_code"]) == 8
    assert link["short_url"].endswith(f"/r/{link['short_code']}")
    assert "utm_source=instagram" in link["final_url"]
    assert link["public_id"].startswith("tl_")


def test_regenerate_code_changes_short_code(bootstrap, db):
    client, _, _ = bootstrap(Role.OWNER, "regen@example.com")
    link = _create_link(client)
    old = link["short_code"]

    r = client.post(f"/api/v1/tracking-links/{link['id']}/regenerate-code")
    assert r.status_code == 200
    new = r.json()["short_code"]
    assert new != old

    row = db.execute(
        select(TrackingLink).where(TrackingLink.id == link["id"])
    ).scalar_one()
    assert row.short_code == new


def test_short_codes_are_unique(bootstrap):
    client, _, _ = bootstrap(Role.OWNER, "uniq@example.com")
    brand_id = _brand(client)
    codes = {_create_link(client, brand_id=brand_id)["short_code"] for _ in range(10)}
    assert len(codes) == 10


def test_redirect_active_link_records_click(bootstrap, raw_client, db):
    client, org_id, _ = bootstrap(Role.OWNER, "red@example.com")
    link = _create_link(client)
    code = link["short_code"]

    r = raw_client.get(
        f"/r/{code}?extra=payload",
        headers={
            "user-agent": "Mozilla/5.0 (Linux; Android 12) AppleWebKit/537.36 Chrome/118",
            "referer": "https://instagram.com/",
        },
        follow_redirects=False,
    )
    assert r.status_code == 307
    assert "utm_source=instagram" in r.headers["location"]
    assert r.headers["location"].startswith("https://checkout.example.com/")

    events = db.execute(select(ClickEvent).where(ClickEvent.organization_id == org_id)).scalars().all()
    assert len(events) == 1
    e = events[0]
    assert e.tracking_link_id == link["id"] or str(e.tracking_link_id) == link["id"]
    assert e.referrer == "https://instagram.com/"
    assert e.device_type == "mobile"
    assert e.browser == "chrome"
    assert e.os == "android"
    # IP is anonymized: hash only, no dotted quad or raw string.
    assert e.ip_hash is not None
    assert len(e.ip_hash) == 32
    assert "." not in e.ip_hash
    # Only extra params are kept, utm_* are stripped from query_params.
    assert e.query_params == {"extra": "payload"}


def test_redirect_unknown_short_code_404(raw_client):
    r = raw_client.get("/r/nonexistent-code", follow_redirects=False)
    assert r.status_code == 404


def test_redirect_inactive_link_410(bootstrap, raw_client, db):
    client, _, _ = bootstrap(Role.OWNER, "inact@example.com")
    link = _create_link(client)
    r_upd = client.patch(
        f"/api/v1/tracking-links/{link['id']}", json={"is_active": False}
    )
    assert r_upd.status_code == 200
    r = raw_client.get(f"/r/{link['short_code']}", follow_redirects=False)
    assert r.status_code == 410


def test_redirect_expired_link_410(bootstrap, raw_client, db):
    client, _, _ = bootstrap(Role.OWNER, "exp@example.com")
    link = _create_link(client)
    past = (datetime.now(UTC) - timedelta(days=1)).isoformat()
    r_upd = client.patch(
        f"/api/v1/tracking-links/{link['id']}", json={"expires_at": past}
    )
    assert r_upd.status_code == 200
    r = raw_client.get(f"/r/{link['short_code']}", follow_redirects=False)
    assert r.status_code == 410


def test_link_isolated_across_orgs(bootstrap):
    client_a, _, _ = bootstrap(Role.OWNER, "iso1@example.com")
    link = _create_link(client_a)

    client_b, _, _ = bootstrap(Role.OWNER, "iso2@example.com")
    r = client_b.get(f"/api/v1/tracking-links/{link['id']}")
    assert r.status_code == 404


def test_sales_cannot_create_link(bootstrap):
    client, _, _ = bootstrap(Role.SALES, "sales-link@example.com")
    # SALES can't even create a brand, so plant one manually.
    # We use a raw insert path via a peer OWNER context.
    other, _, _ = bootstrap(Role.OWNER, "sales-peer@example.com")
    # We can't share brands across orgs, so just check the 403 gate for SALES.
    r = client.post(
        "/api/v1/tracking-links",
        json={
            "brand_id": "00000000-0000-0000-0000-000000000000",
            "destination_url": "https://example.com",
        },
    )
    assert r.status_code == 403
    _ = other
