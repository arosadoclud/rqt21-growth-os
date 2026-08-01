from __future__ import annotations

import uuid
from collections.abc import Generator
from dataclasses import dataclass

import jwt
from fastapi import Cookie, Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import decode_access_token
from app.models.membership import Membership, Role, role_at_least
from app.models.user import User

ACCESS_COOKIE = "rqt_access"
REFRESH_COOKIE = "rqt_refresh"


def get_session() -> Generator[Session, None, None]:
    yield from get_db()


def _unauthorized(detail: str = "not authenticated") -> HTTPException:
    return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail)


def current_user(
    db: Session = Depends(get_session),
    rqt_access: str | None = Cookie(default=None),
    authorization: str | None = Header(default=None),
) -> User:
    token = rqt_access
    if token is None and authorization:
        parts = authorization.split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            token = parts[1]
    if not token:
        raise _unauthorized()
    try:
        payload = decode_access_token(token)
    except jwt.ExpiredSignatureError:
        raise _unauthorized("token expired") from None
    except jwt.PyJWTError:
        raise _unauthorized("invalid token") from None

    user_id = payload.get("sub")
    if not user_id:
        raise _unauthorized("invalid token payload")
    try:
        uid = uuid.UUID(user_id)
    except (TypeError, ValueError):
        raise _unauthorized("invalid token payload") from None

    user = db.get(User, uid)
    if user is None or not user.is_active:
        raise _unauthorized("user not found or inactive")
    return user


@dataclass
class OrgContext:
    organization_id: uuid.UUID
    membership: Membership


def current_org(
    x_organization_id: str | None = Header(default=None),
    user: User = Depends(current_user),
    db: Session = Depends(get_session),
) -> OrgContext:
    if not x_organization_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="missing X-Organization-Id header",
        )
    try:
        org_id = uuid.UUID(x_organization_id)
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="invalid organization id",
        ) from None

    membership = db.execute(
        select(Membership).where(
            Membership.user_id == user.id,
            Membership.organization_id == org_id,
        )
    ).scalar_one_or_none()
    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="not a member of this organization",
        )
    return OrgContext(organization_id=org_id, membership=membership)


def require_role(minimum: Role):
    def _dep(org: OrgContext = Depends(current_org)) -> OrgContext:
        if not role_at_least(org.membership.role, minimum):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"role {minimum.value} required",
            )
        return org

    return _dep


def require_growth_write(org: OrgContext = Depends(current_org)) -> OrgContext:
    """Write access to Phase 2 growth domains: OWNER, ADMIN, MARKETER."""
    if org.membership.role not in (Role.OWNER, Role.ADMIN, Role.MARKETER):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="OWNER, ADMIN or MARKETER required",
        )
    return org


# Phase 3 gates
def require_editorial_write(org: OrgContext = Depends(current_org)) -> OrgContext:
    if org.membership.role not in (Role.OWNER, Role.ADMIN, Role.MARKETER):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="editorial write requires OWNER, ADMIN or MARKETER",
        )
    return org


def require_content_approval(org: OrgContext = Depends(current_org)) -> OrgContext:
    if org.membership.role not in (Role.OWNER, Role.ADMIN):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="content approval requires OWNER or ADMIN",
        )
    return org


def require_lead_write(org: OrgContext = Depends(current_org)) -> OrgContext:
    if org.membership.role not in (Role.OWNER, Role.ADMIN, Role.SALES, Role.MARKETER):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="lead write requires OWNER, ADMIN, SALES or MARKETER",
        )
    return org


def require_lead_export(org: OrgContext = Depends(current_org)) -> OrgContext:
    if org.membership.role not in (Role.OWNER, Role.ADMIN, Role.SALES):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="lead export requires OWNER, ADMIN or SALES",
        )
    return org


def require_ai_generate(org: OrgContext = Depends(current_org)) -> OrgContext:
    if org.membership.role not in (Role.OWNER, Role.ADMIN, Role.MARKETER):
        raise HTTPException(
            status_code=403, detail="AI generation requires OWNER, ADMIN or MARKETER"
        )
    return org


def require_ai_review(org: OrgContext = Depends(current_org)) -> OrgContext:
    return require_ai_generate(org)


def require_ai_usage_read(org: OrgContext = Depends(current_org)) -> OrgContext:
    if org.membership.role not in (Role.OWNER, Role.ADMIN):
        raise HTTPException(status_code=403, detail="AI usage requires OWNER or ADMIN")
    return org


def require_public_source_write(org: OrgContext = Depends(current_org)) -> OrgContext:
    if org.membership.role not in (Role.OWNER, Role.ADMIN, Role.MARKETER):
        raise HTTPException(
            status_code=403,
            detail="public lead source write requires OWNER, ADMIN or MARKETER",
        )
    return org


# Phase 5 gates
def require_asset_write(org: OrgContext = Depends(current_org)) -> OrgContext:
    if org.membership.role not in (Role.OWNER, Role.ADMIN, Role.MARKETER):
        raise HTTPException(
            status_code=403, detail="asset write requires OWNER, ADMIN or MARKETER"
        )
    return org


def require_connection_admin(org: OrgContext = Depends(current_org)) -> OrgContext:
    if org.membership.role not in (Role.OWNER, Role.ADMIN):
        raise HTTPException(
            status_code=403, detail="connection admin requires OWNER or ADMIN"
        )
    return org


def require_publication_prepare(org: OrgContext = Depends(current_org)) -> OrgContext:
    if org.membership.role not in (Role.OWNER, Role.ADMIN, Role.MARKETER):
        raise HTTPException(
            status_code=403,
            detail="preparing a publication requires OWNER, ADMIN or MARKETER",
        )
    return org


def require_publication_approve(org: OrgContext = Depends(current_org)) -> OrgContext:
    if org.membership.role not in (Role.OWNER, Role.ADMIN):
        raise HTTPException(
            status_code=403,
            detail="authorizing automatic publication requires OWNER or ADMIN",
        )
    return org


def require_publication_execute(org: OrgContext = Depends(current_org)) -> OrgContext:
    """Manual publish/mark-published: same roles as preparing one."""
    if org.membership.role not in (Role.OWNER, Role.ADMIN, Role.MARKETER):
        raise HTTPException(
            status_code=403,
            detail="publishing requires OWNER, ADMIN or MARKETER",
        )
    return org


def require_automation_write(org: OrgContext = Depends(current_org)) -> OrgContext:
    if org.membership.role not in (Role.OWNER, Role.ADMIN):
        raise HTTPException(
            status_code=403, detail="automation write requires OWNER or ADMIN"
        )
    return org


def require_headline_admin(org: OrgContext = Depends(current_org)) -> OrgContext:
    """Configuring the Headline auto-cycle controls whether the org posts
    to a real social account unattended — same OWNER/ADMIN bar as
    connection_admin, not the lighter ai_generate bar used for one-off
    manual generations."""
    if org.membership.role not in (Role.OWNER, Role.ADMIN):
        raise HTTPException(
            status_code=403, detail="headline configuration requires OWNER or ADMIN"
        )
    return org
