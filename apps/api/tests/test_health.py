from __future__ import annotations

from fastapi.testclient import TestClient


def test_health_liveness(client: TestClient):
    r = client.get("/api/v1/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_ready_reports_db_and_migrations(client: TestClient):
    r = client.get("/api/v1/ready")
    assert r.status_code == 200
    body = r.json()
    assert body["db"]["ok"] is True
    assert body["migrations"]["ok"] is True
    assert body["migrations"]["current"] is not None


def test_security_headers_present(client: TestClient):
    r = client.get("/api/v1/health")
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["x-frame-options"] == "DENY"
    assert "referrer-policy" in r.headers
