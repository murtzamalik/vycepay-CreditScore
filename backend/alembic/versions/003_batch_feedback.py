"""Add batch_jobs table and enhance loan_feedback with Phase 6 columns.

Revision ID: 003_batch_feedback
Revises: 002_add_user_table
Create Date: 2026-03-08

Tables created:
  - batch_jobs (Phase 6 — async batch scoring jobs)

Tables altered:
  - loan_feedback — add loan_id, is_default, loan_amount,
    disbursement_date, outcome_date columns for ground truth labeling
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision: str = "003_batch_feedback"
down_revision: str = "002_add_user_table"
branch_labels: tuple[str, ...] | None = None
depends_on: str | None = None


def upgrade() -> None:
    # --- Enum types for batch_jobs ---
    batch_job_status_enum = postgresql.ENUM(
        "QUEUED", "PROCESSING", "COMPLETED", "FAILED",
        name="batch_job_status", create_type=False,
    )
    batch_api_tier_enum = postgresql.ENUM(
        "lite", "pro", "custom",
        name="batch_api_tier", create_type=False,
    )

    batch_job_status_enum.create(op.get_bind(), checkfirst=True)
    batch_api_tier_enum.create(op.get_bind(), checkfirst=True)

    # --- batch_jobs ---
    op.create_table(
        "batch_jobs",
        sa.Column("job_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "customer_id", postgresql.UUID(as_uuid=True),
            nullable=False, comment="Customer who submitted the batch job",
        ),
        sa.Column(
            "status", batch_job_status_enum,
            nullable=False, server_default="QUEUED",
        ),
        sa.Column(
            "api_tier", batch_api_tier_enum,
            nullable=False, comment="Scoring tier: lite, pro, or custom",
        ),
        sa.Column(
            "total_records", sa.Integer, nullable=False, server_default="0",
            comment="Total records in the batch",
        ),
        sa.Column(
            "processed_records", sa.Integer, nullable=False, server_default="0",
            comment="Successfully processed records",
        ),
        sa.Column(
            "failed_records", sa.Integer, nullable=False, server_default="0",
            comment="Records that failed processing",
        ),
        sa.Column(
            "file_format", sa.String(10), nullable=False,
            comment="Input file format: csv or json",
        ),
        sa.Column(
            "result_file_path", sa.String(500), nullable=True,
            comment="Path to generated result file",
        ),
        sa.Column(
            "webhook_url", sa.String(2048), nullable=True,
            comment="Webhook URL for completion notification",
        ),
        sa.Column(
            "error_message", sa.Text, nullable=True,
            comment="Error message if batch job failed",
        ),
        sa.Column(
            "started_at", sa.DateTime(timezone=True), nullable=True,
            comment="When processing started",
        ),
        sa.Column(
            "completed_at", sa.DateTime(timezone=True), nullable=True,
            comment="When processing completed",
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            nullable=False, server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            nullable=False, server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_batch_jobs_customer_id", "batch_jobs", ["customer_id"])
    op.create_index("ix_batch_jobs_status", "batch_jobs", ["status"])

    # --- Enhance loan_feedback for Phase 6 ground truth labeling ---
    op.add_column(
        "loan_feedback",
        sa.Column(
            "loan_id", sa.String(100), nullable=True, unique=True,
            comment="Unique loan reference from partner bank",
        ),
    )
    op.add_column(
        "loan_feedback",
        sa.Column(
            "is_default", sa.Boolean, nullable=True,
            comment="Whether loan is classified as defaulted",
        ),
    )
    op.add_column(
        "loan_feedback",
        sa.Column(
            "loan_amount", sa.Numeric(15, 2), nullable=True,
            comment="Loan amount in KES",
        ),
    )
    op.add_column(
        "loan_feedback",
        sa.Column(
            "disbursement_date", sa.Date, nullable=True,
            comment="Date the loan was disbursed",
        ),
    )
    op.add_column(
        "loan_feedback",
        sa.Column(
            "outcome_date", sa.Date, nullable=True,
            comment="Date of the outcome observation",
        ),
    )
    op.create_index("ix_loan_feedback_loan_id", "loan_feedback", ["loan_id"], unique=True)


def downgrade() -> None:
    # Remove enhanced columns from loan_feedback
    op.drop_index("ix_loan_feedback_loan_id", table_name="loan_feedback")
    op.drop_column("loan_feedback", "outcome_date")
    op.drop_column("loan_feedback", "disbursement_date")
    op.drop_column("loan_feedback", "loan_amount")
    op.drop_column("loan_feedback", "is_default")
    op.drop_column("loan_feedback", "loan_id")

    # Drop batch_jobs table
    op.drop_index("ix_batch_jobs_status", table_name="batch_jobs")
    op.drop_index("ix_batch_jobs_customer_id", table_name="batch_jobs")
    op.drop_table("batch_jobs")

    # Drop enum types
    op.execute("DROP TYPE IF EXISTS batch_api_tier")
    op.execute("DROP TYPE IF EXISTS batch_job_status")
