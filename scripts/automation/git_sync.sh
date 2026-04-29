#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
AUTOMATION_ROOT="${AGENT_ZERO_AUTOMATION_DIR:-$REPO_ROOT/.codex-automation}"
LOG_DIR="$AUTOMATION_ROOT/logs"
LOCK_DIR="$AUTOMATION_ROOT/locks"
LOCK_PATH="$LOCK_DIR/git-sync.lock"

mkdir -p "$LOG_DIR" "$LOCK_DIR"

if ! mkdir "$LOCK_PATH" 2>/dev/null; then
  echo "$(date '+%Y-%m-%d %H:%M:%S %z') git sync already running"
  exit 0
fi

cleanup() {
  rmdir "$LOCK_PATH" 2>/dev/null || true
}
trap cleanup EXIT

cd "$REPO_ROOT"

echo "$(date '+%Y-%m-%d %H:%M:%S %z') starting git sync"

current_branch="$(git branch --show-current)"
if [[ "$current_branch" != "main" ]]; then
  echo "current branch is $current_branch, not main; skipping git sync"
  exit 0
fi

git add -A

if ! git diff --cached --quiet; then
  git commit -m "chore: automated checkpoint $(date '+%Y-%m-%d %H:%M:%S %z')"
else
  echo "nothing to commit"
fi

if git rev-parse --abbrev-ref --symbolic-full-name '@{u}' >/dev/null 2>&1; then
  git pull --no-rebase --autostash
else
  echo "no upstream configured for $(git rev-parse --abbrev-ref HEAD); skipping pull"
fi

echo "$(date '+%Y-%m-%d %H:%M:%S %z') finished git sync"
