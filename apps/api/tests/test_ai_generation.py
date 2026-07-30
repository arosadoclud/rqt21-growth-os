from __future__ import annotations

import uuid as _u

from sqlalchemy import select

from app.core import config as config_mod
from app.models.ai import GenerationJob
from app.models.audit_log import AuditLog
from app.models.membership import Role


def _brand(client):
    slug = f"brand-{_u.uuid4().hex[:6]}"
    return client.post("/api/v1/brands", json={"name": slug, "slug": slug}).json()["id"]


def _job_payload(brand_id: str, topic: str = "hábitos saludables") -> dict:
    return {
        "brand_id": brand_id,
        "generation_type": "REEL_SCRIPT",
        "input": {
            "objective": "engagement",
            "platform": "INSTAGRAM",
            "topic": topic,
            "audience": "adultos 30-50",
            "cta": "link en bio",
            "notes": "tono cercano",
        },
    }


def test_create_job_completes_with_mock_provider(bootstrap, db):
    client, _, _ = bootstrap(Role.OWNER, "gen-create@example.com")
    brand_id = _brand(client)
    r = client.post("/api/v1/generation-jobs", json=_job_payload(brand_id))
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["status"] == "COMPLETED"
    assert body["provider"] == "MOCK"
    assert body["output_payload"]["title"]
    assert body["input_tokens"] > 0
    assert body["output_tokens"] > 0
    assert body["prompt_version"]

    audits = db.execute(
        select(AuditLog).where(AuditLog.action == "generation_job.completed")
    ).scalars().all()
    assert len(audits) == 1


def test_marketer_can_generate(bootstrap):
    client, _, _ = bootstrap(Role.MARKETER, "gen-mkt@example.com")
    brand_id = _brand(client)
    r = client.post("/api/v1/generation-jobs", json=_job_payload(brand_id))
    assert r.status_code == 201


def test_sales_cannot_generate(bootstrap):
    client, _, _ = bootstrap(Role.SALES, "gen-sales@example.com")
    r = client.post(
        "/api/v1/generation-jobs",
        json=_job_payload("00000000-0000-0000-0000-000000000000"),
    )
    assert r.status_code == 403


def test_mock_timeout_marks_job_failed(bootstrap, db):
    client, _, _ = bootstrap(Role.OWNER, "gen-timeout@example.com")
    brand_id = _brand(client)
    r = client.post(
        "/api/v1/generation-jobs", json=_job_payload(brand_id, topic="__mock_timeout__")
    )
    assert r.status_code == 201
    body = r.json()
    assert body["status"] == "FAILED"
    assert body["error_code"] == "timeout"
    assert body["error_message"]

    audits = db.execute(
        select(AuditLog).where(AuditLog.action == "generation_job.failed")
    ).scalars().all()
    assert len(audits) == 1
    assert audits[0].payload["error_code"] == "timeout"


def test_mock_rate_limit_marks_job_failed(bootstrap):
    client, _, _ = bootstrap(Role.OWNER, "gen-ratelimit@example.com")
    brand_id = _brand(client)
    r = client.post(
        "/api/v1/generation-jobs", json=_job_payload(brand_id, topic="__mock_rate_limit__")
    )
    assert r.json()["status"] == "FAILED"
    assert r.json()["error_code"] == "rate_limited"


def test_mock_provider_error_marks_job_failed(bootstrap):
    client, _, _ = bootstrap(Role.OWNER, "gen-provider-error@example.com")
    brand_id = _brand(client)
    r = client.post(
        "/api/v1/generation-jobs",
        json=_job_payload(brand_id, topic="__mock_provider_error__"),
    )
    assert r.json()["status"] == "FAILED"
    assert r.json()["error_code"] == "provider_error"


def test_invalid_json_output_marks_job_failed(bootstrap):
    client, _, _ = bootstrap(Role.OWNER, "gen-badjson@example.com")
    brand_id = _brand(client)
    r = client.post(
        "/api/v1/generation-jobs", json=_job_payload(brand_id, topic="__mock_invalid_json__")
    )
    assert r.json()["status"] == "FAILED"
    assert r.json()["error_code"] == "invalid_output"


def test_recoverable_json_output_with_wrapped_text_completes(bootstrap):
    client, _, _ = bootstrap(Role.OWNER, "gen-repair-text@example.com")
    brand_id = _brand(client)
    r = client.post(
        "/api/v1/generation-jobs", json=_job_payload(brand_id, topic="__mock_json_with_text__")
    )
    assert r.json()["status"] == "COMPLETED"
    assert r.json()["output_payload"]["title"]


