from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import audit
from app.deps import OrgContext, current_org, get_session, require_growth_write
from app.models.brand import Brand
from app.models.campaign import Campaign
from app.models.content import ContentItem
from app.models.enums import ContentStatus
from app.models.product import Product
from app.schemas.growth import (
    ContentCreate,
    ContentImport,
    ContentRead,
    ContentUpdate,
)
from app.utils.public_id import make as make_public_id

router = APIRouter(prefix="/content-items", tags=["content"])


def _serialize(c: ContentItem) -> ContentRead:
    return ContentRead.model_validate(c)


def _get_or_404(db: Session, org_id: uuid.UUID, content_id: uuid.UUID) -> ContentItem:
    c = db.execute(
        select(ContentItem).where(
            ContentItem.id == content_id, ContentItem.organization_id == org_id
        )
    ).scalar_one_or_none()
    if c is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="content not found"
        )
    return c


def _validate_fks(
    db: Session,
    org_id: uuid.UUID,
    brand_id: uuid.UUID,
    campaign_id: uuid.UUID | None,
    product_id: uuid.UUID | None,
) -> None:
    b = db.execute(
        select(Brand.id).where(Brand.id == brand_id, Brand.organization_id == org_id)
    ).scalar_one_or_none()
    if b is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="brand not found in organization"
        )
    if campaign_id is not None:
        c = db.execute(
            select(Campaign.id).where(
                Campaign.id == campaign_id, Campaign.organization_id == org_id
            )
        ).scalar_one_or_none()
        if c is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="campaign not found in organization",
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


@router.get("", response_model=list[ContentRead])
def list_content(
    campaign_id: uuid.UUID | None = Query(default=None),
    brand_id: uuid.UUID | None = Query(default=None),
    status_filter: ContentStatus | None = Query(default=None, alias="status"),
    org: OrgContext = Depends(current_org),
    db: Session = Depends(get_session),
) -> list[ContentRead]:
    stmt = (
        select(ContentItem)
        .where(ContentItem.organization_id == org.organization_id)
        .order_by(ContentItem.created_at.desc())
    )
    if campaign_id:
        stmt = stmt.where(ContentItem.campaign_id == campaign_id)
    if brand_id:
        stmt = stmt.where(ContentItem.brand_id == brand_id)
    if status_filter:
        stmt = stmt.where(ContentItem.status == status_filter)
    return [_serialize(c) for c in db.execute(stmt).scalars().all()]


@router.post("", response_model=ContentRead, status_code=status.HTTP_201_CREATED)
def create_content(
    payload: ContentCreate,
    request: Request,
    org: OrgContext = Depends(require_growth_write),
    db: Session = Depends(get_session),
) -> ContentRead:
    _validate_fks(
        db, org.organization_id, payload.brand_id, payload.campaign_id, payload.product_id
    )
    c = ContentItem(
        organization_id=org.organization_id,
        brand_id=payload.brand_id,
        campaign_id=payload.campaign_id,
        product_id=payload.product_id,
        public_id=make_public_id("ct"),
        external_id=payload.external_id,
        source_system=payload.source_system,
        platform=payload.platform,
        content_type=payload.content_type,
        title=payload.title,
        hook=payload.hook,
        caption=payload.caption,
        cta=payload.cta,
        media_url=str(payload.media_url) if payload.media_url else None,
        publication_url=str(payload.publication_url) if payload.publication_url else None,
        status=payload.status,
        published_at=payload.published_at,
    )
    db.add(c)
    db.flush()
    audit.record(
        db,
        action="content.created",
        organization_id=org.organization_id,
        target_type="content",
        target_id=c.id,
        payload={"public_id": c.public_id, "source_system": c.source_system.value},
        request=request,
    )
    db.commit()
    db.refresh(c)
    return _serialize(c)


@router.get("/{content_id}", response_model=ContentRead)
def get_content(
    content_id: uuid.UUID,
    org: OrgContext = Depends(current_org),
    db: Session = Depends(get_session),
) -> ContentRead:
    return _serialize(_get_or_404(db, org.organization_id, content_id))


