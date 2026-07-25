"""Stock video footage provider — real people/food-prep clips for VIDEO_ASSET
scenes, sourced from a licensed stock library (Pexels: free, commercial use
permitted, no attribution required) instead of AI-generated stills. Same
Protocol + Mock + real-gated-behind-flag pattern as every other external
integration in this codebase.

Never scrapes or re-hosts third-party creator content (TikTok, Instagram,
etc.) — only a licensed stock API where redistribution/reuse is explicitly
part of the license.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from typing import Protocol

import httpx
from imageio_ffmpeg import get_ffmpeg_exe

_MOCK_TIMEOUT = "__mock_timeout__"
_MOCK_PROVIDER_ERROR = "__mock_provider_error__"


class StockVideoError(Exception):
    pass


class StockVideoTimeout(StockVideoError):
    pass


class StockVideoNotFound(StockVideoError):
    pass


@dataclass(frozen=True)
class StockVideoRequest:
    query: str
    timeout_seconds: int


@dataclass(frozen=True)
class StockVideoResult:
    content: bytes
    source: str


class StockVideoProviderClient(Protocol):
    async def search(self, request: StockVideoRequest) -> StockVideoResult: ...


class MockStockVideoProvider:
    """Deterministic, offline provider — synthesizes a short real clip with
    motion (ffmpeg's testsrc2 pattern animates every frame) so downstream
    trim/concat/assembly logic in tests runs against real video bytes."""

    async def search(self, request: StockVideoRequest) -> StockVideoResult:
        if _MOCK_TIMEOUT in request.query:
            raise StockVideoTimeout("mock stock video provider: simulated timeout")
        if _MOCK_PROVIDER_ERROR in request.query:
            raise StockVideoError("mock stock video provider: simulated upstream error")

        proc = subprocess.run(
            [
                get_ffmpeg_exe(),
                "-f", "lavfi",
                "-i", "testsrc2=size=640x360:rate=25:duration=4",
                "-pix_fmt", "yuv420p",
                "-c:v", "libx264",
                "-f", "mp4", "-movflags", "frag_keyframe+empty_moov",
                "pipe:1",
            ],
            capture_output=True,
            timeout=request.timeout_seconds,
        )
        if proc.returncode != 0:
            raise StockVideoError(f"mock stock video synthesis failed: {proc.stderr[-500:]!r}")
        return StockVideoResult(content=proc.stdout, source="mock")


class PexelsVideoProvider:
    """Real Pexels Video API client. Never used in automated tests."""

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    async def search(self, request: StockVideoRequest) -> StockVideoResult:
        if not self._api_key:
            raise StockVideoError("PEXELS_API_KEY is not configured")
        try:
            async with httpx.AsyncClient(timeout=request.timeout_seconds) as client:
                resp = await client.get(
                    "https://api.pexels.com/videos/search",
                    headers={"Authorization": self._api_key},
                    params={"query": request.query, "per_page": 5, "orientation": "portrait"},
                )
        except httpx.TimeoutException as exc:
            raise StockVideoTimeout("pexels search timed out") from exc
        except httpx.HTTPError as exc:
            raise StockVideoError("pexels search failed") from exc

        if resp.status_code >= 400:
            raise StockVideoError(f"pexels search error (status {resp.status_code})")

        videos = resp.json().get("videos") or []
        if not videos:
            raise StockVideoNotFound(f"no pexels video found for query {request.query!r}")

        file_url = _pick_video_file(videos[0].get("video_files") or [])
        if not file_url:
            raise StockVideoNotFound("pexels video had no usable video_files entry")

        try:
            async with httpx.AsyncClient(timeout=request.timeout_seconds) as client:
                file_resp = await client.get(file_url)
        except httpx.TimeoutException as exc:
            raise StockVideoTimeout("pexels file download timed out") from exc
        except httpx.HTTPError as exc:
            raise StockVideoError("pexels file download failed") from exc

        if file_resp.status_code >= 400:
            raise StockVideoError(f"pexels file download error (status {file_resp.status_code})")
        return StockVideoResult(content=file_resp.content, source="pexels")


def _pick_video_file(video_files: list[dict]) -> str | None:
    # Prefer a moderate resolution (720p-ish) mp4 — good enough quality for a
    # vertical Reel background clip without downloading a huge 4K file.
    mp4_files = [f for f in video_files if f.get("file_type") == "video/mp4" and f.get("link")]
    if not mp4_files:
        return None
    mp4_files.sort(key=lambda f: abs((f.get("height") or 0) - 1280))
    return mp4_files[0]["link"]


def get_stock_video_provider(name: str) -> StockVideoProviderClient:
    if name == "PEXELS":
        from app.core.config import settings

        return PexelsVideoProvider(settings.pexels_api_key)
    return MockStockVideoProvider()
