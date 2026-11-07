#!/usr/bin/env bash
# Deploy Typer to OCI VM (skijtyper.pl).
# Usage: bash .claude/skills/deploy-typer/deploy.sh [--skip-preflight] [--dry-run]
#
# Requires:
#   - gh CLI authenticated
#   - SSH key at SSH_KEY_PATH (default: D:\oci\typer-private.key)
#   - OCI VM accessible at VM_HOST (default: 144.24.161.5)
set -euo pipefail

SSH_KEY_PATH="${SSH_KEY_PATH:-D:\\oci\\typer-private.key}"
VM_HOST="${VM_HOST:-144.24.161.5}"
VM_USER="${VM_USER:-opc}"
APP_DIR="${APP_DIR:-/home/opc/typer}"
PROD_URL="${PROD_URL:-https://skijtyper.pl}"
SKIP_PREFLIGHT="${1:-}"
DRY_RUN=""

for arg in "$@"; do
  case "$arg" in
    --skip-preflight) SKIP_PREFLIGHT="yes" ;;
    --dry-run) DRY_RUN="yes" ;;
  esac
done

PASS=0
FAIL=0
WARN=0

pass() { echo "  PASS: $1"; PASS=$((PASS + 1)); }
fail() { echo "  FAIL: $1"; FAIL=$((FAIL + 1)); }
warn() { echo "  WARN: $1"; WARN=$((WARN + 1)); }

ssh_cmd() {
  ssh -i "$SSH_KEY_PATH" -o StrictHostKeyChecking=no -o LogLevel=ERROR "$VM_USER@$VM_HOST" "$@"
}

# ── Phase 1: Pre-flight checks ──────────────────────────────────────

if [ "$SKIP_PREFLIGHT" != "yes" ]; then
  echo ""
  echo "=== Phase 1: Pre-flight checks ==="

  # 1a. GitHub Actions on main
  echo ""
  echo "--- CI status on main ---"
  HEAD_SHA=$(git rev-parse HEAD)
  CI_JSON=$(gh run list --branch main --limit 10 --json name,status,conclusion,headSha 2>/dev/null || echo "[]")

  LINT_OK=""
  TEST_OK=""
  while IFS= read -r line; do
    name=$(echo "$line" | sed 's/.*"name":"\([^"]*\)".*/\1/')
    sha=$(echo "$line" | sed 's/.*"headSha":"\([^"]*\)".*/\1/')
    conclusion=$(echo "$line" | sed 's/.*"conclusion":"\([^"]*\)".*/\1/')
    status=$(echo "$line" | sed 's/.*"status":"\([^"]*\)".*/\1/')

    if [ "$sha" = "$HEAD_SHA" ]; then
      if echo "$name" | grep -qi "lint"; then
        if [ "$conclusion" = "success" ]; then
          pass "Lint passed on HEAD ($HEAD_SHA)"
          LINT_OK="yes"
        elif [ "$status" = "in_progress" ] || [ "$status" = "queued" ]; then
          warn "Lint still running on HEAD"
        else
          fail "Lint failed on HEAD (conclusion: $conclusion)"
        fi
      fi
      if echo "$name" | grep -qi "test"; then
        if [ "$conclusion" = "success" ]; then
          pass "Tests passed on HEAD ($HEAD_SHA)"
          TEST_OK="yes"
        elif [ "$status" = "in_progress" ] || [ "$status" = "queued" ]; then
          warn "Tests still running on HEAD"
        else
          fail "Tests failed on HEAD (conclusion: $conclusion)"
        fi
      fi
    fi
  done < <(echo "$CI_JSON" | grep -o '{[^}]*}')

  [ -z "$LINT_OK" ] && warn "No Lint run found for HEAD — may still be queued"
  [ -z "$TEST_OK" ] && warn "No Tests run found for HEAD — may still be queued"

  # 1b. Open PRs
  echo ""
  echo "--- Open PRs ---"
  OPEN_PRS=$(gh pr list --state open --json number,title,headRefName 2>/dev/null || echo "[]")
  if [ "$OPEN_PRS" = "[]" ]; then
    pass "No open PRs"
  else
    PR_COUNT=$(echo "$OPEN_PRS" | grep -o '"number"' | wc -l)
    warn "$PR_COUNT open PR(s) — review before deploying:"
    echo "$OPEN_PRS" | grep -o '"title":"[^"]*"' | sed 's/"title":"//;s/"//' | while read -r title; do
      echo "    - $title"
    done
  fi

  # 1c. Local vs remote sync
  echo ""
  echo "--- Local/remote sync ---"
  git fetch origin main --quiet 2>/dev/null || true
  LOCAL_SHA=$(git rev-parse HEAD)
  REMOTE_SHA=$(git rev-parse origin/main 2>/dev/null || echo "unknown")
  if [ "$LOCAL_SHA" = "$REMOTE_SHA" ]; then
    pass "Local main matches origin/main ($LOCAL_SHA)"
  else
    fail "Local ($LOCAL_SHA) differs from origin/main ($REMOTE_SHA) — push first"
  fi

  if [ "$FAIL" -gt 0 ]; then
    echo ""
    echo "=== Pre-flight FAILED: $FAIL issue(s). Fix before deploying. ==="
    exit 1
  fi
fi

if [ -n "$DRY_RUN" ]; then
  echo ""
  echo "=== Dry run — skipping deploy ==="
  echo "=== Pre-flight: $PASS passed, $WARN warning(s) ==="
  exit 0
fi

# ── Phase 2: Deploy ──────────────────────────────────────────────────

echo ""
echo "=== Phase 2: Deploy ==="

