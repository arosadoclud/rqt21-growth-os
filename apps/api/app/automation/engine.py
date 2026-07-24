"""Automation execution engine.

Deliberately NOT a general rules engine: only the five predefined
(trigger_type, action_type) combinations from Phase 5 spec section 11 are
executable. ``conditions`` and ``action_config`` are plain JSON dicts
compared/read with simple equality — no user-supplied expressions, no code
execution, no arbitrary templating.

Called synchronously, in the same DB transaction as the endpoint that fired
the trigger (e.g. approving content). Never commits — the caller's own
db.commit() persists everything atomically, so an automation side effect
never survives when the primary action rolls back, and vice versa.

Loop protection: none of the five action types re-fire the trigger type that
invoked them (structurally impossible to recurse), but every rule still has
a hard execution ceiling (AUTOMATION_MAX_EXECUTIONS_PER_RULE) as defense in
depth — once reached, further matches are skipped and audited as
``automation.loop_prevented`` instead of executed.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import audit
from app.core.config import settings
from app.models.automation import AutomationRule
from app.models.enums import (
    AutomationActionType,
    AutomationTriggerType,
    LeadActivityType,
    NotificationType,
    PublicationStatus,
)
from app.notify import notify


@dataclass
class TriggerContext:
    brand_id: uuid.UUID | None = None
    content_item_id: uuid.UUID | None = None
    campaign_id: uuid.UUID | None = None
    product_id: uuid.UUID | None = None
    lead_id: uuid.UUID | None = None
    publication_id: uuid.UUID | None = None
    actor_user_id: uuid.UUID | None = None
    extra: dict = field(default_factory=dict)


def _conditions_match(conditions: dict, ctx: TriggerContext) -> bool:
    """Closed comparison set: only equality checks against known context
    fields. No free-form expression evaluation of any kind."""
    for key, expected in (conditions or {}).items():
        actual = getattr(ctx, key, None)
        if actual is None:
            actual = ctx.extra.get(key)
        if str(actual) != str(expected):
            return False
    return True


def _execute_action(
    db: Session, rule: AutomationRule, ctx: TriggerContext, org_id: uuid.UUID
) -> dict:
    """Returns a small summary dict for audit purposes. Raises on hard
    failure (caller catches and audits without aborting the parent
    transaction)."""
    cfg = rule.action_config or {}

    if rule.action_type == AutomationActionType.CREATE_PUBLICATION_DRAFT:
        from app.models.publishing import Publication, PublishingConnection
        from app.utils.public_id import make as make_public_id

        if ctx.content_item_id is None or ctx.brand_id is None:
            raise ValueError("missing content_item_id/brand_id in trigger context")
        connection_id = cfg.get("publishing_connection_id")
        if not connection_id:
            raise ValueError("action_config.publishing_connection_id is required")
        connection = db.execute(
            select(PublishingConnection).where(
                PublishingConnection.id == uuid.UUID(connection_id),
                PublishingConnection.organization_id == org_id,
            )
        ).scalar_one_or_none()
        if connection is None:
            raise ValueError("configured publishing connection not found")

        idem_key = f"automation:{rule.id}:{ctx.content_item_id}"
        existing = db.execute(
            select(Publication).where(
                Publication.organization_id == org_id, Publication.idempotency_key == idem_key
            )
        ).scalar_one_or_none()
        if existing is not None:
            return {"publication_id": str(existing.id), "reused": True}

        pub = Publication(
            organization_id=org_id,
            public_id=make_public_id("pub"),
            content_item_id=ctx.content_item_id,
            brand_id=ctx.brand_id,
            campaign_id=ctx.campaign_id,
            product_id=ctx.product_id,
            publishing_connection_id=connection.id,
            platform=connection.platform,
            publication_type=cfg.get("publication_type", "POST"),
            status=PublicationStatus.DRAFT,
            caption=cfg.get("default_caption", ""),
            idempotency_key=idem_key,
        )
        db.add(pub)
        db.flush()
        return {"publication_id": str(pub.id)}

    if rule.action_type == AutomationActionType.GENERATE_TRACKING_LINK:
        from app.models.tracking import TrackingLink
        from app.utils.public_id import make as make_public_id
        from app.utils.short_code import generate as generate_short_code

        if ctx.brand_id is None:
            raise ValueError("missing brand_id in trigger context")
        destination = cfg.get("destination_url")
        if not destination:
            raise ValueError("action_config.destination_url is required")
        for _ in range(6):
            code = generate_short_code()
            clash = db.execute(
                select(TrackingLink.id).where(TrackingLink.short_code == code)
            ).scalar_one_or_none()
            if clash is None:
                break
        else:
            raise ValueError("could not allocate a unique short code")
        link = TrackingLink(
            organization_id=org_id,
            brand_id=ctx.brand_id,
            campaign_id=ctx.campaign_id,
            content_id=ctx.content_item_id,
            product_id=ctx.product_id,
            public_id=make_public_id("tl"),
            short_code=code,
            destination_url=destination,
            utm_source=cfg.get("utm_source"),
            utm_medium=cfg.get("utm_medium"),
            utm_campaign=cfg.get("utm_campaign"),
        )
        db.add(link)
        db.flush()
        return {"tracking_link_id": str(link.id), "short_code": code}

    if rule.action_type == AutomationActionType.SCHEDULE_RETRY:
        from app.models.publishing import Publication
        from app.publishing.retry import next_retry_at

        if ctx.publication_id is None:
            raise ValueError("missing publication_id in trigger context")
        pub = db.get(Publication, ctx.publication_id)
        if pub is None or pub.organization_id != org_id:
            raise ValueError("publication not found")
        if pub.status == PublicationStatus.FAILED:
            pub.status = PublicationStatus.RETRY_SCHEDULED
            pub.next_retry_at = next_retry_at(max(pub.attempt_count, 1))
            db.flush()
        return {"publication_id": str(pub.id)}

    if rule.action_type == AutomationActionType.CREATE_LEAD_ACTIVITY:
        from app.models.lead import LeadActivity
        from app.utils.public_id import make as make_public_id

        if ctx.lead_id is None:
            raise ValueError("missing lead_id in trigger context")
        activity = LeadActivity(
            public_id=make_public_id("la"),
            organization_id=org_id,
            lead_id=ctx.lead_id,
            actor_user_id=None,
            activity_type=LeadActivityType.NOTE_ADDED,
            description=cfg.get("description", f"Automation: {rule.name}"),
            activity_metadata={"automation_rule_id": str(rule.id)},
        )
        db.add(activity)
        db.flush()
        return {"lead_activity_id": str(activity.id)}

    if rule.action_type == AutomationActionType.SEND_INTERNAL_NOTIFICATION:
        target_user_id = cfg.get("target_user_id") or (
            str(ctx.actor_user_id) if ctx.actor_user_id else None
        )
        if not target_user_id:
            raise ValueError("no target user for notification")
        n = notify(
            db,
            organization_id=org_id,
            user_id=uuid.UUID(target_user_id),
            notification_type=NotificationType(cfg.get("notification_type", "PUBLICATION_FAILED")),
            title=cfg.get("title", rule.name),
            message=cfg.get("message", f"Automation '{rule.name}' triggered"),
            resource_type=cfg.get("resource_type"),
            resource_public_id=cfg.get("resource_public_id"),
        )
        return {"notification_id": str(n.id)}

    raise ValueError(f"unsupported action_type {rule.action_type}")


def run_triggers(
    db: Session,
    *,
    organization_id: uuid.UUID,
    trigger_type: AutomationTriggerType,
    context: TriggerContext,
    request=None,
) -> None:
    rules = db.execute(
        select(AutomationRule).where(
            AutomationRule.organization_id == organization_id,
            AutomationRule.trigger_type == trigger_type,
            AutomationRule.is_active.is_(True),
        )
    ).scalars().all()

    for rule in rules:
        if not _conditions_match(rule.conditions, context):
            continue
        if rule.execution_count >= settings.automation_max_executions_per_rule:
            audit.record(
                db,
                action="automation.loop_prevented",
                actor_user_id=context.actor_user_id,
                organization_id=organization_id,
                target_type="automation_rule",
                target_id=rule.id,
                payload={"execution_count": rule.execution_count},
                request=request,
            )
            continue
        try:
            result = _execute_action(db, rule, context, organization_id)
        except Exception as exc:  # noqa: BLE001 - automation failures must not break the caller
            audit.record(
                db,
                action="automation.executed",
                actor_user_id=context.actor_user_id,
                organization_id=organization_id,
                target_type="automation_rule",
                target_id=rule.id,
                payload={"ok": False, "error": str(exc)[:300]},
                request=request,
            )
            continue

        rule.execution_count += 1
        rule.last_executed_at = datetime.now(UTC)
        db.flush()
        audit.record(
            db,
            action="automation.executed",
            actor_user_id=context.actor_user_id,
            organization_id=organization_id,
            target_type="automation_rule",
            target_id=rule.id,
            payload={"ok": True, "result": result},
            request=request,
        )
