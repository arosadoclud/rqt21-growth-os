from __future__ import annotations

import uuid
from typing import Any

from fastapi import Request
from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog


def _client_ip(request: Request | None) -> str | None:
    if request is None:
        return None
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else None


def _user_agent(request: Request | None) -> str | None:
    if request is None:
        return None
    ua = request.headers.get("user-agent")
    return ua[:500] if ua else None


def record(
    db: Session,
    *,
    action: str,
    actor_user_id: uuid.UUID | None = None,
    organization_id: uuid.UUID | None = None,
    target_type: str | None = None,
    target_id: str | uuid.UUID | None = None,
    payload: dict[str, Any] | None = None,
    request: Request | None = None,
) -> AuditLog:
    entry = AuditLog(
        actor_user_id=actor_user_id,
        organization_id=organization_id,
        action=action,
        target_type=target_type,
        target_id=str(target_id) if target_id is not None else None,
        payload=payload or {},
        ip_address=_client_ip(request),
        user_agent=_user_agent(request),
    )
    db.add(entry)
    db.flush()
    return entry
