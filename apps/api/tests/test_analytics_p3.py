from __future__ import annotations

import uuid as _u
from datetime import UTC, datetime, timedelta

from app.models.membership import Role


def _brand(client):
    slug = f"brand-{_u.uuid4().hex[:6]}"
    return client.post("/api/v1/brands", json={"name": slug, "slug": slug}).json()["id"]


def _mk_campaign(client, brand_id):
    slug = f"cmp-{_u.uuid4().hex[:6]}"
    return client.post(
        "/api/v1/campaigns",
        json={
            "brand_id": brand_id,
            "name": slug,
            "slug": slug,
            "objective": "SALES",
            "platform": "INSTAGRAM",
            "status": "ACTIVE",
        },
    ).json()


def _content(client, brand_id, campaign_id=None):
    return client.post(
        "/api/v1/content-items",
        json={"brand_id": brand_id, "campaign_id": campaign_id, "title": "T"},
    ).json()


def _link(client, brand_id, campaign_id=None, content_id=None):
    return client.post(
        "/api/v1/tracking-links",
        json={
            "brand_id": brand_id,
            "campaign_id": campaign_id,
            "content_id": content_id,
            "destination_url": "https://ex.com/x",
            "utm_source": "instagram",
        },
    ).json()


def test_editorial_summary(bootstrap):
    client, _, _ = bootstrap(Role.OWNER, "edsum@example.com")
    brand_id = _brand(client)
    content = _content(client, brand_id)
    # scheduled this week
    when = (datetime.now(UTC) + timedelta(hours=6)).isoformat()
    client.post(
        "/api/v1/editorial-calendar",
        json={
            "brand_id": brand_id,
            "content_item_id": content["id"],
            "platform": "INSTAGRAM",
            "status": "SCHEDULED",
            "scheduled_for": when,
        },
    )
    r = client.get("/api/v1/analytics/editorial/summary")
    assert r.status_code == 200
    assert r.json()["scheduled_this_week"] >= 1


def test_leads_summary_rates_zero_safe(bootstrap):
    client, _, _ = bootstrap(Role.OWNER, "lsum@example.com")
    r = client.get("/api/v1/analytics/leads/summary")
    assert r.status_code == 200
    body = r.json()
    assert body["total_leads"] == 0
    assert body["conversion_qualified_rate"] == 0.0
    assert body["conversion_won_rate"] == 0.0


def test_leads_summary_counts_states(bootstrap):
    client, _, _ = bootstrap(Role.OWNER, "lsum2@example.com")
    client.post("/api/v1/leads", json={"first_name": "A", "email": "a@ex.com"})
    r_new = client.post("/api/v1/leads", json={"first_name": "B", "email": "b@ex.com"})
    client.post(
        f"/api/v1/leads/{r_new.json()['id']}/status", json={"status": "QUALIFIED"}
    )
    r_won = client.post("/api/v1/leads", json={"first_name": "C", "email": "c@ex.com"})
    client.post(f"/api/v1/leads/{r_won.json()['id']}/status", json={"status": "WON"})

    r = client.get("/api/v1/analytics/leads/summary")
    b = r.json()
    assert b["total_leads"] == 3
    assert b["new_leads"] == 1
    assert b["qualified_leads"] == 1
    assert b["won_leads"] == 1
    assert 30 <= b["conversion_qualified_rate"] <= 40
    assert 30 <= b["conversion_won_rate"] <= 40


def test_campaign_funnel(bootstrap, raw_client):
    client, _, _ = bootstrap(Role.OWNER, "fnl@example.com")
    brand_id = _brand(client)
    camp = _mk_campaign(client, brand_id)
    link = _link(client, brand_id, campaign_id=camp["id"])
    for i in range(4):
        raw_client.get(
            f"/r/{link['short_code']}",
            headers={"x-forwarded-for": f"10.0.0.{i}"},
            follow_redirects=False,
        )
    r_lead = client.post(
        "/api/v1/leads",
        json={
            "first_name": "L",
            "email": "l@ex.com",
            "campaign_id": camp["id"],
            "tracking_link_id": link["id"],
        },
    )
    client.post(
        f"/api/v1/leads/{r_lead.json()['id']}/status", json={"status": "WON"}
    )

    r = client.get(f"/api/v1/analytics/campaigns/{camp['id']}/funnel")
    assert r.status_code == 200
    body = r.json()
    assert body["clicks"] == 4
    assert body["leads"] == 1
    assert body["won_leads"] == 1
    assert body["click_to_lead_rate"] == 25.0
    assert body["lead_to_won_rate"] == 100.0


def test_content_funnel_zero_clicks(bootstrap):
    client, _, _ = bootstrap(Role.OWNER, "cfnl@example.com")
    brand_id = _brand(client)
    content = _content(client, brand_id)
    r = client.get(f"/api/v1/analytics/content/{content['id']}/funnel")
    assert r.status_code == 200
    b = r.json()
    assert b["clicks"] == 0
    assert b["click_to_lead_rate"] == 0.0
    assert b["lead_to_won_rate"] == 0.0
