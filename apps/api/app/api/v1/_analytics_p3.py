"""Phase 3 analytics helpers + endpoints, imported by analytics.py.

Kept in a separate module for readability; the endpoints are attached to the
same router at import time.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from fastapi import Depends
from sqlalchemy import distinct, func, select
from sqlalchemy.orm import Session

from app.deps import OrgContext, current_org, get_session
from app.models.campaign import Campaign
from app.models.click import ClickEvent
from app.models.content import ContentItem
from app.models.editorial import EditorialCalendarItem
from app.models.enums import EditorialStatus, LeadStatus
from app.models.lead import Lead
from app.models.tracking import TrackingLink
from app.schemas.growth import (
    EditorialSummary,
    Funnel,
    LeadsCampaignRow,
    LeadsContentRow,
    LeadsLinkRow,
    LeadsSummary,
    Phase3Dashboard,
)


def safe_rate(numerator: int, denominator: int) -> float:
    if not denominator:
        return 0.0
    return round((numerator / denominator) * 100, 2)


def _week_bounds(now: datetime) -> tuple[datetime, datetime]:
    start = now - timedelta(days=now.weekday())
    start = start.replace(hour=0, minute=0, second=0, microsecond=0)
    return start, start + timedelta(days=7)


def _month_start(now: datetime) -> datetime:
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def editorial_summary_data(db: Session, org_id: uuid.UUID) -> EditorialSummary:
    now = datetime.now(UTC)
    week_start, week_end = _week_bounds(now)
    month_start = _month_start(now)

    pending = db.execute(
        select(func.count(EditorialCalendarItem.id)).where(
            EditorialCalendarItem.organization_id == org_id,
            EditorialCalendarItem.status.in_(
                [EditorialStatus.IN_REVIEW, EditorialStatus.NEEDS_REVISION]
            ),
        )
    ).scalar_one()

    scheduled_week = db.execute(
        select(func.count(EditorialCalendarItem.id)).where(
            EditorialCalendarItem.organization_id == org_id,
            EditorialCalendarItem.status == EditorialStatus.SCHEDULED,
            EditorialCalendarItem.scheduled_for >= week_start,
            EditorialCalendarItem.scheduled_for < week_end,
        )
    ).scalar_one()

    published_month = db.execute(
        select(func.count(EditorialCalendarItem.id)).where(
            EditorialCalendarItem.organization_id == org_id,
            EditorialCalendarItem.status == EditorialStatus.PUBLISHED,
            EditorialCalendarItem.published_at >= month_start,
        )
    ).scalar_one()

    upcoming_rows = db.execute(
        select(EditorialCalendarItem)
        .where(
            EditorialCalendarItem.organization_id == org_id,
            EditorialCalendarItem.status.in_(
                [EditorialStatus.APPROVED, EditorialStatus.SCHEDULED]
            ),
            EditorialCalendarItem.scheduled_for.is_not(None),
            EditorialCalendarItem.scheduled_for >= now,
        )
        .order_by(EditorialCalendarItem.scheduled_for.asc())
        .limit(10)
    ).scalars().all()

    upcoming = [
        {
            "id": str(r.id),
            "public_id": r.public_id,
            "platform": r.platform.value,
            "scheduled_for": r.scheduled_for.isoformat() if r.scheduled_for else None,
            "status": r.status.value,
            "content_item_id": str(r.content_item_id),
        }
        for r in upcoming_rows
    ]

    return EditorialSummary(
        pending_review=pending or 0,
        scheduled_this_week=scheduled_week or 0,
        published_this_month=published_month or 0,
        upcoming=upcoming,
    )


def _lead_status_count(db: Session, org_id: uuid.UUID, status: LeadStatus | None) -> int:
    stmt = select(func.count(Lead.id)).where(Lead.organization_id == org_id)
    if status is not None:
        stmt = stmt.where(Lead.status == status)
    return db.execute(stmt).scalar_one() or 0


def leads_summary_data(db: Session, org_id: uuid.UUID) -> LeadsSummary:
    total = _lead_status_count(db, org_id, None)
    new_leads = _lead_status_count(db, org_id, LeadStatus.NEW)
    qualified = _lead_status_count(db, org_id, LeadStatus.QUALIFIED)
    won = _lead_status_count(db, org_id, LeadStatus.WON)
    lost = _lead_status_count(db, org_id, LeadStatus.LOST)

    top_camp_rows = db.execute(
        select(Campaign, func.count(Lead.id).label("n"))
        .select_from(Campaign)
        .join(Lead, Lead.campaign_id == Campaign.id, isouter=True)
        .where(Campaign.organization_id == org_id)
        .group_by(Campaign.id)
        .order_by(func.count(Lead.id).desc())
        .limit(5)
    ).all()
    top_content_rows = db.execute(
        select(ContentItem, func.count(Lead.id).label("n"))
        .select_from(ContentItem)
        .join(Lead, Lead.content_item_id == ContentItem.id, isouter=True)
        .where(ContentItem.organization_id == org_id)
        .group_by(ContentItem.id)
        .order_by(func.count(Lead.id).desc())
        .limit(5)
    ).all()
    top_link_rows = db.execute(
        select(TrackingLink, func.count(Lead.id).label("n"))
        .select_from(TrackingLink)
        .join(Lead, Lead.tracking_link_id == TrackingLink.id, isouter=True)
        .where(TrackingLink.organization_id == org_id)
        .group_by(TrackingLink.id)
        .order_by(func.count(Lead.id).desc())
        .limit(5)
    ).all()

    return LeadsSummary(
        new_leads=new_leads,
        qualified_leads=qualified,
        won_leads=won,
        lost_leads=lost,
        total_leads=total,
        conversion_qualified_rate=safe_rate(qualified, total),
        conversion_won_rate=safe_rate(won, total),
        top_campaigns=[
            LeadsCampaignRow(campaign_id=c.id, campaign_name=c.name, leads=int(n or 0))
            for c, n in top_camp_rows
        ],
        top_contents=[
            LeadsContentRow(content_id=c.id, content_title=c.title, leads=int(n or 0))
            for c, n in top_content_rows
        ],
        top_links=[
            LeadsLinkRow(
                tracking_link_id=link.id, short_code=link.short_code, leads=int(n or 0)
            )
            for link, n in top_link_rows
        ],
    )


def funnel_data(
    db: Session,
    org_id: uuid.UUID,
    *,
    campaign_id: uuid.UUID | None = None,
    content_id: uuid.UUID | None = None,
    tracking_link_id: uuid.UUID | None = None,
) -> Funnel:
    click_stmt = (
        select(
            func.count(ClickEvent.id),
            func.count(distinct(ClickEvent.ip_hash)),
        )
        .select_from(ClickEvent)
        .join(TrackingLink, TrackingLink.id == ClickEvent.tracking_link_id)
        .where(ClickEvent.organization_id == org_id)
    )
    lead_stmt = select(Lead).where(Lead.organization_id == org_id)

    if campaign_id:
        click_stmt = click_stmt.where(TrackingLink.campaign_id == campaign_id)
        lead_stmt = lead_stmt.where(Lead.campaign_id == campaign_id)
    if content_id:
        click_stmt = click_stmt.where(TrackingLink.content_id == content_id)
        lead_stmt = lead_stmt.where(Lead.content_item_id == content_id)
    if tracking_link_id:
        click_stmt = click_stmt.where(TrackingLink.id == tracking_link_id)
        lead_stmt = lead_stmt.where(Lead.tracking_link_id == tracking_link_id)

    clicks, uniques = db.execute(click_stmt).one()
    leads = db.execute(lead_stmt).scalars().all()
    total_leads = len(leads)
    qualified = sum(
        1 for lead in leads if lead.status in (LeadStatus.QUALIFIED, LeadStatus.WON)
    )
    won = sum(1 for lead in leads if lead.status == LeadStatus.WON)

    return Funnel(
        clicks=clicks or 0,
        unique_visitors=uniques or 0,
        leads=total_leads,
        qualified_leads=qualified,
        won_leads=won,
        click_to_lead_rate=safe_rate(total_leads, clicks or 0),
        lead_to_won_rate=safe_rate(won, total_leads),
    )


def wire(router):
    """Attach phase-3 endpoints to the given router.

    Called at import time from ``analytics.py`` — keeping the wire step
    explicit avoids order-of-import surprises.
    """
    from app.api.v1.analytics import (
        _campaign_or_404,
        _content_or_404,
        _link_or_404,
    )

    @router.get("/editorial/summary", response_model=EditorialSummary)
    def editorial_summary(
        org: OrgContext = Depends(current_org),
        db: Session = Depends(get_session),
    ) -> EditorialSummary:
        return editorial_summary_data(db, org.organization_id)

    @router.get("/leads/summary", response_model=LeadsSummary)
    def leads_summary(
        org: OrgContext = Depends(current_org),
        db: Session = Depends(get_session),
    ) -> LeadsSummary:
        return leads_summary_data(db, org.organization_id)

    @router.get("/dashboard/phase3", response_model=Phase3Dashboard)
    def phase3_dashboard(
        org: OrgContext = Depends(current_org),
        db: Session = Depends(get_session),
    ) -> Phase3Dashboard:
        return Phase3Dashboard(
            editorial=editorial_summary_data(db, org.organization_id),
            leads=leads_summary_data(db, org.organization_id),
        )

    @router.get("/campaigns/{campaign_id}/funnel", response_model=Funnel)
    def campaign_funnel(
        campaign_id: uuid.UUID,
        org: OrgContext = Depends(current_org),
        db: Session = Depends(get_session),
    ) -> Funnel:
        _campaign_or_404(db, org.organization_id, campaign_id)
        return funnel_data(db, org.organization_id, campaign_id=campaign_id)

    @router.get("/content/{content_id}/funnel", response_model=Funnel)
    def content_funnel(
        content_id: uuid.UUID,
        org: OrgContext = Depends(current_org),
        db: Session = Depends(get_session),
    ) -> Funnel:
        _content_or_404(db, org.organization_id, content_id)
        return funnel_data(db, org.organization_id, content_id=content_id)

    @router.get("/tracking-links/{link_id}/funnel", response_model=Funnel)
    def link_funnel(
        link_id: uuid.UUID,
        org: OrgContext = Depends(current_org),
        db: Session = Depends(get_session),
    ) -> Funnel:
        _link_or_404(db, org.organization_id, link_id)
        return funnel_data(db, org.organization_id, tracking_link_id=link_id)
