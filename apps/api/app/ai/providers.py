"""AI provider abstraction.

``AIProviderClient`` is the seam between the generation pipeline and whatever
actually produces text. Tests and local development use ``MockAIProvider`` —
deterministic, offline, no network calls, ever. ``AnthropicAIProvider`` and
``OpenAIProvider`` are real implementations selected via ``AI_PROVIDER`` but
are never exercised by the automated test suite.

Sentinel topics for MockAIProvider (used by tests to force each failure mode
without any conditional test-only code in the provider itself):
    __mock_timeout__        -> raises AIProviderTimeout
    __mock_rate_limit__     -> raises AIProviderRateLimited
    __mock_provider_error__ -> raises AIProviderError
    __mock_invalid_json__   -> returns syntactically invalid JSON
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import httpx

from app.core.config import settings


class AIProviderError(Exception):
    """Base class for provider failures. error_code on the job is derived
    from the specific subclass name, error_message is this exception's str()
    truncated — never the provider's raw response body."""


class AIProviderTimeout(AIProviderError):
    pass


class AIProviderRateLimited(AIProviderError):
    pass


class AIProviderInvalidResponse(AIProviderError):
    pass


@dataclass(frozen=True)
class GenerationRequest:
    system_instructions: str
    user_prompt: str
    model: str
    max_output_tokens: int
    timeout_seconds: int


@dataclass(frozen=True)
class GenerationResult:
    raw_text: str
    input_tokens: int
    output_tokens: int


class AIProviderClient(Protocol):
    async def generate(self, request: GenerationRequest) -> GenerationResult: ...


_MOCK_TIMEOUT = "__mock_timeout__"
_MOCK_RATE_LIMIT = "__mock_rate_limit__"
_MOCK_PROVIDER_ERROR = "__mock_provider_error__"
_MOCK_INVALID_JSON = "__mock_invalid_json__"

_MOCK_FIXTURE = """{
  "title": "5 hábitos keto que sí puedes sostener",
  "hook": "Si crees que keto es solo restricción, mira esto.",
  "script": "Toma 1: primer plano del plato. Toma 2: preparación rápida. Toma 3: CTA.",
  "caption": "Pequeños cambios, resultados sostenibles. Descubre el enfoque de 21 días.",
  "cta": "Link en la bio para ver el programa completo",
  "hashtags": ["#ketodominicana", "#habitossaludables", "#recetaskето"],
  "visual_notes": ["Luz natural", "Primer plano del plato terminado"]
}"""


class MockAIProvider:
    """Deterministic, offline provider for tests and local dev."""

    async def generate(self, request: GenerationRequest) -> GenerationResult:
        prompt = request.user_prompt

        if _MOCK_TIMEOUT in prompt:
            raise AIProviderTimeout("mock provider: simulated timeout")
        if _MOCK_RATE_LIMIT in prompt:
            raise AIProviderRateLimited("mock provider: simulated rate limit")
        if _MOCK_PROVIDER_ERROR in prompt:
            raise AIProviderError("mock provider: simulated upstream error")
        if _MOCK_INVALID_JSON in prompt:
            return GenerationResult(
                raw_text="{not valid json,,,", input_tokens=42, output_tokens=8
            )

        # Deterministic "fake" token counts, roughly proportional to input size
        # so usage summaries look plausible in dev/tests without any real cost.
        input_tokens = max(20, len(request.system_instructions + prompt) // 4)
        output_tokens = len(_MOCK_FIXTURE) // 4
        return GenerationResult(
            raw_text=_MOCK_FIXTURE, input_tokens=input_tokens, output_tokens=output_tokens
        )


class AnthropicAIProvider:
    """Real Anthropic Messages API client. Never used in automated tests."""

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    async def generate(self, request: GenerationRequest) -> GenerationResult:
        if not self._api_key:
            raise AIProviderError("ANTHROPIC_API_KEY is not configured")
        try:
            async with httpx.AsyncClient(timeout=request.timeout_seconds) as client:
                resp = await client.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={
                        "x-api-key": self._api_key,
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json",
                    },
                    json={
                        "model": request.model,
                        "max_tokens": request.max_output_tokens,
                        "system": request.system_instructions,
                        "messages": [{"role": "user", "content": request.user_prompt}],
                    },
                )
        except httpx.TimeoutException as exc:
            raise AIProviderTimeout("anthropic request timed out") from exc
        except httpx.HTTPError as exc:
            raise AIProviderError("anthropic request failed") from exc

        if resp.status_code == 429:
            raise AIProviderRateLimited("anthropic rate limit exceeded")
        if resp.status_code >= 400:
            raise AIProviderError(f"anthropic error (status {resp.status_code})")

        data = resp.json()
        text_parts = [b.get("text", "") for b in data.get("content", []) if b.get("type") == "text"]
        usage = data.get("usage", {})
        return GenerationResult(
            raw_text="".join(text_parts),
            input_tokens=int(usage.get("input_tokens") or 0),
            output_tokens=int(usage.get("output_tokens") or 0),
        )


class OpenAIProvider:
    """Real OpenAI Chat Completions client. Never used in automated tests."""

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    async def generate(self, request: GenerationRequest) -> GenerationResult:
        if not self._api_key:
            raise AIProviderError("OPENAI_API_KEY is not configured")
        try:
            async with httpx.AsyncClient(timeout=request.timeout_seconds) as client:
                resp = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self._api_key}",
                        "content-type": "application/json",
                    },
                    json={
                        "model": request.model,
                        "max_tokens": request.max_output_tokens,
                        "messages": [
                            {"role": "system", "content": request.system_instructions},
                            {"role": "user", "content": request.user_prompt},
                        ],
                    },
                )
        except httpx.TimeoutException as exc:
            raise AIProviderTimeout("openai request timed out") from exc
        except httpx.HTTPError as exc:
            raise AIProviderError("openai request failed") from exc

        if resp.status_code == 429:
            raise AIProviderRateLimited("openai rate limit exceeded")
        if resp.status_code >= 400:
            raise AIProviderError(f"openai error (status {resp.status_code})")

        data = resp.json()
        choice = (data.get("choices") or [{}])[0]
        text = choice.get("message", {}).get("content", "")
        usage = data.get("usage", {})
        return GenerationResult(
            raw_text=text,
            input_tokens=int(usage.get("prompt_tokens") or 0),
            output_tokens=int(usage.get("completion_tokens") or 0),
        )


def get_provider(name: str) -> AIProviderClient:
    if name == "ANTHROPIC":
        return AnthropicAIProvider(settings.anthropic_api_key)
    if name == "OPENAI":
        return OpenAIProvider(settings.openai_api_key)
    return MockAIProvider()
