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
    # Publicly-reachable URL for the asset (a short-lived signed URL from
    # the storage provider) — required by real providers whose upload API
    # takes a URL rather than binary bytes (Meta's Graph API is one of
    # these). MOCK/MANUAL never look at this field.
    asset_public_url: str | None = None
    # Publicly-reachable URL for the publication's AssetVariant thumbnail
    # (e.g. the AI-generated cover for a manually-uploaded reel), if one is
    # attached. Only meaningful for video publications — see
    # MetaPublishingProvider._publish_facebook.
    thumbnail_public_url: str | None = None


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


def _compose_meta_text(publication: PublicationPayload) -> str:
    """Title + caption + hashtags, in the order a human would write them.
    Both _publish_facebook and _publish_instagram send a single text field
    to Meta (no separate hashtags field exists in either endpoint) — before
    this, hashtags were carried on PublicationPayload.hashtags and stored
    on the Publication row, but neither adapter method ever actually read
    that field, so every real Meta post silently went out with none."""
    body = (publication.title or "").strip()
    if (publication.caption or "").strip():
        body = f"{body}\n\n{publication.caption}" if body else (publication.caption or "")
    if publication.hashtags:
        tags = " ".join(
            tag if tag.startswith("#") else f"#{tag}" for tag in publication.hashtags if tag.strip()
        )
        if tags:
            body = f"{body}\n\n{tags}" if body else tags
    return body


