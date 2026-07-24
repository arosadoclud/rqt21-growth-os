from __future__ import annotations

import asyncio
import time
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import audit
from app.ai import budget
from app.ai.council import aggregate, run_council
from app.ai.prompts import render_prompt
from app.ai.queue import InlineJobQueue, get_job_queue
from app.ai.runner import run_generation_job
from app.ai.templates import get_active_template
from app.core.config import settings
from app.deps import (
    OrgContext,
    current_org,
    current_user,
    get_session,
    require_ai_generate,
    require_ai_review,
)
from app.models.ai import BrandVoiceProfile, CouncilReview, GenerationJob
from app.models.brand import Brand
from app.models.campaign import Campaign
from app.models.content import ContentItem
from app.models.enums import (
    AIProvider,
    ContentStatus,
    ContentType,
    GenerationStatus,
    GenerationType,
    SourceSystem,
)
from app.models.product import Product
from app.models.user import User
from app.schemas.ai import (
    CouncilDecisionResult,
    CouncilReviewRead,
    CreateContentFromJob,
    GenerationJobCreate,
    GenerationJobRead,
    serialize_job_for_role,
)
from app.schemas.growth import ContentRead
from app.utils.public_id import make as make_public_id
from app.workers.rq_tasks import run_generation_job_task

router = APIRouter(prefix="/generation-jobs", tags=["generation-jobs"])


_CONTENT_TYPE_MAP = {
    GenerationType.SOCIAL_POST: ContentType.POST,
    GenerationType.REEL_SCRIPT: ContentType.REEL,
    GenerationType.CAROUSEL: ContentType.POST,
    GenerationType.EMAIL: ContentType.OTHER,
    GenerationType.BLOG_OUTLINE: ContentType.ARTICLE,
    GenerationType.BLOG_ARTICLE: ContentType.ARTICLE,
    GenerationType.CTA_VARIATIONS: ContentType.OTHER,
    GenerationType.CONTENT_IDEAS: ContentType.OTHER,
}


def _get_or_404(db: Session, org_id: uuid.UUID, job_id: uuid.UUID) -> GenerationJob:
    job = db.execute(
        select(GenerationJob).where(
            GenerationJob.id == job_id, GenerationJob.organization_id == org_id
        )
    ).scalar_one_or_none()
    if job is None:
        raise HTTPException(status_code=404, detail="generation job not found")
    return job


def _run_now(job_id: uuid.UUID, db: Session) -> None:
    """Run the job via whichever JobQueue backend is configured.

    Inline (default): executes synchronously in-process, response reflects
    the final status immediately — unchanged since Phase 4.

    Redis (QUEUE_BACKEND=redis, Phase 6A): enqueues onto RQ for a separate
    ``rq worker`` process to execute, then waits (bounded) for the DB row to
    leave QUEUED so the endpoint's response contract stays identical either
    way. This still exercises the real distributed path — a different
    process does the work — it just keeps this request synchronous rather
    than returning 202/polling, matching the product's existing UX.
    """
    queue = get_job_queue(
        queue_name="ai-generation",
        task=run_generation_job_task,
        inline_runner=run_generation_job,
    )
    asyncio.run(queue.enqueue(job_id))
    if isinstance(queue, InlineJobQueue):
        return

    deadline = time.monotonic() + settings.ai_request_timeout_seconds + 10
    while time.monotonic() < deadline:
        db.expire_all()
        current = db.get(GenerationJob, job_id)
        if current is not None and current.status != GenerationStatus.QUEUED:
            return
        time.sleep(0.5)


@router.get("", response_model=list[GenerationJobRead])
def list_jobs(
    status_filter: GenerationStatus | None = Query(default=None, alias="status"),
    generation_type: GenerationType | None = None,
    provider: AIProvider | None = None,
    brand_id: uuid.UUID | None = None,
    campaign_id: uuid.UUID | None = None,
    requested_by: uuid.UUID | None = Query(default=None),
    created_after: datetime | None = None,
    created_before: datetime | None = None,
    org: OrgContext = Depends(current_org),
    db: Session = Depends(get_session),
) -> list[GenerationJobRead]:
    stmt = (
        select(GenerationJob)
        .where(GenerationJob.organization_id == org.organization_id)
        .order_by(GenerationJob.created_at.desc())
        .limit(200)
    )
    if status_filter:
        stmt = stmt.where(GenerationJob.status == status_filter)
    if generation_type:
        stmt = stmt.where(GenerationJob.generation_type == generation_type)
    if provider:
        stmt = stmt.where(GenerationJob.provider == provider)
    if brand_id:
        stmt = stmt.where(GenerationJob.brand_id == brand_id)
    if campaign_id:
        stmt = stmt.where(GenerationJob.campaign_id == campaign_id)
    if requested_by:
        stmt = stmt.where(GenerationJob.requested_by_user_id == requested_by)
    if created_after:
        stmt = stmt.where(GenerationJob.created_at >= created_after)
    if created_before:
        stmt = stmt.where(GenerationJob.created_at <= created_before)
    rows = db.execute(stmt).scalars().all()
    return [serialize_job_for_role(j, org.membership.role) for j in rows]


