"""KYC verification request/response schemas (BRD §5.3, Phase 15)."""

from __future__ import annotations

import enum
from datetime import datetime

from pydantic import BaseModel, Field


class IDType(str, enum.Enum):
    """Supported identity document types for KYC verification."""

    NATIONAL_ID = "NATIONAL_ID"
    PASSPORT = "PASSPORT"
    DRIVERS_LICENSE = "DRIVERS_LICENSE"


class KYCStatusEnum(str, enum.Enum):
    """KYC verification status."""

    VERIFIED = "VERIFIED"
    PENDING = "PENDING"
    FAILED = "FAILED"


class BiometricData(BaseModel):
    """Biometric data for face match verification."""

    selfie_image_base64: str = Field(
        ...,
        description="Base64-encoded selfie image for face matching",
    )
    id_image_base64: str | None = Field(
        default=None,
        description="Base64-encoded ID document image (optional if already on file)",
    )


class KYCVerificationRequest(BaseModel):
    """Request to trigger KYC verification for a subject."""

    national_id: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="National ID or document number (hashed before storage/logging)",
    )
    id_type: IDType = Field(
        default=IDType.NATIONAL_ID,
        description="Type of identity document",
    )
    biometric_data: BiometricData | None = Field(
        default=None,
        description="Biometric data for face match and liveness checks",
    )
    first_name: str | None = Field(
        default=None,
        max_length=100,
        description="First name on the identity document",
    )
    last_name: str | None = Field(
        default=None,
        max_length=100,
        description="Last name on the identity document",
    )
    country: str = Field(
        default="KE",
        max_length=2,
        description="ISO 3166-1 alpha-2 country code",
    )


class KYCResult(BaseModel):
    """Internal KYC verification result from Smile ID."""

    status: KYCStatusEnum
    confidence_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Identity match confidence score",
    )
    face_match_score: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Biometric face match confidence",
    )
    liveness_passed: bool | None = Field(
        default=None,
        description="Whether the liveness anti-spoofing check passed",
    )
    provider_reference: str = Field(
        ...,
        description="Smile ID job reference for audit trail",
    )
    verified_at: datetime | None = Field(
        default=None,
        description="Timestamp of successful verification",
    )
    failure_reason: str | None = Field(
        default=None,
        description="Reason for verification failure, if applicable",
    )


class KYCVerificationResponse(BaseModel):
    """API response for KYC verification."""

    subject_id: str = Field(
        ...,
        description="SHA-256 hashed subject identifier",
    )
    status: KYCStatusEnum
    confidence_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
    )
    face_match_score: float | None = None
    liveness_passed: bool | None = None
    provider_reference: str
    verified_at: datetime | None = None
    failure_reason: str | None = None


class KYCStatusResponse(BaseModel):
    """API response for KYC status query."""

    subject_id: str = Field(
        ...,
        description="SHA-256 hashed subject identifier",
    )
    kyc_status: KYCStatusEnum
    last_verified_at: datetime | None = None
    last_check_provider: str | None = None
    confidence_score: float | None = None
