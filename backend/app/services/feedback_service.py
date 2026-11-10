"""Feedback service — loan outcome ingestion and ground truth labeling (Phase 6).

Handles validation, deduplication, national ID hashing, and storage of
loan outcome data submitted by partner banks via POST /v1/feedback/loan-outcome.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import VyceScoreError
from app.models.feedback import LoanFeedback
from app.schemas.feedback import LoanOutcomeCreate, LoanOutcomeResponse
from app.services.id_hasher import hash_national_id

logger = structlog.get_logger(__name__)

# Retraining trigger threshold — number of new ground truth labels
RETRAIN_TRIGGER_THRESHOLD = 1000


def derive_loan_outcome(days_past_due: int, is_default: bool) -> str:
    """Derive a categorical outcome label from DPD and default flag.

    Categories:
        - ``"performing"``: DPD == 0
        - ``"delinquent"``: 1 <= DPD < 90
        - ``"default"``: DPD >= 90 and is_default is True
    """
    if is_default and days_past_due >= 90:
        return "default"
    if days_past_due > 0:
        return "delinquent"
    return "performing"


class LoanOutcomeFeedbackService:
    """Business logic for loan outcome feedback submissions."""

    async def submit_loan_outcome(
        self,
        db: AsyncSession,
        payload: LoanOutcomeCreate,
        partner_id: str,
    ) -> LoanOutcomeResponse:
        """Validate, deduplicate, and store a loan outcome record.

        Args:
            db: Async database session.
            payload: Validated loan outcome data.
            partner_id: Identifier of the partner bank (from customer record).

        Returns:
            LoanOutcomeResponse with the created record details.

        Raises:
            VyceScoreError 409: If a record with the same loan_id already exists.
        """
        # 1. Dedup by loan_id
        existing = await db.execute(
            select(LoanFeedback).where(LoanFeedback.loan_id == payload.loan_id)
        )
        if existing.scalar_one_or_none() is not None:
            raise VyceScoreError(
                code="DUPLICATE_LOAN_ID",
                message=f"Loan outcome for loan_id '{payload.loan_id}' already exists",
                status_code=409,
                details={"loan_id": payload.loan_id},
            )

        # 2. Hash national ID
        id_hash = hash_national_id(payload.subject_id)

        # 3. Derive outcome label
        outcome = derive_loan_outcome(payload.days_past_due, payload.is_default)

        # 4. Create feedback record
        now = datetime.now(timezone.utc)
        record = LoanFeedback(
            id=uuid.uuid4(),
            loan_id=payload.loan_id,
            national_id_hash=id_hash,
            loan_outcome=outcome,
            dpd=payload.days_past_due,
            is_default=payload.is_default,
            loan_amount=payload.loan_amount,
            disbursement_date=payload.disbursement_date,
            outcome_date=payload.outcome_date,
            partner_id=partner_id,
            reported_at=now,
        )
        db.add(record)
        await db.flush()

        # 5. Count total labels for this subject (ground truth tracking)
        label_count_result = await db.execute(
            select(func.count(LoanFeedback.id)).where(
                LoanFeedback.national_id_hash == id_hash
            )
        )
        label_count = label_count_result.scalar() or 0

        # 6. Log for retraining evaluation
        await logger.ainfo(
            "loan_outcome_recorded",
            loan_id=payload.loan_id,
            national_id_hash=id_hash,
            outcome=outcome,
            dpd=payload.days_past_due,
            label_count=label_count,
        )

        # 7. Check retraining trigger threshold
        total_labels_result = await db.execute(
            select(func.count(LoanFeedback.id))
        )
        total_labels = total_labels_result.scalar() or 0
        if total_labels % RETRAIN_TRIGGER_THRESHOLD == 0 and total_labels > 0:
            await logger.ainfo(
                "retrain_trigger_threshold_reached",
                total_labels=total_labels,
                threshold=RETRAIN_TRIGGER_THRESHOLD,
            )

        return LoanOutcomeResponse(
            id=str(record.id),
            loan_id=payload.loan_id,
            national_id_hash=id_hash,
            loan_amount=payload.loan_amount,
            disbursement_date=payload.disbursement_date,
            outcome_date=payload.outcome_date,
            days_past_due=payload.days_past_due,
            is_default=payload.is_default,
            loan_outcome=outcome,
            reported_at=now,
            label_count=label_count,
        )
