"""KPI calculation scheduler (Task 9.9).

Uses APScheduler to run KPI calculations on their defined schedules:
  - Hourly:  :05 past each hour
  - Daily:   03:00 UTC
  - Weekly:  Monday 04:00 UTC
  - Monthly: 1st of month 05:00 UTC

Results are persisted to the kpi_snapshots table.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Coroutine
from typing import Any

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_factory
from app.services.kpi_calculators import (
    calculate_daily_kpis,
    calculate_hourly_kpis,
    calculate_monthly_kpis,
    calculate_weekly_kpis,
)

logger = logging.getLogger("vycescore.kpi_scheduler")

# Module-level scheduler instance
_scheduler: AsyncIOScheduler | None = None


async def _run_calculator(
    name: str,
    calculator: Callable[[AsyncSession], Coroutine[Any, Any, list[Any]]],
) -> None:
    """Execute a KPI calculator function within a fresh DB session and persist results."""
    logger.info("KPI calculation started: %s", name)
    try:
        async with async_session_factory() as session:
            snapshots = await calculator(session)
            if snapshots:
                session.add_all(snapshots)
                await session.commit()
                logger.info(
                    "KPI calculation complete: %s — %d snapshots stored",
                    name,
                    len(snapshots),
                )
            else:
                logger.info("KPI calculation complete: %s — no snapshots produced", name)
    except Exception:
        logger.exception("KPI calculation failed: %s", name)


async def _run_hourly() -> None:
    await _run_calculator("hourly", calculate_hourly_kpis)


async def _run_daily() -> None:
    await _run_calculator("daily", calculate_daily_kpis)


async def _run_weekly() -> None:
    await _run_calculator("weekly", calculate_weekly_kpis)


async def _run_monthly() -> None:
    await _run_calculator("monthly", calculate_monthly_kpis)


def start_kpi_scheduler() -> AsyncIOScheduler:
    """Create and start the APScheduler with all KPI jobs.

    Returns the scheduler instance for shutdown management.
    """
    global _scheduler  # noqa: PLW0603

    if _scheduler is not None and _scheduler.running:
        logger.warning("KPI scheduler already running; skipping duplicate start")
        return _scheduler

    _scheduler = AsyncIOScheduler(timezone="UTC")

    # Hourly: :05 past each hour
    _scheduler.add_job(
        _run_hourly,
        trigger=CronTrigger(minute=5, timezone="UTC"),
        id="kpi_hourly",
        name="Hourly KPI calculations",
        replace_existing=True,
    )

    # Daily: 03:00 UTC
    _scheduler.add_job(
        _run_daily,
        trigger=CronTrigger(hour=3, minute=0, timezone="UTC"),
        id="kpi_daily",
        name="Daily KPI calculations",
        replace_existing=True,
    )

    # Weekly: Monday 04:00 UTC
    _scheduler.add_job(
        _run_weekly,
        trigger=CronTrigger(day_of_week="mon", hour=4, minute=0, timezone="UTC"),
        id="kpi_weekly",
        name="Weekly KPI calculations",
        replace_existing=True,
    )

    # Monthly: 1st of month 05:00 UTC
    _scheduler.add_job(
        _run_monthly,
        trigger=CronTrigger(day=1, hour=5, minute=0, timezone="UTC"),
        id="kpi_monthly",
        name="Monthly KPI calculations",
        replace_existing=True,
    )

    _scheduler.start()
    logger.info("KPI scheduler started with 4 jobs (hourly, daily, weekly, monthly)")
    return _scheduler


def stop_kpi_scheduler() -> None:
    """Shut down the scheduler gracefully."""
    global _scheduler  # noqa: PLW0603
    if _scheduler is not None and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("KPI scheduler stopped")
    _scheduler = None
