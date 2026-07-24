from __future__ import annotations

from moto import mock_aws

from app.infra.secrets import (
    AwsSecretsManagerProvider,
    EnvSecretsProvider,
    get_secrets_provider,
)


def test_env_provider_reads_environment(monkeypatch):
    monkeypatch.setenv("RQT21_TEST_SECRET", "sh-sh-secret")
    provider = EnvSecretsProvider()
    assert provider.get("RQT21_TEST_SECRET") == "sh-sh-secret"


def test_env_provider_returns_default_when_missing(monkeypatch):
    monkeypatch.delenv("RQT21_TEST_MISSING", raising=False)
    provider = EnvSecretsProvider()
    assert provider.get("RQT21_TEST_MISSING", "fallback") == "fallback"


def test_factory_defaults_to_env(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "secrets_provider", "env")
    assert isinstance(get_secrets_provider(), EnvSecretsProvider)


def test_factory_uses_aws_when_configured(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "secrets_provider", "aws-secrets-manager")
    assert isinstance(get_secrets_provider(), AwsSecretsManagerProvider)


def test_aws_provider_reads_secret():
    with mock_aws():
        import boto3

        client = boto3.client("secretsmanager", region_name="us-east-1")
        client.create_secret(Name="rqt21/meta-app-secret", SecretString="s3cr3t-value")

        provider = AwsSecretsManagerProvider(region="us-east-1")
        assert provider.get("rqt21/meta-app-secret") == "s3cr3t-value"


def test_aws_provider_missing_secret_returns_default():
    with mock_aws():
        provider = AwsSecretsManagerProvider(region="us-east-1")
        assert provider.get("does-not-exist", "fallback") == "fallback"
