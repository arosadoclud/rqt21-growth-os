"""Public lead capture.

- Unauthenticated. Rate-limited per IP.
- Requires exactly one attribution source to route the lead into an
  organization: ``tracking_code`` (an existing TrackingLink.short_code) or
  ``public_source_token`` (a PublicLeadSource.public_token minted by an admin
  for a specific landing page). The endpoint never accepts organization_id
  directly — that would let a caller enumerate/target arbitrary orgs.
- Honeypot: a hidden ``website`` field must be empty. If bots fill it, we
  accept the request cosmetically but do not store anything.
- Never reveal whether an email/tracking code/token already exists or is
  merely inactive — same generic error, same opaque success response.
- Dedup: within ``LEAD_DEDUP_WINDOW_MINUTES``, skip inserting a second row
  with the same contact channel for the same organization.
- IP is stored only as an HMAC hash (see app.utils.ip_hash); User-Agent is
  reduced to coarse device/browser/os buckets (see app.utils.ua) and kept in
  the CREATED activity's metadata, never as a raw fingerprint on the Lead row.
- Origin allowlisting (PublicLeadSource.allowed_origins) is defense in depth,
  not the primary security boundary — CORS alone does not stop server-to-
  server abuse, so rate limiting + honeypot + dedup still apply regardless.
"""

from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import or_, select

from app import audit, rate_limit
from app.core.config import settings
from app.core.db import SessionLocal
from app.models.ai import PublicLeadSource
from app.models.enums import LeadActivityType, LeadSource, LeadStatus
from app.models.lead import Lead, LeadActivity
from app.models.tracking import TrackingLink
from app.schemas.leads import PublicLeadAck, PublicLeadCreate
from app.utils.ip_hash import hash_ip
from app.utils.phone import InvalidPhoneNumber, normalize_phone, org_default_country
from app.utils.public_id import make as make_public_id
from app.utils.ua import classify

router = APIRouter(tags=["public-leads"])


def _mint_reference() -> str:
    return secrets.token_urlsafe(9)


def _client_ip(request: Request) -> str | None:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else None


def _origin_allowed(source: PublicLeadSource, request: Request) -> bool:
    if not source.allowed_origins:
        return True
    origin = request.headers.get("origin") or request.headers.get("referer") or ""
    return any(origin.startswith(o) for o in source.allowed_origins)


