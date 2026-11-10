"""Admin API request/response schemas (Phase 7 — Customer & User Management)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, EmailStr, Field

from app.models.customer import CustomerStatus, LicenseTier
from app.models.user import UserRole


# ---------------------------------------------------------------------------
# Customer schemas
# ---------------------------------------------------------------------------


class CustomerCreateRequest(BaseModel):
    """Request body for onboarding a new customer (Task 7.1)."""

    name: str = Field(..., min_length=1, max_length=200)
    contact_email: EmailStr
    license_tier: LicenseTier
    monthly_query_limit: int = Field(..., gt=0)


class CustomerResponse(BaseModel):
    """Customer details returned in API responses."""

    customer_id: uuid.UUID
    name: str
    contact_email: str | None = None
    license_tier: LicenseTier
    status: CustomerStatus
    monthly_query_limit: int
    sandbox_enabled: bool
    production_enabled: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class CustomerCreateResponse(BaseModel):
    """Response after creating a new customer — includes plaintext API key."""

    customer: CustomerResponse
    api_key: str = Field(
        ...,
        description="Store this key securely. It will not be shown again.",
    )


class CustomerListFilter(BaseModel):
    """Query parameters for listing customers (Task 7.2)."""

    status: CustomerStatus | None = None
    tier: LicenseTier | None = None
    page: int = Field(1, ge=1)
    limit: int = Field(50, ge=1, le=200)


class LicenseUpdateRequest(BaseModel):
    """Request body for updating a customer license (Task 7.3)."""

    tier: LicenseTier | None = None
    query_limit: int | None = Field(None, gt=0, alias="queryLimit")
    features: dict[str, bool] | None = None

    model_config = {"populate_by_name": True}


# ---------------------------------------------------------------------------
# Usage schemas
# ---------------------------------------------------------------------------


class UsageResponse(BaseModel):
    """Monthly API usage summary for a customer (Task 7.8)."""

    customer_id: uuid.UUID
    period: str = Field(..., description="YYYY-MM period")
    total_requests: int
    successful_requests: int
    failed_requests: int
    endpoints: dict[str, int] = Field(
        default_factory=dict,
        description="Request count per endpoint",
    )


# ---------------------------------------------------------------------------
# User schemas
# ---------------------------------------------------------------------------


class UserCreateRequest(BaseModel):
    """Request body for creating an admin user (Task 7.6)."""

    email: EmailStr
    full_name: str = Field(..., min_length=1, max_length=200)
    role: UserRole


class UserResponse(BaseModel):
    """User details returned in API responses."""

    user_id: uuid.UUID
    email: str
    full_name: str
    role: UserRole
    is_active: bool
    must_change_password: bool
    created_at: datetime
    last_login: datetime | None = None

    model_config = {"from_attributes": True}


class UserCreateResponse(BaseModel):
    """Response after creating a new user — includes temporary password."""

    user: UserResponse
    temporary_password: str = Field(
        ...,
        description="Provide this to the user securely. They must change it on first login.",
    )


class UserUpdateRequest(BaseModel):
    """Request body for updating/deactivating a user (Task 7.7)."""

    role: UserRole | None = None
    is_active: bool | None = None


# ---------------------------------------------------------------------------
# Quota error schema (Task 7.9)
# ---------------------------------------------------------------------------


class QuotaExceededDetail(BaseModel):
    """Details included in RATE_LIMIT_EXCEEDED error response."""

    quota: int
    used: int
    resets_at: str = Field(..., alias="resetsAt")

    model_config = {"populate_by_name": True}
