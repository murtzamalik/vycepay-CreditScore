"""AML screening request/response schemas (BRD §5.3, Phase 15)."""

from __future__ import annotations

import enum
from datetime import datetime

from pydantic import BaseModel, Field


class AMLRiskRating(str, enum.Enum):
    """AML risk rating levels."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class AMLStatusEnum(str, enum.Enum):
    """AML screening status."""

    CLEAR = "CLEAR"
    REVIEW = "REVIEW"
    FLAGGED = "FLAGGED"


class AMLScreeningRequest(BaseModel):
    """Request to trigger AML screening for a subject."""

    name: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Full name of the individual or entity to screen",
    )
    date_of_birth: str | None = Field(
        default=None,
        description="Date of birth in YYYY-MM-DD format",
    )
    nationality: str = Field(
        default="KE",
        max_length=2,
        description="ISO 3166-1 alpha-2 country code",
    )
    national_id: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="National ID (hashed before storage/logging)",
    )


class AMLMatchDetail(BaseModel):
    """Details of a single AML match hit."""

    list_name: str = Field(..., description="Name of the matched list")
    match_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence of the match",
    )
    match_type: str = Field(
        ...,
        description="Type of match: sanctions, pep, adverse_media",
    )


class AMLResult(BaseModel):
    """Internal AML screening result from ComplyAdvantage."""

    status: AMLStatusEnum
    risk_rating: AMLRiskRating
    risk_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Normalized AML risk score",
    )
    is_sanctioned: bool = Field(
        default=False,
        description="Whether entity is on a sanctions list",
    )
    is_pep: bool = Field(
        default=False,
        description="Whether entity is a Politically Exposed Person",
    )
    adverse_media_found: bool = Field(
        default=False,
        description="Whether adverse media hits were found",
    )
    matches: list[AMLMatchDetail] = Field(
        default_factory=list,
        description="Detailed match hits from screening",
    )
    provider_reference: str = Field(
        ...,
        description="ComplyAdvantage search reference for audit trail",
    )
    screened_at: datetime | None = Field(
        default=None,
        description="Timestamp of screening completion",
    )


class AMLScreeningResponse(BaseModel):
    """API response for AML screening."""

    subject_id: str = Field(
        ...,
        description="SHA-256 hashed subject identifier",
    )
    status: AMLStatusEnum
    risk_rating: AMLRiskRating
    risk_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
    )
    is_sanctioned: bool
    is_pep: bool
    adverse_media_found: bool
    match_count: int = Field(
        ...,
        ge=0,
        description="Number of AML match hits",
    )
    provider_reference: str
    screened_at: datetime | None = None


class AMLStatusResponse(BaseModel):
    """API response for AML status query."""

    subject_id: str = Field(
        ...,
        description="SHA-256 hashed subject identifier",
    )
    aml_status: AMLStatusEnum
    risk_rating: AMLRiskRating | None = None
    risk_score: float | None = None
    is_sanctioned: bool | None = None
    is_pep: bool | None = None
    last_screened_at: datetime | None = None
    last_check_provider: str | None = None
