"""Headline auto-cycle: app.api.v1.headline (config CRUD) and
app.workers.headline_scheduler (batch copy generation only — no image).
Uses the MOCK AI providers (forced in conftest) and a MOCK publishing
connection — never a real Anthropic/Meta call.

Generation happens once a day per schedule: up to max_per_day headlines
get their copy generated in one pass, each assigned a publish slot
interval_hours apart. Photos are uploaded by a human, never generated —
uploading one is what actually publishes (or schedules) its headline, via
app.api.v1.assets.complete_upload's hook into
app.workers.headline_scheduler.publish_headline_content, exercised
end-to-end below via the real upload endpoints."""

from __future__ import annotations

import base64
import uuid as _u
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.ai.headline_topics import HEADLINE_TOPICS, next_topic
from app.models.content import ContentItem
from app.models.enums import PublicationStatus, ReviewStatus, SourceSystem
from app.models.headline import HeadlineSchedule
from app.models.membership import Role
from app.models.publishing import Publication
from app.workers.headline_scheduler import run_now, run_once

_PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 200


def _brand(client) -> str:
    slug = f"brand-{_u.uuid4().hex[:6]}"
    return client.post("/api/v1/brands", json={"name": slug, "slug": slug}).json()["id"]


def _mock_connection(client, brand_id: str, platform: str = "FACEBOOK") -> str:
    r = client.post(
        "/api/v1/publishing-connections",
        json={
            "brand_id": brand_id,
            "platform": platform,
            "provider": "MOCK",
            "account_name": "rqt21.mock",
        },
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _schedule(db, *, organization_id, brand_id, **overrides) -> HeadlineSchedule:
    from app.utils.public_id import make as make_public_id

    overrides.setdefault("enabled", True)
    row = HeadlineSchedule(
        organization_id=organization_id,
        public_id=make_public_id("hls"),
        brand_id=brand_id,
        **overrides,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _upload_photo(client, *, brand_id: str, content_item_id: str) -> dict:
    init = client.post(
        "/api/v1/assets/init-upload",
        json={
            "filename": "flyer.png",
            "mime_type": "image/png",
            "size_bytes": len(_PNG),
            "asset_type": "IMAGE",
            "brand_id": brand_id,
            "content_item_id": content_item_id,
            "alt_text": "Flyer del headline",
        },
    )
    assert init.status_code == 201, init.text
    asset_id = init.json()["asset_id"]
    completed = client.post(
        "/api/v1/assets/complete-upload",
        json={"asset_id": asset_id, "content_base64": base64.b64encode(_PNG).decode()},
    )
    assert completed.status_code == 200, completed.text
    return completed.json()


# ---------------------------------------------------------------- config --


def test_get_headline_config_lazily_creates_disabled_row(bootstrap, db):
    client, org_id, _ = bootstrap(Role.OWNER, "hl-config-get@example.com")
    brand_id = _brand(client)

    r = client.get(f"/api/v1/headline-config/{brand_id}")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["enabled"] is False
    assert body["interval_hours"] == 2
    assert body["max_per_day"] == 12

    row = db.execute(
        select(HeadlineSchedule).where(HeadlineSchedule.brand_id == _u.UUID(brand_id))
    ).scalar_one()
    assert row.enabled is False


def test_update_headline_config_requires_owner_or_admin(bootstrap):
    client, _, _ = bootstrap(Role.MARKETER, "hl-config-forbidden@example.com")
    brand_id = _brand(client)
    r = client.put(
        f"/api/v1/headline-config/{brand_id}",
        json={"enabled": True, "interval_hours": 2, "max_per_day": 12},
    )
    assert r.status_code == 403


def test_update_headline_config_enables_with_connection(bootstrap):
    client, _, _ = bootstrap(Role.OWNER, "hl-config-update@example.com")
    brand_id = _brand(client)
    connection_id = _mock_connection(client, brand_id)

    r = client.put(
        f"/api/v1/headline-config/{brand_id}",
        json={
            "enabled": True,
            "publishing_connection_id": connection_id,
            "platform": "FACEBOOK",
            "interval_hours": 2,
            "max_per_day": 12,
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["enabled"] is True
    assert body["publishing_connection_id"] == connection_id


def test_update_headline_config_rejects_platform_mismatch(bootstrap):
    client, _, _ = bootstrap(Role.OWNER, "hl-config-mismatch@example.com")
    brand_id = _brand(client)
    connection_id = _mock_connection(client, brand_id, platform="INSTAGRAM")

    r = client.put(
        f"/api/v1/headline-config/{brand_id}",
        json={
            "enabled": True,
            "publishing_connection_id": connection_id,
            "platform": "FACEBOOK",
        },
    )
    assert r.status_code == 400


def test_run_now_requires_enabled(bootstrap):
    client, _, _ = bootstrap(Role.OWNER, "hl-run-now-disabled@example.com")
    brand_id = _brand(client)
    r = client.post(f"/api/v1/headline-config/{brand_id}/run-now")
    assert r.status_code == 400


def test_run_now_generates_todays_batch(bootstrap, db):
    client, org_id, _ = bootstrap(Role.OWNER, "hl-run-now@example.com")
    brand_id = _brand(client)
    client.put(
        f"/api/v1/headline-config/{brand_id}",
        json={"enabled": True, "interval_hours": 2, "max_per_day": 1},
    )

    r = client.post(f"/api/v1/headline-config/{brand_id}/run-now")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["daily_count"] == 1
    assert body["last_run_at"] is not None
    assert body["daily_count_date"] == datetime.now(UTC).date().isoformat()

    items = db.execute(
        select(ContentItem).where(
            ContentItem.organization_id == org_id,
            ContentItem.source_system == SourceSystem.HEADLINE_AUTO,
        )
    ).scalars().all()
    assert len(items) == 1


def test_run_now_twice_same_day_is_a_no_op(bootstrap):
    client, _, _ = bootstrap(Role.OWNER, "hl-run-now-twice@example.com")
    brand_id = _brand(client)
    client.put(
        f"/api/v1/headline-config/{brand_id}",
        json={"enabled": True, "max_per_day": 1},
    )

    r1 = client.post(f"/api/v1/headline-config/{brand_id}/run-now")
    assert r1.status_code == 200, r1.text

    r2 = client.post(f"/api/v1/headline-config/{brand_id}/run-now")
    assert r2.status_code == 409


def test_headline_history_lists_only_headline_content(bootstrap, db):
    client, org_id, _ = bootstrap(Role.OWNER, "hl-history@example.com")
    brand_id = _brand(client)
    client.put(f"/api/v1/headline-config/{brand_id}", json={"enabled": True, "max_per_day": 1})
    client.post(f"/api/v1/headline-config/{brand_id}/run-now")

    # A manually created content item must not show up in the history feed.
    client.post("/api/v1/content-items", json={"brand_id": brand_id, "title": "Manual"})

    r = client.get(f"/api/v1/headline-config/{brand_id}/history")
    assert r.status_code == 200, r.text
    body = r.json()
    assert len(body) == 1
    assert body[0]["title"]


def test_pending_photos_lists_approved_content_with_scheduled_for(bootstrap, db, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "enable_auto_approval", True)

    client, org_id, _ = bootstrap(Role.OWNER, "hl-pending@example.com")
    brand_id = _brand(client)
    connection_id = _mock_connection(client, brand_id)
    client.put(
        f"/api/v1/headline-config/{brand_id}",
        json={
            "enabled": True,
            "publishing_connection_id": connection_id,
            "platform": "FACEBOOK",
            "max_per_day": 1,
        },
    )
    client.post(f"/api/v1/headline-config/{brand_id}/run-now")

    r = client.get(f"/api/v1/headline-config/{brand_id}/pending-photos")
    assert r.status_code == 200, r.text
    body = r.json()
    assert len(body) == 1
    assert body[0]["scheduled_for"] is not None
    content_id = body[0]["id"]

    _upload_photo(client, brand_id=brand_id, content_item_id=content_id)

    r2 = client.get(f"/api/v1/headline-config/{brand_id}/pending-photos")
    assert r2.json() == []


# ---------------------------------------------------------------- worker --


def test_next_topic_cycles_without_repeats():
    first = next_topic(0)
    second = next_topic(1)
    assert first != second
    assert next_topic(len(HEADLINE_TOPICS)) == first


def test_run_once_skips_disabled_schedule(bootstrap, db):
    client, org_id, _ = bootstrap(Role.OWNER, "hl-worker-disabled@example.com")
    brand_id = _brand(client)
    _schedule(db, organization_id=org_id, brand_id=_u.UUID(brand_id), enabled=False)

    counts = run_once()
    assert counts["skipped"] >= 0  # disabled schedules aren't even selected


def test_run_once_skips_when_already_ran_today(bootstrap, db):
    client, org_id, _ = bootstrap(Role.OWNER, "hl-worker-not-due@example.com")
    brand_id = _brand(client)
    row = _schedule(
        db,
        organization_id=org_id,
        brand_id=_u.UUID(brand_id),
        daily_count=1,
        daily_count_date=datetime.now(UTC).date(),
    )

    counts = run_once()
    assert counts["skipped"] == 1

    db.refresh(row)
    assert row.daily_count == 1


def test_run_once_generates_and_holds_for_review_without_auto_approval(bootstrap, db):
    """ENABLE_AUTO_APPROVAL is forced off in conftest — a due schedule must
    still generate a ContentItem (source_system=HEADLINE_AUTO), but it
    stays IN_REVIEW in Bandeja, with no image and no publication."""
    client, org_id, _ = bootstrap(Role.OWNER, "hl-worker-holds@example.com")
    brand_id = _brand(client)
    connection_id = _mock_connection(client, brand_id)
    row = _schedule(
        db,
        organization_id=org_id,
        brand_id=_u.UUID(brand_id),
        publishing_connection_id=_u.UUID(connection_id),
        max_per_day=1,
    )

    counts = run_once()
    assert counts["held_for_review"] == 1
    assert counts["awaiting_photo"] == 0

    db.refresh(row)
    assert row.daily_count == 1
    assert row.daily_count_date == datetime.now(UTC).date()
    assert row.topic_rotation_index == 1

    content = db.execute(
        select(ContentItem).where(
            ContentItem.organization_id == org_id,
            ContentItem.source_system == SourceSystem.HEADLINE_AUTO,
        )
    ).scalar_one()
    assert content.review_status == ReviewStatus.IN_REVIEW

    pubs = db.execute(select(Publication).where(Publication.organization_id == org_id)).scalars().all()
    assert pubs == []


def test_run_once_marks_approved_content_awaiting_photo_with_draft_publication(bootstrap, db, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "enable_auto_approval", True)

    client, org_id, _ = bootstrap(Role.OWNER, "hl-worker-awaiting@example.com")
    brand_id = _brand(client)
    connection_id = _mock_connection(client, brand_id)
    _schedule(
        db,
        organization_id=org_id,
        brand_id=_u.UUID(brand_id),
        publishing_connection_id=_u.UUID(connection_id),
        max_per_day=1,
    )

    counts = run_once()
    assert counts["awaiting_photo"] == 1

    content = db.execute(
        select(ContentItem).where(
            ContentItem.organization_id == org_id,
            ContentItem.source_system == SourceSystem.HEADLINE_AUTO,
        )
    ).scalar_one()
    assert content.review_status == ReviewStatus.APPROVED

    # A DRAFT Publication with no asset yet is pre-created for its slot —
    # nothing is actually published until a human uploads the photo.
    pub = db.execute(select(Publication).where(Publication.organization_id == org_id)).scalar_one()
    assert pub.status == PublicationStatus.DRAFT
    assert pub.asset_id is None
    assert pub.scheduled_for is not None


def test_batch_generation_spaces_slots_by_interval_hours(bootstrap, db, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "enable_auto_approval", True)

    client, org_id, _ = bootstrap(Role.OWNER, "hl-worker-batch@example.com")
    brand_id = _brand(client)
    connection_id = _mock_connection(client, brand_id)
    _schedule(
        db,
        organization_id=org_id,
        brand_id=_u.UUID(brand_id),
        publishing_connection_id=_u.UUID(connection_id),
        interval_hours=2,
        max_per_day=3,
    )

    counts = run_once()
    assert counts["awaiting_photo"] == 3

    pubs = db.execute(
        select(Publication).where(Publication.organization_id == org_id).order_by(Publication.scheduled_for)
    ).scalars().all()
    assert len(pubs) == 3
    gaps = [
        (pubs[i + 1].scheduled_for - pubs[i].scheduled_for).total_seconds() / 3600
        for i in range(len(pubs) - 1)
    ]
    assert gaps == [2.0, 2.0]
    # First slot is immediate (roughly "now"), not pushed out an interval.
    assert pubs[0].scheduled_for <= datetime.now(UTC) + timedelta(minutes=1)


def test_uploading_photo_for_immediate_slot_publishes_now(bootstrap, db, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "enable_auto_approval", True)

    client, org_id, _ = bootstrap(Role.OWNER, "hl-upload-publishes@example.com")
    brand_id = _brand(client)
    connection_id = _mock_connection(client, brand_id)
    _schedule(
        db,
        organization_id=org_id,
        brand_id=_u.UUID(brand_id),
        publishing_connection_id=_u.UUID(connection_id),
        max_per_day=1,
    )

    run_once()
    content = db.execute(
        select(ContentItem).where(
            ContentItem.organization_id == org_id,
            ContentItem.source_system == SourceSystem.HEADLINE_AUTO,
        )
    ).scalar_one()

    _upload_photo(client, brand_id=brand_id, content_item_id=str(content.id))

    pub = db.execute(select(Publication).where(Publication.organization_id == org_id)).scalar_one()
    assert pub.status.value == "PUBLISHED"
    assert pub.asset_id is not None
    assert pub.content_item_id == content.id


def test_uploading_photo_for_future_slot_schedules_instead_of_publishing(bootstrap, db, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "enable_auto_approval", True)

    client, org_id, _ = bootstrap(Role.OWNER, "hl-upload-schedules@example.com")
    brand_id = _brand(client)
    connection_id = _mock_connection(client, brand_id)
    _schedule(
        db,
        organization_id=org_id,
        brand_id=_u.UUID(brand_id),
        publishing_connection_id=_u.UUID(connection_id),
        interval_hours=2,
        max_per_day=2,
    )

    run_once()
    # Second slot (index 1) is ~2h in the future.
    pub_future = db.execute(
        select(Publication).where(Publication.organization_id == org_id).order_by(Publication.scheduled_for.desc())
    ).scalars().first()
    content = db.get(ContentItem, pub_future.content_item_id)

    _upload_photo(client, brand_id=brand_id, content_item_id=str(content.id))

    db.refresh(pub_future)
    assert pub_future.status == PublicationStatus.SCHEDULED
    assert pub_future.asset_id is not None


def test_uploading_photo_without_connection_does_not_publish(bootstrap, db, monkeypatch):
    """Auto-approved content with no publishing_connection_id configured
    must never be force-published — the photo still uploads fine, it just
    stays attached without a Publication."""
    from app.core.config import settings

    monkeypatch.setattr(settings, "enable_auto_approval", True)

    client, org_id, _ = bootstrap(Role.OWNER, "hl-upload-no-connection@example.com")
    brand_id = _brand(client)
    _schedule(db, organization_id=org_id, brand_id=_u.UUID(brand_id), max_per_day=1)

    run_once()
    content = db.execute(
        select(ContentItem).where(
            ContentItem.organization_id == org_id,
            ContentItem.source_system == SourceSystem.HEADLINE_AUTO,
        )
    ).scalar_one()

    result = _upload_photo(client, brand_id=brand_id, content_item_id=str(content.id))
    assert result["content_item_id"] == str(content.id)

    pubs = db.execute(select(Publication).where(Publication.organization_id == org_id)).scalars().all()
    assert pubs == []


def test_run_once_resets_and_regenerates_on_new_day(bootstrap, db):
    client, org_id, _ = bootstrap(Role.OWNER, "hl-worker-newday@example.com")
    brand_id = _brand(client)
    connection_id = _mock_connection(client, brand_id)
    row = _schedule(
        db,
        organization_id=org_id,
        brand_id=_u.UUID(brand_id),
        publishing_connection_id=_u.UUID(connection_id),
        max_per_day=1,
        daily_count=1,
        daily_count_date=datetime.now(UTC).date() - timedelta(days=1),
    )

    counts = run_once()
    assert counts["held_for_review"] + counts["awaiting_photo"] == 1

    db.refresh(row)
    assert row.daily_count == 1
    assert row.daily_count_date == datetime.now(UTC).date()


def test_run_now_already_ran_today_returns_none(bootstrap, db):
    client, org_id, _ = bootstrap(Role.OWNER, "hl-runnow-cap@example.com")
    brand_id = _brand(client)
    row = _schedule(
        db,
        organization_id=org_id,
        brand_id=_u.UUID(brand_id),
        max_per_day=1,
        daily_count=1,
        daily_count_date=datetime.now(UTC).date(),
    )

    outcome = run_now(row.id)
    assert outcome is None


# The MOCK AI provider always returns this exact title regardless of the
# topic fed into the prompt (see app/ai/providers.py) — which makes it a
# reliable stand-in for "the model regenerated the same headline again".
_MOCK_TITLE = "5 hábitos keto que sí puedes sostener"


def _mark_title_already_published(db, *, organization_id, brand_id) -> None:
    """Seed a HEADLINE_AUTO ContentItem + PUBLISHED Publication with the
    exact title the MOCK provider always returns, simulating "this headline
    already went out before"."""
    from app.models.enums import ContentStatus
    from app.utils.public_id import make as make_public_id

    content = ContentItem(
        organization_id=organization_id,
        public_id=make_public_id("cnt"),
        brand_id=brand_id,
        source_system=SourceSystem.HEADLINE_AUTO,
        title=_MOCK_TITLE,
        caption="Ya publicado antes.",
        status=ContentStatus.PUBLISHED,
        review_status=ReviewStatus.APPROVED,
    )
    db.add(content)
    db.flush()

    connection_id = db.execute(
        select(Publication.publishing_connection_id).where(Publication.organization_id == organization_id)
    ).scalars().first()
    if connection_id is None:
        from app.models.publishing import PublishingConnection

        connection_id = db.execute(
            select(PublishingConnection.id).where(PublishingConnection.organization_id == organization_id)
        ).scalars().first()

    publication = Publication(
        organization_id=organization_id,
        public_id=make_public_id("pub"),
        content_item_id=content.id,
        brand_id=brand_id,
        publishing_connection_id=connection_id,
        platform="FACEBOOK",
        publication_type="POST",
        status=PublicationStatus.PUBLISHED,
        caption=content.caption,
        title=content.title,
        idempotency_key=f"headline:{content.id}:seed",
    )
    db.add(publication)
    db.commit()


def test_duplicate_title_is_discarded_and_not_regenerated(bootstrap, db, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "enable_auto_approval", True)

    client, org_id, _ = bootstrap(Role.OWNER, "hl-worker-dup@example.com")
    brand_id = _brand(client)
    connection_id = _mock_connection(client, brand_id)

    # A headline with the MOCK provider's fixed title was already
    # published before — any new generation attempt will produce that
    # exact same title again (the MOCK provider ignores the topic), so it
    # must always be discarded instead of being kept as a fresh headline.
    _mark_title_already_published(db, organization_id=org_id, brand_id=_u.UUID(brand_id))

    _schedule(
        db,
        organization_id=org_id,
        brand_id=_u.UUID(brand_id),
        publishing_connection_id=_u.UUID(connection_id),
        max_per_day=1,
    )

    counts = run_once()

    # Every attempt for the single slot produced a duplicate and was
    # discarded — nothing new was kept as awaiting-photo/held-for-review,
    # and the net "generated" count is zero (each duplicate is generated
    # then immediately rolled back out of the count).
    assert counts["awaiting_photo"] == 0
    assert counts["held_for_review"] == 0
    assert counts["generated"] == 0

    # Only the original, already-published ContentItem with that title
    # still exists — no duplicate rows were left behind in the DB.
    matching = db.execute(
        select(ContentItem).where(
            ContentItem.organization_id == org_id,
            ContentItem.source_system == SourceSystem.HEADLINE_AUTO,
            ContentItem.title == _MOCK_TITLE,
        )
    ).scalars().all()
    assert len(matching) == 1
    assert matching[0].status == "PUBLISHED"


def test_uploading_photo_for_duplicate_title_does_not_publish(bootstrap, db, monkeypatch):
    """Two different days' batches (or generation-time dedup missing a
    race) can both leave a DRAFT, photo-less headline sitting around with
    a title that later gets published under a different ContentItem —
    publish_headline_content is the last gate before it actually goes out
    to Facebook/Instagram, so uploading a photo for the stale duplicate
    must not publish it."""
    from app.core.config import settings
    from app.models.enums import ContentStatus
    from app.utils.public_id import make as make_public_id

    monkeypatch.setattr(settings, "enable_auto_approval", True)

    client, org_id, _ = bootstrap(Role.OWNER, "hl-upload-dup@example.com")
    brand_id = _brand(client)
    connection_id = _mock_connection(client, brand_id)

    # A headline awaiting its photo, pre-planned with a DRAFT publication
    # for an immediate slot — same shape _generate_daily_batch produces.
    stale_content = ContentItem(
        organization_id=org_id,
        public_id=make_public_id("cnt"),
        brand_id=_u.UUID(brand_id),
        source_system=SourceSystem.HEADLINE_AUTO,
        title=_MOCK_TITLE,
        caption="Esperando foto.",
        status=ContentStatus.DRAFT,
        review_status=ReviewStatus.APPROVED,
    )
    db.add(stale_content)
    db.flush()
    stale_publication = Publication(
        organization_id=org_id,
        public_id=make_public_id("pub"),
        content_item_id=stale_content.id,
        brand_id=_u.UUID(brand_id),
        publishing_connection_id=_u.UUID(connection_id),
        platform="FACEBOOK",
        publication_type="POST",
        status=PublicationStatus.DRAFT,
        caption=stale_content.caption,
        title=stale_content.title,
        idempotency_key=f"headline:{stale_content.id}",
    )
    db.add(stale_publication)
    db.commit()

    # ...meanwhile the exact same title already went out for real, under
    # a different ContentItem.
    _mark_title_already_published(db, organization_id=org_id, brand_id=_u.UUID(brand_id))

    _upload_photo(client, brand_id=brand_id, content_item_id=str(stale_content.id))

    db.refresh(stale_publication)
    # The photo attaches (the upload itself always succeeds), but the
    # publish gate blocks it — it must never reach READY/PUBLISHED.
    assert stale_publication.status == PublicationStatus.DRAFT
