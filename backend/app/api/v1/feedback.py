"""Feedback endpoint for partner bank loan outcome reporting."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.security import require_api_key
from app.schemas.feedback import FeedbackCreate, FeedbackResponse
from app.services.feedback import FeedbackService

router = APIRouter(prefix="/feedback", tags=["feedback"])


def get_feedback_service() -> FeedbackService:
    return FeedbackService()


@router.post("", response_model=FeedbackResponse, status_code=201)
async def submit_feedback(
    body: FeedbackCreate,
    _api_key: str = Depends(require_api_key),
    service: FeedbackService = Depends(get_feedback_service),
) -> FeedbackResponse:
    """Submit loan outcome feedback from a partner bank."""
    return await service.submit_feedback(body)
