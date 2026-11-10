"""
Date range helpers for VyceScore data pipeline backfills.

Provides utilities for generating date ranges, partition paths, and
managing backfill windows. All dates are in UTC to match the batch
pipeline schedule.

Key constants:
    - DATA_RETENTION_YEARS: 10 (per Kenya DPA 2019 / CBK requirements)
    - BATCH_SCHEDULE_HOUR_UTC: 3 (daily batch runs at 03:00 UTC)
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Iterator

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DATA_RETENTION_YEARS: int = 10
BATCH_SCHEDULE_HOUR_UTC: int = 3
DEFAULT_PARTITION_FORMAT: str = "dt=%Y-%m-%d"


def date_range(
    start_date: date,
    end_date: date,
    inclusive: bool = True,
) -> Iterator[date]:
    """Generate a sequence of dates from start to end.

    Args:
        start_date: First date in the range.
        end_date: Last date in the range.
        inclusive: If True, end_date is included. Defaults to True.

    Yields:
        Each date in the range.

    Examples:
        >>> list(date_range(date(2024, 1, 1), date(2024, 1, 3)))
        [date(2024, 1, 1), date(2024, 1, 2), date(2024, 1, 3)]
    """
    current = start_date
    end = end_date if inclusive else end_date - timedelta(days=1)
    while current <= end:
        yield current
        current += timedelta(days=1)


def partition_paths(
    base_path: str,
    start_date: date,
    end_date: date,
    partition_format: str = DEFAULT_PARTITION_FORMAT,
) -> list[str]:
    """Generate data lake partition paths for a date range.

    Args:
        base_path: Base path in the data lake (e.g., "s3a://bucket/raw/vycepay").
        start_date: First date in the range.
        end_date: Last date in the range (inclusive).
        partition_format: strftime format for the partition directory name.

    Returns:
        List of full partition paths.

    Examples:
        >>> partition_paths("s3a://bucket/raw", date(2024, 1, 1), date(2024, 1, 2))
        ['s3a://bucket/raw/dt=2024-01-01', 's3a://bucket/raw/dt=2024-01-02']
    """
    base = base_path.rstrip("/")
    return [
        f"{base}/{d.strftime(partition_format)}"
        for d in date_range(start_date, end_date)
    ]


def get_backfill_window(
    target_date: date,
    lookback_days: int = 90,
) -> tuple[date, date]:
    """Calculate the backfill window for feature computation.

    Many features (CBLRI, UTDI) require historical data windows.
    This returns the start and end dates for the lookback period.

    Args:
        target_date: The date being processed.
        lookback_days: Number of days to look back. Defaults to 90.

    Returns:
        Tuple of (start_date, end_date) for the backfill window.
    """
    start = target_date - timedelta(days=lookback_days)
    return (start, target_date)


def get_quarter_boundaries(target_date: date) -> tuple[date, date]:
    """Get the start and end dates of the quarter containing target_date.

    Used by UTDI and SCFV which compute features on a quarterly basis.

    Args:
        target_date: Any date within the desired quarter.

    Returns:
        Tuple of (quarter_start, quarter_end).
    """
    quarter = (target_date.month - 1) // 3
    quarter_start_month = quarter * 3 + 1
    quarter_start = date(target_date.year, quarter_start_month, 1)

    if quarter_start_month + 3 > 12:
        quarter_end = date(target_date.year + 1, 1, 1) - timedelta(days=1)
    else:
        quarter_end = date(target_date.year, quarter_start_month + 3, 1) - timedelta(days=1)

    return (quarter_start, quarter_end)


def is_within_retention(
    data_date: date,
    reference_date: date | None = None,
    retention_years: int = DATA_RETENTION_YEARS,
) -> bool:
    """Check if a data date is within the retention period.

    Args:
        data_date: The date of the data partition.
        reference_date: Reference date to check against. Defaults to today (UTC).
        retention_years: Number of years to retain data. Defaults to 10.

    Returns:
        True if the data is within the retention window.
    """
    if reference_date is None:
        reference_date = datetime.now(timezone.utc).date()

    retention_start = date(
        reference_date.year - retention_years,
        reference_date.month,
        reference_date.day,
    )
    return data_date >= retention_start


def get_processing_date(
    logical_date: datetime | None = None,
    offset_days: int = -1,
) -> date:
    """Determine the data date to process based on the logical execution date.

    By default, the batch pipeline processes T-1 data (yesterday's
    transactions), ensuring all late-arriving data is captured.

    Args:
        logical_date: The Airflow logical execution date. Defaults to now (UTC).
        offset_days: Day offset from logical_date. Defaults to -1 (T-1).

    Returns:
        The date to process.
    """
    if logical_date is None:
        logical_date = datetime.now(timezone.utc)

    return (logical_date + timedelta(days=offset_days)).date()
