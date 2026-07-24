from __future__ import annotations

import uuid as _u

from app.models.membership import Role


def _brand(client) -> str:
    slug = f"brand-{_u.uuid4().hex[:6]}"
    return client.post("/api/v1/brands", json={"name": slug, "slug": slug}).json()["id"]


def _mock_connection(client, brand_id: str) -> str:
    r = client.post(
        "/api/v1/publishing-connections",
        json={
            "brand_id": brand_id,
            "platform": "INSTAGRAM",
            "provider": "MOCK",
            "account_name": "rqt21.mock",
        },
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _create_draft_rule(client, brand_id: str, connection_id: str, name: str = "Crear borrador al aprobar"):
    r = client.post(
        "/api/v1/automations",
        json={
            "brand_id": brand_id,
            "name": name,
            "trigger_type": "CONTENT_APPROVED",
            "conditions": {},
            "action_type": "CREATE_PUBLICATION_DRAFT",
            "action_config": {
                "publishing_connection_id": connection_id,
                "publication_type": "POST",
                "default_caption": "Auto draft",
            },
            "is_active": True,
        },
    )
    assert r.status_code == 201, r.text
    return r.json()


def test_content_approved_creates_publication_draft(bootstrap, db):
    from sqlalchemy import select

    from app.models.publishing import Publication

    client, org_id, _ = bootstrap(Role.OWNER, "auto-draft@example.com")
    brand_id = _brand(client)
    conn_id = _mock_connection(client, brand_id)
    _create_draft_rule(client, brand_id, conn_id)

    cid = client.post(
        "/api/v1/content-items", json={"brand_id": brand_id, "title": "Auto content"}
    ).json()["id"]
    r = client.post(f"/api/v1/content-items/{cid}/approve", json={"score": 90})
    assert r.status_code == 201

    pubs = db.execute(
        select(Publication).where(
            Publication.organization_id == org_id, Publication.content_item_id == _u.UUID(cid)
        )
    ).scalars().all()
    assert len(pubs) == 1
    assert pubs[0].status.value == "DRAFT"


def test_automation_never_auto_publishes(bootstrap, db):
    from sqlalchemy import select

    from app.models.publishing import Publication

    client, org_id, _ = bootstrap(Role.OWNER, "auto-nopublish@example.com")
    brand_id = _brand(client)
    conn_id = _mock_connection(client, brand_id)
    _create_draft_rule(client, brand_id, conn_id)

    cid = client.post(
        "/api/v1/content-items", json={"brand_id": brand_id, "title": "Never auto"}
    ).json()["id"]
    client.post(f"/api/v1/content-items/{cid}/approve", json={"score": 90})

    pub = db.execute(
        select(Publication).where(Publication.organization_id == org_id)
    ).scalars().first()
    assert pub.status.value == "DRAFT"
    assert pub.published_at is None


def test_avoids_duplicate_draft_on_second_approval(bootstrap):
    client, _, _ = bootstrap(Role.OWNER, "auto-noloop@example.com")
    brand_id = _brand(client)
    conn_id = _mock_connection(client, brand_id)
    _create_draft_rule(client, brand_id, conn_id)

    cid = client.post(
        "/api/v1/content-items", json={"brand_id": brand_id, "title": "Twice approved"}
    ).json()["id"]
    client.post(f"/api/v1/content-items/{cid}/approve", json={"score": 90})
    client.post(f"/api/v1/content-items/{cid}/approve", json={"score": 95})

    r = client.get(f"/api/v1/publications?content_item_id={cid}")
    assert len(r.json()) == 1


def test_execution_limit_prevents_loop(bootstrap, db, monkeypatch):
    from sqlalchemy import select

    from app.core.config import settings
    from app.models.audit_log import AuditLog

    monkeypatch.setattr(settings, "automation_max_executions_per_rule", 1)

    client, org_id, _ = bootstrap(Role.OWNER, "auto-limit@example.com")
    brand_id = _brand(client)
    conn_id = _mock_connection(client, brand_id)
    _create_draft_rule(client, brand_id, conn_id)

    for i in range(3):
        cid = client.post(
            "/api/v1/content-items", json={"brand_id": brand_id, "title": f"Content {i}"}
        ).json()["id"]
        client.post(f"/api/v1/content-items/{cid}/approve", json={"score": 90})

    loop_events = db.execute(
        select(AuditLog).where(
            AuditLog.organization_id == org_id, AuditLog.action == "automation.loop_prevented"
        )
    ).scalars().all()
    assert len(loop_events) >= 1


def test_deactivated_rule_does_not_fire(bootstrap, db):
    from sqlalchemy import select

    from app.models.publishing import Publication

    client, org_id, _ = bootstrap(Role.OWNER, "auto-inactive@example.com")
    brand_id = _brand(client)
    conn_id = _mock_connection(client, brand_id)
    rule = _create_draft_rule(client, brand_id, conn_id)
    r = client.patch(f"/api/v1/automations/{rule['id']}", json={"is_active": False})
    assert r.status_code == 200
    assert r.json()["is_active"] is False

    cid = client.post(
        "/api/v1/content-items", json={"brand_id": brand_id, "title": "Should not draft"}
    ).json()["id"]
    client.post(f"/api/v1/content-items/{cid}/approve", json={"score": 90})

    pubs = db.execute(
        select(Publication).where(Publication.organization_id == org_id)
    ).scalars().all()
    assert len(pubs) == 0


def test_marketer_cannot_write_automations(bootstrap):
    client, _, _ = bootstrap(Role.MARKETER, "auto-mkt@example.com")
    brand_id = _brand(client)
    r = client.post(
        "/api/v1/automations",
        json={
            "brand_id": brand_id,
            "name": "Nope",
            "trigger_type": "CONTENT_APPROVED",
            "conditions": {},
            "action_type": "CREATE_PUBLICATION_DRAFT",
            "action_config": {},
        },
    )
    assert r.status_code == 403


def test_rejects_non_predefined_combination(bootstrap):
    client, _, _ = bootstrap(Role.OWNER, "auto-badcombo@example.com")
    brand_id = _brand(client)
    r = client.post(
        "/api/v1/automations",
        json={
            "brand_id": brand_id,
            "name": "Invalid combo",
            "trigger_type": "LEAD_CREATED",
            "conditions": {},
            "action_type": "CREATE_PUBLICATION_DRAFT",
            "action_config": {},
        },
    )
    assert r.status_code == 400


def test_automation_summary(bootstrap):
    client, _, _ = bootstrap(Role.OWNER, "auto-summary@example.com")
    brand_id = _brand(client)
    conn_id = _mock_connection(client, brand_id)
    _create_draft_rule(client, brand_id, conn_id)
    r = client.get("/api/v1/automations/summary")
    assert r.status_code == 200
    assert r.json()["active_rules"] >= 1
