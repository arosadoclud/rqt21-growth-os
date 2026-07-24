"""RQ worker entrypoint for the ``ai-generation`` queue (and any other
queue names enqueued via app.ai.queue.RedisJobQueue).

Usage::

    REDIS_URL=redis://localhost:6379/0 uv run python -m app.workers.rq_worker

Run one or more of these as separate long-lived processes/containers in
staging and production (see infra/docker-compose.staging.yml). Each worker
pulls jobs from Redis and executes app.workers.rq_tasks functions — the
worker process must have the same codebase/deps as the API so it can import
those task functions.
"""

from __future__ import annotations

import sys

from app.core.config import settings

QUEUE_NAMES = ["ai-generation"]


def main() -> None:
    if not settings.redis_url:
        print("REDIS_URL is not set — nothing to connect to.", file=sys.stderr)
        raise SystemExit(1)

    import redis as redis_lib
    from rq import Queue, Worker

    connection = redis_lib.Redis.from_url(settings.redis_url)
    queues = [Queue(name, connection=connection) for name in QUEUE_NAMES]
    worker = Worker(queues, connection=connection)
    print(f"[rq_worker] listening on {QUEUE_NAMES} via {settings.redis_url}")
    worker.work(with_scheduler=True)


if __name__ == "__main__":
    main()
