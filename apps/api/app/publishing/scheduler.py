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

import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

from app.core.config import settings


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


class RedisScheduler:
    """Same bookkeeping role as InMemoryScheduler, but shared across
    replicas via a Redis hash — so "what did we tell the scheduler to run"
    is observable from any process, not just the one that called
    schedule(). Still not the source of truth for due work (that stays in
    Postgres, read directly by app.workers.publish_due); this only makes
    the bookkeeping itself durable and shared instead of process-local.
    """

    _HASH_KEY = "rqt21:scheduler:tasks"

    def __init__(self, connection) -> None:
        self._connection = connection

    @staticmethod
    def _field(task_type: str, resource_id: uuid.UUID) -> str:
        return f"{task_type}:{resource_id}"

    async def schedule(self, task_type: str, resource_id: uuid.UUID, run_at: datetime) -> None:
        field = self._field(task_type, resource_id)
        payload = json.dumps({"run_at": run_at.astimezone(UTC).isoformat()})
        self._connection.hset(self._HASH_KEY, field, payload)

    async def cancel(self, task_type: str, resource_id: uuid.UUID) -> None:
        self._connection.hdel(self._HASH_KEY, self._field(task_type, resource_id))

    def is_scheduled(self, task_type: str, resource_id: uuid.UUID) -> bool:
        return bool(self._connection.hexists(self._HASH_KEY, self._field(task_type, resource_id)))


def get_scheduler(connection=None) -> Scheduler:
    """Factory mirroring app.ai.queue.get_job_queue: returns the backend
    selected by settings.scheduler_backend, defaulting to the in-memory
    implementation used since Phase 5."""
    if settings.scheduler_backend == "redis" and settings.redis_url:
        if connection is None:
            import redis as redis_lib

            connection = redis_lib.Redis.from_url(settings.redis_url)
        return RedisScheduler(connection)
    return InMemoryScheduler()
