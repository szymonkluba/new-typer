import sys
from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from app.models import Athlete, Competition, Result
from app.scraper.fis import (
    _parse_athlete_row,
    _parse_fis_date,
    sync_athletes_from_fis,
    sync_competitions_from_fis,
    sync_results_from_fis,
)

# --- _parse_fis_date ---


class TestParseFisDate:
    def test_format_dmy(self):
        assert _parse_fis_date("25 Dec 2024") == date(2024, 12, 25)

    def test_format_full_month(self):
        assert _parse_fis_date("25 December 2024") == date(2024, 12, 25)

    def test_format_mdy(self):
        assert _parse_fis_date("Dec 25, 2024") == date(2024, 12, 25)

    def test_format_dotted(self):
        assert _parse_fis_date("25.12.2024") == date(2024, 12, 25)

    def test_no_year_day_first(self):
        result = _parse_fis_date("25 Dec")
        assert result.month == 12
        assert result.day == 25
        assert result.year == date.today().year

    def test_no_year_month_first(self):
        result = _parse_fis_date("Dec 25")
        assert result.month == 12
        assert result.day == 25
        assert result.year == date.today().year

    def test_leading_trailing_whitespace(self):
        assert _parse_fis_date("  25 Dec 2024  ") == date(2024, 12, 25)

    def test_unparseable_raises_valueerror(self):
        with pytest.raises(ValueError):
            _parse_fis_date("not a date")

    def test_empty_string_raises_valueerror(self):
        with pytest.raises(ValueError):
            _parse_fis_date("")

    def test_invalid_month_raises_valueerror(self):
        with pytest.raises(ValueError):
            _parse_fis_date("25 Xyz 2024")


# --- sync_results_from_fis ---

RESULTS_HTML = """
<html><body>
<table>
<tbody>
<tr><td>1</td><td>AUT</td><td>Stefan Kraft</td><td>AUT</td><td>280.5</td></tr>
<tr><td>2</td><td>GER</td><td>Karl Geiger</td><td>GER</td><td>275.0</td></tr>
<tr><td>3</td><td>NOR</td><td>Halvor Granerud</td><td>NOR</td><td>270.0</td></tr>
</tbody>
</table>
</body></html>
"""


class _NoCloseSession:
    """Wraps a session to prevent close() from being called by the scraper."""

    def __init__(self, session):
        self._session = session

    def __getattr__(self, name):
        if name == "close":
            return lambda: None
        return getattr(self._session, name)


