from __future__ import annotations

import uuid as _u

from sqlalchemy import select

from app.ai.council import aggregate, decide, run_council
from app.models.ai import CouncilReview
from app.models.audit_log import AuditLog
from app.models.enums import CouncilDecision, CouncilReviewerType
from app.models.membership import Role
from app.schemas.ai import GeneratedContent


def _brand(client):
    slug = f"brand-{_u.uuid4().hex[:6]}"
    return client.post("/api/v1/brands", json={"name": slug, "slug": slug}).json()["id"]


def _job_payload(brand_id: str, topic: str = "hábitos saludables") -> dict:
    return {
        "brand_id": brand_id,
        "generation_type": "REEL_SCRIPT",
        "input": {"objective": "engagement", "platform": "INSTAGRAM", "topic": topic},
    }


def test_decide_thresholds():
    assert decide(95, []) == CouncilDecision.APPROVED
    assert decide(100, []) == CouncilDecision.APPROVED
    assert decide(94, []) == CouncilDecision.NEEDS_REVISION
    assert decide(80, []) == CouncilDecision.NEEDS_REVISION
    assert decide(79, []) == CouncilDecision.REJECTED
    assert decide(0, []) == CouncilDecision.REJECTED
    assert decide(99, ["some blocking issue"]) == CouncilDecision.BLOCKED


def test_six_reviewers_run():
    content = GeneratedContent(
        title="Hábitos keto sostenibles",
        hook="¿Sabías que pequeños cambios generan grandes resultados?",
        script="Toma 1... Toma 2... Toma 3...",
        caption="Descubre un enfoque responsable de alimentación.",
        cta="Link en la bio para más información",
        hashtags=["#keto", "#habitossaludables", "#recetas"],
        visual_notes=["Luz natural"],
    )
    outcomes = run_council(content, topic="keto")
    types = {o.reviewer_type for o in outcomes}
    assert types == {
        CouncilReviewerType.BRAND,
        CouncilReviewerType.SEO,
        CouncilReviewerType.EMOTIONAL_TONE,
        CouncilReviewerType.CTA,
        CouncilReviewerType.COMPLIANCE,
        CouncilReviewerType.DEVILS_ADVOCATE,
    }
    for o in outcomes:
        assert 0 <= o.score <= 100


def test_compliance_reviewer_blocks_medical_claims():
    content = GeneratedContent(
        title="Pierde 10 kg garantizado en 7 días",
        hook="Tratamiento médico para eliminar la grasa",
        cta="Compra ya",
        hashtags=["#milagro"],
    )
    outcomes = run_council(content, topic="peso")
    compliance = next(o for o in outcomes if o.reviewer_type == CouncilReviewerType.COMPLIANCE)
    assert compliance.decision == CouncilDecision.BLOCKED
    assert compliance.blocking_issues

    score, decision, blocking = aggregate(outcomes)
    assert decision == CouncilDecision.BLOCKED
    assert blocking


def test_forbidden_terms_trigger_brand_and_compliance():
    content = GeneratedContent(
        title="Nuestro tratamiento médico exclusivo",
        cta="Compra",
        hashtags=["#salud"],
    )
    outcomes = run_council(content, topic="salud", forbidden_terms=["tratamiento médico"])
    brand = next(o for o in outcomes if o.reviewer_type == CouncilReviewerType.BRAND)
    assert any("forbidden term" in i for i in brand.issues)


def test_clean_content_is_not_blocked():
    content = GeneratedContent(
        title="Ideas para una cena ligera y saludable",
        hook="Prepara algo delicioso en minutos",
        caption="Una receta simple para tus noches ocupadas.",
        cta="Ver la receta completa en el link de la bio",
        hashtags=["#recetas", "#saludable", "#cenaligera"],
        visual_notes=["Plano cenital del plato"],
    )
    outcomes = run_council(content, topic="cena saludable")
    _, decision, blocking = aggregate(outcomes)
    assert blocking == []
    assert decision != CouncilDecision.BLOCKED


def test_run_council_endpoint_persists_reviews_and_audits(bootstrap, db):
    client, _, _ = bootstrap(Role.OWNER, "council-run@example.com")
    brand_id = _brand(client)
    job = client.post("/api/v1/generation-jobs", json=_job_payload(brand_id)).json()
    assert job["status"] == "COMPLETED"

    r = client.post(f"/api/v1/generation-jobs/{job['id']}/run-council")
    assert r.status_code == 200, r.text
    body = r.json()
    assert len(body["reviews"]) == 6
    assert body["decision"] in [d.value for d in CouncilDecision]

    rows = db.execute(
        select(CouncilReview).where(CouncilReview.generation_job_id == job["id"])
    ).scalars().all()
    assert len(rows) == 6

    audits = db.execute(
        select(AuditLog).where(AuditLog.action == "generation_job.council_completed")
    ).scalars().all()
    assert len(audits) == 1


def test_run_council_is_idempotent(bootstrap):
    client, _, _ = bootstrap(Role.OWNER, "council-idem@example.com")
    brand_id = _brand(client)
    job = client.post("/api/v1/generation-jobs", json=_job_payload(brand_id)).json()

    r1 = client.post(f"/api/v1/generation-jobs/{job['id']}/run-council")
    r2 = client.post(f"/api/v1/generation-jobs/{job['id']}/run-council")
    assert r1.json()["created_at"] == r2.json()["created_at"]
    assert len(r1.json()["reviews"]) == len(r2.json()["reviews"]) == 6


def test_council_requires_completed_job(bootstrap):
    client, _, _ = bootstrap(Role.OWNER, "council-notdone@example.com")
    brand_id = _brand(client)
    job = client.post(
        "/api/v1/generation-jobs", json=_job_payload(brand_id, topic="__mock_timeout__")
    ).json()
    r = client.post(f"/api/v1/generation-jobs/{job['id']}/run-council")
    assert r.status_code == 400


def test_get_council_before_run_404(bootstrap):
    client, _, _ = bootstrap(Role.OWNER, "council-get-none@example.com")
    brand_id = _brand(client)
    job = client.post("/api/v1/generation-jobs", json=_job_payload(brand_id)).json()
    r = client.get(f"/api/v1/generation-jobs/{job['id']}/council")
    assert r.status_code == 404


def test_marketer_can_run_council_but_not_approve_content(bootstrap):
    client, _, _ = bootstrap(Role.MARKETER, "council-mkt@example.com")
    brand_id = _brand(client)
    job = client.post("/api/v1/generation-jobs", json=_job_payload(brand_id)).json()
    r = client.post(f"/api/v1/generation-jobs/{job['id']}/run-council")
    assert r.status_code == 200

    content = client.post(
        f"/api/v1/generation-jobs/{job['id']}/create-content-item", json={}
    ).json()

    # Council never grants approval by itself — a human must still approve
    # via the content-review workflow, and MARKETER is not allowed to.
    r_approve = client.post(f"/api/v1/content-items/{content['id']}/approve", json={})
    assert r_approve.status_code == 403
