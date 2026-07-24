"""Scheduling abstraction for future-dated work (scheduled publications and
retries).

This is deliberately a different contract than app.ai.queue.JobQueue:
scheduling means "run this at time T", not "run this now". The actual
"finding due work and running it" logic lives in
app.workers.publish_due, which is meant to be invoked by an external
scheduler (cron, a Railway/Render scheduled job, etc) — see that module's
docstring. Nothing here uses asyncio.create_task() as a persistence
mechanism; a task recorded via ``schedule()`` is only durable if the
implementation persists it (InMemoryScheduler does NOT — see below), and the
worker's actual source of truth is always Publication.scheduled_for /
next_retry_at in the database, not this abstraction's own bookkeeping.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


class Scheduler(Protocol):
    async def schedule(self, task_type: str, resource_id: uuid.UUID, run_at: datetime) -> None: ...

    async def cancel(self, task_type: str, resource_id: uuid.UUID) -> None: ...


@dataclass(frozen=True)
class _ScheduledTask:
    task_type: str
    resource_id: uuid.UUID
    run_at: datetime


class InMemoryScheduler:
    """Process-local bookkeeping only — lost on restart. The real source of
    truth for "what's due" is always a DB column (Publication.scheduled_for
    or next_retry_at), queried directly by app.workers.publish_due. This
    class exists to satisfy the Scheduler Protocol in tests and to make the
    call sites (e.g. "I scheduled this") observable/assertable without
    hitting the DB again.
    """

    def __init__(self) -> None:
        self._tasks: dict[tuple[str, uuid.UUID], _ScheduledTask] = {}

    async def schedule(self, task_type: str, resource_id: uuid.UUID, run_at: datetime) -> None:
        self._tasks[(task_type, resource_id)] = _ScheduledTask(task_type, resource_id, run_at)

    async def cancel(self, task_type: str, resource_id: uuid.UUID) -> None:
        self._tasks.pop((task_type, resource_id), None)

    def is_scheduled(self, task_type: str, resource_id: uuid.UUID) -> bool:
        return (task_type, resource_id) in self._tasks
