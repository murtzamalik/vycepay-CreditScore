"""Data Subject Rights endpoints — Kenya DPA 2019 compliance (Phase 12.5).

Routes:
  GET  /v1/data-rights/access/{subjectId}   — Right of Access
  POST /v1/data-rights/correction            — Right of Rectification
  POST /v1/data-rights/deletion/{subjectId}  — Right to Erasure (anonymization)
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.core.security import get_current_user
from app.database import get_db
from app.models.user import User
from app.schemas.common import ErrorResponse
from app.schemas.data_rights import (
    CorrectionRequest,
    CorrectionResponse,
    DeletionResponse,
    SubjectDataResponse,
)
from app.services.data_rights_service import DataRightsService

logger = get_logger("data_rights_endpoints")
router = APIRouter(prefix="/data-rights", tags=["Data Subject Rights (DPA 2019)"])


@router.get(
    "/access/{subject_id}",
    response_model=SubjectDataResponse,
    status_code=status.HTTP_200_OK,
    summary="Right of Access — retrieve all data held about a subject",
    responses={
        404: {"model": ErrorResponse, "description": "Subject not found"},
        401: {"model": ErrorResponse, "description": "Authentication required"},
    },
)
async def access_subject_data(
    subject_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SubjectDataResponse:
    """Retrieve all data held about a subject per Kenya DPA 2019 Article 26.

    Returns identity data, scores, features, API activity counts,
    processing purposes, and retention policy information.
    """
    try:
        return await DataRightsService.get_subject_data(db, subject_id)
    except ValueError as exc:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": str(exc), "details": {}}},
        ) from exc


@router.post(
    "/correction",
    response_model=CorrectionResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Right of Rectification — request data correction",
    responses={
        400: {"model": ErrorResponse, "description": "Invalid correction request"},
        404: {"model": ErrorResponse, "description": "Subject not found"},
        401: {"model": ErrorResponse, "description": "Authentication required"},
    },
)
async def request_correction(
    body: CorrectionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CorrectionResponse:
    """Request correction of data held about a subject per Kenya DPA 2019 Article 27.

    Corrections are placed in PENDING status and require admin review.
    Response is due within 30 days per DPA 2019 requirements.
    """
    try:
        return await DataRightsService.request_correction(db, body)
    except ValueError as exc:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "INVALID_REQUEST", "message": str(exc), "details": {}}},
        ) from exc


@router.post(
    "/deletion/{subject_id}",
    response_model=DeletionResponse,
    status_code=status.HTTP_200_OK,
    summary="Right to Erasure — request data deletion (anonymization)",
    responses={
        404: {"model": ErrorResponse, "description": "Subject not found"},
        401: {"model": ErrorResponse, "description": "Authentication required"},
    },
)
async def request_deletion(
    subject_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DeletionResponse:
    """Request deletion (anonymization) of a subject's data per Kenya DPA 2019 Article 28.

    Due to CBK regulatory requirements, financial data is anonymized
    rather than physically deleted. The subject's identity hash is
    replaced, effectively de-linking their PII from all stored records.
    """
    try:
        return await DataRightsService.request_deletion(db, subject_id)
    except ValueError as exc:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": str(exc), "details": {}}},
        ) from exc
