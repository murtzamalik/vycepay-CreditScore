"""Feedback request/response schemas for loan outcome reporting (Phase 6)."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field, model_validator


# ---------------------------------------------------------------------------
# Legacy schemas (kept for backward compatibility)
# ---------------------------------------------------------------------------


class FeedbackCreate(BaseModel):
    """Legacy payload submitted by partner banks with loan outcome data."""

    national_id: str = Field(..., min_length=5, max_length=20)
    loan_outcome: str = Field(..., pattern=r"^(performing|default|restructured|written_off)$")
    dpd: int = Field(..., ge=0, description="Days past due")
    partner_id: str = Field(..., min_length=1, max_length=64)


class FeedbackResponse(BaseModel):
    """Legacy acknowledgement returned after feedback submission."""

    id: str
    national_id_hash: str
    loan_outcome: str
    dpd: int
    partner_id: str
    reported_at: datetime


# ---------------------------------------------------------------------------
# Phase 6 — POST /v1/feedback/loan-outcome schemas
# ---------------------------------------------------------------------------


class LoanOutcomeCreate(BaseModel):
    """Loan outcome submission from partner banks (BRD feedback loop).

    Attributes:
        loan_id: Unique loan reference from the partner bank.
        subject_id: National ID of the borrower (will be hashed before storage).
        loan_amount: Loan disbursement amount in KES.
        disbursement_date: Date the loan was disbursed.
        outcome_date: Date of the outcome observation.
        days_past_due: Number of days past the due date (>= 0).
        is_default: Whether the loan is classified as defaulted.
    """

    loan_id: str = Field(
        ...,
        min_length=3,
        max_length=100,
        pattern=r"^[A-Za-z0-9_\-]+$",
        description="Unique loan reference from the partner bank",
    )
    subject_id: str = Field(
        ...,
        min_length=5,
        max_length=20,
        description="National ID of the borrower",
    )
    loan_amount: float = Field(
        ...,
        gt=0,
        description="Loan disbursement amount in KES",
    )
    disbursement_date: date = Field(
        ...,
        description="Date the loan was disbursed",
    )
    outcome_date: date = Field(
        ...,
        description="Date of the outcome observation",
    )
    days_past_due: int = Field(
        ...,
        ge=0,
        description="Number of days past the due date",
    )
    is_default: bool = Field(
        ...,
        description="Whether the loan is classified as defaulted (true if DPD >= 90)",
    )

    @model_validator(mode="after")
    def validate_dates_and_default(self) -> LoanOutcomeCreate:
        """Validate business rules for loan outcome data."""
        # Disbursement must be before outcome
        if self.disbursement_date >= self.outcome_date:
            raise ValueError(
                "disbursement_date must be earlier than outcome_date"
            )

        # is_default must align with DPD >= 90
        if self.days_past_due >= 90 and not self.is_default:
            raise ValueError(
                "is_default must be true when days_past_due >= 90"
            )
        if self.is_default and self.days_past_due < 90:
            raise ValueError(
                "is_default should be false when days_past_due < 90; "
                "default classification requires DPD >= 90"
            )

        return self


class LoanOutcomeResponse(BaseModel):
    """Acknowledgement returned after loan outcome submission."""

    id: str = Field(..., description="Unique feedback record ID")
    loan_id: str = Field(..., description="Partner bank loan reference")
    national_id_hash: str = Field(..., description="SHA-256 hash of borrower national ID")
    loan_amount: float
    disbursement_date: date
    outcome_date: date
    days_past_due: int
    is_default: bool
    loan_outcome: str = Field(
        ..., description="Derived outcome label: performing, default, or delinquent"
    )
    reported_at: datetime
    label_count: int = Field(
        ..., ge=0, description="Total ground truth labels collected for this subject"
    )
