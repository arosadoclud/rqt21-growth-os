from __future__ import annotations

import asyncio
import hashlib
import uuid
from datetime import UTC, datetime
from zoneinfo import ZoneInfoNotFoundError

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover
    ZoneInfo = None  # type: ignore[assignment]

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import audit
from app.core.config import settings
from app.deps import (
    OrgContext,
    current_org,
    current_user,
    get_session,
    require_publication_prepare,
)
from app.models.ai import CouncilReview
from app.models.assets import Asset, AssetVariant
from app.models.brand import Brand
from app.models.campaign import Campaign
from app.models.content import ContentItem
from app.models.editorial import EditorialCalendarItem, Review
from app.models.enums import (
    AttemptStatus,
    ConnectionStatus,
    CouncilDecision,
    NotificationType,
    Platform,
    PublicationStatus,
    ReviewDecision,
)
from app.models.membership import Role
from app.models.product import Product
from app.models.publishing import Publication, PublicationAttempt, PublishingConnection
from app.models.user import User
from app.notify import notify
from app.publishing.adapters import (
    PublicationPayload,
    PublishDuplicate,
    PublishError,
    PublishPermanentError,
    PublishRateLimited,
    PublishTimeout,
    get_publishing_provider,
)
from app.publishing.meta_token_resolver import resolve_connection_access_token
from app.publishing.retry import is_recoverable, max_attempts_reached, next_retry_at
from app.publishing.scheduler import get_scheduler
from app.publishing.validation import validate_publication_draft
from app.schemas.publishing import (
    MarkPublishedRequest,
    PublicationAttemptRead,
    PublicationCreate,
    PublicationRead,
    PublicationUpdate,
    PublishingSummary,
    ScheduleRequest,
    ValidationResultSchema,
)
from app.storage.provider import get_storage_provider
from app.utils.public_id import make as make_public_id

router = APIRouter(prefix="/publications", tags=["publications"])
publishing_router = APIRouter(prefix="/publishing", tags=["publishing"])

_scheduler = get_scheduler()


def _get_or_404(db: Session, org_id: uuid.UUID, pub_id: uuid.UUID) -> Publication:
    row = db.execute(
        select(Publication).where(Publication.id == pub_id, Publication.organization_id == org_id)
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="publication not found")
    return row


def _content_is_approved(db: Session, org_id: uuid.UUID, content_id: uuid.UUID) -> bool:
    latest = db.execute(
        select(Review)
        .where(Review.organization_id == org_id, Review.content_item_id == content_id)
        .order_by(Review.created_at.desc())
        .limit(1)
    ).scalar_one_or_none()
    return latest is not None and latest.decision == ReviewDecision.APPROVED


def _content_is_council_blocked(db: Session, org_id: uuid.UUID, content_id: uuid.UUID) -> bool:
    blocked = db.execute(
        select(CouncilReview.id).where(
            CouncilReview.organization_id == org_id,
            CouncilReview.content_item_id == content_id,
            CouncilReview.decision == CouncilDecision.BLOCKED,
        )
    ).first()
    return blocked is not None


def _validate_fks(
    db: Session,
    org_id: uuid.UUID,
    *,
    content_item_id: uuid.UUID,
    brand_id: uuid.UUID,
    campaign_id: uuid.UUID | None,
    product_id: uuid.UUID | None,
    publishing_connection_id: uuid.UUID,
    asset_id: uuid.UUID | None,
    asset_variant_id: uuid.UUID | None,
    editorial_calendar_item_id: uuid.UUID | None,
) -> PublishingConnection:
    checks: list[tuple[type, uuid.UUID | None, str]] = [
        (ContentItem, content_item_id, "content_item"),
        (Brand, brand_id, "brand"),
        (Campaign, campaign_id, "campaign"),
        (Product, product_id, "product"),
        (Asset, asset_id, "asset"),
        (AssetVariant, asset_variant_id, "asset_variant"),
        (EditorialCalendarItem, editorial_calendar_item_id, "editorial_calendar_item"),
    ]
    for model, val, label in checks:
        if val is None:
            continue
        ok = db.execute(
            select(model.id).where(model.id == val, model.organization_id == org_id)
        ).scalar_one_or_none()
        if ok is None:
            raise HTTPException(status_code=400, detail=f"{label} not found in organization")

    connection = db.execute(
        select(PublishingConnection).where(
            PublishingConnection.id == publishing_connection_id,
            PublishingConnection.organization_id == org_id,
        )
    ).scalar_one_or_none()
    if connection is None:
        raise HTTPException(
            status_code=400, detail="publishing connection not found in organization"
        )
    return connection


