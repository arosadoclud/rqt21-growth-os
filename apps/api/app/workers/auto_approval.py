from __future__ import annotations

from sqlalchemy import select

from app import audit
from app.ai.council import aggregate, run_council
from app.core.config import settings
from app.core.db import SessionLocal
from app.models.ai import BrandVoiceProfile
from app.models.content import ContentItem
from app.models.enums import ReviewDecision, ReviewStatus
from app.schemas.ai import GeneratedContent
from app.utils.public_id import make as make_public_id


def _build_generated_content_from_item(content: ContentItem) -> GeneratedContent:
    return GeneratedContent(
        title=content.title or "",
        hook=content.hook,
        script=None,
        caption=content.caption,
        cta=content.cta,
        hashtags=[],
        visual_notes=[],
    )


def _create_review_row(db, org_id, content_id, decision: ReviewDecision, comment: str | None):
    from app.models.editorial import Review
    from app.models.enums import ReviewType as _ReviewType

    r = Review(
        organization_id=org_id,
        public_id=make_public_id("rv"),
        content_item_id=content_id,
        reviewer_user_id=None,
        review_type=_ReviewType.GENERAL,
        decision=decision,
        score=None,
        comment=comment,
    )
    db.add(r)
    db.flush()
    return r


def evaluate_content(db, item: ContentItem) -> tuple[ReviewDecision, str, int]:
    """Run the review council against a single ContentItem and map its
    aggregate score to a (ReviewDecision, review_status, score) triple,
    using the org's configured approve/reject thresholds. Pure evaluation —
    does not touch the item or write any rows, so it's safe to call from
    both the bulk sweep and the synchronous submit-time hook."""
    content = _build_generated_content_from_item(item)
    brand_voice = db.execute(
        select(BrandVoiceProfile).where(
            BrandVoiceProfile.organization_id == item.organization_id,
            BrandVoiceProfile.brand_id == item.brand_id,
        )
    ).scalar_one_or_none()

    outcomes = run_council(
        content,
        topic=item.title or "",
        forbidden_terms=brand_voice.forbidden_terms if brand_voice else [],
        preferred_terms=brand_voice.preferred_terms if brand_voice else [],
        cta_style=brand_voice.cta_style if brand_voice else "",
    )
    avg, decision, _blocking = aggregate(outcomes)

    if decision == "BLOCKED":
        return ReviewDecision.REJECTED, "auto-rejected-blocked", avg
    if avg >= settings.auto_approval_approve_threshold:
        return ReviewDecision.APPROVED, "auto-approved", avg
    if avg <= settings.auto_approval_reject_threshold:
        return ReviewDecision.REJECTED, "auto-rejected-score", avg
    return ReviewDecision.NEEDS_REVISION, "auto-changes-requested", avg


_STATUS_BY_DECISION = {
    ReviewDecision.APPROVED: ReviewStatus.APPROVED,
    ReviewDecision.REJECTED: ReviewStatus.REJECTED,
    ReviewDecision.NEEDS_REVISION: ReviewStatus.CHANGES_REQUESTED,
}

_COMMENT_BY_REASON = {
    "auto-rejected-blocked": "Auto-rechazado (bloqueado por cumplimiento)",
    "auto-approved": "Auto-aprobado por el agente (score={score})",
    "auto-rejected-score": "Auto-rechazado por el agente (score={score})",
    "auto-changes-requested": "Cambios solicitados automáticamente (score={score})",
}


def apply_auto_review(db, item: ContentItem, *, reviewer_id=None, request=None):
    """Evaluate ``item`` and, if auto-approval is enabled, immediately
    record the decision and move review_status — no human click required.
    Returns the created Review row, or None if auto-approval is disabled.
    Does not commit; the caller's transaction persists it."""
    if not settings.enable_auto_approval:
        return None

    mapped, reason, score = evaluate_content(db, item)
    item.review_status = _STATUS_BY_DECISION[mapped]
    comment = _COMMENT_BY_REASON[reason].format(score=score)
    review = _create_review_row(db, item.organization_id, item.id, mapped, comment)

    audit.record(
        db,
        action="content.auto_reviewed",
        actor_user_id=reviewer_id,
        organization_id=item.organization_id,
        target_type="content",
        target_id=item.id,
        payload={"decision": mapped.value, "score": score},
        request=request,
    )

    if mapped == ReviewDecision.APPROVED:
        from app.automation.engine import TriggerContext, run_triggers
        from app.models.enums import AutomationTriggerType

        run_triggers(
            db,
            organization_id=item.organization_id,
            trigger_type=AutomationTriggerType.CONTENT_APPROVED,
            context=TriggerContext(
                brand_id=item.brand_id,
                content_item_id=item.id,
                campaign_id=item.campaign_id,
                product_id=item.product_id,
                actor_user_id=reviewer_id,
            ),
            request=request,
        )

    return review


def run_once() -> dict[str, int]:
    """Bulk sweep: find every ContentItem still IN_REVIEW (e.g. left over
    from before auto-approval was enabled, or a run that failed
    mid-transaction) and apply apply_auto_review() to each. The normal path
    is the synchronous hook in submit_for_review — this exists as a
    catch-all for manual/cron reconciliation, not the primary mechanism."""
    if not settings.enable_auto_approval:
        return {"processed": 0, "skipped": 0}

    counts = {"processed": 0, "skipped": 0}
    with SessionLocal() as db:
        rows = db.execute(
            select(ContentItem).where(ContentItem.review_status == ReviewStatus.IN_REVIEW)
        ).scalars().all()

        for item in rows:
            review = apply_auto_review(db, item)
            db.commit()
            if review is not None:
                counts["processed"] += 1
            else:
                counts["skipped"] += 1

    return counts


def main() -> None:
    result = run_once()
    print(f"[worker] auto_approval: {result}")


if __name__ == "__main__":
    main()
