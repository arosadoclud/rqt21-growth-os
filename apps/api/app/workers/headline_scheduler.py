"""One-shot worker: the automatic "Headline" content cycle.

Once a day (the first time it's due, tracked by daily_count_date), each
enabled HeadlineSchedule gets its ENTIRE day's batch of keto-recipe
SOCIAL_POST copy generated at once (caption/cta/hashtags, Claude) — up to
max_per_day headlines, one every interval_hours apart starting from the
moment the batch runs. Each is submitted for review immediately (same
synchronous auto-approval hook as everything else in the platform); an
approved one gets a DRAFT Publication pre-created right away too (if the
schedule has a connection configured) with its slot's scheduled_for time
already set — it just has no photo yet.

No image is generated. A human uploads the flyer photo for each approved
headline whenever they like (see app.api.v1.headline's pending-photos
endpoint and the hook in app.api.v1.assets.complete_upload) — this was a
deliberate product decision (2026-08-02): letting an image model draw the
flyer produced illegible/off-brand results too often, so photo quality is
guaranteed by having a human pick it. Uploading the photo attaches it to
that headline's pre-scheduled Publication and either publishes it right
away (if its slot time has already passed) or leaves it SCHEDULED for its
slot — app.workers.publish_due is what actually fires it at that time,
same generic "publish this later" mechanism the rest of the platform uses
for manually-scheduled publications. This worker itself never publishes
anything — it only ever creates DRAFT/SCHEDULED rows.

Usage::

    uv run python -m app.workers.headline_scheduler

Meant to be invoked by an EXTERNAL scheduler (cron, a Railway/Render
scheduled job) on a short cadence (~10-15 min) — same one-shot pattern as
app.workers.publish_due and app.workers.cleanup_published_assets. Each
schedule only actually generates once its day's batch hasn't run yet
(daily_count_date != today), so a frequent sweep just finds nothing to do
most of the time.

IMPORTANT (same caveat as app.workers.cleanup_published_assets, and now
ALSO true of app.workers.publish_due): production currently runs as a
single Railway "web" service built straight from the Dockerfile, not via
docker-compose.prod.yml — none of these sidecar loops run automatically
in the real Railway deployment. Separate Railway Cron Jobs (or
equivalent) must be configured for both this module AND publish_due for
scheduled headline photos to actually go out at their slot time instead
of sitting SCHEDULED forever.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select, update

from app import audit
from app.ai.headline_topics import next_topic
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
from app.models.headline import HeadlineSchedule
from app.models.membership import Membership, Role
from app.models.publishing import Publication, PublishingConnection
from app.monitoring.errors import get_error_reporter
from app.publishing.scheduler import get_scheduler
from app.publishing.validation import validate_publication_draft
from app.schemas.ai import GenerationInput
from app.utils.public_id import make as make_public_id

_KETO_AUDIENCE = (
    "Comunidad de personas que siguen la dieta keto en redes sociales, "
    "buscando contenido práctico y de alto valor sobre alimentación"
)

# The topic bank only has 18 entries (app.ai.headline_topics), so it
# repeats well before a brand runs out of days — and Claude tends to
# converge on near-identical titles for the same topic+objective prompt.
# A couple of retries with the next topic is enough to dodge that without
# burning too many extra real API calls on a single slot.
_MAX_DUPLICATE_RETRIES = 2


def _normalize_title(title: str) -> str:
    return " ".join((title or "").strip().lower().split())


def _title_already_published(db, organization_id: uuid.UUID, brand_id: uuid.UUID, title: str) -> bool:
    """True if a HEADLINE_AUTO ContentItem with this same (normalized)
    title already has a PUBLISHED Publication for this brand — i.e. this
    exact headline already went out before, so it must not go out again."""
    normalized = _normalize_title(title)
    if not normalized:
        return False
    titles = db.execute(
        select(ContentItem.title)
        .join(Publication, Publication.content_item_id == ContentItem.id)
        .where(
            ContentItem.organization_id == organization_id,
            ContentItem.brand_id == brand_id,
            ContentItem.source_system == SourceSystem.HEADLINE_AUTO,
            Publication.status == PublicationStatus.PUBLISHED,
        )
    ).scalars().all()
    return any(_normalize_title(t) == normalized for t in titles)

_scheduler = get_scheduler()


def _system_actor_user_id(db, organization_id: uuid.UUID) -> uuid.UUID | None:
    """Headline posts have no human triggering them, but GenerationJob and
    the AI budget tracker both require a user to attribute the run to.
    The org's longest-standing OWNER stands in for "the system acting on
    this organization's behalf" — same idea as a service account, without
    needing to introduce one. Returns None (and the caller skips the
    schedule) if the org somehow has no OWNER membership."""
    row = db.execute(
        select(Membership.user_id)
        .where(Membership.organization_id == organization_id, Membership.role == Role.OWNER)
        .order_by(Membership.created_at.asc())
        .limit(1)
    ).scalar_one_or_none()
    return row


def _resolve_targets(db, schedule: HeadlineSchedule) -> list[tuple[Platform, PublishingConnection]]:
    """Every platform this schedule has an ACTIVE connection configured
    for, right now — a schedule with both set fans out to both at once;
    one with only one set (or neither) publishes to just that one (or
    nowhere, leaving content sitting in the inbox)."""
    targets: list[tuple[Platform, PublishingConnection]] = []
    for platform, connection_id in (
        (Platform.FACEBOOK, schedule.facebook_connection_id),
        (Platform.INSTAGRAM, schedule.instagram_connection_id),
    ):
        if connection_id is None:
            continue
        connection = db.get(PublishingConnection, connection_id)
        if connection is not None and connection.status == ConnectionStatus.ACTIVE:
            targets.append((platform, connection))
    return targets


def _due_for_batch(row: HeadlineSchedule, today: date) -> bool:
    """A schedule needs its daily batch generated once per day — unlike
    the old per-post interval check, interval_hours no longer controls
    WHEN generation happens (that's now "once a day"), only how far apart
    each generated headline's publish slot is."""
    return row.daily_count_date != today


def _claim_batch(schedule_id: uuid.UUID, *, expected_daily_count_date: date | None, today: date) -> bool:
    """Atomic conditional UPDATE, same pattern as publish_due._claim —
    only one concurrent run can win the race to generate a given
    schedule's daily batch. Resets daily_count to 0 as part of the same
    atomic step since _generate_daily_batch counts up from there as it
    creates each headline."""
    with SessionLocal() as db:
        result = db.execute(
            update(HeadlineSchedule)
            .where(
                HeadlineSchedule.id == schedule_id,
                HeadlineSchedule.daily_count_date == expected_daily_count_date,
            )
            .values(daily_count_date=today, daily_count=0)
        )
        db.commit()
        return result.rowcount == 1


def _generate_daily_batch(schedule_id: uuid.UUID) -> dict[str, int]:
    """Generate this schedule's entire day of headline copy in one pass —
    up to max_per_day items, each assigned a scheduled_for slot
    interval_hours apart starting now. Returns
    {"generated", "awaiting_photo", "held_for_review"} counts."""
    from app.api.v1.generation_jobs import (
        convert_job_to_content_item,
        create_and_run_generation_job,
    )

    counts = {"generated": 0, "awaiting_photo": 0, "held_for_review": 0}
    now = datetime.now(UTC)

    with SessionLocal() as db:
        schedule = db.get(HeadlineSchedule, schedule_id)
        if schedule is None or not schedule.enabled:
            return counts

        actor_user_id = _system_actor_user_id(db, schedule.organization_id)
        if actor_user_id is None:
            return counts

        brand = db.get(Brand, schedule.brand_id)
        if brand is None:
            return counts

        targets = _resolve_targets(db, schedule)

        for slot_index in range(schedule.max_per_day):
            schedule.daily_count += 1
            db.flush()

            content = None
            text_job = None
            for _attempt in range(_MAX_DUPLICATE_RETRIES + 1):
                topic = next_topic(schedule.topic_rotation_index)
                schedule.topic_rotation_index += 1
                db.flush()

                gen_input = GenerationInput(
                    objective=topic["objective"],
                    platform="FACEBOOK / INSTAGRAM",
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
                        generation_type=GenerationType.SOCIAL_POST,
                        gen_input=gen_input,
                    )
                except Exception as exc:
                    get_error_reporter().capture_exception(
                        exc, schedule_id=str(schedule_id), source="headline_scheduler.generate_slot"
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
                    source_system=SourceSystem.HEADLINE_AUTO,
                )
                db.flush()

                # Never let the same headline (by title) go out twice — the
                # 18-entry topic bank repeats over time, and Claude tends to
                # converge on near-identical wording for the same topic, so
                # a real duplicate risk exists once a brand has been running
                # a while. If this title already published before, discard
                # this draft and try again with the next topic instead of
                # letting a repeat sit in "Esperando foto".
                if _title_already_published(db, schedule.organization_id, schedule.brand_id, candidate.title):
                    db.delete(candidate)
                    db.flush()
                    counts["generated"] -= 1
                    text_job = None
                    continue

                content = candidate
                break

            if content is None or text_job is None:
                continue

            if content.review_status != ReviewStatus.APPROVED:
                counts["held_for_review"] += 1
                continue

            counts["awaiting_photo"] += 1

            if targets:
                slot_time = now + timedelta(hours=schedule.interval_hours * slot_index)
                hashtags = (text_job.output_payload or {}).get("hashtags") or []
                for platform, connection in targets:
                    publication = Publication(
                        organization_id=schedule.organization_id,
                        public_id=make_public_id("pub"),
                        content_item_id=content.id,
                        brand_id=schedule.brand_id,
                        publishing_connection_id=connection.id,
                        asset_id=None,
                        platform=platform,
                        publication_type=PublicationType.POST,
                        status=PublicationStatus.DRAFT,
                        caption=content.caption or "",
                        title=content.title,
                        cta=content.cta,
                        hashtags=hashtags,
                        scheduled_for=slot_time,
                        idempotency_key=f"headline:{content.id}:{platform.value}",
                        created_by_user_id=None,
                    )
                    db.add(publication)

        schedule.last_run_at = now
        db.commit()

    return counts


def _publish_one(db, content: ContentItem, publication: Publication, *, actor_user_id: uuid.UUID | None) -> str:
    """Push a single already-asset-linked Publication as far toward
    "live" as it can go. Shared by publish_headline_content's fan-out
    loop — one call per platform target."""
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
            payload={"scheduled_for": publication.scheduled_for.isoformat(), "source": "headline_photo_upload"},
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
        payload={"public_id": publication.public_id, "source": "headline_photo_upload"},
    )
    db.commit()

    from app.api.v1.publications import _execute_publish

    _execute_publish(db, None, publication, connection, actor_user_id)
    return "published"


