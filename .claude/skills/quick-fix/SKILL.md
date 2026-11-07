---
name: quick-fix
description: Apply a small code fix to Typer. Use when asked to fix a bug, correct a typo, adjust a translation, tweak styling, or make a small targeted change that does not need a full feature branch workflow.
---

Lightweight workflow for small, targeted fixes in the Typer ski jumping betting app. For larger changes that need a feature branch and PR, use `/implement-feature` instead.

Drive verification via `.claude/skills/quick-fix/verify.sh` — it runs lint + tests and reports pass/fail. All paths below are relative to the repo root.

## When to use this vs /implement-feature

Use **quick-fix** for:
- Bug fixes in a single file
- Translation fixes in `app/i18n.py`
- CSS tweaks in `app/static/css/style.css`
- Config changes in `app/config.py`
- Template fixes in `app/templates/`
- Test fixes or additions

Use **implement-feature** when the change spans multiple modules, adds a new route or model, or needs a PR review.

## Step 1: Understand the fix

Read the relevant file(s). Key locations:

| What | Where |
|---|---|
| Routes | `app/auth/router.py`, `app/bets/router.py`, `app/competitions/router.py`, `app/ranking/router.py` |
| Models | `app/models.py` |
| Templates | `app/templates/<module>/` |
| Translations | `app/i18n.py` — both `pl` and `en` dicts |
| Styles | `app/static/css/style.css` |
| Config | `app/config.py` |
| Scoring | `app/bets/scoring.py` |
| Scraper | `app/scraper/fis.py` |
| DB migrations | `app/database.py` `_migrate_db()` |

## Step 2: Make the fix

Apply the change. Keep it minimal — touch only what's broken.

If fixing a translation, update **both** `pl` and `en` dicts in `app/i18n.py`.

If adding a column to an existing table, add auto-migration in `app/database.py`:

```python
def _migrate_db():
    inspector = sa_inspect(engine)
    if "<table>" in inspector.get_table_names():
        columns = [col["name"] for col in inspector.get_columns("<table>")]
        if "<new_col>" not in columns:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE <table> ADD COLUMN <new_col> <TYPE>"))
```

## Step 3: Verify

Run the verification driver:

```bash
PYTHON=venv/Scripts/python.exe bash .claude/skills/quick-fix/verify.sh
```

On Linux/macOS:
```bash
PYTHON=venv/bin/python bash .claude/skills/quick-fix/verify.sh
```

### Flags

| Flag | What it does |
|---|---|
| `--fix` | Auto-fix lint/format issues before checking |
| `--lint-only` | Skip tests, only check lint + format |
| `--test-only` | Skip lint, only run tests |

Exit 0 = all green. Non-zero = something failed.

If lint fails, run with `--fix` to auto-correct:

```bash
PYTHON=venv/Scripts/python.exe bash .claude/skills/quick-fix/verify.sh --fix
```

### Visual verification

For UI-visible changes (templates, CSS), also start the dev server:

```
preview_start with name "typer-dev"
```

Check the affected pages and take a screenshot. Test both PL and EN via the language toggle.

## Step 4: Commit

```bash
git add <changed-files>
git commit -m "<verb>: <what and why>"
```

Commit message starts with a verb: "Fix", "Correct", "Update", "Adjust". One-line summary. Stage specific files, not `git add .`.

## Gotchas

- **`patch()` target for config**: When testing code that reads from `app.config` at call time (like `Competition.betting_open`), patch `"app.config.VARIABLE"`, not `"app.models.VARIABLE"`.
- **SQLite ALTER TABLE is limited**: You can only ADD columns, not drop or rename. No `NOT NULL` without a default.
- **Missing translation keys silently return the key string**: Always check both PL and EN dicts after editing `app/i18n.py`.
- **The stray file `app/main (# Name clash ...).py`**: This untracked file triggers a ruff lint error. Ignore it — it's not part of the project.
- **Ruff config ignores E501**: Long lines are allowed (line-length 120 in `ruff.toml`), but keep them readable.
- **Test DB is in-memory**: Each test gets a fresh database. `make_competition()` defaults to 7 days from now so `betting_open` returns True.
