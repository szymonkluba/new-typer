---
name: deploy-typer
description: Deploy Typer to production (skijtyper.pl). Use when asked to deploy, ship, release, check CI, verify production, or push changes to the OCI VM.
---

Typer deploys to an OCI VM at skijtyper.pl. Drive the full deploy pipeline via `.claude/skills/deploy-typer/deploy.sh` — it handles pre-flight checks, deployment, and post-deploy verification in one script.

All paths below are relative to the repo root.

## Prerequisites

- `gh` CLI authenticated (for CI status and PR checks)
- SSH key for the OCI VM (path configured via SSH_KEY_PATH env var)
- `curl` for production endpoint verification

## Infrastructure

| Component | Value |
|---|---|
| VM IP | `144.24.161.5` |
| SSH user | `opc` |
| App directory on VM | `/home/opc/typer` |
| Domain | `skijtyper.pl` |
| Container name | `typer-app` |
| DB path in container | `/data/typer.db` |
| Static files (nginx) | `/var/www/typer/static/` |
| SELinux context | `httpd_sys_content_t` |

## Deploy (agent path)

### Full deploy

```bash
bash .claude/skills/deploy-typer/deploy.sh
```

The script runs three phases:

**Phase 1 — Pre-flight:**
- Checks GitHub Actions (Lint + Tests) passed on HEAD
- Checks no open PRs remain
- Checks local main matches origin/main

**Phase 2 — Deploy:**
- SSH to VM, `git pull`
- `docker compose up -d --build`
- Syncs static files if CSS/JS changed (with SELinux context restore)
- Waits for container health check

**Phase 3 — Post-deploy verification:**
- Health endpoint returns `{"status":"ok"}`
- All public pages render (homepage, competitions, login, register, ranking)
- i18n works (Polish and English)
- API endpoints respond (autocomplete, static CSS)
- Deployed commit matches local HEAD
- No errors in container logs

Exit code 0 = all checks pass. Non-zero = something failed.

### Pre-flight only (dry run)

```bash
bash .claude/skills/deploy-typer/deploy.sh --dry-run
```

Runs Phase 1 only — checks CI, PRs, and local/remote sync without touching the VM.

### Skip pre-flight

```bash
bash .claude/skills/deploy-typer/deploy.sh --skip-preflight
```

Jumps straight to deploy + verify. Use when you have already confirmed CI is green.

### Environment overrides

| Variable | Default | Notes |
|---|---|---|
| `SSH_KEY_PATH` | `D:\oci\typer-private.key` | Path to OCI VM SSH key |
| `VM_HOST` | `144.24.161.5` | VM IP address |
| `VM_USER` | `opc` | SSH user |
| `APP_DIR` | `/home/opc/typer` | App directory on VM |
| `PROD_URL` | `https://skijtyper.pl` | Production URL for verification |

## Deploy (manual steps)

When the script cannot run (e.g., auto-mode classifier blocks SSH), do it step by step:

1. Check CI: `gh run list --branch main --limit 4 --json name,status,conclusion,headSha`
2. Check open PRs: `gh pr list --state open`
3. SSH and pull on the VM
4. Rebuild container with `docker compose up -d --build`
5. Sync static files if CSS/JS changed (copy to `/var/www/typer/static/` and `restorecon`)
6. Verify health: `curl -sf https://skijtyper.pl/health`

## DB migrations

SQLite has no migration tool. When `app/models.py` adds a new column:

1. Check if `app/database.py` has auto-migration code (see `_migrate_db()`) — if so, the container handles it on startup.
2. If not, run ALTER TABLE manually inside the container.
3. For new tables: `create_tables()` in `database.py` handles them automatically via `Base.metadata.create_all()`.

## Triggering scrapers

After deploy, if you need data immediately rather than waiting for the cron schedule, run inside the container:

- Competitions: `from app.scraper.fis import sync_competitions_from_fis; sync_competitions_from_fis()`
- Athletes: `from app.scraper.fis import sync_athletes_from_fis; sync_athletes_from_fis()`
- Results: `from app.scraper.fis import sync_results_from_fis; sync_results_from_fis()`

Wrap with: `docker exec typer-app python -c '<import and call>'`

## Gotchas

- **Auto-mode classifier may block SSH commands.** The deploy script runs SSH to the VM, which production-safety classifiers can block. If blocked, use the manual steps above or ask the user to approve.
- **Static files are served by nginx, not FastAPI in production.** CSS/JS changes won't appear until synced to `/var/www/typer/static/`. The deploy script detects this automatically from `git pull` output.
- **SELinux on Oracle Linux 9.** After copying static files, `restorecon` is required or nginx gets permission denied. The script handles this.
- **Container health check takes ~15s.** The docker-compose healthcheck has `start_period: 15s`, so don't panic if the container shows "starting" for a bit.
- **The SSH key warning about post-quantum algorithms is harmless.** It's just OpenSSH noting the key exchange isn't PQ-safe — the connection works fine.

## Troubleshooting

- **`docker compose up -d --build` hangs**: The Playwright chromium install in the Dockerfile can be slow on the aarch64 VM. Allow up to 5 minutes for the build. If cached, it takes ~10s.
- **`sqlite3.OperationalError: no such column`**: A model change added a column but no auto-migration exists. Run ALTER TABLE manually (see DB migrations above).
- **`Permission denied` on static files after deploy**: SELinux context not restored. Run `sudo restorecon -Rv /var/www/typer/static/`.
- **Container exits immediately**: Check logs with `docker logs typer-app`. Common cause: syntax error in new code, or missing import.
