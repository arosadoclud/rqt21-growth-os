from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import audit
from app.deps import OrgContext, current_org, current_user, get_session, require_editorial_write
from app.models.ai import BrandVoiceProfile
from app.models.brand import Brand
from app.models.user import User
from app.schemas.ai import BrandVoiceRead, BrandVoiceWrite
from app.utils.public_id import make as make_public_id

router = APIRouter(prefix="/brand-voice", tags=["brand-voice"])


def _brand_or_404(db: Session, org_id: uuid.UUID, brand_id: uuid.UUID) -> Brand:
    b = db.execute(
        select(Brand).where(Brand.id == brand_id, Brand.organization_id == org_id)
    ).scalar_one_or_none()
    if b is None:
        raise HTTPException(status_code=404, detail="brand not found")
    return b


@router.get("/{brand_id}", response_model=BrandVoiceRead)
def get_brand_voice(
    brand_id: uuid.UUID,
    org: OrgContext = Depends(current_org),
    db: Session = Depends(get_session),
) -> BrandVoiceRead:
    _brand_or_404(db, org.organization_id, brand_id)
    row = db.execute(
        select(BrandVoiceProfile).where(
            BrandVoiceProfile.organization_id == org.organization_id,
            BrandVoiceProfile.brand_id == brand_id,
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="no brand voice profile for this brand")
    return BrandVoiceRead.model_validate(row)


@router.put("/{brand_id}", response_model=BrandVoiceRead)
def upsert_brand_voice(
    brand_id: uuid.UUID,
    payload: BrandVoiceWrite,
    request: Request,
    user: User = Depends(current_user),
    org: OrgContext = Depends(require_editorial_write),
    db: Session = Depends(get_session),
) -> BrandVoiceRead:
    _brand_or_404(db, org.organization_id, brand_id)
    row = db.execute(
        select(BrandVoiceProfile).where(
            BrandVoiceProfile.organization_id == org.organization_id,
            BrandVoiceProfile.brand_id == brand_id,
        )
    ).scalar_one_or_none()

    data = payload.model_dump(exclude={"brand_id"})
    created = row is None
    if row is None:
        row = BrandVoiceProfile(
            organization_id=org.organization_id,
            public_id=make_public_id("bvp"),
            brand_id=brand_id,
            **data,
        )
        db.add(row)
    else:
        for k, v in data.items():
            setattr(row, k, v)
    db.flush()

    audit.record(
        db,
        action="brand_voice.created" if created else "brand_voice.updated",
        actor_user_id=user.id,
        organization_id=org.organization_id,
        target_type="brand_voice",
        target_id=row.id,
        payload={"brand_id": str(brand_id)},
        request=request,
    )
    db.commit()
    db.refresh(row)
    return BrandVoiceRead.model_validate(row)
