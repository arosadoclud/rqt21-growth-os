"""Free fallback providers for VIDEO_ASSET generation — Pollinations.ai
(images) and ElevenLabs (narration) — used when the paid primary provider
(OpenAI) hits a rate limit or quota error. Network calls are stubbed with
httpx.MockTransport, same convention as test_meta_token_resolver.py; no
real Pollinations/ElevenLabs/OpenAI call is ever made in tests.
"""

from __future__ import annotations

import asyncio

import httpx
import pytest

from app.ai.image_providers import (
    FallbackImageProvider,
    ImageGenerationRequest,
    ImageGenerationResult,
    ImageProviderError,
    ImageProviderRateLimited,
    PollinationsImageProvider,
)
from app.ai.tts_providers import (
    ElevenLabsTTSProvider,
    FallbackTTSProvider,
    TTSProviderError,
    TTSProviderTimeout,
    TTSRequest,
    TTSResult,
)


class _AlwaysFailsImageProvider:
    def __init__(self, exc: Exception) -> None:
        self._exc = exc

    async def generate(self, request: ImageGenerationRequest):
        raise self._exc


class _AlwaysFailsTTSProvider:
    def __init__(self, exc: Exception) -> None:
        self._exc = exc

    async def synthesize(self, request: TTSRequest):
        raise self._exc


_RealAsyncClient = httpx.AsyncClient


def _patched_client(handler) -> httpx.AsyncClient:
    return _RealAsyncClient(transport=httpx.MockTransport(handler))


def test_pollinations_image_provider_success(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        assert "prompt/" in request.url.path
        return httpx.Response(200, content=b"\xff\xd8\xff-fake-jpeg-bytes")

    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: _patched_client(handler))
    provider = PollinationsImageProvider()

    async def run():
        return await provider.generate(
            ImageGenerationRequest(prompt="a keto salad", size="1024x1536", timeout_seconds=10)
        )

    result = asyncio.run(run())
    assert result.content == b"\xff\xd8\xff-fake-jpeg-bytes"
    assert result.mime_type == "image/jpeg"


def test_pollinations_image_provider_error_status(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, content=b"")

    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: _patched_client(handler))
    provider = PollinationsImageProvider()

    async def run():
        await provider.generate(
            ImageGenerationRequest(prompt="x", size="1024x1024", timeout_seconds=10)
        )

    with pytest.raises(ImageProviderError):
        asyncio.run(run())


def test_fallback_image_provider_uses_fallback_on_rate_limit():
    primary = _AlwaysFailsImageProvider(ImageProviderRateLimited("quota exhausted"))

    class _StubFallback:
        async def generate(self, request: ImageGenerationRequest):
            return ImageGenerationResult(content=b"fallback-bytes", mime_type="image/jpeg")

    provider = FallbackImageProvider(primary, _StubFallback())

    async def run():
        return await provider.generate(
            ImageGenerationRequest(prompt="x", size="1024x1024", timeout_seconds=10)
        )

    result = asyncio.run(run())
    assert result.content == b"fallback-bytes"


def test_elevenlabs_tts_provider_success(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        assert "/v1/text-to-speech/" in request.url.path
        assert request.headers["xi-api-key"] == "test-key"
        return httpx.Response(200, content=b"fake-mp3-bytes")

    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: _patched_client(handler))
    provider = ElevenLabsTTSProvider(api_key="test-key", voice_id="voice123")

    async def run():
        return await provider.synthesize(TTSRequest(text="hola mundo", timeout_seconds=10))

    result = asyncio.run(run())
    assert result.content == b"fake-mp3-bytes"
    assert result.mime_type == "audio/mpeg"


def test_elevenlabs_tts_provider_missing_key_raises():
    provider = ElevenLabsTTSProvider(api_key="", voice_id="voice123")

    async def run():
        await provider.synthesize(TTSRequest(text="hola", timeout_seconds=10))

    with pytest.raises(TTSProviderError):
        asyncio.run(run())


def test_fallback_tts_provider_uses_fallback_on_provider_error():
    primary = _AlwaysFailsTTSProvider(TTSProviderError("quota exhausted"))

    class _StubFallback:
        async def synthesize(self, request: TTSRequest):
            return TTSResult(content=b"fallback-audio", mime_type="audio/mpeg")

    provider = FallbackTTSProvider(primary, _StubFallback())

    async def run():
        return await provider.synthesize(TTSRequest(text="x", timeout_seconds=10))

    result = asyncio.run(run())
    assert result.content == b"fallback-audio"


def test_fallback_tts_provider_does_not_retry_on_timeout():
    primary = _AlwaysFailsTTSProvider(TTSProviderTimeout("timed out"))

    class _StubFallback:
        async def synthesize(self, request: TTSRequest):
            raise AssertionError("fallback should not be called on timeout")

    provider = FallbackTTSProvider(primary, _StubFallback())

    async def run():
        return await provider.synthesize(TTSRequest(text="x", timeout_seconds=10))

    with pytest.raises(TTSProviderTimeout):
        asyncio.run(run())