@router.post("/public/leads", response_model=PublicLeadAck, status_code=201)
def public_create_lead(payload: PublicLeadCreate, request: Request) -> PublicLeadAck:
    rate_limit.check_public_lead(request)

    # Honeypot: silently accept but do nothing.
    if payload.website:
        return PublicLeadAck(reference=_mint_reference(), accepted=True)

    if bool(payload.tracking_code) == bool(payload.public_source_token):
        # Neither provided, or both provided — reject ambiguity/absence.
        raise HTTPException(
            status_code=400,
            detail="exactly one of tracking_code or public_source_token is required",
        )

    with SessionLocal() as db:
        organization_id = None
        brand_id = product_id = campaign_id = content_id = tracking_link_id = None
        default_utm_source = default_utm_medium = default_utm_campaign = None

        if payload.tracking_code:
            link = db.execute(
                select(TrackingLink).where(TrackingLink.short_code == payload.tracking_code)
            ).scalar_one_or_none()
            if link is None or not link.is_active:
                raise HTTPException(status_code=400, detail="attribution source invalid")
            organization_id = link.organization_id
            brand_id, product_id, campaign_id, content_id = (
                link.brand_id,
                link.product_id,
                link.campaign_id,
                link.content_id,
            )
            tracking_link_id = link.id
            default_utm_source = link.utm_source
            default_utm_medium = link.utm_medium
            default_utm_campaign = link.utm_campaign
            default_utm_content = link.utm_content
            default_utm_term = link.utm_term
        else:
            source_row = db.execute(
                select(PublicLeadSource).where(
                    PublicLeadSource.public_token == payload.public_source_token
                )
            ).scalar_one_or_none()
            if (
                source_row is None
                or not source_row.is_active
                or (
                    source_row.expires_at is not None
                    and source_row.expires_at < datetime.now(UTC)
                )
            ):
                # Same generic error whether the token is unknown, inactive, or expired.
                raise HTTPException(status_code=400, detail="attribution source invalid")
            if not _origin_allowed(source_row, request):
                raise HTTPException(status_code=400, detail="attribution source invalid")
            organization_id = source_row.organization_id
            brand_id, product_id, campaign_id = (
                source_row.brand_id,
                source_row.product_id,
                source_row.campaign_id,
            )
            default_utm_source = source_row.default_utm_source
            default_utm_medium = source_row.default_utm_medium
            default_utm_campaign = source_row.default_utm_campaign
            default_utm_content = None
            default_utm_term = None

        try:
            country_code = org_default_country(db, organization_id)
            phone = normalize_phone(payload.phone, country_code)
            whatsapp = normalize_phone(payload.whatsapp, country_code)
        except InvalidPhoneNumber:
            # Public form: don't leak validation internals — generic 400.
            raise HTTPException(status_code=400, detail="invalid contact information") from None

        # Dedup: same org + any matching contact channel within window.
        window_start = datetime.now(UTC) - timedelta(
            minutes=settings.lead_dedup_window_minutes
        )
        contact_matches = []
        if payload.email:
            contact_matches.append(Lead.email == payload.email)
        if phone:
            contact_matches.append(Lead.phone == phone)
        if whatsapp:
            contact_matches.append(Lead.whatsapp == whatsapp)

        existing = None
        if contact_matches:
            existing = db.execute(
                select(Lead).where(
                    Lead.organization_id == organization_id,
                    Lead.created_at >= window_start,
                    or_(*contact_matches),
                )
            ).scalar_one_or_none()

        if existing is not None:
            # Same visitor within the dedup window: don't duplicate, but still
            # return a positive-looking ack — the client mustn't be able to
            # probe for duplicates.
            return PublicLeadAck(reference=_mint_reference(), accepted=True)

        utm_source = default_utm_source or payload.utm_source
        utm_medium = default_utm_medium or payload.utm_medium
        utm_campaign = default_utm_campaign or payload.utm_campaign
        utm_content = default_utm_content or payload.utm_content
        utm_term = default_utm_term or payload.utm_term

        row = Lead(
            organization_id=organization_id,
            public_id=make_public_id("ld"),
            brand_id=brand_id,
            product_id=product_id,
            campaign_id=campaign_id,
            content_item_id=content_id,
            tracking_link_id=tracking_link_id,
            first_name=payload.first_name,
            last_name=payload.last_name,
            email=payload.email,
            phone=phone,
            whatsapp=whatsapp,
            source=payload.source or LeadSource.LANDING_PAGE,
            status=LeadStatus.NEW,
            country=payload.country,
            city=payload.city,
            notes=payload.notes,
            utm_source=utm_source,
            utm_medium=utm_medium,
            utm_campaign=utm_campaign,
            utm_content=utm_content,
            utm_term=utm_term,
        )
        db.add(row)
        db.flush()

        device, browser, os_name = classify(request.headers.get("user-agent"))
        db.add(
            LeadActivity(
                public_id=make_public_id("la"),
                organization_id=organization_id,
                lead_id=row.id,
                actor_user_id=None,
                activity_type=LeadActivityType.CREATED,
                description="Public capture",
                activity_metadata={
                    "channel": "tracking_link" if tracking_link_id else "public_source",
                    "utm_source": utm_source,
                    "utm_campaign": utm_campaign,
                    "ip_hash": hash_ip(_client_ip(request)),
                    "device_type": device,
                    "browser": browser,
                    "os": os_name,
                },
            )
        )

        audit.record(
            db,
            action="lead.created",
            actor_user_id=None,
            organization_id=organization_id,
            target_type="lead",
            target_id=row.id,
            payload={
                "public_id": row.public_id,
                "channel": "public",
                "tracking_link_id": str(tracking_link_id) if tracking_link_id else None,
            },
            request=request,
        )
        db.commit()
        return PublicLeadAck(reference=_mint_reference(), accepted=True)
