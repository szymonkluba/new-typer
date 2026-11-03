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
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(FIS_CALENDAR_URL, wait_until="networkidle", timeout=30000)

        page.wait_for_selector(".table-row", timeout=10000)

        rows = page.query_selector_all(".table-row")
        for row in rows:
            try:
                _parse_calendar_row(row, db)
            except Exception:
                logger.debug("Skipping unparseable calendar row", exc_info=True)

        browser.close()

    db.commit()
    logger.info("Calendar sync complete")


def _parse_calendar_row(row, db: Session):
    cells = row.query_selector_all(".g-xs-4, .g-xs-5, .g-xs-6, .g-xs-8, .g-xs-10, .g-xs-12, [class*='g-']")
    if not cells:
        return

    text = row.inner_text()
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    if len(lines) < 3:
        return

    link = row.query_selector("a")
    href = link.get_attribute("href") if link else None
    fis_event_id = None
    if href and "eventid=" in href:
        try:
            fis_event_id = int(href.split("eventid=")[1].split("&")[0])
        except (ValueError, IndexError):
            pass

    existing = None
    if fis_event_id:
        existing = db.query(Competition).filter(Competition.fis_event_id == fis_event_id).first()

    if existing:
        return

    date_text = lines[0]
    venue = lines[1] if len(lines) > 1 else "Unknown"
    category = "WC"
    comp_type = "individual"
    gender = "M"

    for line in lines:
        line_upper = line.upper()
        if "TEAM" in line_upper:
            comp_type = "team"
        if any(cat in line_upper for cat in ["GP", "COC", "WC", "QUA"]):
            for cat in ["WC", "GP", "COC", "QUA"]:
                if cat in line_upper:
                    category = cat
                    break
        if line_upper.strip() in ("W", "WOMEN"):
            gender = "W"

    if category != "WC" or gender != "M":
        return

    try:
        comp_date = _parse_fis_date(date_text)
    except (ValueError, IndexError):
        comp_date = date.today()

    name_parts = [p for p in lines[2:] if p and len(p) > 2]
    name = name_parts[0] if name_parts else f"Ski Jumping - {venue}"

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


def _parse_fis_date(text: str) -> date:
    text = text.strip()
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
