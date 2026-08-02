"""One-shot worker: the automatic "Headline" content cycle.

For each enabled HeadlineSchedule that is due (now - last_run_at >=
interval_hours, and under max_per_day for today), generates a keto-recipe
SOCIAL_POST (caption/cta/hashtags, Claude), merges it into a ContentItem
(source_system=HEADLINE_AUTO) via the same conversion path a human-created
generation job uses, and submits it for review — same synchronous
auto-approval hook as everything else in the platform.

No image is generated here. A human uploads the flyer photo for each
approved headline (see app.api.v1.headline's pending-photos endpoint and
the hook in app.api.v1.assets.complete_upload) — this was a deliberate
product decision (2026-08-02): letting an image model draw the flyer
produced illegible/off-brand results too often even after other fixes, so
photo quality is now guaranteed by having a human pick it, while the copy
generation (the actual bottleneck of doing this by hand 12x/day) stays
fully automatic. publish_headline_content() is what actually publishes,
called the moment a matching photo is uploaded — this worker never
publishes anything itself, since it never has a photo to publish with.

Usage::

    uv run python -m app.workers.headline_scheduler

Meant to be invoked by an EXTERNAL scheduler (cron, a Railway/Render
scheduled job) on a short cadence (~10-15 min) — same one-shot pattern as
app.workers.publish_due and app.workers.cleanup_published_assets. Each
schedule tracks its own last_run_at/daily_count, so a frequent sweep just
finds nothing to do until a given schedule is actually due; interval_hours
and max_per_day are per-schedule config, not global.

IMPORTANT (same caveat as app.workers.cleanup_published_assets):
production currently runs as a single Railway "web" service built
straight from the Dockerfile, not via docker-compose.prod.yml — the
sidecar loop wired into that compose file does NOT automatically run in
the real Railway deployment. A separate Railway Cron Job (or equivalent)
must be configured to invoke this module on a schedule for the feature to
actually run in production.
"""

from __future__ import annotations

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
from app.publishing.validation import validate_publication_draft
from app.schemas.ai import GenerationInput
from app.utils.public_id import make as make_public_id

_KETO_AUDIENCE = (
    "Comunidad de personas que siguen la dieta keto en redes sociales, "
    "buscando contenido práctico y de alto valor sobre alimentación"
)


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


def _reset_daily_count_if_new_day(row: HeadlineSchedule, today: date) -> None:
    if row.daily_count_date != today:
        row.daily_count = 0
        row.daily_count_date = today


def _is_due(row: HeadlineSchedule, now: datetime) -> bool:
    if row.daily_count >= row.max_per_day:
        return False
    if row.last_run_at is None:
        return True
    return now - row.last_run_at >= timedelta(hours=row.interval_hours)


def _claim(
    schedule_id: uuid.UUID,
    *,
    expected_last_run_at: datetime | None,
    expected_daily_count: int,
    now: datetime,
    today: date,
) -> bool:
    """Atomic conditional UPDATE, same pattern as publish_due._claim and
    cleanup_published_assets._claim — a schedule only gets processed if its
    last_run_at/daily_count are still exactly what this pass observed, so
    two overlapping worker invocations can't both run the same schedule."""
    with SessionLocal() as db:
        result = db.execute(
            update(HeadlineSchedule)
            .where(
                HeadlineSchedule.id == schedule_id,
                HeadlineSchedule.last_run_at == expected_last_run_at,
                HeadlineSchedule.daily_count == expected_daily_count,
            )
            .values(last_run_at=now, daily_count=expected_daily_count + 1, daily_count_date=today)
        )
        db.commit()
        return result.rowcount == 1


def _run_schedule(schedule_id: uuid.UUID) -> str:
    """Generate one headline's copy for this schedule. Returns
    "awaiting_photo" (approved, waiting on a human to upload its flyer —
    see publish_headline_content), "held_for_review" (not auto-approved,
    needs a normal manual review), or "skipped" (missing actor/brand or
    generation failed — nothing was created)."""
    from app.api.v1.generation_jobs import (
        convert_job_to_content_item,
        create_and_run_generation_job,
    )

    with SessionLocal() as db:
        schedule = db.get(HeadlineSchedule, schedule_id)
        if schedule is None or not schedule.enabled:
            return "skipped"

        actor_user_id = _system_actor_user_id(db, schedule.organization_id)
        if actor_user_id is None:
            return "skipped"

        brand = db.get(Brand, schedule.brand_id)
        if brand is None:
            return "skipped"

        topic = next_topic(schedule.topic_rotation_index)
        schedule.topic_rotation_index += 1
        db.flush()

        gen_input = GenerationInput(
            objective=topic["objective"],
            platform=schedule.platform,
            topic=topic["topic"],
            audience=_KETO_AUDIENCE,
        )

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
        if text_job is None or text_job.status != GenerationStatus.COMPLETED:
            return "skipped"

        content = convert_job_to_content_item(
            db,
            text_job,
            organization_id=schedule.organization_id,
            actor_user_id=actor_user_id,
            source_system=SourceSystem.HEADLINE_AUTO,
        )
        db.commit()

        return "awaiting_photo" if content.review_status == ReviewStatus.APPROVED else "held_for_review"


