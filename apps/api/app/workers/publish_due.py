"""One-shot worker: publish or retry due publications.

Usage::

    uv run python -m app.workers.publish_due

Meant to be invoked by an EXTERNAL scheduler (cron, a Railway/Render
scheduled job, a GitHub Actions cron, etc) at a short interval — this module
does a single pass over due work and exits. It is NOT a long-running loop and
does not use asyncio.create_task() as a persistence mechanism; the durable
state is entirely in Postgres (Publication.scheduled_for / next_retry_at).

Double-processing is prevented with an atomic conditional UPDATE ("claim")
per publication: a row only gets processed if it's still in the expected
SCHEDULED/RETRY_SCHEDULED state at claim time, so two overlapping worker
invocations (or a retry of this same command) can't both execute it.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select, update

from app.core.db import SessionLocal
from app.models.enums import ConnectionStatus, PublicationStatus
from app.models.publishing import Publication, PublishingConnection


def _claim(session_factory, publication_id: uuid.UUID, from_status: PublicationStatus) -> bool:
    with session_factory() as db:
        result = db.execute(
            update(Publication)
            .where(Publication.id == publication_id, Publication.status == from_status)
            .values(status=PublicationStatus.PUBLISHING)
        )
        db.commit()
        return result.rowcount == 1


def _process(pub_id: uuid.UUID) -> str:
    from app.api.v1.publications import _execute_publish

    with SessionLocal() as db:
        row = db.get(Publication, pub_id)
        if row is None:
            return "missing"
        connection = db.get(PublishingConnection, row.publishing_connection_id)
        if connection is None or connection.status != ConnectionStatus.ACTIVE:
            row.status = PublicationStatus.FAILED
            row.failure_code = (
                "connection_revoked"
                if connection is not None
                and connection.status in (ConnectionStatus.REVOKED, ConnectionStatus.DISABLED)
                else "connection_not_active"
            )
            row.failure_message = "publishing connection is not ACTIVE"
            row.next_retry_at = None
            db.commit()
            return "connection_unavailable"
        _execute_publish(db, None, row, connection, row.created_by_user_id)
        return "processed"


def run_once() -> dict[str, int]:
    now = datetime.now(UTC)
    counts = {"scheduled_processed": 0, "retries_processed": 0, "skipped": 0}

    with SessionLocal() as db:
        due_scheduled = db.execute(
            select(Publication.id).where(
                Publication.status == PublicationStatus.SCHEDULED,
                Publication.scheduled_for.is_not(None),
                Publication.scheduled_for <= now,
            )
        ).scalars().all()
        due_retry = db.execute(
            select(Publication.id).where(
                Publication.status == PublicationStatus.RETRY_SCHEDULED,
                Publication.next_retry_at.is_not(None),
                Publication.next_retry_at <= now,
            )
        ).scalars().all()

    for pub_id in due_scheduled:
        if not _claim(SessionLocal, pub_id, PublicationStatus.SCHEDULED):
            counts["skipped"] += 1
            continue
        _process(pub_id)
        counts["scheduled_processed"] += 1

    for pub_id in due_retry:
        if not _claim(SessionLocal, pub_id, PublicationStatus.RETRY_SCHEDULED):
            counts["skipped"] += 1
            continue
        _process(pub_id)
        counts["retries_processed"] += 1

    return counts


def main() -> None:
    result = run_once()
    print(f"[worker] publish_due: {result}")


if __name__ == "__main__":
    main()
