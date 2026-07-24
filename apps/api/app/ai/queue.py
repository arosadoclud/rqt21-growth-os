"""Job execution queue abstraction.

``JobQueue`` is the seam the rest of the app depends on for background-ish
execution. Two implementations exist:

- ``InlineJobQueue`` executes synchronously in-process — correct for a
  single-replica deployment and for tests, but not a substitute for a real
  distributed queue once the API runs multiple replicas or execution needs
  to survive a process restart.
- ``RedisJobQueue`` (Phase 6A) enqueues onto a real Redis-backed RQ queue,
  processed by one or more ``rq worker`` processes (see
  ``app.workers.rq_tasks`` and ``scripts/run_worker.sh``). Idempotency is
  enforced by using the caller-supplied ``idempotency_key`` as the RQ job
  id — Redis rejects/dedupes a second enqueue with the same id, so two API
  replicas racing to enqueue the same logical job converge on one RQ job.

Which backend is used is controlled by ``settings.queue_backend``
(``inline`` by default; ``redis`` opts in once ``REDIS_URL`` is set) via
``get_job_queue()``. Nothing above this layer needs to know which backend is
active.

Publication scheduling (Phase 5) uses the separate
``app.publishing.scheduler.Scheduler`` Protocol instead, because scheduling
a task for a FUTURE time is a different contract than "run this now" — see
that module's docstring.
"""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

from app.core.config import settings


@dataclass(frozen=True)
class JobQueueStatus:
    job_id: uuid.UUID
    state: str  # "queued" | "running" | "done" | "cancelled" | "unknown"
    attempt: int
    idempotency_key: str | None
    next_retry_at: datetime | None


StatusLookup = Callable[[uuid.UUID], Awaitable[JobQueueStatus]]


class JobQueue(Protocol):
    async def enqueue(
        self, job_id: uuid.UUID, *, idempotency_key: str | None = None
    ) -> None: ...

    async def cancel(self, job_id: uuid.UUID) -> None: ...

    async def get_status(self, job_id: uuid.UUID) -> JobQueueStatus: ...


class InlineJobQueue:
    """Synchronous, in-process queue. Runs the job immediately on enqueue.

    Single-replica only: if the process restarts mid-job, the job is left in
    RUNNING with no automatic recovery. Acceptable for dev/tests and the
    default until ``QUEUE_BACKEND=redis`` is set; documented explicitly so
    it isn't mistaken for production-grade queuing.

    ``cancel`` is necessarily a no-op here — by the time a caller could call
    it, the synchronous run has already completed. It exists so callers can
    be written against the Protocol without special-casing this backend; a
    real distributed queue would actually stop a not-yet-started job.
    """

    def __init__(self, runner, status_lookup: StatusLookup | None = None) -> None:
        self._runner = runner
        self._status_lookup = status_lookup

    async def enqueue(
        self, job_id: uuid.UUID, *, idempotency_key: str | None = None
    ) -> None:
        await self._runner(job_id)

    async def cancel(self, job_id: uuid.UUID) -> None:
        return None

    async def get_status(self, job_id: uuid.UUID) -> JobQueueStatus:
        if self._status_lookup is not None:
            return await self._status_lookup(job_id)
        return JobQueueStatus(
            job_id=job_id, state="unknown", attempt=1, idempotency_key=None, next_retry_at=None
        )


_RQ_STATE_MAP = {
    "queued": "queued",
    "scheduled": "queued",
    "deferred": "queued",
    "started": "running",
    "finished": "done",
    "failed": "unknown",
    "stopped": "cancelled",
    "canceled": "cancelled",
}


class RedisJobQueue:
    """RQ-backed distributed queue. Requires a real Redis connection and at
    least one ``rq worker`` process consuming the same queue name for
    anything to actually run — enqueueing alone only registers the job.

    ``task`` must be a module-level, importable callable (RQ pickles it by
    reference, not by value) accepting a single ``str`` job id argument. See
    ``app.workers.rq_tasks`` for the functions used by this app.
    """

    def __init__(
        self,
        *,
        redis_url: str,
        queue_name: str,
        task: Callable[[str], None],
        max_retries: int = 3,
        retry_intervals: list[int] | None = None,
        connection=None,
    ) -> None:
        from rq import Queue
        from rq.job import Retry

        if connection is None:
            import redis as redis_lib

            connection = redis_lib.Redis.from_url(redis_url)
        self._connection = connection
        self._queue = Queue(queue_name, connection=self._connection)
        self._task = task
        self._retry = Retry(max=max_retries, interval=retry_intervals or [10, 30, 60])

    async def enqueue(
        self, job_id: uuid.UUID, *, idempotency_key: str | None = None
    ) -> None:
        from rq.job import Job

        rq_job_id = idempotency_key or str(job_id)
        if Job.exists(rq_job_id, connection=self._connection):
            return  # already enqueued by this or another replica — no duplicate
        self._queue.enqueue(
            self._task,
            str(job_id),
            job_id=rq_job_id,
            retry=self._retry,
            meta={"idempotency_key": idempotency_key, "enqueued_at": datetime.now(UTC).isoformat()},
        )

    async def cancel(self, job_id: uuid.UUID) -> None:
        from rq.job import Job

        rq_job_id = str(job_id)
        try:
            job = Job.fetch(rq_job_id, connection=self._connection)
        except Exception:
            return
        if job.get_status() in ("queued", "scheduled", "deferred"):
            job.cancel()

    async def get_status(self, job_id: uuid.UUID) -> JobQueueStatus:
        from rq.job import Job

        try:
            job = Job.fetch(str(job_id), connection=self._connection)
        except Exception:
            return JobQueueStatus(
                job_id=job_id, state="unknown", attempt=1, idempotency_key=None, next_retry_at=None
            )
        rq_state = job.get_status(refresh=True) or "unknown"
        attempt = max(1, self._retry.max - (job.retries_left or 0) + 1) if job.retries_left is not None else 1
        return JobQueueStatus(
            job_id=job_id,
            state=_RQ_STATE_MAP.get(rq_state, "unknown"),
            attempt=attempt,
            idempotency_key=(job.meta or {}).get("idempotency_key"),
            next_retry_at=None,
        )


def get_job_queue(
    *, queue_name: str, task: Callable[[str], None], inline_runner
) -> JobQueue:
    """Factory: returns the backend selected by ``settings.queue_backend``.

    ``task`` is the RQ-importable sync wrapper (used only for the redis
    backend); ``inline_runner`` is the async coroutine function used only
    for the inline backend. Callers provide both because the two backends
    have different calling conventions (sync-by-reference vs. async).
    """
    if settings.queue_backend == "redis" and settings.redis_url:
        return RedisJobQueue(redis_url=settings.redis_url, queue_name=queue_name, task=task)
    return InlineJobQueue(inline_runner)
