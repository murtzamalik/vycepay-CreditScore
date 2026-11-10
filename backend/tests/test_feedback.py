"""Tests for feedback / loan outcome endpoints and services (Phase 6, Tasks 6.6–6.8).

Covers:
  - Loan outcome schema validation (dates, DPD, is_default alignment)
  - Outcome label derivation
  - Deduplication by loan_id
  - National ID hashing before storage
  - Ground truth label counting
  - 409 Conflict on duplicate loan_id
  - 201 Created on success
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import ValidationError

from app.models.feedback import LoanFeedback
from app.schemas.feedback import LoanOutcomeCreate, LoanOutcomeResponse
from app.services.feedback_service import (
    LoanOutcomeFeedbackService,
    derive_loan_outcome,
)
from app.services.id_hasher import hash_national_id


# =========================================================================
# 1. Loan outcome label derivation
# =========================================================================


class TestDeriveOutcome:
    """Test derive_loan_outcome utility function."""

    def test_performing(self) -> None:
        assert derive_loan_outcome(0, False) == "performing"

    def test_delinquent_low_dpd(self) -> None:
        assert derive_loan_outcome(30, False) == "delinquent"

    def test_delinquent_near_threshold(self) -> None:
        assert derive_loan_outcome(89, False) == "delinquent"

    def test_default_at_90_dpd(self) -> None:
        assert derive_loan_outcome(90, True) == "default"

    def test_default_high_dpd(self) -> None:
        assert derive_loan_outcome(180, True) == "default"


# =========================================================================
# 2. Schema validation
# =========================================================================


class TestLoanOutcomeSchema:
    """Validate LoanOutcomeCreate Pydantic schema."""

    def test_valid_performing_loan(self) -> None:
        payload = LoanOutcomeCreate(
            loan_id="LOAN-001",
            subject_id="12345678",
            loan_amount=50000.00,
            disbursement_date=date(2025, 1, 15),
            outcome_date=date(2026, 1, 15),
            days_past_due=0,
            is_default=False,
        )
        assert payload.loan_id == "LOAN-001"
        assert payload.days_past_due == 0
        assert payload.is_default is False

    def test_valid_default_loan(self) -> None:
        payload = LoanOutcomeCreate(
            loan_id="LOAN-002",
            subject_id="87654321",
            loan_amount=100000.00,
            disbursement_date=date(2025, 1, 15),
            outcome_date=date(2026, 3, 1),
            days_past_due=120,
            is_default=True,
        )
        assert payload.is_default is True
        assert payload.days_past_due == 120

    def test_disbursement_after_outcome_rejected(self) -> None:
        """Disbursement date must be before outcome date."""
        with pytest.raises(ValidationError, match="disbursement_date must be earlier"):
            LoanOutcomeCreate(
                loan_id="LOAN-003",
                subject_id="12345678",
                loan_amount=50000.00,
                disbursement_date=date(2026, 6, 1),
                outcome_date=date(2026, 1, 1),
                days_past_due=0,
                is_default=False,
            )

    def test_same_dates_rejected(self) -> None:
        """Disbursement and outcome on same day is invalid."""
        with pytest.raises(ValidationError, match="disbursement_date must be earlier"):
            LoanOutcomeCreate(
                loan_id="LOAN-004",
                subject_id="12345678",
                loan_amount=50000.00,
                disbursement_date=date(2026, 1, 1),
                outcome_date=date(2026, 1, 1),
                days_past_due=0,
                is_default=False,
            )

    def test_dpd_90_but_not_default_rejected(self) -> None:
        """DPD >= 90 requires is_default=True."""
        with pytest.raises(ValidationError, match="is_default must be true"):
            LoanOutcomeCreate(
                loan_id="LOAN-005",
                subject_id="12345678",
                loan_amount=50000.00,
                disbursement_date=date(2025, 1, 15),
                outcome_date=date(2026, 1, 15),
                days_past_due=90,
                is_default=False,
            )

    def test_default_with_low_dpd_rejected(self) -> None:
        """is_default=True requires DPD >= 90."""
        with pytest.raises(ValidationError, match="is_default should be false"):
            LoanOutcomeCreate(
                loan_id="LOAN-006",
                subject_id="12345678",
                loan_amount=50000.00,
                disbursement_date=date(2025, 1, 15),
                outcome_date=date(2026, 1, 15),
                days_past_due=30,
                is_default=True,
            )

    def test_negative_dpd_rejected(self) -> None:
        with pytest.raises(ValidationError):
            LoanOutcomeCreate(
                loan_id="LOAN-007",
                subject_id="12345678",
                loan_amount=50000.00,
                disbursement_date=date(2025, 1, 15),
                outcome_date=date(2026, 1, 15),
                days_past_due=-1,
                is_default=False,
            )

    def test_negative_loan_amount_rejected(self) -> None:
        with pytest.raises(ValidationError):
            LoanOutcomeCreate(
                loan_id="LOAN-008",
                subject_id="12345678",
                loan_amount=-1000.00,
                disbursement_date=date(2025, 1, 15),
                outcome_date=date(2026, 1, 15),
                days_past_due=0,
                is_default=False,
            )

    def test_zero_loan_amount_rejected(self) -> None:
        with pytest.raises(ValidationError):
            LoanOutcomeCreate(
                loan_id="LOAN-009",
                subject_id="12345678",
                loan_amount=0,
                disbursement_date=date(2025, 1, 15),
                outcome_date=date(2026, 1, 15),
                days_past_due=0,
                is_default=False,
            )

    def test_invalid_loan_id_format_rejected(self) -> None:
        """Loan ID must match ^[A-Za-z0-9_\\-]+$."""
        with pytest.raises(ValidationError):
            LoanOutcomeCreate(
                loan_id="LOAN 001 with spaces!",
                subject_id="12345678",
                loan_amount=50000.00,
                disbursement_date=date(2025, 1, 15),
                outcome_date=date(2026, 1, 15),
                days_past_due=0,
                is_default=False,
            )

    def test_short_loan_id_rejected(self) -> None:
        with pytest.raises(ValidationError):
            LoanOutcomeCreate(
                loan_id="AB",
                subject_id="12345678",
                loan_amount=50000.00,
                disbursement_date=date(2025, 1, 15),
                outcome_date=date(2026, 1, 15),
                days_past_due=0,
                is_default=False,
            )

    def test_short_subject_id_rejected(self) -> None:
        with pytest.raises(ValidationError):
            LoanOutcomeCreate(
                loan_id="LOAN-010",
                subject_id="1234",
                loan_amount=50000.00,
                disbursement_date=date(2025, 1, 15),
                outcome_date=date(2026, 1, 15),
                days_past_due=0,
                is_default=False,
            )


# =========================================================================
# 3. Feedback service
# =========================================================================


class TestLoanOutcomeFeedbackService:
    """Test LoanOutcomeFeedbackService business logic."""

    def _make_payload(
        self,
        loan_id: str = "LOAN-001",
        dpd: int = 0,
        is_default: bool = False,
    ) -> LoanOutcomeCreate:
        return LoanOutcomeCreate(
            loan_id=loan_id,
            subject_id="12345678",
            loan_amount=50000.00,
            disbursement_date=date(2025, 1, 15),
            outcome_date=date(2026, 1, 15),
            days_past_due=dpd,
            is_default=is_default,
        )

    @pytest.mark.asyncio
    async def test_submit_loan_outcome_success(self) -> None:
        """Successfully submits a loan outcome and returns correct response."""
        service = LoanOutcomeFeedbackService()
        mock_db = AsyncMock()

        # No existing record (dedup check)
        mock_dedup_result = MagicMock()
        mock_dedup_result.scalar_one_or_none.return_value = None

        # Label count
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 1

        # Total labels
        mock_total_result = MagicMock()
        mock_total_result.scalar.return_value = 42

        mock_db.execute.side_effect = [
            mock_dedup_result,
            mock_count_result,
            mock_total_result,
        ]

        payload = self._make_payload()
        result = await service.submit_loan_outcome(mock_db, payload, "partner-123")

        assert isinstance(result, LoanOutcomeResponse)
        assert result.loan_id == "LOAN-001"
        assert result.national_id_hash == hash_national_id("12345678")
        assert result.loan_outcome == "performing"
        assert result.days_past_due == 0
        assert result.is_default is False
        assert result.label_count == 1

        mock_db.add.assert_called_once()
        mock_db.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_submit_default_outcome(self) -> None:
        """Submitting a default loan sets outcome to 'default'."""
        service = LoanOutcomeFeedbackService()
        mock_db = AsyncMock()

        mock_dedup_result = MagicMock()
        mock_dedup_result.scalar_one_or_none.return_value = None
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 1
        mock_total_result = MagicMock()
        mock_total_result.scalar.return_value = 5

        mock_db.execute.side_effect = [
            mock_dedup_result,
            mock_count_result,
            mock_total_result,
        ]

        payload = self._make_payload(loan_id="LOAN-DEF", dpd=120, is_default=True)
        result = await service.submit_loan_outcome(mock_db, payload, "partner-123")

        assert result.loan_outcome == "default"
        assert result.is_default is True
        assert result.days_past_due == 120

    @pytest.mark.asyncio
    async def test_submit_delinquent_outcome(self) -> None:
        """Submitting a delinquent loan sets outcome to 'delinquent'."""
        service = LoanOutcomeFeedbackService()
        mock_db = AsyncMock()

        mock_dedup_result = MagicMock()
        mock_dedup_result.scalar_one_or_none.return_value = None
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 2
        mock_total_result = MagicMock()
        mock_total_result.scalar.return_value = 10

        mock_db.execute.side_effect = [
            mock_dedup_result,
            mock_count_result,
            mock_total_result,
        ]

        payload = self._make_payload(loan_id="LOAN-DEL", dpd=45, is_default=False)
        result = await service.submit_loan_outcome(mock_db, payload, "partner-123")

        assert result.loan_outcome == "delinquent"

    @pytest.mark.asyncio
    async def test_duplicate_loan_id_raises_409(self) -> None:
        """Duplicate loan_id returns 409 Conflict."""
        from app.core.exceptions import VyceScoreError

        service = LoanOutcomeFeedbackService()
        mock_db = AsyncMock()

        # Existing record found
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = MagicMock(spec=LoanFeedback)
        mock_db.execute.return_value = mock_result

        payload = self._make_payload(loan_id="LOAN-DUP")

        with pytest.raises(VyceScoreError) as exc_info:
            await service.submit_loan_outcome(mock_db, payload, "partner-123")

        assert exc_info.value.status_code == 409
        assert exc_info.value.code == "DUPLICATE_LOAN_ID"

    @pytest.mark.asyncio
    async def test_national_id_is_hashed(self) -> None:
        """Raw national ID is never stored — only the hash."""
        service = LoanOutcomeFeedbackService()
        mock_db = AsyncMock()

        mock_dedup_result = MagicMock()
        mock_dedup_result.scalar_one_or_none.return_value = None
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 1
        mock_total_result = MagicMock()
        mock_total_result.scalar.return_value = 1

        mock_db.execute.side_effect = [
            mock_dedup_result,
            mock_count_result,
            mock_total_result,
        ]

        payload = self._make_payload()
        result = await service.submit_loan_outcome(mock_db, payload, "partner-123")

        # Verify hash is correct
        expected_hash = hash_national_id("12345678")
        assert result.national_id_hash == expected_hash
        assert len(result.national_id_hash) == 64

        # Verify the record added to DB has hashed ID
        added_record = mock_db.add.call_args[0][0]
        assert added_record.national_id_hash == expected_hash


# =========================================================================
# 4. Response schema
# =========================================================================


class TestLoanOutcomeResponseSchema:
    """Validate LoanOutcomeResponse serialization."""

    def test_response_schema(self) -> None:
        resp = LoanOutcomeResponse(
            id=str(uuid.uuid4()),
            loan_id="LOAN-001",
            national_id_hash="a" * 64,
            loan_amount=50000.00,
            disbursement_date=date(2025, 1, 15),
            outcome_date=date(2026, 1, 15),
            days_past_due=0,
            is_default=False,
            loan_outcome="performing",
            reported_at=datetime.now(timezone.utc),
            label_count=5,
        )
        data = resp.model_dump()
        assert data["loan_id"] == "LOAN-001"
        assert data["loan_outcome"] == "performing"
        assert data["label_count"] == 5
        assert data["is_default"] is False

    def test_default_response_schema(self) -> None:
        resp = LoanOutcomeResponse(
            id=str(uuid.uuid4()),
            loan_id="LOAN-002",
            national_id_hash="b" * 64,
            loan_amount=100000.00,
            disbursement_date=date(2025, 1, 15),
            outcome_date=date(2026, 3, 1),
            days_past_due=120,
            is_default=True,
            loan_outcome="default",
            reported_at=datetime.now(timezone.utc),
            label_count=10,
        )
        data = resp.model_dump()
        assert data["is_default"] is True
        assert data["days_past_due"] == 120
        assert data["loan_outcome"] == "default"


# =========================================================================
# 5. Edge cases
# =========================================================================


class TestFeedbackEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_dpd_exactly_90_with_default_true(self) -> None:
        """DPD exactly at 90 with is_default=True is valid."""
        payload = LoanOutcomeCreate(
            loan_id="LOAN-EDGE-90",
            subject_id="12345678",
            loan_amount=50000.00,
            disbursement_date=date(2025, 1, 15),
            outcome_date=date(2026, 1, 15),
            days_past_due=90,
            is_default=True,
        )
        assert payload.days_past_due == 90
        assert payload.is_default is True

    def test_dpd_89_with_default_false(self) -> None:
        """DPD at 89 with is_default=False is valid."""
        payload = LoanOutcomeCreate(
            loan_id="LOAN-EDGE-89",
            subject_id="12345678",
            loan_amount=50000.00,
            disbursement_date=date(2025, 1, 15),
            outcome_date=date(2026, 1, 15),
            days_past_due=89,
            is_default=False,
        )
        assert payload.days_past_due == 89
        assert payload.is_default is False

    def test_dpd_zero_performing(self) -> None:
        """DPD 0 with is_default=False is valid performing loan."""
        payload = LoanOutcomeCreate(
            loan_id="LOAN-PERF",
            subject_id="12345678",
            loan_amount=50000.00,
            disbursement_date=date(2025, 1, 15),
            outcome_date=date(2026, 1, 15),
            days_past_due=0,
            is_default=False,
        )
        assert payload.days_past_due == 0

    def test_loan_id_with_hyphens_underscores(self) -> None:
        """Loan IDs with hyphens and underscores are valid."""
        payload = LoanOutcomeCreate(
            loan_id="LOAN_REF-2026-001",
            subject_id="12345678",
            loan_amount=50000.00,
            disbursement_date=date(2025, 1, 15),
            outcome_date=date(2026, 1, 15),
            days_past_due=0,
            is_default=False,
        )
        assert payload.loan_id == "LOAN_REF-2026-001"

    def test_very_large_loan_amount(self) -> None:
        """Large loan amounts are accepted."""
        payload = LoanOutcomeCreate(
            loan_id="LOAN-BIG",
            subject_id="12345678",
            loan_amount=999999999.99,
            disbursement_date=date(2025, 1, 15),
            outcome_date=date(2026, 1, 15),
            days_past_due=0,
            is_default=False,
        )
        assert payload.loan_amount == 999999999.99