def publish_headline_content(
    db, content: ContentItem, asset: Asset, *, actor_user_id: uuid.UUID | None
) -> dict[str, str]:
    """Attach ``asset`` to every one of this headline's publish targets
    and push each one as far toward "live" as it can go, at the same
    time — one photo upload fans out to every platform (Facebook,
    Instagram) this brand's HeadlineSchedule has a connection configured
    for. Called by app.api.v1.assets.complete_upload the moment a photo
    lands on an approved HEADLINE_AUTO ContentItem. Returns
    ``{"status": "no_connection"}`` or ``{"status": "duplicate"}`` for
    the whole-content outcomes below, or one entry per platform actually
    processed (e.g. ``{"FACEBOOK": "published", "INSTAGRAM":
    "scheduled"}``) otherwise:

    - "published": the slot's time had already passed (or there was no
      pre-planned slot at all — a connection added after this headline
      was generated), so it published immediately.
    - "scheduled": the slot's time is still in the future; left
      SCHEDULED for app.workers.publish_due to actually fire.
    - "invalid": validation failed (e.g. caption too long) — left DRAFT
      with the photo attached for a human to fix and publish manually.
    - "no_connection" (per platform): that platform has no ACTIVE
      connection configured — skipped.
    - whole-content "duplicate": a headline with this exact title was
      already published to this brand before — the real gate against
      posting the same headline twice on Facebook/Instagram.
      Generation-time dedup (see _title_already_published in
      _generate_daily_batch) already covers same-day batches, but two
      different days' batches (or a manual /generate) can still both
      produce the same title before either one gets its photo uploaded —
      this is the last check before it actually goes out, so it always
      wins even if generation-time dedup missed it.

    Does not raise on any of these outcomes — the asset upload itself
    always succeeds regardless; the caller's transaction persists the
    asset link either way."""
    if content.review_status != ReviewStatus.APPROVED:
        return {"status": "no_connection"}

    if _title_already_published(db, content.organization_id, content.brand_id, content.title):
        return {"status": "duplicate"}

    existing = db.execute(
        select(Publication).where(Publication.content_item_id == content.id)
    ).scalars().all()
    covered = {p.platform for p in existing}

    schedule = db.execute(
        select(HeadlineSchedule).where(
            HeadlineSchedule.organization_id == content.organization_id,
            HeadlineSchedule.brand_id == content.brand_id,
        )
    ).scalar_one_or_none()

    # No slot was pre-planned for a platform if its schedule had no
    # connection configured yet when the daily batch was generated (or
    # got added afterward) — build one fresh for each newly-covered
    # platform and publish it right away, there's no slot time to honor.
    if schedule is not None and schedule.enabled:
        from app.models.ai import GenerationJob

        for platform, connection_id in (
            (Platform.FACEBOOK, schedule.facebook_connection_id),
            (Platform.INSTAGRAM, schedule.instagram_connection_id),
        ):
            if platform in covered or connection_id is None:
                continue
            connection = db.get(PublishingConnection, connection_id)
            if connection is None or connection.status != ConnectionStatus.ACTIVE:
                continue

            text_job = db.execute(
                select(GenerationJob).where(GenerationJob.content_item_id == content.id)
            ).scalar_one_or_none()
            hashtags = ((text_job.output_payload or {}).get("hashtags") if text_job else None) or []

            new_publication = Publication(
                organization_id=content.organization_id,
                public_id=make_public_id("pub"),
                content_item_id=content.id,
                brand_id=content.brand_id,
                publishing_connection_id=connection.id,
                asset_id=asset.id,
                platform=platform,
                publication_type=PublicationType.POST,
                status=PublicationStatus.DRAFT,
                caption=content.caption or "",
                title=content.title,
                cta=content.cta,
                hashtags=hashtags,
                idempotency_key=f"headline:{content.id}:{platform.value}",
                created_by_user_id=None,
            )
            db.add(new_publication)
            db.flush()
            existing.append(new_publication)

    if not existing:
        return {"status": "no_connection"}

    outcomes: dict[str, str] = {}
    for publication in existing:
        publication.asset_id = asset.id
        db.flush()
        outcomes[publication.platform.value] = _publish_one(db, content, publication, actor_user_id=actor_user_id)
    return outcomes


