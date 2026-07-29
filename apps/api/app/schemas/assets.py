from __future__ import annotations

import base64
import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.models.enums import AssetStatus, AssetType, StorageProviderName, VariantStatus, VariantType


class InitUploadRequest(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    mime_type: str = Field(min_length=1, max_length=150)
    size_bytes: int = Field(gt=0)
    asset_type: AssetType
    brand_id: uuid.UUID | None = None
    product_id: uuid.UUID | None = None
    content_item_id: uuid.UUID | None = None
    alt_text: str | None = Field(default=None, max_length=500)
    caption: str | None = Field(default=None, max_length=1000)


class InitUploadResponse(BaseModel):
    asset_id: uuid.UUID
    storage_provider: StorageProviderName
    upload_method: str
    max_size_bytes: int


class CompleteUploadRequest(BaseModel):
    asset_id: uuid.UUID
    content_base64: str = Field(min_length=1)

    @field_validator("content_base64")
    @classmethod
    def _valid_b64(cls, v: str) -> str:
        try:
            base64.b64decode(v, validate=True)
        except Exception as exc:
            raise ValueError("content_base64 is not valid base64") from exc
        return v


class AssetUpdate(BaseModel):
    alt_text: str | None = Field(default=None, max_length=500)
    caption: str | None = Field(default=None, max_length=1000)
    content_item_id: uuid.UUID | None = None
    brand_id: uuid.UUID | None = None
    product_id: uuid.UUID | None = None


class AssetRead(BaseModel):
    id: uuid.UUID
    public_id: str
    brand_id: uuid.UUID | None
    product_id: uuid.UUID | None
    content_item_id: uuid.UUID | None
    uploaded_by_user_id: uuid.UUID | None
    asset_type: AssetType
    status: AssetStatus
    storage_provider: StorageProviderName
    original_filename: str
    safe_filename: str
    mime_type: str
    size_bytes: int
    width: int | None
    height: int | None
    duration_seconds: int | None
    checksum_sha256: str
    alt_text: str | None
    caption: str | None
    metadata: dict[str, Any] = Field(default_factory=dict, alias="asset_metadata")
    created_at: datetime
    updated_at: datetime
    archived_at: datetime | None

    model_config = {"from_attributes": True, "populate_by_name": True}


class SignedUrlResponse(BaseModel):
    url: str
    expires_in_seconds: int


class AssetVariantCreate(BaseModel):
    platform: str = Field(min_length=1, max_length=32)
    variant_type: VariantType
    width: int | None = Field(default=None, gt=0)
    height: int | None = Field(default=None, gt=0)
    duration_seconds: int | None = Field(default=None, gt=0)
    # MVP: associate an already-prepared variant (MOCK transform) rather than
    # running a real transcode pipeline. See Phase 5 spec section 5.
    source_asset_variant_id: uuid.UUID | None = None


class GenerateThumbnailRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    subtitle: str | None = Field(default=None, max_length=200)
    benefits: list[str] = Field(default_factory=list, max_length=3)
    cta_banner: str | None = Field(default=None, max_length=200)
    content_style: str | None = Field(default=None, max_length=32)
    format: str = Field(default="vertical", max_length=32)


class AssetVariantRead(BaseModel):
    id: uuid.UUID
    public_id: str
    asset_id: uuid.UUID
    platform: str
    variant_type: VariantType
    width: int | None
    height: int | None
    duration_seconds: int | None
    mime_type: str
    size_bytes: int
    status: VariantStatus
    transformation_spec: dict[str, Any]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
