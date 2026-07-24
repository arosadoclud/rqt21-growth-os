from __future__ import annotations

import base64
import uuid as _u
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.models.membership import Role
from app.models.publishing import Publication, PublicationAttempt
from app.workers.publish_due import run_once

_PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 200


def _ready_scheduled_publication(client, *, caption="Publicación automática de prueba.", when=None):
    slug = f"brand-{_u.uuid4().hex[:6]}"
    brand_id = client.post("/api/v1/brands", json={"name": slug, "slug": slug}).json()["id"]
    cid = client.post(
        "/api/v1/content-items", json={"brand_id": brand_id, "title": "Worker content"}
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
            "caption": caption,
        },
    ).json()["id"]
    client.post(f"/api/v1/publications/{pub_id}/validate")
    when = when or (datetime.now(UTC) + timedelta(seconds=1))
    client.post(
        f"/api/v1/publications/{pub_id}/schedule",
        json={"scheduled_for": when.isoformat()},
    )
    return pub_id


def _force_due(db, pub_id: str) -> None:
    """Test-only: bypass the future-date guard on /schedule by moving
    scheduled_for into the past directly, simulating time having passed."""
    row = db.get(Publication, _u.UUID(pub_id))
    row.scheduled_for = datetime.now(UTC) - timedelta(seconds=1)
    db.commit()


def test_worker_publishes_due_scheduled_publication(bootstrap, db):
    client, _, _ = bootstrap(Role.OWNER, "worker-due@example.com")
    pub_id = _ready_scheduled_publication(client)
    _force_due(db, pub_id)

    counts = run_once()
    assert counts["scheduled_processed"] == 1

    db.expire_all()
    row = db.get(Publication, _u.UUID(pub_id))
    assert row.status.value == "PUBLISHED"

    attempts = db.execute(
        select(PublicationAttempt).where(PublicationAttempt.publication_id == row.id)
    ).scalars().all()
    assert len(attempts) == 1
    assert attempts[0].status.value == "SUCCEEDED"


def test_worker_skips_not_yet_due(bootstrap, db):
    client, _, _ = bootstrap(Role.OWNER, "worker-notdue@example.com")
    pub_id = _ready_scheduled_publication(
        client, when=datetime.now(UTC) + timedelta(days=1)
    )
    counts = run_once()
    assert counts["scheduled_processed"] == 0

    row = db.get(Publication, _u.UUID(pub_id))
    assert row.status.value == "SCHEDULED"


def test_worker_double_run_does_not_double_process(bootstrap, db):
    """The atomic claim (UPDATE ... WHERE status=X) must prevent a second
    pass over the same already-processed publication from creating a second
    attempt."""
    client, _, _ = bootstrap(Role.OWNER, "worker-noclaim@example.com")
    pub_id = _ready_scheduled_publication(client)
    _force_due(db, pub_id)

    run_once()
    run_once()  # second pass: publication is no longer SCHEDULED, must be skipped

    db.expire_all()
    attempts = db.execute(
        select(PublicationAttempt).where(PublicationAttempt.publication_id == _u.UUID(pub_id))
    ).scalars().all()
    assert len(attempts) == 1


def test_worker_processes_retry_scheduled(bootstrap, db):
    client, _, _ = bootstrap(Role.OWNER, "worker-retry@example.com")
    pub_id = _ready_scheduled_publication(
        client, caption="Fallo temporal __mock_recoverable__ de prueba"
    )
    _force_due(db, pub_id)
    run_once()

    db.expire_all()
    row = db.get(Publication, _u.UUID(pub_id))
    assert row.status.value == "RETRY_SCHEDULED"

    row.next_retry_at = datetime.now(UTC) - timedelta(seconds=1)
    db.commit()

    counts = run_once()
    assert counts["retries_processed"] == 1

    db.expire_all()
    row = db.get(Publication, _u.UUID(pub_id))
    assert row.attempt_count == 2


def test_worker_fails_when_connection_not_active(bootstrap, db):
    client, _, _ = bootstrap(Role.OWNER, "worker-revoked@example.com")
    pub_id = _ready_scheduled_publication(client)
    row = db.get(Publication, _u.UUID(pub_id))
    from app.models.publishing import PublishingConnection

    conn = db.get(PublishingConnection, row.publishing_connection_id)
    conn.status = "REVOKED"
    db.commit()
    _force_due(db, pub_id)

    run_once()

    db.expire_all()
    row = db.get(Publication, _u.UUID(pub_id))
    assert row.status.value == "FAILED"
    assert row.failure_code == "connection_revoked"
