"""Batch scoring endpoints (Phase 6 — Tasks 6.1–6.5).

Endpoints:
  POST /v1/batches           — Submit a batch scoring job
  GET  /v1/batches/{batchId} — Get batch job status
  GET  /v1/batches/{batchId}/results — Download batch results
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, Query, UploadFile
from fastapi.responses import FileResponse
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ForbiddenError, VyceScoreError
from app.core.security import get_current_customer
from app.dependencies import get_db, get_redis
from app.models.batch_job import BatchApiTier, BatchJobStatus
from app.models.customer import Customer, LicenseTier
from app.schemas.batches import (
    BatchApiTierParam,
    BatchJobResponse,
    BatchJobStatusResponse,
)
from app.services.batch_service import (
    BatchService,
    MAX_FILE_SIZE,
    parse_national_ids_from_csv,
    parse_national_ids_from_json,
)

router = APIRouter(prefix="/batches", tags=["batches"])


def _get_batch_service() -> BatchService:
    return BatchService()


def _require_batch_tier():
    """Dependency that requires Pro or Deep Dive license for batch jobs."""

    async def checker(
        customer: Customer = Depends(get_current_customer),
    ) -> Customer:
        allowed = {LicenseTier.PRO.value, LicenseTier.DEEP_DIVE.value}
        if customer.license_tier.value not in allowed:
            raise ForbiddenError(
                "License tier insufficient for batch processing. "
                f"Required: PRO or DEEP_DIVE; current: {customer.license_tier.value}"
            )
        return customer

    return checker


# ---------------------------------------------------------------------------
# POST /v1/batches — Submit batch job (Task 6.1)
# ---------------------------------------------------------------------------


@router.post("", response_model=BatchJobResponse, status_code=202)
async def submit_batch_job(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="CSV or JSON file with national IDs"),
    api_tier: BatchApiTierParam = Form(
        default=BatchApiTierParam.lite,
        description="Scoring tier: lite, pro, or custom",
    ),
    webhook_url: str | None = Form(
        default=None,
        description="Webhook URL for completion notification",
    ),
    customer: Customer = Depends(_require_batch_tier()),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    service: BatchService = Depends(_get_batch_service),
) -> BatchJobResponse:
    """Submit a batch scoring job with a CSV or JSON file of national IDs.

    Accepts file upload (max 10MB) and returns 202 Accepted with a job ID.
    The batch is processed asynchronously in the background.

    **Auth**: API key, Pro or Deep Dive license required.
    """
    # 1. Validate file type
    filename = (file.filename or "").lower()
    if not filename.endswith((".csv", ".json")):
        raise VyceScoreError(
            code="INVALID_FILE_FORMAT",
            message="File must be CSV (.csv) or JSON (.json)",
            status_code=400,
            details={"filename": file.filename},
        )

    # 2. Read and validate file size
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise VyceScoreError(
            code="FILE_TOO_LARGE",
            message=f"File exceeds maximum size of {MAX_FILE_SIZE // (1024 * 1024)}MB",
            status_code=400,
            details={"size_bytes": len(content), "max_bytes": MAX_FILE_SIZE},
        )

    if len(content) == 0:
        raise VyceScoreError(
            code="EMPTY_FILE",
            message="Uploaded file is empty",
            status_code=400,
        )

    # 3. Parse national IDs
    file_format = "csv" if filename.endswith(".csv") else "json"
    if file_format == "csv":
        national_ids = parse_national_ids_from_csv(content)
    else:
        national_ids = parse_national_ids_from_json(content)

    if not national_ids:
        raise VyceScoreError(
            code="NO_RECORDS",
            message="No valid national IDs found in the uploaded file",
            status_code=400,
        )

    # 4. Map tier
    tier_map = {
        BatchApiTierParam.lite: BatchApiTier.LITE,
        BatchApiTierParam.pro: BatchApiTier.PRO,
        BatchApiTierParam.custom: BatchApiTier.CUSTOM,
    }
    batch_tier = tier_map[api_tier]

    # 5. Create batch job
    job = await service.create_batch_job(
        db=db,
        customer_id=customer.customer_id,
        national_ids=national_ids,
        file_format=file_format,
        api_tier=batch_tier,
        webhook_url=webhook_url,
    )

    # 6. Schedule background processing
    background_tasks.add_task(service.process_batch_job, job.job_id, redis)

    return BatchJobResponse(
        job_id=str(job.job_id),
        status=job.status.value,
        total_records=job.total_records,
        message=f"Batch job queued with {job.total_records} records",
    )


# ---------------------------------------------------------------------------
# GET /v1/batches/{batchId} — Get batch status (Task 6.2)
# ---------------------------------------------------------------------------


@router.get("/{batch_id}", response_model=BatchJobStatusResponse)
async def get_batch_status(
    batch_id: uuid.UUID,
    customer: Customer = Depends(get_current_customer),
    db: AsyncSession = Depends(get_db),
    service: BatchService = Depends(_get_batch_service),
) -> BatchJobStatusResponse:
    """Get the status and progress of a batch scoring job.

    **Auth**: API key, must be the owner of the batch job.
    """
    job = await service.get_batch_job(db, batch_id, customer.customer_id)

    total = max(job.total_records, 1)
    progress = round((job.processed_records + job.failed_records) / total * 100, 1)

    download_url: str | None = None
    if job.status == BatchJobStatus.COMPLETED and job.result_file_path:
        download_url = f"/v1/batches/{job.job_id}/results"

    return BatchJobStatusResponse(
        job_id=str(job.job_id),
        status=job.status.value,
        api_tier=job.api_tier.value,
        total_records=job.total_records,
        processed_records=job.processed_records,
        failed_records=job.failed_records,
        progress_percent=min(progress, 100.0),
        result_download_url=download_url,
        error_message=job.error_message,
        created_at=job.created_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
    )


# ---------------------------------------------------------------------------
# GET /v1/batches/{batchId}/results — Download results (Task 6.4)
# ---------------------------------------------------------------------------


@router.get("/{batch_id}/results")
async def download_batch_results(
    batch_id: uuid.UUID,
    customer: Customer = Depends(get_current_customer),
    db: AsyncSession = Depends(get_db),
    service: BatchService = Depends(_get_batch_service),
) -> FileResponse:
    """Download the results file for a completed batch job.

    Returns a CSV or JSON file with score results for each record.

    **Auth**: API key, must be the owner of the batch job.
    """
    job = await service.get_batch_job(db, batch_id, customer.customer_id)

    if job.status != BatchJobStatus.COMPLETED:
        raise VyceScoreError(
            code="BATCH_NOT_COMPLETED",
            message=f"Batch job is not completed yet. Current status: {job.status.value}",
            status_code=400,
            details={"status": job.status.value},
        )

    result_path = service.get_result_file_path(job)
    if result_path is None:
        raise VyceScoreError(
            code="RESULTS_NOT_FOUND",
            message="Result file not found",
            status_code=404,
        )

    media_type = "text/csv" if job.file_format == "csv" else "application/json"
    filename = f"batch_{batch_id}_results.{job.file_format}"

    return FileResponse(
        path=str(result_path),
        media_type=media_type,
        filename=filename,
    )