@router.post("", response_model=GenerationJobRead, status_code=201)
def create_job(
    payload: GenerationJobCreate,
    request: Request,
    user: User = Depends(current_user),
    org: OrgContext = Depends(require_ai_generate),
    db: Session = Depends(get_session),
) -> GenerationJobRead:
    brand = db.execute(
        select(Brand).where(
            Brand.id == payload.brand_id, Brand.organization_id == org.organization_id
        )
    ).scalar_one_or_none()
    if brand is None:
        raise HTTPException(status_code=400, detail="brand not found in organization")
    for model, val, label in (
        (Product, payload.product_id, "product"),
        (Campaign, payload.campaign_id, "campaign"),
    ):
        if val is None:
            continue
        ok = db.execute(
            select(model.id).where(
                model.id == val, model.organization_id == org.organization_id
            )
        ).scalar_one_or_none()
        if ok is None:
            raise HTTPException(status_code=400, detail=f"{label} not found in organization")

    # Idempotency: replaying the same key returns the existing job untouched.
    if payload.idempotency_key:
        existing = db.execute(
            select(GenerationJob).where(
                GenerationJob.organization_id == org.organization_id,
                GenerationJob.idempotency_key == payload.idempotency_key,
            )
        ).scalar_one_or_none()
        if existing is not None:
            return serialize_job_for_role(existing, org.membership.role)

    try:
        budget.enforce(db, org.organization_id, user.id)
    except budget.BudgetExceeded as exc:
        audit.record(
            db,
            action="ai.budget_exceeded",
            actor_user_id=user.id,
            organization_id=org.organization_id,
            target_type="generation_job",
            target_id=None,
            payload={"reason": exc.reason, "generation_type": payload.generation_type.value},
            request=request,
        )
        db.commit()
        raise HTTPException(status_code=402, detail=exc.reason) from exc

    template = get_active_template(db, org.organization_id, payload.generation_type)
    brand_voice = db.execute(
        select(BrandVoiceProfile).where(
            BrandVoiceProfile.organization_id == org.organization_id,
            BrandVoiceProfile.brand_id == payload.brand_id,
        )
    ).scalar_one_or_none()
    system, user_prompt = render_prompt(template, brand_voice, payload.input, brand.name)

    try:
        provider = AIProvider(settings.ai_provider)
    except ValueError:
        provider = AIProvider.MOCK

    job = GenerationJob(
        organization_id=org.organization_id,
        public_id=make_public_id("gj"),
        brand_id=payload.brand_id,
        product_id=payload.product_id,
        campaign_id=payload.campaign_id,
        requested_by_user_id=user.id,
        generation_type=payload.generation_type,
        status=GenerationStatus.QUEUED,
        provider=provider,
        model=settings.ai_model,
        prompt_version=template.version,
        input_payload={
            "system": system,
            "user": user_prompt,
            "raw_input": payload.input.model_dump(),
        },
        idempotency_key=payload.idempotency_key,
    )
    db.add(job)
    db.flush()
    audit.record(
        db,
        action="generation_job.created",
        actor_user_id=user.id,
        organization_id=org.organization_id,
        target_type="generation_job",
        target_id=job.id,
        payload={
            "generation_type": job.generation_type.value,
            "provider": job.provider.value,
            "prompt_version": job.prompt_version,
        },
        request=request,
    )
    db.commit()
    job_id = job.id

    _run_now(job_id, db)

    db.expire_all()
    fresh = _get_or_404(db, org.organization_id, job_id)
    return serialize_job_for_role(fresh, org.membership.role)


@router.get("/{job_id}", response_model=GenerationJobRead)
def get_job(
    job_id: uuid.UUID,
    org: OrgContext = Depends(current_org),
    db: Session = Depends(get_session),
) -> GenerationJobRead:
    return serialize_job_for_role(_get_or_404(db, org.organization_id, job_id), org.membership.role)


