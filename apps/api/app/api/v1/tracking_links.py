from __future__ import annotations

import uuid
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import audit
from app.core.config import settings
from app.deps import OrgContext, current_org, get_session, require_growth_write
from app.models.brand import Brand
from app.models.campaign import Campaign
from app.models.content import ContentItem
from app.models.product import Product
from app.models.tracking import TrackingLink
from app.schemas.growth import (
    TrackingLinkCreate,
    TrackingLinkRead,
    TrackingLinkUpdate,
)
from app.utils.public_id import make as make_public_id
from app.utils.short_code import generate as generate_short_code

router = APIRouter(prefix="/tracking-links", tags=["tracking-links"])


def _build_final_url(link: TrackingLink) -> str:
    """Compose destination + UTM into the canonical outgoing URL."""
    parsed = urlparse(link.destination_url)
    existing = dict(parse_qsl(parsed.query, keep_blank_values=True))
    utm = {
        "utm_source": link.utm_source,
        "utm_medium": link.utm_medium,
        "utm_campaign": link.utm_campaign,
        "utm_content": link.utm_content,
        "utm_term": link.utm_term,
    }
    for k, v in utm.items():
        if v:
            existing[k] = v
    query = urlencode(existing, doseq=True)
    return urlunparse(parsed._replace(query=query))


def _serialize(link: TrackingLink) -> TrackingLinkRead:
    return TrackingLinkRead(
        id=link.id,
        public_id=link.public_id,
        brand_id=link.brand_id,
        product_id=link.product_id,
        campaign_id=link.campaign_id,
        content_id=link.content_id,
        short_code=link.short_code,
        short_url=f"{settings.tracking_base_url.rstrip('/')}/r/{link.short_code}",
        final_url=_build_final_url(link),
        destination_url=link.destination_url,
        utm_source=link.utm_source,
        utm_medium=link.utm_medium,
        utm_campaign=link.utm_campaign,
        utm_content=link.utm_content,
        utm_term=link.utm_term,
        is_active=link.is_active,
        expires_at=link.expires_at,
        created_at=link.created_at,
        updated_at=link.updated_at,
    )


def _get_or_404(db: Session, org_id: uuid.UUID, link_id: uuid.UUID) -> TrackingLink:
    link = db.execute(
        select(TrackingLink).where(
            TrackingLink.id == link_id, TrackingLink.organization_id == org_id
        )
    ).scalar_one_or_none()
    if link is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="tracking link not found"
        )
    return link


def _validate_fks(
    db: Session,
    org_id: uuid.UUID,
    brand_id: uuid.UUID,
    product_id: uuid.UUID | None,
    campaign_id: uuid.UUID | None,
    content_id: uuid.UUID | None,
) -> None:
    checks: list[tuple[type, uuid.UUID | None, str]] = [
        (Brand, brand_id, "brand"),
        (Product, product_id, "product"),
        (Campaign, campaign_id, "campaign"),
        (ContentItem, content_id, "content"),
    ]
    for model, val, label in checks:
        if val is None:
            continue
        row = db.execute(
            select(model.id).where(model.id == val, model.organization_id == org_id)
        ).scalar_one_or_none()
        if row is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"{label} not found in organization",
            )


def _fresh_short_code(db: Session, attempts: int = 6) -> str:
    for _ in range(attempts):
        code = generate_short_code()
        exists = db.execute(
            select(TrackingLink.id).where(TrackingLink.short_code == code)
        ).scalar_one_or_none()
        if exists is None:
            return code
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="could not allocate a unique short code",
    )


