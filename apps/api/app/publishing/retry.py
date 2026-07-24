"""Retry/backoff policy for failed publish attempts.

Centralized so nothing else computes a backoff delay independently. Backoff
is exponential with jitter, capped at PUBLISH_RETRY_MAX_SECONDS, and the
attempt counter is the single source of truth for whether the max has been
reached.
"""

from __future__ import annotations

import random
from datetime import UTC, datetime, timedelta

from app.core.config import settings


def is_recoverable(error_code: str) -> bool:
    """Validation errors and revoked connections are never retried —
    retrying them wastes attempts on something that cannot succeed without a
    human fixing the underlying cause first."""
    return error_code not in ("validation_error", "connection_revoked", "permanent_error")


def max_attempts_reached(attempt_count: int) -> bool:
    return attempt_count >= settings.publish_max_attempts


def next_retry_at(attempt_count: int, retry_after_seconds: int | None = None) -> datetime:
    """attempt_count is the count AFTER the failed attempt just recorded."""
    if retry_after_seconds is not None:
        delay = min(retry_after_seconds, settings.publish_retry_max_seconds)
    else:
        base = settings.publish_retry_base_seconds * (2 ** max(0, attempt_count - 1))
        delay = min(base, settings.publish_retry_max_seconds)
        jitter = random.uniform(0, delay * 0.2)  # noqa: S311 - non-cryptographic jitter
        delay = delay + jitter
    return datetime.now(UTC) + timedelta(seconds=delay)