@router.get("", response_model=list[PublicationRead])
def list_publications(
    status_filter: PublicationStatus | None = Query(default=None, alias="status"),
    platform: Platform | None = None,
    publishing_connection_id: uuid.UUID | None = None,
    brand_id: uuid.UUID | None = None,
    campaign_id: uuid.UUID | None = None,
    content_item_id: uuid.UUID | None = None,
    failed_only: bool = Query(default=False),
    created_after: datetime | None = None,
    created_before: datetime | None = None,
    org: OrgContext = Depends(current_org),
    db: Session = Depends(get_session),
) -> list[PublicationRead]:
    stmt = (
        select(Publication)
        .where(Publication.organization_id == org.organization_id)
        .order_by(Publication.created_at.desc())
        .limit(200)
    )
    if status_filter:
        stmt = stmt.where(Publication.status == status_filter)
    if platform:
        stmt = stmt.where(Publication.platform == platform)
    if publishing_connection_id:
        stmt = stmt.where(Publication.publishing_connection_id == publishing_connection_id)
    if brand_id:
        stmt = stmt.where(Publication.brand_id == brand_id)
    if campaign_id:
        stmt = stmt.where(Publication.campaign_id == campaign_id)
    if content_item_id:
        stmt = stmt.where(Publication.content_item_id == content_item_id)
    if failed_only:
        stmt = stmt.where(Publication.status == PublicationStatus.FAILED)
    if created_after:
        stmt = stmt.where(Publication.created_at >= created_after)
    if created_before:
        stmt = stmt.where(Publication.created_at <= created_before)
    return [PublicationRead.model_validate(p) for p in db.execute(stmt).scalars().all()]


@router.post("", response_model=PublicationRead, status_code=201)
def create_publication(
    payload: PublicationCreate,
    request: Request,
    user: User = Depends(current_user),
    org: OrgContext = Depends(require_publication_prepare),
    db: Session = Depends(get_session),
) -> PublicationRead:
    _validate_fks(
        db,
        org.organization_id,
        content_item_id=payload.content_item_id,
        brand_id=payload.brand_id,
        campaign_id=payload.campaign_id,
        product_id=payload.product_id,
        publishing_connection_id=payload.publishing_connection_id,
        asset_id=payload.asset_id,
        asset_variant_id=payload.asset_variant_id,
        editorial_calendar_item_id=payload.editorial_calendar_item_id,
    )

    # Default idempotency key: same (content, platform, connection) triple
    # returns the existing draft instead of silently duplicating it. A
    # caller that truly wants a second publication for the same triple must
    # pass an explicit, different idempotency_key.
    idem_key = payload.idempotency_key or hashlib.sha256(
        f"{payload.content_item_id}:{payload.platform.value}:{payload.publishing_connection_id}".encode()
    ).hexdigest()[:32]

    existing = db.execute(
        select(Publication).where(
            Publication.organization_id == org.organization_id,
            Publication.idempotency_key == idem_key,
        )
    ).scalar_one_or_none()
    if existing is not None:
        return PublicationRead.model_validate(existing)

    row = Publication(
        organization_id=org.organization_id,
        public_id=make_public_id("pub"),
        content_item_id=payload.content_item_id,
        editorial_calendar_item_id=payload.editorial_calendar_item_id,
        brand_id=payload.brand_id,
        campaign_id=payload.campaign_id,
        product_id=payload.product_id,
        publishing_connection_id=payload.publishing_connection_id,
        asset_id=payload.asset_id,
        asset_variant_id=payload.asset_variant_id,
        platform=payload.platform,
        publication_type=payload.publication_type,
        status=PublicationStatus.DRAFT,
        caption=payload.caption,
        title=payload.title,
        cta=payload.cta,
        hashtags=payload.hashtags,
        idempotency_key=idem_key,
        created_by_user_id=user.id,
    )
    db.add(row)
    db.flush()
    audit.record(
        db,
        action="publication.created",
        actor_user_id=user.id,
        organization_id=org.organization_id,
        target_type="publication",
        target_id=row.id,
        payload={"public_id": row.public_id, "platform": row.platform.value},
        request=request,
    )
    db.commit()
    db.refresh(row)
    return PublicationRead.model_validate(row)


