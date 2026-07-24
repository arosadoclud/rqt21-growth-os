from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import distinct, func, select
from sqlalchemy.orm import Session

from app.deps import OrgContext, current_org, get_session
from app.models.campaign import Campaign
from app.models.click import ClickEvent
from app.models.content import ContentItem
from app.models.tracking import TrackingLink
from app.schemas.growth import (
    CampaignSummary,
    ClickRow,
    ContentSummary,
    DashboardSummary,
)

router = APIRouter(prefix="/analytics", tags=["analytics"])


def _campaign_or_404(db: Session, org_id: uuid.UUID, campaign_id: uuid.UUID) -> Campaign:
    c = db.execute(
        select(Campaign).where(
            Campaign.id == campaign_id, Campaign.organization_id == org_id
        )
    ).scalar_one_or_none()
    if c is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="campaign not found")
    return c


def _content_or_404(db: Session, org_id: uuid.UUID, content_id: uuid.UUID) -> ContentItem:
    c = db.execute(
        select(ContentItem).where(
            ContentItem.id == content_id, ContentItem.organization_id == org_id
        )
    ).scalar_one_or_none()
    if c is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="content not found")
    return c


def _link_or_404(db: Session, org_id: uuid.UUID, link_id: uuid.UUID) -> TrackingLink:
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


def _campaign_summary(db: Session, org_id: uuid.UUID, campaign: Campaign) -> CampaignSummary:
    q_clicks = (
        select(
            func.count(ClickEvent.id),
            func.count(distinct(ClickEvent.ip_hash)),
        )
        .select_from(ClickEvent)
        .join(TrackingLink, TrackingLink.id == ClickEvent.tracking_link_id)
        .where(TrackingLink.campaign_id == campaign.id)
        .where(ClickEvent.organization_id == org_id)
    )
    total, uniques = db.execute(q_clicks).one()

    active_links = db.execute(
        select(func.count(TrackingLink.id)).where(
            TrackingLink.campaign_id == campaign.id,
            TrackingLink.organization_id == org_id,
            TrackingLink.is_active.is_(True),
        )
    ).scalar_one()

    content_count = db.execute(
        select(func.count(ContentItem.id)).where(
            ContentItem.campaign_id == campaign.id,
            ContentItem.organization_id == org_id,
        )
    ).scalar_one()

    return CampaignSummary(
        campaign_id=campaign.id,
        campaign_name=campaign.name,
        total_clicks=total or 0,
        unique_visitors=uniques or 0,
        active_links=active_links or 0,
        content_count=content_count or 0,
    )


def _content_summary(db: Session, org_id: uuid.UUID, content: ContentItem) -> ContentSummary:
    q_clicks = (
        select(
            func.count(ClickEvent.id),
            func.count(distinct(ClickEvent.ip_hash)),
        )
        .select_from(ClickEvent)
        .join(TrackingLink, TrackingLink.id == ClickEvent.tracking_link_id)
        .where(TrackingLink.content_id == content.id)
        .where(ClickEvent.organization_id == org_id)
    )
    total, uniques = db.execute(q_clicks).one()

    active_links = db.execute(
        select(func.count(TrackingLink.id)).where(
            TrackingLink.content_id == content.id,
            TrackingLink.organization_id == org_id,
            TrackingLink.is_active.is_(True),
        )
    ).scalar_one()

    return ContentSummary(
        content_id=content.id,
        content_title=content.title,
        total_clicks=total or 0,
        unique_visitors=uniques or 0,
        active_links=active_links or 0,
    )


@router.get("/campaigns/{campaign_id}/summary", response_model=CampaignSummary)
def campaign_summary(
    campaign_id: uuid.UUID,
    org: OrgContext = Depends(current_org),
    db: Session = Depends(get_session),
) -> CampaignSummary:
    c = _campaign_or_404(db, org.organization_id, campaign_id)
    return _campaign_summary(db, org.organization_id, c)


