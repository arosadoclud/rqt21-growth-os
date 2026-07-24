from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import audit, rate_limit
from app.cookies import clear_auth_cookies, set_access_cookie, set_refresh_cookie
from app.core.config import settings
from app.core.security import (
    create_access_token,
    generate_refresh_token,
    hash_refresh_token,
    verify_password,
)
from app.csrf import generate_csrf_token, set_csrf_cookie
from app.deps import REFRESH_COOKIE, get_session
from app.models.membership import Membership
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.schemas.auth import LoginRequest, LoginResponse, OrganizationSummary, UserPublic

router = APIRouter(prefix="/auth", tags=["auth"])


def _issue_refresh(
    db: Session,
    user: User,
    request: Request,
    *,
    family_id: uuid.UUID,
    replaces: RefreshToken | None = None,
) -> str:
    raw, digest = generate_refresh_token()
    ua = request.headers.get("user-agent", "")[:500] or None
    ip = rate_limit.client_ip(request)
    row = RefreshToken(
        user_id=user.id,
        family_id=family_id,
        token_hash=digest,
        expires_at=datetime.now(UTC)
        + timedelta(seconds=settings.jwt_refresh_ttl_seconds),
        user_agent=ua,
        ip_address=ip,
    )
    db.add(row)
    db.flush()
    if replaces is not None:
        replaces.revoked_at = datetime.now(UTC)
        replaces.revoked_reason = "rotated"
        replaces.replaced_by = row.id
        db.flush()
    return raw


def _user_orgs(db: Session, user: User) -> list[OrganizationSummary]:
    memberships = db.execute(
        select(Membership).where(Membership.user_id == user.id)
    ).scalars().all()
    return [
        OrganizationSummary(
            id=m.organization.id,
            name=m.organization.name,
            slug=m.organization.slug,
            role=m.role,
        )
        for m in memberships
    ]


def _revoke_family(
    db: Session,
    family_id: uuid.UUID,
    *,
    reason: str,
    reuse_hit: RefreshToken | None = None,
) -> int:
    tokens = db.execute(
        select(RefreshToken).where(RefreshToken.family_id == family_id)
    ).scalars().all()
    now = datetime.now(UTC)
    count = 0
    for t in tokens:
        if t.revoked_at is None:
            t.revoked_at = now
            t.revoked_reason = reason
            count += 1
    if reuse_hit is not None:
        reuse_hit.reuse_detected_at = now
    db.flush()
    return count


@router.post("/login", response_model=LoginResponse)
def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_session),
) -> LoginResponse:
    rate_limit.check_login(request, email=payload.email)

    user = db.execute(
        select(User).where(User.email == payload.email.lower())
    ).scalar_one_or_none()
    if user is None or not user.is_active or not verify_password(
        payload.password, user.password_hash
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid credentials",
        )

    access, _ = create_access_token(user_id=str(user.id))
    family_id = uuid.uuid4()
    refresh = _issue_refresh(db, user, request, family_id=family_id)
    csrf = generate_csrf_token()

    audit.record(
        db,
        action="auth.login",
        actor_user_id=user.id,
        target_type="user",
        target_id=user.id,
        request=request,
    )
    db.commit()
    set_access_cookie(response, access)
    set_refresh_cookie(response, refresh)
    set_csrf_cookie(response, csrf)
    return LoginResponse(
        user=UserPublic.model_validate(user), organizations=_user_orgs(db, user)
    )


@router.post("/refresh", response_model=LoginResponse)
def refresh(
    request: Request,
    response: Response,
    db: Session = Depends(get_session),
    rqt_refresh: str | None = Cookie(default=None),
) -> LoginResponse:
    rate_limit.check_refresh(request)

    if not rqt_refresh:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="missing refresh token"
        )
    digest = hash_refresh_token(rqt_refresh)
    row = db.execute(
        select(RefreshToken).where(RefreshToken.token_hash == digest)
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid refresh token"
        )

    # Reuse detection: this token was already rotated (revoked with a
    # successor) but is being presented again. Kill the whole family.
    if row.revoked_at is not None and row.revoked_reason == "rotated":
        _revoke_family(db, row.family_id, reason="reuse_detected", reuse_hit=row)
        audit.record(
            db,
            action="auth.refresh_reuse_detected",
            actor_user_id=row.user_id,
            target_type="refresh_family",
            target_id=row.family_id,
            payload={"token_id": str(row.id)},
            request=request,
        )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="refresh token reuse detected"
        )

    if row.revoked_at is not None or row.expires_at < datetime.now(UTC):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid refresh token"
        )

    user = db.get(User, row.user_id)
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="user inactive"
        )

    access, _ = create_access_token(user_id=str(user.id))
    new_refresh = _issue_refresh(
        db, user, request, family_id=row.family_id, replaces=row
    )
    csrf = generate_csrf_token()
    db.commit()
    set_access_cookie(response, access)
    set_refresh_cookie(response, new_refresh)
    set_csrf_cookie(response, csrf)
    return LoginResponse(
        user=UserPublic.model_validate(user), organizations=_user_orgs(db, user)
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    request: Request,
    response: Response,
    db: Session = Depends(get_session),
    rqt_refresh: str | None = Cookie(default=None, alias=REFRESH_COOKIE),
) -> None:
    user_id = None
    if rqt_refresh:
        digest = hash_refresh_token(rqt_refresh)
        row = db.execute(
            select(RefreshToken).where(RefreshToken.token_hash == digest)
        ).scalar_one_or_none()
        if row is not None:
            # Revoke the whole session family on logout.
            _revoke_family(db, row.family_id, reason="logout")
            user_id = row.user_id
    if user_id is not None:
        audit.record(
            db,
            action="auth.logout",
            actor_user_id=user_id,
            target_type="user",
            target_id=user_id,
            request=request,
        )
    db.commit()
    clear_auth_cookies(response)
    return None