@router.get("/{publication_id}", response_model=PublicationRead)
def get_publication(
    publication_id: uuid.UUID,
    org: OrgContext = Depends(current_org),
    db: Session = Depends(get_session),
) -> PublicationRead:
    return PublicationRead.model_validate(_get_or_404(db, org.organization_id, publication_id))


@router.patch("/{publication_id}", response_model=PublicationRead)
def update_publication(
    publication_id: uuid.UUID,
    payload: PublicationUpdate,
    request: Request,
    user: User = Depends(current_user),
    org: OrgContext = Depends(require_publication_prepare),
    db: Session = Depends(get_session),
) -> PublicationRead:
    row = _get_or_404(db, org.organization_id, publication_id)
    if row.status in (PublicationStatus.PUBLISHED, PublicationStatus.PUBLISHING):
        raise HTTPException(status_code=400, detail="cannot edit a published/publishing item")
    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(row, k, v)
    # Any content edit invalidates a prior READY validation.
    if data and row.status == PublicationStatus.READY:
        row.status = PublicationStatus.DRAFT
    db.flush()
    audit.record(
        db,
        action="publication.updated",
        actor_user_id=user.id,
        organization_id=org.organization_id,
        target_type="publication",
        target_id=row.id,
        payload={"fields": list(data.keys())},
        request=request,
    )
    db.commit()
    db.refresh(row)
    return PublicationRead.model_validate(row)


@router.post("/{publication_id}/validate", response_model=ValidationResultSchema)
def validate_publication(
    publication_id: uuid.UUID,
    request: Request,
    user: User = Depends(current_user),
    org: OrgContext = Depends(require_publication_prepare),
    db: Session = Depends(get_session),
) -> ValidationResultSchema:
    row = _get_or_404(db, org.organization_id, publication_id)
    errors: list[str] = []
    warnings: list[str] = []

    if not _content_is_approved(db, org.organization_id, row.content_item_id):
        errors.append("content is not APPROVED — only approved content can be published")
    if _content_is_council_blocked(db, org.organization_id, row.content_item_id):
        errors.append("content was BLOCKED by the editorial council and cannot be published")

    asset = db.get(Asset, row.asset_id) if row.asset_id else None
    result = validate_publication_draft(
        platform=row.platform,
        publication_type=row.publication_type,
        caption=row.caption,
        hashtags=row.hashtags,
        asset=asset,
    )
    errors.extend(result.errors)
    warnings.extend(result.warnings)

    ok = not errors
    if ok:
        row.status = PublicationStatus.READY
        db.flush()
    audit.record(
        db,
        action="publication.validated",
        actor_user_id=user.id,
        organization_id=org.organization_id,
        target_type="publication",
        target_id=row.id,
        payload={"ok": ok, "error_count": len(errors)},
        request=request,
    )
    db.commit()
    return ValidationResultSchema(ok=ok, errors=errors, warnings=warnings)


