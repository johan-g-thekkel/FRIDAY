#!/usr/bin/env bash
# Local development helper. Runs tests before launching the API.
set -euo pipefail
cd "$(dirname "$0")/.."
if command -v tmux >/dev/null 2>&1 && [[ -z "${TMUX:-}" ]]; then
  SESSION="${FRIDAY_TMUX_SESSION:-friday-dev}"
  if tmux has-session -t "$SESSION" 2>/dev/null; then
    echo "tmux session '$SESSION' already exists. Attach with: tmux attach -t $SESSION"
    exit 0
  fi
  tmux new-session -d -s "$SESSION" "cd '$PWD' && python -m pytest -q && python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload"
  echo "Started tmux session '$SESSION'. Attach with: tmux attach -t $SESSION"
  echo "Stop it with: tmux kill-session -t $SESSION"
else
  python -m pytest -q
  exec python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
fi
