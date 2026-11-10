"""Batch processing service — handles file parsing, scoring, and result generation.

Processes batch scoring jobs asynchronously in chunks. Each record is scored
independently so individual failures do not fail the entire batch.
"""

from __future__ import annotations

import csv
import io
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import structlog
from redis.asyncio import Redis
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.exceptions import NotFoundError, ForbiddenError, VyceScoreError
from app.database import async_session_factory
from app.models.batch_job import BatchApiTier, BatchJob, BatchJobStatus
from app.services.id_hasher import hash_national_id
from app.services.scoring import ScoringService

logger = structlog.get_logger(__name__)
settings = get_settings()

# Directory for batch result files
BATCH_RESULTS_DIR = Path("batch_results")
BATCH_RESULTS_DIR.mkdir(parents=True, exist_ok=True)

CHUNK_SIZE = 100
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
WEBHOOK_MAX_RETRIES = 3


def parse_national_ids_from_csv(content: bytes) -> list[str]:
    """Parse national IDs from a CSV file.

    Expects a header row with a column named 'national_id' (case-insensitive).
    Falls back to first column if no matching header is found.
    """
    text = content.decode("utf-8-sig")
    reader = csv.reader(io.StringIO(text))

    rows = list(reader)
    if not rows:
        raise VyceScoreError(
            code="INVALID_FILE",
            message="CSV file is empty",
            status_code=400,
        )

    header = [col.strip().lower() for col in rows[0]]
    col_idx = 0
    if "national_id" in header:
        col_idx = header.index("national_id")
    elif "nationalid" in header:
        col_idx = header.index("nationalid")
    elif "id" in header:
        col_idx = header.index("id")

    national_ids: list[str] = []
    for row in rows[1:]:
        if row and len(row) > col_idx:
            nid = row[col_idx].strip()
            if nid:
                national_ids.append(nid)

    return national_ids


