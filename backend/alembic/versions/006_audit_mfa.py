"""Add audit_logs table and MFA fields to users.

Revision ID: 006_audit_mfa
Revises: 005_compliance
Create Date: 2026-03-08

Phase 12 — Compliance, Security Hardening & Audit:
  - audit_logs table with hash chain integrity (Task 12.3)
  - MFA fields on users table (Task 12.7)
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision: str = "006_audit_mfa"
down_revision: str = "005_compliance"
branch_labels: tuple[str, ...] | None = None
depends_on: tuple[str, ...] | None = None


def upgrade() -> None:
    # ── Create audit_log_category enum ──
    audit_log_category = postgresql.ENUM(
        "API_REQUEST",
        "AUTHENTICATION",
        "SCORE_CALCULATION",
        "ADMIN_ACTION",
        "SYSTEM_EVENT",
        "DATA_ACCESS",
        "DATA_MODIFICATION",
        name="audit_log_category",
        create_type=False,
    )
    audit_log_category.create(op.get_bind(), checkfirst=True)

    # ── Create audit_logs table ──
    op.create_table(
        "audit_logs",
        sa.Column("log_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "sequence_number",
            sa.BigInteger(),
            nullable=False,
            unique=True,
            comment="Monotonically increasing sequence for hash chain ordering",
        ),
        sa.Column(
            "category",
            audit_log_category,
            nullable=False,
        ),
        sa.Column(
            "action",
            sa.String(200),
            nullable=False,
            comment="Description of the action",
        ),
        sa.Column(
            "actor_id",
            sa.String(100),
            nullable=True,
            comment="User ID or system identifier",
        ),
        sa.Column(
            "actor_type",
            sa.String(50),
            nullable=False,
            server_default="SYSTEM",
            comment="USER | API_KEY | SYSTEM | SCHEDULER",
        ),
        sa.Column(
            "resource_type",
            sa.String(100),
            nullable=True,
            comment="Type of resource affected",
        ),
        sa.Column(
            "resource_id",
            sa.String(100),
            nullable=True,
            comment="Identifier of the affected resource",
        ),
        sa.Column(
            "details",
            postgresql.JSONB(),
            nullable=True,
            comment="Additional structured data about the event",
        ),
        sa.Column(
            "ip_address",
            sa.String(64),
            nullable=True,
            comment="SHA-256 hash of the client IP address",
        ),
        sa.Column(
            "timestamp",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "entry_hash",
            sa.String(64),
            nullable=False,
            comment="SHA-256 hash of this entry",
        ),
        sa.Column(
            "previous_hash",
            sa.String(64),
            nullable=False,
            comment="SHA-256 hash of the previous entry",
        ),
        sa.Column(
            "is_verified",
            sa.Boolean(),
            nullable=False,
            server_default="true",
            comment="Chain integrity verified at write time",
        ),
        sa.Column(
            "retention_years",
            sa.Integer(),
            nullable=False,
            comment="Number of years this entry must be retained",
        ),
        comment="Immutable audit log with hash chain. No UPDATE/DELETE.",
    )

    # ── Indexes for audit_logs ──
    op.create_index(
        "ix_audit_logs_category_timestamp",
        "audit_logs",
        ["category", "timestamp"],
    )
    op.create_index(
        "ix_audit_logs_actor_timestamp",
        "audit_logs",
        ["actor_id", "timestamp"],
    )
    op.create_index(
        "ix_audit_logs_sequence",
        "audit_logs",
        ["sequence_number"],
        unique=True,
    )

    # ── Add MFA fields to users table ──
    op.add_column(
        "users",
        sa.Column(
            "mfa_enabled",
            sa.Boolean(),
            nullable=False,
            server_default="false",
            comment="Whether TOTP MFA is active for this user",
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "mfa_secret",
            sa.String(512),
            nullable=True,
            comment="Encrypted TOTP secret (base32)",
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "mfa_backup_codes",
            postgresql.ARRAY(sa.String(64)),
            nullable=True,
            comment="SHA-256 hashed backup codes for MFA recovery",
        ),
    )


def downgrade() -> None:
    # ── Remove MFA fields from users ──
    op.drop_column("users", "mfa_backup_codes")
    op.drop_column("users", "mfa_secret")
    op.drop_column("users", "mfa_enabled")

    # ── Drop audit_logs table ──
    op.drop_index("ix_audit_logs_sequence", table_name="audit_logs")
    op.drop_index("ix_audit_logs_actor_timestamp", table_name="audit_logs")
    op.drop_index("ix_audit_logs_category_timestamp", table_name="audit_logs")
    op.drop_table("audit_logs")

    # ── Drop enum ──
    sa.Enum(name="audit_log_category").drop(op.get_bind(), checkfirst=True)
