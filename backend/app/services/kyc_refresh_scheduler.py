"""KYC refresh scheduler (Phase 15.5).

Uses APScheduler to run monthly KYC re-verification on the 1st of each
month at 06:00 UTC. Integrates with the existing scheduler pattern
from kpi_scheduler.
"""

from __future__ import annotations

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.services.kyc_refresh_service import run_scheduled_kyc_refresh

logger = logging.getLogger("vycescore.kyc_refresh_scheduler")

_scheduler: AsyncIOScheduler | None = None


def start_kyc_refresh_scheduler() -> AsyncIOScheduler:
    """Create and start the APScheduler for monthly KYC refresh.

    Runs on the 1st of each month at 06:00 UTC, after the monthly
    KPI calculations (05:00 UTC) to avoid overlapping workloads.
    """
    global _scheduler  # noqa: PLW0603

    if _scheduler is not None and _scheduler.running:
        logger.warning("KYC refresh scheduler already running; skipping duplicate start")
        return _scheduler

    _scheduler = AsyncIOScheduler(timezone="UTC")

    # Monthly: 1st of month 06:00 UTC
    _scheduler.add_job(
        run_scheduled_kyc_refresh,
        trigger=CronTrigger(day=1, hour=6, minute=0, timezone="UTC"),
        id="kyc_monthly_refresh",
        name="Monthly KYC refresh",
        replace_existing=True,
    )

    _scheduler.start()
    logger.info("KYC refresh scheduler started — monthly on 1st at 06:00 UTC")
    return _scheduler


def stop_kyc_refresh_scheduler() -> None:
    """Shut down the KYC refresh scheduler gracefully."""
    global _scheduler  # noqa: PLW0603
    if _scheduler is not None and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("KYC refresh scheduler stopped")
    _scheduler = None
