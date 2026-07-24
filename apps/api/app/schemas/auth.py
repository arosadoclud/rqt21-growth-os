from __future__ import annotations

import uuid

from pydantic import BaseModel, EmailStr, Field

from app.models.membership import Role


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=200)


class OrganizationSummary(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    role: Role

    model_config = {"from_attributes": True}


class UserPublic(BaseModel):
    id: uuid.UUID
    email: EmailStr
    full_name: str
    is_active: bool

    model_config = {"from_attributes": True}


class MeResponse(BaseModel):
    user: UserPublic
    organizations: list[OrganizationSummary]


class LoginResponse(MeResponse):
    pass
