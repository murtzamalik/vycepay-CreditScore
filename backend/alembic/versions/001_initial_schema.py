"""Initial schema — all core domain entities.

Revision ID: 001_initial_schema
Revises:
Create Date: 2026-03-08

Tables created:
  - subjects        (BRD §11.1.1)
  - customers       (BRD §11.1.5)
  - scores          (BRD §11.1.2)
  - risk_drivers    (BRD §11.1.3)
  - features        (BRD §11.1.4)
  - api_request_logs(BRD §11.1.6)
  - kpi_snapshots   (BRD §10.5)
  - users           (auth)
  - loan_feedback   (feedback loop)

Partitioning note (BRD §11.4):
  scores, features, and api_request_logs should be range-partitioned in
  production.  This migration creates them as regular tables with composite
  indexes that support partition pruning.  Apply native PostgreSQL
  partitioning (PARTITION BY RANGE) as a follow-up DDL when deploying to
  production.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision: str = "001_initial_schema"
down_revision: str | None = None
branch_labels: tuple[str, ...] | None = None
depends_on: str | None = None


def upgrade() -> None:
    # --- Enum types ---
    subject_type_enum = postgresql.ENUM("INDIVIDUAL", "BUSINESS", name="subject_type", create_type=False)
    kyc_status_enum = postgresql.ENUM("VERIFIED", "PENDING", "FAILED", name="kyc_status", create_type=False)
    aml_status_enum = postgresql.ENUM("CLEAR", "REVIEW", "FLAGGED", name="aml_status", create_type=False)
    license_tier_enum = postgresql.ENUM("LITE", "PRO", "DEEP_DIVE", name="license_tier", create_type=False)
    customer_status_enum = postgresql.ENUM("PENDING", "ACTIVE", "SUSPENDED", "TERMINATED", name="customer_status", create_type=False)
    impact_direction_enum = postgresql.ENUM("POSITIVE", "NEGATIVE", name="impact_direction", create_type=False)
    snapshot_period_enum = postgresql.ENUM("HOURLY", "DAILY", "WEEKLY", "MONTHLY", name="snapshot_period", create_type=False)
    user_role_enum = postgresql.ENUM("Admin", "Operator", "Partner", "ReadOnly", name="user_role", create_type=False)

    for enum_type in [
        subject_type_enum, kyc_status_enum, aml_status_enum,
        license_tier_enum, customer_status_enum, impact_direction_enum,
        snapshot_period_enum, user_role_enum,
    ]:
        enum_type.create(op.get_bind(), checkfirst=True)

    # --- subjects ---
    op.create_table(
        "subjects",
        sa.Column("subject_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("subject_type", subject_type_enum, nullable=False),
        sa.Column(
            "id_hash", sa.String(64), nullable=False, unique=True,
            comment="SHA-256 hash of National ID — PII never stored in plain text",
        ),
        sa.Column("kyc_status", kyc_status_enum, nullable=False, server_default="PENDING"),
        sa.Column("aml_status", aml_status_enum, nullable=False, server_default="CLEAR"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_subjects_id_hash", "subjects", ["id_hash"], unique=True)

    # --- customers ---
    op.create_table(
        "customers",
        sa.Column("customer_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column(
            "contact_email", sa.String(255), nullable=True,
            comment="Primary contact email for the customer organisation",
        ),
        sa.Column("license_tier", license_tier_enum, nullable=False),
        sa.Column("status", customer_status_enum, nullable=False, server_default="PENDING"),
        sa.Column(
            "api_key_hash", sa.String(64), nullable=True, unique=True,
            comment="SHA-256 hash of the customer API key",
        ),
        sa.Column("monthly_query_limit", sa.Integer, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("sandbox_enabled", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("production_enabled", sa.Boolean, nullable=False, server_default="false"),
    )

    # --- scores ---
    op.create_table(
        "scores",
        sa.Column("score_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "subject_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("subjects.subject_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("vyce_score", sa.Integer, nullable=False, comment="VyceScore in range 300-900"),
        sa.Column("niq_score", sa.Integer, nullable=True, comment="NIQ score 0-100"),
        sa.Column("score_date", sa.Date, nullable=False),
        sa.Column("model_version", sa.String(50), nullable=False),
        sa.Column(
            "prediction_horizon", sa.Integer, nullable=False, server_default="12",
            comment="Prediction horizon in months",
        ),
        sa.Column("confidence_lower", sa.Integer, nullable=True, comment="Lower bound of confidence interval"),
        sa.Column("confidence_upper", sa.Integer, nullable=True, comment="Upper bound of confidence interval"),
        sa.Column(
            "feature_snapshot_id", postgresql.UUID(as_uuid=True), nullable=True,
            comment="Reference to the feature snapshot used for this score",
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("vyce_score BETWEEN 300 AND 900", name="ck_scores_vyce_score_range"),
        sa.CheckConstraint("niq_score BETWEEN 0 AND 100", name="ck_scores_niq_score_range"),
        sa.CheckConstraint("confidence_lower IS NULL OR confidence_lower >= 300", name="ck_scores_confidence_lower"),
        sa.CheckConstraint("confidence_upper IS NULL OR confidence_upper <= 900", name="ck_scores_confidence_upper"),
        comment="Partition by score_date in production (range, monthly)",
    )
    op.create_index("ix_scores_subject_id", "scores", ["subject_id"])
    op.create_index("ix_scores_subject_score_date", "scores", ["subject_id", "score_date"])

    # --- risk_drivers ---
    op.create_table(
        "risk_drivers",
        sa.Column("driver_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "score_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("scores.score_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("rank", sa.Integer, nullable=False, comment="Importance rank (1 = most impactful)"),
        sa.Column("factor_name", sa.String(100), nullable=False, comment="Human-readable factor name"),
        sa.Column("impact", impact_direction_enum, nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("shap_value", sa.Numeric(10, 6), nullable=True, comment="SHAP contribution value"),
        sa.Column(
            "feature_name", sa.String(100), nullable=True,
            comment="Internal ML feature name (e.g. CBLRI, UTDI)",
        ),
        sa.CheckConstraint("rank BETWEEN 1 AND 10", name="ck_risk_drivers_rank_range"),
    )
    op.create_index("ix_risk_drivers_score_id", "risk_drivers", ["score_id"])

    # --- features ---
    op.create_table(
        "features",
        sa.Column("feature_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "subject_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("subjects.subject_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("feature_date", sa.Date, nullable=False),
        sa.Column(
            "feature_name", sa.String(100), nullable=False,
            comment="Feature identifier (e.g. CBLRI, UTDI, SCFV, DDC_RATIO, NIQ, GOS)",
        ),
        sa.Column("feature_value", sa.Numeric(20, 6), nullable=False),
        sa.Column(
            "feature_category", sa.String(50), nullable=True,
            comment="TRANSACTION | NETWORK | SUPPLY_CHAIN | COMPLIANCE",
        ),
        sa.Column(
            "data_source", sa.String(50), nullable=True,
            comment="VYCEPAY | VYCETRADE | COMPLIANCE",
        ),
        sa.Column(
            "quality_score", sa.Numeric(3, 2), nullable=True,
            comment="Data quality indicator 0.00-1.00",
        ),
        sa.CheckConstraint(
            "quality_score IS NULL OR (quality_score >= 0 AND quality_score <= 1)",
            name="ck_features_quality_score_range",
        ),
        comment="Partition by feature_date in production (range, monthly)",
    )
    op.create_index("ix_features_subject_id", "features", ["subject_id"])
    op.create_index("ix_features_subject_feature_date", "features", ["subject_id", "feature_date"])

    # --- api_request_logs ---
    op.create_table(
        "api_request_logs",
        sa.Column("log_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "customer_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("customers.customer_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("request_time", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("endpoint", sa.String(200), nullable=False),
        sa.Column(
            "subject_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("subjects.subject_id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("response_status", sa.Integer, nullable=False),
        sa.Column("response_time_ms", sa.Integer, nullable=True, comment="Response time in milliseconds"),
        sa.Column("query_cost", sa.Integer, nullable=False, server_default="1", comment="Query credits consumed"),
        sa.Column("ip_address", sa.String(45), nullable=True, comment="Hashed IP address"),
        comment="Partition by request_time in production (range, daily/weekly)",
    )
    op.create_index("ix_api_request_logs_customer_id", "api_request_logs", ["customer_id"])
    op.create_index(
        "ix_api_request_logs_customer_request_time",
        "api_request_logs",
        ["customer_id", "request_time"],
    )

    # --- kpi_snapshots ---
    op.create_table(
        "kpi_snapshots",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("kpi_id", sa.String(50), nullable=False, comment="Machine-readable KPI identifier"),
        sa.Column("kpi_name", sa.String(100), nullable=False, comment="Human-readable KPI name"),
        sa.Column("snapshot_date", sa.Date, nullable=False),
        sa.Column("snapshot_period", snapshot_period_enum, nullable=True),
        sa.Column("value", sa.Numeric(20, 6), nullable=False),
        sa.Column("unit", sa.String(20), nullable=True, comment="Unit of measurement"),
        sa.Column("target", sa.Numeric(20, 6), nullable=True, comment="Target value"),
        sa.Column("status", sa.String(20), nullable=True, comment="meeting_target | below_target | above_target"),
        sa.Column("dimensions", postgresql.JSON, nullable=True, comment="Dimensional breakdowns"),
        sa.Column("metadata_info", postgresql.JSON, nullable=True, comment="Additional context"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # --- users (auth) ---
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(320), nullable=False, unique=True),
        sa.Column("hashed_password", sa.String(128), nullable=False),
        sa.Column("role", user_role_enum, nullable=False, server_default="ReadOnly"),
        sa.Column("api_key", sa.String(64), nullable=True, unique=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_index("ix_users_api_key", "users", ["api_key"], unique=True)

    # --- loan_feedback (feedback loop) ---
    op.create_table(
        "loan_feedback",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "national_id_hash", sa.String(64), nullable=False,
            comment="SHA-256 hash of the national ID",
        ),
        sa.Column("loan_outcome", sa.String(32), nullable=False, comment="performing | default | restructured"),
        sa.Column("dpd", sa.Integer, nullable=False, server_default="0", comment="Days past due"),
        sa.Column("partner_id", sa.String(64), nullable=False, comment="Reporting partner bank identifier"),
        sa.Column("reported_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_loan_feedback_national_id_hash", "loan_feedback", ["national_id_hash"])
    op.create_index("ix_loan_feedback_partner_id", "loan_feedback", ["partner_id"])


def downgrade() -> None:
    op.drop_table("loan_feedback")
    op.drop_table("users")
    op.drop_table("kpi_snapshots")
    op.drop_table("api_request_logs")
    op.drop_table("features")
    op.drop_table("risk_drivers")
    op.drop_table("scores")
    op.drop_table("customers")
    op.drop_table("subjects")

    # Drop enum types
    for enum_name in [
        "user_role", "snapshot_period", "impact_direction",
        "customer_status", "license_tier", "aml_status",
        "kyc_status", "subject_type",
    ]:
        op.execute(f"DROP TYPE IF EXISTS {enum_name}")
