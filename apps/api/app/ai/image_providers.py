"""Image generation provider abstraction — mirrors app.ai.providers but for
GenerationType.IMAGE_ASSET jobs, which produce image bytes instead of JSON
text. ``MockImageProvider`` is deterministic and offline, used by tests and
local dev. ``OpenAIImageProvider`` is a real client (OpenAI's current
image model, gpt-image-1) selected via get_image_provider, never exercised
by the automated test suite — same convention as the text providers.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass
from typing import Protocol

import httpx

from app.core.config import settings

_MOCK_TIMEOUT = "__mock_timeout__"
_MOCK_RATE_LIMIT = "__mock_rate_limit__"
_MOCK_PROVIDER_ERROR = "__mock_provider_error__"

# A 1x1 transparent PNG, valid image bytes so downstream storage/checksum
# code exercises real logic in tests without any real network call.
_MOCK_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)


class ImageProviderError(Exception):
    pass


class ImageProviderTimeout(ImageProviderError):
    pass


class ImageProviderRateLimited(ImageProviderError):
    pass


@dataclass(frozen=True)
class ImageGenerationRequest:
    prompt: str
    size: str
    timeout_seconds: int


@dataclass(frozen=True)
class ImageGenerationResult:
    content: bytes
    mime_type: str


class ImageProviderClient(Protocol):
    async def generate(self, request: ImageGenerationRequest) -> ImageGenerationResult: ...


class MockImageProvider:
    """Deterministic, offline provider for tests and local dev."""

    async def generate(self, request: ImageGenerationRequest) -> ImageGenerationResult:
        if _MOCK_TIMEOUT in request.prompt:
            raise ImageProviderTimeout("mock image provider: simulated timeout")
        if _MOCK_RATE_LIMIT in request.prompt:
            raise ImageProviderRateLimited("mock image provider: simulated rate limit")
        if _MOCK_PROVIDER_ERROR in request.prompt:
            raise ImageProviderError("mock image provider: simulated upstream error")
        return ImageGenerationResult(content=_MOCK_PNG, mime_type="image/png")


class OpenAIImageProvider:
    """Real OpenAI Images API client (gpt-image-1). Never used in automated
    tests. Requests base64-encoded output directly — no image_url to fetch
    separately, no risk of that URL expiring before we can download it."""

    def __init__(self, api_key: str, model: str) -> None:
        self._api_key = api_key
        self._model = model

    async def generate(self, request: ImageGenerationRequest) -> ImageGenerationResult:
        if not self._api_key:
            raise ImageProviderError("OPENAI_API_KEY is not configured")
        try:
            async with httpx.AsyncClient(timeout=request.timeout_seconds) as client:
                resp = await client.post(
                    "https://api.openai.com/v1/images/generations",
                    headers={
                        "Authorization": f"Bearer {self._api_key}",
                        "content-type": "application/json",
                    },
                    json={
                        "model": self._model,
                        "prompt": request.prompt,
                        "size": request.size,
                        "n": 1,
                    },
                )
        except httpx.TimeoutException as exc:
            raise ImageProviderTimeout("openai image request timed out") from exc
        except httpx.HTTPError as exc:
            raise ImageProviderError("openai image request failed") from exc

        if resp.status_code == 429:
            raise ImageProviderRateLimited("openai image rate limit exceeded")
        if resp.status_code >= 400:
            raise ImageProviderError(f"openai image error (status {resp.status_code})")

        data = resp.json()
        items = data.get("data") or []
        if not items or not items[0].get("b64_json"):
            raise ImageProviderError("openai image response missing b64_json")
        content = base64.b64decode(items[0]["b64_json"])
        return ImageGenerationResult(content=content, mime_type="image/png")


def get_image_provider(name: str) -> ImageProviderClient:
    if name == "OPENAI":
        return OpenAIImageProvider(settings.openai_api_key, settings.openai_image_model)
    return MockImageProvider()
