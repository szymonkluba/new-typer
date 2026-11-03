import os

SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-change-in-production")
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///typer.db")
COOKIE_NAME = "session"
COOKIE_MAX_AGE = 60 * 60 * 24 * 30  # 30 days

FIS_CALENDAR_URL = "https://www.fis-ski.com/DB/ski-jumping/calendar-results.html"
FIS_EVENT_URL = "https://www.fis-ski.com/DB/general/event-details.html"
FIS_RESULTS_URL = "https://www.fis-ski.com/DB/general/results.html"

SCRAPER_COMPETITIONS_CRON_HOUR = 6
SCRAPER_RESULTS_INTERVAL_HOURS = 2
