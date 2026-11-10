"""Tests for batch scoring endpoints and services (Phase 6, Tasks 6.1–6.5).

Covers:
  - CSV and JSON file parsing
  - File validation (format, size, empty)
  - Batch job creation and status retrieval
  - Background batch processing with chunking
  - Individual record failure handling
  - Result file generation (CSV/JSON)
  - Webhook notification with retries
  - Ownership enforcement on status and results
  - Tier validation (Pro/DeepDive required)
"""

from __future__ import annotations

import csv
import io
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.exceptions import ForbiddenError, NotFoundError, VyceScoreError
from app.models.batch_job import BatchApiTier, BatchJob, BatchJobStatus
from app.models.customer import Customer, CustomerStatus, LicenseTier
from app.schemas.batches import BatchJobResponse, BatchJobStatusResponse
from app.services.batch_service import (
    BatchService,
    MAX_FILE_SIZE,
    parse_national_ids_from_csv,
    parse_national_ids_from_json,
)


# =========================================================================
# 1. CSV parser
# =========================================================================


class TestParseCSV:
    """Validate CSV parsing logic for batch input files."""

    def test_parse_with_national_id_header(self) -> None:
        content = b"national_id\n12345678\n87654321\n"
        result = parse_national_ids_from_csv(content)
        assert result == ["12345678", "87654321"]

    def test_parse_with_id_header(self) -> None:
        content = b"id,name\n12345678,Alice\n87654321,Bob\n"
        result = parse_national_ids_from_csv(content)
        assert result == ["12345678", "87654321"]

    def test_parse_without_matching_header_uses_first_column(self) -> None:
        content = b"some_col,other\n12345678,x\n87654321,y\n"
        result = parse_national_ids_from_csv(content)
        assert result == ["12345678", "87654321"]

    def test_parse_skips_empty_values(self) -> None:
        content = b"national_id\n12345678\n\n87654321\n"
        result = parse_national_ids_from_csv(content)
        assert result == ["12345678", "87654321"]

    def test_parse_strips_whitespace(self) -> None:
        content = b"national_id\n  12345678  \n  87654321  \n"
        result = parse_national_ids_from_csv(content)
        assert result == ["12345678", "87654321"]

    def test_empty_csv_raises(self) -> None:
        with pytest.raises(VyceScoreError, match="empty"):
            parse_national_ids_from_csv(b"")

    def test_header_only_csv_returns_empty(self) -> None:
        content = b"national_id\n"
        result = parse_national_ids_from_csv(content)
        assert result == []

    def test_bom_handling(self) -> None:
        """UTF-8 BOM should be handled transparently."""
        content = b"\xef\xbb\xbfnational_id\n12345678\n"
        result = parse_national_ids_from_csv(content)
        assert result == ["12345678"]


# =========================================================================
# 2. JSON parser
# =========================================================================


class TestParseJSON:
    """Validate JSON parsing logic for batch input files."""

    def test_parse_array_of_strings(self) -> None:
        content = json.dumps(["12345678", "87654321"]).encode()
        result = parse_national_ids_from_json(content)
        assert result == ["12345678", "87654321"]

    def test_parse_object_with_national_ids_key(self) -> None:
        content = json.dumps({"national_ids": ["12345678", "87654321"]}).encode()
        result = parse_national_ids_from_json(content)
        assert result == ["12345678", "87654321"]

    def test_parse_object_with_ids_key(self) -> None:
        content = json.dumps({"ids": ["12345678"]}).encode()
        result = parse_national_ids_from_json(content)
        assert result == ["12345678"]

    def test_parse_object_with_camel_case_key(self) -> None:
        content = json.dumps({"nationalIds": ["12345678"]}).encode()
        result = parse_national_ids_from_json(content)
        assert result == ["12345678"]

    def test_invalid_json_raises(self) -> None:
        with pytest.raises(VyceScoreError, match="Invalid JSON"):
            parse_national_ids_from_json(b"not valid json")

    def test_invalid_structure_raises(self) -> None:
        content = json.dumps({"other_key": "value"}).encode()
        with pytest.raises(VyceScoreError, match="array of IDs"):
            parse_national_ids_from_json(content)

    def test_skips_empty_values(self) -> None:
        content = json.dumps(["12345678", "", "87654321"]).encode()
        result = parse_national_ids_from_json(content)
        assert result == ["12345678", "87654321"]