@router.get("/content/{content_id}/summary", response_model=ContentSummary)
def content_summary(
    content_id: uuid.UUID,
    org: OrgContext = Depends(current_org),
    db: Session = Depends(get_session),
) -> ContentSummary:
    c = _content_or_404(db, org.organization_id, content_id)
    return _content_summary(db, org.organization_id, c)


@router.get("/tracking-links/{link_id}/clicks", response_model=list[ClickRow])
def link_clicks(
    link_id: uuid.UUID,
    limit: int = Query(default=100, ge=1, le=1000),
    org: OrgContext = Depends(current_org),
    db: Session = Depends(get_session),
) -> list[ClickRow]:
    _link_or_404(db, org.organization_id, link_id)
    rows = (
        db.execute(
            select(ClickEvent)
            .where(
                ClickEvent.tracking_link_id == link_id,
                ClickEvent.organization_id == org.organization_id,
            )
            .order_by(ClickEvent.occurred_at.desc())
            .limit(limit)
        )
        .scalars()
        .all()
    )
    return [
        ClickRow(
            id=r.id,
            occurred_at=r.occurred_at,
            referrer=r.referrer,
            device_type=r.device_type,
            browser=r.browser,
            os=r.os,
            country=r.country,
            query_params=r.query_params,
        )
        for r in rows
    ]


@router.get("/dashboard/summary", response_model=DashboardSummary)
def dashboard_summary(
    org: OrgContext = Depends(current_org),
    db: Session = Depends(get_session),
) -> DashboardSummary:
    org_id = org.organization_id
    campaigns_total = db.execute(
        select(func.count(Campaign.id)).where(Campaign.organization_id == org_id)
    ).scalar_one()
    contents_total = db.execute(
        select(func.count(ContentItem.id)).where(ContentItem.organization_id == org_id)
    ).scalar_one()
    active_links = db.execute(
        select(func.count(TrackingLink.id)).where(
            TrackingLink.organization_id == org_id, TrackingLink.is_active.is_(True)
        )
    ).scalar_one()
    clicks_total = db.execute(
        select(func.count(ClickEvent.id)).where(ClickEvent.organization_id == org_id)
    ).scalar_one()

    # Top 5 campaigns by clicks.
    top_campaigns_stmt = (
        select(Campaign, func.count(ClickEvent.id).label("clicks"))
        .select_from(Campaign)
        .join(TrackingLink, TrackingLink.campaign_id == Campaign.id, isouter=True)
        .join(ClickEvent, ClickEvent.tracking_link_id == TrackingLink.id, isouter=True)
        .where(Campaign.organization_id == org_id)
        .group_by(Campaign.id)
        .order_by(func.count(ClickEvent.id).desc())
        .limit(5)
    )
    top_campaigns = [
        _campaign_summary(db, org_id, c) for c, _ in db.execute(top_campaigns_stmt).all()
    ]

    top_contents_stmt = (
        select(ContentItem, func.count(ClickEvent.id).label("clicks"))
        .select_from(ContentItem)
        .join(TrackingLink, TrackingLink.content_id == ContentItem.id, isouter=True)
        .join(ClickEvent, ClickEvent.tracking_link_id == TrackingLink.id, isouter=True)
        .where(ContentItem.organization_id == org_id)
        .group_by(ContentItem.id)
        .order_by(func.count(ClickEvent.id).desc())
        .limit(5)
    )
    top_contents = [
        _content_summary(db, org_id, c) for c, _ in db.execute(top_contents_stmt).all()
    ]

    return DashboardSummary(
        campaigns_total=campaigns_total,
        contents_total=contents_total,
        active_links=active_links,
        clicks_total=clicks_total,
        top_campaigns=top_campaigns,
        top_contents=top_contents,
    )


from app.api.v1._analytics_p3 import wire as _wire_p3  # noqa: E402 — depends on helpers above

_wire_p3(router)

