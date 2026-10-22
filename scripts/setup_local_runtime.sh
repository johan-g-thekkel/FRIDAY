#!/usr/bin/env bash
set -euo pipefail

MODEL="${FRIDAY_OLLAMA_MODEL:-qwen2.5:1.5b}"
BASE_URL="${OLLAMA_BASE_URL:-http://127.0.0.1:11434}"
LOG_FILE="${TMPDIR:-/tmp}/friday-ollama.log"

if ! command -v ollama >/dev/null 2>&1; then
  echo "Installing Ollama in this runtime..."
  if ! command -v curl >/dev/null 2>&1; then
    echo "curl is required to install Ollama." >&2
    exit 1
  fi
  curl -fsSL https://ollama.com/install.sh | sh
fi

if ! curl -fsS "${BASE_URL%/}/api/tags" >/dev/null 2>&1; then
  echo "Starting Ollama server..."
  nohup ollama serve >"$LOG_FILE" 2>&1 </dev/null &
  ready=0
  for _ in $(seq 1 30); do
    if curl -fsS "${BASE_URL%/}/api/tags" >/dev/null 2>&1; then
      ready=1
      break
    fi
    sleep 1
  done
  if [ "$ready" -ne 1 ]; then
    echo "Ollama did not start. Inspect $LOG_FILE" >&2
    exit 1
  fi
fi

echo "Downloading local model: $MODEL"
ollama pull "$MODEL"

if [ "${1:-}" = "--voice" ]; then
  echo "Installing optional offline Whisper speech recognition..."
  python -m pip install -r requirements-voice.txt
fi

echo
echo "Local model setup finished."
echo "Verify with: ollama list"
echo "Start FRIDAY with: python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload"
echo "Ollama stays in the same runtime. It is not your laptop's Ollama when this script runs in Codespaces."
