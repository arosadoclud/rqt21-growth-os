from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

from app.models.enums import LeadActivityType, LeadSource, LeadStatus, SourceSystem

# Phone/whatsapp are intentionally NOT normalized to E.164 at the schema
# level: the correct default country comes from the organization
# (Organization.country_code), which is not known until the request reaches
# an endpoint with an authenticated OrgContext. Schemas only trim; endpoints
# call app.utils.phone.normalize_phone(value, org.country_code) before
# persisting. See app/api/v1/leads.py and app/api/public_leads.py.


def _trim(v: str | None) -> str | None:
    if v is None:
        return None
    v = v.strip()
    return v or None


class LeadBase(BaseModel):
    first_name: str = Field(min_length=1, max_length=120)
    last_name: str | None = Field(default=None, max_length=120)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=40)
    whatsapp: str | None = Field(default=None, max_length=40)
    source: LeadSource = LeadSource.MANUAL
    country: str | None = Field(default=None, max_length=4)
    city: str | None = Field(default=None, max_length=120)
    notes: str | None = Field(default=None, max_length=4000)

    brand_id: uuid.UUID | None = None
    product_id: uuid.UUID | None = None
    campaign_id: uuid.UUID | None = None
    content_item_id: uuid.UUID | None = None
    tracking_link_id: uuid.UUID | None = None

    utm_source: str | None = None
    utm_medium: str | None = None
    utm_campaign: str | None = None
    utm_content: str | None = None
    utm_term: str | None = None

    @field_validator("phone", "whatsapp")
    @classmethod
    def _phone(cls, v: str | None) -> str | None:
        return _trim(v)

    @field_validator("email")
    @classmethod
    def _email_lower(cls, v: str | None) -> str | None:
        return v.lower() if v else None

    @model_validator(mode="after")
    def _at_least_one_contact(self) -> LeadBase:
        if not (self.email or self.phone or self.whatsapp):
            raise ValueError("at least one of email/phone/whatsapp is required")
        return self


class LeadCreate(LeadBase):
    external_id: str | None = Field(default=None, max_length=255)
    source_system: SourceSystem | None = None
    status: LeadStatus = LeadStatus.NEW


class LeadImport(LeadBase):
    """Idempotent import by (org, source_system, external_id)."""
    external_id: str = Field(min_length=1, max_length=255)
    source_system: SourceSystem
    status: LeadStatus = LeadStatus.NEW


class LeadUpdate(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    email: EmailStr | None = None
    phone: str | None = None
    whatsapp: str | None = None
    country: str | None = None
    city: str | None = None
    notes: str | None = None
    brand_id: uuid.UUID | None = None
    product_id: uuid.UUID | None = None
    campaign_id: uuid.UUID | None = None
    content_item_id: uuid.UUID | None = None

    @field_validator("phone", "whatsapp")
    @classmethod
    def _phone(cls, v: str | None) -> str | None:
        return _trim(v)

    @field_validator("email")
    @classmethod
    def _email_lower(cls, v: str | None) -> str | None:
        return v.lower() if v else None


class LeadStatusChangeRequest(BaseModel):
    status: LeadStatus
    note: str | None = Field(default=None, max_length=2000)


class LeadRead(BaseModel):
    id: uuid.UUID
    public_id: str
    brand_id: uuid.UUID | None
    product_id: uuid.UUID | None
    campaign_id: uuid.UUID | None
    content_item_id: uuid.UUID | None
    tracking_link_id: uuid.UUID | None
    first_name: str
    last_name: str | None
    email: str | None
    phone: str | None
    whatsapp: str | None
    source: LeadSource
    status: LeadStatus
    country: str | None
    city: str | None
    notes: str | None
    utm_source: str | None
    utm_medium: str | None
    utm_campaign: str | None
    utm_content: str | None
    utm_term: str | None
    external_id: str | None
    source_system: SourceSystem | None
    created_at: datetime
    updated_at: datetime
    pii_access: str = "full"

    model_config = {"from_attributes": True}


def serialize_lead_for_role(lead, role) -> LeadRead:
    """Serialize a Lead ORM row respecting the caller's PII access level.

    ANALYST/VIEWER receive masked email/phone/whatsapp and no notes.
    All other roles receive the full record.
    """
    from app.utils.pii import mask_email, mask_notes, mask_phone, role_can_see_full_pii

    if role_can_see_full_pii(role):
        return LeadRead.model_validate(lead)

    data = LeadRead.model_validate(lead).model_dump()
    data["email"] = mask_email(data["email"])
    data["phone"] = mask_phone(data["phone"])
    data["whatsapp"] = mask_phone(data["whatsapp"])
    data["notes"] = mask_notes(data["notes"])
    data["pii_access"] = "redacted"
    return LeadRead(**data)


class LeadActivityCreate(BaseModel):
    activity_type: LeadActivityType = LeadActivityType.NOTE_ADDED
    description: str = Field(min_length=1, max_length=2000)
    metadata: dict[str, Any] = Field(default_factory=dict)


class LeadActivityRead(BaseModel):
    id: uuid.UUID
    public_id: str
    lead_id: uuid.UUID
    actor_user_id: uuid.UUID | None
    activity_type: LeadActivityType
    description: str | None
    metadata: dict[str, Any]
    created_at: datetime

    model_config = {"from_attributes": True}


def sanitize_lead_activity(activity: LeadActivityRead, role) -> LeadActivityRead:
    """Redacted roles see the activity type + timestamp but no freeform text
    or arbitrary metadata (may embed PII: emails in EMAIL_SENT, notes, etc)."""
    from app.utils.pii import role_can_see_full_pii

    if role_can_see_full_pii(role):
        return activity
    return LeadActivityRead(
        id=activity.id,
        public_id=activity.public_id,
        lead_id=activity.lead_id,
        actor_user_id=activity.actor_user_id,
        activity_type=activity.activity_type,
        description=None,
        metadata={},
        created_at=activity.created_at,
    )


class PublicLeadCreate(BaseModel):
    """Payload accepted at the public capture endpoint."""
    first_name: str = Field(min_length=1, max_length=120)
    last_name: str | None = Field(default=None, max_length=120)
    email: EmailStr | None = None
    phone: str | None = None
    whatsapp: str | None = None
    country: str | None = Field(default=None, max_length=4)
    city: str | None = Field(default=None, max_length=120)
    notes: str | None = Field(default=None, max_length=2000)
    source: LeadSource = LeadSource.LANDING_PAGE
    tracking_code: str | None = None
    public_source_token: str | None = Field(default=None, max_length=128)
    # UTMs the landing page may include when there is no tracking code.
    utm_source: str | None = None
    utm_medium: str | None = None
    utm_campaign: str | None = None
    utm_content: str | None = None
    utm_term: str | None = None
    # Honeypot: real humans leave this empty. Name is neutral so it looks like
    # a normal form field to bots.
    website: str | None = None

    @field_validator("phone", "whatsapp")
    @classmethod
    def _phone(cls, v: str | None) -> str | None:
        return _trim(v)

    @field_validator("email")
    @classmethod
    def _email_lower(cls, v: str | None) -> str | None:
        return v.lower() if v else None

    @model_validator(mode="after")
    def _at_least_one_contact(self) -> PublicLeadCreate:
        if not (self.email or self.phone or self.whatsapp):
            raise ValueError("at least one of email/phone/whatsapp is required")
        return self


class PublicLeadAck(BaseModel):
    """Response to public capture — never expose internal ids or state."""
    reference: str
    accepted: bool = True
