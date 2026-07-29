from __future__ import annotations

import base64
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app import audit
from app.core.config import settings
from app.deps import OrgContext, current_org, current_user, get_session, require_asset_write
from app.models.assets import Asset, AssetVariant
from app.models.content import ContentItem
from app.models.enums import AssetStatus, AssetType, VariantType
from app.models.membership import Role
from app.models.user import User
from app.schemas.assets import (
    AssetRead,
    AssetUpdate,
    AssetVariantCreate,
    AssetVariantRead,
    CompleteUploadRequest,
    GenerateThumbnailRequest,
    InitUploadRequest,
    InitUploadResponse,
    SignedUrlResponse,
)
from app.storage.provider import get_storage_provider, make_storage_key
from app.storage.validation import AssetRejected, make_safe_filename, validate_upload
from app.utils.public_id import make as make_public_id

router = APIRouter(prefix="/assets", tags=["assets"])

_SIGNED_URL_ROLES = (Role.OWNER, Role.ADMIN, Role.MARKETER, Role.SALES)


def _get_or_404(db: Session, org_id: uuid.UUID, asset_id: uuid.UUID) -> Asset:
    row = db.execute(
        select(Asset).where(Asset.id == asset_id, Asset.organization_id == org_id)
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="asset not found")
    return row


@router.get("", response_model=list[AssetRead])
def list_assets(
    asset_type: AssetType | None = Query(default=None),
    status_filter: AssetStatus | None = Query(default=None, alias="status"),
    brand_id: uuid.UUID | None = None,
    product_id: uuid.UUID | None = None,
    content_item_id: uuid.UUID | None = None,
    q: str | None = Query(default=None),
    created_after: datetime | None = None,
    created_before: datetime | None = None,
    org: OrgContext = Depends(current_org),
    db: Session = Depends(get_session),
) -> list[AssetRead]:
    stmt = (
        select(Asset)
        .where(Asset.organization_id == org.organization_id)
        .order_by(Asset.created_at.desc())
        .limit(200)
    )
    if asset_type:
        stmt = stmt.where(Asset.asset_type == asset_type)
    if status_filter:
        stmt = stmt.where(Asset.status == status_filter)
    if brand_id:
        stmt = stmt.where(Asset.brand_id == brand_id)
    if product_id:
        stmt = stmt.where(Asset.product_id == product_id)
    if content_item_id:
        stmt = stmt.where(Asset.content_item_id == content_item_id)
    if created_after:
        stmt = stmt.where(Asset.created_at >= created_after)
    if created_before:
        stmt = stmt.where(Asset.created_at <= created_before)
    if q:
        pat = f"%{q}%"
        stmt = stmt.where(
            or_(Asset.original_filename.ilike(pat), Asset.caption.ilike(pat))
        )
    return [AssetRead.model_validate(a) for a in db.execute(stmt).scalars().all()]


@router.post("/init-upload", response_model=InitUploadResponse, status_code=201)
def init_upload(
    payload: InitUploadRequest,
    request: Request,
    user: User = Depends(current_user),
    org: OrgContext = Depends(require_asset_write),
    db: Session = Depends(get_session),
) -> InitUploadResponse:
    if payload.content_item_id is not None:
        ok = db.execute(
            select(ContentItem.id).where(
                ContentItem.id == payload.content_item_id,
                ContentItem.organization_id == org.organization_id,
            )
        ).scalar_one_or_none()
        if ok is None:
            raise HTTPException(
                status_code=400, detail="content item not found in organization"
            )

    safe_filename = make_safe_filename(payload.filename)
    storage_key = make_storage_key(org.organization_id, safe_filename)
    provider = settings.storage_provider.upper()

    asset = Asset(
        organization_id=org.organization_id,
        public_id=make_public_id("as"),
        brand_id=payload.brand_id,
        product_id=payload.product_id,
        content_item_id=payload.content_item_id,
        uploaded_by_user_id=user.id,
        asset_type=payload.asset_type,
        status=AssetStatus.UPLOADING,
        storage_provider=provider if provider in ("LOCAL", "S3", "R2", "MOCK") else "MOCK",
        storage_key=storage_key,
        original_filename=payload.filename[:255],
        safe_filename=safe_filename,
        mime_type=payload.mime_type,
        size_bytes=0,
        checksum_sha256="",
        alt_text=payload.alt_text,
        caption=payload.caption,
    )
    db.add(asset)
    db.flush()
    audit.record(
        db,
        action="asset.upload_initialized",
        actor_user_id=user.id,
        organization_id=org.organization_id,
        target_type="asset",
        target_id=asset.id,
        payload={"public_id": asset.public_id, "declared_mime": payload.mime_type},
        request=request,
    )
    db.commit()
    from app.storage.validation import max_size_bytes

    return InitUploadResponse(
        asset_id=asset.id,
        storage_provider=asset.storage_provider,
        upload_method="complete-upload",
        max_size_bytes=max_size_bytes(payload.asset_type),
    )


