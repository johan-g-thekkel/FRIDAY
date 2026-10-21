#!/usr/bin/env bash
set -euo pipefail

MODEL="${FRIDAY_OLLAMA_MODEL:-qwen2.5:3b}"
BASE_URL="${OLLAMA_HOST:-http://127.0.0.1:11434}"

echo "FRIDAY local AI setup"
echo "Model to pull: $MODEL"
echo "Ollama endpoint: $BASE_URL"
echo
if ! command -v ollama >/dev/null 2>&1; then
  echo "Ollama CLI was not found."
  echo "Install Ollama from https://ollama.com/download and reopen your terminal."
  exit 1
fi

if ! curl --silent --show-error --fail "$BASE_URL/api/tags" >/dev/null; then
  echo "Ollama is installed but its local server is not reachable at $BASE_URL."
  echo "Start the Ollama desktop app/service, then rerun this script."
  echo "On Linux, try: ollama serve"
  exit 1
fi

echo "Pulling the selected model. This step needs internet and downloads model files."
echo "After the download finishes, inference can run offline while Ollama and the model remain installed."
ollama pull "$MODEL"

echo
echo "Local model setup complete. Start FRIDAY:"
echo "  python -m pip install -r requirements.txt"
echo "  python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000"
echo
echo "Open http://127.0.0.1:8000/static/local-ai.html"
echo "This script does not install coding agents or enable shell execution."
