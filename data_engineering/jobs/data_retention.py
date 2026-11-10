"""Data retention automation for VyceScore pipelines.

Enforces the 10-year data retention policy and PII anonymization
requirements per Kenya Data Protection Act (DPA 2019).

Responsibilities:
    1. PII anonymization: Replace raw PII fields with hashes in
       aged datasets (beyond the staging window).
    2. Retention enforcement: Delete data older than 10 years.
    3. Audit logging: Record all retention actions for compliance.

Usage:
    python -m data_engineering.jobs.data_retention --date 2026-03-08
    python -m data_engineering.jobs.data_retention --dry-run
"""

from __future__ import annotations

import argparse
import hashlib
import logging
import os
import shutil
import sys
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

RETENTION_YEARS = 10
STAGING_RETENTION_DAYS = 7  # Raw PII retained only in staging for 7 days
DATALAKE_BASE = os.getenv(
    "VYCESCORE_DATALAKE_PATH", "s3a://vycescore-datalake"
)

PII_COLUMNS = [
    "national_id",
    "phone_number",
    "full_name",
    "email",
    "address",
    "date_of_birth",
]

ANONYMIZATION_PATHS = [
    f"{DATALAKE_BASE}/staged/transactions",
    f"{DATALAKE_BASE}/staged/supply_chain",
    f"{DATALAKE_BASE}/staged/compliance",
]

RETENTION_PATHS = [
    f"{DATALAKE_BASE}/staged",
    f"{DATALAKE_BASE}/features",
    f"{DATALAKE_BASE}/scores",
    f"{DATALAKE_BASE}/raw",
]


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class RetentionAction:
    """Record of a single retention or anonymization action."""

    action_type: str  # "anonymize" | "delete" | "skip"
    path: str
    partition_date: str
    rows_affected: int = 0
    details: str = ""
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "action_type": self.action_type,
            "path": self.path,
            "partition_date": self.partition_date,
            "rows_affected": self.rows_affected,
            "details": self.details,
            "timestamp": self.timestamp,
        }


@dataclass
class RetentionReport:
    """Summary report for a retention job run."""

    run_date: str
    dry_run: bool = False
    partitions_scanned: int = 0
    partitions_anonymized: int = 0
    partitions_deleted: int = 0
    rows_anonymized: int = 0
    actions: list[RetentionAction] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    started_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    completed_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_date": self.run_date,
            "dry_run": self.dry_run,
            "partitions_scanned": self.partitions_scanned,
            "partitions_anonymized": self.partitions_anonymized,
            "partitions_deleted": self.partitions_deleted,
            "rows_anonymized": self.rows_anonymized,
            "errors": self.errors,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "actions": [a.to_dict() for a in self.actions],
        }


# ---------------------------------------------------------------------------
# Date helpers
# ---------------------------------------------------------------------------

def get_retention_cutoff(reference_date: date | None = None) -> date:
    """Calculate the date beyond which data must be deleted.

    Args:
        reference_date: Reference date (default: today).

    Returns:
        Cutoff date (10 years before reference).
    """
    if reference_date is None:
        reference_date = date.today()
    return reference_date - timedelta(days=RETENTION_YEARS * 365)


def get_anonymization_cutoff(reference_date: date | None = None) -> date:
    """Calculate the date beyond which PII must be anonymized.

    Args:
        reference_date: Reference date (default: today).

    Returns:
        Cutoff date (STAGING_RETENTION_DAYS before reference).
    """
    if reference_date is None:
        reference_date = date.today()
    return reference_date - timedelta(days=STAGING_RETENTION_DAYS)


def parse_partition_date(partition_dir: str) -> date | None:
    """Extract the date from a partition directory name.

    Expected format: dt=YYYY-MM-DD

    Args:
        partition_dir: Directory name or path ending in dt=YYYY-MM-DD.

    Returns:
        Parsed date or None if format doesn't match.
    """
    name = os.path.basename(partition_dir.rstrip("/"))
    if not name.startswith("dt="):
        return None
    try:
        return datetime.strptime(name[3:], "%Y-%m-%d").date()
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# PII anonymization
# ---------------------------------------------------------------------------

