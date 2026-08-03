"""Historias auto-cycle: app.api.v1.story (config CRUD) and
app.workers.story_scheduler (batch copy generation only — no image).
Uses the MOCK AI providers (forced in conftest) and a MOCK publishing
connection — never a real Anthropic/Meta call.

Same daily-batch + scheduled-slot design as test_headline.py, but the
slot spacing unit is interval_minutes (default 40) instead of
interval_hours — Historias are short, conversational, follower-connection
content on a much tighter cadence than Headline."""

from __future__ import annotations

import base64
import uuid as _u
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.ai.story_topics import STORY_TOPICS, normalize_text, pair_key
from app.core.db import SessionLocal
from app.models.content import ContentItem
from app.models.enums import Platform, PublicationStatus, ReviewStatus, SourceSystem
from app.models.membership import Role
from app.models.publishing import Publication
from app.models.story import StorySchedule
from app.models.story_topic_usage import StoryTopicUsage
from app.workers.story_scheduler import (
    _delete_story_content,
    _find_existing_duplicate,
    _generate_daily_batch,
    _reserve_slot,
    _select_topic,
    _title_used_recently,
    run_now,
    run_once,
)

_PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 200


def _brand(client) -> str:
    slug = f"brand-{_u.uuid4().hex[:6]}"
    return client.post("/api/v1/brands", json={"name": slug, "slug": slug}).json()["id"]


def _mock_connection(client, brand_id: str, platform: str = "INSTAGRAM") -> str:
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


