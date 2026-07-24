from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.deps import get_session

router = APIRouter(tags=["health"])


def _check_redis() -> tuple[bool, str | None]:
    """Only checked when the app is actually configured to depend on
    Redis (queue or scheduler backend) — an unconfigured REDIS_URL is not
    a degraded state for a deployment that doesn't use it."""
    if not settings.redis_url or (
        settings.queue_backend != "redis" and settings.scheduler_backend != "redis"
    ):
        return True, None
    try:
        import redis as redis_lib

        redis_lib.Redis.from_url(settings.redis_url, socket_connect_timeout=2).ping()
        return True, None
    except Exception as exc:  # pragma: no cover - narrow error surface
        return False, str(exc)[:200]


def _latest_revision() -> str | None:
    """Return the newest revision id declared in the alembic versions dir."""
    versions_dir = Path(__file__).resolve().parents[3] / "alembic" / "versions"
    latest_mtime = -1.0
    latest_id: str | None = None
    for f in versions_dir.glob("*.py"):
        if f.stat().st_mtime > latest_mtime:
            latest_mtime = f.stat().st_mtime
            latest_id = f.stem
    return latest_id


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ready")
def ready(db: Session = Depends(get_session)) -> dict[str, object]:
    db_ok = True
    db_error: str | None = None
    current_rev: str | None = None
    latest_rev = _latest_revision()
    migrations_ok = True

    try:
        db.execute(text("SELECT 1"))
        row = db.execute(text("SELECT version_num FROM alembic_version LIMIT 1"))
        result = row.scalar()
        current_rev = str(result) if result else None
    except Exception as exc:  # pragma: no cover - narrow error surface
        db_ok = False
        db_error = str(exc)[:200]
        migrations_ok = False

    if db_ok and latest_rev and current_rev:
        # Compare by prefix so "0002_refresh_family" matches whichever the file was named.
        migrations_ok = current_rev == latest_rev or latest_rev.startswith(current_rev)

    redis_ok, redis_error = _check_redis()

    ready_flag = db_ok and migrations_ok and redis_ok
    return {
        "status": "ok" if ready_flag else "degraded",
        "db": {"ok": db_ok, "error": db_error},
        "migrations": {
            "ok": migrations_ok,
            "current": current_rev,
            "latest": latest_rev,
        },
        "redis": {"ok": redis_ok, "error": redis_error},
    }