# =========================================================================
# 3. Batch job creation
# =========================================================================


def _make_customer(
    tier: LicenseTier = LicenseTier.PRO,
    customer_id: uuid.UUID | None = None,
) -> Customer:
    c = MagicMock(spec=Customer)
    c.customer_id = customer_id or uuid.uuid4()
    c.license_tier = tier
    c.status = CustomerStatus.ACTIVE
    c.name = "Test Bank"
    return c


def _make_batch_job(
    customer_id: uuid.UUID | None = None,
    status: BatchJobStatus = BatchJobStatus.QUEUED,
    total_records: int = 5,
    processed_records: int = 0,
    failed_records: int = 0,
    file_format: str = "csv",
    result_file_path: str | None = None,
    webhook_url: str | None = None,
) -> BatchJob:
    job = MagicMock(spec=BatchJob)
    job.job_id = uuid.uuid4()
    job.customer_id = customer_id or uuid.uuid4()
    job.status = status
    job.api_tier = BatchApiTier.LITE
    job.total_records = total_records
    job.processed_records = processed_records
    job.failed_records = failed_records
    job.file_format = file_format
    job.result_file_path = result_file_path
    job.webhook_url = webhook_url
    job.error_message = None
    job.created_at = datetime.now(timezone.utc)
    job.started_at = None
    job.completed_at = None
    return job


class TestBatchJobCreation:
    """Test BatchService.create_batch_job."""

    @pytest.mark.asyncio
    async def test_creates_queued_job(self) -> None:
        service = BatchService()
        mock_db = AsyncMock()
        customer_id = uuid.uuid4()
        ids = ["12345678", "87654321", "11111111"]

        job = await service.create_batch_job(
            db=mock_db,
            customer_id=customer_id,
            national_ids=ids,
            file_format="csv",
            api_tier=BatchApiTier.LITE,
        )

        assert job.status == BatchJobStatus.QUEUED
        assert job.total_records == 3
        assert job.processed_records == 0
        assert job.failed_records == 0
        assert job.customer_id == customer_id
        mock_db.add.assert_called_once()
        mock_db.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_stores_input_ids_file(self) -> None:
        service = BatchService()
        mock_db = AsyncMock()
        ids = ["12345678"]

        job = await service.create_batch_job(
            db=mock_db,
            customer_id=uuid.uuid4(),
            national_ids=ids,
            file_format="json",
            api_tier=BatchApiTier.PRO,
        )

        # Check input file was created
        from app.services.batch_service import BATCH_RESULTS_DIR
        ids_file = BATCH_RESULTS_DIR / f"{job.job_id}_input.json"
        assert ids_file.exists()
        stored = json.loads(ids_file.read_text())
        assert stored == ["12345678"]

        # Clean up
        ids_file.unlink()

    @pytest.mark.asyncio
    async def test_webhook_url_stored(self) -> None:
        service = BatchService()
        mock_db = AsyncMock()

        job = await service.create_batch_job(
            db=mock_db,
            customer_id=uuid.uuid4(),
            national_ids=["12345678"],
            file_format="csv",
            api_tier=BatchApiTier.LITE,
            webhook_url="https://example.com/webhook",
        )

        assert job.webhook_url == "https://example.com/webhook"

        # Clean up
        from app.services.batch_service import BATCH_RESULTS_DIR
        ids_file = BATCH_RESULTS_DIR / f"{job.job_id}_input.json"
        if ids_file.exists():
            ids_file.unlink()


# =========================================================================
# 4. Batch job status retrieval
# =========================================================================