@router.post("/{publication_id}/schedule", response_model=PublicationRead)
def schedule_publication(
    publication_id: uuid.UUID,
    payload: ScheduleRequest,
    request: Request,
    user: User = Depends(current_user),
    org: OrgContext = Depends(require_publication_prepare),
    db: Session = Depends(get_session),
) -> PublicationRead:
    row = _get_or_404(db, org.organization_id, publication_id)
    if row.status != PublicationStatus.READY:
        raise HTTPException(status_code=400, detail="only a READY publication can be scheduled")
    if payload.scheduled_for <= datetime.now(UTC):
        raise HTTPException(status_code=400, detail="scheduled_for must be in the future")
    if ZoneInfo is not None:
        try:
            ZoneInfo(payload.timezone)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise HTTPException(status_code=400, detail="invalid timezone") from exc

    row.status = PublicationStatus.SCHEDULED
    row.scheduled_for = payload.scheduled_for
    row.timezone = payload.timezone
    db.flush()
    asyncio.run(_scheduler.schedule("publication", row.id, payload.scheduled_for))
    audit.record(
        db,
        action="publication.scheduled",
        actor_user_id=user.id,
        organization_id=org.organization_id,
        target_type="publication",
        target_id=row.id,
        payload={"scheduled_for": payload.scheduled_for.isoformat()},
        request=request,
    )
    db.commit()
    db.refresh(row)
    return PublicationRead.model_validate(row)


def _require_role(org: OrgContext, roles: tuple[Role, ...], detail: str) -> None:
    if org.membership.role not in roles:
        raise HTTPException(status_code=403, detail=detail)


