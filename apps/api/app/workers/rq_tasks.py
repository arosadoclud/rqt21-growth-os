"""Module-level task wrappers importable by RQ workers.

RQ pickles enqueued jobs by (module path, function name) — the function
must be a plain module-level callable the worker process can import, not a
closure or bound method. Each wrapper here just bridges a sync RQ job call
into the existing async runner, in its own event loop.
"""

from __future__ import annotations

import asyncio
import uuid


def run_generation_job_task(job_id_str: str) -> None:
    from app.ai.runner import run_generation_job

    asyncio.run(run_generation_job(uuid.UUID(job_id_str)))
