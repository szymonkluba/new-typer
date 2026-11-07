---
name: implement-feature
description: Implement a new feature or change existing behavior in Typer. Use when asked to add a feature, change behavior, fix a bug, refactor, or implement a user story. Expects a feature description.
---

Workflow skill for implementing features in the Typer ski jumping betting app (FastAPI + SQLite + Jinja2 + HTMX). Follow these steps in order. Use `/run-typer` for local verification and `/deploy-typer` for production deployment.

All paths below are relative to the repo root.

## Step 1: Create a feature branch

Branch from `main`. Use a slug that describes the feature:

```bash
git checkout main
git pull origin main
git checkout -b feature/<short-slug>
```

Convention from past PRs: branches use `feature/` or `claude/` prefix with a kebab-case slug.

## Step 2: Understand the architecture

### Source layout

```
app/
  main.py              # FastAPI app, lifespan, middleware, index route
  config.py            # Environment-driven config vars
  database.py          # SQLAlchemy engine, SessionLocal, create_tables, migrations
  models.py            # All SQLAlchemy models (Athlete, User, Competition, Result, Bet)
  i18n.py              # TRANSLATIONS dict (pl + en), translate(), format_date_localized()
  templating.py        # Jinja2 setup, _() translation helper, current_lang ContextVar
  auth/
    router.py          # /auth/login, /auth/register, /auth/logout
    dependencies.py    # get_current_user (cookie-based sessions)
    utils.py           # hash_password, verify_password (bcrypt)
  bets/
    router.py          # /bets/place/<id>, /bets/my, /bets/athletes (autocomplete)
    scoring.py         # score_bet() — points calculation
  competitions/
    router.py          # /competitions, /competitions/<id>
  ranking/
    router.py          # /ranking
  scraper/
    fis.py             # Playwright scrapers: competitions, athletes, results
    scheduler.py       # APScheduler cron jobs
  static/css/style.css # Single CSS file
  templates/           # Jinja2 templates with HTMX
    base.html          # Layout: navbar, footer, lang toggle
    index.html         # Homepage: leaderboard + upcoming competitions
    error.html
    auth/login.html, register.html
    bets/my_bets.html
    competitions/list.html, detail.html
    ranking/leaderboard.html
```

### Key patterns

- **Routers** are FastAPI `APIRouter` with `prefix` and `tags`. Register new ones in `app/main.py`.
- **Templates** use Jinja2 with `_("key")` for i18n. Every user-facing string must be in both `pl` and `en` dicts in `app/i18n.py`.
- **Database** uses SQLAlchemy ORM. Models are in `app/models.py`. New tables are auto-created by `Base.metadata.create_all()`. New columns on existing tables need `ALTER TABLE` (see Step 6).
- **Auth** is cookie-based. `get_current_user` returns `User | None`. Use `Depends(get_current_user)` in route params.
- **Config** uses `os.getenv()` with defaults in `app/config.py`.
- **Business logic** belongs on the model (e.g., `Competition.betting_open`) or in a module next to the router (e.g., `bets/scoring.py`), not in the router itself.

### Linting rules

CI runs `ruff check .` and `ruff format --check .` with config in `ruff.toml`:
- Target: Python 3.11, line length 120
- Rules: E (pycodestyle), F (pyflakes), I (isort)
- E501 (line too long) is ignored

Run locally before committing:

```bash
python -m ruff check . --fix
python -m ruff format .
```

## Step 3: Implement the feature

### Adding a new route

1. Create or edit the router file in `app/<module>/router.py`
2. Register the router in `app/main.py` if new
3. Add template in `app/templates/<module>/`
4. Add all user-facing strings to both language dicts in `app/i18n.py`
5. Update `app/static/css/style.css` if new UI elements need styling

### Adding a new model or column

1. Add/modify the model in `app/models.py`
2. New tables: handled automatically by `create_tables()`
3. New columns on existing tables: add auto-migration in `app/database.py` `_migrate_db()`:

```python
def _migrate_db():
    inspector = sa_inspect(engine)
    if "<table>" in inspector.get_table_names():
        columns = [col["name"] for col in inspector.get_columns("<table>")]
        if "<new_col>" not in columns:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE <table> ADD COLUMN <new_col> <TYPE>"))
```

### Adding config

Add to `app/config.py` with `os.getenv()` and a sensible default. Import from `app.config` where needed.

## Step 4: Write tests

Tests go in `tests/test_<module>.py`. Use the fixtures from `tests/conftest.py`:

