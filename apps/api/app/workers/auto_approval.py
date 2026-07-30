from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select

from app.core.config import settings
from app.core.db import SessionLocal
from app.models.content import ContentItem
from app.models.ai import BrandVoiceProfile
from app.ai.council import run_council, aggregate
from app.schemas.ai import GeneratedContent
from app import audit
from app.models.enums import ReviewDecision, ReviewStatus
from app.utils.public_id import make as make_public_id


def _build_generated_content_from_item(content: ContentItem) -> GeneratedContent:
    return GeneratedContent(
        title=content.title or "",
        hook=content.hook,
        script=None,
        caption=content.caption,
        cta=content.cta,
        hashtags=content.hashtags or [],
        visual_notes=[],
    )


def _create_review_row(db, org_id, content_id, decision: ReviewDecision, comment: str | None):
    from app.models.editorial import Review

    r = Review(
        organization_id=org_id,
        public_id=make_public_id("rv"),
        content_item_id=content_id,
        reviewer_user_id=None,
        review_type=None,
        decision=decision,
        score=None,
        comment=comment,
    )
    db.add(r)
    db.flush()
    return r


def run_once() -> dict[str, int]:
    """Single pass: find ContentItem.review_status == IN_REVIEW and
    run the council + auto-decision according to settings.
    """
    if not settings.enable_auto_approval:
        return {"processed": 0, "skipped": 0}

    counts = {"processed": 0, "skipped": 0}
    now = datetime.now(UTC)
    with SessionLocal() as db:
        rows = db.execute(
            select(ContentItem).where(ContentItem.review_status == ReviewStatus.IN_REVIEW)
        ).scalars().all()

        for item in rows:
            # build GeneratedContent from item
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
            avg, decision, blocking = aggregate(outcomes)

            # Apply decision according to thresholds but also allow explicit
            # council decisions to map to review_status values.
            if decision == "BLOCKED":
                # treat as REJECTED
                mapped = ReviewDecision.REJECTED
                item.review_status = ReviewStatus.REJECTED
                comment = "Auto-rejected (blocked by compliance)"
            else:
                score = avg
                if score >= settings.auto_approval_approve_threshold:
                    mapped = ReviewDecision.APPROVED
                    item.review_status = ReviewStatus.APPROVED
                    comment = f"Auto-approved by agent (score={score})"
                elif score <= settings.auto_approval_reject_threshold:
                    mapped = ReviewDecision.REJECTED
                    item.review_status = ReviewStatus.REJECTED
                    comment = f"Auto-rejected by agent (score={score})"
                else:
                    mapped = ReviewDecision.NEEDS_REVISION
                    item.review_status = ReviewStatus.CHANGES_REQUESTED
                    comment = f"Auto-marked for changes (score={score})"

            r = _create_review_row(db, item.organization_id, item.id, mapped, comment)

            audit.record(
                db,
                action="content.auto_reviewed",
                actor_user_id=None,
                organization_id=item.organization_id,
                target_type="content",
                target_id=item.id,
                payload={"decision": mapped.value, "score": avg},
                request=None,
            )
            db.commit()
            counts["processed"] += 1

    return counts


def main() -> None:
    result = run_once()
    print(f"[worker] auto_approval: {result}")


if __name__ == "__main__":
    main()