def test_valid_json_output_matches_schema(bootstrap):
    client, _, _ = bootstrap(Role.OWNER, "gen-goodjson@example.com")
    brand_id = _brand(client)
    r = client.post("/api/v1/generation-jobs", json=_job_payload(brand_id))
    out = r.json()["output_payload"]
    assert set(["title", "hashtags", "visual_notes"]).issubset(out.keys())
    assert isinstance(out["hashtags"], list)


def test_cancel_only_queued_or_running(bootstrap):
    client, _, _ = bootstrap(Role.OWNER, "gen-cancel@example.com")
    brand_id = _brand(client)
    job = client.post("/api/v1/generation-jobs", json=_job_payload(brand_id)).json()
    # MOCK runs synchronously so this job is already COMPLETED — cancel must
    # be rejected.
    r = client.post(f"/api/v1/generation-jobs/{job['id']}/cancel")
    assert r.status_code == 400


def test_retry_only_failed_jobs(bootstrap, db):
    client, _, _ = bootstrap(Role.OWNER, "gen-retry@example.com")
    brand_id = _brand(client)
    failed = client.post(
        "/api/v1/generation-jobs", json=_job_payload(brand_id, topic="__mock_timeout__")
    ).json()
    assert failed["status"] == "FAILED"

    r = client.post(f"/api/v1/generation-jobs/{failed['id']}/retry")
    assert r.status_code == 200
    retried = r.json()
    assert retried["id"] != failed["id"]

    row = db.execute(select(GenerationJob).where(GenerationJob.id == retried["id"])).scalar_one()
    assert str(row.retry_of_job_id) == failed["id"]

    audits = db.execute(
        select(AuditLog).where(AuditLog.action == "generation_job.retried")
    ).scalars().all()
    assert len(audits) == 1


def test_retry_completed_job_rejected(bootstrap):
    client, _, _ = bootstrap(Role.OWNER, "gen-retry-bad@example.com")
    brand_id = _brand(client)
    job = client.post("/api/v1/generation-jobs", json=_job_payload(brand_id)).json()
    assert job["status"] == "COMPLETED"
    r = client.post(f"/api/v1/generation-jobs/{job['id']}/retry")
    assert r.status_code == 400


def test_job_isolated_across_orgs(bootstrap):
    client_a, _, _ = bootstrap(Role.OWNER, "gen-iso-a@example.com")
    brand_id = _brand(client_a)
    job = client_a.post("/api/v1/generation-jobs", json=_job_payload(brand_id)).json()

    client_b, _, _ = bootstrap(Role.OWNER, "gen-iso-b@example.com")
    r = client_b.get(f"/api/v1/generation-jobs/{job['id']}")
    assert r.status_code == 404


def test_idempotency_key_returns_same_job(bootstrap, db):
    client, _, _ = bootstrap(Role.OWNER, "gen-idem@example.com")
    brand_id = _brand(client)
    payload = _job_payload(brand_id)
    payload["idempotency_key"] = "unique-key-1"
    r1 = client.post("/api/v1/generation-jobs", json=payload)
    r2 = client.post("/api/v1/generation-jobs", json=payload)
    assert r1.json()["id"] == r2.json()["id"]

    rows = db.execute(
        select(GenerationJob).where(GenerationJob.idempotency_key == "unique-key-1")
    ).scalars().all()
    assert len(rows) == 1


def test_daily_org_limit_enforced(bootstrap, monkeypatch, db):
    client, _, _ = bootstrap(Role.OWNER, "gen-daily-limit@example.com")
    brand_id = _brand(client)
    monkeypatch.setattr(config_mod.settings, "ai_daily_job_limit_per_org", 1, raising=True)
    monkeypatch.setattr(config_mod.settings, "ai_daily_job_limit_per_user", 1000, raising=True)

    r1 = client.post("/api/v1/generation-jobs", json=_job_payload(brand_id))
    assert r1.status_code == 201

    r2 = client.post("/api/v1/generation-jobs", json=_job_payload(brand_id, topic="second"))
    assert r2.status_code == 402

    audits = db.execute(
        select(AuditLog).where(AuditLog.action == "ai.budget_exceeded")
    ).scalars().all()
    assert len(audits) == 1