def _execute_publish(
    db: Session,
    request: Request | None,
    row: Publication,
    connection: PublishingConnection,
    actor_user_id: uuid.UUID | None,
) -> Publication:
    attempt_number = row.attempt_count + 1

    access_token = ""
    if connection.provider.value == "META":
        access_token = asyncio.run(resolve_connection_access_token(connection))
    provider = get_publishing_provider(connection.provider.value, access_token=access_token)

    asset_public_url: str | None = None
    if row.asset_id is not None:
        asset = db.get(Asset, row.asset_id)
        if asset is not None:
            storage_provider = get_storage_provider()
            asset_public_url = asyncio.run(
                storage_provider.create_signed_url(
                    storage_key=asset.storage_key,
                    ttl_seconds=settings.asset_signed_url_ttl_seconds,
                )
            )

    thumbnail_public_url: str | None = None
    if row.asset_variant_id is not None:
        variant = db.get(AssetVariant, row.asset_variant_id)
        if variant is not None:
            storage_provider = get_storage_provider()
            thumbnail_public_url = asyncio.run(
                storage_provider.create_signed_url(
                    storage_key=variant.storage_key,
                    ttl_seconds=settings.asset_signed_url_ttl_seconds,
                )
            )

    # Prefer an explicit Facebook `page_id` stored inside the encrypted
    # connection credentials for FACEBOOK publishes. For INSTAGRAM the
    # `external_account_id` holds the IG account id and must be used.
    target_account_id = connection.external_account_id
    if row.platform.value == "FACEBOOK" and connection.credentials_encrypted:
        try:
            from app.publishing.crypto import decrypt_credentials

            creds = decrypt_credentials(connection.credentials_encrypted)
            if isinstance(creds, dict) and creds.get("page_id"):
                target_account_id = creds.get("page_id")
        except Exception:
            # Fall back to the stored external_account_id if decryption fails
            target_account_id = connection.external_account_id

    payload = PublicationPayload(
        publication_id=str(row.id),
        platform=row.platform.value,
        publication_type=row.publication_type.value,
        caption=row.caption,
        title=row.title,
        cta=row.cta,
        hashtags=row.hashtags,
        asset_storage_key=None,
        connection_external_account_id=target_account_id,
        asset_public_url=asset_public_url,
        thumbnail_public_url=thumbnail_public_url,
    )

    row.status = PublicationStatus.PUBLISHING
    row.attempt_count = attempt_number
    db.flush()
    audit.record(
        db,
        action="publication.started",
        actor_user_id=actor_user_id,
        organization_id=row.organization_id,
        target_type="publication",
        target_id=row.id,
        payload={"attempt_number": attempt_number},
        request=request,
    )

    attempt = PublicationAttempt(
        public_id=make_public_id("pa"),
        organization_id=row.organization_id,
        publication_id=row.id,
        attempt_number=attempt_number,
        provider=connection.provider,
        status=AttemptStatus.STARTED,
        request_summary={"platform": row.platform.value, "caption_length": len(row.caption)},
    )
    db.add(attempt)
    db.flush()

    try:
        result = asyncio.run(provider.publish(payload, row.idempotency_key))
    except PublishDuplicate as exc:
        # Treat as already-published: the provider is telling us this exact
        # idempotency key already succeeded, so we converge on that id
        # rather than erroring or retrying.
        attempt.status = AttemptStatus.SUCCEEDED
        attempt.external_id = exc.existing_external_id
        attempt.response_summary = {"note": "duplicate — reused existing external id"}
        attempt.completed_at = datetime.now(UTC)
        row.status = PublicationStatus.PUBLISHED
        row.published_at = datetime.now(UTC)
        row.external_publication_id = exc.existing_external_id
        row.next_retry_at = None
        db.flush()
        audit.record(
            db,
            action="publication.published",
            actor_user_id=actor_user_id,
            organization_id=row.organization_id,
            target_type="publication",
            target_id=row.id,
            payload={"duplicate": True},
            request=request,
        )
        db.commit()
        db.refresh(row)
        return row
    except (PublishRateLimited, PublishTimeout, PublishError) as exc:
        error_code = (
            "rate_limited"
            if isinstance(exc, PublishRateLimited)
            else "timeout"
            if isinstance(exc, PublishTimeout)
            else "permanent_error"
            if isinstance(exc, PublishPermanentError)
            else "recoverable_error"
        )
        attempt.status = (
            AttemptStatus.RATE_LIMITED if isinstance(exc, PublishRateLimited) else AttemptStatus.FAILED
        )
        attempt.error_code = error_code
        attempt.error_message = str(exc)[:500]
        attempt.completed_at = datetime.now(UTC)
        db.flush()

        retry_after = getattr(exc, "retry_after_seconds", None)
        recoverable = is_recoverable(error_code)
        if recoverable and not max_attempts_reached(attempt_number):
            row.status = PublicationStatus.RETRY_SCHEDULED
            row.next_retry_at = next_retry_at(attempt_number, retry_after)
            row.failure_code = error_code
            row.failure_message = str(exc)[:500]
            db.flush()
            asyncio.run(_scheduler.schedule("publication_retry", row.id, row.next_retry_at))
            audit.record(
                db,
                action="publication.retry_scheduled",
                actor_user_id=actor_user_id,
                organization_id=row.organization_id,
                target_type="publication",
                target_id=row.id,
                payload={"attempt_number": attempt_number, "error_code": error_code},
                request=request,
            )
        else:
            row.status = PublicationStatus.FAILED
            row.failure_code = error_code
            row.failure_message = str(exc)[:500]
            row.next_retry_at = None
            db.flush()
            audit.record(
                db,
                action="publication.failed",
                actor_user_id=actor_user_id,
                organization_id=row.organization_id,
                target_type="publication",
                target_id=row.id,
                payload={"attempt_number": attempt_number, "error_code": error_code},
                request=request,
            )
            if row.created_by_user_id:
                notify(
                    db,
                    organization_id=row.organization_id,
                    user_id=row.created_by_user_id,
                    notification_type=NotificationType.PUBLICATION_FAILED,
                    title="Publicación fallida",
                    message=f"Falló la publicación en {row.platform.value}: {error_code}",
                    resource_type="publication",
                    resource_public_id=row.public_id,
                )

            from app.automation.engine import TriggerContext, run_triggers
            from app.models.enums import AutomationTriggerType as _ATT

            run_triggers(
                db,
                organization_id=row.organization_id,
                trigger_type=_ATT.PUBLICATION_FAILED,
                context=TriggerContext(
                    brand_id=row.brand_id,
                    campaign_id=row.campaign_id,
                    product_id=row.product_id,
                    publication_id=row.id,
                    actor_user_id=actor_user_id,
                ),
                request=request,
            )
        db.commit()
        db.refresh(row)
        return row

    attempt.status = AttemptStatus.SUCCEEDED
    attempt.external_id = result.external_publication_id
    attempt.response_summary = {"raw_status": result.raw_status}
    attempt.completed_at = datetime.now(UTC)
    row.status = PublicationStatus.PUBLISHED
    row.published_at = datetime.now(UTC)
    row.external_publication_id = result.external_publication_id
    row.external_url = result.external_url
    row.failure_code = None
    row.failure_message = None
    row.next_retry_at = None
    db.flush()
    audit.record(
        db,
        action="publication.published",
        actor_user_id=actor_user_id,
        organization_id=row.organization_id,
        target_type="publication",
        target_id=row.id,
        payload={"external_id": result.external_publication_id},
        request=request,
    )
    if row.created_by_user_id:
        notify(
            db,
            organization_id=row.organization_id,
            user_id=row.created_by_user_id,
            notification_type=NotificationType.PUBLICATION_SUCCEEDED,
            title="Publicación exitosa",
            message=f"Se publicó en {row.platform.value}",
            resource_type="publication",
            resource_public_id=row.public_id,
        )
    db.commit()
    db.refresh(row)
    return row


