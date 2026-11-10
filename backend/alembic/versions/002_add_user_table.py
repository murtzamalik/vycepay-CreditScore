"""Add extended user table columns for auth lockout and password management.

Revision ID: 002_add_user_table
Revises: 001_initial_schema
Create Date: 2026-03-08

This migration alters the ``users`` table created in 001 to match the
expanded User model required by the authentication system:
  - Rename ``id`` -> ``user_id``
  - Rename ``hashed_password`` -> ``password_hash``
  - Add ``full_name`` (VARCHAR 200, NOT NULL, default '')
  - Add ``failed_login_attempts`` (INTEGER, default 0)
  - Add ``locked_until`` (TIMESTAMP WITH TIME ZONE, nullable)
  - Add ``last_login`` (TIMESTAMP WITH TIME ZONE, nullable)
  - Add ``must_change_password`` (BOOLEAN, default TRUE)
  - Drop ``api_key`` column (API keys are now on customers table only)
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers
revision: str = "002_add_user_table"
down_revision: str = "001_initial_schema"
branch_labels: tuple[str, ...] | None = None
depends_on: str | None = None


def upgrade() -> None:
    # Rename PK column id -> user_id
    op.alter_column("users", "id", new_column_name="user_id")

    # Rename hashed_password -> password_hash and widen
    op.alter_column(
        "users",
        "hashed_password",
        new_column_name="password_hash",
        type_=sa.String(255),
        existing_type=sa.String(128),
        existing_nullable=False,
    )

    # Widen email column to 255
    op.alter_column(
        "users",
        "email",
        type_=sa.String(255),
        existing_type=sa.String(320),
        existing_nullable=False,
    )

    # Add full_name — required, but backfill existing rows with empty string
    op.add_column(
        "users",
        sa.Column("full_name", sa.String(200), nullable=False, server_default=""),
    )

    # Add lockout and tracking columns
    op.add_column(
        "users",
        sa.Column("failed_login_attempts", sa.Integer, nullable=False, server_default="0"),
    )
    op.add_column(
        "users",
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("last_login", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("must_change_password", sa.Boolean, nullable=False, server_default="true"),
    )

    # Drop the api_key column (API keys live on customers table)
    op.drop_index("ix_users_api_key", table_name="users")
    op.drop_column("users", "api_key")


def downgrade() -> None:
    # Re-add api_key column
    op.add_column(
        "users",
        sa.Column("api_key", sa.String(64), nullable=True, unique=True),
    )
    op.create_index("ix_users_api_key", "users", ["api_key"], unique=True)

    # Drop new columns
    op.drop_column("users", "must_change_password")
    op.drop_column("users", "last_login")
    op.drop_column("users", "locked_until")
    op.drop_column("users", "failed_login_attempts")
    op.drop_column("users", "full_name")

    # Rename back
    op.alter_column(
        "users",
        "email",
        type_=sa.String(320),
        existing_type=sa.String(255),
        existing_nullable=False,
    )
    op.alter_column(
        "users",
        "password_hash",
        new_column_name="hashed_password",
        type_=sa.String(128),
        existing_type=sa.String(255),
        existing_nullable=False,
    )
    op.alter_column("users", "user_id", new_column_name="id")