@router.post("/{job_id}/cancel", response_model=GenerationJobRead)
def cancel_job(
    job_id: uuid.UUID,
    request: Request,
    user: User = Depends(current_user),
    org: OrgContext = Depends(require_ai_generate),
    db: Session = Depends(get_session),
) -> GenerationJobRead:
    job = _get_or_404(db, org.organization_id, job_id)
    if job.status not in (GenerationStatus.QUEUED, GenerationStatus.RUNNING):
        raise HTTPException(
            status_code=400, detail="only QUEUED or RUNNING jobs can be cancelled"
        )
    job.status = GenerationStatus.CANCELLED
    job.completed_at = datetime.now(UTC)
    db.flush()
    audit.record(
        db,
        action="generation_job.cancelled",
        actor_user_id=user.id,
        organization_id=org.organization_id,
        target_type="generation_job",
        target_id=job.id,
        payload={},
        request=request,
    )
    db.commit()
    db.refresh(job)
    return serialize_job_for_role(job, org.membership.role)


@router.post("/{job_id}/retry", response_model=GenerationJobRead)
def retry_job(
    job_id: uuid.UUID,
    request: Request,
    user: User = Depends(current_user),
    org: OrgContext = Depends(require_ai_generate),
    db: Session = Depends(get_session),
) -> GenerationJobRead:
    original = _get_or_404(db, org.organization_id, job_id)
    if original.status != GenerationStatus.FAILED:
        raise HTTPException(status_code=400, detail="only FAILED jobs can be retried")

    try:
        budget.enforce(db, org.organization_id, user.id)
    except budget.BudgetExceeded as exc:
        audit.record(
            db,
            action="ai.budget_exceeded",
            actor_user_id=user.id,
            organization_id=org.organization_id,
            target_type="generation_job",
            target_id=original.id,
            payload={"reason": exc.reason, "retry_of": str(original.id)},
            request=request,
        )
        db.commit()
        raise HTTPException(status_code=402, detail=exc.reason) from exc

    retry = GenerationJob(
        organization_id=org.organization_id,
        public_id=make_public_id("gj"),
        brand_id=original.brand_id,
        product_id=original.product_id,
        campaign_id=original.campaign_id,
        requested_by_user_id=user.id,
        generation_type=original.generation_type,
        status=GenerationStatus.QUEUED,
        provider=original.provider,
        model=original.model,
        prompt_version=original.prompt_version,
        input_payload=original.input_payload,
        retry_of_job_id=original.id,
    )
    db.add(retry)
    db.flush()
    audit.record(
        db,
        action="generation_job.retried",
        actor_user_id=user.id,
        organization_id=org.organization_id,
        target_type="generation_job",
        target_id=retry.id,
        payload={"retry_of_job_id": str(original.id)},
        request=request,
    )
    db.commit()
    retry_id = retry.id

    _run_now(retry_id, db)

    db.expire_all()
    fresh = _get_or_404(db, org.organization_id, retry_id)
    return serialize_job_for_role(fresh, org.membership.role)


def _council_result(rows: list[CouncilReview]) -> CouncilDecisionResult:
    from app.ai.council import ReviewerOutcome

    outcomes = [
        ReviewerOutcome(
            reviewer_type=r.reviewer_type,
            score=r.score,
            decision=r.decision,
            summary=r.summary,
            issues=list(r.issues),
            recommendations=list(r.recommendations),
            blocking_issues=list(r.blocking_issues),
        )
        for r in rows
    ]
    score, decision, blocking = aggregate(outcomes)
    issues = [i for o in outcomes for i in o.issues]
    recommendations = [rec for o in outcomes for rec in o.recommendations]
    return CouncilDecisionResult(
        score=score,
        decision=decision,
        reviews=[CouncilReviewRead.model_validate(r) for r in rows],
        issues=issues,
        recommendations=recommendations,
        blocking_issues=blocking,
        created_at=rows[0].created_at if rows else datetime.now(UTC),
    )


