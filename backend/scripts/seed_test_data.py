"""Seed script to create test subjects, scores, features, risk drivers, and customers for UAT.

DETERMINISTIC: This script produces identical data on every run. All UUIDs are
derived via uuid5 from a fixed namespace, timestamps are fixed, and no random
values are used. Running this script against an empty DB or an existing DB with
prior seed data will always converge to the same state.

Run from the backend directory:
    python -m scripts.seed_test_data
"""

from __future__ import annotations

import asyncio
import sys
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.database import async_session_factory, engine
from app.services.auth_service import AuthService
from app.services.id_hasher import hash_national_id

# ---------------------------------------------------------------------------
# Deterministic UUID helpers
# ---------------------------------------------------------------------------
_SEED_NS = uuid.UUID("a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d")

# Fixed timestamp for all seed records
_SEED_TS = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)


def _customer_uuid(name: str) -> uuid.UUID:
    return uuid.uuid5(_SEED_NS, f"customer:{name}")


def _subject_uuid(national_id: str) -> uuid.UUID:
    return uuid.uuid5(_SEED_NS, f"subject:{national_id}")


def _score_uuid(national_id: str, score_date: date) -> uuid.UUID:
    return uuid.uuid5(_SEED_NS, f"score:{national_id}:{score_date.isoformat()}")


def _feature_uuid(national_id: str, feature_name: str, feature_date: date) -> uuid.UUID:
    return uuid.uuid5(_SEED_NS, f"feature:{national_id}:{feature_name}:{feature_date.isoformat()}")


def _risk_driver_uuid(national_id: str, score_date: date, rank: int) -> uuid.UUID:
    return uuid.uuid5(_SEED_NS, f"risk_driver:{national_id}:{score_date.isoformat()}:{rank}")