@router.post("/complete-upload", response_model=AssetRead)
def complete_upload(
    payload: CompleteUploadRequest,
    request: Request,
    user: User = Depends(current_user),
    org: OrgContext = Depends(require_asset_write),
    db: Session = Depends(get_session),
) -> AssetRead:
    asset = _get_or_404(db, org.organization_id, payload.asset_id)
    if asset.status != AssetStatus.UPLOADING:
        raise HTTPException(
            status_code=400, detail="asset is not awaiting upload completion"
        )

    content = base64.b64decode(payload.content_base64)

    try:
        real_mime, real_type = validate_upload(
            declared_mime=asset.mime_type, asset_type=asset.asset_type, content=content
        )
    except AssetRejected as exc:
        asset.status = AssetStatus.REJECTED
        db.flush()
        audit.record(
            db,
            action="asset.rejected",
            actor_user_id=user.id,
            organization_id=org.organization_id,
            target_type="asset",
            target_id=asset.id,
            payload={"reason": exc.reason},
            request=request,
        )
        db.commit()
        raise HTTPException(status_code=422, detail=exc.reason) from exc

    # Duplicate detection by (org, checksum) BEFORE writing bytes.
    import hashlib

    checksum = hashlib.sha256(content).hexdigest()
    dup = db.execute(
        select(Asset).where(
            Asset.organization_id == org.organization_id,
            Asset.checksum_sha256 == checksum,
            Asset.id != asset.id,
            Asset.status != AssetStatus.REJECTED,
        )
    ).scalar_one_or_none()

    provider = get_storage_provider()
    import asyncio

    stored = asyncio.run(
        provider.upload(storage_key=asset.storage_key, content=content, mime_type=real_mime)
    )

    asset.mime_type = real_mime
    asset.asset_type = real_type
    asset.size_bytes = stored.size_bytes
    asset.checksum_sha256 = stored.checksum_sha256
    asset.status = AssetStatus.READY
    if dup is not None:
        asset.asset_metadata = {**asset.asset_metadata, "duplicate_of": str(dup.id)}
    db.flush()

    audit.record(
        db,
        action="asset.upload_completed",
        actor_user_id=user.id,
        organization_id=org.organization_id,
        target_type="asset",
        target_id=asset.id,
        payload={
            "size_bytes": asset.size_bytes,
            "mime_type": asset.mime_type,
            "duplicate": dup is not None,
        },
        request=request,
    )
    db.commit()
    db.refresh(asset)
    return AssetRead.model_validate(asset)


@router.get("/{asset_id}", response_model=AssetRead)
def get_asset(
    asset_id: uuid.UUID,
    org: OrgContext = Depends(current_org),
    db: Session = Depends(get_session),
) -> AssetRead:
    return AssetRead.model_validate(_get_or_404(db, org.organization_id, asset_id))


@router.patch("/{asset_id}", response_model=AssetRead)
def update_asset(
    asset_id: uuid.UUID,
    payload: AssetUpdate,
    request: Request,
    user: User = Depends(current_user),
    org: OrgContext = Depends(require_asset_write),
    db: Session = Depends(get_session),
) -> AssetRead:
    asset = _get_or_404(db, org.organization_id, asset_id)
    if asset.status == AssetStatus.ARCHIVED:
        raise HTTPException(status_code=400, detail="archived assets cannot be edited")
    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(asset, k, v)
    db.flush()
    audit.record(
        db,
        action="asset.updated",
        actor_user_id=user.id,
        organization_id=org.organization_id,
        target_type="asset",
        target_id=asset.id,
        payload={"fields": list(data.keys())},
        request=request,
    )
    db.commit()
    db.refresh(asset)
    return AssetRead.model_validate(asset)


