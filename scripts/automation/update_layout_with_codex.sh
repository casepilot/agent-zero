#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
AUTOMATION_ROOT="${AGENT_ZERO_AUTOMATION_DIR:-$REPO_ROOT/.codex-automation}"
LOG_DIR="$AUTOMATION_ROOT/logs"
LOCK_DIR="$AUTOMATION_ROOT/locks"
LOCK_PATH="$LOCK_DIR/layout-refresh.lock"
CODEX_BIN="${CODEX_BIN:-/Users/deepak/.nvm/versions/node/v20.19.5/bin/codex}"

export PATH="/Users/deepak/.nvm/versions/node/v20.19.5/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"

mkdir -p "$LOG_DIR" "$LOCK_DIR"

if ! mkdir "$LOCK_PATH" 2>/dev/null; then
  echo "$(date '+%Y-%m-%d %H:%M:%S %z') layout refresh already running"
  exit 0
fi

cleanup() {
  rmdir "$LOCK_PATH" 2>/dev/null || true
}
trap cleanup EXIT

cd "$REPO_ROOT"

echo "$(date '+%Y-%m-%d %H:%M:%S %z') starting layout refresh"

"$CODEX_BIN" exec \
  --cd "$REPO_ROOT" \
  --sandbox workspace-write \
  --output-last-message "$LOG_DIR/layout-last-message.txt" \
  - <<'PROMPT'
You are maintaining /Users/deepak/hackathon/agent-zero.

Use simple language.

Task:
Update docs/layout.md so it reflects the current codebase layout.

Rules:
- Before editing, read docs/project.md, docs/layout.md, and docs/to_do.md.
- Inspect the current folders and files.
- Edit docs/layout.md only.
- Keep the document useful for future contributors.
- Separate current layout from planned or missing folders if needed.
- Do not stage, commit, pull, push, or edit any other file.
PROMPT

echo "$(date '+%Y-%m-%d %H:%M:%S %z') finished layout refresh"
