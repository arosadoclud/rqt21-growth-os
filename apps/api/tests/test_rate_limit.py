from __future__ import annotations

from fastapi.testclient import TestClient

from app import rate_limit
from app.core import config as config_mod


def _override(monkeypatch, **kwargs):
    for k, v in kwargs.items():
        monkeypatch.setattr(config_mod.settings, k, v, raising=True)


def test_login_ip_rate_limit(client: TestClient, make_user, monkeypatch):
    make_user("lim@example.com")
    _override(monkeypatch, rl_login_ip_limit=3, rl_login_window_seconds=60)
    rate_limit.reset()

    for _ in range(3):
        r = client.post(
            "/api/v1/auth/login",
            json={"email": "lim@example.com", "password": "wrong"},
        )
        assert r.status_code == 401

    r = client.post(
        "/api/v1/auth/login",
        json={"email": "lim@example.com", "password": "wrong"},
    )
    assert r.status_code == 429
    assert "Retry-After" in r.headers
    assert int(r.headers["Retry-After"]) >= 1


def test_login_email_rate_limit(client: TestClient, make_user, monkeypatch):
    make_user("burst@example.com")
    _override(
        monkeypatch,
        rl_login_ip_limit=1000,
        rl_login_email_limit=2,
        rl_login_window_seconds=60,
    )
    rate_limit.reset()

    for _ in range(2):
        r = client.post(
            "/api/v1/auth/login",
            json={"email": "burst@example.com", "password": "wrong"},
        )
        assert r.status_code == 401

    r = client.post(
        "/api/v1/auth/login",
        json={"email": "burst@example.com", "password": "wrong"},
    )
    assert r.status_code == 429


def test_rate_limit_recovers_after_reset(client: TestClient, make_user, monkeypatch):
    make_user("recov@example.com")
    _override(monkeypatch, rl_login_ip_limit=1, rl_login_window_seconds=60)
    rate_limit.reset()

    r1 = client.post(
        "/api/v1/auth/login",
        json={"email": "recov@example.com", "password": "wrong"},
    )
    assert r1.status_code == 401

    r2 = client.post(
        "/api/v1/auth/login",
        json={"email": "recov@example.com", "password": "wrong"},
    )
    assert r2.status_code == 429

    rate_limit.reset()  # simulates window elapsing

    r3 = client.post(
        "/api/v1/auth/login",
        json={"email": "recov@example.com", "password": "Password1!"},
    )
    assert r3.status_code == 200


def test_refresh_rate_limit(client: TestClient, monkeypatch):
    _override(monkeypatch, rl_refresh_ip_limit=2, rl_refresh_window_seconds=60)
    rate_limit.reset()

    for _ in range(2):
        r = client.post("/api/v1/auth/refresh")
        assert r.status_code == 401  # no cookie, but still counts

    r = client.post("/api/v1/auth/refresh")
    assert r.status_code == 429
