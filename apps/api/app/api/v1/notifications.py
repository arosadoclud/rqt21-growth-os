from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import audit
from app.deps import OrgContext, current_org, current_user, get_session
from app.models.automation import Notification
from app.models.user import User
from app.schemas.automation import NotificationRead

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=list[NotificationRead])
def list_notifications(
    unread_only: bool = Query(default=False),
    user: User = Depends(current_user),
    org: OrgContext = Depends(current_org),
    db: Session = Depends(get_session),
) -> list[NotificationRead]:
    stmt = (
        select(Notification)
        .where(
            Notification.organization_id == org.organization_id,
            Notification.user_id == user.id,
        )
        .order_by(Notification.created_at.desc())
        .limit(100)
    )
    if unread_only:
        stmt = stmt.where(Notification.read_at.is_(None))
    return [NotificationRead.model_validate(n) for n in db.execute(stmt).scalars().all()]


@router.post("/{notification_id}/read", response_model=NotificationRead)
def mark_read(
    notification_id: uuid.UUID,
    request: Request,
    user: User = Depends(current_user),
    org: OrgContext = Depends(current_org),
    db: Session = Depends(get_session),
) -> NotificationRead:
    row = db.execute(
        select(Notification).where(
            Notification.id == notification_id,
            Notification.organization_id == org.organization_id,
            Notification.user_id == user.id,
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="notification not found")
    if row.read_at is None:
        row.read_at = datetime.now(UTC)
        db.flush()
        audit.record(
            db,
            action="notification.read",
            actor_user_id=user.id,
            organization_id=org.organization_id,
            target_type="notification",
            target_id=row.id,
            payload={},
            request=request,
        )
    db.commit()
    db.refresh(row)
    return NotificationRead.model_validate(row)
