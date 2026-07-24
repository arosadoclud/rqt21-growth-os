from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import audit
from app.deps import (
    OrgContext,
    current_org,
    current_user,
    get_session,
    require_content_approval,
    require_editorial_write,
)
from app.models.content import ContentItem
from app.models.editorial import Review
from app.models.enums import ContentStatus, ReviewDecision, ReviewType
from app.models.user import User
from app.schemas.editorial import ReviewActionRequest, ReviewCreate, ReviewRead
from app.utils.public_id import make as make_public_id

router = APIRouter(prefix="/content-items/{content_id}", tags=["reviews"])


def _content_or_404(db: Session, org_id: uuid.UUID, content_id: uuid.UUID) -> ContentItem:
    c = db.execute(
        select(ContentItem).where(
            ContentItem.id == content_id, ContentItem.organization_id == org_id
        )
    ).scalar_one_or_none()
    if c is None:
        raise HTTPException(status_code=404, detail="content not found")
    return c


@router.get("/reviews", response_model=list[ReviewRead])
def list_reviews(
    content_id: uuid.UUID,
    org: OrgContext = Depends(current_org),
    db: Session = Depends(get_session),
) -> list[ReviewRead]:
    _content_or_404(db, org.organization_id, content_id)
    rows = (
        db.execute(
            select(Review)
            .where(
                Review.organization_id == org.organization_id,
                Review.content_item_id == content_id,
            )
            .order_by(Review.created_at.desc())
        )
        .scalars()
        .all()
    )
    return [ReviewRead.model_validate(r) for r in rows]


def _create_review(
    db: Session,
    *,
    org_id: uuid.UUID,
    content_id: uuid.UUID,
    reviewer_id: uuid.UUID | None,
    review_type: ReviewType,
    decision: ReviewDecision,
    score: int | None,
    comment: str | None,
) -> Review:
    r = Review(
        organization_id=org_id,
        public_id=make_public_id("rv"),
        content_item_id=content_id,
        reviewer_user_id=reviewer_id,
        review_type=review_type,
        decision=decision,
        score=score,
        comment=comment,
    )
    db.add(r)
    db.flush()
    return r


@router.post("/reviews", response_model=ReviewRead, status_code=201)
def create_review(
    content_id: uuid.UUID,
    payload: ReviewCreate,
    request: Request,
    user: User = Depends(current_user),
    org: OrgContext = Depends(require_editorial_write),
    db: Session = Depends(get_session),
) -> ReviewRead:
    _content_or_404(db, org.organization_id, content_id)
    r = _create_review(
        db,
        org_id=org.organization_id,
        content_id=content_id,
        reviewer_id=user.id,
        review_type=payload.review_type,
        decision=payload.decision,
        score=payload.score,
        comment=payload.comment,
    )
    audit.record(
        db,
        action="review.created",
        actor_user_id=user.id,
        organization_id=org.organization_id,
        target_type="review",
        target_id=r.id,
        payload={
            "content_id": str(content_id),
            "decision": r.decision.value,
            "review_type": r.review_type.value,
        },
        request=request,
    )
    db.commit()
    db.refresh(r)
    return ReviewRead.model_validate(r)


@router.post("/submit-review", response_model=ReviewRead, status_code=201)
def submit_for_review(
    content_id: uuid.UUID,
    payload: ReviewActionRequest,
    request: Request,
    user: User = Depends(current_user),
    org: OrgContext = Depends(require_editorial_write),
    db: Session = Depends(get_session),
) -> ReviewRead:
    content = _content_or_404(db, org.organization_id, content_id)
    # Log an explicit review event with decision NEEDS_REVISION acting as
    # "please look at this" (there is no plain 'PENDING' decision).
    r = _create_review(
        db,
        org_id=org.organization_id,
        content_id=content_id,
        reviewer_id=user.id,
        review_type=payload.review_type,
        decision=ReviewDecision.NEEDS_REVISION,
        score=payload.score,
        comment=payload.comment or "Submitted for review",
    )
    if content.status in (ContentStatus.DRAFT, ContentStatus.SCHEDULED):
        pass  # no schema field for editorial status on ContentItem yet
    audit.record(
        db,
        action="content.submitted_for_review",
        actor_user_id=user.id,
        organization_id=org.organization_id,
        target_type="content",
        target_id=content.id,
        payload={"review_id": str(r.id)},
        request=request,
    )
    db.commit()
    db.refresh(r)
    return ReviewRead.model_validate(r)


