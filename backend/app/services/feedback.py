"""Feedback service for partner bank loan outcome submissions."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from app.core.security import hash_national_id
from app.schemas.feedback import FeedbackCreate, FeedbackResponse


class FeedbackService:
    """Loan feedback operations (stub implementation)."""

    async def submit_feedback(self, payload: FeedbackCreate) -> FeedbackResponse:
        """Record loan outcome feedback from a partner bank.

        In production this persists to the database and may trigger a
        retraining evaluation.  The stub simply echoes back the data.
        """
        return FeedbackResponse(
            id=str(uuid.uuid4()),
            national_id_hash=hash_national_id(payload.national_id),
            loan_outcome=payload.loan_outcome,
            dpd=payload.dpd,
            partner_id=payload.partner_id,
            reported_at=datetime.now(timezone.utc),
        )
