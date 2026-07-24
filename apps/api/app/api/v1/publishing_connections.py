from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import audit
from app.deps import OrgContext, current_org, current_user, get_session, require_connection_admin
from app.models.brand import Brand
from app.models.enums import ConnectionStatus
from app.models.membership import Role
from app.models.publishing import PublishingConnection
from app.models.user import User
from app.publishing.adapters import get_publishing_provider
from app.publishing.crypto import decrypt_credentials, encrypt_credentials, last_four
from app.schemas.publishing import (
    PublishingConnectionCreate,
    PublishingConnectionRead,
    PublishingConnectionUpdate,
)
from app.utils.public_id import make as make_public_id

router = APIRouter(prefix="/publishing-connections", tags=["publishing-connections"])


def _get_or_404(db: Session, org_id: uuid.UUID, conn_id: uuid.UUID) -> PublishingConnection:
    row = db.execute(
        select(PublishingConnection).where(
            PublishingConnection.id == conn_id, PublishingConnection.organization_id == org_id
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="publishing connection not found")
    return row


def _serialize(row: PublishingConnection, role: Role) -> PublishingConnectionRead:
    data = PublishingConnectionRead.model_validate(row).model_dump()
    # Only OWNER/ADMIN ever see even the last-4 hint; MARKETER/ANALYST see
    # status + capabilities only, never anything credential-shaped.
    if role in (Role.OWNER, Role.ADMIN) and row.credentials_encrypted:
        try:
            data["credentials_last_four"] = last_four(decrypt_credentials(row.credentials_encrypted))
        except Exception:
            data["credentials_last_four"] = None
    else:
        data["credentials_last_four"] = None
    return PublishingConnectionRead(**data)


@router.get("", response_model=list[PublishingConnectionRead])
def list_connections(
    org: OrgContext = Depends(current_org),
    db: Session = Depends(get_session),
) -> list[PublishingConnectionRead]:
    if org.membership.role == Role.VIEWER:
        raise HTTPException(status_code=403, detail="VIEWER cannot access publishing connections")
    rows = db.execute(
        select(PublishingConnection)
        .where(PublishingConnection.organization_id == org.organization_id)
        .order_by(PublishingConnection.created_at.desc())
    ).scalars().all()
    return [_serialize(r, org.membership.role) for r in rows]


@router.post("", response_model=PublishingConnectionRead, status_code=201)
def create_connection(
    payload: PublishingConnectionCreate,
    request: Request,
    user: User = Depends(current_user),
    org: OrgContext = Depends(require_connection_admin),
    db: Session = Depends(get_session),
) -> PublishingConnectionRead:
    ok = db.execute(
        select(Brand.id).where(
            Brand.id == payload.brand_id, Brand.organization_id == org.organization_id
        )
    ).scalar_one_or_none()
    if ok is None:
        raise HTTPException(status_code=400, detail="brand not found in organization")

    encrypted = encrypt_credentials(payload.credentials) if payload.credentials else None
    row = PublishingConnection(
        organization_id=org.organization_id,
        public_id=make_public_id("pcn"),
        brand_id=payload.brand_id,
        platform=payload.platform,
        provider=payload.provider,
        account_name=payload.account_name,
        external_account_id=payload.external_account_id,
        capabilities=payload.capabilities,
        credentials_encrypted=encrypted,
        token_expires_at=payload.token_expires_at,
        status=ConnectionStatus.PENDING if payload.provider not in ("MOCK", "MANUAL") else ConnectionStatus.ACTIVE,
        created_by_user_id=user.id,
    )
    db.add(row)
    db.flush()
    audit.record(
        db,
        action="publishing_connection.created",
        actor_user_id=user.id,
        organization_id=org.organization_id,
        target_type="publishing_connection",
        target_id=row.id,
        payload={"platform": row.platform.value, "provider": row.provider.value},
        request=request,
    )
    db.commit()
    db.refresh(row)
    return _serialize(row, org.membership.role)


@router.get("/{connection_id}", response_model=PublishingConnectionRead)
def get_connection(
    connection_id: uuid.UUID,
    org: OrgContext = Depends(current_org),
    db: Session = Depends(get_session),
) -> PublishingConnectionRead:
    if org.membership.role == Role.VIEWER:
        raise HTTPException(status_code=403, detail="VIEWER cannot access publishing connections")
    return _serialize(_get_or_404(db, org.organization_id, connection_id), org.membership.role)


@router.patch("/{connection_id}", response_model=PublishingConnectionRead)
def update_connection(
    connection_id: uuid.UUID,
    payload: PublishingConnectionUpdate,
    request: Request,
    user: User = Depends(current_user),
    org: OrgContext = Depends(require_connection_admin),
    db: Session = Depends(get_session),
) -> PublishingConnectionRead:
    row = _get_or_404(db, org.organization_id, connection_id)
    data = payload.model_dump(exclude_unset=True, exclude={"credentials"})
    for k, v in data.items():
        setattr(row, k, v)
    if payload.credentials is not None:
        row.credentials_encrypted = encrypt_credentials(payload.credentials)
    db.flush()
    audit.record(
        db,
        action="publishing_connection.updated",
        actor_user_id=user.id,
        organization_id=org.organization_id,
        target_type="publishing_connection",
        target_id=row.id,
        payload={"fields": list(data.keys())},
        request=request,
    )
    db.commit()
    db.refresh(row)
    return _serialize(row, org.membership.role)


@router.post("/{connection_id}/verify", response_model=PublishingConnectionRead)
def verify_connection(
    connection_id: uuid.UUID,
    request: Request,
    user: User = Depends(current_user),
    org: OrgContext = Depends(require_connection_admin),
    db: Session = Depends(get_session),
) -> PublishingConnectionRead:
    from datetime import UTC, datetime

    row = _get_or_404(db, org.organization_id, connection_id)
    provider = get_publishing_provider(row.provider.value)
    # MOCK/MANUAL "verification" is deterministic and offline; META raises
    # (adapter not active) which we surface as an ERROR connection state
    # rather than crashing the request.
    import asyncio

    from app.publishing.adapters import PublicationPayload

    try:
        result = asyncio.run(
            provider.validate(
                PublicationPayload(
                    publication_id="verify",
                    platform=row.platform.value,
                    publication_type="POST",
                    caption="verification ping",
                    title=None,
                    cta=None,
                )
            )
        )
        row.status = ConnectionStatus.ACTIVE if result.ok or row.provider.value in ("MOCK", "MANUAL") else ConnectionStatus.ERROR
    except Exception:
        row.status = ConnectionStatus.ERROR
    row.last_verified_at = datetime.now(UTC)
    db.flush()
    audit.record(
        db,
        action="publishing_connection.verified",
        actor_user_id=user.id,
        organization_id=org.organization_id,
        target_type="publishing_connection",
        target_id=row.id,
        payload={"result_status": row.status.value},
        request=request,
    )
    db.commit()
    db.refresh(row)
    return _serialize(row, org.membership.role)


@router.post("/{connection_id}/revoke", response_model=PublishingConnectionRead)
def revoke_connection(
    connection_id: uuid.UUID,
    request: Request,
    user: User = Depends(current_user),
    org: OrgContext = Depends(require_connection_admin),
    db: Session = Depends(get_session),
) -> PublishingConnectionRead:
    row = _get_or_404(db, org.organization_id, connection_id)
    row.status = ConnectionStatus.REVOKED
    row.credentials_encrypted = None
    db.flush()
    audit.record(
        db,
        action="publishing_connection.revoked",
        actor_user_id=user.id,
        organization_id=org.organization_id,
        target_type="publishing_connection",
        target_id=row.id,
        payload={},
        request=request,
    )
    db.commit()
    db.refresh(row)
    return _serialize(row, org.membership.role)


@router.post("/{connection_id}/disable", response_model=PublishingConnectionRead)
def disable_connection(
    connection_id: uuid.UUID,
    request: Request,
    user: User = Depends(current_user),
    org: OrgContext = Depends(require_connection_admin),
    db: Session = Depends(get_session),
) -> PublishingConnectionRead:
    row = _get_or_404(db, org.organization_id, connection_id)
    row.status = ConnectionStatus.DISABLED
    db.flush()
    audit.record(
        db,
        action="publishing_connection.disabled",
        actor_user_id=user.id,
        organization_id=org.organization_id,
        target_type="publishing_connection",
        target_id=row.id,
        payload={},
        request=request,
    )
    db.commit()
    db.refresh(row)
    return _serialize(row, org.membership.role)
