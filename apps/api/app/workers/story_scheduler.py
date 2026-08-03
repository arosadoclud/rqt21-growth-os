"""One-shot worker: the automatic "Historias" content cycle.

Same overall shape as app.workers.headline_scheduler (daily-batch
generation, human uploads the photo, app.workers.publish_due fires it at
its slot) but deliberately different in kind, not just configuration:
Historias are short, conversational, follower-connection prompts
(questions, polls, behind-the-scenes) on a much tighter cadence
(interval_minutes, default 40) — Stories are ephemeral (24h) and
consumed differently than a Headline feed post.

Once a day (the first time it's due, tracked by daily_count_date), each
enabled StorySchedule gets its ENTIRE day's batch of story copy generated
at once (caption/cta/hashtags, Claude, GenerationType.STORY) — up to
max_per_day items, one every interval_minutes apart starting from the
moment the batch runs. Each is submitted for review immediately (same
synchronous auto-approval hook as everything else in the platform); an
approved one gets a DRAFT Publication pre-created right away too (if the
schedule has a connection configured) with its slot's scheduled_for time
already set — it just has no photo yet.

No image is generated — same "a human picks the photo" product decision
as Headline (2026-08-02), for the same quality reason. Uploading the
photo attaches it to that story's pre-scheduled Publication and either
publishes it right away (if its slot time has already passed) or leaves
it SCHEDULED for its slot — app.workers.publish_due is what actually
fires it at that time.

Usage::

    uv run python -m app.workers.story_scheduler

Meant to be invoked by an EXTERNAL scheduler (Railway Cron Job) on a
short cadence — the interval_minutes granularity is much finer than
Headline's, so this should run more often (~10 min) than
headline_scheduler's (~15 min) to keep slot timing accurate.
"""

from __future__ import annotations

import asyncio
import random
import uuid
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select, update

from app import audit
from app.ai.story_topics import (
    INTERACTIVE_STYLE_GUIDE,
    STORY_TOPICS,
    ingredients_key,
    normalize_text,
    pair_key,
)
from app.core.db import SessionLocal
from app.models.assets import Asset
from app.models.brand import Brand
from app.models.content import ContentItem
from app.models.enums import (
    ConnectionStatus,
    GenerationStatus,
    GenerationType,
    Platform,
    PublicationStatus,
    PublicationType,
    ReviewStatus,
    SourceSystem,
)
from app.models.membership import Membership, Role
from app.models.publishing import Publication, PublishingConnection
from app.models.story import StorySchedule
from app.models.story_topic_usage import StoryTopicUsage
from app.monitoring.errors import get_error_reporter
from app.publishing.scheduler import get_scheduler
from app.publishing.validation import validate_publication_draft
from app.schemas.ai import GenerationInput
from app.utils.public_id import make as make_public_id

_KETO_AUDIENCE = (
    "Comunidad de personas que siguen la dieta keto en redes sociales, "
    "buscando contenido práctico y de alto valor sobre alimentación"
)

# How many attempts to dodge a duplicate/on-cooldown title within a
# single slot before giving up on it — Claude sometimes converges on
# near-identical wording for the same topic.
_MAX_DUPLICATE_RETRIES = 2

# Never reuse the same topic, answer-pair, or main ingredient combo (nor
# the same generated title, regardless of emoji/case/punctuation) for a
# given brand within this many days.
_COOLDOWN_DAYS = 7


def _normalize_title(title: str) -> str:
    return normalize_text(title)


def _title_already_published(db, organization_id: uuid.UUID, brand_id: uuid.UUID, title: str) -> bool:
    """True if a STORY_AUTO ContentItem with this same (normalized) title
    already has a PUBLISHED Publication for this brand — i.e. this exact
    story already went out before, so it must not go out again. This is
    the "never post the same thing twice, ever" gate, checked right
    before actually publishing (see publish_story_content); the separate
    7-day _title_used_recently below is the generation-time variety gate."""
    normalized = normalize_text(title)
    if not normalized:
        return False
    titles = db.execute(
        select(ContentItem.title)
        .join(Publication, Publication.content_item_id == ContentItem.id)
        .where(
            ContentItem.organization_id == organization_id,
            ContentItem.brand_id == brand_id,
            ContentItem.source_system == SourceSystem.STORY_AUTO,
            Publication.status == PublicationStatus.PUBLISHED,
        )
    ).scalars().all()
    return any(normalize_text(t) == normalized for t in titles)


