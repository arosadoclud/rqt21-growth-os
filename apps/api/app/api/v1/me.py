from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.deps import current_user, get_session
from app.models.membership import Membership
from app.models.user import User
from app.schemas.auth import MeResponse, OrganizationSummary, UserPublic

router = APIRouter(tags=["me"])


@router.get("/me", response_model=MeResponse)
def me(
    user: User = Depends(current_user),
    db: Session = Depends(get_session),
) -> MeResponse:
    memberships = db.execute(
        select(Membership).where(Membership.user_id == user.id)
    ).scalars().all()
    orgs = [
        OrganizationSummary(
            id=m.organization.id,
            name=m.organization.name,
            slug=m.organization.slug,
            role=m.role,
        )
        for m in memberships
    ]
    return MeResponse(user=UserPublic.model_validate(user), organizations=orgs)
