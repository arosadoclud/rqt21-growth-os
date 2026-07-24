from __future__ import annotations

import uuid

import fakeredis
import pytest

from app.ai.queue import InlineJobQueue, RedisJobQueue, get_job_queue
from app.core.config import settings


def _noop_task(job_id_str: str) -> None:
    return None


@pytest.fixture
def fake_conn():
    return fakeredis.FakeStrictRedis()


def test_enqueue_registers_a_job(fake_conn):
    queue = RedisJobQueue(
        redis_url="redis://unused", queue_name="test-q", task=_noop_task, connection=fake_conn
    )
    job_id = uuid.uuid4()
    import asyncio

    asyncio.run(queue.enqueue(job_id))

    from rq.job import Job

    assert Job.exists(str(job_id), connection=fake_conn)


def test_enqueue_is_idempotent_by_key(fake_conn):
    queue = RedisJobQueue(
        redis_url="redis://unused", queue_name="test-q", task=_noop_task, connection=fake_conn
    )
    job_id = uuid.uuid4()
    import asyncio

    asyncio.run(queue.enqueue(job_id, idempotency_key="fixed-key-1"))
    asyncio.run(queue.enqueue(job_id, idempotency_key="fixed-key-1"))

    assert len(queue._queue.job_ids) == 1


def test_get_status_reports_queued(fake_conn):
    queue = RedisJobQueue(
        redis_url="redis://unused", queue_name="test-q", task=_noop_task, connection=fake_conn
    )
    job_id = uuid.uuid4()
    import asyncio

    asyncio.run(queue.enqueue(job_id))
    status = asyncio.run(queue.get_status(job_id))
    assert status.state == "queued"


def test_get_status_unknown_for_missing_job(fake_conn):
    queue = RedisJobQueue(
        redis_url="redis://unused", queue_name="test-q", task=_noop_task, connection=fake_conn
    )
    status_coro = queue.get_status(uuid.uuid4())
    import asyncio

    status = asyncio.run(status_coro)
    assert status.state == "unknown"


def test_cancel_removes_queued_job(fake_conn):
    queue = RedisJobQueue(
        redis_url="redis://unused", queue_name="test-q", task=_noop_task, connection=fake_conn
    )
    job_id = uuid.uuid4()
    import asyncio

    asyncio.run(queue.enqueue(job_id))
    asyncio.run(queue.cancel(job_id))

    from rq.job import Job

    job = Job.fetch(str(job_id), connection=fake_conn)
    assert job.get_status(refresh=True) in ("canceled", "stopped")


def test_factory_returns_inline_by_default(monkeypatch):
    monkeypatch.setattr(settings, "queue_backend", "inline")

    async def runner(job_id):
        return None

    q = get_job_queue(queue_name="x", task=_noop_task, inline_runner=runner)
    assert isinstance(q, InlineJobQueue)


def test_factory_returns_redis_when_configured(monkeypatch):
    monkeypatch.setattr(settings, "queue_backend", "redis")
    monkeypatch.setattr(settings, "redis_url", "redis://localhost:6379/0")

    async def runner(job_id):
        return None

    q = get_job_queue(queue_name="x", task=_noop_task, inline_runner=runner)
    assert isinstance(q, RedisJobQueue)


def test_factory_falls_back_to_inline_without_redis_url(monkeypatch):
    monkeypatch.setattr(settings, "queue_backend", "redis")
    monkeypatch.setattr(settings, "redis_url", "")

    async def runner(job_id):
        return None

    q = get_job_queue(queue_name="x", task=_noop_task, inline_runner=runner)
    assert isinstance(q, InlineJobQueue)
