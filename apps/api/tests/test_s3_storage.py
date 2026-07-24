from __future__ import annotations

import asyncio

import boto3
import pytest
from moto import mock_aws

from app.storage.provider import S3StorageProvider, get_storage_provider

_BUCKET = "rqt21-test-assets"
_REGION = "us-east-1"


@pytest.fixture
def s3_bucket():
    with mock_aws():
        client = boto3.client("s3", region_name=_REGION)
        client.create_bucket(Bucket=_BUCKET)
        yield client


def test_upload_and_download_roundtrip(s3_bucket):
    provider = S3StorageProvider(bucket=_BUCKET, region=_REGION)
    content = b"fake-png-bytes-for-testing"

    stored = asyncio.run(
        provider.upload(storage_key="org1/photo.png", content=content, mime_type="image/png")
    )
    assert stored.size_bytes == len(content)
    assert stored.checksum_sha256

    obj = s3_bucket.get_object(Bucket=_BUCKET, Key="org1/photo.png")
    assert obj["Body"].read() == content
    assert obj["ContentType"] == "image/png"


def test_signed_url_is_time_limited(s3_bucket):
    provider = S3StorageProvider(bucket=_BUCKET, region=_REGION)
    asyncio.run(
        provider.upload(storage_key="org1/photo.png", content=b"x", mime_type="image/png")
    )
    url = asyncio.run(provider.create_signed_url(storage_key="org1/photo.png", ttl_seconds=60))
    assert "org1/photo.png" in url
    assert "X-Amz-Expires=60" in url or "Expires=" in url


def test_delete_removes_object(s3_bucket):
    provider = S3StorageProvider(bucket=_BUCKET, region=_REGION)
    asyncio.run(
        provider.upload(storage_key="org1/photo.png", content=b"x", mime_type="image/png")
    )
    asyncio.run(provider.delete(storage_key="org1/photo.png"))

    from botocore.exceptions import ClientError

    with pytest.raises(ClientError):
        s3_bucket.get_object(Bucket=_BUCKET, Key="org1/photo.png")


def test_missing_bucket_raises_at_construction():
    with pytest.raises(ValueError):
        S3StorageProvider(bucket="")


def test_factory_selects_s3_provider(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "storage_provider", "S3")
    monkeypatch.setattr(settings, "storage_bucket", _BUCKET)
    monkeypatch.setattr(settings, "storage_region", _REGION)
    provider = get_storage_provider()
    assert isinstance(provider, S3StorageProvider)


def test_factory_selects_r2_provider_with_endpoint(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "storage_provider", "R2")
    monkeypatch.setattr(settings, "storage_bucket", _BUCKET)
    monkeypatch.setattr(
        settings, "storage_endpoint", "https://accountid.r2.cloudflarestorage.com"
    )
    provider = get_storage_provider()
    assert isinstance(provider, S3StorageProvider)
