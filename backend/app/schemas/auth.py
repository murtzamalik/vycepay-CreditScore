"""Authentication-related Pydantic v2 schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    """Credentials for admin portal login (BRD UC-AUTH-002)."""

    email: EmailStr
    password: str = Field(..., min_length=8)


class LoginResponse(BaseModel):
    """JWT token pair returned after successful login."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = Field(..., description="Access token TTL in seconds")


class TokenPayload(BaseModel):
    """Decoded JWT claims."""

    sub: str
    role: str
    exp: datetime
    type: str = Field(..., description="Token type: access | refresh | reset")


class RefreshRequest(BaseModel):
    """Request body for refreshing an access token."""

    refresh_token: str


class PasswordResetRequest(BaseModel):
    """Request a password reset link (BRD UC-AUTH-003)."""

    email: EmailStr


class PasswordResetConfirm(BaseModel):
    """Confirm password reset with token and new password."""

    token: str
    new_password: str = Field(..., min_length=8)


class ChangePasswordRequest(BaseModel):
    """Change password for authenticated user."""

    current_password: str = Field(..., min_length=8)
    new_password: str = Field(..., min_length=8)


class APIKeyResponse(BaseModel):
    """Returned once when a new API key is generated."""

    api_key: str
    message: str = "Store this key securely. It will not be shown again."