def _title_used_recently(db, organization_id: uuid.UUID, brand_id: uuid.UUID, title: str, now: datetime) -> bool:
    """True if a story with this same (normalized) title was generated
    for this brand in the last _COOLDOWN_DAYS days, regardless of
    publish status — the generation-time variety gate (requirement:
    "cooldown de 7 días para títulos"), broader than
    _title_already_published's "ever published" check."""
    normalized = normalize_text(title)
    if not normalized:
        return False
    cutoff = now - timedelta(days=_COOLDOWN_DAYS)
    row = db.execute(
        select(StoryTopicUsage.id)
        .where(
            StoryTopicUsage.organization_id == organization_id,
            StoryTopicUsage.brand_id == brand_id,
            StoryTopicUsage.normalized_title == normalized,
            StoryTopicUsage.used_at >= cutoff,
        )
        .limit(1)
    ).first()
    return row is not None


def _find_existing_duplicate(
    db, organization_id: uuid.UUID, brand_id: uuid.UUID, title: str, *, exclude_id: uuid.UUID | None = None
) -> ContentItem | None:
    """The absolute "never two stories with the same title" gate — unlike
    _title_already_published (PUBLISHED-only) or _title_used_recently
    (7-day window), this checks EVERY existing STORY_AUTO ContentItem for
    this brand regardless of status or age. Returns the existing
    duplicate if found, so the caller can delete it."""
    normalized = normalize_text(title)
    if not normalized:
        return None
    candidates = db.execute(
        select(ContentItem).where(
            ContentItem.organization_id == organization_id,
            ContentItem.brand_id == brand_id,
            ContentItem.source_system == SourceSystem.STORY_AUTO,
        )
    ).scalars().all()
    for candidate in candidates:
        if exclude_id is not None and candidate.id == exclude_id:
            continue
        if normalize_text(candidate.title) == normalized:
            return candidate
    return None


def _delete_story_content(db, content: ContentItem, *, keep_asset: Asset | None = None) -> None:
    """Remove a duplicate-titled story entirely instead of letting it sit
    around: deletes its Publication row(s) first (content_items.id has an
    ondelete=RESTRICT foreign key from publications, so those must go
    first) and the ContentItem itself. ``keep_asset`` is the just-uploaded
    photo the caller (app.api.v1.assets.complete_upload) still holds a
    reference to and will refresh/return right after this call — it's
    detached (content_item_id set to NULL, same as the FK's own
    ondelete=SET NULL would do) rather than deleted, so that refresh
    doesn't blow up on a row that no longer exists. Any OTHER asset
    already linked to this content is deleted outright."""
    pubs = db.execute(select(Publication).where(Publication.content_item_id == content.id)).scalars().all()
    for pub in pubs:
        db.delete(pub)
    db.flush()

    linked_assets = db.execute(select(Asset).where(Asset.content_item_id == content.id)).scalars().all()
    for a in linked_assets:
        if keep_asset is not None and a.id == keep_asset.id:
            a.content_item_id = None
        else:
            db.delete(a)
    db.flush()

    db.delete(content)
    db.commit()