def run_now(schedule_id: uuid.UUID) -> dict[str, int] | None:
    """Manual trigger (POST /headline-config/{brand_id}/run-now): generate
    today's full batch of headline copy right away, if it hasn't already
    run today. Returns None if the schedule is disabled or its batch was
    already generated today (nothing to do) — the caller treats that as
    "already done, check pending-photos"."""
    today = datetime.now(UTC).date()

    with SessionLocal() as db:
        row = db.get(HeadlineSchedule, schedule_id)
        if row is None or not row.enabled:
            return None
        expected_date = row.daily_count_date
        if not _due_for_batch(row, today):
            return None

    if not _claim_batch(schedule_id, expected_daily_count_date=expected_date, today=today):
        return None

    try:
        return _generate_daily_batch(schedule_id)
    except Exception as exc:
        get_error_reporter().capture_exception(exc, schedule_id=str(schedule_id), source="headline_scheduler.run_now")
        return None


def run_once() -> dict[str, int]:
    today = datetime.now(UTC).date()
    counts = {"generated": 0, "awaiting_photo": 0, "held_for_review": 0, "skipped": 0}

    with SessionLocal() as db:
        schedule_ids = (
            db.execute(select(HeadlineSchedule.id).where(HeadlineSchedule.enabled.is_(True)))
            .scalars()
            .all()
        )

    for schedule_id in schedule_ids:
        with SessionLocal() as db:
            row = db.get(HeadlineSchedule, schedule_id)
            if row is None or not row.enabled or not _due_for_batch(row, today):
                counts["skipped"] += 1
                continue
            expected_date = row.daily_count_date

        if not _claim_batch(schedule_id, expected_daily_count_date=expected_date, today=today):
            counts["skipped"] += 1
            continue

        try:
            batch_counts = _generate_daily_batch(schedule_id)
        except Exception as exc:
            # One schedule's failure must never stop the sweep from
            # reaching the remaining schedules.
            get_error_reporter().capture_exception(
                exc, schedule_id=str(schedule_id), source="headline_scheduler.run_once"
            )
            counts["skipped"] += 1
            continue

        for key in ("generated", "awaiting_photo", "held_for_review"):
            counts[key] += batch_counts.get(key, 0)

    return counts


def main() -> None:
    result = run_once()
    print(f"[worker] headline_scheduler: {result}")


if __name__ == "__main__":
    main()
