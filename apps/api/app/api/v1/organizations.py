from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import audit
from app.core.security import hash_password
from app.deps import current_user, get_session, require_role
from app.models.membership import Membership, Role
from app.models.organization import Organization
from app.models.user import User
from app.schemas.organization import (
    MemberCreate,
    MemberRead,
    MemberUpdate,
    OrganizationCreate,
    OrganizationRead,
)

router = APIRouter(prefix="/organizations", tags=["organizations"])


def _serialize_member(m: Membership) -> MemberRead:
    return MemberRead(
        id=m.id,
        user_id=m.user.id,
        email=m.user.email,
        full_name=m.user.full_name,
        role=m.role,
    )


def _assert_member(db: Session, user: User, org_id: uuid.UUID) -> Membership:
    membership = db.execute(
        select(Membership).where(
            Membership.user_id == user.id, Membership.organization_id == org_id
        )
    ).scalar_one_or_none()
    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="not a member of this organization",
        )
    return membership


@router.get("", response_model=list[OrganizationRead])
def list_orgs(
    user: User = Depends(current_user),
    db: Session = Depends(get_session),
) -> list[OrganizationRead]:
    rows = db.execute(
        select(Organization)
        .join(Membership, Membership.organization_id == Organization.id)
        .where(Membership.user_id == user.id)
    ).scalars().all()
    return [OrganizationRead.model_validate(o) for o in rows]


@router.post("", response_model=OrganizationRead, status_code=status.HTTP_201_CREATED)
def create_org(
    payload: OrganizationCreate,
    request: Request,
    user: User = Depends(current_user),
    db: Session = Depends(get_session),
) -> OrganizationRead:
    org = Organization(name=payload.name, slug=payload.slug)
    db.add(org)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="slug already exists"
        ) from None
    membership = Membership(user_id=user.id, organization_id=org.id, role=Role.OWNER)
    db.add(membership)
    db.flush()
    audit.record(
        db,
        action="organization.create",
        actor_user_id=user.id,
        organization_id=org.id,
        target_type="organization",
        target_id=org.id,
        payload={"slug": org.slug, "name": org.name},
        request=request,
    )
    db.commit()
    return OrganizationRead.model_validate(org)


@router.get("/{org_id}", response_model=OrganizationRead)
def get_org(
    org_id: uuid.UUID,
    user: User = Depends(current_user),
    db: Session = Depends(get_session),
) -> OrganizationRead:
    _assert_member(db, user, org_id)
    org = db.get(Organization, org_id)
    if org is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="not found")
    return OrganizationRead.model_validate(org)


@router.get("/{org_id}/members", response_model=list[MemberRead])
def list_members(
    org_id: uuid.UUID,
    user: User = Depends(current_user),
    db: Session = Depends(get_session),
) -> list[MemberRead]:
    _assert_member(db, user, org_id)
    rows = db.execute(
        select(Membership).where(Membership.organization_id == org_id)
    ).scalars().all()
    return [_serialize_member(m) for m in rows]


@router.post(
    "/{org_id}/members",
    response_model=MemberRead,
    status_code=status.HTTP_201_CREATED,
)
def add_member(
    org_id: uuid.UUID,
    payload: MemberCreate,
    request: Request,
    user: User = Depends(current_user),
    db: Session = Depends(get_session),
) -> MemberRead:
    caller_membership = _assert_member(db, user, org_id)
    if caller_membership.role not in (Role.OWNER, Role.ADMIN):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="OWNER or ADMIN required",
        )
    if payload.role == Role.OWNER and caller_membership.role != Role.OWNER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="only OWNER can create OWNER members",
        )

    email = payload.email.lower()
    target = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
    created_new_user = False
    if target is None:
        target = User(
            email=email,
            full_name=payload.full_name,
            password_hash=hash_password(payload.password),
        )
        db.add(target)
        db.flush()
        created_new_user = True
        audit.record(
            db,
            action="user.create",
            actor_user_id=user.id,
            organization_id=org_id,
            target_type="user",
            target_id=target.id,
            payload={"email": email},
            request=request,
        )

    existing = db.execute(
        select(Membership).where(
            Membership.user_id == target.id,
            Membership.organization_id == org_id,
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="already a member"
        )

    membership = Membership(user_id=target.id, organization_id=org_id, role=payload.role)
    db.add(membership)
    db.flush()
    audit.record(
        db,
        action="membership.create",
        actor_user_id=user.id,
        organization_id=org_id,
        target_type="membership",
        target_id=membership.id,
        payload={"user_id": str(target.id), "role": payload.role.value, "new_user": created_new_user},
        request=request,
    )
    db.commit()
    db.refresh(membership)
    return _serialize_member(membership)


@router.patch("/{org_id}/members/{member_id}", response_model=MemberRead)
def update_member(
    org_id: uuid.UUID,
    member_id: uuid.UUID,
    payload: MemberUpdate,
    request: Request,
    user: User = Depends(current_user),
    db: Session = Depends(get_session),
) -> MemberRead:
    caller = _assert_member(db, user, org_id)
    if caller.role not in (Role.OWNER, Role.ADMIN):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="OWNER or ADMIN required",
        )
    membership = db.get(Membership, member_id)
    if membership is None or membership.organization_id != org_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="member not found")
    if payload.role == Role.OWNER and caller.role != Role.OWNER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="only OWNER can assign OWNER",
        )
    if membership.role == Role.OWNER and caller.role != Role.OWNER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="only OWNER can modify an OWNER",
        )
    if membership.role == Role.OWNER and payload.role != Role.OWNER:
        remaining_owners = db.execute(
            select(Membership).where(
                Membership.organization_id == org_id,
                Membership.role == Role.OWNER,
                Membership.id != membership.id,
            )
        ).scalars().all()
        if not remaining_owners:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="cannot demote the last OWNER",
            )

    old_role = membership.role
    membership.role = payload.role
    db.flush()
    audit.record(
        db,
        action="membership.role_change",
        actor_user_id=user.id,
        organization_id=org_id,
        target_type="membership",
        target_id=membership.id,
        payload={"from": old_role.value, "to": payload.role.value},
        request=request,
    )
    db.commit()
    db.refresh(membership)
    return _serialize_member(membership)


__all__ = ["router", "require_role"]
