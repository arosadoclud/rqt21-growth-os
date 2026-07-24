from __future__ import annotations

import re
import uuid

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.models.membership import Role

SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class OrganizationCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    slug: str = Field(min_length=2, max_length=64)

    @field_validator("slug")
    @classmethod
    def _slug_shape(cls, v: str) -> str:
        v = v.lower().strip()
        if not SLUG_RE.match(v):
            raise ValueError("slug must be lowercase alphanumeric with dashes")
        return v


class OrganizationRead(BaseModel):
    id: uuid.UUID
    name: str
    slug: str

    model_config = {"from_attributes": True}


class MemberRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    email: EmailStr
    full_name: str
    role: Role

    model_config = {"from_attributes": True}


class MemberCreate(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=8, max_length=200)
    role: Role


class MemberUpdate(BaseModel):
    role: Role