def anonymize_pii_columns(
    df: pd.DataFrame,
    pii_columns: list[str] | None = None,
    *,
    salt: str = "retention-anonymize",
) -> tuple[pd.DataFrame, int]:
    """Replace PII columns with anonymized hashes.

    Args:
        df: Input DataFrame potentially containing PII.
        pii_columns: List of column names to anonymize.
        salt: Salt for hashing.

    Returns:
        Tuple of (anonymized DataFrame, count of cells anonymized).
    """
    if pii_columns is None:
        pii_columns = PII_COLUMNS

    df = df.copy()
    cells_anonymized = 0

    for col in pii_columns:
        if col not in df.columns:
            continue

        non_null_mask = df[col].notna()
        non_null_count = int(non_null_mask.sum())

        if non_null_count > 0:
            df.loc[non_null_mask, col] = df.loc[non_null_mask, col].apply(
                lambda v: hashlib.sha256(
                    f"{salt}{v}".encode("utf-8")
                ).hexdigest()[:16] + "***ANONYMIZED***"
            )
            cells_anonymized += non_null_count

    return df, cells_anonymized


def anonymize_partition(
    partition_path: str,
    *,
    dry_run: bool = False,
    pii_columns: list[str] | None = None,
) -> RetentionAction:
    """Anonymize PII in a single partition.

    Args:
        partition_path: Path to the partition directory.
        dry_run: If True, report what would happen without making changes.
        pii_columns: Optional override for PII column names.

    Returns:
        RetentionAction describing what was done.
    """
    part_date = parse_partition_date(partition_path)
    date_str = str(part_date) if part_date else "unknown"

    try:
        df = pd.read_parquet(partition_path)
    except Exception as exc:
        return RetentionAction(
            action_type="skip",
            path=partition_path,
            partition_date=date_str,
            details=f"Cannot read partition: {exc}",
        )

    cols_present = [
        c for c in (pii_columns or PII_COLUMNS)
        if c in df.columns
    ]

    if not cols_present:
        return RetentionAction(
            action_type="skip",
            path=partition_path,
            partition_date=date_str,
            details="No PII columns found",
        )

    anonymized_df, cells_count = anonymize_pii_columns(
        df, pii_columns=cols_present
    )

    if dry_run:
        return RetentionAction(
            action_type="anonymize",
            path=partition_path,
            partition_date=date_str,
            rows_affected=len(df),
            details=f"DRY RUN: Would anonymize {cells_count} cells in columns {cols_present}",
        )

    # Overwrite with anonymized data
    anonymized_df.to_parquet(
        os.path.join(partition_path, "data.parquet"),
        index=False,
        engine="pyarrow",
    )

    return RetentionAction(
        action_type="anonymize",
        path=partition_path,
        partition_date=date_str,
        rows_affected=len(df),
        details=f"Anonymized {cells_count} cells in columns {cols_present}",
    )


# ---------------------------------------------------------------------------
# Partition deletion
# ---------------------------------------------------------------------------

def delete_partition(
    partition_path: str,
    *,
    dry_run: bool = False,
) -> RetentionAction:
    """Delete a data partition that exceeds the retention period.

    Args:
        partition_path: Path to the partition directory.
        dry_run: If True, report what would happen without deleting.

    Returns:
        RetentionAction describing what was done.
    """
    part_date = parse_partition_date(partition_path)
    date_str = str(part_date) if part_date else "unknown"

    if dry_run:
        return RetentionAction(
            action_type="delete",
            path=partition_path,
            partition_date=date_str,
            details="DRY RUN: Would delete partition",
        )

    try:
        shutil.rmtree(partition_path)
        logger.info("Deleted partition: %s", partition_path)
        return RetentionAction(
            action_type="delete",
            path=partition_path,
            partition_date=date_str,
            details="Partition deleted",
        )
    except Exception as exc:
        return RetentionAction(
            action_type="skip",
            path=partition_path,
            partition_date=date_str,
            details=f"Failed to delete: {exc}",
        )


# ---------------------------------------------------------------------------
# Partition discovery
# ---------------------------------------------------------------------------