def parse_national_ids_from_json(content: bytes) -> list[str]:
    """Parse national IDs from a JSON file.

    Accepts either:
      - A JSON array of strings: ["id1", "id2", ...]
      - A JSON object with a "national_ids" key: {"national_ids": ["id1", ...]}
    """
    try:
        data = json.loads(content.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise VyceScoreError(
            code="INVALID_FILE",
            message=f"Invalid JSON: {exc}",
            status_code=400,
        ) from exc

    if isinstance(data, list):
        return [str(item).strip() for item in data if item]

    if isinstance(data, dict):
        ids = data.get("national_ids") or data.get("nationalIds") or data.get("ids")
        if ids and isinstance(ids, list):
            return [str(item).strip() for item in ids if item]

    raise VyceScoreError(
        code="INVALID_FILE",
        message="JSON must be an array of IDs or an object with a 'national_ids' key",
        status_code=400,
    )


class BatchService:
    """Orchestrates batch job creation, processing, and result generation."""

    def __init__(self) -> None:
        self._scoring = ScoringService()

    async def create_batch_job(
        self,
        db: AsyncSession,
        customer_id: uuid.UUID,
        national_ids: list[str],
        file_format: str,
        api_tier: BatchApiTier,
        webhook_url: str | None = None,
    ) -> BatchJob:
        """Create a new batch job record in QUEUED status."""
        job = BatchJob(
            job_id=uuid.uuid4(),
            customer_id=customer_id,
            status=BatchJobStatus.QUEUED,
            api_tier=api_tier,
            total_records=len(national_ids),
            processed_records=0,
            failed_records=0,
            file_format=file_format,
            webhook_url=webhook_url,
        )
        db.add(job)
        await db.flush()

        # Store the national IDs temporarily for the background processor
        # Using a simple JSON file keyed by job_id
        ids_file = BATCH_RESULTS_DIR / f"{job.job_id}_input.json"
        ids_file.write_text(json.dumps(national_ids), encoding="utf-8")

        await logger.ainfo(
            "batch_job_created",
            job_id=str(job.job_id),
            total_records=len(national_ids),
            api_tier=api_tier.value,
        )
        return job

    async def get_batch_job(
        self,
        db: AsyncSession,
        job_id: uuid.UUID,
        customer_id: uuid.UUID,
    ) -> BatchJob:
        """Retrieve a batch job, ensuring the caller owns it."""
        result = await db.execute(
            select(BatchJob).where(BatchJob.job_id == job_id)
        )
        job = result.scalar_one_or_none()

        if job is None:
            raise NotFoundError("BatchJob", str(job_id))

        if job.customer_id != customer_id:
            raise ForbiddenError("You do not own this batch job")

        return job

    async def process_batch_job(
        self,
        job_id: uuid.UUID,
        redis: Redis,
    ) -> None:
        """Process a batch job in chunks. Runs as a background task.

        Uses its own database session since the request session will be closed.
        """
        async with async_session_factory() as db:
            try:
                await self._do_process(db, job_id, redis)
            except Exception as exc:
                await logger.aerror(
                    "batch_job_failed",
                    job_id=str(job_id),
                    error=str(exc),
                )
                await db.execute(
                    update(BatchJob)
                    .where(BatchJob.job_id == job_id)
                    .values(
                        status=BatchJobStatus.FAILED,
                        error_message=str(exc)[:2000],
                        completed_at=datetime.now(timezone.utc),
                    )
                )
                await db.commit()

                # Attempt webhook notification even on failure
                result = await db.execute(
                    select(BatchJob).where(BatchJob.job_id == job_id)
                )
                job = result.scalar_one_or_none()
                if job and job.webhook_url:
                    await self._send_webhook(job)

    async def _do_process(
        self,
        db: AsyncSession,
        job_id: uuid.UUID,
        redis: Redis,
    ) -> None:
        """Core processing logic for a batch job."""
        # Load input IDs
        ids_file = BATCH_RESULTS_DIR / f"{job_id}_input.json"
        if not ids_file.exists():
            raise VyceScoreError(
                code="BATCH_INPUT_MISSING",
                message="Batch input file not found",
                status_code=500,
            )

        national_ids: list[str] = json.loads(ids_file.read_text(encoding="utf-8"))

        # Mark as processing
        await db.execute(
            update(BatchJob)
            .where(BatchJob.job_id == job_id)
            .values(
                status=BatchJobStatus.PROCESSING,
                started_at=datetime.now(timezone.utc),
            )
        )
        await db.commit()

        # Fetch job for api_tier
        result = await db.execute(select(BatchJob).where(BatchJob.job_id == job_id))
        job = result.scalar_one()

        results: list[dict[str, Any]] = []
        processed = 0
        failed = 0

        # Process in chunks
        for i in range(0, len(national_ids), CHUNK_SIZE):
            chunk = national_ids[i : i + CHUNK_SIZE]

            for nid in chunk:
                record = await self._score_single(db, redis, nid, job.api_tier)
                results.append(record)
                if record["status"] == "success":
                    processed += 1
                else:
                    failed += 1

            # Update progress after each chunk
            await db.execute(
                update(BatchJob)
                .where(BatchJob.job_id == job_id)
                .values(
                    processed_records=processed,
                    failed_records=failed,
                )
            )
            await db.commit()

        # Generate result file
        result_path = await self._generate_result_file(
            job_id, results, job.file_format
        )

        # Mark as completed
        await db.execute(
            update(BatchJob)
            .where(BatchJob.job_id == job_id)
            .values(
                status=BatchJobStatus.COMPLETED,
                processed_records=processed,
                failed_records=failed,
                result_file_path=str(result_path),
                completed_at=datetime.now(timezone.utc),
            )
        )
        await db.commit()

        # Clean up input file
        try:
            ids_file.unlink()
        except OSError:
            pass

        await logger.ainfo(
            "batch_job_completed",
            job_id=str(job_id),
            processed=processed,
            failed=failed,
        )

        # Send webhook notification
        result = await db.execute(select(BatchJob).where(BatchJob.job_id == job_id))
        job = result.scalar_one()
        if job.webhook_url:
            await self._send_webhook(job)

    async def _score_single(
        self,
        db: AsyncSession,
        redis: Redis,
        national_id: str,
        api_tier: BatchApiTier,
    ) -> dict[str, Any]:
        """Score a single national ID, returning a result dict."""
        id_hash = hash_national_id(national_id)
        try:
            if api_tier == BatchApiTier.PRO:
                score_resp = await self._scoring.get_pro_score(
                    db, redis, national_id
                )
                return {
                    "national_id_hash": id_hash,
                    "vyce_score": score_resp.vyce_score,
                    "niq_score": score_resp.niq_score,
                    "score_date": score_resp.score_date,
                    "model_version": score_resp.model_version,
                    "status": "success",
                    "error_message": None,
                }
            else:
                # Default to lite scoring
                score_resp = await self._scoring.get_lite_score(
                    db, redis, national_id
                )
                return {
                    "national_id_hash": id_hash,
                    "vyce_score": score_resp.vyce_score,
                    "niq_score": score_resp.niq_score,
                    "score_date": score_resp.score_date,
                    "model_version": score_resp.score_version,
                    "status": "success",
                    "error_message": None,
                }
        except Exception as exc:
            await logger.awarning(
                "batch_record_failed",
                national_id_hash=id_hash,
                error=str(exc),
            )
            return {
                "national_id_hash": id_hash,
                "vyce_score": None,
                "niq_score": None,
                "score_date": None,
                "model_version": None,
                "status": "error",
                "error_message": str(exc),
            }

    async def _generate_result_file(
        self,
        job_id: uuid.UUID,
        results: list[dict[str, Any]],
        file_format: str,
    ) -> Path:
        """Generate result file in CSV or JSON format."""
        if file_format == "csv":
            return self._write_csv_results(job_id, results)
        else:
            return self._write_json_results(job_id, results)

    def _write_csv_results(
        self, job_id: uuid.UUID, results: list[dict[str, Any]]
    ) -> Path:
        """Write results as CSV."""
        path = BATCH_RESULTS_DIR / f"{job_id}_results.csv"
        fieldnames = [
            "national_id_hash", "vyce_score", "niq_score",
            "score_date", "model_version", "status", "error_message",
        ]
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(results)
        return path

    def _write_json_results(
        self, job_id: uuid.UUID, results: list[dict[str, Any]]
    ) -> Path:
        """Write results as JSON."""
        path = BATCH_RESULTS_DIR / f"{job_id}_results.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"results": results, "total": len(results)}, f, indent=2)
        return path

    async def _send_webhook(self, job: BatchJob) -> None:
        """POST completion notification to the webhook URL with retries."""
        if not job.webhook_url:
            return

        import httpx

        payload = {
            "job_id": str(job.job_id),
            "status": job.status.value,
            "total_records": job.total_records,
            "processed_records": job.processed_records,
            "failed_records": job.failed_records,
            "completed_at": (
                job.completed_at.isoformat() if job.completed_at else None
            ),
        }

        for attempt in range(1, WEBHOOK_MAX_RETRIES + 1):
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    resp = await client.post(
                        job.webhook_url,
                        json=payload,
                        headers={"Content-Type": "application/json"},
                    )
                    if resp.status_code < 400:
                        await logger.ainfo(
                            "webhook_sent",
                            job_id=str(job.job_id),
                            attempt=attempt,
                            status_code=resp.status_code,
                        )
                        return
                    await logger.awarning(
                        "webhook_non_success",
                        job_id=str(job.job_id),
                        attempt=attempt,
                        status_code=resp.status_code,
                    )
            except Exception as exc:
                await logger.awarning(
                    "webhook_failed",
                    job_id=str(job.job_id),
                    attempt=attempt,
                    error=str(exc),
                )

        await logger.aerror(
            "webhook_exhausted_retries",
            job_id=str(job.job_id),
            max_retries=WEBHOOK_MAX_RETRIES,
        )

    def get_result_file_path(self, job: BatchJob) -> Path | None:
        """Return the result file path if it exists."""
        if not job.result_file_path:
            return None
        path = Path(job.result_file_path)
        if path.exists():
            return path
        return None
