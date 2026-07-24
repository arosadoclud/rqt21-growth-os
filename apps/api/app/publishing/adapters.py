"""Publishing provider adapters.

``PublishingProviderClient`` is the seam between a Publication and whatever
actually posts it externally. Only ``MockPublishingProvider`` and
``ManualPublishingProvider`` are fully live in this MVP — real social
publishing is out of scope (see Phase 5 spec section 27).
``MetaPublishingProvider`` exists as an isolated skeleton: it validates its
own credential contract and raises a clear "not active" error rather than
attempting any real network call unless explicit env vars are present AND
the caller opts in — neither of which this codebase currently does.

Sentinel captions let tests exercise every MOCK failure mode deterministically:
    __mock_rate_limit__      -> PublishRateLimited (Retry-After honored)
    __mock_timeout__         -> PublishTimeout
    __mock_recoverable__     -> PublishRecoverableError
    __mock_permanent__       -> PublishPermanentError
    __mock_duplicate__       -> PublishDuplicate
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Protocol

from app.core.config import settings


class PublishError(Exception):
    pass


class PublishRateLimited(PublishError):
    def __init__(self, retry_after_seconds: int = 30) -> None:
        self.retry_after_seconds = retry_after_seconds
        super().__init__("rate limited")


class PublishTimeout(PublishError):
    pass


class PublishRecoverableError(PublishError):
    pass


class PublishPermanentError(PublishError):
    pass


class PublishDuplicate(PublishError):
    def __init__(self, existing_external_id: str) -> None:
        self.existing_external_id = existing_external_id
        super().__init__("duplicate publication")


@dataclass(frozen=True)
class PublicationPayload:
    publication_id: str
    platform: str
    publication_type: str
    caption: str
    title: str | None
    cta: str | None
    hashtags: list[str] = field(default_factory=list)
    asset_storage_key: str | None = None
    connection_external_account_id: str | None = None


@dataclass(frozen=True)
class ValidationResult:
    ok: bool
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class PublishResult:
    external_publication_id: str
    external_url: str | None
    raw_status: str


@dataclass(frozen=True)
class PublishStatusResult:
    external_publication_id: str
    status: str


class PublishingProviderClient(Protocol):
    async def validate(self, publication: PublicationPayload) -> ValidationResult: ...

    async def publish(
        self, publication: PublicationPayload, idempotency_key: str
    ) -> PublishResult: ...

    async def get_status(self, external_publication_id: str) -> PublishStatusResult: ...


_SENTINELS = {
    "__mock_rate_limit__": PublishRateLimited,
    "__mock_timeout__": PublishTimeout,
    "__mock_recoverable__": PublishRecoverableError,
    "__mock_permanent__": PublishPermanentError,
}


class MockPublishingProvider:
    """Deterministic, offline. Used by tests, dev, and the seed script."""

    async def validate(self, publication: PublicationPayload) -> ValidationResult:
        errors = []
        if not publication.caption.strip():
            errors.append("caption is required")
        return ValidationResult(ok=not errors, errors=errors)

    async def publish(
        self, publication: PublicationPayload, idempotency_key: str
    ) -> PublishResult:
        for marker, exc_cls in _SENTINELS.items():
            if marker in publication.caption:
                if exc_cls is PublishRateLimited:
                    raise PublishRateLimited(retry_after_seconds=5)
                raise exc_cls(marker)
        if "__mock_duplicate__" in publication.caption:
            stable_id = hashlib.sha256(idempotency_key.encode()).hexdigest()[:16]
            raise PublishDuplicate(existing_external_id=f"mock-{stable_id}")

        # External id is a stable function of the idempotency key, so
        # replaying the same publish() call (e.g. a retried request with the
        # same idempotency_key) yields the same external id.
        stable_id = hashlib.sha256(idempotency_key.encode()).hexdigest()[:16]
        return PublishResult(
            external_publication_id=f"mock-{stable_id}",
            external_url=f"https://mock.local/p/{stable_id}",
            raw_status="published",
        )

    async def get_status(self, external_publication_id: str) -> PublishStatusResult:
        return PublishStatusResult(
            external_publication_id=external_publication_id, status="published"
        )


class ManualPublishingProvider:
    """Not an auto-publisher — it exists so the Publication state machine has
    a uniform adapter to call even when the human is doing the actual work
    outside the system. ``publish()`` never claims success on its own; the
    caller (mark-published endpoint) is what records the human-provided URL
    and timestamp. Calling publish() here always raises, by design — manual
    publications go through app.api.v1.publications.mark_published instead
    of the adapter's publish() path."""

    async def validate(self, publication: PublicationPayload) -> ValidationResult:
        errors = []
        if not publication.caption.strip():
            errors.append("caption is required")
        return ValidationResult(ok=not errors, errors=errors, warnings=["manual publication — no automatic posting"])

    async def publish(
        self, publication: PublicationPayload, idempotency_key: str
    ) -> PublishResult:
        raise PublishPermanentError(
            "MANUAL connections are never auto-published; use mark-published instead"
        )

    async def get_status(self, external_publication_id: str) -> PublishStatusResult:
        return PublishStatusResult(
            external_publication_id=external_publication_id, status="unknown"
        )


class MetaPublishingProvider:
    """Skeleton for Meta (Instagram/Facebook) Graph API publishing.

    Functionally isolated: constructing this class does not make any network
    call. ``publish()`` refuses to run unless BOTH a Meta access token is
    configured AND the org's connection has been explicitly verified —
    neither happens anywhere in this codebase yet, so this path is dead code
    until a real integration is deliberately wired in.
    """

    def __init__(self, access_token: str = "") -> None:
        self._access_token = access_token or settings.meta_access_token

    async def validate(self, publication: PublicationPayload) -> ValidationResult:
        return ValidationResult(
            ok=False, errors=["META adapter is not active in this deployment"]
        )

    async def publish(
        self, publication: PublicationPayload, idempotency_key: str
    ) -> PublishResult:
        if not self._access_token:
            raise PublishPermanentError(
                "META publishing is not configured (missing access token)"
            )
        raise PublishPermanentError("META publishing is not enabled in this deployment")

    async def get_status(self, external_publication_id: str) -> PublishStatusResult:
        raise PublishPermanentError("META adapter is not active in this deployment")


def get_publishing_provider(provider_name: str) -> PublishingProviderClient:
    if provider_name == "MANUAL":
        return ManualPublishingProvider()
    if provider_name == "META":
        return MetaPublishingProvider()
    return MockPublishingProvider()


def idempotency_key_for(*, organization_id: str, publication_id: str, attempt: int) -> str:
    """Stable idempotency key: same publication + same logical attempt series
    (retries reuse this, not a fresh random value, so the provider can
    de-duplicate a network-level retry)."""
    raw = f"{organization_id}:{publication_id}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]
