from __future__ import annotations

import uuid as _u

from sqlalchemy import select

from app.models.audit_log import AuditLog
from app.models.editorial import Review
from app.models.membership import Role


def _content(client):
    slug = f"brand-{_u.uuid4().hex[:6]}"
    brand_id = client.post(
        "/api/v1/brands", json={"name": slug, "slug": slug}
    ).json()["id"]
    return client.post(
        "/api/v1/content-items", json={"brand_id": brand_id, "title": "Rev"}
    ).json()["id"]


def test_create_review_by_marketer(bootstrap, db):
    client, _, _ = bootstrap(Role.MARKETER, "rev-mkt@example.com")
    cid = _content(client)
    r = client.post(
        f"/api/v1/content-items/{cid}/reviews",
        json={"review_type": "COPY", "decision": "NEEDS_REVISION", "score": 70},
    )
    assert r.status_code == 201, r.text
    assert r.json()["public_id"].startswith("rv_")


def test_review_score_range_validated(bootstrap):
    client, _, _ = bootstrap(Role.OWNER, "rev-score@example.com")
    cid = _content(client)
    r = client.post(
        f"/api/v1/content-items/{cid}/reviews",
        json={"decision": "APPROVED", "score": 150},
    )
    assert r.status_code == 422


def test_marketer_can_submit_but_not_approve(bootstrap):
    client, _, _ = bootstrap(Role.MARKETER, "mkt-approve@example.com")
    cid = _content(client)
    r_sub = client.post(
        f"/api/v1/content-items/{cid}/submit-review", json={"comment": "please review"}
    )
    assert r_sub.status_code == 201
    r_app = client.post(f"/api/v1/content-items/{cid}/approve", json={})
    assert r_app.status_code == 403


def test_admin_can_approve(bootstrap, db):
    client, _, _ = bootstrap(Role.ADMIN, "admin-approve@example.com")
    cid = _content(client)
    r = client.post(f"/api/v1/content-items/{cid}/approve", json={"score": 95})
    assert r.status_code == 201
    audits = db.execute(
        select(AuditLog).where(AuditLog.action == "content.approved")
    ).scalars().all()
    assert len(audits) == 1


def test_history_is_non_destructive(bootstrap, db):
    client, _, _ = bootstrap(Role.OWNER, "hist@example.com")
    cid = _content(client)
    client.post(
        f"/api/v1/content-items/{cid}/reviews",
        json={"decision": "NEEDS_REVISION", "comment": "v1"},
    )
    client.post(
        f"/api/v1/content-items/{cid}/reviews",
        json={"decision": "APPROVED", "comment": "v2"},
    )
    r = client.get(f"/api/v1/content-items/{cid}/reviews")
    assert r.status_code == 200
    assert len(r.json()) == 2

    reviews = db.execute(
        select(Review).where(Review.content_item_id == cid).order_by(Review.created_at)
    ).scalars().all()
    assert [rv.comment for rv in reviews] == ["v1", "v2"]


def test_review_isolated_across_orgs(bootstrap):
    client_a, _, _ = bootstrap(Role.OWNER, "rev-a@example.com")
    cid = _content(client_a)
    client_b, _, _ = bootstrap(Role.OWNER, "rev-b@example.com")
    r = client_b.get(f"/api/v1/content-items/{cid}/reviews")
    assert r.status_code == 404
