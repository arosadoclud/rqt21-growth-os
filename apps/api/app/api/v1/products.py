from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import audit
from app.deps import OrgContext, current_org, get_session, require_growth_write
from app.models.brand import Brand
from app.models.enums import ProductStatus
from app.models.product import Product
from app.schemas.growth import ProductCreate, ProductRead, ProductUpdate
from app.utils.public_id import make as make_public_id

router = APIRouter(prefix="/products", tags=["products"])


def _serialize(p: Product) -> ProductRead:
    return ProductRead.model_validate(p)


def _get_or_404(db: Session, org_id: uuid.UUID, product_id: uuid.UUID) -> Product:
    p = db.execute(
        select(Product).where(
            Product.id == product_id, Product.organization_id == org_id
        )
    ).scalar_one_or_none()
    if p is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="product not found"
        )
    return p


def _assert_brand(db: Session, org_id: uuid.UUID, brand_id: uuid.UUID) -> None:
    ok = db.execute(
        select(Brand.id).where(Brand.id == brand_id, Brand.organization_id == org_id)
    ).scalar_one_or_none()
    if ok is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="brand not found in organization"
        )


@router.get("", response_model=list[ProductRead])
def list_products(
    brand_id: uuid.UUID | None = Query(default=None),
    status_filter: ProductStatus | None = Query(default=None, alias="status"),
    org: OrgContext = Depends(current_org),
    db: Session = Depends(get_session),
) -> list[ProductRead]:
    stmt = (
        select(Product)
        .where(Product.organization_id == org.organization_id)
        .order_by(Product.created_at.desc())
    )
    if brand_id:
        stmt = stmt.where(Product.brand_id == brand_id)
    if status_filter:
        stmt = stmt.where(Product.status == status_filter)
    return [_serialize(p) for p in db.execute(stmt).scalars().all()]


@router.post("", response_model=ProductRead, status_code=status.HTTP_201_CREATED)
def create_product(
    payload: ProductCreate,
    request: Request,
    org: OrgContext = Depends(require_growth_write),
    db: Session = Depends(get_session),
) -> ProductRead:
    _assert_brand(db, org.organization_id, payload.brand_id)
    p = Product(
        organization_id=org.organization_id,
        brand_id=payload.brand_id,
        public_id=make_public_id("pr"),
        name=payload.name,
        slug=payload.slug,
        description=payload.description,
        price=payload.price,
        currency=payload.currency,
        checkout_url=str(payload.checkout_url) if payload.checkout_url else None,
        status=payload.status,
    )
    db.add(p)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="slug already exists"
        ) from None
    audit.record(
        db,
        action="product.created",
        organization_id=org.organization_id,
        target_type="product",
        target_id=p.id,
        payload={"slug": p.slug, "public_id": p.public_id},
        request=request,
    )
    db.commit()
    db.refresh(p)
    return _serialize(p)


@router.get("/{product_id}", response_model=ProductRead)
def get_product(
    product_id: uuid.UUID,
    org: OrgContext = Depends(current_org),
    db: Session = Depends(get_session),
) -> ProductRead:
    return _serialize(_get_or_404(db, org.organization_id, product_id))


@router.patch("/{product_id}", response_model=ProductRead)
def update_product(
    product_id: uuid.UUID,
    payload: ProductUpdate,
    request: Request,
    org: OrgContext = Depends(require_growth_write),
    db: Session = Depends(get_session),
) -> ProductRead:
    p = _get_or_404(db, org.organization_id, product_id)
    data = payload.model_dump(exclude_unset=True)
    if "checkout_url" in data and data["checkout_url"] is not None:
        data["checkout_url"] = str(data["checkout_url"])
    if "currency" in data and data["currency"] is not None:
        data["currency"] = data["currency"].upper()
    for k, v in data.items():
        setattr(p, k, v)
    db.flush()
    audit.record(
        db,
        action="product.updated",
        organization_id=org.organization_id,
        target_type="product",
        target_id=p.id,
        payload={"fields": list(data.keys())},
        request=request,
    )
    db.commit()
    db.refresh(p)
    return _serialize(p)


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
def archive_product(
    product_id: uuid.UUID,
    request: Request,
    org: OrgContext = Depends(require_growth_write),
    db: Session = Depends(get_session),
) -> None:
    p = _get_or_404(db, org.organization_id, product_id)
    if p.status != ProductStatus.ARCHIVED:
        p.status = ProductStatus.ARCHIVED
        db.flush()
        audit.record(
            db,
            action="product.updated",
            organization_id=org.organization_id,
            target_type="product",
            target_id=p.id,
            payload={"archived": True},
            request=request,
        )
    db.commit()
    return None
