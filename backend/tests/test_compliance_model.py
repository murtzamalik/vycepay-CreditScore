"""Tests for ComplianceCheck model (Phase 15.3)."""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock

from app.models.compliance_check import (
    ComplianceCheck,
    ComplianceCheckStatus,
    ComplianceCheckType,
)


class TestComplianceCheckModel:
    def test_enum_values(self) -> None:
        """Test ComplianceCheckType enum values."""
        assert ComplianceCheckType.KYC.value == "KYC"
        assert ComplianceCheckType.AML.value == "AML"

    def test_status_enum_values(self) -> None:
        """Test ComplianceCheckStatus enum values."""
        assert ComplianceCheckStatus.PASSED.value == "PASSED"
        assert ComplianceCheckStatus.FAILED.value == "FAILED"
        assert ComplianceCheckStatus.PENDING.value == "PENDING"
        assert ComplianceCheckStatus.REVIEW.value == "REVIEW"

    def test_tablename(self) -> None:
        """Test table name is correctly set."""
        assert ComplianceCheck.__tablename__ == "compliance_checks"

    def test_check_type_enum_members(self) -> None:
        """Test all expected enum members exist."""
        assert len(ComplianceCheckType) == 2
        assert ComplianceCheckType.KYC in ComplianceCheckType
        assert ComplianceCheckType.AML in ComplianceCheckType

    def test_check_status_enum_members(self) -> None:
        """Test all expected status enum members exist."""
        assert len(ComplianceCheckStatus) == 4
        assert ComplianceCheckStatus.PASSED in ComplianceCheckStatus
        assert ComplianceCheckStatus.FAILED in ComplianceCheckStatus
        assert ComplianceCheckStatus.PENDING in ComplianceCheckStatus
        assert ComplianceCheckStatus.REVIEW in ComplianceCheckStatus
