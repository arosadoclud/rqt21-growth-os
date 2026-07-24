from __future__ import annotations

import re
import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field, HttpUrl, field_validator

from app.models.enums import (
    CampaignObjective,
    CampaignStatus,
    ContentStatus,
    ContentType,
    Platform,
    ProductStatus,
    SourceSystem,
)

SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def _slug(v: str) -> str:
    v = v.lower().strip()
    if not SLUG_RE.match(v):
        raise ValueError("slug must be lowercase alphanumeric with dashes")
    return v


# ---------- Brand ----------

class BrandCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    slug: str = Field(min_length=2, max_length=80)
    description: str | None = Field(default=None, max_length=2000)
    website_url: HttpUrl | None = None

    @field_validator("slug")
    @classmethod
    def _s(cls, v: str) -> str:
        return _slug(v)


class BrandUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    website_url: HttpUrl | None = None
    is_active: bool | None = None


class BrandRead(BaseModel):
    id: uuid.UUID
    public_id: str
    name: str
    slug: str
    description: str | None
    website_url: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ---------- Product ----------

class ProductCreate(BaseModel):
    brand_id: uuid.UUID
    name: str = Field(min_length=1, max_length=255)
    slug: str = Field(min_length=2, max_length=80)
    description: str | None = Field(default=None, max_length=4000)
    price: Decimal | None = None
    currency: str = Field(default="USD", min_length=3, max_length=3)
    checkout_url: HttpUrl | None = None
    status: ProductStatus = ProductStatus.DRAFT

    @field_validator("slug")
    @classmethod
    def _s(cls, v: str) -> str:
        return _slug(v)

    @field_validator("currency")
    @classmethod
    def _cur(cls, v: str) -> str:
        return v.upper()


class ProductUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=4000)
    price: Decimal | None = None
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    checkout_url: HttpUrl | None = None
    status: ProductStatus | None = None


class ProductRead(BaseModel):
    id: uuid.UUID
    public_id: str
    brand_id: uuid.UUID
    name: str
    slug: str
    description: str | None
    price: Decimal | None
    currency: str
    checkout_url: str | None
    status: ProductStatus
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ---------- Campaign ----------

class CampaignCreate(BaseModel):
    brand_id: uuid.UUID
    product_id: uuid.UUID | None = None
    name: str = Field(min_length=1, max_length=255)
    slug: str = Field(min_length=2, max_length=80)
    objective: CampaignObjective = CampaignObjective.OTHER
    platform: Platform = Platform.OTHER
    status: CampaignStatus = CampaignStatus.DRAFT
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    budget: Decimal | None = None

    @field_validator("slug")
    @classmethod
    def _s(cls, v: str) -> str:
        return _slug(v)


class CampaignUpdate(BaseModel):
    name: str | None = None
    objective: CampaignObjective | None = None
    platform: Platform | None = None
    status: CampaignStatus | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    budget: Decimal | None = None
    product_id: uuid.UUID | None = None


class CampaignRead(BaseModel):
    id: uuid.UUID
    public_id: str
    brand_id: uuid.UUID
    product_id: uuid.UUID | None
    name: str
    slug: str
    objective: CampaignObjective
    platform: Platform
    status: CampaignStatus
    starts_at: datetime | None
    ends_at: datetime | None
    budget: Decimal | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ---------- Content ----------

class ContentCreate(BaseModel):
    brand_id: uuid.UUID
    campaign_id: uuid.UUID | None = None
    product_id: uuid.UUID | None = None
    external_id: str | None = Field(default=None, max_length=255)
    source_system: SourceSystem = SourceSystem.MANUAL
    platform: Platform = Platform.OTHER
    content_type: ContentType = ContentType.POST
    title: str = Field(min_length=1, max_length=500)
    hook: str | None = Field(default=None, max_length=2000)
    caption: str | None = Field(default=None, max_length=8000)
    cta: str | None = Field(default=None, max_length=500)
    media_url: HttpUrl | None = None
    publication_url: HttpUrl | None = None
    status: ContentStatus = ContentStatus.DRAFT
    published_at: datetime | None = None


class ContentUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=500)
    hook: str | None = None
    caption: str | None = None
    cta: str | None = None
    media_url: HttpUrl | None = None
    publication_url: HttpUrl | None = None
    status: ContentStatus | None = None
    published_at: datetime | None = None
    campaign_id: uuid.UUID | None = None
    product_id: uuid.UUID | None = None


