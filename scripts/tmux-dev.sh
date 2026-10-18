#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "\${BASH_SOURCE[0]}")/.." && pwd)"
SESSION="teddy-dev"

if ! command -v tmux >/dev/null 2>&1; then
  echo "tmux is not installed."
  echo "In Ubuntu/Debian Codespaces, install it with:"
  echo "  sudo apt-get update && sudo apt-get install -y tmux"
  exit 1
fi

if [[ ! -x "$ROOT/.venv/bin/python" ]]; then
  echo "TEDDY's .venv was not found at $ROOT/.venv."
  echo "Create it first:"
  echo "  cd \"$ROOT\""
  echo "  python -m venv .venv"
  echo "  source .venv/bin/activate"
  echo "  python -m pip install -r requirements.txt"
  exit 1
fi

if tmux has-session -t "$SESSION" 2>/dev/null; then
  echo "Attaching to existing tmux session: $SESSION"
  exec tmux attach-session -t "$SESSION"
fi

tmux new-session -d -s "$SESSION" -n api -c "$ROOT" \
  "source .venv/bin/activate && python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload"

tmux new-window -t "$SESSION" -n shell -c "$ROOT"
tmux select-window -t "$SESSION:api"

echo "TEDDY dev session created."
echo "Detach without stopping programs: Ctrl+b, then d"
echo "Reattach later: tmux attach -t $SESSION"
echo "Stop the development session: tmux kill-session -t $SESSION"
echo
echo "Note: tmux survives a disconnected terminal, not a stopped/rebuilt Codespace."
exec tmux attach-session -t "$SESSION"
