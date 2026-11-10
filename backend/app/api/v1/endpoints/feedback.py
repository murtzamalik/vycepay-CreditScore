"""Feedback endpoints for partner bank loan outcome reporting (Phase 6).

Endpoints:
  POST /v1/feedback              — Legacy loan feedback (backward compat)
  POST /v1/feedback/loan-outcome — Submit loan outcome data (Task 6.6)
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_customer, require_api_key
from app.dependencies import get_db
from app.models.customer import Customer
from app.schemas.feedback import (
    FeedbackCreate,
    FeedbackResponse,
    LoanOutcomeCreate,
    LoanOutcomeResponse,
)
from app.services.feedback import FeedbackService
from app.services.feedback_service import LoanOutcomeFeedbackService

router = APIRouter(prefix="/feedback", tags=["feedback"])


def _get_legacy_feedback_service() -> FeedbackService:
    return FeedbackService()


def _get_feedback_service() -> LoanOutcomeFeedbackService:
    return LoanOutcomeFeedbackService()


# ---------------------------------------------------------------------------
# POST /v1/feedback/loan-outcome — Submit loan outcome (Task 6.6)
# ---------------------------------------------------------------------------


@router.post(
    "/loan-outcome",
    response_model=LoanOutcomeResponse,
    status_code=201,
    summary="Submit loan outcome feedback",
    description=(
        "Submit loan outcome data from a partner bank for ground truth "
        "labeling. The national ID is hashed before storage. Duplicate "
        "loan IDs return 409 Conflict."
    ),
)
async def submit_loan_outcome(
    body: LoanOutcomeCreate,
    customer: Customer = Depends(get_current_customer),
    db: AsyncSession = Depends(get_db),
    service: LoanOutcomeFeedbackService = Depends(_get_feedback_service),
) -> LoanOutcomeResponse:
    """Submit loan outcome feedback from a partner bank.

    **Auth**: API key (Partner Integration tier).
    **Rate limit**: Unlimited.
    """
    return await service.submit_loan_outcome(
        db=db,
        payload=body,
        partner_id=str(customer.customer_id),
    )


# ---------------------------------------------------------------------------
# POST /v1/feedback — Legacy feedback endpoint (backward compat)
# ---------------------------------------------------------------------------


@router.post("", response_model=FeedbackResponse, status_code=201)
async def submit_feedback(
    body: FeedbackCreate,
    _api_key: str = Depends(require_api_key),
    service: FeedbackService = Depends(_get_legacy_feedback_service),
) -> FeedbackResponse:
    """Submit loan outcome feedback from a partner bank (legacy endpoint)."""
    return await service.submit_feedback(body)
