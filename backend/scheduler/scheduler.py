"""
APScheduler integration — runs match discovery every 10 minutes.

Can also be triggered manually via the /api/v2/scheduler/run endpoint.
"""

from __future__ import annotations

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from backend.logger import get_logger

logger = get_logger(__name__)

_scheduler: BackgroundScheduler | None = None


def _run_discovery_job():
    """Wrapper that imports and runs discover_matches with error handling."""
    from backend.scheduler.match_discovery import discover_matches
    try:
        new = discover_matches()
        logger.info("[SCHEDULER] Discovery job completed — %d new matches", new)
    except Exception:
        logger.exception("[SCHEDULER] Discovery job failed")


def start_scheduler() -> BackgroundScheduler:
    """Start the background scheduler (idempotent)."""
    global _scheduler
    if _scheduler and _scheduler.running:
        logger.info("[SCHEDULER] Already running, skipping start")
        return _scheduler

    _scheduler = BackgroundScheduler(timezone="Asia/Kolkata")
    _scheduler.add_job(
        _run_discovery_job,
        trigger=IntervalTrigger(minutes=10),
        id="match_discovery",
        name="Discover new IPL matches",
        replace_existing=True,
        max_instances=1,
    )
    _scheduler.start()
    logger.info("[SCHEDULER] Started — discovery every 10 minutes")
    return _scheduler


def stop_scheduler():
    """Gracefully shut down the scheduler."""
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("[SCHEDULER] Stopped")
    _scheduler = None


def run_discovery_now() -> int:
    """Manually trigger match discovery (for debugging or one-off runs)."""
    from backend.scheduler.match_discovery import discover_matches
    logger.info("[SCHEDULER] Manual discovery triggered")
    return discover_matches()