@router.post("/{publication_id}/publish", response_model=PublicationRead)
def publish_publication(
    publication_id: uuid.UUID,
    request: Request,
    user: User = Depends(current_user),
    org: OrgContext = Depends(current_org),
    db: Session = Depends(get_session),
) -> PublicationRead:
    row = _get_or_404(db, org.organization_id, publication_id)
    connection = db.get(PublishingConnection, row.publishing_connection_id)
    if connection is None:
        raise HTTPException(status_code=400, detail="publishing connection missing")

    if connection.provider.value == "MANUAL":
        raise HTTPException(
            status_code=400,
            detail="MANUAL connections cannot be auto-published; use mark-published",
        )
    # Automatic publication requires explicit OWNER/ADMIN authorization.
    _require_role(
        org, (Role.OWNER, Role.ADMIN), "authorizing automatic publication requires OWNER or ADMIN"
    )
    if row.status not in (PublicationStatus.READY, PublicationStatus.SCHEDULED):
        raise HTTPException(
            status_code=400, detail="publication must be READY or SCHEDULED to publish"
        )
    if connection.status != ConnectionStatus.ACTIVE:
        raise HTTPException(status_code=400, detail="publishing connection is not ACTIVE")

    row.approved_by_user_id = user.id
    db.flush()
    return PublicationRead.model_validate(_execute_publish(db, request, row, connection, user.id))


@router.post("/{publication_id}/retry", response_model=PublicationRead)
def retry_publication(
    publication_id: uuid.UUID,
    request: Request,
    user: User = Depends(current_user),
    org: OrgContext = Depends(current_org),
    db: Session = Depends(get_session),
) -> PublicationRead:
    _require_role(org, (Role.OWNER, Role.ADMIN), "manual retry requires OWNER or ADMIN")
    row = _get_or_404(db, org.organization_id, publication_id)
    if row.status not in (PublicationStatus.FAILED, PublicationStatus.RETRY_SCHEDULED):
        raise HTTPException(
            status_code=400, detail="only FAILED or RETRY_SCHEDULED publications can be retried"
        )
    connection = db.get(PublishingConnection, row.publishing_connection_id)
    if connection is None:
        raise HTTPException(status_code=400, detail="publishing connection missing")
    return PublicationRead.model_validate(_execute_publish(db, request, row, connection, user.id))


