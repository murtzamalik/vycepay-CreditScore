"""KYC verification endpoints (BRD §5.3, Phase 15.1).

POST /v1/compliance/kyc/verify  — trigger KYC verification
GET  /v1/compliance/kyc/status/{subjectId} — get KYC status
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, status
from sqlalchemy import select

from app.core.exceptions import NotFoundError
from app.dependencies import DbSessionDep
from app.models.subject import Subject
from app.schemas.kyc import (
    KYCStatusResponse,
    KYCVerificationRequest,
    KYCVerificationResponse,
)
from app.services.compliance_service import ComplianceService
from app.services.id_hasher import hash_national_id

router = APIRouter(prefix="/compliance/kyc", tags=["compliance"])


@router.post(
    "/verify",
    response_model=KYCVerificationResponse,
    status_code=status.HTTP_200_OK,
    summary="Trigger KYC verification for a subject",
    description=(
        "Initiates KYC verification via Smile ID. Performs identity document "
        "verification and optional biometric face match with liveness check."
    ),
)
async def verify_kyc(
    request: KYCVerificationRequest,
    db: DbSessionDep,
) -> KYCVerificationResponse:
    """Trigger KYC verification for a subject."""
    id_hash = hash_national_id(request.national_id)

    # Find or fail on subject
    result = await db.execute(
        select(Subject).where(Subject.id_hash == id_hash)
    )
    subject = result.scalar_one_or_none()
    if subject is None:
        raise NotFoundError("Subject", id_hash[:12] + "...")

    # Run KYC check
    service = ComplianceService()
    kyc_result = await service.run_kyc_check(
        db=db,
        subject=subject,
        national_id=request.national_id,
        id_type=request.id_type,
        biometric_data=request.biometric_data,
        first_name=request.first_name,
        last_name=request.last_name,
        country=request.country,
    )

    return KYCVerificationResponse(
        subject_id=id_hash,
        status=kyc_result.status,
        confidence_score=kyc_result.confidence_score,
        face_match_score=kyc_result.face_match_score,
        liveness_passed=kyc_result.liveness_passed,
        provider_reference=kyc_result.provider_reference,
        verified_at=kyc_result.verified_at,
        failure_reason=kyc_result.failure_reason,
    )


@router.get(
    "/status/{subject_id}",
    response_model=KYCStatusResponse,
    summary="Get KYC verification status for a subject",
)
async def get_kyc_status(
    subject_id: uuid.UUID,
    db: DbSessionDep,
) -> KYCStatusResponse:
    """Get the current KYC verification status for a subject."""
    result = await db.execute(
        select(Subject).where(Subject.subject_id == subject_id)
    )
    subject = result.scalar_one_or_none()
    if subject is None:
        raise NotFoundError("Subject", str(subject_id))

    # Get latest KYC check details
    service = ComplianceService()
    latest_check = await service.get_latest_kyc_check(db, subject.subject_id)

    return KYCStatusResponse(
        subject_id=subject.id_hash,
        kyc_status=subject.kyc_status.value,
        last_verified_at=latest_check.checked_at if latest_check else None,
        last_check_provider=latest_check.provider if latest_check else None,
        confidence_score=latest_check.confidence_score if latest_check else None,
    )
