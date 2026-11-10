"""Add compliance_checks table for KYC/AML audit trail.

Revision ID: 005_compliance
Revises: 004_billing_partner
Create Date: 2026-03-08

Tables created:
  - compliance_checks (Phase 15 — KYC/AML compliance check history)
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision: str = "005_compliance"
down_revision: str = "004_billing_partner"
branch_labels: tuple[str, ...] | None = None
depends_on: str | None = None


def upgrade() -> None:
    # --- Enum types for compliance_checks ---
    compliance_check_type_enum = postgresql.ENUM(
        "KYC", "AML",
        name="compliance_check_type", create_type=False,
    )
    compliance_check_status_enum = postgresql.ENUM(
        "PASSED", "FAILED", "PENDING", "REVIEW",
        name="compliance_check_status", create_type=False,
    )

    compliance_check_type_enum.create(op.get_bind(), checkfirst=True)
    compliance_check_status_enum.create(op.get_bind(), checkfirst=True)

    # --- compliance_checks ---
    op.create_table(
        "compliance_checks",
        sa.Column(
            "check_id", postgresql.UUID(as_uuid=True), primary_key=True,
        ),
        sa.Column(
            "subject_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("subjects.subject_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "check_type", compliance_check_type_enum,
            nullable=False,
        ),
        sa.Column(
            "status", compliance_check_status_enum,
            nullable=False,
        ),
        sa.Column(
            "provider", sa.String(50), nullable=False,
            comment="Provider name: smile_id or comply_advantage",
        ),
        sa.Column(
            "provider_reference", sa.String(200), nullable=True,
            comment="Provider-specific reference/job ID for audit trail",
        ),
        sa.Column(
            "confidence_score", sa.Float, nullable=True,
            comment="Confidence score from provider (0.0 to 1.0)",
        ),
        sa.Column(
            "risk_score", sa.Float, nullable=True,
            comment="Risk score from provider (0.0 to 1.0)",
        ),
        sa.Column(
            "raw_response", sa.Text, nullable=True,
            comment="Encrypted JSON of full provider response",
        ),
        sa.Column(
            "checked_at", sa.DateTime(timezone=True), nullable=True,
            comment="Timestamp when the check was completed by the provider",
        ),
        sa.Column(
            "expires_at", sa.DateTime(timezone=True), nullable=True,
            comment="When this check result expires and needs refresh",
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
    op.create_index(
        "ix_compliance_checks_subject_id",
        "compliance_checks",
        ["subject_id"],
    )
    op.create_index(
        "ix_compliance_checks_check_type",
        "compliance_checks",
        ["check_type"],
    )
    op.create_index(
        "ix_compliance_checks_checked_at",
        "compliance_checks",
        ["checked_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_compliance_checks_checked_at", table_name="compliance_checks")
    op.drop_index("ix_compliance_checks_check_type", table_name="compliance_checks")
    op.drop_index("ix_compliance_checks_subject_id", table_name="compliance_checks")
    op.drop_table("compliance_checks")

    op.execute("DROP TYPE IF EXISTS compliance_check_status")
    op.execute("DROP TYPE IF EXISTS compliance_check_type")