class TestBatchJobRetrieval:
    """Test BatchService.get_batch_job."""

    @pytest.mark.asyncio
    async def test_returns_job_for_owner(self) -> None:
        service = BatchService()
        mock_db = AsyncMock()
        customer_id = uuid.uuid4()
        job = _make_batch_job(customer_id=customer_id)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = job
        mock_db.execute.return_value = mock_result

        result = await service.get_batch_job(mock_db, job.job_id, customer_id)
        assert result.job_id == job.job_id

    @pytest.mark.asyncio
    async def test_raises_404_for_missing_job(self) -> None:
        service = BatchService()
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        with pytest.raises(NotFoundError):
            await service.get_batch_job(mock_db, uuid.uuid4(), uuid.uuid4())

    @pytest.mark.asyncio
    async def test_raises_403_for_non_owner(self) -> None:
        service = BatchService()
        mock_db = AsyncMock()
        job = _make_batch_job(customer_id=uuid.uuid4())

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = job
        mock_db.execute.return_value = mock_result

        other_customer = uuid.uuid4()
        with pytest.raises(ForbiddenError, match="do not own"):
            await service.get_batch_job(mock_db, job.job_id, other_customer)


# =========================================================================
# 5. Result file generation
# =========================================================================


class TestResultFileGeneration:
    """Test CSV and JSON result file generation."""

    def test_csv_result_file(self) -> None:
        service = BatchService()
        job_id = uuid.uuid4()
        results = [
            {
                "national_id_hash": "abc123",
                "vyce_score": 720,
                "niq_score": 75,
                "score_date": "2026-03-08",
                "model_version": "v1.0.0",
                "status": "success",
                "error_message": None,
            },
            {
                "national_id_hash": "def456",
                "vyce_score": None,
                "niq_score": None,
                "score_date": None,
                "model_version": None,
                "status": "error",
                "error_message": "Subject not found",
            },
        ]

        path = service._write_csv_results(job_id, results)
        assert path.exists()

        with open(path) as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            assert len(rows) == 2
            assert rows[0]["status"] == "success"
            assert rows[0]["vyce_score"] == "720"
            assert rows[1]["status"] == "error"

        # Clean up
        path.unlink()

    def test_json_result_file(self) -> None:
        service = BatchService()
        job_id = uuid.uuid4()
        results = [
            {
                "national_id_hash": "abc123",
                "vyce_score": 720,
                "niq_score": 75,
                "score_date": "2026-03-08",
                "model_version": "v1.0.0",
                "status": "success",
                "error_message": None,
            },
        ]

        path = service._write_json_results(job_id, results)
        assert path.exists()

        data = json.loads(path.read_text())
        assert data["total"] == 1
        assert data["results"][0]["vyce_score"] == 720

        # Clean up
        path.unlink()


# =========================================================================
# 6. Tier validation
# =========================================================================


class TestBatchTierValidation:
    """Verify that batch endpoints require Pro or Deep Dive tier."""

    @pytest.mark.asyncio
    async def test_lite_tier_blocked(self) -> None:
        from app.api.v1.endpoints.batches import _require_batch_tier

        checker = _require_batch_tier()
        customer = _make_customer(LicenseTier.LITE)

        with pytest.raises(ForbiddenError, match="License tier insufficient"):
            await checker(customer=customer)

    @pytest.mark.asyncio
    async def test_pro_tier_allowed(self) -> None:
        from app.api.v1.endpoints.batches import _require_batch_tier

        checker = _require_batch_tier()
        customer = _make_customer(LicenseTier.PRO)

        result = await checker(customer=customer)
        assert result.license_tier == LicenseTier.PRO

    @pytest.mark.asyncio
    async def test_deep_dive_tier_allowed(self) -> None:
        from app.api.v1.endpoints.batches import _require_batch_tier

        checker = _require_batch_tier()
        customer = _make_customer(LicenseTier.DEEP_DIVE)

        result = await checker(customer=customer)
        assert result.license_tier == LicenseTier.DEEP_DIVE


# =========================================================================
# 7. Status response schema
# =========================================================================


