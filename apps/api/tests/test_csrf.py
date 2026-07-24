from __future__ import annotations

from fastapi.testclient import TestClient

from app.csrf import CSRF_COOKIE, CSRF_HEADER


def test_login_does_not_require_csrf(raw_client: TestClient, make_user):
    make_user("csrflogin@example.com")
    r = raw_client.post(
        "/api/v1/auth/login",
        json={"email": "csrflogin@example.com", "password": "Password1!"},
    )
    assert r.status_code == 200
    assert raw_client.cookies.get(CSRF_COOKIE)


def test_mutation_without_csrf_header_is_rejected(raw_client: TestClient, make_user):
    make_user("nomut@example.com")
    r = raw_client.post(
        "/api/v1/auth/login",
        json={"email": "nomut@example.com", "password": "Password1!"},
    )
    assert r.status_code == 200

    r2 = raw_client.post(
        "/api/v1/organizations",
        json={"name": "X", "slug": "x-org"},
    )
    assert r2.status_code == 403
    assert r2.json()["detail"] == "missing CSRF token"


def test_mutation_with_wrong_csrf_header_is_rejected(raw_client: TestClient, make_user):
    make_user("wrong@example.com")
    raw_client.post(
        "/api/v1/auth/login",
        json={"email": "wrong@example.com", "password": "Password1!"},
    )
    r = raw_client.post(
        "/api/v1/organizations",
        json={"name": "X", "slug": "x-org2"},
        headers={CSRF_HEADER: "tampered-value"},
    )
    assert r.status_code == 403
    assert r.json()["detail"] == "invalid CSRF token"


def test_mutation_with_matching_csrf_header_succeeds(raw_client: TestClient, make_user):
    make_user("ok@example.com")
    raw_client.post(
        "/api/v1/auth/login",
        json={"email": "ok@example.com", "password": "Password1!"},
    )
    token = raw_client.cookies.get(CSRF_COOKIE)
    assert token
    r = raw_client.post(
        "/api/v1/organizations",
        json={"name": "Ok Co", "slug": "ok-co"},
        headers={CSRF_HEADER: token},
    )
    assert r.status_code == 201


def test_get_endpoints_ignore_csrf(raw_client: TestClient, make_user):
    make_user("getonly@example.com")
    raw_client.post(
        "/api/v1/auth/login",
        json={"email": "getonly@example.com", "password": "Password1!"},
    )
    r = raw_client.get("/api/v1/me")
    assert r.status_code == 200


def test_logout_does_not_require_csrf(raw_client: TestClient, make_user):
    """Logout is idempotent revocation of the caller's own session; even if
    forged, the impact is signing the victim out."""
    make_user("logout_csrf@example.com")
    raw_client.post(
        "/api/v1/auth/login",
        json={"email": "logout_csrf@example.com", "password": "Password1!"},
    )
    r = raw_client.post("/api/v1/auth/logout")
    assert r.status_code == 204
