import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from app.config import SCRAPER_COMPETITIONS_CRON_HOUR, SCRAPER_RESULTS_INTERVAL_HOURS

logger = logging.getLogger(__name__)
scheduler = BackgroundScheduler()


def start_scheduler():
    from app.scraper.fis import sync_competitions_from_fis, sync_results_from_fis

    scheduler.add_job(
        sync_competitions_from_fis,
        trigger=CronTrigger(hour=SCRAPER_COMPETITIONS_CRON_HOUR),
        id="sync_competitions",
        replace_existing=True,
    )

    scheduler.add_job(
        sync_results_from_fis,
        trigger=IntervalTrigger(hours=SCRAPER_RESULTS_INTERVAL_HOURS),
        id="sync_results",
        replace_existing=True,
    )

    scheduler.start()
    logger.info("Scraper scheduler started")


def stop_scheduler():
    scheduler.shutdown(wait=False)
    logger.info("Scraper scheduler stopped")
