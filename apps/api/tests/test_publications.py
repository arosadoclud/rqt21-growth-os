from __future__ import annotations

import base64
import uuid as _u
from datetime import UTC, datetime, timedelta

from app.models.membership import Role

_PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 200


def _brand(client) -> str:
    slug = f"brand-{_u.uuid4().hex[:6]}"
    return client.post("/api/v1/brands", json={"name": slug, "slug": slug}).json()["id"]


def _member_client(make_user, add_member, db, org_id, role: Role, email: str):
    from app.main import app
    from app.models.organization import Organization
    from tests.conftest import AuthedClient

    org = db.get(Organization, org_id)
    u = make_user(email)
    add_member(u, org, role)
    c = AuthedClient(app)
    r = c.post("/api/v1/auth/login", json={"email": email, "password": "Password1!"})
    assert r.status_code == 200, r.text
    c.headers["X-Organization-Id"] = str(org_id)
    return c


def _approve(owner_client, brand_id: str) -> str:
    cid = owner_client.post(
        "/api/v1/content-items", json={"brand_id": brand_id, "title": "Lasana keto"}
    ).json()["id"]
    r = owner_client.post(f"/api/v1/content-items/{cid}/approve", json={"score": 90})
    assert r.status_code == 201, r.text
    return cid


def _mock_connection(owner_client, brand_id: str) -> str:
    r = owner_client.post(
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


def _manual_connection(owner_client, brand_id: str) -> str:
    r = owner_client.post(
        "/api/v1/publishing-connections",
        json={
            "brand_id": brand_id,
            "platform": "INSTAGRAM",
            "provider": "MANUAL",
            "account_name": "Equipo social",
        },
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _ready_asset(owner_client, brand_id: str) -> str:
    r = owner_client.post(
        "/api/v1/assets/init-upload",
        json={
            "filename": "photo.png",
            "mime_type": "image/png",
            "size_bytes": len(_PNG),
            "asset_type": "IMAGE",
            "brand_id": brand_id,
            "alt_text": "Lasana keto servida",
        },
    )
    asset_id = r.json()["asset_id"]
    r2 = owner_client.post(
        "/api/v1/assets/complete-upload",
        json={"asset_id": asset_id, "content_base64": base64.b64encode(_PNG).decode()},
    )
    assert r2.status_code == 200
    return asset_id


def _create_publication(client, *, content_id, brand_id, connection_id, asset_id=None, caption="Hola, prueba de publicacion."):
    payload = {
        "content_item_id": content_id,
        "brand_id": brand_id,
        "publishing_connection_id": connection_id,
        "asset_id": asset_id,
        "platform": "INSTAGRAM",
        "publication_type": "POST",
        "caption": caption,
    }
    return client.post("/api/v1/publications", json=payload)


def _full_setup(bootstrap, make_user, add_member, db, actor_role: Role, actor_email: str):
    """Bootstrap an OWNER to approve content + create a MOCK connection +
    upload a READY asset, then return an actor client with the given role in
    the same org, plus the ids the actor will need."""
    owner_client, org_id, _owner = bootstrap(Role.OWNER, f"owner-{actor_email}")
    brand_id = _brand(owner_client)
    cid = _approve(owner_client, brand_id)
    conn_id = _mock_connection(owner_client, brand_id)
    asset_id = _ready_asset(owner_client, brand_id)
    actor = (
        owner_client
        if actor_role == Role.OWNER
        else _member_client(make_user, add_member, db, org_id, actor_role, actor_email)
    )
    return actor, org_id, brand_id, cid, conn_id, asset_id


def test_create_publication_from_approved_content(bootstrap, make_user, add_member, db):
    actor, _, brand_id, cid, conn_id, asset_id = _full_setup(
        bootstrap, make_user, add_member, db, Role.MARKETER, "pub-create@example.com"
    )
    r = _create_publication(actor, content_id=cid, brand_id=brand_id, connection_id=conn_id, asset_id=asset_id)
    assert r.status_code == 201, r.text
    assert r.json()["status"] == "DRAFT"
    assert r.json()["public_id"].startswith("pub_")


def test_validate_blocks_unapproved_content(bootstrap):
    client, _, _ = bootstrap(Role.OWNER, "pub-unapproved@example.com")
    brand_id = _brand(client)
    cid = client.post(
        "/api/v1/content-items", json={"brand_id": brand_id, "title": "Sin aprobar"}
    ).json()["id"]
    conn_id = _mock_connection(client, brand_id)
    asset_id = _ready_asset(client, brand_id)
    pub_id = _create_publication(
        client, content_id=cid, brand_id=brand_id, connection_id=conn_id, asset_id=asset_id
    ).json()["id"]
    r = client.post(f"/api/v1/publications/{pub_id}/validate")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is False
    assert any("APPROVED" in e for e in body["errors"])


def test_validate_blocks_council_blocked_content(bootstrap, db):
    from app.models.ai import CouncilReview
    from app.models.enums import CouncilDecision, CouncilReviewerType
    from app.utils.public_id import make as make_public_id

    client, org_id, _ = bootstrap(Role.OWNER, "pub-blocked@example.com")
    brand_id = _brand(client)
    cid = _approve(client, brand_id)
    conn_id = _mock_connection(client, brand_id)
    asset_id = _ready_asset(client, brand_id)

    job_id = client.post(
        "/api/v1/generation-jobs",
        json={
            "brand_id": brand_id,
            "generation_type": "SOCIAL_POST",
            "input": {"objective": "engagement", "platform": "INSTAGRAM", "topic": "test"},
        },
    ).json()["id"]

    db.add(
        CouncilReview(
            public_id=make_public_id("cr"),
            organization_id=org_id,
            generation_job_id=_u.UUID(job_id),
            content_item_id=_u.UUID(cid),
            reviewer_type=CouncilReviewerType.COMPLIANCE,
            score=0,
            decision=CouncilDecision.BLOCKED,
            summary="Blocked in test",
            blocking_issues=["fake medical claim"],
        )
    )
    db.commit()

    pub_id = _create_publication(
        client, content_id=cid, brand_id=brand_id, connection_id=conn_id, asset_id=asset_id
    ).json()["id"]
    r = client.post(f"/api/v1/publications/{pub_id}/validate")
    body = r.json()
    assert body["ok"] is False
    assert any("BLOCKED" in e for e in body["errors"])


def test_validate_requires_asset_for_instagram(bootstrap):
    client, _, _ = bootstrap(Role.OWNER, "pub-noasset@example.com")
    brand_id = _brand(client)
    cid = _approve(client, brand_id)
    conn_id = _mock_connection(client, brand_id)
    pub_id = _create_publication(
        client, content_id=cid, brand_id=brand_id, connection_id=conn_id, asset_id=None
    ).json()["id"]
    r = client.post(f"/api/v1/publications/{pub_id}/validate")
    body = r.json()
    assert body["ok"] is False
    assert any("requires an asset" in e for e in body["errors"])


def test_validate_publication_draft_blocks_more_than_five_hashtags():
    """PublicationCreate already rejects >5 hashtags at the API layer, but
    validate_publication_draft is the actual pre-publish gate and must
    enforce it independently too — e.g. app.workers.headline_scheduler
    builds Publication rows directly, bypassing that schema entirely."""
    from app.models.enums import Platform, PublicationType
    from app.publishing.validation import validate_publication_draft

    result = validate_publication_draft(
        platform=Platform.FACEBOOK,
        publication_type=PublicationType.POST,
        caption="Una receta simple y deliciosa para hoy.",
        hashtags=["#a", "#b", "#c", "#d", "#e", "#f"],
        asset=None,
    )
    assert result.ok is False
    assert any("spammy" in e for e in result.errors)


def test_validate_publication_draft_blocks_long_caption_and_cta():
    from app.models.enums import Platform, PublicationType
    from app.publishing.validation import validate_publication_draft

    long_caption = "palabra " * 190  # well past the 200-word combined cap
    result = validate_publication_draft(
        platform=Platform.FACEBOOK,
        publication_type=PublicationType.POST,
        caption=long_caption,
        hashtags=["#keto"],
        asset=None,
        cta="palabra " * 20,
    )
    assert result.ok is False
    assert any("200 words" in e for e in result.errors)


def test_validate_publication_draft_allows_five_hashtags_and_short_caption():
    from app.models.enums import Platform, PublicationType
    from app.publishing.validation import validate_publication_draft

    result = validate_publication_draft(
        platform=Platform.FACEBOOK,
        publication_type=PublicationType.POST,
        caption="Una receta simple y deliciosa para hoy.",
        hashtags=["#a", "#b", "#c", "#d", "#e"],
        asset=None,
        cta="Ver más",
    )
    assert result.ok is True


def test_full_ready_schedule_mock_publish_flow(bootstrap):
    client, _, _ = bootstrap(Role.OWNER, "pub-flow@example.com")
    brand_id = _brand(client)
    cid = _approve(client, brand_id)
    conn_id = _mock_connection(client, brand_id)
    asset_id = _ready_asset(client, brand_id)
    pub_id = _create_publication(
        client, content_id=cid, brand_id=brand_id, connection_id=conn_id, asset_id=asset_id
    ).json()["id"]

    r_val = client.post(f"/api/v1/publications/{pub_id}/validate")
    assert r_val.json()["ok"] is True

    r_pub = client.post(f"/api/v1/publications/{pub_id}/publish")
    assert r_pub.status_code == 200, r_pub.text
    body = r_pub.json()
    assert body["status"] == "PUBLISHED"
    assert body["external_publication_id"]
    assert body["published_at"] is not None

    r_attempts = client.get(f"/api/v1/publications/{pub_id}/attempts")
    assert len(r_attempts.json()) == 1
    assert r_attempts.json()[0]["status"] == "SUCCEEDED"


def test_marketer_cannot_authorize_automatic_publish(bootstrap, make_user, add_member, db):
    actor, _, brand_id, cid, conn_id, asset_id = _full_setup(
        bootstrap, make_user, add_member, db, Role.MARKETER, "pub-mkt-noauth@example.com"
    )
    pub_id = _create_publication(
        actor, content_id=cid, brand_id=brand_id, connection_id=conn_id, asset_id=asset_id
    ).json()["id"]
    actor.post(f"/api/v1/publications/{pub_id}/validate")
    r = actor.post(f"/api/v1/publications/{pub_id}/publish")
    assert r.status_code == 403


def test_idempotent_create_returns_same_draft(bootstrap):
    client, _, _ = bootstrap(Role.OWNER, "pub-idem@example.com")
    brand_id = _brand(client)
    cid = _approve(client, brand_id)
    conn_id = _mock_connection(client, brand_id)
    asset_id = _ready_asset(client, brand_id)
    r1 = _create_publication(client, content_id=cid, brand_id=brand_id, connection_id=conn_id, asset_id=asset_id)
    r2 = _create_publication(client, content_id=cid, brand_id=brand_id, connection_id=conn_id, asset_id=asset_id)
    assert r1.json()["id"] == r2.json()["id"]


def test_schedule_requires_ready_and_future_date(bootstrap):
    client, _, _ = bootstrap(Role.OWNER, "pub-sched@example.com")
    brand_id = _brand(client)
    cid = _approve(client, brand_id)
    conn_id = _mock_connection(client, brand_id)
    asset_id = _ready_asset(client, brand_id)
    pub_id = _create_publication(
        client, content_id=cid, brand_id=brand_id, connection_id=conn_id, asset_id=asset_id
    ).json()["id"]

    r_early = client.post(
        f"/api/v1/publications/{pub_id}/schedule",
        json={"scheduled_for": (datetime.now(UTC) + timedelta(days=1)).isoformat()},
    )
    assert r_early.status_code == 400

    client.post(f"/api/v1/publications/{pub_id}/validate")

    r_past = client.post(
        f"/api/v1/publications/{pub_id}/schedule",
        json={"scheduled_for": (datetime.now(UTC) - timedelta(days=1)).isoformat()},
    )
    assert r_past.status_code == 400

    r_ok = client.post(
        f"/api/v1/publications/{pub_id}/schedule",
        json={"scheduled_for": (datetime.now(UTC) + timedelta(days=1)).isoformat(), "timezone": "America/Santo_Domingo"},
    )
    assert r_ok.status_code == 200
    assert r_ok.json()["status"] == "SCHEDULED"


def test_rate_limit_sentinel_schedules_retry(bootstrap):
    client, _, _ = bootstrap(Role.OWNER, "pub-ratelimit@example.com")
    brand_id = _brand(client)
    cid = _approve(client, brand_id)
    conn_id = _mock_connection(client, brand_id)
    asset_id = _ready_asset(client, brand_id)
    pub_id = _create_publication(
        client, content_id=cid, brand_id=brand_id, connection_id=conn_id, asset_id=asset_id,
        caption="Aviso __mock_rate_limit__ de prueba",
    ).json()["id"]
    client.post(f"/api/v1/publications/{pub_id}/validate")
    r = client.post(f"/api/v1/publications/{pub_id}/publish")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "RETRY_SCHEDULED"
    assert body["next_retry_at"] is not None


def test_permanent_error_marks_failed_and_notifies(bootstrap, db):
    from sqlalchemy import select

    from app.models.automation import Notification

    client, org_id, _ = bootstrap(Role.OWNER, "pub-permanent@example.com")
    brand_id = _brand(client)
    cid = _approve(client, brand_id)
    conn_id = _mock_connection(client, brand_id)
    asset_id = _ready_asset(client, brand_id)
    pub_id = _create_publication(
        client, content_id=cid, brand_id=brand_id, connection_id=conn_id, asset_id=asset_id,
        caption="Aviso __mock_permanent__ de prueba",
    ).json()["id"]
    client.post(f"/api/v1/publications/{pub_id}/validate")
    r = client.post(f"/api/v1/publications/{pub_id}/publish")
    assert r.json()["status"] == "FAILED"

    notifs = db.execute(
        select(Notification).where(
            Notification.organization_id == org_id,
            Notification.notification_type == "PUBLICATION_FAILED",
        )
    ).scalars().all()
    assert len(notifs) == 1


def test_manual_retry_by_owner(bootstrap):
    client, _, _ = bootstrap(Role.OWNER, "pub-retry@example.com")
    brand_id = _brand(client)
    cid = _approve(client, brand_id)
    conn_id = _mock_connection(client, brand_id)
    asset_id = _ready_asset(client, brand_id)
    pub_id = _create_publication(
        client, content_id=cid, brand_id=brand_id, connection_id=conn_id, asset_id=asset_id,
        caption="Aviso __mock_recoverable__ de prueba",
    ).json()["id"]
    client.post(f"/api/v1/publications/{pub_id}/validate")
    r1 = client.post(f"/api/v1/publications/{pub_id}/publish")
    assert r1.json()["status"] == "RETRY_SCHEDULED"

    r2 = client.post(f"/api/v1/publications/{pub_id}/retry")
    assert r2.status_code == 200
    assert r2.json()["status"] in ("RETRY_SCHEDULED", "FAILED")
    assert r2.json()["attempt_count"] == 2


def test_cancel_publication(bootstrap, make_user, add_member, db):
    actor, _, brand_id, cid, conn_id, asset_id = _full_setup(
        bootstrap, make_user, add_member, db, Role.MARKETER, "pub-cancel@example.com"
    )
    pub_id = _create_publication(
        actor, content_id=cid, brand_id=brand_id, connection_id=conn_id, asset_id=asset_id
    ).json()["id"]
    r = actor.post(f"/api/v1/publications/{pub_id}/cancel")
    assert r.status_code == 200
    assert r.json()["status"] == "CANCELLED"


def test_mark_published_manual(bootstrap, make_user, add_member, db):
    owner_client, org_id, _ = bootstrap(Role.OWNER, "owner-pub-manual@example.com")
    brand_id = _brand(owner_client)
    cid = _approve(owner_client, brand_id)
    conn_id = _manual_connection(owner_client, brand_id)
    asset_id = _ready_asset(owner_client, brand_id)
    actor = _member_client(make_user, add_member, db, org_id, Role.MARKETER, "pub-manual@example.com")

    pub_id = _create_publication(
        actor, content_id=cid, brand_id=brand_id, connection_id=conn_id, asset_id=asset_id
    ).json()["id"]

    r_auto = actor.post(f"/api/v1/publications/{pub_id}/publish")
    assert r_auto.status_code == 400

    r = actor.post(
        f"/api/v1/publications/{pub_id}/mark-published",
        json={"external_url": "https://instagram.com/p/abc123"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "PUBLISHED"
    assert body["external_url"] == "https://instagram.com/p/abc123"

    attempts = actor.get(f"/api/v1/publications/{pub_id}/attempts").json()
    assert len(attempts) == 1
    assert attempts[0]["status"] == "SUCCEEDED"


def test_cross_org_publication_isolated(bootstrap):
    client_a, _, _ = bootstrap(Role.OWNER, "pub-a@example.com")
    brand_id = _brand(client_a)
    cid = _approve(client_a, brand_id)
    conn_id = _mock_connection(client_a, brand_id)
    asset_id = _ready_asset(client_a, brand_id)
    pub_id = _create_publication(
        client_a, content_id=cid, brand_id=brand_id, connection_id=conn_id, asset_id=asset_id
    ).json()["id"]

    client_b, _, _ = bootstrap(Role.OWNER, "pub-b@example.com")
    r = client_b.get(f"/api/v1/publications/{pub_id}")
    assert r.status_code == 404


def test_sales_cannot_prepare_publications(bootstrap):
    client, _, _ = bootstrap(Role.SALES, "pub-sales@example.com")
    r = client.post(
        "/api/v1/publications",
        json={
            "content_item_id": str(_u.uuid4()),
            "brand_id": str(_u.uuid4()),
            "publishing_connection_id": str(_u.uuid4()),
            "platform": "INSTAGRAM",
            "publication_type": "POST",
            "caption": "test",
        },
    )
    assert r.status_code == 403


def test_publishing_summary(bootstrap):
    client, _, _ = bootstrap(Role.OWNER, "pub-summary@example.com")
    brand_id = _brand(client)
    cid = _approve(client, brand_id)
    conn_id = _mock_connection(client, brand_id)
    asset_id = _ready_asset(client, brand_id)
    pub_id = _create_publication(
        client, content_id=cid, brand_id=brand_id, connection_id=conn_id, asset_id=asset_id
    ).json()["id"]
    client.post(f"/api/v1/publications/{pub_id}/validate")
    client.post(f"/api/v1/publications/{pub_id}/publish")

    r = client.get("/api/v1/publishing/summary")
    assert r.status_code == 200
    body = r.json()
    assert body["published"] >= 1
    assert "INSTAGRAM" in body["by_platform"]