@router.post("/{publication_id}/cancel", response_model=PublicationRead)
def cancel_publication(
    publication_id: uuid.UUID,
    request: Request,
    user: User = Depends(current_user),
    org: OrgContext = Depends(require_publication_prepare),
    db: Session = Depends(get_session),
) -> PublicationRead:
    row = _get_or_404(db, org.organization_id, publication_id)
    if row.status in (PublicationStatus.PUBLISHED, PublicationStatus.PUBLISHING):
        raise HTTPException(
            status_code=400, detail="cannot cancel a published/publishing item"
        )
    row.status = PublicationStatus.CANCELLED
    row.next_retry_at = None
    db.flush()
    asyncio.run(_scheduler.cancel("publication", row.id))
    asyncio.run(_scheduler.cancel("publication_retry", row.id))
    audit.record(
        db,
        action="publication.cancelled",
        actor_user_id=user.id,
        organization_id=org.organization_id,
        target_type="publication",
        target_id=row.id,
        payload={},
        request=request,
    )
    db.commit()
    db.refresh(row)
    return PublicationRead.model_validate(row)


@router.delete("/{publication_id}", status_code=204)
def delete_publication(
    publication_id: uuid.UUID,
    request: Request,
    user: User = Depends(current_user),
    org: OrgContext = Depends(require_publication_prepare),
    db: Session = Depends(get_session),
) -> None:
    """Archive a publication (soft-delete).

    This marks the publication as ARCHIVED and cancels any scheduled tasks.
    Published or currently publishing items cannot be archived via this endpoint.
    """
    row = _get_or_404(db, org.organization_id, publication_id)
    if row.status in (PublicationStatus.PUBLISHED, PublicationStatus.PUBLISHING):
        raise HTTPException(status_code=400, detail="cannot delete a published/publishing item")

    row.status = PublicationStatus.ARCHIVED
    row.next_retry_at = None
    db.flush()
    # Cancel any scheduled jobs related to this publication
    asyncio.run(_scheduler.cancel("publication", row.id))
    asyncio.run(_scheduler.cancel("publication_retry", row.id))
    audit.record(
        db,
        action="publication.archived",
        actor_user_id=user.id,
        organization_id=org.organization_id,
        target_type="publication",
        target_id=row.id,
        payload={},
        request=request,
    )
    db.commit()
    return None


@router.post("/{publication_id}/mark-published", response_model=PublicationRead)
def mark_published(
    publication_id: uuid.UUID,
    payload: MarkPublishedRequest,
    request: Request,
    user: User = Depends(current_user),
    org: OrgContext = Depends(require_publication_prepare),
    db: Session = Depends(get_session),
) -> PublicationRead:
    row = _get_or_404(db, org.organization_id, publication_id)
    connection = db.get(PublishingConnection, row.publishing_connection_id)
    if connection is None or connection.provider.value != "MANUAL":
        raise HTTPException(
            status_code=400, detail="mark-published is only valid for MANUAL connections"
        )
    if row.status not in (PublicationStatus.READY, PublicationStatus.SCHEDULED, PublicationStatus.DRAFT):
        raise HTTPException(
            status_code=400, detail="publication is not in a publishable state"
        )

    attempt_number = row.attempt_count + 1
    now = payload.published_at or datetime.now(UTC)
    attempt = PublicationAttempt(
        public_id=make_public_id("pa"),
        organization_id=org.organization_id,
        publication_id=row.id,
        attempt_number=attempt_number,
        provider=connection.provider,
        status=AttemptStatus.SUCCEEDED,
        request_summary={"manual": True},
        response_summary={"external_url": payload.external_url},
        started_at=now,
        completed_at=now,
    )
    db.add(attempt)

    row.status = PublicationStatus.PUBLISHED
    row.published_at = now
    row.external_url = payload.external_url
    row.attempt_count = attempt_number
    row.approved_by_user_id = user.id
    row.failure_code = None
    row.failure_message = None
    row.next_retry_at = None
    db.flush()
    audit.record(
        db,
        action="publication.marked_manual",
        actor_user_id=user.id,
        organization_id=org.organization_id,
        target_type="publication",
        target_id=row.id,
        payload={"external_url_host": payload.external_url.split("/")[2] if "//" in payload.external_url else None},
        request=request,
    )
    db.commit()
    db.refresh(row)
    return PublicationRead.model_validate(row)


