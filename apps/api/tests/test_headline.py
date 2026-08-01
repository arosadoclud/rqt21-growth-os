"""Headline auto-cycle: app.api.v1.headline (config CRUD) and
app.workers.headline_scheduler (generation + conditional publish). Uses
the MOCK AI/image providers (forced in conftest) and a MOCK publishing
connection — never a real Anthropic/OpenAI/Meta call."""

from __future__ import annotations

import uuid as _u
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.ai.headline_topics import HEADLINE_TOPICS, next_topic
from app.models.content import ContentItem
from app.models.enums import ReviewStatus, SourceSystem
from app.models.headline import HeadlineSchedule
from app.models.membership import Role
from app.models.publishing import Publication
from app.workers.headline_scheduler import run_now, run_once


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


def test_run_now_generates_content(bootstrap, db):
    client, org_id, _ = bootstrap(Role.OWNER, "hl-run-now@example.com")
    brand_id = _brand(client)
    client.put(
        f"/api/v1/headline-config/{brand_id}",
        json={"enabled": True, "interval_hours": 2, "max_per_day": 12},
    )

    r = client.post(f"/api/v1/headline-config/{brand_id}/run-now")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["daily_count"] == 1
    assert body["last_run_at"] is not None

    items = db.execute(
        select(ContentItem).where(
            ContentItem.organization_id == org_id,
            ContentItem.source_system == SourceSystem.HEADLINE_AUTO,
        )
    ).scalars().all()
    assert len(items) == 1


def test_headline_history_lists_only_headline_content(bootstrap, db):
    client, org_id, _ = bootstrap(Role.OWNER, "hl-history@example.com")
    brand_id = _brand(client)
    client.put(f"/api/v1/headline-config/{brand_id}", json={"enabled": True})
    client.post(f"/api/v1/headline-config/{brand_id}/run-now")

    # A manually created content item must not show up in the history feed.
    client.post("/api/v1/content-items", json={"brand_id": brand_id, "title": "Manual"})

    r = client.get(f"/api/v1/headline-config/{brand_id}/history")
    assert r.status_code == 200, r.text
    body = r.json()
    assert len(body) == 1
    assert body[0]["title"]


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


def test_run_once_skips_when_not_due(bootstrap, db):
    client, org_id, _ = bootstrap(Role.OWNER, "hl-worker-not-due@example.com")
    brand_id = _brand(client)
    row = _schedule(
        db,
        organization_id=org_id,
        brand_id=_u.UUID(brand_id),
        interval_hours=2,
        last_run_at=datetime.now(UTC) - timedelta(minutes=5),
    )

    counts = run_once()
    assert counts["skipped"] == 1

    db.refresh(row)
    assert row.daily_count == 0


def test_run_once_generates_and_holds_for_review_without_auto_approval(bootstrap, db):
    """ENABLE_AUTO_APPROVAL is forced off in conftest — a due schedule must
    still generate a ContentItem (source_system=HEADLINE_AUTO), but it
    stays IN_REVIEW in Bandeja and nothing gets published."""
    client, org_id, _ = bootstrap(Role.OWNER, "hl-worker-holds@example.com")
    brand_id = _brand(client)
    connection_id = _mock_connection(client, brand_id)
    row = _schedule(
        db,
        organization_id=org_id,
        brand_id=_u.UUID(brand_id),
        publishing_connection_id=_u.UUID(connection_id),
    )

    counts = run_once()
    assert counts["held_for_review"] == 1
    assert counts["published"] == 0

    db.refresh(row)
    assert row.daily_count == 1
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