def _select_topic(db, organization_id: uuid.UUID, brand_id: uuid.UUID, now: datetime) -> dict[str, object]:
    """Pick a topic avoiding (a) any topic/pair/ingredient combo used for
    this brand in the last _COOLDOWN_DAYS days, and (b) any category
    already used earlier TODAY — so a day's batch cycles through every
    category before any of them repeat, instead of the old flat
    round-robin. Degrades gracefully (relaxing category variety, then
    pair/ingredient cooldown, then topic-id cooldown, in that order)
    rather than ever blocking generation outright — with 45 topics
    across 9 categories this fallback should essentially never trigger,
    but a much higher max_per_day than the bank supports must still work
    instead of erroring."""
    cutoff = now - timedelta(days=_COOLDOWN_DAYS)
    today_start = datetime(now.year, now.month, now.day, tzinfo=UTC)

    recent = db.execute(
        select(
            StoryTopicUsage.topic_id,
            StoryTopicUsage.pair_key,
            StoryTopicUsage.ingredients_key,
            StoryTopicUsage.category,
            StoryTopicUsage.used_at,
        ).where(
            StoryTopicUsage.organization_id == organization_id,
            StoryTopicUsage.brand_id == brand_id,
            StoryTopicUsage.used_at >= cutoff,
        )
    ).all()

    used_topic_ids = {r.topic_id for r in recent}
    used_pair_keys = {r.pair_key for r in recent if r.pair_key}
    used_ingredient_keys = {r.ingredients_key for r in recent if r.ingredients_key}
    used_categories_today = {r.category for r in recent if r.used_at >= today_start}

    def eligible(topic: dict[str, object], *, respect_category: bool, respect_cooldown: bool) -> bool:
        if respect_cooldown:
            if topic["id"] in used_topic_ids:
                return False
            pk = pair_key(topic.get("pair"))  # type: ignore[arg-type]
            if pk and pk in used_pair_keys:
                return False
            ik = ingredients_key(topic.get("ingredients"))  # type: ignore[arg-type]
            if ik and ik in used_ingredient_keys:
                return False
        if respect_category and topic["category"] in used_categories_today:
            return False
        return True

    for respect_category, respect_cooldown in ((True, True), (False, True), (True, False), (False, False)):
        candidates = [
            t for t in STORY_TOPICS if eligible(t, respect_category=respect_category, respect_cooldown=respect_cooldown)
        ]
        if candidates:
            return random.choice(candidates)
    return STORY_TOPICS[0]  # unreachable in practice — the bank is never empty


_scheduler = get_scheduler()


def _system_actor_user_id(db, organization_id: uuid.UUID) -> uuid.UUID | None:
    """Same "org's longest-standing OWNER stands in for the system" idea
    as headline_scheduler._system_actor_user_id — GenerationJob and the AI
    budget tracker both require a user to attribute the run to."""
    row = db.execute(
        select(Membership.user_id)
        .where(Membership.organization_id == organization_id, Membership.role == Role.OWNER)
        .order_by(Membership.created_at.asc())
        .limit(1)
    ).scalar_one_or_none()
    return row


def _due_for_batch(row: StorySchedule, today: date) -> bool:
    return row.daily_count_date != today


def _claim_batch(schedule_id: uuid.UUID, *, expected_daily_count_date: date | None, today: date) -> bool:
    """Atomic conditional UPDATE, same pattern as
    headline_scheduler._claim_batch — only one concurrent run can win the
    race to generate a given schedule's daily batch."""
    with SessionLocal() as db:
        result = db.execute(
            update(StorySchedule)
            .where(
                StorySchedule.id == schedule_id,
                StorySchedule.daily_count_date == expected_daily_count_date,
            )
            .values(daily_count_date=today, daily_count=0)
        )
        db.commit()
        return result.rowcount == 1


def _reserve_slot(db, schedule_id: uuid.UUID) -> int | None:
    """Atomically increments daily_count by 1 ONLY if it's still below
    max_per_day, in a single conditional UPDATE — this is the actual
    concurrency guard against ever exceeding the daily cap: the WHERE
    comparison and the increment happen in one SQL statement (Postgres
    row-locks the row for the duration), so two processes racing to
    reserve the same schedule's next slot can never together push
    daily_count past max_per_day, unlike a Python-side read-then-write.
    Returns the new daily_count, or None once the cap is reached — the
    caller must stop immediately in that case, before calling Claude or
    creating anything. Commits on its own so the reservation is durable
    and visible to any concurrent run right away."""
    result = db.execute(
        update(StorySchedule)
        .where(
            StorySchedule.id == schedule_id,
            StorySchedule.daily_count < StorySchedule.max_per_day,
        )
        .values(daily_count=StorySchedule.daily_count + 1)
        .returning(StorySchedule.daily_count)
    )
    db.commit()
    row = result.first()
    return row[0] if row else None


