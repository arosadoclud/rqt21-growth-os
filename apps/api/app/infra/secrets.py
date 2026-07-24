"""Secrets provider abstraction (Phase 6A).

Every secret this app reads today comes from environment variables via
pydantic-settings — that's ``EnvSecretsProvider`` and it's the default.
This module exists so a future move to a real secrets manager (AWS Secrets
Manager, GCP Secret Manager, Doppler, etc.) is a new class behind the same
``get()`` call, not a rewrite of every call site. Nothing currently reads
through this abstraction for values already covered by Settings — it's the
extension point for secrets that need runtime rotation without a redeploy
(e.g. per-connection Meta tokens are already handled by
app.publishing.crypto instead, since those are per-row, not per-process).
"""

from __future__ import annotations

from typing import Protocol

from app.core.config import settings


class SecretsProvider(Protocol):
    def get(self, key: str, default: str | None = None) -> str | None: ...


class EnvSecretsProvider:
    """Default — reads straight from the process environment. Matches
    exactly what pydantic-settings already does for every Settings field;
    this class exists for secrets fetched by name at call time rather than
    declared upfront on Settings."""

    def get(self, key: str, default: str | None = None) -> str | None:
        import os

        return os.environ.get(key, default)


class AwsSecretsManagerProvider:
    """Skeleton for AWS Secrets Manager — not wired in by default (requires
    SECRETS_PROVIDER=aws-secrets-manager). Lazily creates the boto3 client
    on first use, never at construction time. A missing/inaccessible secret
    returns ``default`` rather than raising, so a misconfigured secret name
    degrades to "use the fallback" instead of crashing the process."""

    def __init__(self, *, region: str = "") -> None:
        self._region = region
        self._client = None

    def _ensure_client(self):
        if self._client is None:
            import boto3

            self._client = boto3.client("secretsmanager", region_name=self._region or None)
        return self._client

    def get(self, key: str, default: str | None = None) -> str | None:
        client = self._ensure_client()
        try:
            resp = client.get_secret_value(SecretId=key)
        except Exception:
            return default
        return resp.get("SecretString", default)


def get_secrets_provider() -> SecretsProvider:
    if settings.secrets_provider == "aws-secrets-manager":
        return AwsSecretsManagerProvider(region=settings.storage_region)
    return EnvSecretsProvider()
