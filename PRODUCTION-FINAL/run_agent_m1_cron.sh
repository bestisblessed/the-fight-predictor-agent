#!/bin/zsh
set -euo pipefail

export PATH="/Users/pablo/.pyenv/shims:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PYTHON_BIN="$SCRIPT_DIR/.venv/bin/python"
LOCK_DIR="$SCRIPT_DIR/logs/poll_mentions.lock"

cd "$SCRIPT_DIR"
mkdir -p logs responses

if [ ! -x "$PYTHON_BIN" ]; then
  echo "ERROR: Python virtualenv not found or not executable: $PYTHON_BIN"
  echo "Run: cd $SCRIPT_DIR && python3 -m venv .venv && .venv/bin/python -m pip install -r requirements.txt"
  exit 1
fi

if ! mkdir "$LOCK_DIR" 2>/dev/null; then
  echo "INFO: another poll_mentions.py run is still active; skipping this cron tick"
  exit 0
fi
trap 'rm -rf "$LOCK_DIR"' EXIT INT TERM

exec "$PYTHON_BIN" -u poll_mentions.py "$@"