def _generate_daily_batch(schedule_id: uuid.UUID) -> dict[str, int]:
    """Generate this schedule's entire day of story copy in one pass — up
    to max_per_day items, each assigned a scheduled_for slot
    interval_minutes apart starting now. Returns
    {"generated", "awaiting_photo", "held_for_review"} counts."""
    from app.api.v1.generation_jobs import (
        convert_job_to_content_item,
        create_and_run_generation_job,
    )

    counts = {"generated": 0, "awaiting_photo": 0, "held_for_review": 0}
    now = datetime.now(UTC)

    with SessionLocal() as db:
        schedule = db.get(StorySchedule, schedule_id)
        if schedule is None or not schedule.enabled:
            return counts

        actor_user_id = _system_actor_user_id(db, schedule.organization_id)
        if actor_user_id is None:
            return counts

        brand = db.get(Brand, schedule.brand_id)
        if brand is None:
            return counts

        connection: PublishingConnection | None = None
        platform: Platform | None = None
        if schedule.publishing_connection_id is not None:
            connection = db.get(PublishingConnection, schedule.publishing_connection_id)
            if connection is not None and connection.status != ConnectionStatus.ACTIVE:
                connection = None
            try:
                platform = Platform(schedule.platform)
            except ValueError:
                platform = None

        interval_minutes = schedule.interval_minutes

        while True:
            # Atomic per-slot reservation — the actual guard against ever
            # exceeding max_per_day, even under concurrent runs. Reaching
            # the cap stops the loop immediately, before calling Claude
            # or creating anything for this slot.
            reserved = _reserve_slot(db, schedule_id)
            if reserved is None:
                break
            slot_index = reserved - 1

            content = None
            text_job = None
            for _attempt in range(_MAX_DUPLICATE_RETRIES + 1):
                topic = _select_topic(db, schedule.organization_id, schedule.brand_id, now)

                gen_input = GenerationInput(
                    objective=f"{topic['objective']} {INTERACTIVE_STYLE_GUIDE}",
                    platform=schedule.platform,
                    topic=topic["topic"],
                    audience=_KETO_AUDIENCE,
                )

                try:
                    text_job = create_and_run_generation_job(
                        db,
                        organization_id=schedule.organization_id,
                        brand_id=schedule.brand_id,
                        product_id=None,
                        campaign_id=None,
                        actor_user_id=actor_user_id,
                        generation_type=GenerationType.STORY,
                        gen_input=gen_input,
                    )
                except Exception as exc:
                    get_error_reporter().capture_exception(
                        exc, schedule_id=str(schedule_id), source="story_scheduler.generate_slot"
                    )
                    text_job = None
                    continue
                if text_job is None or text_job.status != GenerationStatus.COMPLETED:
                    text_job = None
                    continue

                counts["generated"] += 1
                candidate = convert_job_to_content_item(
                    db,
                    text_job,
                    organization_id=schedule.organization_id,
                    actor_user_id=actor_user_id,
                    source_system=SourceSystem.STORY_AUTO,
                )
                db.flush()

                # Absolute gate: never let two stories share the same
                # (normalized) title, period — regardless of status or
                # age — plus the narrower published/7-day checks below,
                # kept for their own docstring's reasoning.
                if (
                    _find_existing_duplicate(
                        db, schedule.organization_id, schedule.brand_id, candidate.title, exclude_id=candidate.id
                    )
                    is not None
                    or _title_already_published(db, schedule.organization_id, schedule.brand_id, candidate.title)
                    or _title_used_recently(db, schedule.organization_id, schedule.brand_id, candidate.title, now)
                ):
                    db.delete(candidate)
                    db.flush()
                    counts["generated"] -= 1
                    text_job = None
                    continue

                content = candidate
                db.add(
                    StoryTopicUsage(
                        organization_id=schedule.organization_id,
                        brand_id=schedule.brand_id,
                        topic_id=str(topic["id"]),
                        category=str(topic["category"]),
                        pair_key=pair_key(topic.get("pair")),  # type: ignore[arg-type]
                        ingredients_key=ingredients_key(topic.get("ingredients")),  # type: ignore[arg-type]
                        normalized_title=normalize_text(candidate.title),
                        used_at=now,
                    )
                )
                db.flush()
                break

            if content is None or text_job is None:
                continue

            if content.review_status != ReviewStatus.APPROVED:
                counts["held_for_review"] += 1
                continue

            counts["awaiting_photo"] += 1

            if connection is not None and platform is not None:
                slot_time = now + timedelta(minutes=interval_minutes * slot_index)
                hashtags = (text_job.output_payload or {}).get("hashtags") or []
                publication = Publication(
                    organization_id=schedule.organization_id,
                    public_id=make_public_id("pub"),
                    content_item_id=content.id,
                    brand_id=schedule.brand_id,
                    publishing_connection_id=connection.id,
                    asset_id=None,
                    platform=platform,
                    publication_type=PublicationType.STORY,
                    status=PublicationStatus.DRAFT,
                    caption=content.caption or "",
                    title=content.title,
                    cta=content.cta,
                    hashtags=hashtags,
                    scheduled_for=slot_time,
                    idempotency_key=f"story:{content.id}",
                    created_by_user_id=None,
                )
                db.add(publication)
            db.commit()

        schedule.last_run_at = now
        db.commit()
    return counts