@router.post("/{job_id}/run-council", response_model=CouncilDecisionResult)
def run_council_endpoint(
    job_id: uuid.UUID,
    request: Request,
    user: User = Depends(current_user),
    org: OrgContext = Depends(require_ai_review),
    db: Session = Depends(get_session),
) -> CouncilDecisionResult:
    job = _get_or_404(db, org.organization_id, job_id)
    if job.status != GenerationStatus.COMPLETED or not job.output_payload:
        raise HTTPException(
            status_code=400, detail="council can only run on a COMPLETED job with output"
        )

    existing = db.execute(
        select(CouncilReview)
        .where(CouncilReview.generation_job_id == job.id)
        .order_by(CouncilReview.created_at.asc())
    ).scalars().all()
    if existing:
        # Idempotent: council already ran for this job — don't duplicate.
        return _council_result(existing)

    from app.schemas.ai import GeneratedContent

    content = GeneratedContent.model_validate(job.output_payload)
    brand_voice = db.execute(
        select(BrandVoiceProfile).where(
            BrandVoiceProfile.organization_id == org.organization_id,
            BrandVoiceProfile.brand_id == job.brand_id,
        )
    ).scalar_one_or_none()

    audit.record(
        db,
        action="generation_job.council_started",
        actor_user_id=user.id,
        organization_id=org.organization_id,
        target_type="generation_job",
        target_id=job.id,
        payload={},
        request=request,
    )
    db.commit()

    raw_input = (job.input_payload or {}).get("raw_input", {})
    outcomes = run_council(
        content,
        topic=raw_input.get("topic", ""),
        forbidden_terms=brand_voice.forbidden_terms if brand_voice else [],
        preferred_terms=brand_voice.preferred_terms if brand_voice else [],
        cta_style=brand_voice.cta_style if brand_voice else "",
    )

    rows: list[CouncilReview] = []
    for outcome in outcomes:
        row = CouncilReview(
            public_id=make_public_id("cr"),
            organization_id=org.organization_id,
            generation_job_id=job.id,
            content_item_id=job.content_item_id,
            reviewer_type=outcome.reviewer_type,
            score=outcome.score,
            decision=outcome.decision,
            summary=outcome.summary,
            issues=outcome.issues,
            recommendations=outcome.recommendations,
            blocking_issues=outcome.blocking_issues,
        )
        db.add(row)
        rows.append(row)
    db.flush()

    audit.record(
        db,
        action="generation_job.council_completed",
        actor_user_id=user.id,
        organization_id=org.organization_id,
        target_type="generation_job",
        target_id=job.id,
        payload={
            "avg_score": sum(o.score for o in outcomes) / len(outcomes),
            "blocking": bool([i for o in outcomes for i in o.blocking_issues]),
        },
        request=request,
    )
    db.commit()
    for r in rows:
        db.refresh(r)
    return _council_result(rows)


@router.get("/{job_id}/council", response_model=CouncilDecisionResult)
def get_council(
    job_id: uuid.UUID,
    org: OrgContext = Depends(current_org),
    db: Session = Depends(get_session),
) -> CouncilDecisionResult:
    job = _get_or_404(db, org.organization_id, job_id)
    rows = db.execute(
        select(CouncilReview)
        .where(CouncilReview.generation_job_id == job.id)
        .order_by(CouncilReview.created_at.asc())
    ).scalars().all()
    if not rows:
        raise HTTPException(status_code=404, detail="council has not run for this job yet")
    return _council_result(rows)


@router.post("/{job_id}/create-content-item", response_model=ContentRead, status_code=201)
def create_content_item(
    job_id: uuid.UUID,
    payload: CreateContentFromJob,
    request: Request,
    user: User = Depends(current_user),
    org: OrgContext = Depends(require_ai_generate),
    db: Session = Depends(get_session),
) -> ContentRead:
    job = _get_or_404(db, org.organization_id, job_id)

    if job.content_item_id is not None:
        # Idempotent: a job converts to at most one ContentItem.
        existing = db.get(ContentItem, job.content_item_id)
        if existing is not None:
            return ContentRead.model_validate(existing)

    if job.status != GenerationStatus.COMPLETED or not job.output_payload:
        raise HTTPException(
            status_code=400,
            detail="only a COMPLETED job with output can become a ContentItem",
        )

    output = job.output_payload
    content = ContentItem(
        organization_id=org.organization_id,
        brand_id=job.brand_id,
        campaign_id=job.campaign_id,
        product_id=job.product_id,
        public_id=make_public_id("ct"),
        external_id=job.public_id,
        source_system=SourceSystem.MANUAL,
        content_type=_CONTENT_TYPE_MAP.get(job.generation_type, ContentType.OTHER),
        title=payload.title or output.get("title") or "Untitled",
        hook=payload.hook or output.get("hook"),
        caption=payload.caption or output.get("caption"),
        cta=payload.cta or output.get("cta"),
        status=ContentStatus.DRAFT,
    )
    db.add(content)
    db.flush()

    job.content_item_id = content.id
    db.flush()

    audit.record(
        db,
        action="generation_job.content_created",
        actor_user_id=user.id,
        organization_id=org.organization_id,
        target_type="content",
        target_id=content.id,
        payload={"generation_job_id": str(job.id)},
        request=request,
    )
    db.commit()
    db.refresh(content)
    return ContentRead.model_validate(content)
