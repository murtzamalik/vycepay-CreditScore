"""User ORM model with RBAC roles for admin portal authentication."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, Integer, String
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class UserRole(str, enum.Enum):
    """RBAC roles supported by VyceScore."""

    ADMIN = "Admin"
    OPERATOR = "Operator"
    PARTNER = "Partner"
    READ_ONLY = "ReadOnly"


class User(TimestampMixin, Base):
    """An admin portal user with role-based access control."""

    __tablename__ = "users"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
    )
    email: Mapped[str] = mapped_column(
        String(255), unique=True, index=True, nullable=False,
    )
    password_hash: Mapped[str] = mapped_column(
        String(255), nullable=False,
    )
    full_name: Mapped[str] = mapped_column(
        String(200), nullable=False,
    )
    role: Mapped[UserRole] = mapped_column(
        Enum(
            UserRole,
            name="user_role",
            create_constraint=False,
            values_callable=lambda e: [m.value for m in e],
        ),
        default=UserRole.READ_ONLY,
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true", nullable=False,
    )
    failed_login_attempts: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False,
    )
    locked_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    last_login: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    must_change_password: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true", nullable=False,
    )

    # --- MFA fields (Phase 12.7) ---
    mfa_enabled: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False,
        comment="Whether TOTP MFA is active for this user",
    )
    mfa_secret: Mapped[str | None] = mapped_column(
        String(512), nullable=True,
        comment="Encrypted TOTP secret (base32). Null if MFA not set up.",
    )
    mfa_backup_codes: Mapped[list[str] | None] = mapped_column(
        ARRAY(String(64)), nullable=True,
        comment="SHA-256 hashed backup codes for MFA recovery",
    )

    def __repr__(self) -> str:
        return f"<User {self.user_id} email={self.email!r} role={self.role.value}>"
