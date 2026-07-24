from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime, timedelta

import fakeredis
import pytest

from app.infra.redis_lock import RedisLock
from app.publishing.scheduler import InMemoryScheduler, RedisScheduler, get_scheduler


@pytest.fixture
def fake_conn():
    return fakeredis.FakeStrictRedis()


def test_redis_lock_mutual_exclusion(fake_conn):
    lock_a = RedisLock(fake_conn, "test-lock", ttl_seconds=30)
    lock_b = RedisLock(fake_conn, "test-lock", ttl_seconds=30)

    assert lock_a.acquire() is True
    assert lock_b.acquire() is False  # already held

    lock_a.release()
    assert lock_b.acquire() is True  # free after release


def test_redis_lock_release_only_own_token(fake_conn):
    lock_a = RedisLock(fake_conn, "shared", ttl_seconds=30)
    lock_a.acquire()

    # A lock object that never acquired must not be able to release someone
    # else's held lock (token mismatch guards this).
    imposter = RedisLock(fake_conn, "shared", ttl_seconds=30)
    imposter.acquired = True  # simulate a buggy caller forcing release
    imposter.release()

    assert fake_conn.get("lock:shared") is not None  # lock_a's lock survives


def test_redis_lock_context_manager(fake_conn):
    with RedisLock(fake_conn, "ctx-lock") as lock:
        assert lock.acquired is True
        assert fake_conn.exists("lock:ctx-lock")
    assert not fake_conn.exists("lock:ctx-lock")


def test_redis_scheduler_schedule_and_cancel(fake_conn):
    scheduler = RedisScheduler(fake_conn)
    resource_id = uuid.uuid4()
    run_at = datetime.now(UTC) + timedelta(days=1)

    asyncio.run(scheduler.schedule("publication", resource_id, run_at))
    assert scheduler.is_scheduled("publication", resource_id) is True

    asyncio.run(scheduler.cancel("publication", resource_id))
    assert scheduler.is_scheduled("publication", resource_id) is False


def test_scheduler_factory_defaults_to_memory(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "scheduler_backend", "memory")
    assert isinstance(get_scheduler(), InMemoryScheduler)


def test_scheduler_factory_uses_redis_when_configured(monkeypatch, fake_conn):
    from app.core.config import settings

    monkeypatch.setattr(settings, "scheduler_backend", "redis")
    monkeypatch.setattr(settings, "redis_url", "redis://localhost:6379/0")
    scheduler = get_scheduler(connection=fake_conn)
    assert isinstance(scheduler, RedisScheduler)


def test_worker_skips_sweep_when_lock_held(monkeypatch, fake_conn):
    """Simulate two worker instances racing: the second must see the sweep
    as already in progress and skip without touching any publication."""
    from app.core.config import settings
    from app.workers import publish_due

    monkeypatch.setattr(settings, "scheduler_backend", "redis")
    monkeypatch.setattr(settings, "redis_url", "redis://localhost:6379/0")
    monkeypatch.setattr("redis.Redis.from_url", lambda *a, **k: fake_conn)

    held_lock = RedisLock(fake_conn, "publish_due", ttl_seconds=60)
    assert held_lock.acquire() is True

    result = publish_due.run_once()
    assert result["skipped"] == -1
    assert result["scheduled_processed"] == 0
    assert result["retries_processed"] == 0

    held_lock.release()