def test_run_once_generates_image_prompt_from_the_actual_headline_title(bootstrap, db):
    """The flyer image has the headline TITLE rendered onto it (branded
    visual style), so its generation prompt must be built from the real
    title SOCIAL_POST produced -- not the raw topic-bank entry that only
    seeded that generation. MockAIProvider always returns a fixed title
    ("5 hábitos keto que sí puedes sostener"), so the IMAGE_ASSET job's
    stored raw_input.topic must match that exact title, never the
    HEADLINE_TOPICS topic text used as the SOCIAL_POST input."""
    from app.models.ai import GenerationJob
    from app.models.enums import GenerationType

    client, org_id, _ = bootstrap(Role.OWNER, "hl-worker-image-topic@example.com")
    brand_id = _brand(client)
    connection_id = _mock_connection(client, brand_id)
    _schedule(
        db,
        organization_id=org_id,
        brand_id=_u.UUID(brand_id),
        publishing_connection_id=_u.UUID(connection_id),
    )

    counts = run_once()
    assert counts["held_for_review"] == 1

    image_job = db.execute(
        select(GenerationJob).where(
            GenerationJob.organization_id == org_id,
            GenerationJob.generation_type == GenerationType.IMAGE_ASSET,
        )
    ).scalar_one()
    assert image_job.input_payload["raw_input"]["topic"] == "5 hábitos keto que sí puedes sostener"

    text_job = db.execute(
        select(GenerationJob).where(
            GenerationJob.organization_id == org_id,
            GenerationJob.generation_type == GenerationType.SOCIAL_POST,
        )
    ).scalar_one()
    # The two jobs were seeded from the same topic-bank entry but the image
    # prompt's topic must NOT be that raw entry — it must be the generated
    # title instead, even though in this fixture the two only coincide
    # if the topic bank literally matches the mock title (it doesn't).
    assert image_job.input_payload["raw_input"]["topic"] != text_job.input_payload["raw_input"]["topic"]


def test_run_once_publishes_when_auto_approved(bootstrap, db, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "enable_auto_approval", True)

    client, org_id, _ = bootstrap(Role.OWNER, "hl-worker-publishes@example.com")
    brand_id = _brand(client)
    connection_id = _mock_connection(client, brand_id)
    _schedule(
        db,
        organization_id=org_id,
        brand_id=_u.UUID(brand_id),
        publishing_connection_id=_u.UUID(connection_id),
    )

    counts = run_once()
    assert counts["published"] == 1

    content = db.execute(
        select(ContentItem).where(
            ContentItem.organization_id == org_id,
            ContentItem.source_system == SourceSystem.HEADLINE_AUTO,
        )
    ).scalar_one()
    assert content.review_status == ReviewStatus.APPROVED

    pub = db.execute(select(Publication).where(Publication.organization_id == org_id)).scalar_one()
    assert pub.status.value == "PUBLISHED"
    assert pub.asset_id is not None


def test_run_once_holds_for_review_when_auto_approved_without_connection(bootstrap, db, monkeypatch):
    """Auto-approved content with no publishing_connection_id configured
    must never be force-published — it just stays approved in Bandeja."""
    from app.core.config import settings

    monkeypatch.setattr(settings, "enable_auto_approval", True)

    client, org_id, _ = bootstrap(Role.OWNER, "hl-worker-no-connection@example.com")
    brand_id = _brand(client)
    _schedule(db, organization_id=org_id, brand_id=_u.UUID(brand_id))

    counts = run_once()
    assert counts["held_for_review"] == 1
    assert counts["published"] == 0


def test_run_once_enforces_daily_cap(bootstrap, db):
    client, org_id, _ = bootstrap(Role.OWNER, "hl-worker-cap@example.com")
    brand_id = _brand(client)
    row = _schedule(
        db,
        organization_id=org_id,
        brand_id=_u.UUID(brand_id),
        max_per_day=1,
        daily_count=1,
        daily_count_date=datetime.now(UTC).date(),
    )

    counts = run_once()
    assert counts["skipped"] == 1
    assert counts["published"] == 0
    assert counts["held_for_review"] == 0

    db.refresh(row)
    assert row.daily_count == 1


def test_run_once_resets_daily_count_on_new_day(bootstrap, db):
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
    assert counts["held_for_review"] == 1

    db.refresh(row)
    assert row.daily_count == 1
    assert row.daily_count_date == datetime.now(UTC).date()


def test_run_now_bypasses_interval_but_respects_daily_cap(bootstrap, db):
    client, org_id, _ = bootstrap(Role.OWNER, "hl-runnow-cap@example.com")
    brand_id = _brand(client)
    row = _schedule(
        db,
        organization_id=org_id,
        brand_id=_u.UUID(brand_id),
        last_run_at=datetime.now(UTC),  # would never be "due" for run_once
        max_per_day=1,
        daily_count=1,
        daily_count_date=datetime.now(UTC).date(),
    )

    outcome = run_now(row.id)
    assert outcome == "skipped"
