"""Unit tests for SQLAlchemy domain models.

These tests verify model instantiation, enum correctness, and that
CHECK constraints are defined on the relevant tables — all without
requiring a running database.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from app.models import (
    AMLStatus,
    ApiRequestLog,
    Base,
    Customer,
    CustomerStatus,
    Feature,
    ImpactDirection,
    KPISnapshot,
    KYCStatus,
    LicenseTier,
    LoanFeedback,
    RiskDriver,
    Score,
    SnapshotPeriod,
    Subject,
    SubjectType,
    User,
    UserRole,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _uuid() -> uuid.UUID:
    return uuid.uuid4()


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Subject
# ---------------------------------------------------------------------------

class TestSubject:
    def test_instantiation(self) -> None:
        s = Subject(
            subject_id=_uuid(),
            subject_type=SubjectType.INDIVIDUAL,
            id_hash="a" * 64,
        )
        assert s.subject_type == SubjectType.INDIVIDUAL
        assert len(s.id_hash) == 64

    def test_default_kyc_aml(self) -> None:
        s = Subject(
            subject_id=_uuid(),
            subject_type=SubjectType.BUSINESS,
            id_hash="b" * 64,
        )
        assert s.kyc_status is None or s.kyc_status == KYCStatus.PENDING
        assert s.aml_status is None or s.aml_status == AMLStatus.CLEAR

    def test_subject_type_enum_values(self) -> None:
        assert SubjectType.INDIVIDUAL.value == "INDIVIDUAL"
        assert SubjectType.BUSINESS.value == "BUSINESS"
        assert len(SubjectType) == 2

    def test_kyc_status_enum_values(self) -> None:
        assert set(KYCStatus) == {KYCStatus.VERIFIED, KYCStatus.PENDING, KYCStatus.FAILED}

    def test_aml_status_enum_values(self) -> None:
        assert set(AMLStatus) == {AMLStatus.CLEAR, AMLStatus.REVIEW, AMLStatus.FLAGGED}

    def test_repr(self) -> None:
        sid = _uuid()
        s = Subject(subject_id=sid, subject_type=SubjectType.INDIVIDUAL, id_hash="c" * 64)
        assert str(sid) in repr(s)


# ---------------------------------------------------------------------------
# Customer
# ---------------------------------------------------------------------------

class TestCustomer:
    def test_instantiation(self) -> None:
        c = Customer(
            customer_id=_uuid(),
            name="Equity Bank",
            license_tier=LicenseTier.PRO,
            monthly_query_limit=50_000,
        )
        assert c.name == "Equity Bank"
        assert c.license_tier == LicenseTier.PRO

    def test_license_tier_enum_values(self) -> None:
        assert LicenseTier.LITE.value == "LITE"
        assert LicenseTier.PRO.value == "PRO"
        assert LicenseTier.DEEP_DIVE.value == "DEEP_DIVE"
        assert len(LicenseTier) == 3

    def test_customer_status_enum_values(self) -> None:
        assert set(CustomerStatus) == {
            CustomerStatus.PENDING,
            CustomerStatus.ACTIVE,
            CustomerStatus.SUSPENDED,
            CustomerStatus.TERMINATED,
        }

    def test_defaults(self) -> None:
        c = Customer(
            customer_id=_uuid(),
            name="Test",
            license_tier=LicenseTier.LITE,
            monthly_query_limit=1000,
        )
        # Python-side defaults
        assert c.sandbox_enabled is None or c.sandbox_enabled is True
        assert c.production_enabled is None or c.production_enabled is False


# ---------------------------------------------------------------------------
# Score
# ---------------------------------------------------------------------------

class TestScore:
    def test_instantiation(self) -> None:
        s = Score(
            score_id=_uuid(),
            subject_id=_uuid(),
            vyce_score=650,
            niq_score=72,
            score_date=date.today(),
            model_version="v1.0.0",
        )
        assert s.vyce_score == 650
        assert s.niq_score == 72

    def test_check_constraints_exist(self) -> None:
        """Verify that CHECK constraints are registered on the table."""
        table = Score.__table__
        constraint_names = {c.name for c in table.constraints if hasattr(c, "name") and c.name}
        assert "ck_scores_vyce_score_range" in constraint_names
        assert "ck_scores_niq_score_range" in constraint_names

    def test_composite_index_exists(self) -> None:
        table = Score.__table__
        index_names = {idx.name for idx in table.indexes}
        assert "ix_scores_subject_score_date" in index_names

    def test_prediction_horizon_default(self) -> None:
        s = Score(
            score_id=_uuid(),
            subject_id=_uuid(),
            vyce_score=500,
            score_date=date.today(),
            model_version="v1.0.0",
        )
        # Python-side default
        assert s.prediction_horizon is None or s.prediction_horizon == 12


# ---------------------------------------------------------------------------
# RiskDriver
# ---------------------------------------------------------------------------

class TestRiskDriver:
    def test_instantiation(self) -> None:
        rd = RiskDriver(
            driver_id=_uuid(),
            score_id=_uuid(),
            rank=1,
            factor_name="Low transaction diversity",
            impact=ImpactDirection.NEGATIVE,
            shap_value=Decimal("-0.234567"),
            feature_name="UTDI",
        )
        assert rd.rank == 1
        assert rd.impact == ImpactDirection.NEGATIVE

    def test_impact_enum_values(self) -> None:
        assert ImpactDirection.POSITIVE.value == "POSITIVE"
        assert ImpactDirection.NEGATIVE.value == "NEGATIVE"
        assert len(ImpactDirection) == 2

    def test_rank_check_constraint_exists(self) -> None:
        table = RiskDriver.__table__
        constraint_names = {c.name for c in table.constraints if hasattr(c, "name") and c.name}
        assert "ck_risk_drivers_rank_range" in constraint_names


# ---------------------------------------------------------------------------
# Feature
# ---------------------------------------------------------------------------

class TestFeature:
    def test_instantiation(self) -> None:
        f = Feature(
            feature_id=_uuid(),
            subject_id=_uuid(),
            feature_date=date.today(),
            feature_name="CBLRI",
            feature_value=Decimal("0.875432"),
            feature_category="TRANSACTION",
            data_source="VYCEPAY",
            quality_score=Decimal("0.95"),
        )
        assert f.feature_name == "CBLRI"
        assert f.feature_value == Decimal("0.875432")

    def test_quality_score_check_constraint_exists(self) -> None:
        table = Feature.__table__
        constraint_names = {c.name for c in table.constraints if hasattr(c, "name") and c.name}
        assert "ck_features_quality_score_range" in constraint_names

    def test_composite_index_exists(self) -> None:
        table = Feature.__table__
        index_names = {idx.name for idx in table.indexes}
        assert "ix_features_subject_feature_date" in index_names


# ---------------------------------------------------------------------------
# ApiRequestLog
# ---------------------------------------------------------------------------

class TestApiRequestLog:
    def test_instantiation(self) -> None:
        log = ApiRequestLog(
            log_id=_uuid(),
            customer_id=_uuid(),
            endpoint="/v1/scores/lite/12345",
            response_status=200,
            response_time_ms=42,
        )
        assert log.endpoint == "/v1/scores/lite/12345"
        assert log.response_status == 200

    def test_composite_index_exists(self) -> None:
        table = ApiRequestLog.__table__
        index_names = {idx.name for idx in table.indexes}
        assert "ix_api_request_logs_customer_request_time" in index_names

    def test_query_cost_default(self) -> None:
        log = ApiRequestLog(
            log_id=_uuid(),
            customer_id=_uuid(),
            endpoint="/v1/scores/pro/12345",
            response_status=200,
        )
        assert log.query_cost is None or log.query_cost == 1


# ---------------------------------------------------------------------------
# KPISnapshot
# ---------------------------------------------------------------------------

class TestKPISnapshot:
    def test_instantiation(self) -> None:
        kpi = KPISnapshot(
            kpi_id="auc_roc",
            kpi_name="Model AUC-ROC",
            snapshot_date=date.today(),
            snapshot_period=SnapshotPeriod.DAILY,
            value=Decimal("0.782000"),
            unit="ratio",
            target=Decimal("0.750000"),
            status="meeting_target",
        )
        assert kpi.kpi_id == "auc_roc"
        assert kpi.value == Decimal("0.782000")

    def test_snapshot_period_enum_values(self) -> None:
        assert set(SnapshotPeriod) == {
            SnapshotPeriod.HOURLY,
            SnapshotPeriod.DAILY,
            SnapshotPeriod.WEEKLY,
            SnapshotPeriod.MONTHLY,
        }


# ---------------------------------------------------------------------------
# Legacy models — smoke tests
# ---------------------------------------------------------------------------

class TestUser:
    def test_instantiation(self) -> None:
        u = User(
            user_id=_uuid(),
            email="admin@vycescore.co.ke",
            password_hash="hashed",
            full_name="Admin User",
            role=UserRole.ADMIN,
        )
        assert u.role == UserRole.ADMIN

    def test_user_role_enum_values(self) -> None:
        assert len(UserRole) == 4


class TestLoanFeedback:
    def test_instantiation(self) -> None:
        fb = LoanFeedback(
            id=_uuid(),
            national_id_hash="d" * 64,
            loan_outcome="default",
            dpd=95,
            partner_id="equity_bank",
        )
        assert fb.dpd == 95


# ---------------------------------------------------------------------------
# Metadata completeness
# ---------------------------------------------------------------------------

class TestMetadata:
    def test_all_tables_registered(self) -> None:
        """Every expected table name is present in Base.metadata."""
        table_names = set(Base.metadata.tables.keys())
        expected = {
            "subjects",
            "customers",
            "scores",
            "risk_drivers",
            "features",
            "api_request_logs",
            "kpi_snapshots",
            "users",
            "loan_feedback",
        }
        assert expected.issubset(table_names), f"Missing tables: {expected - table_names}"