def publish_story_content(db, content: ContentItem, asset: Asset, *, actor_user_id: uuid.UUID | None) -> str:
    """Attach ``asset`` to whatever this story's publish slot is and move
    it as far toward "live" as it can go. Called by
    app.api.v1.assets.complete_upload the moment a photo lands on an
    approved STORY_AUTO ContentItem. Returns:

    - "published": the slot's time had already passed (or there was no
      pre-planned slot at all — a connection added after this story was
      generated), so it published immediately.
    - "scheduled": the slot's time is still in the future; left
      SCHEDULED for app.workers.publish_due to actually fire.
    - "invalid": validation failed (e.g. caption too long) — left DRAFT
      with the photo attached for a human to fix and publish manually.
    - "no_connection": nothing to publish to; the photo just sits
      attached to the content with no Publication at all.
    - "duplicate_deleted": a story with this exact title already exists
      for this brand (published, pending, or otherwise) — the upload
      must not go through, so instead of leaving this one stuck, it (and
      its Publication, if any) is deleted outright; the just-uploaded
      photo is detached rather than deleted, since the caller still
      holds a reference to it.

    Does not raise on any of these outcomes — the asset upload itself
    always succeeds regardless; the caller's transaction persists the
    asset link either way."""
    if content.review_status != ReviewStatus.APPROVED:
        return "no_connection"

    duplicate = _find_existing_duplicate(
        db, content.organization_id, content.brand_id, content.title, exclude_id=content.id
    )
    if duplicate is not None or _title_already_published(db, content.organization_id, content.brand_id, content.title):
        _delete_story_content(db, content, keep_asset=asset)
        return "duplicate_deleted"

    publication = db.execute(
        select(Publication).where(Publication.content_item_id == content.id)
    ).scalar_one_or_none()

    if publication is None:
        # No slot was pre-planned for this story (its schedule had no
        # connection configured yet when the daily batch was generated).
        # Fall back to building one fresh and publishing right away —
        # there's no slot time to honor, so immediate is the only option.
        schedule = db.execute(
            select(StorySchedule).where(
                StorySchedule.organization_id == content.organization_id,
                StorySchedule.brand_id == content.brand_id,
            )
        ).scalar_one_or_none()
        if schedule is None or not schedule.enabled or schedule.publishing_connection_id is None:
            return "no_connection"
        connection = db.get(PublishingConnection, schedule.publishing_connection_id)
        if connection is None or connection.status != ConnectionStatus.ACTIVE:
            return "no_connection"
        try:
            platform = Platform(schedule.platform)
        except ValueError:
            return "no_connection"

        from app.models.ai import GenerationJob

        text_job = db.execute(
            select(GenerationJob).where(GenerationJob.content_item_id == content.id)
        ).scalar_one_or_none()
        hashtags = ((text_job.output_payload or {}).get("hashtags") if text_job else None) or []

        publication = Publication(
            organization_id=content.organization_id,
            public_id=make_public_id("pub"),
            content_item_id=content.id,
            brand_id=content.brand_id,
            publishing_connection_id=connection.id,
            asset_id=asset.id,
            platform=platform,
            publication_type=PublicationType.STORY,
            status=PublicationStatus.DRAFT,
            caption=content.caption or "",
            title=content.title,
            cta=content.cta,
            hashtags=hashtags,
            idempotency_key=f"story:{content.id}",
            created_by_user_id=None,
        )
        db.add(publication)
        db.flush()
    else:
        publication.asset_id = asset.id
        db.flush()

    connection = db.get(PublishingConnection, publication.publishing_connection_id)
    if connection is None or connection.status != ConnectionStatus.ACTIVE:
        return "no_connection"

    asset_row = db.get(Asset, publication.asset_id)
    validation = validate_publication_draft(
        platform=publication.platform,
        publication_type=publication.publication_type,
        caption=publication.caption,
        hashtags=publication.hashtags,
        asset=asset_row,
        cta=publication.cta,
    )
    if validation.errors:
        db.commit()
        return "invalid"

    now = datetime.now(UTC)
    if publication.scheduled_for is not None and publication.scheduled_for > now:
        publication.status = PublicationStatus.SCHEDULED
        db.flush()
        audit.record(
            db,
            action="publication.scheduled",
            actor_user_id=actor_user_id,
            organization_id=content.organization_id,
            target_type="publication",
            target_id=publication.id,
            payload={"scheduled_for": publication.scheduled_for.isoformat(), "source": "story_photo_upload"},
        )
        db.commit()
        asyncio.run(_scheduler.schedule("publication", publication.id, publication.scheduled_for))
        return "scheduled"

    publication.status = PublicationStatus.READY
    db.flush()
    audit.record(
        db,
        action="publication.created" if publication.created_by_user_id is None else "publication.updated",
        actor_user_id=actor_user_id,
        organization_id=content.organization_id,
        target_type="publication",
        target_id=publication.id,
        payload={"public_id": publication.public_id, "source": "story_photo_upload"},
    )
    db.commit()

    from app.api.v1.publications import _execute_publish

    _execute_publish(db, None, publication, connection, actor_user_id)
    return "published"