def publish_headline_content(db, content: ContentItem, asset: Asset, *, actor_user_id: uuid.UUID | None) -> bool:
    """Build, validate and publish a Publication for a headline whose photo
    just arrived — called by app.api.v1.assets.complete_upload the moment
    an Asset gets linked to an approved HEADLINE_AUTO ContentItem. Returns
    True if it actually published, False if any precondition failed (no
    matching schedule, no connection configured, connection not ACTIVE,
    validation errors) — the content and its new photo are left exactly as
    they are either way, so a human can still publish manually from
    Distribución if this returns False. Does not commit on the False path;
    the caller's own transaction (asset upload) still persists the asset
    link regardless of this function's outcome."""
    if content.review_status != ReviewStatus.APPROVED:
        return False

    schedule = db.execute(
        select(HeadlineSchedule).where(
            HeadlineSchedule.organization_id == content.organization_id,
            HeadlineSchedule.brand_id == content.brand_id,
        )
    ).scalar_one_or_none()
    if schedule is None or not schedule.enabled or schedule.publishing_connection_id is None:
        return False

    connection = db.get(PublishingConnection, schedule.publishing_connection_id)
    if connection is None or connection.status != ConnectionStatus.ACTIVE:
        return False

    try:
        platform = Platform(schedule.platform)
    except ValueError:
        return False

    # ContentItem itself has no hashtags column — they live on the
    # GenerationJob's output_payload (see convert_job_to_content_item),
    # so fetch them back from the job that produced this content.
    from app.models.ai import GenerationJob

    text_job = db.execute(
        select(GenerationJob).where(GenerationJob.content_item_id == content.id)
    ).scalar_one_or_none()
    hashtags = ((text_job.output_payload or {}).get("hashtags") if text_job else None) or []
    caption = content.caption or ""

    validation = validate_publication_draft(
        platform=platform,
        publication_type=PublicationType.POST,
        caption=caption,
        hashtags=hashtags,
        asset=asset,
        cta=content.cta,
    )
    if validation.errors:
        return False

    publication = Publication(
        organization_id=content.organization_id,
        public_id=make_public_id("pub"),
        content_item_id=content.id,
        brand_id=content.brand_id,
        publishing_connection_id=connection.id,
        asset_id=asset.id,
        platform=platform,
        publication_type=PublicationType.POST,
        status=PublicationStatus.READY,
        caption=caption,
        title=content.title,
        cta=content.cta,
        hashtags=hashtags,
        idempotency_key=f"headline:{content.id}",
        created_by_user_id=None,
    )
    db.add(publication)
    db.flush()
    audit.record(
        db,
        action="publication.created",
        actor_user_id=actor_user_id,
        organization_id=content.organization_id,
        target_type="publication",
        target_id=publication.id,
        payload={"public_id": publication.public_id, "source": "headline_photo_upload"},
    )
    db.commit()

    from app.api.v1.publications import _execute_publish

    _execute_publish(db, None, publication, connection, actor_user_id)
    return True


def run_now(schedule_id: uuid.UUID) -> str:
    """Manual trigger (POST /headline-config/{brand_id}/run-now): generate
    one headline's copy right away, bypassing interval_hours but still
    enforcing max_per_day via the same atomic claim as the regular sweep,
    so a manual run and the scheduled sweep can never double-spend the
    same daily slot."""
    now = datetime.now(UTC)
    today = now.date()

    with SessionLocal() as db:
        row = db.get(HeadlineSchedule, schedule_id)
        if row is None or not row.enabled:
            return "skipped"
        _reset_daily_count_if_new_day(row, today)
        db.commit()
        if row.daily_count >= row.max_per_day:
            return "skipped"
        expected_last_run_at = row.last_run_at
        expected_daily_count = row.daily_count

    if not _claim(
        schedule_id,
        expected_last_run_at=expected_last_run_at,
        expected_daily_count=expected_daily_count,
        now=now,
        today=today,
    ):
        return "skipped"

    try:
        return _run_schedule(schedule_id)
    except Exception as exc:
        get_error_reporter().capture_exception(exc, schedule_id=str(schedule_id), source="headline_scheduler.run_now")
        return "skipped"


def run_once() -> dict[str, int]:
    now = datetime.now(UTC)
    today = now.date()
    counts = {"awaiting_photo": 0, "held_for_review": 0, "skipped": 0}

    with SessionLocal() as db:
        schedule_ids = (
            db.execute(select(HeadlineSchedule.id).where(HeadlineSchedule.enabled.is_(True)))
            .scalars()
            .all()
        )

    for schedule_id in schedule_ids:
        with SessionLocal() as db:
            row = db.get(HeadlineSchedule, schedule_id)
            if row is None or not row.enabled:
                counts["skipped"] += 1
                continue
            _reset_daily_count_if_new_day(row, today)
            db.commit()
            expected_last_run_at = row.last_run_at
            expected_daily_count = row.daily_count
            due = _is_due(row, now)

        if not due:
            counts["skipped"] += 1
            continue

        if not _claim(
            schedule_id,
            expected_last_run_at=expected_last_run_at,
            expected_daily_count=expected_daily_count,
            now=now,
            today=today,
        ):
            counts["skipped"] += 1
            continue

        try:
            outcome = _run_schedule(schedule_id)
        except Exception as exc:
            # A budget cap, a provider outage, anything unexpected — this
            # schedule already spent its claimed slot for this interval,
            # but one failure must never stop the sweep from reaching the
            # remaining schedules. Still reported so it's not silently
            # invisible (this bypasses FastAPI's global exception handler
            # since run_once is invoked from a worker/cron, not a request).
            get_error_reporter().capture_exception(
                exc, schedule_id=str(schedule_id), source="headline_scheduler.run_once"
            )
            outcome = "skipped"
        counts[outcome if outcome in counts else "skipped"] += 1

    return counts


def main() -> None:
    result = run_once()
    print(f"[worker] headline_scheduler: {result}")


if __name__ == "__main__":
    main()