class ContentImport(BaseModel):
    """Same shape as ContentCreate but requires external_id + source_system.

    Idempotent by (organization, source_system, external_id).
    """
    brand_id: uuid.UUID
    campaign_id: uuid.UUID | None = None
    product_id: uuid.UUID | None = None
    external_id: str = Field(min_length=1, max_length=255)
    source_system: SourceSystem
    platform: Platform = Platform.OTHER
    content_type: ContentType = ContentType.POST
    title: str = Field(min_length=1, max_length=500)
    hook: str | None = None
    caption: str | None = None
    cta: str | None = None
    media_url: HttpUrl | None = None
    publication_url: HttpUrl | None = None
    status: ContentStatus = ContentStatus.DRAFT
    published_at: datetime | None = None


class ContentRead(BaseModel):
    id: uuid.UUID
    public_id: str
    brand_id: uuid.UUID
    campaign_id: uuid.UUID | None
    product_id: uuid.UUID | None
    external_id: str | None
    source_system: SourceSystem
    platform: Platform
    content_type: ContentType
    title: str
    hook: str | None
    caption: str | None
    cta: str | None
    media_url: str | None
    publication_url: str | None
    status: ContentStatus
    published_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ---------- Tracking Link ----------

class TrackingLinkCreate(BaseModel):
    brand_id: uuid.UUID
    product_id: uuid.UUID | None = None
    campaign_id: uuid.UUID | None = None
    content_id: uuid.UUID | None = None
    destination_url: HttpUrl
    utm_source: str | None = Field(default=None, max_length=150)
    utm_medium: str | None = Field(default=None, max_length=150)
    utm_campaign: str | None = Field(default=None, max_length=150)
    utm_content: str | None = Field(default=None, max_length=150)
    utm_term: str | None = Field(default=None, max_length=150)
    expires_at: datetime | None = None


class TrackingLinkUpdate(BaseModel):
    destination_url: HttpUrl | None = None
    utm_source: str | None = None
    utm_medium: str | None = None
    utm_campaign: str | None = None
    utm_content: str | None = None
    utm_term: str | None = None
    expires_at: datetime | None = None
    is_active: bool | None = None
    campaign_id: uuid.UUID | None = None
    content_id: uuid.UUID | None = None
    product_id: uuid.UUID | None = None


class TrackingLinkRead(BaseModel):
    id: uuid.UUID
    public_id: str
    brand_id: uuid.UUID
    product_id: uuid.UUID | None
    campaign_id: uuid.UUID | None
    content_id: uuid.UUID | None
    short_code: str
    short_url: str
    final_url: str
    destination_url: str
    utm_source: str | None
    utm_medium: str | None
    utm_campaign: str | None
    utm_content: str | None
    utm_term: str | None
    is_active: bool
    expires_at: datetime | None
    created_at: datetime
    updated_at: datetime


# ---------- Analytics ----------

class CampaignSummary(BaseModel):
    campaign_id: uuid.UUID
    campaign_name: str
    total_clicks: int
    unique_visitors: int
    active_links: int
    content_count: int


class ContentSummary(BaseModel):
    content_id: uuid.UUID
    content_title: str
    total_clicks: int
    unique_visitors: int
    active_links: int


class ClickRow(BaseModel):
    id: uuid.UUID
    occurred_at: datetime
    referrer: str | None
    device_type: str | None
    browser: str | None
    os: str | None
    country: str | None
    query_params: dict


class DashboardSummary(BaseModel):
    campaigns_total: int
    contents_total: int
    active_links: int
    clicks_total: int
    top_campaigns: list[CampaignSummary]
    top_contents: list[ContentSummary]


class EditorialSummary(BaseModel):
    pending_review: int
    scheduled_this_week: int
    published_this_month: int
    upcoming: list[dict]


class LeadsCampaignRow(BaseModel):
    campaign_id: uuid.UUID
    campaign_name: str
    leads: int


class LeadsContentRow(BaseModel):
    content_id: uuid.UUID
    content_title: str
    leads: int


class LeadsLinkRow(BaseModel):
    tracking_link_id: uuid.UUID
    short_code: str
    leads: int


class LeadsSummary(BaseModel):
    new_leads: int
    qualified_leads: int
    won_leads: int
    lost_leads: int
    total_leads: int
    conversion_qualified_rate: float
    conversion_won_rate: float
    top_campaigns: list[LeadsCampaignRow]
    top_contents: list[LeadsContentRow]
    top_links: list[LeadsLinkRow]


class Funnel(BaseModel):
    clicks: int
    unique_visitors: int
    leads: int
    qualified_leads: int
    won_leads: int
    click_to_lead_rate: float
    lead_to_won_rate: float


class Phase3Dashboard(BaseModel):
    editorial: EditorialSummary
    leads: LeadsSummary
