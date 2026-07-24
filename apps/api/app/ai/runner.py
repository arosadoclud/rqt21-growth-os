"""Executes a single GenerationJob: QUEUED -> RUNNING -> COMPLETED|FAILED.

Called by the JobQueue implementation (InlineJobQueue runs it immediately,
in-process). Opens its own DB session since it may run outside the request
that created the job (true once a real distributed queue backend is wired
in place of InlineJobQueue).
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from decimal import Decimal

from pydantic import ValidationError

from app import audit
from app.ai.providers import (
    AIProviderError,
    AIProviderRateLimited,
    AIProviderTimeout,
    GenerationRequest,
    get_provider,
)
from app.core.config import settings
from app.core.db import SessionLocal
from app.models.ai import GenerationJob
from app.models.enums import GenerationStatus
from app.schemas.ai import GeneratedContent

_PRICE_PER_1K = {
    ("ANTHROPIC", "input"): Decimal("0.003"),
    ("ANTHROPIC", "output"): Decimal("0.015"),
    ("OPENAI", "input"): Decimal("0.0025"),
    ("OPENAI", "output"): Decimal("0.01"),
}


def _estimate_cost(provider: str, input_tokens: int, output_tokens: int) -> Decimal:
    if provider == "MOCK":
        return Decimal("0")
    price_in = _PRICE_PER_1K.get((provider, "input"), Decimal("0.002"))
    price_out = _PRICE_PER_1K.get((provider, "output"), Decimal("0.008"))
    cost = (Decimal(input_tokens) / 1000 * price_in) + (Decimal(output_tokens) / 1000 * price_out)
    return cost.quantize(Decimal("0.000001"))


def _extract_json(raw: str) -> str:
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
    return text.strip()


def _try_parse(text: str) -> GeneratedContent | None:
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None
    try:
        return GeneratedContent.model_validate(data)
    except ValidationError:
        return None


def _attempt_repair(text: str) -> str | None:
    """One controlled repair attempt: trim to the outermost {...} span.
    No retries beyond this — a job that fails here is marked FAILED."""
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    return text[start : end + 1]


def _fail(job: GenerationJob, db, error_code: str, message: str) -> None:
    job.status = GenerationStatus.FAILED
    job.error_code = error_code
    job.error_message = message[:500]
    job.completed_at = datetime.now(UTC)
    db.flush()
    audit.record(
        db,
        action="generation_job.failed",
        actor_user_id=job.requested_by_user_id,
        organization_id=job.organization_id,
        target_type="generation_job",
        target_id=job.id,
        payload={"error_code": error_code},
    )
    db.commit()


async def run_generation_job(job_id: uuid.UUID) -> None:
    with SessionLocal() as db:
        job = db.get(GenerationJob, job_id)
        if job is None or job.status != GenerationStatus.QUEUED:
            return

        job.status = GenerationStatus.RUNNING
        job.started_at = datetime.now(UTC)
        db.flush()
        audit.record(
            db,
            action="generation_job.started",
            actor_user_id=job.requested_by_user_id,
            organization_id=job.organization_id,
            target_type="generation_job",
            target_id=job.id,
            payload={"provider": job.provider.value, "model": job.model},
        )
        db.commit()

        system = job.input_payload.get("system", "")
        user = job.input_payload.get("user", "")
        provider = get_provider(job.provider.value)
        request = GenerationRequest(
            system_instructions=system,
            user_prompt=user,
            model=job.model,
            max_output_tokens=settings.ai_max_output_tokens,
            timeout_seconds=settings.ai_request_timeout_seconds,
        )

        try:
            result = await provider.generate(request)
        except AIProviderTimeout as exc:
            _fail(job, db, "timeout", str(exc))
            return
        except AIProviderRateLimited as exc:
            _fail(job, db, "rate_limited", str(exc))
            return
        except AIProviderError as exc:
            _fail(job, db, "provider_error", str(exc))
            return

        text = _extract_json(result.raw_text)
        content = _try_parse(text)
        if content is None:
            repaired = _attempt_repair(text)
            content = _try_parse(repaired) if repaired else None
        if content is None:
            _fail(
                job,
                db,
                "invalid_output",
                "provider output failed schema validation after one repair attempt",
            )
            return

        job.output_payload = content.model_dump()
        job.input_tokens = result.input_tokens
        job.output_tokens = result.output_tokens
        job.estimated_cost = _estimate_cost(
            job.provider.value, result.input_tokens, result.output_tokens
        )
        job.status = GenerationStatus.COMPLETED
        job.completed_at = datetime.now(UTC)
        db.flush()
        audit.record(
            db,
            action="generation_job.completed",
            actor_user_id=job.requested_by_user_id,
            organization_id=job.organization_id,
            target_type="generation_job",
            target_id=job.id,
            payload={
                "input_tokens": result.input_tokens,
                "output_tokens": result.output_tokens,
            },
        )
        db.commit()
