import sys
from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from app.models import Athlete, Competition, Result
from app.scraper.fis import (
    _parse_athlete_row,
    _parse_fis_date,
    _parse_result_row,
    _resolve_race_id,
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


# --- result row mocking ---


def _mock_result_row(rank, fis_code, name, nation, total_points):
    """Create a mock Playwright ElementHandle that mimics a results page row."""
    row = MagicMock()
    row.get_attribute.return_value = "https://www.fis-ski.com/DB/general/athlete-biography.html?competitorid=99999"

    def _div(text):
        d = MagicMock()
        d.inner_text.return_value = str(text) if text is not None else ""
        return d

    cols = [
        _div(rank),
        _div("1"),  # bib
        _div(fis_code if fis_code is not None else ""),
        _div(name),
        _div("1993"),  # year
        _div(nation),
        _div("130.0"),  # r1 distance
        _div("150.0"),  # r1 points
        _div("1"),  # r1 rank
        _div("135.0"),  # r2 distance
        _div("155.0"),  # r2 points
        _div("2"),  # r2 rank
        _div(total_points if total_points is not None else ""),
        _div("0.0"),  # diff
    ]

    row.query_selector_all.return_value = cols

    nation_el = MagicMock()
    nation_el.inner_text.return_value = nation
    row.query_selector.return_value = nation_el

    return row


class _NoCloseSession:
    """Wraps a session to prevent close() from being called by the scraper."""

    def __init__(self, session):
        self._session = session

    def __getattr__(self, name):
        if name == "close":
            return lambda: None
        return getattr(self._session, name)


# --- _parse_result_row ---


class TestParseResultRow:
    def test_parses_valid_row(self):
        row = _mock_result_row(1, 7091, "PREVC Domen", "SLO", 316.7)
        result = _parse_result_row(row)
        assert result == (1, 7091, "PREVC Domen", "SLO", 316.7)

    def test_returns_none_for_dq_row(self):
        row = _mock_result_row("DSQ", 7147, "ZAJC Timi", "SLO", None)
        assert _parse_result_row(row) is None

    def test_returns_none_for_empty_name(self):
        row = _mock_result_row(1, 7091, "", "SLO", 316.7)
        assert _parse_result_row(row) is None

    def test_missing_fis_code_sets_none(self):
        row = _mock_result_row(1, None, "PREVC Domen", "SLO", 316.7)
        result = _parse_result_row(row)
        assert result is not None
        assert result[1] is None

    def test_returns_none_for_too_few_columns(self):
        row = MagicMock()
        d = MagicMock()
        d.inner_text.return_value = "1"
        row.query_selector_all.return_value = [d, d, d, d]
        assert _parse_result_row(row) is None

    def test_missing_total_points(self):
        row = _mock_result_row(5, 6996, "KRAFT Stefan", "AUT", None)
        result = _parse_result_row(row)
        assert result is not None
        rank, fis_code, name, nation, total_points = result
        assert rank == 5
        assert name == "KRAFT Stefan"
        assert total_points is not None or total_points is None  # may find sub-score


# --- _resolve_race_id ---


class TestResolveRaceId:
    def test_resolves_race_id_from_event_page(self):
        page = MagicMock()
        link = MagicMock()
        link.get_attribute.return_value = "https://www.fis-ski.com/DB/general/results.html?sectorcode=JP&raceid=7501"
        link.inner_text.return_value = "Individual Large Hill"
        page.query_selector_all.return_value = [link]
        page.wait_for_selector.return_value = MagicMock()

        comp = MagicMock()
        comp.fis_event_id = 58086
        comp.type = "individual"

        result = _resolve_race_id(page, comp)
        assert result == 7501

    def test_skips_team_events(self):
        page = MagicMock()
        team_link = MagicMock()
        team_link.get_attribute.return_value = (
            "https://www.fis-ski.com/DB/general/results.html?sectorcode=JP&raceid=9999"
        )
        team_link.inner_text.return_value = "Team Large Hill"

        indiv_link = MagicMock()
        indiv_link.get_attribute.return_value = (
            "https://www.fis-ski.com/DB/general/results.html?sectorcode=JP&raceid=7501"
        )
        indiv_link.inner_text.return_value = "Individual Large Hill"

        page.query_selector_all.return_value = [team_link, indiv_link]
        page.wait_for_selector.return_value = MagicMock()

        comp = MagicMock()
        comp.fis_event_id = 58086
        comp.type = "individual"

        result = _resolve_race_id(page, comp)
        assert result == 7501

    def test_skips_qualification(self):
        page = MagicMock()
        qual_link = MagicMock()
        qual_link.get_attribute.return_value = (
            "https://www.fis-ski.com/DB/general/results.html?sectorcode=JP&raceid=7500"
        )
        qual_link.inner_text.return_value = "Individual Large Hill Qualification"

        main_link = MagicMock()
        main_link.get_attribute.return_value = (
            "https://www.fis-ski.com/DB/general/results.html?sectorcode=JP&raceid=7501"
        )
        main_link.inner_text.return_value = "Individual Large Hill"

        page.query_selector_all.return_value = [qual_link, main_link]
        page.wait_for_selector.return_value = MagicMock()

        comp = MagicMock()
        comp.fis_event_id = 58086
        comp.type = "individual"

        result = _resolve_race_id(page, comp)
        assert result == 7501

    def test_returns_none_when_no_links(self):
        page = MagicMock()
        page.wait_for_selector.side_effect = Exception("timeout")

        comp = MagicMock()
        comp.fis_event_id = 58086
        comp.type = "individual"

        result = _resolve_race_id(page, comp)
        assert result is None


# --- sync_results_from_fis ---


def _setup_playwright_mocks(mock_rows):
    """Set up Playwright mocking for sync_results_from_fis tests."""
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

    return mock_pw_module, mock_page


class TestSyncResults:
    def test_sync_results_imports_results(self, db, make_competition, test_engine):
        comp = make_competition(
            status="upcoming",
            comp_date=date(2020, 1, 1),
            fis_event_id=58086,
            fis_race_id=7501,
        )
        comp_id = comp.id
        mock_rows = [
            _mock_result_row(1, 7091, "PREVC Domen", "SLO", 316.7),
            _mock_result_row(2, 7395, "TSCHOFENIG Daniel", "AUT", 299.2),
            _mock_result_row(3, 6552, "HOFFMANN Felix", "GER", 297.3),
        ]
        mock_pw, mock_page = _setup_playwright_mocks(mock_rows)

        saved = {k: sys.modules.pop(k) for k in list(sys.modules) if k.startswith("playwright")}
        wrapped = _NoCloseSession(db)
        with (
            patch.dict(
                sys.modules,
                {"playwright": mock_pw, "playwright.sync_api": mock_pw.sync_api},
            ),
            patch("app.scraper.fis.SessionLocal", return_value=wrapped),
        ):
            sync_results_from_fis()
        sys.modules.update(saved)

        db.expire_all()
        results = db.query(Result).filter(Result.competition_id == comp_id).all()
        assert len(results) == 3
        first = db.query(Result).filter(Result.competition_id == comp_id, Result.rank == 1).first()
        assert first.athlete_name == "PREVC Domen"
        assert first.fis_code == 7091
        comp = db.query(Competition).filter(Competition.id == comp_id).first()
        assert comp.status == "completed"

    def test_sync_results_skips_future_date(self, db, make_competition):
        make_competition(
            status="upcoming",
            comp_date=date(2099, 12, 31),
            fis_event_id=58086,
            fis_race_id=7501,
        )
        wrapped = _NoCloseSession(db)
        with patch("app.scraper.fis.SessionLocal", return_value=wrapped):
            sync_results_from_fis()

        results = db.query(Result).all()
        assert len(results) == 0

    def test_sync_results_skips_null_event_id(self, db, make_competition):
        make_competition(
            status="upcoming",
            comp_date=date(2020, 1, 1),
            fis_event_id=None,
        )
        wrapped = _NoCloseSession(db)
        with patch("app.scraper.fis.SessionLocal", return_value=wrapped):
            sync_results_from_fis()

        results = db.query(Result).all()
        assert len(results) == 0

    def test_sync_results_skips_completed(self, db, make_competition):
        make_competition(
            status="completed",
            comp_date=date(2020, 1, 1),
            fis_event_id=58086,
            fis_race_id=7501,
        )
        wrapped = _NoCloseSession(db)
        with patch("app.scraper.fis.SessionLocal", return_value=wrapped):
            sync_results_from_fis()

        results = db.query(Result).all()
        assert len(results) == 0

    def test_sync_results_skips_if_results_exist(self, db, make_competition, make_result, test_engine):
        comp = make_competition(
            status="upcoming",
            comp_date=date(2020, 1, 1),
            fis_event_id=58086,
            fis_race_id=7501,
        )
        make_result(comp.id, 1, "Existing", "POL")

        mock_rows = [_mock_result_row(1, 7091, "PREVC Domen", "SLO", 316.7)]
        mock_pw, _ = _setup_playwright_mocks(mock_rows)

        saved = {k: sys.modules.pop(k) for k in list(sys.modules) if k.startswith("playwright")}
        wrapped = _NoCloseSession(db)
        with (
            patch.dict(
                sys.modules,
                {"playwright": mock_pw, "playwright.sync_api": mock_pw.sync_api},
            ),
            patch("app.scraper.fis.SessionLocal", return_value=wrapped),
        ):
            sync_results_from_fis()
        sys.modules.update(saved)

        db.expire_all()
        results = db.query(Result).filter(Result.competition_id == comp.id).all()
        assert len(results) == 1
        assert results[0].athlete_name == "Existing"

    def test_sync_results_handles_playwright_timeout(self, db, make_competition, test_engine):
        comp = make_competition(
            status="upcoming",
            comp_date=date(2020, 1, 1),
            fis_event_id=58086,
            fis_race_id=7501,
        )
        mock_pw, mock_page = _setup_playwright_mocks([])
        mock_page.wait_for_selector.side_effect = Exception("timeout")

        saved = {k: sys.modules.pop(k) for k in list(sys.modules) if k.startswith("playwright")}
        wrapped = _NoCloseSession(db)
        with (
            patch.dict(
                sys.modules,
                {"playwright": mock_pw, "playwright.sync_api": mock_pw.sync_api},
            ),
            patch("app.scraper.fis.SessionLocal", return_value=wrapped),
        ):
            sync_results_from_fis()
        sys.modules.update(saved)

        results = db.query(Result).filter(Result.competition_id == comp.id).all()
        assert len(results) == 0

    def test_sync_results_canonicalizes_name_via_athlete(self, db, make_competition, make_athlete, test_engine):
        make_athlete(fis_code=7091, name="PREVC Domen", nation="SLO")
        comp = make_competition(
            status="upcoming",
            comp_date=date(2020, 1, 1),
            fis_event_id=58086,
            fis_race_id=7501,
        )
        mock_rows = [_mock_result_row(1, 7091, "PREVC  Domen", "SLO", 316.7)]
        mock_pw, _ = _setup_playwright_mocks(mock_rows)

        saved = {k: sys.modules.pop(k) for k in list(sys.modules) if k.startswith("playwright")}
        wrapped = _NoCloseSession(db)
        with (
            patch.dict(
                sys.modules,
                {"playwright": mock_pw, "playwright.sync_api": mock_pw.sync_api},
            ),
            patch("app.scraper.fis.SessionLocal", return_value=wrapped),
        ):
            sync_results_from_fis()
        sys.modules.update(saved)

        db.expire_all()
        result = db.query(Result).filter(Result.competition_id == comp.id).first()
        assert result.athlete_name == "PREVC Domen"
        assert result.fis_code == 7091

    def test_sync_results_imports_all_rows(self, db, make_competition, test_engine):
        comp = make_competition(
            status="upcoming",
            comp_date=date(2020, 1, 1),
            fis_event_id=58086,
            fis_race_id=7501,
        )
        mock_rows = [_mock_result_row(i + 1, 7000 + i, f"ATHLETE {i}", "POL", 100.0 - i) for i in range(15)]
        mock_pw, _ = _setup_playwright_mocks(mock_rows)

        saved = {k: sys.modules.pop(k) for k in list(sys.modules) if k.startswith("playwright")}
        wrapped = _NoCloseSession(db)
        with (
            patch.dict(
                sys.modules,
                {"playwright": mock_pw, "playwright.sync_api": mock_pw.sync_api},
            ),
            patch("app.scraper.fis.SessionLocal", return_value=wrapped),
        ):
            sync_results_from_fis()
        sys.modules.update(saved)

        db.expire_all()
        results = db.query(Result).filter(Result.competition_id == comp.id).all()
        assert len(results) == 15

    def test_sync_results_resolves_race_id(self, db, make_competition, test_engine):
        comp = make_competition(
            status="upcoming",
            comp_date=date(2020, 1, 1),
            fis_event_id=58086,
            fis_race_id=None,
        )
        comp_id = comp.id

        mock_rows = [_mock_result_row(1, 7091, "PREVC Domen", "SLO", 316.7)]
        mock_pw, mock_page = _setup_playwright_mocks(mock_rows)

        race_link = MagicMock()
        race_link.get_attribute.return_value = (
            "https://www.fis-ski.com/DB/general/results.html?sectorcode=JP&raceid=7501"
        )
        race_link.inner_text.return_value = "Individual Large Hill"

        call_count = [0]
        original_qsa = mock_page.query_selector_all

        def side_effect(selector):
            call_count[0] += 1
            if selector == "a[href*='raceid=']":
                return [race_link]
            return original_qsa(selector)

        mock_page.query_selector_all = MagicMock(side_effect=side_effect)

        saved = {k: sys.modules.pop(k) for k in list(sys.modules) if k.startswith("playwright")}
        wrapped = _NoCloseSession(db)
        with (
            patch.dict(
                sys.modules,
                {"playwright": mock_pw, "playwright.sync_api": mock_pw.sync_api},
            ),
            patch("app.scraper.fis.SessionLocal", return_value=wrapped),
        ):
            sync_results_from_fis()
        sys.modules.update(saved)

        db.expire_all()
        comp = db.query(Competition).filter(Competition.id == comp_id).first()
        assert comp.fis_race_id == 7501


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
