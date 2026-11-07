#!/usr/bin/env bash
# Smoke test for Typer — starts the dev server, hits key endpoints, reports pass/fail.
# Usage: bash .claude/skills/run-typer/smoke.sh
# Requires: Python venv with deps installed (see SKILL.md).
set -euo pipefail

PORT="${PORT:-8000}"
BASE="http://localhost:$PORT"
PYTHON="${PYTHON:-python}"
PASS=0
FAIL=0
SERVER_PID=""

cleanup() {
  if [ -n "$SERVER_PID" ]; then
    kill "$SERVER_PID" 2>/dev/null || true
    wait "$SERVER_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT

echo "=== Starting dev server on port $PORT ==="
$PYTHON run.py &>"$TMPDIR/typer-smoke.log" &
SERVER_PID=$!

for i in $(seq 1 30); do
  if curl -sf "$BASE/health" >/dev/null 2>&1; then
    echo "Server ready after ${i}s"
    break
  fi
  sleep 1
done

if ! curl -sf "$BASE/health" >/dev/null 2>&1; then
  echo "FAIL: Server did not start. Logs:"
  cat "$TMPDIR/typer-smoke.log"
  exit 1
fi

check() {
  local desc="$1" url="$2" expect="$3"
  body=$(curl -sf -b "lang=en" "$url" 2>/dev/null || true)
  if echo "$body" | grep -qi "$expect"; then
    echo "  PASS: $desc"
    PASS=$((PASS + 1))
  else
    echo "  FAIL: $desc (expected '$expect')"
    FAIL=$((FAIL + 1))
  fi
}

check_status() {
  local desc="$1" url="$2" expected_status="$3"
  status=$(curl -s -o /dev/null -w '%{http_code}' -b "lang=en" "$url" 2>/dev/null || echo "000")
  if [ "$status" = "$expected_status" ]; then
    echo "  PASS: $desc (HTTP $status)"
    PASS=$((PASS + 1))
  else
    echo "  FAIL: $desc (expected $expected_status, got $status)"
    FAIL=$((FAIL + 1))
  fi
}

echo ""
echo "=== Health ==="
check "health endpoint" "$BASE/health" '"status":"ok"'

echo ""
echo "=== Public pages ==="
check "homepage renders" "$BASE/" "Typer"
check "homepage has hero" "$BASE/" "Prediction Market"
check "competitions page" "$BASE/competitions" "Competitions"
check "login page" "$BASE/auth/login" "Login"
check "register page" "$BASE/auth/register" "Register"
check "ranking page" "$BASE/ranking" "Ranking"

echo ""
echo "=== Language toggle ==="
body_pl=$(curl -sf -b "lang=pl" "$BASE/" 2>/dev/null || true)
if echo "$body_pl" | grep -qi "Rynek Prognostyczny"; then
  echo "  PASS: Polish homepage"
  PASS=$((PASS + 1))
else
  echo "  FAIL: Polish homepage (expected 'Rynek Prognostyczny')"
  FAIL=$((FAIL + 1))
fi

echo ""
echo "=== Auth flow ==="
REG_RESP=$(curl -s -o /dev/null -w '%{http_code}' -X POST "$BASE/auth/register" \
  -d "username=smoketest&password=test1234&password_confirm=test1234" 2>/dev/null || echo "000")
if [ "$REG_RESP" = "303" ] || [ "$REG_RESP" = "200" ]; then
  echo "  PASS: register POST accepted (HTTP $REG_RESP)"
  PASS=$((PASS + 1))
else
  echo "  FAIL: register POST (expected 303/200, got $REG_RESP)"
  FAIL=$((FAIL + 1))
fi

LOGIN_RESP=$(curl -s -c - -X POST "$BASE/auth/login" \
  -d "username=smoketest&password=test1234" 2>/dev/null)
if echo "$LOGIN_RESP" | grep -q "session"; then
  echo "  PASS: login sets session cookie"
  PASS=$((PASS + 1))
else
  echo "  FAIL: login did not set session cookie"
  FAIL=$((FAIL + 1))
fi

echo ""
echo "=== API endpoints ==="
check_status "autocomplete needs query" "$BASE/bets/athletes?q=K" 200
check_status "404 for missing page" "$BASE/nonexistent" 404

echo ""
echo "=== Results: $PASS passed, $FAIL failed ==="
if [ "$FAIL" -gt 0 ]; then
  exit 1
fi
