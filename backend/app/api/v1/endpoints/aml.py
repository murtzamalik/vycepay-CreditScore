"""AML screening endpoints (BRD §5.3, Phase 15.2).

POST /v1/compliance/aml/screen  — trigger AML screening
GET  /v1/compliance/aml/status/{subjectId} — get AML status
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, status
from sqlalchemy import select

from app.core.exceptions import NotFoundError
from app.dependencies import DbSessionDep
from app.models.subject import Subject
from app.schemas.aml import (
    AMLScreeningRequest,
    AMLScreeningResponse,
    AMLStatusResponse,
)
from app.services.compliance_service import ComplianceService
from app.services.id_hasher import hash_national_id

router = APIRouter(prefix="/compliance/aml", tags=["compliance"])


@router.post(
    "/screen",
    response_model=AMLScreeningResponse,
    status_code=status.HTTP_200_OK,
    summary="Trigger AML screening for a subject",
    description=(
        "Initiates AML screening via ComplyAdvantage. Checks against "
        "sanctions lists, PEP databases, and adverse media sources."
    ),
)
async def screen_aml(
    request: AMLScreeningRequest,
    db: DbSessionDep,
) -> AMLScreeningResponse:
    """Trigger AML screening for a subject."""
    id_hash = hash_national_id(request.national_id)

    # Find or fail on subject
    result = await db.execute(
        select(Subject).where(Subject.id_hash == id_hash)
    )
    subject = result.scalar_one_or_none()
    if subject is None:
        raise NotFoundError("Subject", id_hash[:12] + "...")

    # Run AML check
    service = ComplianceService()
    aml_result = await service.run_aml_check(
        db=db,
        subject=subject,
        name=request.name,
        national_id=request.national_id,
        date_of_birth=request.date_of_birth,
        nationality=request.nationality,
    )

    return AMLScreeningResponse(
        subject_id=id_hash,
        status=aml_result.status,
        risk_rating=aml_result.risk_rating,
        risk_score=aml_result.risk_score,
        is_sanctioned=aml_result.is_sanctioned,
        is_pep=aml_result.is_pep,
        adverse_media_found=aml_result.adverse_media_found,
        match_count=len(aml_result.matches),
        provider_reference=aml_result.provider_reference,
        screened_at=aml_result.screened_at,
    )


@router.get(
    "/status/{subject_id}",
    response_model=AMLStatusResponse,
    summary="Get AML screening status for a subject",
)
async def get_aml_status(
    subject_id: uuid.UUID,
    db: DbSessionDep,
) -> AMLStatusResponse:
    """Get the current AML screening status for a subject."""
    result = await db.execute(
        select(Subject).where(Subject.subject_id == subject_id)
    )
    subject = result.scalar_one_or_none()
    if subject is None:
        raise NotFoundError("Subject", str(subject_id))

    # Get latest AML check details
    service = ComplianceService()
    latest_check = await service.get_latest_aml_check(db, subject.subject_id)

    return AMLStatusResponse(
        subject_id=subject.id_hash,
        aml_status=subject.aml_status.value,
        risk_rating=None,
        risk_score=latest_check.risk_score if latest_check else None,
        is_sanctioned=None,
        is_pep=None,
        last_screened_at=latest_check.checked_at if latest_check else None,
        last_check_provider=latest_check.provider if latest_check else None,
    )