async def seed() -> None:
    async with async_session_factory() as session:
        # ---------------------------------------------------------------
        # 1. Seed Customers (with known API keys)
        # ---------------------------------------------------------------
        from app.models.customer import Customer, CustomerStatus, LicenseTier

        test_customers = [
            {
                "customer_id": _customer_uuid("Equity Bank Kenya"),
                "name": "Equity Bank Kenya",
                "contact_email": "api@equitybank.co.ke",
                "license_tier": LicenseTier.PRO,
                "status": CustomerStatus.ACTIVE,
                "monthly_query_limit": 100000,
                "api_key_raw": "vyc_test_equity_bank_pro_key_2026",
            },
            {
                "customer_id": _customer_uuid("KCB Group"),
                "name": "KCB Group",
                "contact_email": "integration@kcbgroup.com",
                "license_tier": LicenseTier.DEEP_DIVE,
                "status": CustomerStatus.ACTIVE,
                "monthly_query_limit": 500000,
                "api_key_raw": "vyc_test_kcb_group_enterprise_key_2026",
            },
            {
                "customer_id": _customer_uuid("Safaricom M-Pesa"),
                "name": "Safaricom M-Pesa",
                "contact_email": "partners@safaricom.co.ke",
                "license_tier": LicenseTier.LITE,
                "status": CustomerStatus.ACTIVE,
                "monthly_query_limit": 50000,
                "api_key_raw": "vyc_test_safaricom_lite_key_2026",
            },
            {
                "customer_id": _customer_uuid("Faulu Microfinance"),
                "name": "Faulu Microfinance",
                "contact_email": "tech@faulu.co.ke",
                "license_tier": LicenseTier.LITE,
                "status": CustomerStatus.PENDING,
                "monthly_query_limit": 10000,
                "api_key_raw": None,  # Pending customers have no API key yet
            },
            {
                "customer_id": _customer_uuid("NCBA Bank"),
                "name": "NCBA Bank",
                "contact_email": "digital@ncbagroup.com",
                "license_tier": LicenseTier.PRO,
                "status": CustomerStatus.SUSPENDED,
                "monthly_query_limit": 75000,
                "api_key_raw": None,  # Suspended customers have API key revoked
            },
        ]

        for c in test_customers:
            raw_key = c["api_key_raw"]
            key_hash = AuthService.hash_api_key(raw_key) if raw_key else None

            values = {
                "customer_id": c["customer_id"],
                "name": c["name"],
                "contact_email": c["contact_email"],
                "license_tier": c["license_tier"],
                "status": c["status"],
                "monthly_query_limit": c["monthly_query_limit"],
                "api_key_hash": key_hash,
                "created_at": _SEED_TS,
            }

            stmt = pg_insert(Customer).values(**values)
            stmt = stmt.on_conflict_do_update(
                index_elements=["customer_id"],
                set_={
                    "name": stmt.excluded.name,
                    "contact_email": stmt.excluded.contact_email,
                    "license_tier": stmt.excluded.license_tier,
                    "status": stmt.excluded.status,
                    "monthly_query_limit": stmt.excluded.monthly_query_limit,
                    "api_key_hash": stmt.excluded.api_key_hash,
                },
            )
            await session.execute(stmt)
            key_display = raw_key if raw_key else "(none)"
            print(f"  UPSERT Customer: {c['name']}  id={c['customer_id']}  API Key: {key_display}")

        # ---------------------------------------------------------------
        # 2. Seed Subjects (national IDs)
        # ---------------------------------------------------------------
        from app.models.subject import Subject, SubjectType

        test_subjects = [
            {"national_id": "12345678", "subject_type": SubjectType.INDIVIDUAL},
            {"national_id": "23456789", "subject_type": SubjectType.INDIVIDUAL},
            {"national_id": "34567890", "subject_type": SubjectType.INDIVIDUAL},
            {"national_id": "MSME001", "subject_type": SubjectType.BUSINESS},
            {"national_id": "MSME002", "subject_type": SubjectType.BUSINESS},
        ]

        subject_ids: dict[str, uuid.UUID] = {}
        for s in test_subjects:
            nid = s["national_id"]
            sid = _subject_uuid(nid)
            id_hash = hash_national_id(nid)
            subject_ids[nid] = sid

            values = {
                "subject_id": sid,
                "subject_type": s["subject_type"],
                "id_hash": id_hash,
                "created_at": _SEED_TS,
                "updated_at": _SEED_TS,
            }

            stmt = pg_insert(Subject).values(**values)
            stmt = stmt.on_conflict_do_update(
                index_elements=["subject_id"],
                set_={
                    "subject_type": stmt.excluded.subject_type,
                    "id_hash": stmt.excluded.id_hash,
                    "updated_at": _SEED_TS,
                },
            )
            await session.execute(stmt)
            print(f"  UPSERT Subject: {nid}  id={sid}  hash={id_hash[:16]}...")

        # ---------------------------------------------------------------
        # 3. Seed Scores
        # ---------------------------------------------------------------
        from app.models.score import Score

        test_scores = [
            {"national_id": "12345678", "vyce_score": 720, "niq_score": 78, "score_date": date(2026, 3, 8), "model_version": "v1.0.0", "confidence_lower": 690, "confidence_upper": 750},
            {"national_id": "23456789", "vyce_score": 540, "niq_score": 45, "score_date": date(2026, 3, 8), "model_version": "v1.0.0", "confidence_lower": 510, "confidence_upper": 570},
            {"national_id": "34567890", "vyce_score": 380, "niq_score": 22, "score_date": date(2026, 3, 7), "model_version": "v1.0.0", "confidence_lower": 350, "confidence_upper": 410},
            {"national_id": "MSME001", "vyce_score": 650, "niq_score": 62, "score_date": date(2026, 3, 8), "model_version": "v1.0.0", "confidence_lower": 620, "confidence_upper": 680},
            {"national_id": "MSME002", "vyce_score": 810, "niq_score": 91, "score_date": date(2026, 3, 8), "model_version": "v1.0.0", "confidence_lower": 780, "confidence_upper": 840},
        ]

        score_ids: dict[str, uuid.UUID] = {}
        for sc in test_scores:
            nid = sc["national_id"]
            sid = subject_ids[nid]
            score_id = _score_uuid(nid, sc["score_date"])
            score_ids[nid] = score_id

            values = {
                "score_id": score_id,
                "subject_id": sid,
                "vyce_score": sc["vyce_score"],
                "niq_score": sc["niq_score"],
                "score_date": sc["score_date"],
                "model_version": sc["model_version"],
                "confidence_lower": sc["confidence_lower"],
                "confidence_upper": sc["confidence_upper"],
                "created_at": _SEED_TS,
            }

            stmt = pg_insert(Score).values(**values)
            stmt = stmt.on_conflict_do_update(
                index_elements=["score_id"],
                set_={
                    "vyce_score": stmt.excluded.vyce_score,
                    "niq_score": stmt.excluded.niq_score,
                    "model_version": stmt.excluded.model_version,
                    "confidence_lower": stmt.excluded.confidence_lower,
                    "confidence_upper": stmt.excluded.confidence_upper,
                },
            )
            await session.execute(stmt)
            print(f"  UPSERT Score for {nid}: VyceScore={sc['vyce_score']}, NIQ={sc['niq_score']}  id={score_id}")

        # ---------------------------------------------------------------
        # 4. Seed Risk Drivers (for Pro scores)
        # ---------------------------------------------------------------
        from app.models.risk_driver import ImpactDirection, RiskDriver

        risk_driver_data: dict[str, list[dict]] = {
            "12345678": [
                {"rank": 1, "factor_name": "Cross-Border Liquidity Resilience", "feature_name": "CBLRI", "impact": ImpactDirection.POSITIVE, "shap_value": Decimal("0.045"), "description": "Consistent international transaction patterns indicate stable cross-border income"},
                {"rank": 2, "factor_name": "Supply Chain Formalization", "feature_name": "SCFV", "impact": ImpactDirection.POSITIVE, "shap_value": Decimal("0.032"), "description": "Growing number of digitized supplier-buyer relationships via VyceTrade"},
                {"rank": 3, "factor_name": "Digital Documentation Compliance", "feature_name": "DDC", "impact": ImpactDirection.NEGATIVE, "shap_value": Decimal("-0.018"), "description": "Below-average operational task completion rate in the last quarter"},
            ],
            "23456789": [
                {"rank": 1, "factor_name": "Geographic Operational Stability", "feature_name": "GOS", "impact": ImpactDirection.NEGATIVE, "shap_value": Decimal("-0.052"), "description": "High variance in transaction endpoint locations suggests operational instability"},
                {"rank": 2, "factor_name": "Network Interdependence Quality", "feature_name": "NIQ", "impact": ImpactDirection.NEGATIVE, "shap_value": Decimal("-0.038"), "description": "Trading partners have below-average VyceScores"},
                {"rank": 3, "factor_name": "Utility Transactional Diversity", "feature_name": "UTDI", "impact": ImpactDirection.POSITIVE, "shap_value": Decimal("0.021"), "description": "Moderate merchant category diversity in recent quarters"},
            ],
            "MSME001": [
                {"rank": 1, "factor_name": "Supply Chain Formalization", "feature_name": "SCFV", "impact": ImpactDirection.POSITIVE, "shap_value": Decimal("0.067"), "description": "Rapidly growing digitized supplier network"},
                {"rank": 2, "factor_name": "Cross-Border Liquidity Resilience", "feature_name": "CBLRI", "impact": ImpactDirection.POSITIVE, "shap_value": Decimal("0.041"), "description": "Stable cross-border payment patterns"},
                {"rank": 3, "factor_name": "Geographic Operational Stability", "feature_name": "GOS", "impact": ImpactDirection.NEGATIVE, "shap_value": Decimal("-0.015"), "description": "Minor fluctuations in operational geography"},
            ],
        }

        for nid, drivers in risk_driver_data.items():
            # Look up the score_date for this national ID to derive deterministic UUIDs
            score_date = next(sc["score_date"] for sc in test_scores if sc["national_id"] == nid)
            score_id = score_ids[nid]

            for d in drivers:
                driver_id = _risk_driver_uuid(nid, score_date, d["rank"])
                values = {
                    "driver_id": driver_id,
                    "score_id": score_id,
                    "rank": d["rank"],
                    "factor_name": d["factor_name"],
                    "feature_name": d["feature_name"],
                    "impact": d["impact"],
                    "shap_value": d["shap_value"],
                    "description": d["description"],
                }

                stmt = pg_insert(RiskDriver).values(**values)
                stmt = stmt.on_conflict_do_update(
                    index_elements=["driver_id"],
                    set_={
                        "factor_name": stmt.excluded.factor_name,
                        "feature_name": stmt.excluded.feature_name,
                        "impact": stmt.excluded.impact,
                        "shap_value": stmt.excluded.shap_value,
                        "description": stmt.excluded.description,
                    },
                )
                await session.execute(stmt)
            print(f"  UPSERT {len(drivers)} risk drivers for {nid}")

        # ---------------------------------------------------------------
        # 5. Seed Features
        # ---------------------------------------------------------------
        from app.models.feature import Feature

        _FEATURE_DATE = date(2026, 3, 8)

        feature_data: dict[str, list[dict]] = {
            "12345678": [
                {"feature_name": "CBLRI", "feature_value": Decimal("0.82"), "feature_category": "liquidity", "data_source": "VycePay"},
                {"feature_name": "UTDI", "feature_value": Decimal("0.65"), "feature_category": "diversity", "data_source": "VycePay"},
                {"feature_name": "SCFV", "feature_value": Decimal("0.71"), "feature_category": "supply_chain", "data_source": "VyceTrade"},
                {"feature_name": "DDC", "feature_value": Decimal("0.58"), "feature_category": "compliance", "data_source": "VycePay"},
                {"feature_name": "NIQ", "feature_value": Decimal("78.00"), "feature_category": "network", "data_source": "VyceScore"},
                {"feature_name": "GOS", "feature_value": Decimal("0.88"), "feature_category": "geographic", "data_source": "VycePay"},
            ],
        }

        for nid, features in feature_data.items():
            sid = subject_ids[nid]

            for f in features:
                fid = _feature_uuid(nid, f["feature_name"], _FEATURE_DATE)
                values = {
                    "feature_id": fid,
                    "subject_id": sid,
                    "feature_date": _FEATURE_DATE,
                    "feature_name": f["feature_name"],
                    "feature_value": f["feature_value"],
                    "feature_category": f["feature_category"],
                    "data_source": f["data_source"],
                    "quality_score": Decimal("0.95"),
                }

                stmt = pg_insert(Feature).values(**values)
                stmt = stmt.on_conflict_do_update(
                    index_elements=["feature_id"],
                    set_={
                        "feature_value": stmt.excluded.feature_value,
                        "feature_category": stmt.excluded.feature_category,
                        "data_source": stmt.excluded.data_source,
                        "quality_score": stmt.excluded.quality_score,
                    },
                )
                await session.execute(stmt)
            print(f"  UPSERT {len(features)} features for {nid}")

        # ---------------------------------------------------------------
        # 6. Seed Score History (12 months of monthly scores per subject)
        # ---------------------------------------------------------------
        # Realistic score trajectories over 12 months (oldest -> newest).
        # Each list has 12 entries representing monthly scores leading up
        # to the current score already seeded in section 3.
        score_history_data: dict[str, list[dict]] = {
            "12345678": [  # Improving individual: 620 -> 720
                {"vyce_score": 620, "niq_score": 55, "confidence_lower": 590, "confidence_upper": 650},
                {"vyce_score": 635, "niq_score": 58, "confidence_lower": 605, "confidence_upper": 665},
                {"vyce_score": 640, "niq_score": 60, "confidence_lower": 610, "confidence_upper": 670},
                {"vyce_score": 648, "niq_score": 61, "confidence_lower": 618, "confidence_upper": 678},
                {"vyce_score": 660, "niq_score": 63, "confidence_lower": 630, "confidence_upper": 690},
                {"vyce_score": 665, "niq_score": 65, "confidence_lower": 635, "confidence_upper": 695},
                {"vyce_score": 672, "niq_score": 67, "confidence_lower": 642, "confidence_upper": 702},
                {"vyce_score": 685, "niq_score": 69, "confidence_lower": 655, "confidence_upper": 715},
                {"vyce_score": 690, "niq_score": 71, "confidence_lower": 660, "confidence_upper": 720},
                {"vyce_score": 700, "niq_score": 73, "confidence_lower": 670, "confidence_upper": 730},
                {"vyce_score": 708, "niq_score": 75, "confidence_lower": 678, "confidence_upper": 738},
                {"vyce_score": 715, "niq_score": 77, "confidence_lower": 685, "confidence_upper": 745},
            ],
            "23456789": [  # Declining individual: 640 -> 540
                {"vyce_score": 640, "niq_score": 62, "confidence_lower": 610, "confidence_upper": 670},
                {"vyce_score": 630, "niq_score": 60, "confidence_lower": 600, "confidence_upper": 660},
                {"vyce_score": 618, "niq_score": 58, "confidence_lower": 588, "confidence_upper": 648},
                {"vyce_score": 610, "niq_score": 56, "confidence_lower": 580, "confidence_upper": 640},
                {"vyce_score": 600, "niq_score": 54, "confidence_lower": 570, "confidence_upper": 630},
                {"vyce_score": 592, "niq_score": 53, "confidence_lower": 562, "confidence_upper": 622},
                {"vyce_score": 585, "niq_score": 51, "confidence_lower": 555, "confidence_upper": 615},
                {"vyce_score": 575, "niq_score": 50, "confidence_lower": 545, "confidence_upper": 605},
                {"vyce_score": 568, "niq_score": 49, "confidence_lower": 538, "confidence_upper": 598},
                {"vyce_score": 560, "niq_score": 48, "confidence_lower": 530, "confidence_upper": 590},
                {"vyce_score": 552, "niq_score": 46, "confidence_lower": 522, "confidence_upper": 582},
                {"vyce_score": 545, "niq_score": 45, "confidence_lower": 515, "confidence_upper": 575},
            ],
            "34567890": [  # Volatile high-risk individual: ~380 with swings
                {"vyce_score": 410, "niq_score": 28, "confidence_lower": 380, "confidence_upper": 440},
                {"vyce_score": 395, "niq_score": 25, "confidence_lower": 365, "confidence_upper": 425},
                {"vyce_score": 420, "niq_score": 30, "confidence_lower": 390, "confidence_upper": 450},
                {"vyce_score": 385, "niq_score": 23, "confidence_lower": 355, "confidence_upper": 415},
                {"vyce_score": 370, "niq_score": 20, "confidence_lower": 340, "confidence_upper": 400},
                {"vyce_score": 390, "niq_score": 24, "confidence_lower": 360, "confidence_upper": 420},
                {"vyce_score": 365, "niq_score": 19, "confidence_lower": 335, "confidence_upper": 395},
                {"vyce_score": 380, "niq_score": 22, "confidence_lower": 350, "confidence_upper": 410},
                {"vyce_score": 355, "niq_score": 18, "confidence_lower": 325, "confidence_upper": 385},
                {"vyce_score": 370, "niq_score": 20, "confidence_lower": 340, "confidence_upper": 400},
                {"vyce_score": 385, "niq_score": 23, "confidence_lower": 355, "confidence_upper": 415},
                {"vyce_score": 375, "niq_score": 21, "confidence_lower": 345, "confidence_upper": 405},
            ],
            "MSME001": [  # Steadily growing MSME: 560 -> 650
                {"vyce_score": 560, "niq_score": 42, "confidence_lower": 530, "confidence_upper": 590},
                {"vyce_score": 572, "niq_score": 44, "confidence_lower": 542, "confidence_upper": 602},
                {"vyce_score": 580, "niq_score": 46, "confidence_lower": 550, "confidence_upper": 610},
                {"vyce_score": 588, "niq_score": 48, "confidence_lower": 558, "confidence_upper": 618},
                {"vyce_score": 595, "niq_score": 50, "confidence_lower": 565, "confidence_upper": 625},
                {"vyce_score": 605, "niq_score": 52, "confidence_lower": 575, "confidence_upper": 635},
                {"vyce_score": 612, "niq_score": 54, "confidence_lower": 582, "confidence_upper": 642},
                {"vyce_score": 620, "niq_score": 55, "confidence_lower": 590, "confidence_upper": 650},
                {"vyce_score": 628, "niq_score": 57, "confidence_lower": 598, "confidence_upper": 658},
                {"vyce_score": 635, "niq_score": 59, "confidence_lower": 605, "confidence_upper": 665},
                {"vyce_score": 640, "niq_score": 60, "confidence_lower": 610, "confidence_upper": 670},
                {"vyce_score": 645, "niq_score": 61, "confidence_lower": 615, "confidence_upper": 675},
            ],
            "MSME002": [  # High-performing MSME: 750 -> 810
                {"vyce_score": 750, "niq_score": 80, "confidence_lower": 720, "confidence_upper": 780},
                {"vyce_score": 758, "niq_score": 81, "confidence_lower": 728, "confidence_upper": 788},
                {"vyce_score": 765, "niq_score": 83, "confidence_lower": 735, "confidence_upper": 795},
                {"vyce_score": 770, "niq_score": 84, "confidence_lower": 740, "confidence_upper": 800},
                {"vyce_score": 775, "niq_score": 85, "confidence_lower": 745, "confidence_upper": 805},
                {"vyce_score": 780, "niq_score": 86, "confidence_lower": 750, "confidence_upper": 810},
                {"vyce_score": 785, "niq_score": 87, "confidence_lower": 755, "confidence_upper": 815},
                {"vyce_score": 790, "niq_score": 88, "confidence_lower": 760, "confidence_upper": 820},
                {"vyce_score": 795, "niq_score": 89, "confidence_lower": 765, "confidence_upper": 825},
                {"vyce_score": 798, "niq_score": 89, "confidence_lower": 768, "confidence_upper": 828},
                {"vyce_score": 802, "niq_score": 90, "confidence_lower": 772, "confidence_upper": 832},
                {"vyce_score": 808, "niq_score": 91, "confidence_lower": 778, "confidence_upper": 838},
            ],
        }

        for nid, monthly_scores in score_history_data.items():
            sid = subject_ids[nid]
            current_score_date = next(
                sc["score_date"] for sc in test_scores if sc["national_id"] == nid
            )

            # Generate deterministic dates: 12 months back from current score date
            for i, ms in enumerate(monthly_scores):
                months_back = len(monthly_scores) - i
                hist_date = date(
                    current_score_date.year + (current_score_date.month - months_back - 1) // 12,
                    (current_score_date.month - months_back - 1) % 12 + 1,
                    min(current_score_date.day, 28),  # safe day for all months
                )
                hist_score_id = _score_uuid(nid, hist_date)

                values = {
                    "score_id": hist_score_id,
                    "subject_id": sid,
                    "vyce_score": ms["vyce_score"],
                    "niq_score": ms["niq_score"],
                    "score_date": hist_date,
                    "model_version": "v1.0.0",
                    "confidence_lower": ms["confidence_lower"],
                    "confidence_upper": ms["confidence_upper"],
                    "created_at": _SEED_TS,
                }

                stmt = pg_insert(Score).values(**values)
                stmt = stmt.on_conflict_do_update(
                    index_elements=["score_id"],
                    set_={
                        "vyce_score": stmt.excluded.vyce_score,
                        "niq_score": stmt.excluded.niq_score,
                        "model_version": stmt.excluded.model_version,
                        "confidence_lower": stmt.excluded.confidence_lower,
                        "confidence_upper": stmt.excluded.confidence_upper,
                    },
                )
                await session.execute(stmt)

            print(f"  UPSERT {len(monthly_scores)} historical scores for {nid}")

        await session.commit()

    await engine.dispose()
    print("\nTest data seeded successfully (deterministic).")
    print("\n--- Test National IDs (each with 12-month score history) ---")
    print("  12345678  — Individual, VyceScore 720 (Low Risk)    — Improving trend (620->720)")
    print("  23456789  — Individual, VyceScore 540 (Medium Risk) — Declining trend (640->540)")
    print("  34567890  — Individual, VyceScore 380 (High Risk)   — Volatile trend (~380)")
    print("  MSME001   — MSME, VyceScore 650 (Medium Risk)      — Steady growth (560->650)")
    print("  MSME002   — MSME, VyceScore 810 (Low Risk)         — Strong upward (750->810)")
    print("\n--- Test API Keys (for X-API-Key header) ---")
    print("  Equity Bank (Pro):        vyc_test_equity_bank_pro_key_2026")
    print("  KCB Group (DeepDive):     vyc_test_kcb_group_enterprise_key_2026")
    print("  Safaricom (Lite):         vyc_test_safaricom_lite_key_2026")
    print("\n--- Test Customers (additional) ---")
    print("  Faulu Microfinance (Lite, Pending)    — no API key")
    print("  NCBA Bank (Pro, Suspended)            — no API key")


if __name__ == "__main__":
    print("Seeding UAT test data (deterministic)...\n")
    asyncio.run(seed())
