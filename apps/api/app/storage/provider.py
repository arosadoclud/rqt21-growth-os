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

import asyncio
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


class S3StorageProvider:
    """Real S3-compatible provider (Phase 6A) — works against AWS S3 or
    Cloudflare R2 (R2 is S3-API-compatible; point ``endpoint_url`` at the
    account's R2 endpoint and this class needs no changes). Bytes never
    touch this process's disk; boto3 streams straight to the bucket.

    Blocking boto3 calls run in a thread via ``asyncio.to_thread`` so they
    don't block whichever event loop ``asyncio.run()`` spun up for the
    caller (see app.api.v1.assets, which always calls this from a sync
    endpoint via ``asyncio.run(...)``).
    """

    def __init__(
        self,
        *,
        bucket: str,
        region: str = "",
        endpoint_url: str = "",
        access_key: str = "",
        secret_key: str = "",
    ) -> None:
        import boto3

        if not bucket:
            raise ValueError("STORAGE_BUCKET is required for the S3/R2 provider")
        self._bucket = bucket
        self._client = boto3.client(
            "s3",
            region_name=region or None,
            endpoint_url=endpoint_url or None,
            aws_access_key_id=access_key or None,
            aws_secret_access_key=secret_key or None,
        )

    async def upload(
        self, *, storage_key: str, content: bytes, mime_type: str
    ) -> StoredAsset:
        checksum = _sha256(content)
        await asyncio.to_thread(
            self._client.put_object,
            Bucket=self._bucket,
            Key=storage_key,
            Body=content,
            ContentType=mime_type,
            Metadata={"sha256": checksum},
        )
        return StoredAsset(
            storage_key=storage_key, size_bytes=len(content), checksum_sha256=checksum
        )

    async def create_signed_url(self, *, storage_key: str, ttl_seconds: int) -> str:
        return await asyncio.to_thread(
            self._client.generate_presigned_url,
            "get_object",
            Params={"Bucket": self._bucket, "Key": storage_key},
            ExpiresIn=ttl_seconds,
        )

    async def delete(self, *, storage_key: str) -> None:
        await asyncio.to_thread(
            self._client.delete_object, Bucket=self._bucket, Key=storage_key
        )


def make_storage_key(organization_id: uuid.UUID, safe_filename: str) -> str:
    return f"{organization_id}/{uuid.uuid4().hex}-{safe_filename}"


def get_storage_provider() -> StorageProviderClient:
    name = settings.storage_provider.upper()
    if name == "LOCAL":
        return LocalStorageProvider()
    if name in ("S3", "R2"):
        return S3StorageProvider(
            bucket=settings.storage_bucket,
            region=settings.storage_region,
            endpoint_url=settings.storage_endpoint,
            access_key=settings.storage_access_key,
            secret_key=settings.storage_secret_key,
        )
    # MOCK is also the safe fallback for any unrecognized value so a
    # misconfigured env var never silently no-ops writes to a real bucket.
    return MockStorageProvider()
