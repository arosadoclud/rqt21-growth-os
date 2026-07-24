from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import audit
from app.deps import OrgContext, current_org, get_session, require_growth_write
from app.models.brand import Brand
from app.schemas.growth import BrandCreate, BrandRead, BrandUpdate
from app.utils.public_id import make as make_public_id

router = APIRouter(prefix="/brands", tags=["brands"])


def _serialize(b: Brand) -> BrandRead:
    return BrandRead.model_validate(b)


def _get_or_404(db: Session, org_id: uuid.UUID, brand_id: uuid.UUID) -> Brand:
    b = db.execute(
        select(Brand).where(Brand.id == brand_id, Brand.organization_id == org_id)
    ).scalar_one_or_none()
    if b is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="brand not found")
    return b


@router.get("", response_model=list[BrandRead])
def list_brands(
    is_active: bool | None = Query(default=None),
    org: OrgContext = Depends(current_org),
    db: Session = Depends(get_session),
) -> list[BrandRead]:
    stmt = select(Brand).where(Brand.organization_id == org.organization_id).order_by(Brand.created_at.desc())
    if is_active is not None:
        stmt = stmt.where(Brand.is_active.is_(is_active))
    rows = db.execute(stmt).scalars().all()
    return [_serialize(b) for b in rows]


@router.post("", response_model=BrandRead, status_code=status.HTTP_201_CREATED)
def create_brand(
    payload: BrandCreate,
    request: Request,
    org: OrgContext = Depends(require_growth_write),
    db: Session = Depends(get_session),
) -> BrandRead:
    b = Brand(
        organization_id=org.organization_id,
        public_id=make_public_id("br"),
        name=payload.name,
        slug=payload.slug,
        description=payload.description,
        website_url=str(payload.website_url) if payload.website_url else None,
    )
    db.add(b)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="slug already exists"
        ) from None
    audit.record(
        db,
        action="brand.created",
        actor_user_id=None,
        organization_id=org.organization_id,
        target_type="brand",
        target_id=b.id,
        payload={"slug": b.slug, "public_id": b.public_id},
        request=request,
    )
    db.commit()
    db.refresh(b)
    return _serialize(b)


@router.get("/{brand_id}", response_model=BrandRead)
def get_brand(
    brand_id: uuid.UUID,
    org: OrgContext = Depends(current_org),
    db: Session = Depends(get_session),
) -> BrandRead:
    return _serialize(_get_or_404(db, org.organization_id, brand_id))


@router.patch("/{brand_id}", response_model=BrandRead)
def update_brand(
    brand_id: uuid.UUID,
    payload: BrandUpdate,
    request: Request,
    org: OrgContext = Depends(require_growth_write),
    db: Session = Depends(get_session),
) -> BrandRead:
    b = _get_or_404(db, org.organization_id, brand_id)
    data = payload.model_dump(exclude_unset=True)
    if "website_url" in data and data["website_url"] is not None:
        data["website_url"] = str(data["website_url"])
    for k, v in data.items():
        setattr(b, k, v)
    db.flush()
    audit.record(
        db,
        action="brand.updated",
        organization_id=org.organization_id,
        target_type="brand",
        target_id=b.id,
        payload={"fields": list(data.keys())},
        request=request,
    )
    db.commit()
    db.refresh(b)
    return _serialize(b)


@router.delete("/{brand_id}", status_code=status.HTTP_204_NO_CONTENT)
def deactivate_brand(
    brand_id: uuid.UUID,
    request: Request,
    org: OrgContext = Depends(require_growth_write),
    db: Session = Depends(get_session),
) -> None:
    b = _get_or_404(db, org.organization_id, brand_id)
    if b.is_active:
        b.is_active = False
        db.flush()
        audit.record(
            db,
            action="brand.updated",
            organization_id=org.organization_id,
            target_type="brand",
            target_id=b.id,
            payload={"deactivated": True},
            request=request,
        )
    db.commit()
    return None
