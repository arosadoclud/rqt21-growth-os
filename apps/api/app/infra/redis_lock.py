"""Minimal distributed mutex on top of Redis (SET NX PX + token-checked
release). Used to make cluster-wide "only one of you do this sweep right
now" guarantees — e.g. app.workers.publish_due when multiple worker/cron
instances point at the same Redis.

Not a general-purpose distributed lock library (no auto-extend, no
Redlock-across-multiple-Redis-nodes). A single Redis instance/cluster is
assumed, matching this project's actual deployment target.
"""

from __future__ import annotations

import uuid
from types import TracebackType


class RedisLock:
    """Usage::

        lock = RedisLock(connection, "publish_due", ttl_seconds=60)
        if lock.acquire():
            try:
                ...
            finally:
                lock.release()

    Or as a context manager — ``acquired`` tells the caller whether they
    actually hold the lock (a `with` block always runs; check the flag):

        with RedisLock(connection, "publish_due") as lock:
            if not lock.acquired:
                return  # someone else is already running this
            ...
    """

    def __init__(self, connection, key: str, *, ttl_seconds: int = 60) -> None:
        self._connection = connection
        self._key = f"lock:{key}"
        self._ttl_seconds = ttl_seconds
        self._token = uuid.uuid4().hex
        self.acquired = False

    def acquire(self) -> bool:
        ok = self._connection.set(self._key, self._token, nx=True, ex=self._ttl_seconds)
        self.acquired = bool(ok)
        return self.acquired

    def release(self) -> None:
        """Compare-and-delete via WATCH/MULTI so we never release a lock
        someone else re-acquired after ours expired (TTL race). Avoids Lua
        EVAL — not universally available across every Redis-compatible
        target this project might run against, and WATCH/MULTI covers the
        same guarantee for a single key."""
        if not self.acquired:
            return
        try:
            with self._connection.pipeline(transaction=True) as pipe:
                try:
                    pipe.watch(self._key)
                    current = pipe.get(self._key)
                    if isinstance(current, bytes):
                        current = current.decode()
                    if current != self._token:
                        pipe.unwatch()
                        return
                    pipe.multi()
                    pipe.delete(self._key)
                    pipe.execute()
                except Exception:
                    pipe.reset()
        finally:
            self.acquired = False

    def __enter__(self) -> RedisLock:
        self.acquire()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.release()