@router.patch("/{content_id}", response_model=ContentRead)
def update_content(
    content_id: uuid.UUID,
    payload: ContentUpdate,
    request: Request,
    org: OrgContext = Depends(require_growth_write),
    db: Session = Depends(get_session),
) -> ContentRead:
    c = _get_or_404(db, org.organization_id, content_id)
    data = payload.model_dump(exclude_unset=True)
    for url_field in ("media_url", "publication_url"):
        if url_field in data and data[url_field] is not None:
            data[url_field] = str(data[url_field])
    if "campaign_id" in data or "product_id" in data:
        _validate_fks(
            db,
            org.organization_id,
            c.brand_id,
            data.get("campaign_id", c.campaign_id),
            data.get("product_id", c.product_id),
        )
    for k, v in data.items():
        setattr(c, k, v)
    db.flush()
    audit.record(
        db,
        action="content.updated",
        organization_id=org.organization_id,
        target_type="content",
        target_id=c.id,
        payload={"fields": list(data.keys())},
        request=request,
    )
    db.commit()
    db.refresh(c)
    return _serialize(c)


@router.post("/import", response_model=ContentRead)
def import_content(
    payload: ContentImport,
    request: Request,
    org: OrgContext = Depends(require_growth_write),
    db: Session = Depends(get_session),
) -> ContentRead:
    """Idempotent import keyed by (organization, source_system, external_id).

    Returns 200 with the existing content if already imported, updating
    mutable fields; 201 semantics via body vs. new record are implicit — the
    unique constraint guarantees at-most-one row.
    """
    _validate_fks(
        db, org.organization_id, payload.brand_id, payload.campaign_id, payload.product_id
    )
    existing = db.execute(
        select(ContentItem).where(
            ContentItem.organization_id == org.organization_id,
            ContentItem.source_system == payload.source_system,
            ContentItem.external_id == payload.external_id,
        )
    ).scalar_one_or_none()

    if existing is not None:
        # Update the "flowing" fields but preserve identity.
        for field in (
            "title",
            "hook",
            "caption",
            "cta",
            "status",
            "published_at",
            "campaign_id",
            "product_id",
            "platform",
            "content_type",
        ):
            new_val = getattr(payload, field)
            if new_val is not None:
                setattr(existing, field, new_val)
        for url_field, val in (
            ("media_url", payload.media_url),
            ("publication_url", payload.publication_url),
        ):
            if val is not None:
                setattr(existing, url_field, str(val))
        db.flush()
        audit.record(
            db,
            action="content.imported",
            organization_id=org.organization_id,
            target_type="content",
            target_id=existing.id,
            payload={
                "external_id": payload.external_id,
                "source_system": payload.source_system.value,
                "operation": "upsert",
            },
            request=request,
        )
        db.commit()
        db.refresh(existing)
        return _serialize(existing)

    c = ContentItem(
        organization_id=org.organization_id,
        brand_id=payload.brand_id,
        campaign_id=payload.campaign_id,
        product_id=payload.product_id,
        public_id=make_public_id("ct"),
        external_id=payload.external_id,
        source_system=payload.source_system,
        platform=payload.platform,
        content_type=payload.content_type,
        title=payload.title,
        hook=payload.hook,
        caption=payload.caption,
        cta=payload.cta,
        media_url=str(payload.media_url) if payload.media_url else None,
        publication_url=str(payload.publication_url) if payload.publication_url else None,
        status=payload.status,
        published_at=payload.published_at,
    )
    db.add(c)
    db.flush()
    audit.record(
        db,
        action="content.imported",
        organization_id=org.organization_id,
        target_type="content",
        target_id=c.id,
        payload={
            "external_id": payload.external_id,
            "source_system": payload.source_system.value,
            "operation": "create",
        },
        request=request,
    )
    db.commit()
    db.refresh(c)
    return _serialize(c)
