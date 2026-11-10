"""Seed UAT test data into the VyceScore database.

Run from the backend directory with the venv activated:
    cd backend
    .venv/Scripts/activate
    $env:PYTHONPATH = "."
    python ../uat_seed.py

Creates:
    - 1 Admin user      (admin@vycescore.co.ke / Admin123!@#)
    - 1 Partner customer (Test Bank Kenya) with API key
    - 3 Subjects with scores, features, and risk drivers
    - Prints credentials for use in UAT testing
"""

import hashlib
import uuid
from datetime import date, timedelta

import bcrypt
from sqlalchemy import create_engine, text

DB_URL = "postgresql://vycescore:vycescore_dev@localhost:5432/vycescore"
engine = create_engine(DB_URL)

# ── Credentials ──────────────────────────────────────────────────────────────

ADMIN_EMAIL = "admin@vycescore.co.ke"
ADMIN_PASSWORD = "Admin123!@#"
ADMIN_NAME = "VyceScore Admin"

API_KEY = "vyc_uat_partner_key_testbank_2026"
CUSTOMER_NAME = "Test Bank Kenya"

# National IDs for test subjects
SUBJECTS = [
    {
        "national_id": "30012345",
        "type": "INDIVIDUAL",
        "score": 720,
        "niq": 75,
        "risk_level": "Low Risk",
        "drivers": [
            (1, "Cross-Border Liquidity", "POSITIVE", "Strong international cash flow from remittances", 0.23, "CBLRI"),
            (2, "Transaction Diversity", "POSITIVE", "Active across 12 merchant categories", 0.18, "UTDI"),
            (3, "Geographic Stability", "NEGATIVE", "Moderate location variance in transactions", -0.12, "GOS_INDEX"),
        ],
    },
    {
        "national_id": "30067890",
        "type": "BUSINESS",
        "score": 480,
        "niq": 35,
        "risk_level": "High Risk",
        "drivers": [
            (1, "Supply Chain Formalization", "NEGATIVE", "Low digitized supplier-buyer links", -0.31, "SCFV"),
            (2, "Documentation Compliance", "NEGATIVE", "Only 40% of operational tasks completed", -0.22, "DDC_RATIO"),
            (3, "Network Quality", "NEGATIVE", "Trading partners have low average scores", -0.15, "NIQ_SCORE"),
        ],
    },
    {
        "national_id": "30099999",
        "type": "INDIVIDUAL",
        "score": 600,
        "niq": 55,
        "risk_level": "Medium Risk",
        "drivers": [
            (1, "Transaction Diversity", "POSITIVE", "Growing merchant category diversity", 0.14, "UTDI"),
            (2, "Geographic Stability", "POSITIVE", "Stable transaction locations", 0.11, "GOS_INDEX"),
            (3, "Cross-Border Liquidity", "NEGATIVE", "Irregular international cash flow", -0.09, "CBLRI"),
        ],
    },
]


