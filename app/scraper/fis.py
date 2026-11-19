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

        events = []
        for row in rows:
            try:
                event = _parse_calendar_row(row)
                if event:
                    events.append(event)
            except Exception:
                logger.debug("Skipping unparseable calendar row", exc_info=True)

        for event in events:
            try:
                _create_competitions_for_event(db, page, event)
            except Exception:
                logger.debug(
                    "Failed to discover races for event %s",
                    event.get("fis_event_id"),
                    exc_info=True,
                )

        browser.close()

    db.commit()
    logger.info("Calendar sync complete")


def _parse_calendar_row(row) -> dict | None:
    """Parse a calendar row and return event metadata, or None to skip."""
    link = row.query_selector("a[href*='eventid']")
    if not link:
        return None
    href = link.get_attribute("href")
    fis_event_id = None
    if href and "eventid=" in href:
        try:
            fis_event_id = int(href.split("eventid=")[1].split("&")[0])
        except (ValueError, IndexError):
            return None

    text = row.inner_text()
    lines = [l.strip() for l in text.split("\n") if l.strip()]

    date_text = ""
    data_lines = [l for l in lines if len(l) > 1 or not l.isalpha()]
    for line in data_lines:
        if any(
            month in line
            for month in ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        ):
            date_text = line
            break

    venue_el = row.query_selector(".g-lg-7.hidden-sm-down .split-row__item")
    if not venue_el:
        venue_el = row.query_selector(".g-lg-7.hidden-sm-down")
    venue = venue_el.inner_text().strip() if venue_el else "Unknown"

    cat_el = row.query_selector(".g-lg-7.g-sm-6")
    category = "WC"
    if cat_el:
        cat_text = cat_el.inner_text().upper()
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
        return None

    try:
        comp_date = _parse_fis_date(date_text)
    except (ValueError, IndexError):
        logger.warning("Unparseable date '%s' for %s, skipping row", date_text, venue)
        return None

    return {
        "fis_event_id": fis_event_id,
        "venue": venue,
        "date": comp_date,
        "category": category,
        "gender": gender,
    }


def _discover_races_for_event(page, fis_event_id: int) -> list[dict]:
    """Visit event details page and return all non-qualification races."""
    url = f"{FIS_EVENT_URL}?sectorcode=JP&eventid={fis_event_id}"
    page.goto(url, wait_until="domcontentloaded", timeout=30000)

    try:
        page.wait_for_selector("a[href*='raceid=']", timeout=15000)
    except Exception:
        return []

    links = page.query_selector_all("a[href*='raceid=']")
    races = []
    seen_race_ids = set()

    for link in links:
        href = link.get_attribute("href") or ""
        if "raceid=" not in href:
            continue
        text = link.inner_text().strip()
        upper_text = text.upper()

        skip_keywords = ("QUALIFICATION", "TRAINING", "TRIAL", "PROLOGUE")
        if any(kw in upper_text for kw in skip_keywords) or "QUA" in upper_text.split():
            continue

        try:
            race_id = int(href.split("raceid=")[1].split("&")[0])
        except (ValueError, IndexError):
            continue

        if race_id in seen_race_ids:
            continue
        seen_race_ids.add(race_id)

        race_type = "team" if "TEAM" in upper_text else "individual"

        races.append(
            {
                "fis_race_id": race_id,
                "type": race_type,
                "description": text,
            }
        )

    return races


def _create_competitions_for_event(db: Session, page, event: dict):
    """Discover races for an event and create Competition records."""
    fis_event_id = event["fis_event_id"]
    if not fis_event_id:
        return

    races = _discover_races_for_event(page, fis_event_id)

    if not races:
        existing = db.query(Competition).filter(Competition.fis_event_id == fis_event_id).first()
        if existing:
            return
        comp = Competition(
            fis_event_id=fis_event_id,
            name=f"Ski Jumping {event['category']} - {event['venue']}",
            venue=event["venue"],
            date=event["date"],
            category=event["category"],
            type="individual",
            gender=event["gender"],
            status="upcoming",
        )
        db.add(comp)
        logger.info("Added competition: %s (%s)", comp.name, event["date"])
        return

    # Upgrade legacy competitions (created before per-race scraping)
    legacy_comps = list(
        db.query(Competition)
        .filter(
            Competition.fis_event_id == fis_event_id,
            Competition.fis_race_id.is_(None),
        )
        .all()
    )

    for race in races:
        existing = db.query(Competition).filter(Competition.fis_race_id == race["fis_race_id"]).first()
        if existing:
            continue

        upgraded = False
        for i, legacy in enumerate(legacy_comps):
            if legacy.type == race["type"]:
                legacy.fis_race_id = race["fis_race_id"]
                legacy.name = f"Ski Jumping {event['category']} - {event['venue']} - {race['description']}"
                logger.info("Upgraded competition: %s (race_id=%d)", legacy.name, race["fis_race_id"])
                legacy_comps.pop(i)
                upgraded = True
                break

        if not upgraded:
            name = f"Ski Jumping {event['category']} - {event['venue']} - {race['description']}"
            comp = Competition(
                fis_event_id=fis_event_id,
                fis_race_id=race["fis_race_id"],
                name=name,
                venue=event["venue"],
                date=event["date"],
                category=event["category"],
                type=race["type"],
                gender=event["gender"],
                status="upcoming",
            )
            db.add(comp)
            logger.info("Added competition: %s (%s, %s)", name, event["venue"], event["date"])


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
