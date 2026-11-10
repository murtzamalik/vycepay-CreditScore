"""BatchJob ORM model for asynchronous batch scoring jobs."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class BatchJobStatus(str, enum.Enum):
    """Lifecycle status of a batch scoring job."""

    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class BatchApiTier(str, enum.Enum):
    """API tier to use for batch scoring."""

    LITE = "lite"
    PRO = "pro"
    CUSTOM = "custom"


class BatchJob(TimestampMixin, Base):
    """An asynchronous batch scoring job submitted by a customer."""

    __tablename__ = "batch_jobs"

    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True,
        comment="Customer who submitted the batch job",
    )
    status: Mapped[BatchJobStatus] = mapped_column(
        Enum(BatchJobStatus, name="batch_job_status"),
        default=BatchJobStatus.QUEUED,
        server_default="QUEUED",
        nullable=False,
    )
    api_tier: Mapped[BatchApiTier] = mapped_column(
        Enum(BatchApiTier, name="batch_api_tier"),
        nullable=False,
        comment="Scoring tier: lite, pro, or custom",
    )
    total_records: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="Total records in the batch"
    )
    processed_records: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="Successfully processed records"
    )
    failed_records: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="Records that failed processing"
    )
    file_format: Mapped[str] = mapped_column(
        String(10), nullable=False, comment="Input file format: csv or json"
    )
    result_file_path: Mapped[str | None] = mapped_column(
        String(500), nullable=True, comment="Path to generated result file"
    )
    webhook_url: Mapped[str | None] = mapped_column(
        String(2048), nullable=True, comment="Webhook URL for completion notification"
    )
    error_message: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="Error message if batch job failed"
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="When processing started"
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="When processing completed"
    )

    def __repr__(self) -> str:
        return (
            f"<BatchJob {self.job_id} status={self.status.value} "
            f"progress={self.processed_records}/{self.total_records}>"
        )