class TestSyncResults:
    def test_sync_results_processes_past_upcoming_with_race_id(self, db, make_competition, test_engine):
        comp = make_competition(
            status="upcoming",
            comp_date=date(2020, 1, 1),
            fis_race_id=1234,
        )
        comp_id = comp.id
        mock_resp = MagicMock()
        mock_resp.text = RESULTS_HTML
        mock_resp.raise_for_status = MagicMock()

        wrapped = _NoCloseSession(db)
        with (
            patch("app.scraper.fis.SessionLocal", return_value=wrapped),
            patch("app.scraper.fis.httpx.get", return_value=mock_resp),
        ):
            sync_results_from_fis()

        db.expire_all()
        results = db.query(Result).filter(Result.competition_id == comp_id).all()
        assert len(results) == 3
        comp = db.query(Competition).filter(Competition.id == comp_id).first()
        assert comp.status == "completed"

    def test_sync_results_skips_future_date(self, db, make_competition):
        comp = make_competition(
            status="upcoming",
            comp_date=date(2099, 12, 31),
            fis_race_id=1234,
        )
        comp_id = comp.id
        wrapped = _NoCloseSession(db)
        with patch("app.scraper.fis.SessionLocal", return_value=wrapped):
            sync_results_from_fis()

        results = db.query(Result).filter(Result.competition_id == comp_id).all()
        assert len(results) == 0

    def test_sync_results_skips_null_race_id(self, db, make_competition):
        comp = make_competition(
            status="upcoming",
            comp_date=date(2020, 1, 1),
            fis_race_id=None,
        )
        comp_id = comp.id
        wrapped = _NoCloseSession(db)
        with patch("app.scraper.fis.SessionLocal", return_value=wrapped):
            sync_results_from_fis()

        results = db.query(Result).filter(Result.competition_id == comp_id).all()
        assert len(results) == 0

    def test_sync_results_skips_completed(self, db, make_competition):
        comp = make_competition(
            status="completed",
            comp_date=date(2020, 1, 1),
            fis_race_id=1234,
        )
        comp_id = comp.id
        wrapped = _NoCloseSession(db)
        with patch("app.scraper.fis.SessionLocal", return_value=wrapped):
            sync_results_from_fis()

        results = db.query(Result).filter(Result.competition_id == comp_id).all()
        assert len(results) == 0

    def test_sync_results_skips_if_results_exist(self, db, make_competition, make_result):
        comp = make_competition(
            status="upcoming",
            comp_date=date(2020, 1, 1),
            fis_race_id=1234,
        )
        comp_id = comp.id
        make_result(comp_id, 1, "Existing", "POL")

        mock_resp = MagicMock()
        mock_resp.text = RESULTS_HTML
        mock_resp.raise_for_status = MagicMock()

        wrapped = _NoCloseSession(db)
        with (
            patch("app.scraper.fis.SessionLocal", return_value=wrapped),
            patch("app.scraper.fis.httpx.get", return_value=mock_resp),
        ):
            sync_results_from_fis()

        db.expire_all()
        results = db.query(Result).filter(Result.competition_id == comp_id).all()
        assert len(results) == 1

    def test_sync_results_handles_no_table_html(self, db, make_competition):
        comp = make_competition(
            status="upcoming",
            comp_date=date(2020, 1, 1),
            fis_race_id=1234,
        )
        comp_id = comp.id
        mock_resp = MagicMock()
        mock_resp.text = "<html><body><p>No results</p></body></html>"
        mock_resp.raise_for_status = MagicMock()

        wrapped = _NoCloseSession(db)
        with (
            patch("app.scraper.fis.SessionLocal", return_value=wrapped),
            patch("app.scraper.fis.httpx.get", return_value=mock_resp),
        ):
            sync_results_from_fis()

        results = db.query(Result).filter(Result.competition_id == comp_id).all()
        assert len(results) == 0

    def test_sync_results_handles_http_error(self, db, make_competition):
        comp = make_competition(
            status="upcoming",
            comp_date=date(2020, 1, 1),
            fis_race_id=1234,
        )
        comp_id = comp.id
        import httpx

        wrapped = _NoCloseSession(db)
        with (
            patch("app.scraper.fis.SessionLocal", return_value=wrapped),
            patch("app.scraper.fis.httpx.get", side_effect=httpx.HTTPError("fail")),
        ):
            sync_results_from_fis()

        results = db.query(Result).filter(Result.competition_id == comp_id).all()
        assert len(results) == 0

    def test_sync_results_parses_top_10_rows_only(self, db, make_competition):
        comp = make_competition(
            status="upcoming",
            comp_date=date(2020, 1, 1),
            fis_race_id=1234,
        )
        comp_id = comp.id
        rows = ""
        for i in range(15):
            rows += f"<tr><td>{i + 1}</td><td>POL</td><td>Athlete {i}</td><td>POL</td><td>{100 - i}.0</td></tr>\n"
        html = f"<html><body><table><tbody>{rows}</tbody></table></body></html>"

        mock_resp = MagicMock()
        mock_resp.text = html
        mock_resp.raise_for_status = MagicMock()

        wrapped = _NoCloseSession(db)
        with (
            patch("app.scraper.fis.SessionLocal", return_value=wrapped),
            patch("app.scraper.fis.httpx.get", return_value=mock_resp),
        ):
            sync_results_from_fis()

        db.expire_all()
        results = db.query(Result).filter(Result.competition_id == comp_id).all()
        assert len(results) == 10


# --- sync_competitions_from_fis ---


