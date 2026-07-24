"""Storage provider abstraction for asset bytes.

Nothing above this layer ever sees a real bucket/credentials directly — every
call goes through ``StorageProviderClient``. Bytes are never stored in
Postgres; only ``storage_key`` (a path/identifier) is persisted on the Asset
row. Automated tests only ever use ``MockStorageProvider`` — no network, no
disk, fully deterministic.

``LocalStorageProvider`` is a real (but non-production) implementation that
writes to a local directory, useful for manual dev/demo without an S3/R2
account. It still never returns a "public" URL — ``create_signed_url``
returns a short-lived, HMAC-signed token consumed by our own
``GET /assets/{id}/download-url`` -> local file server, never a bare
filesystem path exposed to the client.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from app.core.config import settings


@dataclass(frozen=True)
class StoredAsset:
    storage_key: str
    size_bytes: int
    checksum_sha256: str


class StorageProviderClient(Protocol):
    async def upload(
        self, *, storage_key: str, content: bytes, mime_type: str
    ) -> StoredAsset: ...

    async def create_signed_url(self, *, storage_key: str, ttl_seconds: int) -> str: ...

    async def delete(self, *, storage_key: str) -> None: ...


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _sign(storage_key: str, expires_at: int) -> str:
    key = (settings.ip_hash_secret or settings.jwt_secret).encode("utf-8")
    msg = f"{storage_key}:{expires_at}".encode()
    return hmac.new(key, msg, hashlib.sha256).hexdigest()[:32]


def verify_signed_token(storage_key: str, expires_at: int, token: str) -> bool:
    if expires_at < int(time.time()):
        return False
    expected = _sign(storage_key, expires_at)
    return hmac.compare_digest(expected, token)


class MockStorageProvider:
    """No I/O whatsoever. Used by tests and CI."""

    async def upload(
        self, *, storage_key: str, content: bytes, mime_type: str
    ) -> StoredAsset:
        return StoredAsset(
            storage_key=storage_key,
            size_bytes=len(content),
            checksum_sha256=_sha256(content),
        )

    async def create_signed_url(self, *, storage_key: str, ttl_seconds: int) -> str:
        expires_at = int(time.time()) + ttl_seconds
        token = _sign(storage_key, expires_at)
        return f"mock://assets/{storage_key}?exp={expires_at}&sig={token}"

    async def delete(self, *, storage_key: str) -> None:
        return None


class LocalStorageProvider:
    """Writes to a local directory. Not for production use, but exercises
    real bytes-on-disk behavior for manual testing without cloud credentials."""

    def __init__(self, base_dir: str | Path = "./data/assets") -> None:
        self._base = Path(base_dir)
        self._base.mkdir(parents=True, exist_ok=True)

    def _path(self, storage_key: str) -> Path:
        # storage_key is always server-generated (uuid-based), never derived
        # from client input, so there is no path-traversal surface here.
        safe = storage_key.replace("..", "").lstrip("/\\")
        return self._base / safe

    async def upload(
        self, *, storage_key: str, content: bytes, mime_type: str
    ) -> StoredAsset:
        path = self._path(storage_key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return StoredAsset(
            storage_key=storage_key,
            size_bytes=len(content),
            checksum_sha256=_sha256(content),
        )

    async def create_signed_url(self, *, storage_key: str, ttl_seconds: int) -> str:
        expires_at = int(time.time()) + ttl_seconds
        token = _sign(storage_key, expires_at)
        return f"/api/v1/assets/_local-file/{storage_key}?exp={expires_at}&sig={token}"

    async def delete(self, *, storage_key: str) -> None:
        path = self._path(storage_key)
        if path.exists():
            os.remove(path)


def make_storage_key(organization_id: uuid.UUID, safe_filename: str) -> str:
    return f"{organization_id}/{uuid.uuid4().hex}-{safe_filename}"


def get_storage_provider() -> StorageProviderClient:
    name = settings.storage_provider.upper()
    if name == "LOCAL":
        return LocalStorageProvider()
    # S3/R2 are not implemented in this MVP (no cloud credentials required
    # yet) — MOCK is also the safe fallback for any unrecognized value so a
    # misconfigured env var never silently no-ops writes to a real bucket.
    return MockStorageProvider()
