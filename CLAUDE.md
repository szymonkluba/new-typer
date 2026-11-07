# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Run dev server (auto-reloads)
python run.py

# Run all tests
pytest tests/ -v --tb=short

# Run a single test file or class
pytest tests/test_bets_routes.py -v
pytest tests/test_bets_routes.py::TestAthleteAutocomplete -v

# Lint and format
ruff check .
ruff format --check .
ruff check --fix .
ruff format .
```

The venv lives at the repo root (`venv/`). CI uses Python 3.11.

## Architecture

FastAPI app with server-rendered Jinja2 templates, SQLite via SQLAlchemy, and a FIS scraper that populates competition/athlete/result data.

### Request flow

`app/main.py` creates the FastAPI app and wires routers. An HTTP middleware reads a `lang` cookie and sets a `contextvars.ContextVar` (`current_lang` in `app/templating.py`) that all translation calls use — there is no request-scoped lang parameter passed around.

### Routing modules

Each feature lives under `app/<feature>/router.py` with prefix:
- `app/auth/` — `/auth` — register, login, logout (bcrypt for passwords, itsdangerous signed cookies for sessions)
- `app/competitions/` — `/competitions` — list and detail views
- `app/bets/` — `/bets` — place/update bets, HTMX athlete autocomplete endpoint (`GET /bets/athletes`)
- `app/ranking/` — `/ranking` — leaderboard

### i18n

All user-facing strings go through `app/i18n.py` (a flat `TRANSLATIONS` dict keyed by `"pl"` / `"en"`). Default language is Polish (`pl`). In templates, use `{{ _("key") }}`. In Python, import `_` from `app.templating`. Custom Jinja filters: `format_date`, `translate_status`.

### Scraper

`app/scraper/fis.py` scrapes FIS website (using Playwright + BeautifulSoup) for competitions, results, and athletes. `app/scraper/scheduler.py` runs these on APScheduler cron/interval triggers during app lifespan. Scraper schedule is configurable via env vars in `app/config.py`.

### Scoring

`app/bets/scoring.py` — users bet on podium positions (1st, 2nd, 3rd). Exact position match = 3 points, athlete on podium but wrong position = 1 point. Name matching is case-insensitive and Unicode-normalized.

### Betting cutoff

`Competition.betting_open` (property on the model) closes betting at the competition's `start_time` (or `BET_CUTOFF_HOUR`, default 16:00) on competition day, in `Europe/Warsaw` timezone.

### Test setup

Tests use an in-memory SQLite database. The test client sets `lang=en` cookie. The scheduler is patched out. Factory fixtures (`make_user`, `make_competition`, `make_result`, `make_athlete`, `make_bet`) are in `tests/conftest.py`.
