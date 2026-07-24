from __future__ import annotations

from app.models.membership import Role


def _seed_notification(db, org_id, user_id):
    from app.models.automation import Notification
    from app.models.enums import NotificationType
    from app.utils.public_id import make as make_public_id

    n = Notification(
        public_id=make_public_id("nt"),
        organization_id=org_id,
        user_id=user_id,
        notification_type=NotificationType.CONTENT_APPROVED,
        title="Content approved",
        message="Your content was approved.",
        resource_type="content_item",
        resource_public_id="ct_test123",
    )
    db.add(n)
    db.commit()
    db.refresh(n)
    return n


def test_list_notifications_for_current_user(bootstrap, db):
    client, org_id, user = bootstrap(Role.OWNER, "notif-list@example.com")
    _seed_notification(db, org_id, user.id)
    r = client.get("/api/v1/notifications")
    assert r.status_code == 200
    body = r.json()
    assert len(body) == 1
    assert body[0]["title"] == "Content approved"
    assert body[0]["read_at"] is None


def test_mark_read(bootstrap, db):
    client, org_id, user = bootstrap(Role.OWNER, "notif-read@example.com")
    n = _seed_notification(db, org_id, user.id)
    r = client.post(f"/api/v1/notifications/{n.id}/read")
    assert r.status_code == 200
    assert r.json()["read_at"] is not None

    r2 = client.get("/api/v1/notifications?unread_only=true")
    assert len(r2.json()) == 0


def test_notifications_isolated_per_user(bootstrap, make_user, add_member, db):
    client_a, org_id, user_a = bootstrap(Role.OWNER, "notif-a@example.com")
    _seed_notification(db, org_id, user_a.id)

    from app.main import app
    from app.models.organization import Organization
    from tests.conftest import AuthedClient

    org = db.get(Organization, org_id)
    user_b = make_user("notif-b@example.com")
    add_member(user_b, org, Role.MARKETER)
    client_b = AuthedClient(app)
    r = client_b.post(
        "/api/v1/auth/login", json={"email": "notif-b@example.com", "password": "Password1!"}
    )
    assert r.status_code == 200
    client_b.headers["X-Organization-Id"] = str(org_id)

    r2 = client_b.get("/api/v1/notifications")
    assert r2.json() == []


def test_mark_read_of_other_users_notification_is_404(bootstrap, make_user, add_member, db):
    client_a, org_id, user_a = bootstrap(Role.OWNER, "notif-owner-x@example.com")
    n = _seed_notification(db, org_id, user_a.id)

    from app.main import app
    from app.models.organization import Organization
    from tests.conftest import AuthedClient

    org = db.get(Organization, org_id)
    user_b = make_user("notif-b2@example.com")
    add_member(user_b, org, Role.MARKETER)
    client_b = AuthedClient(app)
    r = client_b.post(
        "/api/v1/auth/login", json={"email": "notif-b2@example.com", "password": "Password1!"}
    )
    assert r.status_code == 200
    client_b.headers["X-Organization-Id"] = str(org_id)

    r2 = client_b.post(f"/api/v1/notifications/{n.id}/read")
    assert r2.status_code == 404


def test_publication_failure_generates_notification(bootstrap):
    import base64
    import uuid as _u

    _PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 200

    client, _, _ = bootstrap(Role.OWNER, "notif-pubfail@example.com")
    slug = f"brand-{_u.uuid4().hex[:6]}"
    brand_id = client.post("/api/v1/brands", json={"name": slug, "slug": slug}).json()["id"]
    cid = client.post(
        "/api/v1/content-items", json={"brand_id": brand_id, "title": "Fail me"}
    ).json()["id"]
    client.post(f"/api/v1/content-items/{cid}/approve", json={"score": 90})
    conn_id = client.post(
        "/api/v1/publishing-connections",
        json={"brand_id": brand_id, "platform": "INSTAGRAM", "provider": "MOCK", "account_name": "m"},
    ).json()["id"]
    asset_id = client.post(
        "/api/v1/assets/init-upload",
        json={
            "filename": "p.png", "mime_type": "image/png", "size_bytes": len(_PNG),
            "asset_type": "IMAGE", "brand_id": brand_id, "alt_text": "alt",
        },
    ).json()["asset_id"]
    client.post(
        "/api/v1/assets/complete-upload",
        json={"asset_id": asset_id, "content_base64": base64.b64encode(_PNG).decode()},
    )
    pub_id = client.post(
        "/api/v1/publications",
        json={
            "content_item_id": cid, "brand_id": brand_id, "publishing_connection_id": conn_id,
            "asset_id": asset_id, "platform": "INSTAGRAM", "publication_type": "POST",
            "caption": "Fallo __mock_permanent__ de prueba",
        },
    ).json()["id"]
    client.post(f"/api/v1/publications/{pub_id}/validate")
    client.post(f"/api/v1/publications/{pub_id}/publish")

    r = client.get("/api/v1/notifications")
    types = [n["notification_type"] for n in r.json()]
    assert "PUBLICATION_FAILED" in types
