#!/usr/bin/env bash
# Verify a code change: lint + format + test suite.
# Usage: bash .claude/skills/quick-fix/verify.sh [--lint-only] [--test-only] [--fix]
# Exit 0 = all green. Non-zero = something failed.
set -euo pipefail

PYTHON="${PYTHON:-python}"
LINT_ONLY=""
TEST_ONLY=""
AUTO_FIX=""

for arg in "$@"; do
  case "$arg" in
    --lint-only) LINT_ONLY="yes" ;;
    --test-only) TEST_ONLY="yes" ;;
    --fix) AUTO_FIX="yes" ;;
  esac
done

PASS=0
FAIL=0

pass() { echo "  PASS: $1"; PASS=$((PASS + 1)); }
fail() { echo "  FAIL: $1"; FAIL=$((FAIL + 1)); }

# ── Lint ────────────────────────────────────────────────────────────

if [ "$TEST_ONLY" != "yes" ]; then
  echo ""
  echo "=== Lint & Format ==="

  if [ "$AUTO_FIX" = "yes" ]; then
    echo "--- Auto-fixing with ruff ---"
    $PYTHON -m ruff check . --fix 2>&1 || true
    $PYTHON -m ruff format . 2>&1 || true
    echo "  Applied auto-fixes"
  fi

  echo "--- ruff check ---"
  if $PYTHON -m ruff check . 2>&1; then
    pass "ruff check"
  else
    fail "ruff check (run with --fix to auto-correct)"
  fi

  echo "--- ruff format --check ---"
  if $PYTHON -m ruff format --check . 2>&1; then
    pass "ruff format"
  else
    fail "ruff format (run with --fix to auto-correct)"
  fi
fi

# ── Tests ───────────────────────────────────────────────────────────

if [ "$LINT_ONLY" != "yes" ]; then
  echo ""
  echo "=== Tests ==="

  echo "--- pytest ---"
  if $PYTHON -m pytest tests/ -v --tb=short 2>&1; then
    pass "pytest"
  else
    fail "pytest"
  fi
fi

# ── Summary ─────────────────────────────────────────────────────────

echo ""
echo "========================================"
echo "=== Verify: $PASS passed, $FAIL failed ==="
echo "========================================"
if [ "$FAIL" -gt 0 ]; then
  exit 1
fi
