"""Job execution queue abstraction.

``JobQueue`` is the seam the rest of the app depends on for background-ish
execution. ``InlineJobQueue`` executes synchronously in-process — correct for
a single-replica deployment and for tests, but NOT a substitute for a real
distributed queue once the API runs multiple replicas or execution needs to
survive a process restart. Swapping to Redis/RQ, Dramatiq, or Celery means
implementing this same Protocol against that backend; nothing above this
layer needs to change.

This module intentionally stays generic (job_id + a caller-supplied runner),
so both GenerationJob (Phase 4) and, if ever needed, other job-shaped work
can share it. Publication scheduling (Phase 5) uses the separate
``app.publishing.scheduler.Scheduler`` Protocol instead, because scheduling a
task for a FUTURE time is a different contract than "run this now" — see
that module's docstring.
"""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


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
    RUNNING with no automatic recovery. Acceptable for the current MVP scale;
    documented explicitly so it isn't mistaken for production-grade queuing.

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
