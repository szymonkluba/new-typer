---
name: run-typer
description: Build, run, and drive the Typer ski jumping betting app. Use when asked to start Typer, run its tests, take a screenshot, or verify a change in the running app.
---

Typer is a FastAPI + SQLite + Jinja2 web app. Drive it via `preview_start` (Claude Code Desktop) or the smoke script at `.claude/skills/run-typer/smoke.sh`.

## Prerequisites

- Python 3.11+ (3.12 recommended)
- pip

No system-level packages needed beyond Python. Playwright is in `requirements.txt` but only used by the scraper jobs, not for running the app.

## Setup

```bash
python -m venv venv
venv/Scripts/activate  # Windows
# source venv/bin/activate  # Linux/macOS
pip install -r requirements.txt -r requirements-dev.txt
```

No `.env` file required for local dev. The app uses an SQLite file (`typer.db`) created automatically on first start.

### Environment variables (all optional)

| Variable | Default | Notes |
|---|---|---|
| `DATABASE_URL` | `sqlite:///typer.db` | SQLAlchemy connection string |
| `TIMEZONE` | `Europe/Warsaw` | For betting cutoff calculation |
| `BET_CUTOFF_HOUR` | `16` | Default hour (local time) after which betting closes |

## Run (agent path)

### Claude Code Desktop — browser pane

A `launch.json` is already configured. Start the dev server and open the browser pane:

```
preview_start with name "typer-dev"
```

This starts `python run.py` (uvicorn with hot reload on port 8000) and opens `http://localhost:8000` in the browser pane. Use `read_page`, `computer`, `navigate`, and `screenshot` to interact.

Key pages to verify after a change:

| URL | What to check |
|---|---|
| `/` | Homepage renders, leaderboard and upcoming competitions show |
| `/competitions` | Tab filters (upcoming/completed/all) work |
| `/competitions/<id>` | Bet form visible if betting open, autocomplete works |
| `/auth/register` | Registration form renders |
| `/auth/login` | Login form renders |
| `/ranking` | Leaderboard table renders |
| `/health` | Returns `{"status":"ok"}` |

### Smoke script — quick verification without browser

```bash
PYTHON=venv/Scripts/python.exe TMPDIR=$TEMP bash .claude/skills/run-typer/smoke.sh
```

On Linux/macOS:
```bash
PYTHON=venv/bin/python bash .claude/skills/run-typer/smoke.sh
```

The smoke script starts the dev server in the background, hits 12 endpoints (health, all public pages, language toggle, auth flow, autocomplete, 404 handling), and reports pass/fail. It cleans up the server process on exit.

Output on success:
```
=== Results: 12 passed, 0 failed ===
```

## Run (human path)

```bash
python run.py
```

Opens uvicorn with hot reload at `http://localhost:8000`. Ctrl+C to stop.

## Test

```bash
python -m pytest tests/ -v --tb=short
```

175 tests, all pass. Tests use an in-memory SQLite database and mock the scraper scheduler. No external services needed.

## Gotchas

- **The SQLite DB file (`typer.db`) is created in the working directory.** If you `cd` into a subdirectory and run the app, it creates a separate empty database there. Always run from the repo root.
- **Scraper scheduler starts on app boot.** In dev this is fine — the cron jobs won't fire for hours. Tests mock it out via `conftest.py`.
- **`betting_open` is time-sensitive.** The `Competition.betting_open` property checks the current time against the competition date + cutoff hour. Tests that need betting to be blocked use `patch("app.config.BET_CUTOFF_HOUR", 0)` — patch the config module, not the model.
- **Static files are served by FastAPI in dev** (`/static` mount) but by nginx in production. CSS/JS changes are immediate in dev, but production needs `cp` to `/var/www/typer/static/` with SELinux context restore.
- **The `launch.json` points to the main repo's venv**, not the worktree's. If the venv path changes, update `.claude/launch.json`.