@router.delete("/{asset_id}", status_code=204)
def archive_asset_delete(
    asset_id: uuid.UUID,
    request: Request,
    user: User = Depends(current_user),
    org: OrgContext = Depends(require_asset_write),
    db: Session = Depends(get_session),
) -> None:
    """DELETE never removes bytes or the row — it archives, matching the
    'no eliminar físicamente' rule when a publication may reference this
    asset historically."""
    asset = _get_or_404(db, org.organization_id, asset_id)
    if asset.status != AssetStatus.ARCHIVED:
        asset.status = AssetStatus.ARCHIVED
        asset.archived_at = datetime.now(UTC)
        db.flush()
        audit.record(
            db,
            action="asset.archived",
            actor_user_id=user.id,
            organization_id=org.organization_id,
            target_type="asset",
            target_id=asset.id,
            payload={},
            request=request,
        )
    db.commit()
    return None


@router.post("/{asset_id}/archive", response_model=AssetRead)
def archive_asset(
    asset_id: uuid.UUID,
    request: Request,
    user: User = Depends(current_user),
    org: OrgContext = Depends(require_asset_write),
    db: Session = Depends(get_session),
) -> AssetRead:
    asset = _get_or_404(db, org.organization_id, asset_id)
    if asset.status != AssetStatus.ARCHIVED:
        asset.status = AssetStatus.ARCHIVED
        asset.archived_at = datetime.now(UTC)
        db.flush()
        audit.record(
            db,
            action="asset.archived",
            actor_user_id=user.id,
            organization_id=org.organization_id,
            target_type="asset",
            target_id=asset.id,
            payload={},
            request=request,
        )
    db.commit()
    db.refresh(asset)
    return AssetRead.model_validate(asset)


@router.get("/{asset_id}/download-url", response_model=SignedUrlResponse)
def download_url(
    asset_id: uuid.UUID,
    request: Request,
    user: User = Depends(current_user),
    org: OrgContext = Depends(current_org),
    db: Session = Depends(get_session),
) -> SignedUrlResponse:
    if org.membership.role not in _SIGNED_URL_ROLES:
        raise HTTPException(
            status_code=403,
            detail="ANALYST/VIEWER cannot obtain private asset URLs",
        )
    asset = _get_or_404(db, org.organization_id, asset_id)
    if asset.status not in (AssetStatus.READY,):
        raise HTTPException(status_code=400, detail="asset is not READY")

    import asyncio

    provider = get_storage_provider()
    url = asyncio.run(
        provider.create_signed_url(
            storage_key=asset.storage_key, ttl_seconds=settings.asset_signed_url_ttl_seconds
        )
    )
    audit.record(
        db,
        action="asset.downloaded",
        actor_user_id=user.id,
        organization_id=org.organization_id,
        target_type="asset",
        target_id=asset.id,
        payload={},  # never log the signed URL itself
        request=request,
    )
    db.commit()
    return SignedUrlResponse(
        url=url, expires_in_seconds=settings.asset_signed_url_ttl_seconds
    )


@router.get("/{asset_id}/variants", response_model=list[AssetVariantRead])
def list_variants(
    asset_id: uuid.UUID,
    org: OrgContext = Depends(current_org),
    db: Session = Depends(get_session),
) -> list[AssetVariantRead]:
    _get_or_404(db, org.organization_id, asset_id)
    rows = db.execute(
        select(AssetVariant).where(
            AssetVariant.organization_id == org.organization_id,
            AssetVariant.asset_id == asset_id,
        )
    ).scalars().all()
    return [AssetVariantRead.model_validate(v) for v in rows]


@router.post("/{asset_id}/variants", response_model=AssetVariantRead, status_code=201)
def create_variant(
    asset_id: uuid.UUID,
    payload: AssetVariantCreate,
    request: Request,
    user: User = Depends(current_user),
    org: OrgContext = Depends(require_asset_write),
    db: Session = Depends(get_session),
) -> AssetVariantRead:
    asset = _get_or_404(db, org.organization_id, asset_id)
    if asset.status != AssetStatus.READY:
        raise HTTPException(
            status_code=400, detail="only a READY asset can have variants generated"
        )

    # MVP: MOCK "transformation" — reuse the original asset's bytes/mime and
    # just record the intended target dimensions. A real worker would
    # transcode; the interface point is here for that to plug into later.
    variant = AssetVariant(
        organization_id=org.organization_id,
        public_id=make_public_id("av"),
        asset_id=asset.id,
        platform=payload.platform,
        variant_type=payload.variant_type,
        width=payload.width,
        height=payload.height,
        duration_seconds=payload.duration_seconds,
        storage_key=asset.storage_key,
        mime_type=asset.mime_type,
        size_bytes=asset.size_bytes,
        transformation_spec={
            "mock": True,
            "source_asset_id": str(asset.id),
            "requested_width": payload.width,
            "requested_height": payload.height,
        },
    )
    db.add(variant)
    db.flush()
    audit.record(
        db,
        action="asset.variant_created",
        actor_user_id=user.id,
        organization_id=org.organization_id,
        target_type="asset_variant",
        target_id=variant.id,
        payload={"platform": payload.platform, "variant_type": payload.variant_type.value},
        request=request,
    )
    db.commit()
    db.refresh(variant)
    return AssetVariantRead.model_validate(variant)


