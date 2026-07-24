from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import audit
from app.deps import OrgContext, current_org, get_session, require_growth_write
from app.models.brand import Brand
from app.models.campaign import Campaign
from app.models.enums import CampaignStatus
from app.models.product import Product
from app.schemas.growth import CampaignCreate, CampaignRead, CampaignUpdate
from app.utils.public_id import make as make_public_id

router = APIRouter(prefix="/campaigns", tags=["campaigns"])


def _serialize(c: Campaign) -> CampaignRead:
    return CampaignRead.model_validate(c)


def _get_or_404(db: Session, org_id: uuid.UUID, campaign_id: uuid.UUID) -> Campaign:
    c = db.execute(
        select(Campaign).where(
            Campaign.id == campaign_id, Campaign.organization_id == org_id
        )
    ).scalar_one_or_none()
    if c is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="campaign not found"
        )
    return c


def _validate_fks(
    db: Session,
    org_id: uuid.UUID,
    brand_id: uuid.UUID,
    product_id: uuid.UUID | None,
) -> None:
    b = db.execute(
        select(Brand.id).where(Brand.id == brand_id, Brand.organization_id == org_id)
    ).scalar_one_or_none()
    if b is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="brand not found in organization"
        )
    if product_id is not None:
        p = db.execute(
            select(Product.id).where(
                Product.id == product_id, Product.organization_id == org_id
            )
        ).scalar_one_or_none()
        if p is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="product not found in organization",
            )


@router.get("", response_model=list[CampaignRead])
def list_campaigns(
    brand_id: uuid.UUID | None = Query(default=None),
    status_filter: CampaignStatus | None = Query(default=None, alias="status"),
    org: OrgContext = Depends(current_org),
    db: Session = Depends(get_session),
) -> list[CampaignRead]:
    stmt = (
        select(Campaign)
        .where(Campaign.organization_id == org.organization_id)
        .order_by(Campaign.created_at.desc())
    )
    if brand_id:
        stmt = stmt.where(Campaign.brand_id == brand_id)
    if status_filter:
        stmt = stmt.where(Campaign.status == status_filter)
    return [_serialize(c) for c in db.execute(stmt).scalars().all()]


@router.post("", response_model=CampaignRead, status_code=status.HTTP_201_CREATED)
def create_campaign(
    payload: CampaignCreate,
    request: Request,
    org: OrgContext = Depends(require_growth_write),
    db: Session = Depends(get_session),
) -> CampaignRead:
    _validate_fks(db, org.organization_id, payload.brand_id, payload.product_id)
    c = Campaign(
        organization_id=org.organization_id,
        brand_id=payload.brand_id,
        product_id=payload.product_id,
        public_id=make_public_id("cm"),
        name=payload.name,
        slug=payload.slug,
        objective=payload.objective,
        platform=payload.platform,
        status=payload.status,
        starts_at=payload.starts_at,
        ends_at=payload.ends_at,
        budget=payload.budget,
    )
    db.add(c)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="slug already exists"
        ) from None
    audit.record(
        db,
        action="campaign.created",
        organization_id=org.organization_id,
        target_type="campaign",
        target_id=c.id,
        payload={"slug": c.slug, "public_id": c.public_id},
        request=request,
    )
    db.commit()
    db.refresh(c)
    return _serialize(c)


@router.get("/{campaign_id}", response_model=CampaignRead)
def get_campaign(
    campaign_id: uuid.UUID,
    org: OrgContext = Depends(current_org),
    db: Session = Depends(get_session),
) -> CampaignRead:
    return _serialize(_get_or_404(db, org.organization_id, campaign_id))


@router.patch("/{campaign_id}", response_model=CampaignRead)
def update_campaign(
    campaign_id: uuid.UUID,
    payload: CampaignUpdate,
    request: Request,
    org: OrgContext = Depends(require_growth_write),
    db: Session = Depends(get_session),
) -> CampaignRead:
    c = _get_or_404(db, org.organization_id, campaign_id)
    data = payload.model_dump(exclude_unset=True)
    if "product_id" in data and data["product_id"] is not None:
        _validate_fks(db, org.organization_id, c.brand_id, data["product_id"])
    for k, v in data.items():
        setattr(c, k, v)
    db.flush()
    audit.record(
        db,
        action="campaign.updated",
        organization_id=org.organization_id,
        target_type="campaign",
        target_id=c.id,
        payload={"fields": list(data.keys())},
        request=request,
    )
    db.commit()
    db.refresh(c)
    return _serialize(c)


@router.delete("/{campaign_id}", status_code=status.HTTP_204_NO_CONTENT)
def archive_campaign(
    campaign_id: uuid.UUID,
    request: Request,
    org: OrgContext = Depends(require_growth_write),
    db: Session = Depends(get_session),
) -> None:
    c = _get_or_404(db, org.organization_id, campaign_id)
    if c.status != CampaignStatus.ARCHIVED:
        c.status = CampaignStatus.ARCHIVED
        db.flush()
        audit.record(
            db,
            action="campaign.updated",
            organization_id=org.organization_id,
            target_type="campaign",
            target_id=c.id,
            payload={"archived": True},
            request=request,
        )
    db.commit()
    return None
