"""Pre-flight consumption checks, run BEFORE any provider is called.

If a limit is exceeded we never call the provider, we never create a
GenerationJob row that looks like a technical failure, and we always audit
the rejection as `ai.budget_exceeded` so it's distinguishable from a real
provider error in the audit trail.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.ai import GenerationJob
from app.models.enums import GenerationStatus


class BudgetExceeded(Exception):
    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


@dataclass(frozen=True)
class UsageSnapshot:
    jobs_today_org: int
    jobs_today_user: int
    cost_this_month: Decimal


def _month_start(now: datetime) -> datetime:
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def _day_start(now: datetime) -> datetime:
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


def snapshot(db: Session, org_id: uuid.UUID, user_id: uuid.UUID) -> UsageSnapshot:
    now = datetime.now(UTC)
    day_start = _day_start(now)
    month_start = _month_start(now)

    jobs_today_org = db.execute(
        select(func.count(GenerationJob.id)).where(
            GenerationJob.organization_id == org_id,
            GenerationJob.created_at >= day_start,
        )
    ).scalar_one()
    jobs_today_user = db.execute(
        select(func.count(GenerationJob.id)).where(
            GenerationJob.organization_id == org_id,
            GenerationJob.requested_by_user_id == user_id,
            GenerationJob.created_at >= day_start,
        )
    ).scalar_one()
    cost_this_month = db.execute(
        select(func.coalesce(func.sum(GenerationJob.estimated_cost), 0)).where(
            GenerationJob.organization_id == org_id,
            GenerationJob.created_at >= month_start,
            GenerationJob.status == GenerationStatus.COMPLETED,
        )
    ).scalar_one()

    return UsageSnapshot(
        jobs_today_org=jobs_today_org or 0,
        jobs_today_user=jobs_today_user or 0,
        cost_this_month=Decimal(cost_this_month or 0),
    )


def enforce(db: Session, org_id: uuid.UUID, user_id: uuid.UUID) -> None:
    usage = snapshot(db, org_id, user_id)

    if usage.jobs_today_org >= settings.ai_daily_job_limit_per_org:
        raise BudgetExceeded(
            f"organization daily generation limit reached "
            f"({settings.ai_daily_job_limit_per_org} jobs/day)"
        )
    if usage.jobs_today_user >= settings.ai_daily_job_limit_per_user:
        raise BudgetExceeded(
            f"per-user daily generation limit reached "
            f"({settings.ai_daily_job_limit_per_user} jobs/day)"
        )
    monthly_budget = Decimal(str(settings.ai_monthly_budget_usd))
    if usage.cost_this_month >= monthly_budget:
        raise BudgetExceeded(
            f"organization monthly AI budget exhausted (${monthly_budget})"
        )
