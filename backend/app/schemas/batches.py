"""Batch job request/response schemas."""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field, HttpUrl


class BatchApiTierParam(str, Enum):
    """API tier for batch scoring."""

    lite = "lite"
    pro = "pro"
    custom = "custom"


class BatchJobStatusEnum(str, Enum):
    """Batch job lifecycle status."""

    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------


class BatchSubmitParams(BaseModel):
    """Query/form parameters for batch submission."""

    api_tier: BatchApiTierParam = Field(
        default=BatchApiTierParam.lite,
        description="Scoring tier to use: lite, pro, or custom",
    )
    webhook_url: str | None = Field(
        default=None,
        max_length=2048,
        description="Webhook URL to POST completion notification to",
    )


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class BatchJobResponse(BaseModel):
    """Response returned when a batch job is submitted (202 Accepted)."""

    job_id: str = Field(..., description="Unique batch job identifier")
    status: BatchJobStatusEnum = Field(..., description="Current job status")
    total_records: int = Field(..., ge=0, description="Total records in the batch")
    message: str = Field(..., description="Human-readable status message")


class BatchJobStatusResponse(BaseModel):
    """Response for GET /v1/batches/{batchId}."""

    job_id: str = Field(..., description="Unique batch job identifier")
    status: BatchJobStatusEnum = Field(..., description="Current job status")
    api_tier: str = Field(..., description="Scoring tier used")
    total_records: int = Field(..., ge=0)
    processed_records: int = Field(..., ge=0)
    failed_records: int = Field(..., ge=0)
    progress_percent: float = Field(
        ..., ge=0.0, le=100.0, description="Processing progress percentage"
    )
    result_download_url: str | None = Field(
        None, description="URL to download results (available when COMPLETED)"
    )
    error_message: str | None = Field(
        None, description="Error details if job FAILED"
    )
    created_at: datetime = Field(..., description="Job submission time")
    started_at: datetime | None = Field(None, description="Processing start time")
    completed_at: datetime | None = Field(None, description="Processing end time")


class BatchResultRecord(BaseModel):
    """A single record in the batch result output."""

    national_id_hash: str = Field(..., description="SHA-256 hash of the national ID")
    vyce_score: int | None = Field(None, ge=300, le=900)
    niq_score: int | None = Field(None, ge=0, le=100)
    score_date: str | None = Field(None)
    model_version: str | None = Field(None)
    status: str = Field(..., description="success or error")
    error_message: str | None = Field(None)
