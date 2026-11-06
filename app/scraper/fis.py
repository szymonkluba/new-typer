import logging
from datetime import date, datetime

from sqlalchemy.orm import Session

from app.config import FIS_ATHLETES_URL, FIS_CALENDAR_URL, FIS_EVENT_URL, FIS_RESULTS_URL
from app.database import SessionLocal
from app.models import Athlete, Competition, Result

logger = logging.getLogger(__name__)

_USER_AGENT = "Mozilla/5.0 (X11; Linux aarch64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"


def _launch_browser(playwright):
    browser = playwright.chromium.launch(headless=True, args=["--no-sandbox"])
    context = browser.new_context(user_agent=_USER_AGENT, viewport={"width": 1280, "height": 800})
    return browser, context.new_page()


def _dismiss_cookie_consent(page):
    try:
        deny_btn = page.wait_for_selector("#CybotCookiebotDialogBodyButtonDecline", timeout=5000)
        if deny_btn:
            deny_btn.click()
            page.wait_for_timeout(1000)
    except Exception:
        pass


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
        browser, page = _launch_browser(p)
        page.goto(FIS_CALENDAR_URL, wait_until="domcontentloaded", timeout=60000)
        _dismiss_cookie_consent(page)

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


def sync_athletes_from_fis():
    """Scrape FIS biographies page for active male ski jumpers using Playwright."""
    try:
        from playwright.sync_api import sync_playwright  # noqa: F401
    except ImportError:
        logger.warning("Playwright not installed, skipping athlete sync")
        return

    db = SessionLocal()
    try:
        _scrape_athletes(db)
    except Exception:
        logger.exception("Failed to sync athletes from FIS")
    finally:
        db.close()


def _scrape_athletes(db: Session):
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser, page = _launch_browser(p)
        page.goto(FIS_ATHLETES_URL, wait_until="domcontentloaded", timeout=60000)
        _dismiss_cookie_consent(page)

        page.wait_for_selector(".table-row", timeout=30000)

        rows = page.query_selector_all(".table-row")
        logger.info("Found %d athlete rows", len(rows))

        new_count = 0
        updated_count = 0

        for row in rows:
            try:
                result = _parse_athlete_row(row)
                if result is None:
                    continue
                fis_code, competitor_id, name, nation = result

                existing = db.query(Athlete).filter(Athlete.fis_code == fis_code).first()
                if existing:
                    existing.name = name
                    existing.nation = nation
                    existing.competitor_id = competitor_id
                    existing.updated_at = datetime.utcnow()
                    updated_count += 1
                else:
                    db.add(
                        Athlete(
                            fis_code=fis_code,
                            competitor_id=competitor_id,
                            name=name,
                            nation=nation,
                        )
                    )
                    new_count += 1
            except Exception:
                logger.debug("Skipping unparseable athlete row", exc_info=True)

        browser.close()

    db.commit()
    logger.info("Athlete sync complete: %d new, %d updated", new_count, updated_count)


def _parse_athlete_row(row):
    href = row.get_attribute("href")
    if not href or "competitorid=" not in href:
        return None
    try:
        competitor_id = int(href.split("competitorid=")[1].split("&")[0])
    except (ValueError, IndexError):
        return None

    cols = row.query_selector_all(".container > div")
    if len(cols) < 3:
        return None

    fis_code_divs = cols[0].query_selector_all(":scope > div")
    if len(fis_code_divs) < 2:
        return None
    try:
        fis_code = int(fis_code_divs[1].inner_text().strip())
    except (ValueError, IndexError):
        return None

    name = cols[1].inner_text().strip()
    if not name:
        return None

    nation_el = row.query_selector(".country__name-short")
    nation = nation_el.inner_text().strip() if nation_el else ""

    return fis_code, competitor_id, name, nation


def sync_results_from_fis():
    """Check for results of past-date upcoming competitions."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        logger.warning("Playwright not installed, skipping results sync")
        return

    db = SessionLocal()
    try:
        comps = (
            db.query(Competition)
            .filter(
                Competition.status == "upcoming",
                Competition.date <= date.today(),
                Competition.fis_event_id.isnot(None),
            )
            .all()
        )
        if not comps:
            return

        with sync_playwright() as p:
            browser, page = _launch_browser(p)
            _dismiss_cookie_consent(page)

            for comp in comps:
                try:
                    if comp.fis_race_id is None:
                        race_id = _resolve_race_id(page, comp)
                        if race_id:
                            comp.fis_race_id = race_id
                        else:
                            logger.debug("Could not resolve race ID for %s", comp.name)
                            continue

                    _scrape_results(db, comp, page)
                except Exception:
                    logger.debug("No results yet for %s", comp.name, exc_info=True)

            browser.close()

        db.commit()
    except Exception:
        logger.exception("Failed to sync results")
    finally:
        db.close()


def _resolve_race_id(page, competition: Competition) -> int | None:
    url = f"{FIS_EVENT_URL}?sectorcode=JP&eventid={competition.fis_event_id}"
    page.goto(url, wait_until="domcontentloaded", timeout=30000)

    try:
        page.wait_for_selector("a[href*='raceid=']", timeout=15000)
    except Exception:
        return None

    links = page.query_selector_all("a[href*='raceid=']")
    for link in links:
        href = link.get_attribute("href") or ""
        text = link.inner_text().upper()
        if "raceid=" not in href:
            continue
        if competition.type == "individual" and "TEAM" in text:
            continue
        if "QUALIFICATION" in text or "QUA" in text.split():
            continue
        try:
            return int(href.split("raceid=")[1].split("&")[0])
        except (ValueError, IndexError):
            continue
    return None


def _parse_result_row(row):
    cols = row.query_selector_all(".container > div")
    if len(cols) < 5:
        return None

    try:
        rank = int(cols[0].inner_text().strip())
    except ValueError:
        return None

    try:
        fis_code = int(cols[2].inner_text().strip())
    except ValueError:
        fis_code = None

    name = cols[3].inner_text().strip()
    if not name:
        return None

    nation_el = row.query_selector(".country__name-short")
    nation = nation_el.inner_text().strip() if nation_el else ""

    # Tot. Points is the second-to-last numeric column (last is Diff. Points)
    total_points = None
    for col in reversed(cols[5:-1]):
        text = col.inner_text().strip()
        if text:
            try:
                total_points = float(text)
                break
            except ValueError:
                continue

    return rank, fis_code, name, nation, total_points


def _scrape_results(db: Session, competition: Competition, page):
    url = f"{FIS_RESULTS_URL}?sectorcode=JP&raceid={competition.fis_race_id}"
    page.goto(url, wait_until="domcontentloaded", timeout=30000)

    try:
        page.wait_for_selector(".table-row", timeout=15000)
    except Exception:
        return

    existing_results = db.query(Result).filter(Result.competition_id == competition.id).count()
    if existing_results > 0:
        return

    rows = page.query_selector_all(".table-row")
    for row in rows:
        parsed = _parse_result_row(row)
        if parsed is None:
            continue

        rank, fis_code, name, nation, total_points = parsed

        if fis_code:
            athlete = db.query(Athlete).filter(Athlete.fis_code == fis_code).first()
            if athlete:
                name = athlete.name

        db.add(
            Result(
                competition_id=competition.id,
                rank=rank,
                fis_code=fis_code,
                athlete_name=name,
                nation=nation,
                total_points=total_points,
            )
        )

    competition.status = "completed"
    logger.info("Results imported for %s", competition.name)