def discover_partitions(base_path: str) -> list[str]:
    """Discover date-partitioned directories under a base path.

    Args:
        base_path: Base directory to scan.

    Returns:
        List of partition directory paths sorted by date.
    """
    partitions: list[str] = []

    if not os.path.isdir(base_path):
        logger.debug("Path does not exist or is not local: %s", base_path)
        return partitions

    try:
        for entry in sorted(os.listdir(base_path)):
            full_path = os.path.join(base_path, entry)
            if os.path.isdir(full_path) and entry.startswith("dt="):
                partitions.append(full_path)
    except PermissionError:
        logger.warning("Permission denied scanning: %s", base_path)

    return partitions


# ---------------------------------------------------------------------------
# Main job
# ---------------------------------------------------------------------------

def run_retention_job(
    reference_date: date | None = None,
    *,
    dry_run: bool = False,
    anonymization_paths: list[str] | None = None,
    retention_paths: list[str] | None = None,
) -> RetentionReport:
    """Execute the full data retention and anonymization job.

    Steps:
        1. Scan staging paths for partitions older than the
           anonymization cutoff and anonymize PII.
        2. Scan all data paths for partitions older than the
           retention cutoff and delete them.

    Args:
        reference_date: Date to use as "today" for cutoff calculations.
        dry_run: If True, report actions without making changes.
        anonymization_paths: Override paths to scan for PII.
        retention_paths: Override paths to scan for deletion.

    Returns:
        RetentionReport summarizing all actions taken.
    """
    if reference_date is None:
        reference_date = date.today()

    if anonymization_paths is None:
        anonymization_paths = ANONYMIZATION_PATHS

    if retention_paths is None:
        retention_paths = RETENTION_PATHS

    anon_cutoff = get_anonymization_cutoff(reference_date)
    delete_cutoff = get_retention_cutoff(reference_date)

    report = RetentionReport(
        run_date=str(reference_date),
        dry_run=dry_run,
    )

    logger.info(
        "Running retention job: ref=%s, anon_cutoff=%s, delete_cutoff=%s, dry_run=%s",
        reference_date, anon_cutoff, delete_cutoff, dry_run,
    )

    # Phase 1: PII anonymization
    for base_path in anonymization_paths:
        partitions = discover_partitions(base_path)
        for partition_path in partitions:
            report.partitions_scanned += 1
            part_date = parse_partition_date(partition_path)
            if part_date is None:
                continue
            if part_date <= anon_cutoff:
                try:
                    action = anonymize_partition(
                        partition_path, dry_run=dry_run,
                    )
                    report.actions.append(action)
                    if action.action_type == "anonymize":
                        report.partitions_anonymized += 1
                        report.rows_anonymized += action.rows_affected
                except Exception as exc:
                    msg = f"Error anonymizing {partition_path}: {exc}"
                    logger.error(msg)
                    report.errors.append(msg)

    # Phase 2: Retention enforcement (deletion)
    for base_path in retention_paths:
        partitions = discover_partitions(base_path)
        for partition_path in partitions:
            report.partitions_scanned += 1
            part_date = parse_partition_date(partition_path)
            if part_date is None:
                continue
            if part_date <= delete_cutoff:
                try:
                    action = delete_partition(
                        partition_path, dry_run=dry_run,
                    )
                    report.actions.append(action)
                    if action.action_type == "delete":
                        report.partitions_deleted += 1
                except Exception as exc:
                    msg = f"Error deleting {partition_path}: {exc}"
                    logger.error(msg)
                    report.errors.append(msg)

    report.completed_at = datetime.now(timezone.utc).isoformat()
    logger.info("Retention job complete: %s", report.to_dict())
    return report


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args(args: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="VyceScore Data Retention & PII Anonymization"
    )
    parser.add_argument(
        "--date",
        default=None,
        help="Reference date (YYYY-MM-DD, default: today)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report actions without making changes",
    )
    return parser.parse_args(args)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    parsed = parse_args()
    ref = (
        datetime.strptime(parsed.date, "%Y-%m-%d").date()
        if parsed.date else None
    )
    result = run_retention_job(
        reference_date=ref,
        dry_run=parsed.dry_run,
    )
    import json
    print(json.dumps(result.to_dict(), indent=2))
    sys.exit(0 if not result.errors else 1)
