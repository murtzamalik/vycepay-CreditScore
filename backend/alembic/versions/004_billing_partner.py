"""Add billing_records and embed_configs tables for Phase 14.

Revision ID: 004_billing_partner
Revises: 003_batch_feedback
Create Date: 2026-03-08

Tables created:
  - billing_records (monthly billing records per customer)
  - embed_configs (white-label embed configuration per customer)
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ENUM, JSONB, UUID

# revision identifiers
revision: str = "004_billing_partner"
down_revision: str = "003_batch_feedback"
branch_labels: tuple[str, ...] | None = None
depends_on: str | None = None


def upgrade() -> None:
    # --- billing_status enum ---
    billing_status_enum = ENUM(
        "DRAFT", "FINALIZED", "PAID", "OVERDUE",
        name="billing_status",
        create_type=False,
    )
    billing_status_enum.create(op.get_bind(), checkfirst=True)

    # --- billing_records table ---
    op.create_table(
        "billing_records",
        sa.Column("billing_id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "customer_id",
            UUID(as_uuid=True),
            sa.ForeignKey("customers.customer_id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("billing_period", sa.String(7), nullable=False),
        sa.Column(
            "status",
            billing_status_enum,
            nullable=False,
            server_default="DRAFT",
        ),
        # Query counts
        sa.Column("lite_queries", sa.Integer, nullable=False, server_default="0"),
        sa.Column("pro_queries", sa.Integer, nullable=False, server_default="0"),
        sa.Column("batch_queries", sa.Integer, nullable=False, server_default="0"),
        sa.Column("total_queries", sa.Integer, nullable=False, server_default="0"),
        # Pricing
        sa.Column("base_fee", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("lite_cost", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("pro_cost", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("overage_cost", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("total_amount", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("currency", sa.String(3), nullable=False, server_default="KES"),
        sa.Column("included_queries", sa.Integer, nullable=False, server_default="0"),
        sa.Column("overage_queries", sa.Integer, nullable=False, server_default="0"),
        # Timestamps
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # Unique constraint: one record per customer per period
    op.create_index(
        "ix_billing_records_customer_period",
        "billing_records",
        ["customer_id", "billing_period"],
        unique=True,
    )

    # --- embed_configs table ---
    op.create_table(
        "embed_configs",
        sa.Column("embed_config_id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "customer_id",
            UUID(as_uuid=True),
            sa.ForeignKey("customers.customer_id", ondelete="CASCADE"),
            unique=True,
            nullable=False,
        ),
        sa.Column(
            "customer_token",
            sa.String(64),
            unique=True,
            index=True,
            nullable=False,
        ),
        sa.Column("allowed_origins", JSONB, nullable=True),
        sa.Column("theme_config", JSONB, nullable=True),
        sa.Column("widget_config", JSONB, nullable=True),
        sa.Column(
            "is_active",
            sa.Boolean,
            nullable=False,
            server_default="true",
        ),
        # Timestamps
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )


def downgrade() -> None:
    op.drop_table("embed_configs")
    op.drop_index("ix_billing_records_customer_period", table_name="billing_records")
    op.drop_table("billing_records")
    sa.Enum(name="billing_status").drop(op.get_bind(), checkfirst=True)
