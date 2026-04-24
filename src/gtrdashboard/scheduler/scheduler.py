"""APScheduler integration for scheduled pipeline runs."""

from __future__ import annotations

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

_scheduler: AsyncIOScheduler | None = None


def init_scheduler() -> None:
    """Initialize and start the scheduler."""
    global _scheduler
    if _scheduler is not None:
        return

    _scheduler = AsyncIOScheduler()
    _scheduler.start()
    _load_jobs()


def shutdown_scheduler() -> None:
    """Shutdown the scheduler."""
    global _scheduler
    if _scheduler:
        _scheduler.shutdown()
        _scheduler = None


def _load_jobs() -> None:
    """Load scheduled jobs from user preferences."""
    from gtrdashboard.database import get_or_create_preferences, get_session

    session = get_session()
    try:
        prefs = get_or_create_preferences(session)
        _schedule_daily_pipeline(prefs.daily_run_time)
    finally:
        session.close()


def _schedule_daily_pipeline(time_str: str) -> None:
    """Schedule the daily pipeline job."""
    global _scheduler
    if _scheduler is None:
        return

    try:
        hour, minute = map(int, time_str.split(":"))
    except ValueError:
        hour, minute = 9, 0

    _scheduler.add_job(
        "gtrdashboard.scheduler.jobs:run_scheduled_pipeline",
        CronTrigger(hour=hour, minute=minute),
        id="daily_pipeline",
        replace_existing=True,
    )


def reschedule_daily_pipeline(time_str: str) -> None:
    """Reschedule the daily pipeline to a new time."""
    global _scheduler
    if _scheduler is None:
        return

    try:
        hour, minute = map(int, time_str.split(":"))
    except ValueError:
        hour, minute = 9, 0

    _scheduler.reschedule_job(
        "daily_pipeline",
        trigger=CronTrigger(hour=hour, minute=minute),
    )
