import sys
from datetime import date
from unittest.mock import patch, MagicMock

import pytest

from app.scraper.fis import _parse_fis_date, sync_results_from_fis, sync_competitions_from_fis
from app.models import Competition, Result


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
        with patch("app.scraper.fis.SessionLocal", return_value=wrapped), \
             patch("app.scraper.fis.httpx.get", return_value=mock_resp):
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
        with patch("app.scraper.fis.SessionLocal", return_value=wrapped), \
             patch("app.scraper.fis.httpx.get", return_value=mock_resp):
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
        with patch("app.scraper.fis.SessionLocal", return_value=wrapped), \
             patch("app.scraper.fis.httpx.get", return_value=mock_resp):
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
        with patch("app.scraper.fis.SessionLocal", return_value=wrapped), \
             patch("app.scraper.fis.httpx.get", side_effect=httpx.HTTPError("fail")):
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
            rows += f"<tr><td>{i+1}</td><td>POL</td><td>Athlete {i}</td><td>POL</td><td>{100-i}.0</td></tr>\n"
        html = f"<html><body><table><tbody>{rows}</tbody></table></body></html>"

        mock_resp = MagicMock()
        mock_resp.text = html
        mock_resp.raise_for_status = MagicMock()

        wrapped = _NoCloseSession(db)
        with patch("app.scraper.fis.SessionLocal", return_value=wrapped), \
             patch("app.scraper.fis.httpx.get", return_value=mock_resp):
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
        with patch.dict(sys.modules, {"playwright": mock_pw, "playwright.sync_api": mock_pw.sync_api}), \
             patch("app.scraper.fis.SessionLocal", return_value=wrapped), \
             patch("app.scraper.fis._scrape_calendar", side_effect=RuntimeError("boom")):
            sync_competitions_from_fis()
        sys.modules.update(saved)