class TestSyncCompetitions:
    def test_sync_competitions_skips_without_playwright(self):
        # Setting a module to None in sys.modules causes ImportError on import
        saved = {k: sys.modules.pop(k) for k in list(sys.modules) if k.startswith("playwright")}
        with patch.dict(sys.modules, {"playwright": None, "playwright.sync_api": None}):
            sync_competitions_from_fis()
        sys.modules.update(saved)

    def test_sync_competitions_handles_exception(self, db):
        mock_pw = MagicMock()
        saved = {k: sys.modules.pop(k) for k in list(sys.modules) if k.startswith("playwright")}
        wrapped = _NoCloseSession(db)
        with (
            patch.dict(sys.modules, {"playwright": mock_pw, "playwright.sync_api": mock_pw.sync_api}),
            patch("app.scraper.fis.SessionLocal", return_value=wrapped),
            patch("app.scraper.fis._scrape_calendar", side_effect=RuntimeError("boom")),
        ):
            sync_competitions_from_fis()
        sys.modules.update(saved)


# --- sync_athletes_from_fis ---


def _mock_athlete_row(fis_code, competitor_id, name, nation):
    """Create a mock Playwright ElementHandle that mimics an athlete row."""
    row = MagicMock()
    row.get_attribute.return_value = (
        f"https://www.fis-ski.com/DB/general/athlete-biography.html?sectorcode=JP&competitorid={competitor_id}"
    )

    fis_code_div = MagicMock()
    fis_code_div.inner_text.return_value = str(fis_code)
    status_div = MagicMock()
    status_div.inner_text.return_value = "Active"

    col0 = MagicMock()
    col0.query_selector_all.return_value = [status_div, fis_code_div]

    col1 = MagicMock()
    col1.inner_text.return_value = name

    col2 = MagicMock()

    nation_el = MagicMock()
    nation_el.inner_text.return_value = nation
    row.query_selector.return_value = nation_el

    row.query_selector_all.return_value = [col0, col1, col2]
    return row


class TestParseAthleteRow:
    def test_parses_valid_row(self):
        row = _mock_athlete_row(6996, 182547, "AALTO Antti", "FIN")
        result = _parse_athlete_row(row)
        assert result == (6996, 182547, "AALTO Antti", "FIN")

    def test_returns_none_for_missing_href(self):
        row = MagicMock()
        row.get_attribute.return_value = None
        assert _parse_athlete_row(row) is None

    def test_returns_none_for_no_competitor_id(self):
        row = MagicMock()
        row.get_attribute.return_value = "https://www.fis-ski.com/DB/general/biographies.html"
        assert _parse_athlete_row(row) is None

    def test_returns_none_for_too_few_columns(self):
        row = MagicMock()
        row.get_attribute.return_value = "https://www.fis-ski.com/DB/general/athlete-biography.html?competitorid=123"
        row.query_selector_all.return_value = [MagicMock(), MagicMock()]
        assert _parse_athlete_row(row) is None

    def test_returns_none_for_non_numeric_fis_code(self):
        row = MagicMock()
        row.get_attribute.return_value = "https://www.fis-ski.com/DB/general/athlete-biography.html?competitorid=123"
        fis_code_div = MagicMock()
        fis_code_div.inner_text.return_value = "abc"
        status_div = MagicMock()
        col0 = MagicMock()
        col0.query_selector_all.return_value = [status_div, fis_code_div]
        col1 = MagicMock()
        col1.inner_text.return_value = "TEST Name"
        col2 = MagicMock()
        row.query_selector_all.return_value = [col0, col1, col2]
        assert _parse_athlete_row(row) is None

    def test_returns_none_for_empty_name(self):
        row = _mock_athlete_row(6996, 182547, "", "FIN")
        assert _parse_athlete_row(row) is None