def run_now(schedule_id: uuid.UUID) -> dict[str, int] | None:
    """Generate today's full batch for one schedule right away, if it
    hasn't already run today. Returns None if it was already run today,
    the schedule is disabled, or generation failed to even claim (a run
    is already in progress)."""
    with SessionLocal() as db:
        row = db.get(StorySchedule, schedule_id)
        if row is None or not row.enabled:
            return None
        today = datetime.now(UTC).date()
        if not _due_for_batch(row, today):
            return None
        expected = row.daily_count_date

    if not _claim_batch(schedule_id, expected_daily_count_date=expected, today=today):
        return None

    try:
        return _generate_daily_batch(schedule_id)
    except Exception as exc:
        get_error_reporter().capture_exception(exc, schedule_id=str(schedule_id), source="story_scheduler.run_now")
        return None


def run_once() -> dict[str, int]:
    """Sweep all enabled schedules, batch-generating any not yet run
    today. Meant to be invoked on a recurring cadence by an external
    scheduler."""
    counts = {"generated": 0, "awaiting_photo": 0, "held_for_review": 0, "skipped": 0}
    today = datetime.now(UTC).date()

    with SessionLocal() as db:
        schedule_ids = db.execute(
            select(StorySchedule.id, StorySchedule.daily_count_date).where(StorySchedule.enabled.is_(True))
        ).all()

    for schedule_id, daily_count_date in schedule_ids:
        if daily_count_date == today:
            counts["skipped"] += 1
            continue
        if not _claim_batch(schedule_id, expected_daily_count_date=daily_count_date, today=today):
            counts["skipped"] += 1
            continue
        try:
            result = _generate_daily_batch(schedule_id)
        except Exception as exc:
            get_error_reporter().capture_exception(
                exc, schedule_id=str(schedule_id), source="story_scheduler.run_once"
            )
            counts["skipped"] += 1
            continue
        for key in ("generated", "awaiting_photo", "held_for_review"):
            counts[key] += result.get(key, 0)

    return counts


def main() -> None:
    result = run_once()
    print(f"[worker] story_scheduler: {result}")


if __name__ == "__main__":
    main()
