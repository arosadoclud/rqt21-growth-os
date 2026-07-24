from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.security import hash_refresh_token
from app.deps import REFRESH_COOKIE
from app.models.audit_log import AuditLog
from app.models.refresh_token import RefreshToken


def _rows(db):
    return db.execute(select(RefreshToken)).scalars().all()


def test_family_id_shared_across_rotations(client: TestClient, make_user, login, db):
    make_user("fam@example.com")
    login("fam@example.com")
    client.post("/api/v1/auth/refresh")
    client.post("/api/v1/auth/refresh")

    all_rows = _rows(db)
    assert len(all_rows) == 3
    families = {r.family_id for r in all_rows}
    assert len(families) == 1


def test_reuse_of_rotated_token_kills_family(
    client: TestClient, make_user, login, db
):
    make_user("reuse@example.com")
    login("reuse@example.com")
    stolen = client.cookies.get(REFRESH_COOKIE)
    assert stolen

    r = client.post("/api/v1/auth/refresh")
    assert r.status_code == 200

    # Attacker replays the stolen (already-rotated) token.
    client.cookies.delete(REFRESH_COOKIE)
    client.cookies.set(REFRESH_COOKIE, stolen)
    r_reuse = client.post("/api/v1/auth/refresh")
    assert r_reuse.status_code == 401
    assert r_reuse.json()["detail"] == "refresh token reuse detected"

    # The whole family should now be revoked with reason "reuse_detected"
    # (or "rotated" for the stolen token, whose reuse triggered it).
    rows = _rows(db)
    assert all(r.revoked_at is not None for r in rows)
    assert any(r.revoked_reason == "reuse_detected" for r in rows)

    # The reuse hit should have reuse_detected_at set.
    stolen_row = db.execute(
        select(RefreshToken).where(RefreshToken.token_hash == hash_refresh_token(stolen))
    ).scalar_one()
    assert stolen_row.reuse_detected_at is not None

    # Audit log recorded the incident.
    audits = db.execute(
        select(AuditLog).where(AuditLog.action == "auth.refresh_reuse_detected")
    ).scalars().all()
    assert len(audits) == 1

    # Even the newest (currently-valid at the time of reuse) refresh token
    # can no longer be used — the family is dead.
    # The client currently has the stolen refresh cookie forced in; grab the
    # newest live refresh from the DB and confirm it's dead too.
    from app.models.refresh_token import RefreshToken as RT
    newest = db.execute(
        select(RT).order_by(RT.created_at.desc()).limit(1)
    ).scalar_one()
    assert newest.revoked_at is not None


def test_logout_revokes_entire_family(client: TestClient, make_user, login, db):
    make_user("logfam@example.com")
    login("logfam@example.com")
    client.post("/api/v1/auth/refresh")
    r = client.post("/api/v1/auth/logout")
    assert r.status_code == 204

    rows = _rows(db)
    assert len(rows) == 2
    assert all(r.revoked_at is not None for r in rows)
