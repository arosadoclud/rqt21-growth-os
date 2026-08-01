"""Editorial council: six deterministic, rule-based reviewers that evaluate a
generated draft before a human decides whether to approve it.

The council NEVER approves content on a human's behalf — see
app.deps.require_content_approval, which still gates ContentItem approval to
OWNER/ADMIN regardless of what the council concluded. The council's job is to
surface a structured recommendation, not to make the final call.

Scoring/decision thresholds are centralized in `decide()` — nothing else in
this module (or in the endpoints layer) re-implements this rule, so the
95/80 cutoffs only need to change in one place.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.ai.compliance import scan_compliance
from app.models.enums import CouncilDecision, CouncilReviewerType
from app.publishing.platform_rules import MAX_HASHTAGS_ANTI_SPAM
from app.schemas.ai import GeneratedContent


def decide(score: int, blocking_issues: list[str]) -> CouncilDecision:
    if blocking_issues:
        return CouncilDecision.BLOCKED
    if score >= 95:
        return CouncilDecision.APPROVED
    if score >= 80:
        return CouncilDecision.NEEDS_REVISION
    return CouncilDecision.REJECTED


@dataclass
class ReviewerOutcome:
    reviewer_type: CouncilReviewerType
    score: int
    decision: CouncilDecision
    summary: str
    issues: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    blocking_issues: list[str] = field(default_factory=list)


def _full_text(content: GeneratedContent) -> str:
    parts = [
        content.title,
        content.hook or "",
        content.script or "",
        content.caption or "",
        content.cta or "",
        " ".join(content.hashtags),
        " ".join(content.visual_notes),
    ]
    return "\n".join(p for p in parts if p)


def _review_brand(content: GeneratedContent, forbidden_terms: list[str], preferred_terms: list[str]) -> ReviewerOutcome:
    text = _full_text(content).lower()
    issues: list[str] = []
    recommendations: list[str] = []
    score = 92
    for term in forbidden_terms:
        if term.strip() and term.strip().lower() in text:
            issues.append(f"uses forbidden term '{term}'")
            score -= 20
    if preferred_terms and not any(t.strip().lower() in text for t in preferred_terms if t.strip()):
        recommendations.append("consider using one of the brand's preferred terms")
        score -= 3
    score = max(0, min(100, score))
    return ReviewerOutcome(
        reviewer_type=CouncilReviewerType.BRAND,
        score=score,
        decision=decide(score, []),
        summary="Brand voice alignment check",
        issues=issues,
        recommendations=recommendations,
    )


def _review_seo(content: GeneratedContent, topic: str) -> ReviewerOutcome:
    issues: list[str] = []
    recommendations: list[str] = []
    score = 90
    if not (3 <= len(content.hashtags) <= 10):
        issues.append("hashtag count outside the recommended 3-10 range")
        score -= 8
    if len(content.title) < 10:
        issues.append("title is very short for discoverability")
        score -= 6
    topic_words = {w.lower() for w in topic.split() if len(w) > 3}
    haystack = _full_text(content).lower()
    if topic_words and not any(w in haystack for w in topic_words):
        recommendations.append("tie the copy more explicitly to the requested topic")
        score -= 5
    score = max(0, min(100, score))
    return ReviewerOutcome(
        reviewer_type=CouncilReviewerType.SEO,
        score=score,
        decision=decide(score, []),
        summary="Discoverability and topical relevance check",
        issues=issues,
        recommendations=recommendations,
    )


_NEGATIVE_WORDS = {"nunca", "imposible", "fracaso", "odio"}


def _review_emotional_tone(content: GeneratedContent) -> ReviewerOutcome:
    issues: list[str] = []
    recommendations: list[str] = []
    score = 93
    if not content.hook:
        issues.append("missing an emotional hook")
        score -= 10
    text = _full_text(content).lower()
    hits = [w for w in _NEGATIVE_WORDS if w in text]
    if hits:
        issues.append(f"tone risk: negative language ({', '.join(hits)})")
        score -= 10
    if not content.caption or len(content.caption) < 20:
        recommendations.append("expand the caption for a stronger emotional arc")
        score -= 4
    score = max(0, min(100, score))
    return ReviewerOutcome(
        reviewer_type=CouncilReviewerType.EMOTIONAL_TONE,
        score=score,
        decision=decide(score, []),
        summary="Emotional tone and hook strength check",
        issues=issues,
        recommendations=recommendations,
    )


def _review_cta(content: GeneratedContent, cta_style: str) -> ReviewerOutcome:
    issues: list[str] = []
    recommendations: list[str] = []
    score = 91
    if not content.cta or not content.cta.strip():
        issues.append("no call to action present")
        score -= 25
    elif cta_style and cta_style.strip().lower() not in content.cta.lower():
        recommendations.append(f"align CTA phrasing with brand style: '{cta_style}'")
        score -= 5
    score = max(0, min(100, score))
    return ReviewerOutcome(
        reviewer_type=CouncilReviewerType.CTA,
        score=score,
        decision=decide(score, []),
        summary="Call-to-action clarity and brand-style fit",
        issues=issues,
        recommendations=recommendations,
    )


def _review_compliance(content: GeneratedContent, forbidden_terms: list[str]) -> ReviewerOutcome:
    text = _full_text(content)
    blocking = scan_compliance(text, forbidden_terms)
    score = 100 - (25 * len(blocking))
    score = max(0, min(100, score))
    return ReviewerOutcome(
        reviewer_type=CouncilReviewerType.COMPLIANCE,
        score=score,
        decision=decide(score, blocking),
        summary="Health/medical claims and forbidden-term compliance scan",
        issues=list(blocking),
        recommendations=(
            ["rewrite flagged claims using responsible, non-medical language"] if blocking else []
        ),
        blocking_issues=blocking,
    )


def _review_devils_advocate(content: GeneratedContent) -> ReviewerOutcome:
    issues: list[str] = []
    recommendations: list[str] = []
    score = 86
    if len(content.hashtags) > MAX_HASHTAGS_ANTI_SPAM:
        # Same threshold enforced as a hard block at the actual pre-publish
        # gate (app.publishing.validation.validate_publication_draft) — this
        # is just an earlier warning during auto-review, matching Meta's own
        # "more than 5 hashtags" spam-policy line.
        issues.append("hashtag count looks spammy")
        score -= 8
    if content.caption and len(content.caption) < 20:
        issues.append("caption reads as generic/low-effort")
        score -= 6
    generic_openers = ("descubre", "conoce", "no te pierdas")
    if content.hook and content.hook.strip().lower().startswith(generic_openers):
        recommendations.append("open with something less generic than a stock phrase")
        score -= 4
    score = max(0, min(100, score))
    return ReviewerOutcome(
        reviewer_type=CouncilReviewerType.DEVILS_ADVOCATE,
        score=score,
        decision=decide(score, []),
        summary="Adversarial pass for weak/generic claims",
        issues=issues,
        recommendations=recommendations,
    )


def run_council(
    content: GeneratedContent,
    *,
    topic: str,
    forbidden_terms: list[str] | None = None,
    preferred_terms: list[str] | None = None,
    cta_style: str = "",
) -> list[ReviewerOutcome]:
    forbidden_terms = forbidden_terms or []
    preferred_terms = preferred_terms or []
    return [
        _review_brand(content, forbidden_terms, preferred_terms),
        _review_seo(content, topic),
        _review_emotional_tone(content),
        _review_cta(content, cta_style),
        _review_compliance(content, forbidden_terms),
        _review_devils_advocate(content),
    ]


def aggregate(outcomes: list[ReviewerOutcome]) -> tuple[float, CouncilDecision, list[str]]:
    """Return (avg_score, aggregate_decision, all_blocking_issues)."""
    avg = round(sum(o.score for o in outcomes) / len(outcomes), 1) if outcomes else 0.0
    blocking: list[str] = []
    for o in outcomes:
        blocking.extend(o.blocking_issues)
    return avg, decide(int(avg), blocking), blocking