@router.get("", response_model=list[TrackingLinkRead])
def list_tracking_links(
    campaign_id: uuid.UUID | None = Query(default=None),
    content_id: uuid.UUID | None = Query(default=None),
    is_active: bool | None = Query(default=None),
    org: OrgContext = Depends(current_org),
    db: Session = Depends(get_session),
) -> list[TrackingLinkRead]:
    stmt = (
        select(TrackingLink)
        .where(TrackingLink.organization_id == org.organization_id)
        .order_by(TrackingLink.created_at.desc())
    )
    if campaign_id:
        stmt = stmt.where(TrackingLink.campaign_id == campaign_id)
    if content_id:
        stmt = stmt.where(TrackingLink.content_id == content_id)
    if is_active is not None:
        stmt = stmt.where(TrackingLink.is_active.is_(is_active))
    return [_serialize(link) for link in db.execute(stmt).scalars().all()]


@router.post("", response_model=TrackingLinkRead, status_code=status.HTTP_201_CREATED)
def create_tracking_link(
    payload: TrackingLinkCreate,
    request: Request,
    org: OrgContext = Depends(require_growth_write),
    db: Session = Depends(get_session),
) -> TrackingLinkRead:
    _validate_fks(
        db,
        org.organization_id,
        payload.brand_id,
        payload.product_id,
        payload.campaign_id,
        payload.content_id,
    )
    link = TrackingLink(
        organization_id=org.organization_id,
        brand_id=payload.brand_id,
        product_id=payload.product_id,
        campaign_id=payload.campaign_id,
        content_id=payload.content_id,
        public_id=make_public_id("tl"),
        short_code=_fresh_short_code(db),
        destination_url=str(payload.destination_url),
        utm_source=payload.utm_source,
        utm_medium=payload.utm_medium,
        utm_campaign=payload.utm_campaign,
        utm_content=payload.utm_content,
        utm_term=payload.utm_term,
        expires_at=payload.expires_at,
    )
    db.add(link)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="short code collision"
        ) from None
    audit.record(
        db,
        action="tracking_link.created",
        organization_id=org.organization_id,
        target_type="tracking_link",
        target_id=link.id,
        payload={"short_code": link.short_code, "public_id": link.public_id},
        request=request,
    )
    db.commit()
    db.refresh(link)
    return _serialize(link)


@router.get("/{link_id}", response_model=TrackingLinkRead)
def get_tracking_link(
    link_id: uuid.UUID,
    org: OrgContext = Depends(current_org),
    db: Session = Depends(get_session),
) -> TrackingLinkRead:
    return _serialize(_get_or_404(db, org.organization_id, link_id))


@router.patch("/{link_id}", response_model=TrackingLinkRead)
def update_tracking_link(
    link_id: uuid.UUID,
    payload: TrackingLinkUpdate,
    request: Request,
    org: OrgContext = Depends(require_growth_write),
    db: Session = Depends(get_session),
) -> TrackingLinkRead:
    link = _get_or_404(db, org.organization_id, link_id)
    data = payload.model_dump(exclude_unset=True)
    if "destination_url" in data and data["destination_url"] is not None:
        data["destination_url"] = str(data["destination_url"])
    for k, v in data.items():
        setattr(link, k, v)
    db.flush()
    audit.record(
        db,
        action="tracking_link.updated",
        organization_id=org.organization_id,
        target_type="tracking_link",
        target_id=link.id,
        payload={"fields": list(data.keys())},
        request=request,
    )
    db.commit()
    db.refresh(link)
    return _serialize(link)


@router.post("/{link_id}/regenerate-code", response_model=TrackingLinkRead)
def regenerate_code(
    link_id: uuid.UUID,
    request: Request,
    org: OrgContext = Depends(require_growth_write),
    db: Session = Depends(get_session),
) -> TrackingLinkRead:
    link = _get_or_404(db, org.organization_id, link_id)
    old = link.short_code
    link.short_code = _fresh_short_code(db)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="short code collision"
        ) from None
    audit.record(
        db,
        action="tracking_link.code_regenerated",
        organization_id=org.organization_id,
        target_type="tracking_link",
        target_id=link.id,
        payload={"old_short_code": old, "new_short_code": link.short_code},
        request=request,
    )
    db.commit()
    db.refresh(link)
    return _serialize(link)
