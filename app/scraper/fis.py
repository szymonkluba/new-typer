import logging
from datetime import date, datetime

import httpx
from bs4 import BeautifulSoup
from sqlalchemy.orm import Session

from app.config import FIS_CALENDAR_URL, FIS_RESULTS_URL
from app.database import SessionLocal
from app.models import Competition, Result

logger = logging.getLogger(__name__)

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}


def sync_competitions_from_fis():
    """Scrape FIS calendar for upcoming ski jumping competitions using Playwright."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        logger.warning("Playwright not installed, skipping calendar sync")
        return

    db = SessionLocal()
    try:
        _scrape_calendar(db)
    except Exception:
        logger.exception("Failed to sync competitions from FIS")
    finally:
        db.close()


def _scrape_calendar(db: Session):
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (X11; Linux aarch64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 800},
        )
        page = context.new_page()
        page.goto(FIS_CALENDAR_URL, wait_until="domcontentloaded", timeout=60000)

        # Dismiss cookie consent if present
        try:
            deny_btn = page.wait_for_selector("#CybotCookiebotDialogBodyButtonDecline", timeout=5000)
            if deny_btn:
                deny_btn.click()
                page.wait_for_timeout(1000)
        except Exception:
            pass

        page.wait_for_selector(".table-row", timeout=30000)

        rows = page.query_selector_all(".table-row")
        logger.info("Found %d calendar rows", len(rows))
        for row in rows:
            try:
                _parse_calendar_row(row, db)
            except Exception:
                logger.debug("Skipping unparseable calendar row", exc_info=True)

        browser.close()

    db.commit()
    logger.info("Calendar sync complete")


def _parse_calendar_row(row, db: Session):
    link = row.query_selector("a[href*='eventid']")
    if not link:
        return
    href = link.get_attribute("href")
    fis_event_id = None
    if href and "eventid=" in href:
        try:
            fis_event_id = int(href.split("eventid=")[1].split("&")[0])
        except (ValueError, IndexError):
            return

    if fis_event_id:
        existing = db.query(Competition).filter(Competition.fis_event_id == fis_event_id).first()
        if existing:
            return

    text = row.inner_text()
    lines = [l.strip() for l in text.split("\n") if l.strip()]

    # FIS row structure: [status letters..., date, venue, nation, category, event_type, discipline, gender...]
    # Status letters are single chars like D/P/C, skip them to find the date
    date_text = ""
    venue = "Unknown"
    data_lines = [l for l in lines if len(l) > 1 or not l.isalpha()]
    for line in data_lines:
        if any(
            month in line
            for month in ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        ):
            date_text = line
            break

    # Venue: the element with class containing g-lg-7 and hidden-sm-down
    venue_el = row.query_selector(".g-lg-7.hidden-sm-down .split-row__item")
    if not venue_el:
        venue_el = row.query_selector(".g-lg-7.hidden-sm-down")
    if venue_el:
        venue = venue_el.inner_text().strip()

    # Category and event type from the category cell
    cat_el = row.query_selector(".g-lg-7.g-sm-6")
    category = "WC"
    comp_type = "individual"
    if cat_el:
        cat_text = cat_el.inner_text().upper()
        if "TEAM" in cat_text and "IND" not in cat_text:
            comp_type = "team"
        for cat in ["WC", "GP", "COC", "QUA"]:
            if cat in cat_text:
                category = cat
                break

    has_m = any(l.strip().upper() == "M" for l in lines)
    has_w = any(l.strip().upper() == "W" for l in lines)
    if has_w and not has_m:
        gender = "W"
    else:
        gender = "M"

    if category != "WC" or gender != "M":
        return

    try:
        comp_date = _parse_fis_date(date_text)
    except (ValueError, IndexError):
        logger.warning("Unparseable date '%s' for %s, skipping row", date_text, venue)
        return

    name = f"Ski Jumping {category} - {venue}"

    comp = Competition(
        fis_event_id=fis_event_id,
        name=name,
        venue=venue,
        date=comp_date,
        category=category,
        type=comp_type,
        gender=gender,
        status="upcoming",
    )
    db.add(comp)
    logger.info("Added competition: %s (%s, %s)", name, venue, comp_date)


def _parse_fis_date(text: str) -> date:
    text = text.strip()
    # Handle date ranges like "20-22 Nov" — take the first day
    if "-" in text.split(" ")[0]:
        first_day = text.split("-")[0].strip()
        rest = text.split(" ", 1)[1] if " " in text else ""
        text = f"{first_day} {rest}".strip()
    for fmt in ("%d %b %Y", "%d %B %Y", "%b %d, %Y", "%d.%m.%Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    parts = text.split()
    if len(parts) >= 2:
        for fmt in ("%d %b", "%b %d"):
            try:
                d = datetime.strptime(" ".join(parts[:2]), fmt)
                return d.replace(year=date.today().year).date()
            except ValueError:
                continue
    raise ValueError(f"Cannot parse date: {text}")


def sync_results_from_fis():
    """Check for results of past-date upcoming competitions."""
    db = SessionLocal()
    try:
        comps = (
            db.query(Competition)
            .filter(
                Competition.status == "upcoming",
                Competition.date <= date.today(),
                Competition.fis_race_id.isnot(None),
            )
            .all()
        )
        for comp in comps:
            try:
                _scrape_results(db, comp)
            except Exception:
                logger.debug(f"No results yet for {comp.name}", exc_info=True)
        db.commit()
    except Exception:
        logger.exception("Failed to sync results")
    finally:
        db.close()


def _scrape_results(db: Session, competition: Competition):
    url = f"{FIS_RESULTS_URL}?sectorcode=JP&raceid={competition.fis_race_id}"
    resp = httpx.get(url, headers=HEADERS, timeout=15, follow_redirects=True)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "lxml")
    table = soup.select_one("#events-info-results table, .table-container table, table")
    if not table:
        return

    rows = table.select("tbody tr, tr.table-row")
    if not rows:
        return

    existing_results = db.query(Result).filter(Result.competition_id == competition.id).count()
    if existing_results > 0:
        return

    for row in rows[:10]:
        cells = row.select("td, div[class*='g-']")
        if len(cells) < 4:
            continue
        try:
            rank_text = cells[0].get_text(strip=True)
            rank = int(rank_text)
        except (ValueError, IndexError):
            continue

        name = cells[2].get_text(strip=True) if len(cells) > 2 else cells[1].get_text(strip=True)
        nation = ""
        for cell in cells:
            txt = cell.get_text(strip=True)
            if len(txt) == 3 and txt.isalpha() and txt.isupper():
                nation = txt
                break

        points_text = cells[-1].get_text(strip=True) if cells else ""
        try:
            total_points = float(points_text)
        except (ValueError, TypeError):
            total_points = None

        db.add(
            Result(
                competition_id=competition.id,
                rank=rank,
                athlete_name=name,
                nation=nation,
                total_points=total_points,
            )
        )

    competition.status = "completed"
    logger.info(f"Results imported for {competition.name}")
