"""One-shot worker: the automatic "Headline" content cycle.

For each enabled HeadlineSchedule that is due (now - last_run_at >=
interval_hours, and under max_per_day for today), generates a keto-recipe
SOCIAL_POST (caption/cta/hashtags, Claude) plus a matching flyer image
(IMAGE_ASSET, DALL-E/Pollinations), merges them into a single ContentItem
(source_system=HEADLINE_AUTO) via the same conversion path a human-created
generation job uses, and submits it for review — same synchronous
auto-approval hook as everything else in the platform. Only if the
council actually approves it does this worker build and publish a
Publication straight to the schedule's connection; otherwise the content
simply stays in Bandeja for a human to look at, same as any other
auto-review outcome. This worker never force-publishes unapproved
content — that was an explicit product decision, not an oversight.

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
    """Generate + (maybe) publish one headline post for this schedule.
    Returns "published", "held_for_review", or "skipped" (missing actor /
    connection / asset — content still lands in Bandeja either way)."""
    from app.api.v1.generation_jobs import (
        convert_job_to_content_item,
        create_and_run_generation_job,
    )
    from app.api.v1.publications import _execute_publish

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

        # The flyer is a branded image with the headline TITLE rendered
        # onto it (see _brand_visual_directives in app.ai.runner) — it must
        # depict the actual generated headline, not the raw topic-bank
        # entry that only seeded the text generation. Text runs first
        # specifically so this is available: the image prompt's "topic" is
        # the real title text_job just produced (falling back to the topic
        # bank entry only if generation somehow produced no title).
        generated_title = (text_job.output_payload or {}).get("title") or topic["topic"]
        image_gen_input = GenerationInput(
            objective=topic["objective"],
            platform=schedule.platform,
            topic=generated_title,
            audience=_KETO_AUDIENCE,
        )

        image_job = create_and_run_generation_job(
            db,
            organization_id=schedule.organization_id,
            brand_id=schedule.brand_id,
            product_id=None,
            campaign_id=None,
            actor_user_id=actor_user_id,
            generation_type=GenerationType.IMAGE_ASSET,
            gen_input=image_gen_input,
        )
        if image_job is None or image_job.status != GenerationStatus.COMPLETED:
            # No ContentItem was created yet — nothing to leave in Bandeja,
            # the whole attempt just didn't produce anything this run.
            db.commit()
            return "skipped"

        content = convert_job_to_content_item(
            db,
            text_job,
            organization_id=schedule.organization_id,
            actor_user_id=actor_user_id,
            source_system=SourceSystem.HEADLINE_AUTO,
        )

        asset_id = (image_job.output_payload or {}).get("asset_id")
        content_asset_id: uuid.UUID | None = None
        if asset_id:
            asset = db.get(Asset, uuid.UUID(asset_id))
            if asset is not None and asset.organization_id == schedule.organization_id:
                asset.content_item_id = content.id
                content_asset_id = asset.id
        db.flush()

        if content.review_status != ReviewStatus.APPROVED:
            db.commit()
            return "held_for_review"

        if (
            schedule.publishing_connection_id is None
            or content_asset_id is None
        ):
            db.commit()
            return "held_for_review"

        connection = db.get(PublishingConnection, schedule.publishing_connection_id)
        if connection is None or connection.status != ConnectionStatus.ACTIVE:
            db.commit()
            return "held_for_review"

        try:
            platform = Platform(schedule.platform)
        except ValueError:
            db.commit()
            return "held_for_review"

        asset_row = db.get(Asset, content_asset_id)
        hashtags = (text_job.output_payload or {}).get("hashtags") or []
        caption = content.caption or ""

        validation = validate_publication_draft(
            platform=platform,
            publication_type=PublicationType.POST,
            caption=caption,
            hashtags=hashtags,
            asset=asset_row,
            cta=content.cta,
        )
        if validation.errors:
            db.commit()
            return "held_for_review"

        publication = Publication(
            organization_id=schedule.organization_id,
            public_id=make_public_id("pub"),
            content_item_id=content.id,
            brand_id=schedule.brand_id,
            publishing_connection_id=connection.id,
            asset_id=content_asset_id,
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
            organization_id=schedule.organization_id,
            target_type="publication",
            target_id=publication.id,
            payload={"public_id": publication.public_id, "source": "headline_scheduler"},
        )
        db.commit()

        _execute_publish(db, None, publication, connection, actor_user_id)
        return "published"


def run_now(schedule_id: uuid.UUID) -> str:
    """Manual trigger (POST /headline-config/{brand_id}/run-now): one
    generation+maybe-publish cycle for a single schedule right away,
    bypassing interval_hours but still enforcing max_per_day via the same
    atomic claim as the regular sweep, so a manual run and the scheduled
    sweep can never double-spend the same daily slot."""
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
    except Exception:
        return "skipped"


def run_once() -> dict[str, int]:
    now = datetime.now(UTC)
    today = now.date()
    counts = {"published": 0, "held_for_review": 0, "skipped": 0}

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
        except Exception:
            # A budget cap, a provider outage, anything unexpected — this
            # schedule already spent its claimed slot for this interval,
            # but one failure must never stop the sweep from reaching the
            # remaining schedules.
            outcome = "skipped"
        counts[outcome if outcome in counts else "skipped"] += 1

    return counts


def main() -> None:
    result = run_once()
    print(f"[worker] headline_scheduler: {result}")


if __name__ == "__main__":
    main()
