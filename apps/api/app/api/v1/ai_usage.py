from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.deps import OrgContext, get_session, require_ai_usage_read
from app.models.ai import GenerationJob
from app.models.brand import Brand
from app.models.enums import GenerationStatus
from app.schemas.ai import AIUsageSummary

router = APIRouter(prefix="/ai-usage", tags=["ai-usage"])


@router.get("/summary", response_model=AIUsageSummary)
def usage_summary(
    org: OrgContext = Depends(require_ai_usage_read),
    db: Session = Depends(get_session),
) -> AIUsageSummary:
    org_id = org.organization_id

    jobs_total = db.execute(
        select(func.count(GenerationJob.id)).where(GenerationJob.organization_id == org_id)
    ).scalar_one()
    jobs_completed = db.execute(
        select(func.count(GenerationJob.id)).where(
            GenerationJob.organization_id == org_id,
            GenerationJob.status == GenerationStatus.COMPLETED,
        )
    ).scalar_one()
    jobs_failed = db.execute(
        select(func.count(GenerationJob.id)).where(
            GenerationJob.organization_id == org_id,
            GenerationJob.status == GenerationStatus.FAILED,
        )
    ).scalar_one()
    input_tokens = db.execute(
        select(func.coalesce(func.sum(GenerationJob.input_tokens), 0)).where(
            GenerationJob.organization_id == org_id
        )
    ).scalar_one()
    output_tokens = db.execute(
        select(func.coalesce(func.sum(GenerationJob.output_tokens), 0)).where(
            GenerationJob.organization_id == org_id
        )
    ).scalar_one()
    estimated_cost = db.execute(
        select(func.coalesce(func.sum(GenerationJob.estimated_cost), 0)).where(
            GenerationJob.organization_id == org_id
        )
    ).scalar_one()

    by_provider_rows = db.execute(
        select(GenerationJob.provider, func.count(GenerationJob.id))
        .where(GenerationJob.organization_id == org_id)
        .group_by(GenerationJob.provider)
    ).all()
    by_type_rows = db.execute(
        select(GenerationJob.generation_type, func.count(GenerationJob.id))
        .where(GenerationJob.organization_id == org_id)
        .group_by(GenerationJob.generation_type)
    ).all()
    by_brand_rows = db.execute(
        select(Brand.name, func.count(GenerationJob.id))
        .select_from(GenerationJob)
        .join(Brand, Brand.id == GenerationJob.brand_id)
        .where(GenerationJob.organization_id == org_id)
        .group_by(Brand.name)
    ).all()

    return AIUsageSummary(
        jobs_total=jobs_total or 0,
        jobs_completed=jobs_completed or 0,
        jobs_failed=jobs_failed or 0,
        input_tokens=int(input_tokens or 0),
        output_tokens=int(output_tokens or 0),
        estimated_cost=Decimal(estimated_cost or 0),
        monthly_budget=Decimal(str(settings.ai_monthly_budget_usd)),
        by_provider={p.value: n for p, n in by_provider_rows},
        by_type={t.value: n for t, n in by_type_rows},
        by_brand={name: n for name, n in by_brand_rows},
    )
