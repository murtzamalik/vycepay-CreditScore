"""Pydantic v2 schemas for TOTP Multi-Factor Authentication (Phase 12.7)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class MFASetupResponse(BaseModel):
    """Response from MFA setup — contains secret and backup codes.

    The secret and backup codes are shown ONCE and must be stored
    securely by the user.
    """

    secret: str = Field(..., description="Base32-encoded TOTP secret")
    totp_uri: str = Field(
        ...,
        description="otpauth:// URI for QR code scanning (Google Authenticator)",
    )
    backup_codes: list[str] = Field(
        ...,
        description="One-time backup codes. Store securely — shown only once.",
    )
    message: str = "Scan the QR code or enter the secret in your authenticator app. "                  "Then verify with a code to complete setup."


class MFAVerifyRequest(BaseModel):
    """Request body for MFA verification (setup confirmation or login)."""

    code: str = Field(
        ...,
        min_length=4,
        max_length=10,
        description="6-digit TOTP code or backup code (format: XXXX-XXXX)",
    )


class MFAVerifyResponse(BaseModel):
    """Response from MFA verification."""

    verified: bool
    message: str


class MFAStatusResponse(BaseModel):
    """Current MFA status for a user."""

    mfa_enabled: bool
    mfa_required: bool = Field(
        ...,
        description="Whether MFA is mandatory for the user's role",
    )
    backup_codes_remaining: int | None = Field(
        None,
        description="Number of unused backup codes (null if MFA not enabled)",
    )


class MFADisableRequest(BaseModel):
    """Request to disable MFA — requires current password for security."""

    password: str = Field(
        ...,
        min_length=8,
        description="Current account password to confirm identity",
    )