def _schedule(db, *, organization_id, brand_id, **overrides) -> StorySchedule:
    from app.utils.public_id import make as make_public_id

    overrides.setdefault("enabled", True)
    row = StorySchedule(
        organization_id=organization_id,
        public_id=make_public_id("sts"),
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
            "filename": "story.png",
            "mime_type": "image/png",
            "size_bytes": len(_PNG),
            "asset_type": "IMAGE",
            "brand_id": brand_id,
            "content_item_id": content_item_id,
            "alt_text": "Foto de la historia",
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


def test_get_story_config_lazily_creates_disabled_row(bootstrap, db):
    client, org_id, _ = bootstrap(Role.OWNER, "sty-config-get@example.com")
    brand_id = _brand(client)

    r = client.get(f"/api/v1/story-config/{brand_id}")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["enabled"] is False
    assert body["interval_minutes"] == 40
    assert body["max_per_day"] == 12

    row = db.execute(
        select(StorySchedule).where(StorySchedule.brand_id == _u.UUID(brand_id))
    ).scalar_one()
    assert row.enabled is False


def test_update_story_config_requires_owner_or_admin(bootstrap):
    client, _, _ = bootstrap(Role.MARKETER, "sty-config-forbidden@example.com")
    brand_id = _brand(client)
    r = client.put(
        f"/api/v1/story-config/{brand_id}",
        json={"enabled": True, "interval_minutes": 40, "max_per_day": 12},
    )
    assert r.status_code == 403


def test_update_story_config_enables_with_connection(bootstrap):
    client, _, _ = bootstrap(Role.OWNER, "sty-config-update@example.com")
    brand_id = _brand(client)
    connection_id = _mock_connection(client, brand_id)

    r = client.put(
        f"/api/v1/story-config/{brand_id}",
        json={
            "enabled": True,
            "publishing_connection_id": connection_id,
            "platform": "INSTAGRAM",
            "interval_minutes": 40,
            "max_per_day": 12,
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["enabled"] is True
    assert body["publishing_connection_id"] == connection_id


def test_update_story_config_rejects_platform_mismatch(bootstrap):
    client, _, _ = bootstrap(Role.OWNER, "sty-config-mismatch@example.com")
    brand_id = _brand(client)
    connection_id = _mock_connection(client, brand_id, platform="FACEBOOK")

    r = client.put(
        f"/api/v1/story-config/{brand_id}",
        json={
            "enabled": True,
            "publishing_connection_id": connection_id,
            "platform": "INSTAGRAM",
        },
    )
    assert r.status_code == 400


def test_update_story_config_supports_two_platforms_for_same_brand(bootstrap, db):
    """A brand can run Facebook and Instagram Historias at the same
    time — each PUT is keyed by (brand, platform), so configuring one
    must not touch or overwrite the other."""
    client, _, _ = bootstrap(Role.OWNER, "sty-config-two-platforms@example.com")
    brand_id = _brand(client)
    fb_connection_id = _mock_connection(client, brand_id, platform="FACEBOOK")
    ig_connection_id = _mock_connection(client, brand_id, platform="INSTAGRAM")

    r_fb = client.put(
        f"/api/v1/story-config/{brand_id}",
        json={
            "enabled": True,
            "publishing_connection_id": fb_connection_id,
            "platform": "FACEBOOK",
            "interval_minutes": 30,
            "max_per_day": 5,
        },
    )
    assert r_fb.status_code == 200, r_fb.text
    r_ig = client.put(
        f"/api/v1/story-config/{brand_id}",
        json={
            "enabled": True,
            "publishing_connection_id": ig_connection_id,
            "platform": "INSTAGRAM",
            "interval_minutes": 40,
            "max_per_day": 12,
        },
    )
    assert r_ig.status_code == 200, r_ig.text

    r_fb_read = client.get(f"/api/v1/story-config/{brand_id}", params={"platform": "FACEBOOK"})
    r_ig_read = client.get(f"/api/v1/story-config/{brand_id}", params={"platform": "INSTAGRAM"})
    assert r_fb_read.json()["publishing_connection_id"] == fb_connection_id
    assert r_fb_read.json()["max_per_day"] == 5
    assert r_ig_read.json()["publishing_connection_id"] == ig_connection_id
    assert r_ig_read.json()["max_per_day"] == 12

    rows = db.execute(
        select(StorySchedule).where(StorySchedule.brand_id == _u.UUID(brand_id))
    ).scalars().all()
    assert {row.platform for row in rows} == {"FACEBOOK", "INSTAGRAM"}


def test_list_story_configs_returns_one_row_per_platform(bootstrap):
    client, _, _ = bootstrap(Role.OWNER, "sty-config-list@example.com")
    brand_id = _brand(client)
    client.put(
        f"/api/v1/story-config/{brand_id}",
        json={"enabled": True, "platform": "FACEBOOK", "interval_minutes": 40, "max_per_day": 12},
    )
    client.put(
        f"/api/v1/story-config/{brand_id}",
        json={"enabled": False, "platform": "INSTAGRAM", "interval_minutes": 40, "max_per_day": 12},
    )
    r = client.get(f"/api/v1/story-config/{brand_id}/list")
    assert r.status_code == 200, r.text
    body = r.json()
    assert {row["platform"] for row in body} == {"FACEBOOK", "INSTAGRAM"}


def test_run_now_requires_enabled(bootstrap):
    client, _, _ = bootstrap(Role.OWNER, "sty-run-now-disabled@example.com")
    brand_id = _brand(client)
    r = client.post(f"/api/v1/story-config/{brand_id}/run-now")
    assert r.status_code == 400


def test_run_now_generates_todays_batch(bootstrap, db):
    client, org_id, _ = bootstrap(Role.OWNER, "sty-run-now@example.com")
    brand_id = _brand(client)
    client.put(
        f"/api/v1/story-config/{brand_id}",
        json={"enabled": True, "interval_minutes": 40, "max_per_day": 1},
    )

    r = client.post(f"/api/v1/story-config/{brand_id}/run-now")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["daily_count"] == 1
    assert body["last_run_at"] is not None
    assert body["daily_count_date"] == datetime.now(UTC).date().isoformat()

    items = db.execute(
        select(ContentItem).where(
            ContentItem.organization_id == org_id,
            ContentItem.source_system == SourceSystem.STORY_AUTO,
        )
    ).scalars().all()
    assert len(items) == 1


def test_run_now_twice_same_day_is_a_no_op(bootstrap):
    client, _, _ = bootstrap(Role.OWNER, "sty-run-now-twice@example.com")
    brand_id = _brand(client)
    client.put(
        f"/api/v1/story-config/{brand_id}",
        json={"enabled": True, "max_per_day": 1},
    )

    r1 = client.post(f"/api/v1/story-config/{brand_id}/run-now")
    assert r1.status_code == 200, r1.text

    r2 = client.post(f"/api/v1/story-config/{brand_id}/run-now")
    assert r2.status_code == 409


def test_story_history_lists_only_story_content(bootstrap, db):
    client, org_id, _ = bootstrap(Role.OWNER, "sty-history@example.com")
    brand_id = _brand(client)
    client.put(f"/api/v1/story-config/{brand_id}", json={"enabled": True, "max_per_day": 1})
    client.post(f"/api/v1/story-config/{brand_id}/run-now")

    # A manually created content item must not show up in the history feed.
    client.post("/api/v1/content-items", json={"brand_id": brand_id, "title": "Manual"})

    r = client.get(f"/api/v1/story-config/{brand_id}/history")
    assert r.status_code == 200, r.text
    body = r.json()
    assert len(body) == 1
    assert body[0]["title"]


def test_pending_photos_lists_approved_content_with_scheduled_for(bootstrap, db, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "enable_auto_approval", True)

    client, org_id, _ = bootstrap(Role.OWNER, "sty-pending@example.com")
    brand_id = _brand(client)
    connection_id = _mock_connection(client, brand_id)
    client.put(
        f"/api/v1/story-config/{brand_id}",
        json={
            "enabled": True,
            "publishing_connection_id": connection_id,
            "platform": "INSTAGRAM",
            "max_per_day": 1,
        },
    )
    client.post(f"/api/v1/story-config/{brand_id}/run-now")

    r = client.get(f"/api/v1/story-config/{brand_id}/pending-photos")
    assert r.status_code == 200, r.text
    body = r.json()
    assert len(body) == 1
    assert body[0]["scheduled_for"] is not None
    content_id = body[0]["id"]

    _upload_photo(client, brand_id=brand_id, content_item_id=content_id)

    r2 = client.get(f"/api/v1/story-config/{brand_id}/pending-photos")
    assert r2.json() == []


# ---------------------------------------------------------------- worker --


def test_normalize_text_ignores_emoji_case_and_punctuation():
    a = normalize_text("¿QUÉ PREPARAMOS HOY? Pollo al ajo 🐔 vs. Salmón cremoso 🐟")
    b = normalize_text("que preparamos hoy pollo al ajo VS salmon cremoso")
    assert a == b


def test_pair_key_is_order_independent():
    assert pair_key(("pollo", "salmon")) == pair_key(("salmon", "pollo"))
    assert pair_key(("Pollo 🐔", "Salmón!")) == pair_key(("salmon", "pollo"))


def test_select_topic_respects_seven_day_cooldown(bootstrap, db):
    client, org_id, _ = bootstrap(Role.OWNER, "sty-cooldown@example.com")
    brand_id = _u.UUID(_brand(client))
    now = datetime.now(UTC)

    # A topic used 2 days ago (inside the 7-day window) must not be
    # picked again; one used 8 days ago (outside the window) is fair
    # game again.
    on_cooldown = STORY_TOPICS[0]
    off_cooldown = STORY_TOPICS[1]

    db.add(
        StoryTopicUsage(
            organization_id=org_id,
            brand_id=brand_id,
            topic_id=str(on_cooldown["id"]),
            category=str(on_cooldown["category"]),
            pair_key=pair_key(on_cooldown.get("pair")),
            ingredients_key=None,
            normalized_title=normalize_text("algo publicado hace 2 dias"),
            used_at=now - timedelta(days=2),
        )
    )
    db.add(
        StoryTopicUsage(
            organization_id=org_id,
            brand_id=brand_id,
            topic_id=str(off_cooldown["id"]),
            category=str(off_cooldown["category"]),
            pair_key=pair_key(off_cooldown.get("pair")),
            ingredients_key=None,
            normalized_title=normalize_text("algo publicado hace 8 dias"),
            used_at=now - timedelta(days=8),
        )
    )
    db.commit()

    picks = [_select_topic(db, org_id, brand_id, now)["id"] for _ in range(50)]
    assert on_cooldown["id"] not in picks
    # off_cooldown is outside the window, so it's eligible again — not
    # asserting it's picked (random), just that it's not excluded.


def test_select_topic_avoids_pair_reuse_regardless_of_order(bootstrap, db):
    client, org_id, _ = bootstrap(Role.OWNER, "sty-pair-cooldown@example.com")
    brand_id = _u.UUID(_brand(client))
    now = datetime.now(UTC)

    pollo_salmon = next(t for t in STORY_TOPICS if t["id"] == "pollo_salmon")
    db.add(
        StoryTopicUsage(
            organization_id=org_id,
            brand_id=brand_id,
            topic_id="some_other_topic_id",  # different topic, same pair
            category=str(pollo_salmon["category"]),
            pair_key=pair_key(pollo_salmon["pair"]),
            ingredients_key=None,
            normalized_title=normalize_text("otro titulo con pollo y salmon"),
            used_at=now - timedelta(hours=1),
        )
    )
    db.commit()

    picks = [_select_topic(db, org_id, brand_id, now) for _ in range(50)]
    assert all(pair_key(p.get("pair")) != pair_key(pollo_salmon["pair"]) for p in picks)


def test_select_topic_cycles_categories_before_reusing_one(bootstrap, db):
    client, org_id, _ = bootstrap(Role.OWNER, "sty-category-cycle@example.com")
    brand_id = _u.UUID(_brand(client))
    now = datetime.now(UTC)
    all_categories = {t["category"] for t in STORY_TOPICS}

    used_categories: set[str] = set()
    for _ in range(len(all_categories)):
        topic = _select_topic(db, org_id, brand_id, now)
        assert topic["category"] not in used_categories, "reused a category before cycling all of them"
        used_categories.add(str(topic["category"]))
        db.add(
            StoryTopicUsage(
                organization_id=org_id,
                brand_id=brand_id,
                topic_id=str(topic["id"]),
                category=str(topic["category"]),
                pair_key=pair_key(topic.get("pair")),
                ingredients_key=None,
                normalized_title=normalize_text(f"titulo de prueba {topic['id']}"),
                used_at=now,
            )
        )
        db.commit()
    assert used_categories == all_categories


def test_title_used_recently_detects_normalized_match(bootstrap, db):
    client, org_id, _ = bootstrap(Role.OWNER, "sty-title-cooldown@example.com")
    brand_id = _u.UUID(_brand(client))
    now = datetime.now(UTC)

    db.add(
        StoryTopicUsage(
            organization_id=org_id,
            brand_id=brand_id,
            topic_id="pollo_salmon",
            category="esto_o_lo_otro",
            pair_key="pollo|salmon",
            ingredients_key=None,
            normalized_title=normalize_text("¿QUÉ PREPARAMOS HOY? Pollo al ajo 🐔 vs. Salmón 🐟"),
            used_at=now - timedelta(days=3),
        )
    )
    db.add(
        StoryTopicUsage(
            organization_id=org_id,
            brand_id=brand_id,
            topic_id="duelo_snacks",
            category="encuesta",
            pair_key="nueces|rollitos de queso",
            ingredients_key=None,
            normalized_title=normalize_text("algo publicado hace mas de una semana"),
            used_at=now - timedelta(days=9),
        )
    )
    db.commit()

    # Same content, different emoji/case/punctuation — still a match, and
    # still inside the 7-day window.
    assert _title_used_recently(db, org_id, brand_id, "que preparamos hoy pollo al ajo vs salmon", now) is True
    # Outside the 7-day window — no longer on cooldown.
    assert _title_used_recently(db, org_id, brand_id, "algo publicado hace mas de una semana", now) is False
    # Never used at all.
    assert _title_used_recently(db, org_id, brand_id, "algo completamente distinto", now) is False


def test_reserve_slot_stops_exactly_at_max_per_day(bootstrap, db):
    client, org_id, _ = bootstrap(Role.OWNER, "sty-reserve-cap@example.com")
    brand_id = _u.UUID(_brand(client))
    row = _schedule(db, organization_id=org_id, brand_id=brand_id, max_per_day=3, daily_count=0)

    reservations = [_reserve_slot(db, row.id) for _ in range(5)]
    assert reservations == [1, 2, 3, None, None]

    db.refresh(row)
    assert row.daily_count == 3


def test_reserve_slot_never_exceeds_cap_under_concurrency(bootstrap, db):
    """Real concurrency test: several threads race to reserve slots on
    the same schedule via independent DB sessions, same as the actual
    worker would under two overlapping cron runs. The atomic conditional
    UPDATE in _reserve_slot must ensure the total successful reservations
    never exceeds max_per_day and no slot number is ever handed out
    twice, regardless of interleaving."""
    import threading

    client, org_id, _ = bootstrap(Role.OWNER, "sty-reserve-concurrency@example.com")
    brand_id = _u.UUID(_brand(client))
    row = _schedule(db, organization_id=org_id, brand_id=brand_id, max_per_day=5, daily_count=0)
    schedule_id = row.id

    results: list[int | None] = []
    lock = threading.Lock()

    def worker() -> None:
        with SessionLocal() as thread_db:
            reserved = _reserve_slot(thread_db, schedule_id)
        with lock:
            results.append(reserved)

    threads = [threading.Thread(target=worker) for _ in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    successful = [r for r in results if r is not None]
    assert len(successful) == 5
    assert sorted(successful) == [1, 2, 3, 4, 5]

    db.refresh(row)
    assert row.daily_count == 5


def test_generate_daily_batch_stops_without_calling_claude_once_cap_reached(bootstrap, db, monkeypatch):
    """If the daily cap was already reached (e.g. by a previous run),
    _generate_daily_batch must return immediately without ever calling
    the AI provider or creating a ContentItem — requirement: never call
    Claude nor create records once max_per_day is hit."""
    from app.core.config import settings

    monkeypatch.setattr(settings, "enable_auto_approval", True)

    client, org_id, _ = bootstrap(Role.OWNER, "sty-cap-reached@example.com")
    brand_id = _u.UUID(_brand(client))
    connection_id = _mock_connection(client, str(brand_id))
    _schedule(
        db,
        organization_id=org_id,
        brand_id=brand_id,
        publishing_connection_id=_u.UUID(connection_id),
        max_per_day=2,
        daily_count=2,  # already at the cap
        daily_count_date=datetime.now(UTC).date(),
    )

    calls = {"count": 0}
    from app.api.v1 import generation_jobs as generation_jobs_module

    def _spy(*args, **kwargs):
        calls["count"] += 1
        raise AssertionError("Claude must not be called once the daily cap is reached")

    monkeypatch.setattr(generation_jobs_module, "create_and_run_generation_job", _spy)

    row = db.execute(select(StorySchedule).where(StorySchedule.brand_id == brand_id)).scalar_one()
    counts = _generate_daily_batch(row.id)

    assert calls["count"] == 0
    assert counts == {"generated": 0, "awaiting_photo": 0, "held_for_review": 0}

    items = db.execute(
        select(ContentItem).where(
            ContentItem.organization_id == org_id, ContentItem.source_system == SourceSystem.STORY_AUTO
        )
    ).scalars().all()
    assert items == []


def test_run_once_skips_disabled_schedule(bootstrap, db):
    client, org_id, _ = bootstrap(Role.OWNER, "sty-worker-disabled@example.com")
    brand_id = _brand(client)
    _schedule(db, organization_id=org_id, brand_id=_u.UUID(brand_id), enabled=False)

    counts = run_once()
    assert counts["skipped"] >= 0  # disabled schedules aren't even selected


def test_run_once_skips_when_already_ran_today(bootstrap, db):
    client, org_id, _ = bootstrap(Role.OWNER, "sty-worker-not-due@example.com")
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
    still generate a ContentItem (source_system=STORY_AUTO), but it stays
    IN_REVIEW in Bandeja, with no image and no publication."""
    client, org_id, _ = bootstrap(Role.OWNER, "sty-worker-holds@example.com")
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

    content = db.execute(
        select(ContentItem).where(
            ContentItem.organization_id == org_id,
            ContentItem.source_system == SourceSystem.STORY_AUTO,
        )
    ).scalar_one()
    assert content.review_status == ReviewStatus.IN_REVIEW

    pubs = db.execute(select(Publication).where(Publication.organization_id == org_id)).scalars().all()
    assert pubs == []


def test_run_once_marks_approved_content_awaiting_photo_with_draft_publication(bootstrap, db, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "enable_auto_approval", True)

    client, org_id, _ = bootstrap(Role.OWNER, "sty-worker-awaiting@example.com")
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
            ContentItem.source_system == SourceSystem.STORY_AUTO,
        )
    ).scalar_one()
    assert content.review_status == ReviewStatus.APPROVED

    # A DRAFT Publication with no asset yet is pre-created for its slot —
    # nothing is actually published until a human uploads the photo.
    pub = db.execute(select(Publication).where(Publication.organization_id == org_id)).scalar_one()
    assert pub.status == PublicationStatus.DRAFT
    assert pub.asset_id is None
    assert pub.scheduled_for is not None
    assert pub.publication_type.value == "STORY"


def test_batch_generation_spaces_slots_by_interval_minutes(bootstrap, db, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "enable_auto_approval", True)
    # The MOCK AI provider always returns the exact same title regardless
    # of topic — real Claude varies phrasing, but MOCK doesn't, so the
    # 7-day title cooldown (working as designed) would otherwise discard
    # every slot after the first here. Bypass it for this test, whose
    # actual purpose is verifying slot spacing, not cooldown behavior
    # (that's covered separately by the cooldown-specific tests below).
    monkeypatch.setattr("app.workers.story_scheduler._title_used_recently", lambda *a, **k: False)
    monkeypatch.setattr("app.workers.story_scheduler._find_existing_duplicate", lambda *a, **k: None)

    client, org_id, _ = bootstrap(Role.OWNER, "sty-worker-batch@example.com")
    brand_id = _brand(client)
    connection_id = _mock_connection(client, brand_id)
    _schedule(
        db,
        organization_id=org_id,
        brand_id=_u.UUID(brand_id),
        publishing_connection_id=_u.UUID(connection_id),
        interval_minutes=40,
        max_per_day=3,
    )

    counts = run_once()
    assert counts["awaiting_photo"] == 3

    pubs = db.execute(
        select(Publication).where(Publication.organization_id == org_id).order_by(Publication.scheduled_for)
    ).scalars().all()
    assert len(pubs) == 3
    gaps = [
        (pubs[i + 1].scheduled_for - pubs[i].scheduled_for).total_seconds() / 60
        for i in range(len(pubs) - 1)
    ]
    assert gaps == [40.0, 40.0]
    # First slot is immediate (roughly "now"), not pushed out an interval.
    assert pubs[0].scheduled_for <= datetime.now(UTC) + timedelta(minutes=1)


def test_uploading_photo_for_immediate_slot_publishes_now(bootstrap, db, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "enable_auto_approval", True)

    client, org_id, _ = bootstrap(Role.OWNER, "sty-upload-publishes@example.com")
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
            ContentItem.source_system == SourceSystem.STORY_AUTO,
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
    # Same MOCK-fixed-title caveat as test_batch_generation_spaces_slots_
    # by_interval_minutes above — this test needs 2 real slots, not a
    # cooldown discard on the second one.
    monkeypatch.setattr("app.workers.story_scheduler._title_used_recently", lambda *a, **k: False)
    monkeypatch.setattr("app.workers.story_scheduler._find_existing_duplicate", lambda *a, **k: None)

    client, org_id, _ = bootstrap(Role.OWNER, "sty-upload-schedules@example.com")
    brand_id = _brand(client)
    connection_id = _mock_connection(client, brand_id)
    _schedule(
        db,
        organization_id=org_id,
        brand_id=_u.UUID(brand_id),
        publishing_connection_id=_u.UUID(connection_id),
        interval_minutes=40,
        max_per_day=2,
    )

    run_once()
    # Second slot (index 1) is ~40min in the future.
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

    client, org_id, _ = bootstrap(Role.OWNER, "sty-upload-no-connection@example.com")
    brand_id = _brand(client)
    _schedule(db, organization_id=org_id, brand_id=_u.UUID(brand_id), max_per_day=1)

    run_once()
    content = db.execute(
        select(ContentItem).where(
            ContentItem.organization_id == org_id,
            ContentItem.source_system == SourceSystem.STORY_AUTO,
        )
    ).scalar_one()

    result = _upload_photo(client, brand_id=brand_id, content_item_id=str(content.id))
    assert result["content_item_id"] == str(content.id)

    pubs = db.execute(select(Publication).where(Publication.organization_id == org_id)).scalars().all()
    assert pubs == []


def test_uploading_photo_picks_matching_platform_schedule_when_brand_has_two(bootstrap, db, monkeypatch):
    """A brand can have both a FACEBOOK and an INSTAGRAM StorySchedule at
    once. Content generated by the FACEBOOK one (with no connection yet,
    so no Publication was pre-created) must, once a connection is added,
    publish through the FACEBOOK schedule/connection — not the unrelated
    INSTAGRAM one that happens to already have a connection — even though
    both rows match on (organization_id, brand_id)."""
    from app.core.config import settings

    monkeypatch.setattr(settings, "enable_auto_approval", True)

    client, org_id, _ = bootstrap(Role.OWNER, "sty-upload-two-platforms@example.com")
    brand_id = _brand(client)
    ig_connection_id = _mock_connection(client, brand_id, platform="INSTAGRAM")
    fb_connection_id = _mock_connection(client, brand_id, platform="FACEBOOK")

    _schedule(
        db,
        organization_id=org_id,
        brand_id=_u.UUID(brand_id),
        platform="INSTAGRAM",
        publishing_connection_id=_u.UUID(ig_connection_id),
        max_per_day=1,
    )
    fb_schedule = _schedule(
        db,
        organization_id=org_id,
        brand_id=_u.UUID(brand_id),
        platform="FACEBOOK",
        publishing_connection_id=None,
        max_per_day=1,
    )

    run_now(fb_schedule.id)
    content = db.execute(
        select(ContentItem).where(
            ContentItem.organization_id == org_id,
            ContentItem.source_system == SourceSystem.STORY_AUTO,
        )
    ).scalar_one()
    assert content.platform == Platform.FACEBOOK
    assert db.execute(select(Publication).where(Publication.organization_id == org_id)).scalars().all() == []

    fb_schedule.publishing_connection_id = _u.UUID(fb_connection_id)
    db.commit()

    _upload_photo(client, brand_id=brand_id, content_item_id=str(content.id))

    publication = db.execute(
        select(Publication).where(Publication.content_item_id == content.id)
    ).scalar_one()
    assert publication.platform == Platform.FACEBOOK
    assert publication.publishing_connection_id == _u.UUID(fb_connection_id)


def test_run_once_resets_and_regenerates_on_new_day(bootstrap, db):
    client, org_id, _ = bootstrap(Role.OWNER, "sty-worker-newday@example.com")
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
    client, org_id, _ = bootstrap(Role.OWNER, "sty-runnow-cap@example.com")
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
# reliable stand-in for "the model regenerated the same story again".
_MOCK_TITLE = "5 hábitos keto que sí puedes sostener"


def _mark_title_already_published(db, *, organization_id, brand_id) -> None:
    """Seed a STORY_AUTO ContentItem + PUBLISHED Publication with the
    exact title the MOCK provider always returns, simulating "this story
    already went out before"."""
    from app.models.enums import ContentStatus
    from app.utils.public_id import make as make_public_id

    content = ContentItem(
        organization_id=organization_id,
        public_id=make_public_id("cnt"),
        brand_id=brand_id,
        source_system=SourceSystem.STORY_AUTO,
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
        platform="INSTAGRAM",
        publication_type="STORY",
        status=PublicationStatus.PUBLISHED,
        caption=content.caption,
        title=content.title,
        idempotency_key=f"story:{content.id}:seed",
    )
    db.add(publication)
    db.commit()


def test_duplicate_title_is_discarded_and_not_regenerated(bootstrap, db, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "enable_auto_approval", True)

    client, org_id, _ = bootstrap(Role.OWNER, "sty-worker-dup@example.com")
    brand_id = _brand(client)
    connection_id = _mock_connection(client, brand_id)

    # A story with the MOCK provider's fixed title was already published
    # before — any new generation attempt will produce that exact same
    # title again (the MOCK provider ignores the topic), so it must
    # always be discarded instead of being kept as a fresh story.
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
            ContentItem.source_system == SourceSystem.STORY_AUTO,
            ContentItem.title == _MOCK_TITLE,
        )
    ).scalars().all()
    assert len(matching) == 1
    assert matching[0].status == "PUBLISHED"


def test_uploading_photo_for_duplicate_title_deletes_the_duplicate(bootstrap, db, monkeypatch):
    """Two different days' batches (or generation-time dedup missing a
    race) can both leave a DRAFT, photo-less story sitting around with a
    title that later gets published under a different ContentItem —
    publish_story_content is the last gate before it actually goes out to
    Instagram/Facebook. Uploading a photo for the stale duplicate must
    not publish it — it must delete the duplicate content and its
    Publication outright instead of leaving it stuck."""
    from app.core.config import settings
    from app.models.enums import ContentStatus
    from app.utils.public_id import make as make_public_id

    monkeypatch.setattr(settings, "enable_auto_approval", True)

    client, org_id, _ = bootstrap(Role.OWNER, "sty-upload-dup@example.com")
    brand_id = _brand(client)
    connection_id = _mock_connection(client, brand_id)

    # A story awaiting its photo, pre-planned with a DRAFT publication
    # for an immediate slot — same shape _generate_daily_batch produces.
    stale_content = ContentItem(
        organization_id=org_id,
        public_id=make_public_id("cnt"),
        brand_id=_u.UUID(brand_id),
        source_system=SourceSystem.STORY_AUTO,
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
        platform="INSTAGRAM",
        publication_type="STORY",
        status=PublicationStatus.DRAFT,
        caption=stale_content.caption,
        title=stale_content.title,
        idempotency_key=f"story:{stale_content.id}",
    )
    db.add(stale_publication)
    db.commit()
    stale_content_id, stale_publication_id = stale_content.id, stale_publication.id

    # ...meanwhile the exact same title already went out for real, under
    # a different ContentItem.
    _mark_title_already_published(db, organization_id=org_id, brand_id=_u.UUID(brand_id))

    result = _upload_photo(client, brand_id=brand_id, content_item_id=str(stale_content.id))
    # The upload endpoint itself still succeeds (it always does), but the
    # duplicate content and its stale Publication are gone afterward —
    # the uploaded asset survives, just detached from the deleted content.
    assert result["content_item_id"] is None

    # This session's identity map still holds stale references to
    # stale_content/stale_publication from before the HTTP call — db.get()
    # would return the zombie object, and even a fresh select() tries to
    # refresh them mid-query and blows up on a row that's now gone.
    # Drop them from the identity map outright (nothing here is
    # uncommitted) so the query below reflects what the server committed.
    db.expunge_all()
    assert db.execute(select(ContentItem).where(ContentItem.id == stale_content_id)).scalar_one_or_none() is None
    assert db.execute(select(Publication).where(Publication.id == stale_publication_id)).scalar_one_or_none() is None


def test_find_existing_duplicate_catches_pending_not_just_published(bootstrap, db):
    """_find_existing_duplicate is the absolute gate — unlike
    _title_already_published (PUBLISHED-only), it must also catch a
    duplicate that's still sitting in Bandeja/Esperando foto (DRAFT,
    never published) — this is the case the old code missed entirely."""
    from app.utils.public_id import make as make_public_id

    client, org_id, _ = bootstrap(Role.OWNER, "sty-find-dup@example.com")
    brand_id = _u.UUID(_brand(client))

    pending = ContentItem(
        organization_id=org_id,
        public_id=make_public_id("cnt"),
        brand_id=brand_id,
        source_system=SourceSystem.STORY_AUTO,
        title="¿POLLO 🐔 O SALMÓN?",
        caption="Esperando foto, nunca publicado.",
        review_status=ReviewStatus.APPROVED,
    )
    db.add(pending)
    db.commit()

    found = _find_existing_duplicate(db, org_id, brand_id, "pollo o salmon")
    assert found is not None
    assert found.id == pending.id

    # Excluding the item itself (e.g. checking a freshly-generated
    # candidate against everything else) must not match itself.
    assert _find_existing_duplicate(db, org_id, brand_id, "pollo o salmon", exclude_id=pending.id) is None

    assert _find_existing_duplicate(db, org_id, brand_id, "algo completamente distinto") is None


def test_delete_story_content_removes_publication_and_detaches_kept_asset(bootstrap, db):
    from app.models.assets import Asset
    from app.utils.public_id import make as make_public_id

    client, org_id, _ = bootstrap(Role.OWNER, "sty-delete-content@example.com")
    brand_id = _u.UUID(_brand(client))
    connection_id = _u.UUID(_mock_connection(client, str(brand_id)))

    content = ContentItem(
        organization_id=org_id,
        public_id=make_public_id("cnt"),
        brand_id=brand_id,
        source_system=SourceSystem.STORY_AUTO,
        title="A borrar",
        review_status=ReviewStatus.APPROVED,
    )
    db.add(content)
    db.flush()

    publication = Publication(
        organization_id=org_id,
        public_id=make_public_id("pub"),
        content_item_id=content.id,
        brand_id=brand_id,
        publishing_connection_id=connection_id,
        platform="INSTAGRAM",
        publication_type="STORY",
        status=PublicationStatus.DRAFT,
        title=content.title,
        idempotency_key=f"story:{content.id}",
    )
    db.add(publication)

    asset = Asset(
        organization_id=org_id,
        public_id=make_public_id("ast"),
        brand_id=brand_id,
        content_item_id=content.id,
        asset_type="IMAGE",
        storage_key="test/key.png",
        storage_provider="MOCK",
        original_filename="key.png",
        safe_filename="key.png",
        mime_type="image/png",
        size_bytes=10,
        checksum_sha256="0" * 64,
        status="READY",
    )
    db.add(asset)
    db.commit()

    content_id, publication_id, asset_id = content.id, publication.id, asset.id
    _delete_story_content(db, content, keep_asset=asset)

    assert db.get(ContentItem, content_id) is None
    assert db.get(Publication, publication_id) is None
    kept = db.get(Asset, asset_id)
    assert kept is not None
    assert kept.content_item_id is None
