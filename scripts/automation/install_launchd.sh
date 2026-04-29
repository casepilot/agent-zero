#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
LAUNCHD_SOURCE="$REPO_ROOT/scripts/launchd"
LAUNCHD_TARGET="$HOME/Library/LaunchAgents"
AUTOMATION_ROOT="${AGENT_ZERO_AUTOMATION_DIR:-$REPO_ROOT/.codex-automation}"

mkdir -p "$LAUNCHD_TARGET" "$AUTOMATION_ROOT/logs" "$AUTOMATION_ROOT/locks"

install_agent() {
  local label="$1"
  local source="$LAUNCHD_SOURCE/$label.plist"
  local target="$LAUNCHD_TARGET/$label.plist"

  if launchctl print "gui/$UID/$label" >/dev/null 2>&1; then
    launchctl bootout "gui/$UID/$label" >/dev/null 2>&1 || true
    launchctl bootout "gui/$UID" "$target" >/dev/null 2>&1 || true
  fi

  cp "$source" "$target"
  launchctl bootstrap "gui/$UID" "$target"
  launchctl enable "gui/$UID/$label"
  echo "installed $label"
}

install_agent "com.agent-zero.git-sync"

echo "launch agents installed"
echo "logs: $AUTOMATION_ROOT/logs"
