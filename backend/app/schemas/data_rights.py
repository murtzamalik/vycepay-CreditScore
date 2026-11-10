"""Pydantic v2 schemas for Data Subject Rights endpoints (Kenya DPA 2019, Phase 12.5).

Supports:
  - Right of Access (Article 26): Subject can request all data held about them
  - Right of Rectification (Article 27): Subject can request correction of data
  - Right to Deletion / Erasure (Article 28): Subject can request deletion (anonymization)
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Access request/response
# ---------------------------------------------------------------------------


class SubjectDataResponse(BaseModel):
    """All data held about a subject — returned for Right of Access requests."""

    subject_id: str
    subject_type: str
    kyc_status: str
    aml_status: str
    created_at: datetime
    scores: list[ScoreRecord] = Field(default_factory=list)
    features: list[FeatureRecord] = Field(default_factory=list)
    api_request_count: int = 0
    data_categories: list[str] = Field(
        default_factory=list,
        description="Categories of data held (e.g., 'identity', 'financial', 'scoring')",
    )
    processing_purposes: list[str] = Field(
        default_factory=lambda: [
            "Credit scoring and risk assessment",
            "Regulatory compliance (CBK, Kenya DPA 2019)",
            "Fraud prevention and AML screening",
        ],
    )
    data_retention_policy: str = "10 years from date of last activity, per CBK regulations"
    request_timestamp: datetime


class ScoreRecord(BaseModel):
    """A score record included in a data access response."""

    score_id: str
    vyce_score: int
    niq_score: int | None = None
    score_date: str
    model_version: str


class FeatureRecord(BaseModel):
    """A feature record included in a data access response."""

    feature_name: str
    feature_value: str
    feature_date: str
    feature_category: str | None = None


# Fix forward references
SubjectDataResponse.model_rebuild()


# ---------------------------------------------------------------------------
# Correction request/response
# ---------------------------------------------------------------------------


class CorrectionRequest(BaseModel):
    """Request to correct data held about a subject (Right of Rectification)."""

    subject_id: str = Field(..., description="UUID of the subject")
    field_name: str = Field(
        ...,
        description="Name of the field to correct (e.g., 'kyc_status', 'subject_type')",
    )
    current_value: str = Field(..., description="Current value of the field")
    corrected_value: str = Field(..., description="Requested corrected value")
    justification: str = Field(
        ...,
        min_length=10,
        description="Reason for the correction request",
    )
    supporting_document_ref: str | None = Field(
        None,
        description="Reference to supporting documentation (if any)",
    )


class CorrectionResponse(BaseModel):
    """Response to a data correction request."""

    request_id: str
    subject_id: str
    status: str = Field(
        ...,
        description="PENDING | APPROVED | REJECTED",
    )
    field_name: str
    message: str
    created_at: datetime


# ---------------------------------------------------------------------------
# Deletion request/response
# ---------------------------------------------------------------------------


class DeletionResponse(BaseModel):
    """Response to a data deletion (anonymization) request."""

    request_id: str
    subject_id: str
    status: str = Field(
        ...,
        description="PENDING | COMPLETED | REJECTED",
    )
    message: str
    anonymized_fields: list[str] = Field(
        default_factory=list,
        description="List of fields that were anonymized",
    )
    retained_fields: list[str] = Field(
        default_factory=list,
        description="Fields retained for regulatory compliance (anonymized but not deleted)",
    )
    created_at: datetime


# ---------------------------------------------------------------------------
# Data rights request tracking
# ---------------------------------------------------------------------------


class DataRightsRequestStatus(BaseModel):
    """Status of a data rights request for tracking purposes."""

    request_id: str
    request_type: str = Field(..., description="ACCESS | CORRECTION | DELETION")
    subject_id: str
    status: str
    created_at: datetime
    completed_at: datetime | None = None
    details: dict[str, Any] = Field(default_factory=dict)