| Fixture | What it gives you |
|---|---|
| `client` | Starlette TestClient with mocked scheduler, `lang=en` cookie |
| `db` | SQLAlchemy session (in-memory SQLite, auto-rolled-back) |
| `auth_client(user)` | TestClient with session cookie for the given user |
| `make_user(username?, password?)` | Creates and returns a User |
| `make_competition(name?, venue?, comp_date?, status?, ...)` | Creates and returns a Competition |
| `make_result(competition_id, rank, athlete_name, nation?, ...)` | Creates and returns a Result |
| `make_athlete(fis_code?, competitor_id?, name?, nation?)` | Creates and returns an Athlete |
| `make_bet(user_id, competition_id, position, athlete_name)` | Creates and returns a Bet |

Test patterns:
- Group tests in classes: `class TestFeatureName:`
- Test both success and error cases
- For time-sensitive logic, use `patch("app.config.VARIABLE", value)`
- For routes, check status codes and response content
- For auth-required routes, test both authenticated and unauthenticated

Run tests:

```bash
python -m pytest tests/ -v --tb=short
```

All 175+ existing tests must still pass.

## Step 5: Manual verification

Start the dev server and verify the feature works in the browser:

```bash
preview_start with name "typer-dev"
```

Or use the smoke script:

```bash
PYTHON=venv/Scripts/python.exe TMPDIR=$TEMP bash .claude/skills/run-typer/smoke.sh
```

For UI changes, navigate to the affected pages in the browser pane and take screenshots. Test:
- The golden path (feature works as expected)
- Edge cases (empty states, missing data, long strings)
- Both languages (toggle PL/EN via the header links)
- Authenticated vs unauthenticated views
- Mobile responsiveness (resize the browser pane)

## Step 6: Lint and format

```bash
python -m ruff check . --fix
python -m ruff format .
```

Both must pass with zero errors before committing. CI will reject the PR otherwise.

## Step 7: Commit and push

```bash
git add <changed-files>
git commit -m "<message>"
git push -u origin feature/<short-slug>
```

Commit message conventions (from git log):
- Start with a verb: "Add", "Fix", "Rewrite", "Wire", "Update"
- One-line summary of what changed and why
- No issue numbers (this project does not use them)

Stage specific files, not `git add .` or `git add -A`.

## Step 8: Create a PR

```bash
gh pr create --title "<short title>" --body "$(cat <<'EOF'
## Summary
- <what changed>
- <why>

## Test plan
- [ ] Unit tests pass (`pytest tests/ -v`)
- [ ] Lint passes (`ruff check . && ruff format --check .`)
- [ ] Manual verification in browser
- [ ] Both PL and EN translations added
EOF
)"
```

PR title: under 70 characters, starts with a verb.

## Step 9: Verify CI checks

After pushing, wait for GitHub Actions to run:

```bash
gh run list --branch feature/<short-slug> --limit 4 --json name,status,conclusion
```

Both `Lint` and `Tests` must show `conclusion: success`. If either fails:

1. Check the failure: `gh run view <run-id> --log-failed`
2. Fix locally
3. Commit and push again
4. Re-check CI

## Checklist

Before marking the feature as done, verify all of these:

- [ ] Feature branch created from latest main
- [ ] Feature implemented following project patterns
- [ ] All user-facing strings in both PL and EN in `app/i18n.py`
- [ ] Tests written and passing (175+ existing tests still green)
- [ ] `ruff check .` and `ruff format .` pass
- [ ] Manual verification: feature works in browser (screenshot taken)
- [ ] DB migration added if new columns on existing tables
- [ ] Changes committed with descriptive message
- [ ] PR created with summary and test plan
- [ ] GitHub Actions (Lint + Tests) both green on the PR

## Gotchas

- **`patch()` target for config**: When testing code that imports from `app.config` at call time (like `Competition.betting_open`), patch `"app.config.VARIABLE"`, not `"app.models.VARIABLE"`.
- **SQLite ALTER TABLE is limited**: You can only ADD columns, not drop or rename. No `NOT NULL` without a default.
- **Template i18n**: Missing translation keys silently return the key string. Always add both PL and EN entries.
- **The `ruff.toml` ignores E501**: Long lines are allowed, but keep them readable. Line length limit is 120.
- **Static files in dev vs prod**: FastAPI serves `/static` in dev. In production, nginx does. The deploy skill handles syncing.
- **Test DB is in-memory**: Each test function gets a fresh database via fixtures. No cleanup needed, but no data persists between tests.
- **`conftest.py` default competition date is 7 days from now**: `make_competition()` defaults to a future date so `betting_open` returns True. Override `comp_date` for time-sensitive tests.