@router.get("/{publication_id}/attempts", response_model=list[PublicationAttemptRead])
def list_attempts(
    publication_id: uuid.UUID,
    org: OrgContext = Depends(current_org),
    db: Session = Depends(get_session),
) -> list[PublicationAttemptRead]:
    _get_or_404(db, org.organization_id, publication_id)
    rows = db.execute(
        select(PublicationAttempt)
        .where(
            PublicationAttempt.organization_id == org.organization_id,
            PublicationAttempt.publication_id == publication_id,
        )
        .order_by(PublicationAttempt.attempt_number.asc())
    ).scalars().all()
    return [PublicationAttemptRead.model_validate(a) for a in rows]


@publishing_router.get("/queue", response_model=list[PublicationRead])
def publishing_queue(
    org: OrgContext = Depends(current_org),
    db: Session = Depends(get_session),
) -> list[PublicationRead]:
    rows = db.execute(
        select(Publication)
        .where(
            Publication.organization_id == org.organization_id,
            Publication.status.in_(
                [
                    PublicationStatus.READY,
                    PublicationStatus.SCHEDULED,
                    PublicationStatus.PUBLISHING,
                    PublicationStatus.RETRY_SCHEDULED,
                    PublicationStatus.FAILED,
                ]
            ),
        )
        .order_by(Publication.scheduled_for.asc().nulls_last(), Publication.created_at.desc())
    ).scalars().all()
    return [PublicationRead.model_validate(p) for p in rows]


@publishing_router.get("/summary", response_model=PublishingSummary)
def publishing_summary(
    org: OrgContext = Depends(current_org),
    db: Session = Depends(get_session),
) -> PublishingSummary:
    from datetime import timedelta

    from sqlalchemy import func

    org_id = org.organization_id
    scheduled = db.execute(
        select(func.count(Publication.id)).where(
            Publication.organization_id == org_id, Publication.status == PublicationStatus.SCHEDULED
        )
    ).scalar_one()
    published = db.execute(
        select(func.count(Publication.id)).where(
            Publication.organization_id == org_id, Publication.status == PublicationStatus.PUBLISHED
        )
    ).scalar_one()
    failed = db.execute(
        select(func.count(Publication.id)).where(
            Publication.organization_id == org_id, Publication.status == PublicationStatus.FAILED
        )
    ).scalar_one()
    retries = db.execute(
        select(func.coalesce(func.sum(Publication.attempt_count - 1), 0)).where(
            Publication.organization_id == org_id, Publication.attempt_count > 1
        )
    ).scalar_one()
    by_platform_rows = db.execute(
        select(Publication.platform, func.count(Publication.id))
        .where(Publication.organization_id == org_id)
        .group_by(Publication.platform)
    ).all()
    upcoming = db.execute(
        select(func.count(Publication.id)).where(
            Publication.organization_id == org_id,
            Publication.status == PublicationStatus.SCHEDULED,
            Publication.scheduled_for >= datetime.now(UTC),
            Publication.scheduled_for < datetime.now(UTC) + timedelta(days=7),
        )
    ).scalar_one()
    conn_errors = db.execute(
        select(func.count(PublishingConnection.id)).where(
            PublishingConnection.organization_id == org_id,
            PublishingConnection.status == ConnectionStatus.ERROR,
        )
    ).scalar_one()

    total_terminal = published + failed
    success_rate = round((published / total_terminal) * 100, 2) if total_terminal else 0.0

    return PublishingSummary(
        scheduled=scheduled or 0,
        published=published or 0,
        failed=failed or 0,
        success_rate=success_rate,
        retries=int(retries or 0),
        by_platform={p.value: n for p, n in by_platform_rows},
        upcoming_7_days=upcoming or 0,
        connections_with_error=conn_errors or 0,
    )
