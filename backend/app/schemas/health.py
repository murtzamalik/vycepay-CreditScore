"""Health check response schema."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Response model for the health-check endpoint."""

    status: str = Field(default="healthy", examples=["healthy"])
    version: str = Field(examples=["0.1.0"])
    timestamp: datetime = Field(
        description="Server timestamp in ISO 8601 format",
        examples=["2026-01-15T12:00:00Z"],
    )