def test_monthly_budget_enforced(bootstrap, monkeypatch, db):
    client, _, _ = bootstrap(Role.OWNER, "gen-budget@example.com")
    brand_id = _brand(client)
    # Budget of $0 with a COMPLETED job already costing $0 (MOCK) won't trip
    # naturally, so drop the budget below zero to force the check.
    monkeypatch.setattr(config_mod.settings, "ai_monthly_budget_usd", -1.0, raising=True)

    r = client.post("/api/v1/generation-jobs", json=_job_payload(brand_id))
    assert r.status_code == 402

    audits = db.execute(
        select(AuditLog).where(AuditLog.action == "ai.budget_exceeded")
    ).scalars().all()
    assert len(audits) == 1


def test_convert_to_content_item(bootstrap, db):
    client, _, _ = bootstrap(Role.OWNER, "gen-convert@example.com")
    brand_id = _brand(client)
    job = client.post("/api/v1/generation-jobs", json=_job_payload(brand_id)).json()

    r = client.post(f"/api/v1/generation-jobs/{job['id']}/create-content-item", json={})
    assert r.status_code == 201, r.text
    content = r.json()
    assert content["status"] == "DRAFT"
    assert content["title"]

    audits = db.execute(
        select(AuditLog).where(AuditLog.action == "generation_job.content_created")
    ).scalars().all()
    assert len(audits) == 1


def test_convert_to_content_item_is_idempotent(bootstrap):
    client, _, _ = bootstrap(Role.OWNER, "gen-convert-idem@example.com")
    brand_id = _brand(client)
    job = client.post("/api/v1/generation-jobs", json=_job_payload(brand_id)).json()

    r1 = client.post(f"/api/v1/generation-jobs/{job['id']}/create-content-item", json={})
    r2 = client.post(f"/api/v1/generation-jobs/{job['id']}/create-content-item", json={})
    assert r1.json()["id"] == r2.json()["id"]


def test_convert_requires_completed_job(bootstrap):
    client, _, _ = bootstrap(Role.OWNER, "gen-convert-bad@example.com")
    brand_id = _brand(client)
    job = client.post(
        "/api/v1/generation-jobs", json=_job_payload(brand_id, topic="__mock_timeout__")
    ).json()
    assert job["status"] == "FAILED"
    r = client.post(f"/api/v1/generation-jobs/{job['id']}/create-content-item", json={})
    assert r.status_code == 400


def test_analyst_cannot_see_prompt_or_cost(bootstrap, make_user, add_member, db):
    client, org_id, _ = bootstrap(Role.OWNER, "gen-analyst-owner@example.com")
    brand_id = _brand(client)
    job = client.post("/api/v1/generation-jobs", json=_job_payload(brand_id)).json()
    assert job["input_payload"] is not None

    from app.main import app as fastapi_app
    from app.models.organization import Organization
    from tests.conftest import AuthedClient

    org = db.get(Organization, org_id)
    user = make_user("gen-analyst@example.com")
    add_member(user, org, Role.ANALYST)
    analyst = AuthedClient(fastapi_app)
    analyst.post(
        "/api/v1/auth/login",
        json={"email": "gen-analyst@example.com", "password": "Password1!"},
    )
    analyst.headers["X-Organization-Id"] = str(org_id)

    r = analyst.get(f"/api/v1/generation-jobs/{job['id']}")
    assert r.status_code == 200
    body = r.json()
    assert body["input_payload"] is None
    assert body["estimated_cost"] is None
    assert body["visibility"] == "restricted"
    # Non-sensitive fields remain visible.
    assert body["status"] == "COMPLETED"
    assert body["output_payload"] is not None


def test_viewer_cannot_see_ai_usage_summary(bootstrap):
    client, _, _ = bootstrap(Role.VIEWER, "gen-viewer-usage@example.com")
    r = client.get("/api/v1/ai-usage/summary")
    assert r.status_code == 403


def test_owner_sees_ai_usage_summary(bootstrap):
    client, _, _ = bootstrap(Role.OWNER, "gen-owner-usage@example.com")
    brand_id = _brand(client)
    client.post("/api/v1/generation-jobs", json=_job_payload(brand_id))
    r = client.get("/api/v1/ai-usage/summary")
    assert r.status_code == 200
    body = r.json()
    assert body["jobs_total"] >= 1
    assert "by_provider" in body
    assert "MOCK" in body["by_provider"]