class MetaPublishingProvider:
    """Real Meta (Facebook Pages / Instagram professional accounts) Graph
    API publishing — Phase 6A.

    Two independent gates must BOTH be true before this class ever makes a
    network call:
      1. a page/IG access token is configured (``access_token`` param or
         ``settings.meta_access_token`` — a long-lived PAGE token obtained
         via the app.oauth.meta flow, not the app id/secret);
      2. ``settings.meta_publishing_enabled`` is explicitly ``true``.
    Without both, every method raises ``PublishPermanentError`` with a
    specific reason instead of silently no-opping or attempting a call —
    this is what makes it safe to wire this class into the live adapter
    registry in Phase 6A without any risk of it firing for real until
    Phase 6B deliberately flips both switches.

    Facebook posts a photo via ``/{page_id}/photos`` (or a text post via
    ``/{page_id}/feed`` when no asset is attached). Instagram uses the
    two-step container flow: create a media container
    (``/{ig_user_id}/media``), then publish it
    (``/{ig_user_id}/media_publish``). Both need a publicly reachable
    asset URL — see ``PublicationPayload.asset_public_url``.

    ``PublicationType.STORY`` is a real exception to both of the above —
    see ``_publish_facebook_story`` and the ``media_type=STORIES`` branch
    in ``_publish_instagram``. Posting a Story through the normal
    photo/feed/media endpoints still "works" (Meta accepts it as an
    ordinary feed post) but it's silently the wrong thing: it never shows
    up as a Story to followers, and it never counts toward Meta's own
    "Crear N historias nuevas" weekly Page-goal widget in the
    professional dashboard — the whole reason Historias exists as its
    own PublicationType instead of just being another POST.
    """

    GRAPH_HOST = "https://graph.facebook.com"
    # Common Graph API error codes: 4/17/32/613 are various rate-limit
    # flavors; 1/2 are transient/server-side — both retryable. Anything
    # else (permissions, validation, revoked token) is permanent.
    _RATE_LIMIT_CODES = {4, 17, 32, 613}
    _RECOVERABLE_CODES = {1, 2}

    def __init__(
        self,
        access_token: str = "",
        *,
        http_client: object | None = None,
        api_version: str = "",
    ) -> None:
        self._access_token = access_token or settings.meta_access_token
        self._api_version = api_version or settings.meta_graph_api_version
        self._injected_client = http_client

    @property
    def _ready(self) -> bool:
        return bool(self._access_token) and settings.meta_publishing_enabled

    def _client(self):
        import httpx

        return self._injected_client or httpx.AsyncClient(timeout=30.0)

    async def validate(self, publication: PublicationPayload) -> ValidationResult:
        if not self._ready:
            return ValidationResult(
                ok=False, errors=["META adapter is not active in this deployment"]
            )
        errors: list[str] = []
        if not publication.connection_external_account_id:
            errors.append(
                "missing target Facebook Page / Instagram account id — for Facebook use the Facebook Page id (credentials.page_id), for Instagram use the Instagram account id"
            )
        if publication.platform == "INSTAGRAM" and not publication.asset_public_url:
            errors.append(
                "Instagram publishing requires a publicly reachable asset URL (use a signed storage URL)"
            )
        # Accept either a caption or a title (title will be prefixed to the
        # caption in the payload). Previously we required caption only,
        # which rejected drafts that only provided a title.
        if not (publication.caption or "").strip() and not (publication.title or "").strip():
            errors.append("caption or title is required — provide at least one")
        return ValidationResult(ok=not errors, errors=errors)

    async def publish(
        self, publication: PublicationPayload, idempotency_key: str
    ) -> PublishResult:
        if not self._ready:
            raise PublishPermanentError(
                "META publishing requires both a configured access token and "
                "META_PUBLISHING_ENABLED=true"
            )
        import httpx as httpx_lib

        try:
            if publication.platform == "INSTAGRAM":
                return await self._publish_instagram(publication)
            return await self._publish_facebook(publication)
        except httpx_lib.HTTPError as exc:
            raise PublishRecoverableError(f"network error calling Graph API: {exc}") from exc

    _VIDEO_PUBLICATION_TYPES = {"REEL", "VIDEO"}

    async def _publish_facebook(self, publication: PublicationPayload) -> PublishResult:
        if publication.publication_type == "STORY":
            return await self._publish_facebook_story(publication)
        page_id = publication.connection_external_account_id
        async with self._client() as client:
            # Defensive preflight: ensure the provided page_id is reachable
            # with the current access token. This surfaces a clearer error
            # when callers accidentally pass an Instagram account id where a
            # Facebook Page id is required.
            try:
                resp_check = await client.get(
                    f"{self.GRAPH_HOST}/{self._api_version}/{page_id}",
                    params={"fields": "id", "access_token": self._access_token},
                )
                # _parse will raise a PublishPermanentError on permission/invalid id
                self._parse(resp_check)
            except PublishPermanentError as exc:
                raise PublishPermanentError(
                    f"target id {page_id} is not a valid Facebook Page for this token: {exc}"
                ) from exc
            # Build the textual body for the post: title + caption +
            # hashtags. Include the title as a prefix when present so
            # titles are surfaced in the external post (Facebook/Instagram
            # don't have a separate "title" field for typical photo/post
            # endpoints), and hashtags appended at the end since neither
            # endpoint has a dedicated hashtags field either.
            text_body = _compose_meta_text(publication)

            if publication.asset_public_url and publication.publication_type in self._VIDEO_PUBLICATION_TYPES:
                # Video files must go through /videos (not /photos, which
                # only accepts images and would reject video content).
                url = f"{self.GRAPH_HOST}/{self._api_version}/{page_id}/videos"
                params = {
                    "file_url": publication.asset_public_url,
                    "description": text_body,
                    "access_token": self._access_token,
                }
                if publication.thumbnail_public_url:
                    params["thumb"] = publication.thumbnail_public_url
            elif publication.asset_public_url:
                url = f"{self.GRAPH_HOST}/{self._api_version}/{page_id}/photos"
                params = {
                    "url": publication.asset_public_url,
                    "caption": text_body,
                    "access_token": self._access_token,
                }
            else:
                url = f"{self.GRAPH_HOST}/{self._api_version}/{page_id}/feed"
                params = {"message": text_body, "access_token": self._access_token}
            resp = await client.post(url, params=params)
        data = self._parse(resp)
        post_id = data.get("post_id") or data.get("id")
        return PublishResult(
            external_publication_id=post_id,
            external_url=f"https://www.facebook.com/{post_id}",
            raw_status="published",
        )

    async def _publish_facebook_story(self, publication: PublicationPayload) -> PublishResult:
        """Facebook Page Stories use dedicated endpoints
        (``/{page_id}/photo_stories``), never ``/photos`` or ``/feed`` — a
        publication tagged PublicationType.STORY that went out through the
        regular photo/feed endpoints (the bug this method fixes) becomes an
        ordinary feed post, which is why it never counted toward Meta's own
        "Crear N historias nuevas" weekly Page goal even though our system
        correctly labeled it internally. Two-step flow per Meta's docs:
        upload the photo unpublished, then attach it to a Story via its id.
        Stories don't render a caption/text overlay from the API — the
        title/caption is already baked into the image itself, same as
        every other headline/story flyer a human uploads in this app."""
        page_id = publication.connection_external_account_id
        if not publication.asset_public_url:
            raise PublishPermanentError("Facebook Stories require an image")
        async with self._client() as client:
            upload_resp = await client.post(
                f"{self.GRAPH_HOST}/{self._api_version}/{page_id}/photos",
                params={
                    "url": publication.asset_public_url,
                    "published": "false",
                    "access_token": self._access_token,
                },
            )
            uploaded = self._parse(upload_resp)
            photo_id = uploaded["id"]

            story_resp = await client.post(
                f"{self.GRAPH_HOST}/{self._api_version}/{page_id}/photo_stories",
                params={"photo_id": photo_id, "access_token": self._access_token},
            )
            published = self._parse(story_resp)
        post_id = published.get("post_id") or published.get("id")
        return PublishResult(
            # Facebook Stories don't return a stable public permalink from
            # this endpoint (they're ephemeral, same reason Instagram
            # Stories below also leave external_url unset).
            external_publication_id=post_id,
            external_url=None,
            raw_status="published",
        )

    async def _publish_instagram(self, publication: PublicationPayload) -> PublishResult:
        ig_user_id = publication.connection_external_account_id
        is_story = publication.publication_type == "STORY"
        media_field = (
            "video_url" if publication.publication_type in ("REEL", "VIDEO") else "image_url"
        )
        async with self._client() as client:
            create_params = {
                media_field: publication.asset_public_url,
                "access_token": self._access_token,
            }
            if is_story:
                # media_type=STORIES is what makes this a real, ephemeral
                # Instagram Story instead of a normal feed post — the fix
                # for it never counting toward Meta's own "Crear N
                # historias nuevas" weekly Page goal. Stories don't render
                # a caption from the API (Meta rejects/ignores it), so it's
                # deliberately omitted here — the title/caption is already
                # baked into the image a human uploaded.
                create_params["media_type"] = "STORIES"
            else:
                # Instagram also uses a single caption field for title +
                # caption + hashtags — see _compose_meta_text.
                create_params["caption"] = _compose_meta_text(publication)
                if publication.publication_type == "REEL":
                    create_params["media_type"] = "REELS"
            create_resp = await client.post(
                f"{self.GRAPH_HOST}/{self._api_version}/{ig_user_id}/media", params=create_params
            )
            created = self._parse(create_resp)
            creation_id = created["id"]

            publish_resp = await client.post(
                f"{self.GRAPH_HOST}/{self._api_version}/{ig_user_id}/media_publish",
                params={"creation_id": creation_id, "access_token": self._access_token},
            )
            published = self._parse(publish_resp)
        media_id = published["id"]
        return PublishResult(
            external_publication_id=media_id,
            # The Graph API doesn't return a permalink from media_publish
            # directly; a follow-up GET .../{media_id}?fields=permalink
            # would be needed for a real URL — left for Phase 6B.
            external_url=None,
            raw_status="published",
        )

    async def get_status(self, external_publication_id: str) -> PublishStatusResult:
        if not self._ready:
            raise PublishPermanentError("META adapter is not active in this deployment")
        async with self._client() as client:
            resp = await client.get(
                f"{self.GRAPH_HOST}/{self._api_version}/{external_publication_id}",
                params={"fields": "id", "access_token": self._access_token},
            )
        data = self._parse(resp)
        return PublishStatusResult(
            external_publication_id=data.get("id", external_publication_id), status="published"
        )

    def _parse(self, resp) -> dict:
        try:
            data = resp.json()
        except Exception as exc:
            raise PublishRecoverableError(
                f"non-JSON Graph API response ({resp.status_code})"
            ) from exc
        error = data.get("error")
        if error:
            code = error.get("code")
            message = str(error.get("message", error))[:300]
            if code in self._RATE_LIMIT_CODES:
                raise PublishRateLimited(retry_after_seconds=60)
            if code in self._RECOVERABLE_CODES:
                raise PublishRecoverableError(message)
            raise PublishPermanentError(message)
        return data


def get_publishing_provider(
    provider_name: str, *, access_token: str = ""
) -> PublishingProviderClient:
    """``access_token`` is the per-connection decrypted credential (see
    app.publishing.crypto) — each org's Meta connection carries its own
    token, so the caller must decrypt PublishingConnection.credentials_encrypted
    and pass it here rather than relying on a single process-wide token.
    Falls back to settings.meta_access_token only when no per-connection
    token is available (e.g. a connection created before one was set)."""
    if provider_name == "MANUAL":
        return ManualPublishingProvider()
    if provider_name == "META":
        return MetaPublishingProvider(access_token)
    return MockPublishingProvider()


def idempotency_key_for(*, organization_id: str, publication_id: str, attempt: int) -> str:
    """Stable idempotency key: same publication + same logical attempt series
    (retries reuse this, not a fresh random value, so the provider can
    de-duplicate a network-level retry)."""
    raw = f"{organization_id}:{publication_id}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]