def hash_api_key(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def hash_national_id(nid: str) -> str:
    return hashlib.sha256(nid.encode()).hexdigest()


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def main():
    with engine.connect() as conn:
        # ── 1. Admin User ────────────────────────────────────────────────
        # Check if admin already exists
        existing = conn.execute(
            text("SELECT user_id FROM users WHERE email = :email"),
            {"email": ADMIN_EMAIL},
        ).fetchone()

        if existing:
            print(f"  Admin user already exists: {ADMIN_EMAIL}")
        else:
            user_id = str(uuid.uuid4())
            pw_hash = hash_password(ADMIN_PASSWORD)
            conn.execute(
                text("""
                    INSERT INTO users (user_id, email, password_hash, full_name, role,
                                       is_active, must_change_password, created_at, updated_at)
                    VALUES (:uid, :email, :pw, :name, 'Admin', true, false, now(), now())
                """),
                {"uid": user_id, "email": ADMIN_EMAIL, "pw": pw_hash, "name": ADMIN_NAME},
            )
            print(f"  Created admin user: {ADMIN_EMAIL}")

        # ── 2. Partner Customer ──────────────────────────────────────────
        key_hash = hash_api_key(API_KEY)
        existing = conn.execute(
            text("SELECT customer_id FROM customers WHERE api_key_hash = :h"),
            {"h": key_hash},
        ).fetchone()

        if existing:
            customer_id = str(existing[0])
            print(f"  Customer already exists: {CUSTOMER_NAME}")
        else:
            customer_id = str(uuid.uuid4())
            conn.execute(
                text("""
                    INSERT INTO customers (customer_id, name, contact_email, license_tier, status,
                                           api_key_hash, monthly_query_limit, created_at,
                                           sandbox_enabled, production_enabled)
                    VALUES (:cid, :name, 'partner@testbank.co.ke', 'PRO', 'ACTIVE',
                            :hash, 10000, now(), true, true)
                """),
                {"cid": customer_id, "name": CUSTOMER_NAME, "hash": key_hash},
            )
            print(f"  Created customer: {CUSTOMER_NAME}")

        # ── 3. Subjects, Features, Scores, Risk Drivers ──────────────────
        today = date.today()
        for subj in SUBJECTS:
            nid = subj["national_id"]
            id_hash = hash_national_id(nid)

            existing = conn.execute(
                text("SELECT subject_id FROM subjects WHERE id_hash = :h"),
                {"h": id_hash},
            ).fetchone()

            if existing:
                print(f"  Subject {nid} already exists")
                continue

            subject_id = str(uuid.uuid4())
            score_id = str(uuid.uuid4())

            # Subject
            conn.execute(
                text("""
                    INSERT INTO subjects (subject_id, subject_type, id_hash, kyc_status, aml_status,
                                          created_at, updated_at)
                    VALUES (:sid, :stype, :hash, 'VERIFIED', 'CLEAR', now(), now())
                """),
                {"sid": subject_id, "stype": subj["type"], "hash": id_hash},
            )

            # Features
            features = [
                ("CBLRI", 0.72, "transaction", "vycepay"),
                ("UTDI", 0.65, "transaction", "vycepay"),
                ("SCFV", 0.58, "supply_chain", "vycetrade"),
                ("DDC_RATIO", 0.81, "compliance", "vycetrade"),
                ("NIQ_SCORE", float(subj["niq"]), "network", "vycepay"),
                ("GOS_INDEX", 0.44, "geographic", "vycepay"),
            ]
            for fname, fval, fcat, src in features:
                conn.execute(
                    text("""
                        INSERT INTO features (feature_id, subject_id, feature_date, feature_name,
                                              feature_value, feature_category, data_source, quality_score)
                        VALUES (:fid, :sid, :fd, :fn, :fv, :fc, :src, 0.95)
                    """),
                    {
                        "fid": str(uuid.uuid4()), "sid": subject_id,
                        "fd": today.isoformat(), "fn": fname, "fv": fval,
                        "fc": fcat, "src": src,
                    },
                )

            # Score
            lower = max(300, subj["score"] - 40)
            upper = min(900, subj["score"] + 40)
            conn.execute(
                text("""
                    INSERT INTO scores (score_id, subject_id, vyce_score, niq_score, score_date,
                                        model_version, prediction_horizon, confidence_lower,
                                        confidence_upper, created_at)
                    VALUES (:scid, :sid, :score, :niq, :sd, 'v1.0.0', 12, :lo, :hi, now())
                """),
                {
                    "scid": score_id, "sid": subject_id,
                    "score": subj["score"], "niq": subj["niq"],
                    "sd": today.isoformat(), "lo": lower, "hi": upper,
                },
            )

            # Risk drivers
            for rank, fname, impact, desc, shap, feature in subj["drivers"]:
                conn.execute(
                    text("""
                        INSERT INTO risk_drivers (driver_id, score_id, rank, factor_name, impact,
                                                  description, shap_value, feature_name)
                        VALUES (:did, :scid, :rank, :fn, :imp, :desc, :shap, :feat)
                    """),
                    {
                        "did": str(uuid.uuid4()), "scid": score_id,
                        "rank": rank, "fn": fname, "imp": impact,
                        "desc": desc, "shap": shap, "feat": feature,
                    },
                )

            print(f"  Created subject {nid} ({subj['type']}) — Score: {subj['score']}, NIQ: {subj['niq']}")

        conn.commit()

    # ── Print credentials ────────────────────────────────────────────────
    print()
    print("=" * 60)
    print("  UAT TEST CREDENTIALS")
    print("=" * 60)
    print()
    print("  ADMIN PORTAL (JWT Auth)")
    print(f"    Email:    {ADMIN_EMAIL}")
    print(f"    Password: {ADMIN_PASSWORD}")
    print()
    print("  PARTNER API (API Key Auth)")
    print(f"    X-API-Key: {API_KEY}")
    print(f"    Customer:  {CUSTOMER_NAME}")
    print()
    print("  TEST SUBJECTS (National IDs)")
    for s in SUBJECTS:
        print(f"    {s['national_id']}  ({s['type']})  Score={s['score']}  NIQ={s['niq']}  [{s['risk_level']}]")
    print()
    print("=" * 60)


if __name__ == "__main__":
    print()
    print("Seeding UAT data...")
    print()
    main()
