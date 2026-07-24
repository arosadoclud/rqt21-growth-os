from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import audit
from app.deps import OrgContext, current_user, get_session, require_automation_write
from app.models.audit_log import AuditLog
from app.models.automation import AutomationRule
from app.models.brand import Brand
from app.models.user import User
from app.schemas.automation import (
    AutomationRuleCreate,
    AutomationRuleRead,
    AutomationRuleUpdate,
    AutomationSummary,
)
from app.utils.public_id import make as make_public_id

router = APIRouter(prefix="/automations", tags=["automations"])

# Only these five (trigger, action) combinations are executable — see
# app.automation.engine. Anything else is rejected at creation time.
_ALLOWED_COMBINATIONS = {
    ("CONTENT_APPROVED", "CREATE_PUBLICATION_DRAFT"),
    ("CONTENT_APPROVED", "GENERATE_TRACKING_LINK"),
    ("PUBLICATION_FAILED", "SCHEDULE_RETRY"),
    ("PUBLICATION_FAILED", "SEND_INTERNAL_NOTIFICATION"),
    ("LEAD_CREATED", "CREATE_LEAD_ACTIVITY"),
    ("LEAD_STATUS_CHANGED", "CREATE_LEAD_ACTIVITY"),
    ("LEAD_STATUS_CHANGED", "SEND_INTERNAL_NOTIFICATION"),
    ("CALENDAR_ITEM_DUE", "SEND_INTERNAL_NOTIFICATION"),
}


def _get_or_404(db: Session, org_id: uuid.UUID, rule_id: uuid.UUID) -> AutomationRule:
    row = db.execute(
        select(AutomationRule).where(
            AutomationRule.id == rule_id, AutomationRule.organization_id == org_id
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="automation rule not found")
    return row


@router.get("", response_model=list[AutomationRuleRead])
def list_rules(
    org: OrgContext = Depends(require_automation_write),
    db: Session = Depends(get_session),
) -> list[AutomationRuleRead]:
    rows = db.execute(
        select(AutomationRule)
        .where(AutomationRule.organization_id == org.organization_id)
        .order_by(AutomationRule.created_at.desc())
    ).scalars().all()
    return [AutomationRuleRead.model_validate(r) for r in rows]


@router.post("", response_model=AutomationRuleRead, status_code=201)
def create_rule(
    payload: AutomationRuleCreate,
    request: Request,
    user: User = Depends(current_user),
    org: OrgContext = Depends(require_automation_write),
    db: Session = Depends(get_session),
) -> AutomationRuleRead:
    combo = (payload.trigger_type.value, payload.action_type.value)
    if combo not in _ALLOWED_COMBINATIONS:
        raise HTTPException(
            status_code=400,
            detail=f"trigger/action combination {combo} is not one of the predefined templates",
        )
    if payload.brand_id is not None:
        ok = db.execute(
            select(Brand.id).where(
                Brand.id == payload.brand_id, Brand.organization_id == org.organization_id
            )
        ).scalar_one_or_none()
        if ok is None:
            raise HTTPException(status_code=400, detail="brand not found in organization")

    row = AutomationRule(
        organization_id=org.organization_id,
        public_id=make_public_id("ar"),
        brand_id=payload.brand_id,
        name=payload.name,
        trigger_type=payload.trigger_type,
        conditions=payload.conditions,
        action_type=payload.action_type,
        action_config=payload.action_config,
        is_active=payload.is_active,
        created_by_user_id=user.id,
    )
    db.add(row)
    db.flush()
    audit.record(
        db,
        action="automation.created",
        actor_user_id=user.id,
        organization_id=org.organization_id,
        target_type="automation_rule",
        target_id=row.id,
        payload={"trigger_type": row.trigger_type.value, "action_type": row.action_type.value},
        request=request,
    )
    db.commit()
    db.refresh(row)
    return AutomationRuleRead.model_validate(row)


@router.patch("/{rule_id}", response_model=AutomationRuleRead)
def update_rule(
    rule_id: uuid.UUID,
    payload: AutomationRuleUpdate,
    request: Request,
    user: User = Depends(current_user),
    org: OrgContext = Depends(require_automation_write),
    db: Session = Depends(get_session),
) -> AutomationRuleRead:
    row = _get_or_404(db, org.organization_id, rule_id)
    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(row, k, v)
    db.flush()
    audit.record(
        db,
        action="automation.updated",
        actor_user_id=user.id,
        organization_id=org.organization_id,
        target_type="automation_rule",
        target_id=row.id,
        payload={"fields": list(data.keys())},
        request=request,
    )
    db.commit()
    db.refresh(row)
    return AutomationRuleRead.model_validate(row)


@router.get("/summary", response_model=AutomationSummary)
def automation_summary(
    org: OrgContext = Depends(require_automation_write),
    db: Session = Depends(get_session),
) -> AutomationSummary:
    from sqlalchemy import func

    active = db.execute(
        select(func.count(AutomationRule.id)).where(
            AutomationRule.organization_id == org.organization_id,
            AutomationRule.is_active.is_(True),
        )
    ).scalar_one()
    total_exec = db.execute(
        select(func.coalesce(func.sum(AutomationRule.execution_count), 0)).where(
            AutomationRule.organization_id == org.organization_id
        )
    ).scalar_one()
    loops = db.execute(
        select(func.count(AuditLog.id)).where(
            AuditLog.organization_id == org.organization_id,
            AuditLog.action == "automation.loop_prevented",
        )
    ).scalar_one()
    return AutomationSummary(
        active_rules=active or 0, total_executions=int(total_exec or 0), loop_preventions=loops or 0
    )