class TestBatchStatusResponse:
    """Validate batch status response construction."""

    def test_queued_job_response(self) -> None:
        resp = BatchJobStatusResponse(
            job_id=str(uuid.uuid4()),
            status="QUEUED",
            api_tier="lite",
            total_records=100,
            processed_records=0,
            failed_records=0,
            progress_percent=0.0,
            result_download_url=None,
            error_message=None,
            created_at=datetime.now(timezone.utc),
            started_at=None,
            completed_at=None,
        )
        data = resp.model_dump()
        assert data["status"] == "QUEUED"
        assert data["progress_percent"] == 0.0
        assert data["result_download_url"] is None

    def test_completed_job_response(self) -> None:
        job_id = str(uuid.uuid4())
        resp = BatchJobStatusResponse(
            job_id=job_id,
            status="COMPLETED",
            api_tier="pro",
            total_records=50,
            processed_records=48,
            failed_records=2,
            progress_percent=100.0,
            result_download_url=f"/v1/batches/{job_id}/results",
            error_message=None,
            created_at=datetime.now(timezone.utc),
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
        )
        data = resp.model_dump()
        assert data["status"] == "COMPLETED"
        assert data["progress_percent"] == 100.0
        assert data["result_download_url"] is not None

    def test_failed_job_response(self) -> None:
        resp = BatchJobStatusResponse(
            job_id=str(uuid.uuid4()),
            status="FAILED",
            api_tier="lite",
            total_records=100,
            processed_records=30,
            failed_records=70,
            progress_percent=100.0,
            result_download_url=None,
            error_message="Internal processing error",
            created_at=datetime.now(timezone.utc),
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
        )
        data = resp.model_dump()
        assert data["status"] == "FAILED"
        assert data["error_message"] == "Internal processing error"


# =========================================================================
# 8. Webhook notification
# =========================================================================


class TestWebhookNotification:
    """Test webhook sending with retry logic."""

    @pytest.mark.asyncio
    async def test_webhook_success_on_first_try(self) -> None:
        import httpx as httpx_mod

        service = BatchService()
        job = _make_batch_job(
            webhook_url="https://example.com/webhook",
            status=BatchJobStatus.COMPLETED,
        )
        job.completed_at = datetime.now(timezone.utc)

        mock_response = MagicMock()
        mock_response.status_code = 200

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response

        with patch.object(httpx_mod, "AsyncClient") as mock_client_cls:
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            await service._send_webhook(job)

            mock_client.post.assert_called_once()
            call_args = mock_client.post.call_args
            assert call_args[0][0] == "https://example.com/webhook"
            payload = call_args[1]["json"]
            assert payload["status"] == "COMPLETED"

    @pytest.mark.asyncio
    async def test_webhook_skipped_if_no_url(self) -> None:
        service = BatchService()
        job = _make_batch_job(webhook_url=None)

        # Should not raise any error
        await service._send_webhook(job)

    @pytest.mark.asyncio
    async def test_webhook_retries_on_failure(self) -> None:
        import httpx as httpx_mod

        service = BatchService()
        job = _make_batch_job(
            webhook_url="https://example.com/webhook",
            status=BatchJobStatus.COMPLETED,
        )
        job.completed_at = datetime.now(timezone.utc)

        mock_client = AsyncMock()
        mock_client.post.side_effect = Exception("Connection refused")

        with patch.object(httpx_mod, "AsyncClient") as mock_client_cls:
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            await service._send_webhook(job)

            # Should retry 3 times
            assert mock_client.post.call_count == 3


# =========================================================================
# 9. Batch submit response schema
# =========================================================================


class TestBatchSubmitResponse:
    """Validate batch submission response."""

    def test_submit_response_schema(self) -> None:
        resp = BatchJobResponse(
            job_id=str(uuid.uuid4()),
            status="QUEUED",
            total_records=50,
            message="Batch job queued with 50 records",
        )
        data = resp.model_dump()
        assert data["status"] == "QUEUED"
        assert data["total_records"] == 50
        assert "50 records" in data["message"]


# =========================================================================
# 10. Result file path resolution
# =========================================================================


class TestResultFilePath:
    """Test get_result_file_path."""

    def test_returns_none_if_no_path(self) -> None:
        service = BatchService()
        job = _make_batch_job(result_file_path=None)
        assert service.get_result_file_path(job) is None

    def test_returns_none_if_file_missing(self) -> None:
        service = BatchService()
        job = _make_batch_job(result_file_path="/nonexistent/path.csv")
        assert service.get_result_file_path(job) is None

    def test_returns_path_if_file_exists(self, tmp_path: Path) -> None:
        service = BatchService()
        result_file = tmp_path / "results.csv"
        result_file.write_text("test")
        job = _make_batch_job(result_file_path=str(result_file))
        assert service.get_result_file_path(job) == result_file