@router.post("/approve", response_model=ReviewRead, status_code=201)
def approve_content(
    content_id: uuid.UUID,
    payload: ReviewActionRequest,
    request: Request,
    user: User = Depends(current_user),
    org: OrgContext = Depends(require_content_approval),
    db: Session = Depends(get_session),
) -> ReviewRead:
    content = _content_or_404(db, org.organization_id, content_id)
    r = _create_review(
        db,
        org_id=org.organization_id,
        content_id=content_id,
        reviewer_id=user.id,
        review_type=payload.review_type,
        decision=ReviewDecision.APPROVED,
        score=payload.score,
        comment=payload.comment,
    )
    audit.record(
        db,
        action="content.approved",
        actor_user_id=user.id,
        organization_id=org.organization_id,
        target_type="content",
        target_id=content_id,
        payload={"review_id": str(r.id)},
        request=request,
    )

    from app.automation.engine import TriggerContext, run_triggers
    from app.models.enums import AutomationTriggerType

    run_triggers(
        db,
        organization_id=org.organization_id,
        trigger_type=AutomationTriggerType.CONTENT_APPROVED,
        context=TriggerContext(
            brand_id=content.brand_id,
            content_item_id=content.id,
            campaign_id=content.campaign_id,
            product_id=content.product_id,
            actor_user_id=user.id,
        ),
        request=request,
    )

    db.commit()
    db.refresh(r)
    return ReviewRead.model_validate(r)


@router.post("/request-changes", response_model=ReviewRead, status_code=201)
def request_changes(
    content_id: uuid.UUID,
    payload: ReviewActionRequest,
    request: Request,
    user: User = Depends(current_user),
    org: OrgContext = Depends(require_content_approval),
    db: Session = Depends(get_session),
) -> ReviewRead:
    _content_or_404(db, org.organization_id, content_id)
    r = _create_review(
        db,
        org_id=org.organization_id,
        content_id=content_id,
        reviewer_id=user.id,
        review_type=payload.review_type,
        decision=ReviewDecision.NEEDS_REVISION,
        score=payload.score,
        comment=payload.comment,
    )
    audit.record(
        db,
        action="content.changes_requested",
        actor_user_id=user.id,
        organization_id=org.organization_id,
        target_type="content",
        target_id=content_id,
        payload={"review_id": str(r.id)},
        request=request,
    )
    db.commit()
    db.refresh(r)
    return ReviewRead.model_validate(r)


@router.post("/reject", response_model=ReviewRead, status_code=201)
def reject_content(
    content_id: uuid.UUID,
    payload: ReviewActionRequest,
    request: Request,
    user: User = Depends(current_user),
    org: OrgContext = Depends(require_content_approval),
    db: Session = Depends(get_session),
) -> ReviewRead:
    _content_or_404(db, org.organization_id, content_id)
    r = _create_review(
        db,
        org_id=org.organization_id,
        content_id=content_id,
        reviewer_id=user.id,
        review_type=payload.review_type,
        decision=ReviewDecision.REJECTED,
        score=payload.score,
        comment=payload.comment,
    )
    audit.record(
        db,
        action="content.rejected",
        actor_user_id=user.id,
        organization_id=org.organization_id,
        target_type="content",
        target_id=content_id,
        payload={"review_id": str(r.id)},
        request=request,
    )
    db.commit()
    db.refresh(r)
    return ReviewRead.model_validate(r)
