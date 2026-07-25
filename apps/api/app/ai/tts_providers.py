"""Text-to-speech provider abstraction for VIDEO_ASSET narration — same
Protocol + Mock + real-gated-behind-flag pattern as every other external
integration in this codebase. ``MockTTSProvider`` is deterministic and
offline (synthesizes real silence with the bundled ffmpeg binary, no
network) so tests exercise real audio bytes without ever calling OpenAI.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from typing import Protocol

import httpx
from imageio_ffmpeg import get_ffmpeg_exe

from app.core.config import settings

_MOCK_TIMEOUT = "__mock_timeout__"
_MOCK_PROVIDER_ERROR = "__mock_provider_error__"


class TTSProviderError(Exception):
    pass


class TTSProviderTimeout(TTSProviderError):
    pass


@dataclass(frozen=True)
class TTSRequest:
    text: str
    timeout_seconds: int


@dataclass(frozen=True)
class TTSResult:
    content: bytes
    mime_type: str


class TTSProviderClient(Protocol):
    async def synthesize(self, request: TTSRequest) -> TTSResult: ...


def _estimate_seconds(text: str) -> float:
    # ~2.5 spoken words/second, clamped to a sane range for a short-form
    # video narration (never silent, never a multi-minute clip by accident).
    words = max(len(text.split()), 1)
    return max(3.0, min(60.0, words / 2.5))


class MockTTSProvider:
    """Deterministic, offline provider — synthesizes real silence of a
    text-proportional duration with the bundled ffmpeg binary, so downstream
    duration/assembly logic in tests runs against real audio bytes."""

    async def synthesize(self, request: TTSRequest) -> TTSResult:
        if _MOCK_TIMEOUT in request.text:
            raise TTSProviderTimeout("mock tts provider: simulated timeout")
        if _MOCK_PROVIDER_ERROR in request.text:
            raise TTSProviderError("mock tts provider: simulated upstream error")

        duration = _estimate_seconds(request.text)
        proc = subprocess.run(
            [
                get_ffmpeg_exe(),
                "-f", "lavfi",
                "-i", "anullsrc=r=24000:cl=mono",
                "-t", str(duration),
                "-q:a", "9",
                "-acodec", "libmp3lame",
                "-f", "mp3",
                "pipe:1",
            ],
            capture_output=True,
            timeout=request.timeout_seconds,
        )
        if proc.returncode != 0:
            raise TTSProviderError(f"mock tts synthesis failed: {proc.stderr[-500:]!r}")
        return TTSResult(content=proc.stdout, mime_type="audio/mpeg")


class OpenAITTSProvider:
    """Real OpenAI text-to-speech client. Never used in automated tests."""

    def __init__(self, api_key: str, model: str, voice: str) -> None:
        self._api_key = api_key
        self._model = model
        self._voice = voice

    async def synthesize(self, request: TTSRequest) -> TTSResult:
        if not self._api_key:
            raise TTSProviderError("OPENAI_API_KEY is not configured")
        try:
            async with httpx.AsyncClient(timeout=request.timeout_seconds) as client:
                resp = await client.post(
                    "https://api.openai.com/v1/audio/speech",
                    headers={
                        "Authorization": f"Bearer {self._api_key}",
                        "content-type": "application/json",
                    },
                    json={
                        "model": self._model,
                        "voice": self._voice,
                        "input": request.text,
                        "response_format": "mp3",
                    },
                )
        except httpx.TimeoutException as exc:
            raise TTSProviderTimeout("openai tts request timed out") from exc
        except httpx.HTTPError as exc:
            raise TTSProviderError("openai tts request failed") from exc

        if resp.status_code >= 400:
            raise TTSProviderError(f"openai tts error (status {resp.status_code})")
        return TTSResult(content=resp.content, mime_type="audio/mpeg")


def get_tts_provider(name: str) -> TTSProviderClient:
    if name == "OPENAI":
        return OpenAITTSProvider(
            settings.openai_api_key, settings.openai_tts_model, settings.openai_tts_voice
        )
    return MockTTSProvider()