@router.post(
    "/{asset_id}/generate-thumbnail", response_model=AssetVariantRead, status_code=201
)
def generate_thumbnail(
    asset_id: uuid.UUID,
    payload: GenerateThumbnailRequest,
    request: Request,
    user: User = Depends(current_user),
    org: OrgContext = Depends(require_asset_write),
    db: Session = Depends(get_session),
) -> AssetVariantRead:
    """AI-generated branded thumbnail for a manually-uploaded video asset —
    same flyer pipeline (brand visual_style + real logo overlay) as
    IMAGE_ASSET generation jobs, but driven by explicit copy instead of an
    AI-brainstormed brief, since there's no GenerationJob for a manual
    upload. See app.ai.thumbnails."""
    import asyncio

    from app.ai.image_providers import ImageProviderError
    from app.ai.thumbnails import generate_thumbnail_image
    from app.models.ai import BrandVoiceProfile
    from app.models.brand import Brand

    asset = _get_or_404(db, org.organization_id, asset_id)
    if asset.asset_type != AssetType.VIDEO:
        raise HTTPException(
            status_code=400, detail="thumbnails can only be generated for video assets"
        )
    if payload.format not in ("vertical", "facebook_horizontal"):
        raise HTTPException(status_code=422, detail="format must be 'vertical' or 'facebook_horizontal'")

    brand = db.get(Brand, asset.brand_id) if asset.brand_id else None
    brand_voice = None
    if asset.brand_id:
        brand_voice = db.execute(
            select(BrandVoiceProfile).where(
                BrandVoiceProfile.organization_id == org.organization_id,
                BrandVoiceProfile.brand_id == asset.brand_id,
            )
        ).scalar_one_or_none()

    try:
        content = asyncio.run(
            generate_thumbnail_image(
                title=payload.title,
                subtitle=payload.subtitle,
                benefits=payload.benefits,
                cta_banner=payload.cta_banner,
                content_style=payload.content_style,  # type: ignore[arg-type]
                fmt=payload.format,  # type: ignore[arg-type]
                brand_voice=brand_voice,
                brand_slug=brand.slug if brand else "",
            )
        )
    except ImageProviderError as exc:
        raise HTTPException(status_code=502, detail=f"thumbnail generation failed: {exc}") from exc

    try:
        real_mime, real_type = validate_upload(
            declared_mime="image/png", asset_type=AssetType.IMAGE, content=content
        )
    except AssetRejected as exc:
        raise HTTPException(status_code=422, detail=exc.reason) from exc

    safe_filename = make_safe_filename(f"thumbnail-{asset.public_id}.png")
    storage_key = make_storage_key(org.organization_id, safe_filename)
    stored = asyncio.run(
        get_storage_provider().upload(storage_key=storage_key, content=content, mime_type=real_mime)
    )

    variant = AssetVariant(
        organization_id=org.organization_id,
        public_id=make_public_id("av"),
        asset_id=asset.id,
        platform="FACEBOOK" if payload.format == "facebook_horizontal" else "ALL",
        variant_type=VariantType.THUMBNAIL,
        width=1200 if payload.format == "facebook_horizontal" else None,
        height=630 if payload.format == "facebook_horizontal" else None,
        storage_key=stored.storage_key,
        mime_type=real_mime,
        size_bytes=stored.size_bytes,
        transformation_spec={
            "ai_generated": True,
            "title": payload.title,
            "format": payload.format,
            "content_style": payload.content_style,
        },
    )
    db.add(variant)
    db.flush()
    audit.record(
        db,
        action="asset.thumbnail_generated",
        actor_user_id=user.id,
        organization_id=org.organization_id,
        target_type="asset_variant",
        target_id=variant.id,
        payload={"source_asset_id": str(asset.id), "format": payload.format},
        request=request,
    )
    db.commit()
    db.refresh(variant)
    return AssetVariantRead.model_validate(variant)
