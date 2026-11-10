"""SQLAlchemy ORM models — all domain entities for VyceScore.

Importing this module ensures every model is registered with
:pydata:`Base.metadata`, which Alembic needs for ``--autogenerate``.
"""

from app.models.base import Base, TimestampMixin  # noqa: F401

# Domain entities (BRD §11)
from app.models.subject import AMLStatus, KYCStatus, Subject, SubjectType  # noqa: F401
from app.models.customer import Customer, CustomerStatus, LicenseTier  # noqa: F401
from app.models.score import Score  # noqa: F401
from app.models.risk_driver import ImpactDirection, RiskDriver  # noqa: F401
from app.models.feature import Feature  # noqa: F401
from app.models.api_request_log import ApiRequestLog  # noqa: F401
from app.models.kpi_snapshot import KPISnapshot, SnapshotPeriod  # noqa: F401

# Auth / supporting models
from app.models.user import User, UserRole  # noqa: F401
from app.models.feedback import LoanFeedback  # noqa: F401
from app.models.batch_job import BatchApiTier, BatchJob, BatchJobStatus  # noqa: F401
from app.models.compliance_check import (  # noqa: F401
    ComplianceCheck,
    ComplianceCheckStatus,
    ComplianceCheckType,
)
from app.models.audit_log import AuditLog, AuditLogCategory  # noqa: F401
