#!/usr/bin/env bash
set -Eeuo pipefail

cd "$(dirname "$0")"

if [ $# -lt 1 ]; then
  echo "Usage: ./link_safe_commit.sh \"commit message\""
  exit 2
fi

MESSAGE="$*"

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "ERROR: not inside a git repo"
  exit 2
fi

CHANGES="$(git status --porcelain --untracked-files=all)"

if [ -z "$CHANGES" ]; then
  echo "No changes to commit."
  exit 1
fi

BLOCKED_PATHS="$(printf '%s\n' "$CHANGES" | awk '{print $2}' | grep -E '^(\.agents/|research/|venv/|\.venv/|__pycache__/|\.pytest_cache/|\.mypy_cache/|\.ruff_cache/)' || true)"

if [ -n "$BLOCKED_PATHS" ]; then
  echo "ERROR: refusing to commit generated/research/local paths:"
  printf '%s\n' "$BLOCKED_PATHS"
  exit 1
fi

echo "Running Link healthcheck..."
python3 link_healthcheck.py

echo "Running compile/import checks..."
python3 -m py_compile *.py
python3 - <<'PY'
import standalone_orchestrator
import modern_command_guard
print("imports OK")
PY

echo "Healthcheck passed. Committing..."
git add -A
git commit -m "$MESSAGE"

git tag -f safe-link-latest

echo
echo "Committed safely:"
git log --oneline --decorate -1
echo
echo "safe-link-latest ->"
git rev-parse --short safe-link-latest
