#!/bin/zsh
set -euo pipefail

export PATH="/Users/pablo/.pyenv/shims:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PYTHON_BIN="/Users/pablo/.pyenv/shims/python"
LOCK_FILE="/tmp/fight_predictor_agent.lockfile"

if [ "${FIGHT_AGENT_LOCKED:-0}" != "1" ]; then
  set +e
  /usr/bin/lockf -s -t 0 -k "$LOCK_FILE" /usr/bin/env FIGHT_AGENT_LOCKED=1 "$0" "$@"
  lock_status=$?
  set -e
  if [ "$lock_status" -eq 75 ]; then
    echo "INFO: another poll_mentions.py run is still active; skipping this cron tick"
    exit 0
  fi
  exit "$lock_status"
fi

cd "$SCRIPT_DIR"
mkdir -p logs responses

if [ ! -x "$PYTHON_BIN" ]; then
  echo "ERROR: pyenv Python shim not found or not executable: $PYTHON_BIN"
  echo "Run: pyenv install -s 3.12.10 && cd /Users/pablo/Code/the-fight-predictor-agent && pyenv local 3.12.10 && python -m pip install -r PRODUCTION-FINAL/requirements.txt"
  exit 1
fi

exec "$PYTHON_BIN" -u poll_mentions.py "$@"
