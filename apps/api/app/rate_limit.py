"""In-process sliding-window rate limiter.

Single-process only. If the API is later scaled horizontally, this should be
swapped for a shared backend (Redis). All state lives in module-level dicts
keyed by (bucket, subject) → deque[timestamps].
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass

from fastapi import HTTPException, Request

from app.core.config import settings


@dataclass(frozen=True)
class Rule:
    limit: int
    window_seconds: int


_hits: dict[tuple[str, str], deque[float]] = defaultdict(deque)
_lock = threading.Lock()


def reset() -> None:
    with _lock:
        _hits.clear()


def _check(bucket: str, subject: str, rule: Rule) -> None:
    if rule.limit <= 0 or not subject:
        return
    now = time.monotonic()
    key = (bucket, subject)
    with _lock:
        q = _hits[key]
        cutoff = now - rule.window_seconds
        while q and q[0] < cutoff:
            q.popleft()
        if len(q) >= rule.limit:
            retry_after = max(1, int(rule.window_seconds - (now - q[0])))
            raise HTTPException(
                status_code=429,
                detail="too many requests",
                headers={"Retry-After": str(retry_after)},
            )
        q.append(now)


def client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def check_login(request: Request, *, email: str | None) -> None:
    ip = client_ip(request)
    _check(
        "login:ip",
        ip,
        Rule(settings.rl_login_ip_limit, settings.rl_login_window_seconds),
    )
    if email:
        _check(
            "login:email",
            email.lower(),
            Rule(settings.rl_login_email_limit, settings.rl_login_window_seconds),
        )


def check_refresh(request: Request) -> None:
    ip = client_ip(request)
    _check(
        "refresh:ip",
        ip,
        Rule(settings.rl_refresh_ip_limit, settings.rl_refresh_window_seconds),
    )


def check(bucket: str, subject: str, limit: int, window_seconds: int) -> None:
    """Public generic entry point. Backends: in-memory now; the module contract
    stays the same when we swap this out for Redis later."""
    _check(bucket, subject, Rule(limit, window_seconds))


def check_public_lead(request: Request) -> None:
    check(
        "public_lead:ip",
        client_ip(request),
        settings.public_lead_rate_limit,
        settings.public_lead_window_seconds,
    )


def check_public_redirect(request: Request) -> None:
    check(
        "public_redirect:ip",
        client_ip(request),
        settings.public_redirect_rate_limit,
        settings.public_redirect_window_seconds,
    )
