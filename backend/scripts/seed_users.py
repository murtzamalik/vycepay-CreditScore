"""Seed script to create test users for UAT testing.

DETERMINISTIC: This script produces identical data on every run. All UUIDs,
password hashes, and timestamps are fixed so that a fresh database always
matches the values referenced in docs/UAT_Testing_Document.md.

Run from the backend directory:
    python -m scripts.seed_users
"""

from __future__ import annotations

import asyncio
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

# Ensure the backend package is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.database import async_session_factory, engine
from app.models.user import User, UserRole

# ---------------------------------------------------------------------------
# Fixed namespace for deterministic UUID generation (uuid5)
# ---------------------------------------------------------------------------
_SEED_NS = uuid.UUID("a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d")


def _user_uuid(email: str) -> uuid.UUID:
    """Derive a deterministic UUID from a user email."""
    return uuid.uuid5(_SEED_NS, f"user:{email}")


# ---------------------------------------------------------------------------
# Fixed bcrypt hashes (pre-computed once with a fixed salt so every run is
# identical).  To regenerate:
#   import bcrypt; salt = bcrypt.gensalt(rounds=12)
#   for pw in ["Admin@2026", ...]:
#       print(bcrypt.hashpw(pw.encode(), salt).decode())
# The salt below is $2b$12$XDtd2Z9TPw4EgYLCpyskG.
# ---------------------------------------------------------------------------
_PASSWORD_HASHES = {
    "Admin@2026": "$2b$12$XDtd2Z9TPw4EgYLCpyskG.FsPm6wjDAjfvUU4GdNu2eRpy2PBOFv6",
    "Operator@2026": "$2b$12$XDtd2Z9TPw4EgYLCpyskG.coszXdzK1/9xiKe.s2Akk1VzMnMVDBi",
    "Partner@2026": "$2b$12$XDtd2Z9TPw4EgYLCpyskG.mOhjp9NBAKMzml2nb8/kswG.hSRVGGK",
    "ReadOnly@2026": "$2b$12$XDtd2Z9TPw4EgYLCpyskG.KqnRkrMHe0768UW.e6QEWr7okfhIb2a",
}

# Fixed timestamp for all seed records
_SEED_TS = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)


SEED_USERS = [
    {
        "user_id": _user_uuid("admin@vycepay.com"),
        "email": "admin@vycepay.com",
        "full_name": "James Mwangi",
        "role": UserRole.ADMIN,
        "password": "Admin@2026",
    },
    {
        "user_id": _user_uuid("operator@vycepay.com"),
        "email": "operator@vycepay.com",
        "full_name": "Odhiambo Ochieng",
        "role": UserRole.OPERATOR,
        "password": "Operator@2026",
    },
    {
        "user_id": _user_uuid("partner@equitybank.co.ke"),
        "email": "partner@equitybank.co.ke",
        "full_name": "Wanjiku Kamau",
        "role": UserRole.PARTNER,
        "password": "Partner@2026",
    },
    {
        "user_id": _user_uuid("readonly@kcbgroup.com"),
        "email": "readonly@kcbgroup.com",
        "full_name": "Amina Hassan",
        "role": UserRole.READ_ONLY,
        "password": "ReadOnly@2026",
    },
]


async def seed() -> None:
    async with async_session_factory() as session:
        for u in SEED_USERS:
            # Use upsert: INSERT … ON CONFLICT (email) DO UPDATE
            password_hash = _PASSWORD_HASHES[u["password"]]
            values = {
                "user_id": u["user_id"],
                "email": u["email"],
                "full_name": u["full_name"],
                "role": u["role"],
                "password_hash": password_hash,
                "is_active": True,
                "must_change_password": False,
                "failed_login_attempts": 0,
                "mfa_enabled": False,
                "created_at": _SEED_TS,
                "updated_at": _SEED_TS,
            }

            stmt = pg_insert(User).values(**values)
            stmt = stmt.on_conflict_do_update(
                index_elements=["email"],
                set_={
                    "user_id": stmt.excluded.user_id,
                    "full_name": stmt.excluded.full_name,
                    "role": stmt.excluded.role,
                    "password_hash": stmt.excluded.password_hash,
                    "is_active": stmt.excluded.is_active,
                    "must_change_password": stmt.excluded.must_change_password,
                    "updated_at": _SEED_TS,
                },
            )
            await session.execute(stmt)
            print(f"  UPSERT {u['email']} / {u['password']}  role={u['role'].value}  id={u['user_id']}")

        await session.commit()
    await engine.dispose()
    print("\nDone. All UAT users are ready (deterministic IDs).")


if __name__ == "__main__":
    print("Seeding UAT test users (deterministic)...\n")
    asyncio.run(seed())
