from __future__ import annotations

import uuid as _u

from sqlalchemy import select

from app.models.content import ContentItem
from app.models.editorial import Review
from app.models.enums import ReviewStatus
from app.models.membership import Role
from app.workers.auto_approval import run_once


def test_run_once_creates_review(bootstrap, db, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "enable_auto_approval", True)

    client, _, org = bootstrap(Role.OWNER, "auto-approval@example.com")
    slug = f"brand-{_u.uuid4().hex[:6]}"
    brand_id = client.post("/api/v1/brands", json={"name": slug, "slug": slug}).json()["id"]
    content_id = client.post(
        "/api/v1/content-items", json={"brand_id": brand_id, "title": "Prueba AI"}
    ).json()["id"]

    content = db.get(ContentItem, content_id)
    content.review_status = ReviewStatus.IN_REVIEW
    db.commit()

    counts = run_once()

    rv = db.execute(select(Review).where(Review.content_item_id == content.id)).scalar_one_or_none()
    assert rv is not None
    assert counts.get("processed", 0) >= 1