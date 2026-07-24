"""Internal notification helper — used by publications, assets, automations,
and generation-job flows to leave a persistent, pollable notification for a
user. No websockets/real-time delivery; the frontend polls
GET /api/v1/notifications on a manual refresh (see Phase 5 spec section 12).
"""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.models.automation import Notification
from app.models.enums import NotificationType
from app.utils.public_id import make as make_public_id


def notify(
    db: Session,
    *,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
    notification_type: NotificationType,
    title: str,
    message: str,
    resource_type: str | None = None,
    resource_public_id: str | None = None,
) -> Notification:
    row = Notification(
        public_id=make_public_id("nt"),
        organization_id=organization_id,
        user_id=user_id,
        notification_type=notification_type,
        title=title[:255],
        message=message[:1000],
        resource_type=resource_type,
        resource_public_id=resource_public_id,
    )
    db.add(row)
    db.flush()
    return row
