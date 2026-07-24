from __future__ import annotations

import uuid as _u

from app.models.membership import Role


def _brand(client) -> str:
    slug = f"brand-{_u.uuid4().hex[:6]}"
    return client.post("/api/v1/brands", json={"name": slug, "slug": slug}).json()["id"]


def _mk(client, brand_id, name="C", slug=None, **extra):
    slug = slug or f"camp-{_u.uuid4().hex[:6]}"
    p = {
        "brand_id": brand_id,
        "name": name,
        "slug": slug,
        "platform": "INSTAGRAM",
        "objective": "SALES",
        "status": "ACTIVE",
    }
    p.update(extra)
    return client.post("/api/v1/campaigns", json=p).json()


def _content(client, brand_id, campaign_id=None, title="Reel", ext="x"):
    r = client.post(
        "/api/v1/content-items",
        json={
            "brand_id": brand_id,
            "campaign_id": campaign_id,
            "title": title,
            "external_id": ext,
        },
    )
    return r.json()


def _link(client, brand_id, campaign_id=None, content_id=None):
    r = client.post(
        "/api/v1/tracking-links",
        json={
            "brand_id": brand_id,
            "campaign_id": campaign_id,
            "content_id": content_id,
            "destination_url": "https://example.com/x",
            "utm_source": "ig",
        },
    )
    return r.json()


def test_campaign_summary_counts_clicks(bootstrap, raw_client):
    client, _, _ = bootstrap(Role.OWNER, "an1@example.com")
    brand_id = _brand(client)
    camp = _mk(client, brand_id)
    link = _link(client, brand_id, campaign_id=camp["id"])

    for i in range(3):
        raw_client.get(
            f"/r/{link['short_code']}",
            headers={"x-forwarded-for": f"10.0.0.{i}"},
            follow_redirects=False,
        )

    r = client.get(f"/api/v1/analytics/campaigns/{camp['id']}/summary")
    assert r.status_code == 200
    body = r.json()
    assert body["total_clicks"] == 3
    assert body["unique_visitors"] == 3
    assert body["active_links"] == 1


def test_content_summary_counts_clicks(bootstrap, raw_client):
    client, _, _ = bootstrap(Role.OWNER, "an2@example.com")
    brand_id = _brand(client)
    ct = _content(client, brand_id, title="Reel A", ext="a")
    link = _link(client, brand_id, content_id=ct["id"])
    raw_client.get(f"/r/{link['short_code']}", follow_redirects=False)
    raw_client.get(f"/r/{link['short_code']}", follow_redirects=False)

    r = client.get(f"/api/v1/analytics/content/{ct['id']}/summary")
    assert r.status_code == 200
    body = r.json()
    assert body["total_clicks"] == 2


def test_link_clicks_list(bootstrap, raw_client):
    client, _, _ = bootstrap(Role.OWNER, "an3@example.com")
    brand_id = _brand(client)
    link = _link(client, brand_id)
    for _ in range(4):
        raw_client.get(f"/r/{link['short_code']}", follow_redirects=False)

    r = client.get(f"/api/v1/analytics/tracking-links/{link['id']}/clicks")
    assert r.status_code == 200
    assert len(r.json()) == 4


def test_dashboard_summary(bootstrap, raw_client):
    client, _, _ = bootstrap(Role.OWNER, "an4@example.com")
    brand_id = _brand(client)
    c1 = _mk(client, brand_id, name="C1", slug="c1")
    c2 = _mk(client, brand_id, name="C2", slug="c2")
    ct = _content(client, brand_id, campaign_id=c1["id"], title="Reel", ext="reel1")
    link1 = _link(client, brand_id, campaign_id=c1["id"], content_id=ct["id"])
    link2 = _link(client, brand_id, campaign_id=c2["id"])
    for _ in range(5):
        raw_client.get(f"/r/{link1['short_code']}", follow_redirects=False)
    raw_client.get(f"/r/{link2['short_code']}", follow_redirects=False)

    r = client.get("/api/v1/analytics/dashboard/summary")
    assert r.status_code == 200
    body = r.json()
    assert body["campaigns_total"] == 2
    assert body["contents_total"] == 1
    assert body["active_links"] == 2
    assert body["clicks_total"] == 6
    assert body["top_campaigns"][0]["campaign_id"] == c1["id"]
    assert body["top_campaigns"][0]["total_clicks"] == 5