class TestSyncAthletes:
    def test_sync_athletes_skips_without_playwright(self):
        saved = {k: sys.modules.pop(k) for k in list(sys.modules) if k.startswith("playwright")}
        with patch.dict(sys.modules, {"playwright": None, "playwright.sync_api": None}):
            sync_athletes_from_fis()
        sys.modules.update(saved)

    def test_sync_athletes_handles_exception(self, db):
        mock_pw = MagicMock()
        saved = {k: sys.modules.pop(k) for k in list(sys.modules) if k.startswith("playwright")}
        wrapped = _NoCloseSession(db)
        with (
            patch.dict(sys.modules, {"playwright": mock_pw, "playwright.sync_api": mock_pw.sync_api}),
            patch("app.scraper.fis.SessionLocal", return_value=wrapped),
            patch("app.scraper.fis._scrape_athletes", side_effect=RuntimeError("boom")),
        ):
            sync_athletes_from_fis()
        sys.modules.update(saved)

    def test_sync_athletes_inserts_new(self, db, test_engine):
        mock_rows = [
            _mock_athlete_row(6996, 182547, "AALTO Antti", "FIN"),
            _mock_athlete_row(9348, 245955, "AARDAL Johannes", "NOR"),
        ]

        mock_page = MagicMock()
        mock_page.query_selector_all.return_value = mock_rows
        mock_page.wait_for_selector.return_value = MagicMock()

        mock_context = MagicMock()
        mock_context.new_page.return_value = mock_page

        mock_browser = MagicMock()
        mock_browser.new_context.return_value = mock_context

        mock_pw_instance = MagicMock()
        mock_pw_instance.chromium.launch.return_value = mock_browser
        mock_pw_instance.__enter__ = MagicMock(return_value=mock_pw_instance)
        mock_pw_instance.__exit__ = MagicMock(return_value=False)

        mock_sync_pw = MagicMock(return_value=mock_pw_instance)

        saved = {k: sys.modules.pop(k) for k in list(sys.modules) if k.startswith("playwright")}
        mock_pw_module = MagicMock()
        mock_pw_module.sync_api.sync_playwright = mock_sync_pw
        wrapped = _NoCloseSession(db)
        with (
            patch.dict(
                sys.modules,
                {"playwright": mock_pw_module, "playwright.sync_api": mock_pw_module.sync_api},
            ),
            patch("app.scraper.fis.SessionLocal", return_value=wrapped),
        ):
            sync_athletes_from_fis()

        sys.modules.update(saved)

        db.expire_all()
        athletes = db.query(Athlete).all()
        assert len(athletes) == 2
        aalto = db.query(Athlete).filter(Athlete.fis_code == 6996).first()
        assert aalto.name == "AALTO Antti"
        assert aalto.nation == "FIN"
        assert aalto.competitor_id == 182547

    def test_sync_athletes_updates_existing(self, db, make_athlete, test_engine):
        make_athlete(fis_code=6996, competitor_id=182547, name="AALTO Antti", nation="FIN")

        mock_rows = [
            _mock_athlete_row(6996, 182547, "AALTO Antti-Pekka", "FIN"),
        ]

        mock_page = MagicMock()
        mock_page.query_selector_all.return_value = mock_rows
        mock_page.wait_for_selector.return_value = MagicMock()

        mock_context = MagicMock()
        mock_context.new_page.return_value = mock_page

        mock_browser = MagicMock()
        mock_browser.new_context.return_value = mock_context

        mock_pw_instance = MagicMock()
        mock_pw_instance.chromium.launch.return_value = mock_browser
        mock_pw_instance.__enter__ = MagicMock(return_value=mock_pw_instance)
        mock_pw_instance.__exit__ = MagicMock(return_value=False)

        mock_pw_module = MagicMock()
        mock_pw_module.sync_api.sync_playwright = MagicMock(return_value=mock_pw_instance)

        saved = {k: sys.modules.pop(k) for k in list(sys.modules) if k.startswith("playwright")}
        wrapped = _NoCloseSession(db)
        with (
            patch.dict(
                sys.modules,
                {"playwright": mock_pw_module, "playwright.sync_api": mock_pw_module.sync_api},
            ),
            patch("app.scraper.fis.SessionLocal", return_value=wrapped),
        ):
            sync_athletes_from_fis()

        sys.modules.update(saved)

        db.expire_all()
        athletes = db.query(Athlete).all()
        assert len(athletes) == 1
        assert athletes[0].name == "AALTO Antti-Pekka"
