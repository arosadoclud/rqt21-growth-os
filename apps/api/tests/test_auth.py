from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.security import create_access_token, hash_refresh_token
from app.deps import ACCESS_COOKIE, REFRESH_COOKIE
from app.models.membership import Role
from app.models.refresh_token import RefreshToken


def test_login_success(client: TestClient, make_user, make_org, add_member):
    u = make_user("alice@example.com")
    org = make_org("acme")
    add_member(u, org, Role.OWNER)
    r = client.post(
        "/api/v1/auth/login",
        json={"email": "alice@example.com", "password": "Password1!"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["user"]["email"] == "alice@example.com"
    assert len(body["organizations"]) == 1
    assert body["organizations"][0]["role"] == "OWNER"
    assert client.cookies.get(ACCESS_COOKIE)
    assert client.cookies.get(REFRESH_COOKIE)


def test_login_bad_password(client: TestClient, make_user):
    make_user("bob@example.com")
    r = client.post(
        "/api/v1/auth/login",
        json={"email": "bob@example.com", "password": "wrong"},
    )
    assert r.status_code == 401


def test_login_unknown_user(client: TestClient):
    r = client.post(
        "/api/v1/auth/login",
        json={"email": "nope@example.com", "password": "whatever"},
    )
    assert r.status_code == 401


def test_me_requires_auth(client: TestClient):
    r = client.get("/api/v1/me")
    assert r.status_code == 401


def test_me_ok(client: TestClient, make_user, login):
    make_user("cara@example.com")
    login("cara@example.com")
    r = client.get("/api/v1/me")
    assert r.status_code == 200
    assert r.json()["user"]["email"] == "cara@example.com"


def test_refresh_rotates_and_revokes_old(client: TestClient, make_user, login, db):
    make_user("dave@example.com")
    login("dave@example.com")
    old_refresh = client.cookies.get(REFRESH_COOKIE)
    assert old_refresh
    r = client.post("/api/v1/auth/refresh")
    assert r.status_code == 200
    new_refresh = client.cookies.get(REFRESH_COOKIE)
    assert new_refresh
    assert new_refresh != old_refresh

    old = db.execute(
        select(RefreshToken).where(RefreshToken.token_hash == hash_refresh_token(old_refresh))
    ).scalar_one()
    assert old.revoked_at is not None
    assert old.replaced_by is not None


def test_refresh_without_cookie(client: TestClient):
    r = client.post("/api/v1/auth/refresh")
    assert r.status_code == 401


def test_logout_revokes_refresh(client: TestClient, make_user, login, db):
    make_user("erin@example.com")
    login("erin@example.com")
    refresh = client.cookies.get(REFRESH_COOKIE)
    r = client.post("/api/v1/auth/logout")
    assert r.status_code == 204

    row = db.execute(
        select(RefreshToken).where(RefreshToken.token_hash == hash_refresh_token(refresh))
    ).scalar_one()
    assert row.revoked_at is not None

    client.cookies.delete(REFRESH_COOKIE)
    client.cookies.set(REFRESH_COOKIE, refresh)
    r2 = client.post("/api/v1/auth/refresh")
    assert r2.status_code == 401


def test_access_token_expiry(client: TestClient, make_user, db):
    user = make_user("frank@example.com")
    expired, _ = create_access_token(
        user_id=str(user.id),
        ttl_seconds=-10,
        now=datetime.now(UTC) - timedelta(seconds=10),
    )
    client.cookies.set(ACCESS_COOKIE, expired)
    r = client.get("/api/v1/me")
    assert r.status_code == 401


def test_password_never_returned(client: TestClient, make_user, login):
    make_user("gary@example.com")
    login("gary@example.com")
    r = client.get("/api/v1/me")
    body = r.json()
    assert "password" not in body["user"]
    assert "password_hash" not in body["user"]