# 2a. Git pull on VM
echo ""
echo "--- Pulling latest on VM ---"
PULL_OUTPUT=$(ssh_cmd "cd $APP_DIR && git pull" 2>&1)
echo "$PULL_OUTPUT" | grep -v "WARNING.*post-quantum"
if echo "$PULL_OUTPUT" | grep -q "Already up to date"; then
  warn "VM already up to date — nothing to deploy"
else
  pass "Pulled latest commits"
fi

# 2b. Check what changed for static files
NEEDS_STATIC=""
if echo "$PULL_OUTPUT" | grep -q "app/static/"; then
  NEEDS_STATIC="yes"
  echo "  Static files changed — will sync"
fi

# 2c. Rebuild container
echo ""
echo "--- Rebuilding container ---"
BUILD_OUTPUT=$(ssh_cmd "cd $APP_DIR && docker compose up -d --build" 2>&1)
if echo "$BUILD_OUTPUT" | grep -q "Started\|Running"; then
  pass "Container rebuilt and started"
else
  echo "$BUILD_OUTPUT" | grep -v "WARNING.*post-quantum"
  fail "Container rebuild may have failed"
fi

# 2d. Sync static files if needed
if [ -n "$NEEDS_STATIC" ]; then
  echo ""
  echo "--- Syncing static files ---"
  ssh_cmd "sudo cp -r $APP_DIR/app/static/* /var/www/typer/static/ && sudo restorecon -Rv /var/www/typer/static/" 2>&1 | grep -v "WARNING.*post-quantum"
  pass "Static files synced with SELinux context"
fi

# Wait for container to be healthy
echo ""
echo "--- Waiting for container health ---"
for i in $(seq 1 30); do
  HEALTH=$(ssh_cmd "docker inspect --format='{{.State.Health.Status}}' typer-app" 2>/dev/null | grep -v "WARNING" || echo "unknown")
  if [ "$HEALTH" = "healthy" ]; then
    pass "Container healthy after ${i}s"
    break
  fi
  sleep 1
done
if [ "$HEALTH" != "healthy" ]; then
  fail "Container not healthy after 30s (status: $HEALTH)"
fi

# ── Phase 3: Post-deploy verification ────────────────────────────────

echo ""
echo "=== Phase 3: Post-deploy verification ==="

check_prod() {
  local desc="$1" path="$2" expect="$3"
  body=$(curl -sf -b "lang=en" "${PROD_URL}${path}" 2>/dev/null || true)
  if echo "$body" | grep -qi "$expect"; then
    pass "$desc"
  else
    fail "$desc (expected '$expect')"
  fi
}

check_status() {
  local desc="$1" path="$2" expected="$3"
  status=$(curl -s -o /dev/null -w '%{http_code}' "${PROD_URL}${path}" 2>/dev/null || echo "000")
  if [ "$status" = "$expected" ]; then
    pass "$desc (HTTP $status)"
  else
    fail "$desc (expected $expected, got $status)"
  fi
}

# 3a. Health
echo ""
echo "--- Health ---"
check_prod "health endpoint" "/health" '"status":"ok"'

# 3b. Public pages
echo ""
echo "--- Public pages ---"
check_prod "homepage" "/" "Typer"
check_prod "competitions page" "/competitions" "ompetition"
check_prod "login page" "/auth/login" "ogin"
check_prod "register page" "/auth/register" "egist"
check_prod "ranking page" "/ranking" "anking"

# 3c. Language toggle
echo ""
echo "--- i18n ---"
check_prod "English homepage" "/" "Prediction Market"
body_pl=$(curl -sf -b "lang=pl" "${PROD_URL}/" 2>/dev/null || true)
if echo "$body_pl" | grep -qi "Rynek Prognostyczny"; then
  pass "Polish homepage"
else
  fail "Polish homepage (expected 'Rynek Prognostyczny')"
fi

# 3d. API endpoints
echo ""
echo "--- API ---"
check_status "autocomplete endpoint" "/bets/athletes?q=Kr" 200
check_status "static CSS" "/static/css/style.css" 200

# 3e. Deployed commit matches
echo ""
echo "--- Deployed version ---"
DEPLOYED_SHA=$(ssh_cmd "cd $APP_DIR && git rev-parse --short HEAD" 2>/dev/null | grep -v "WARNING" || echo "unknown")
EXPECTED_SHA=$(git rev-parse --short HEAD)
if [ "$DEPLOYED_SHA" = "$EXPECTED_SHA" ]; then
  pass "Deployed commit matches local HEAD ($DEPLOYED_SHA)"
else
  fail "Deployed commit ($DEPLOYED_SHA) != local HEAD ($EXPECTED_SHA)"
fi

# 3f. Container logs — check for errors
echo ""
echo "--- Container logs (last 20 lines) ---"
LOGS=$(ssh_cmd "docker logs typer-app --tail 20" 2>&1 | grep -v "WARNING.*post-quantum")
ERROR_COUNT=$(echo "$LOGS" | grep -ci "error\|traceback\|exception" || true)
if [ "$ERROR_COUNT" -eq 0 ]; then
  pass "No errors in recent container logs"
else
  warn "$ERROR_COUNT error-like line(s) in recent logs"
  echo "$LOGS" | grep -i "error\|traceback\|exception" | head -5
fi

# ── Summary ──────────────────────────────────────────────────────────

echo ""
echo "========================================"
echo "=== Deploy complete: $PASS passed, $FAIL failed, $WARN warning(s) ==="
echo "========================================"
if [ "$FAIL" -gt 0 ]; then
  exit 1
fi
