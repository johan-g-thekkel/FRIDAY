# FRIDAY — local voice assistant setup

FRIDAY's default page is a voice-first humanoid interface. The microphone is activated only after you click Activate FRIDAY. It records each spoken turn, sends that audio to FRIDAY's backend for local Whisper transcription, routes the text to a real model in Ollama, and speaks the model's answer using the browser/operating-system speech voice. There is no hidden hosted speech-recognition fallback.

## Important: local laptop versus GitHub Codespaces

A Codespace is a remote Linux machine. If you install Ollama in a Codespace, the model runs on that remote machine, not on your Windows laptop. To keep inference on your laptop, download or clone this repository onto Windows, install Ollama on Windows, and run the FRIDAY backend locally.

The API and UI work in both environments. Microphone access requires a secure context; localhost and the HTTPS URL exposed by Codespaces normally qualify in current browsers.

## Option A — run all model inference on your Windows laptop

1. Install Python 3.11 or newer and install [Ollama for Windows](https://ollama.com/download/windows).
2. Open PowerShell in the repository folder.
3. Run these commands:

    python -m venv .venv
    .\.venv\Scripts\Activate.ps1
    python -m pip install --upgrade pip
    python -m pip install -r requirements.txt
    .\scripts\setup_local_runtime.ps1

    The setup script pulls qwen2.5:1.5b by default. You can use another installed model by setting the FRIDAY_OLLAMA_MODEL environment variable before running the script. The 1.5B model is a small starting point for low-memory systems; bigger models can be smarter but need more RAM and run slower.
4. Run the API and UI:

    python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload

5. Open http://127.0.0.1:8000. Allow microphone access and click Activate FRIDAY. The advanced console is at http://127.0.0.1:8000/console.

On Windows, FRIDAY enables a small explicit local action allowlist by default: say “open Calculator”, “open Notepad”, “open File Explorer”, “open Paint”, or “open browser”. It can also open a spoken HTTP/HTTPS URL in your default browser. These commands only work when the backend runs on the laptop; arbitrary shell commands are not enabled. To disable all local app launches, set ENABLE_LOCAL_DESKTOP_ACTIONS=false in the environment before starting FRIDAY.

## Option B — run inside GitHub Codespaces

Open a terminal in the Codespace and run:

    python -m venv .venv
    source .venv/bin/activate
    python -m pip install --upgrade pip
    python -m pip install -r requirements.txt
    bash scripts/setup_local_runtime.sh --voice
    python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload

In the Ports tab, open port 8000. This downloads the model inside the Codespace; it does not use the laptop's local Ollama process. The setup step downloads Ollama's small qwen2.5:1.5b model and installs optional local Whisper transcription. The lightweight tiny Whisper model weights are fetched on first transcription, then cached in that runtime.

If the setup script needs to be rerun after a Codespace restart, repeat the model server setup step if Ollama did not remain running. If the local model is missing, check with ollama list and run ollama pull qwen2.5:1.5b.

## Checks

- Backend: /health
- Local model and offline speech readiness: /api/v1/voice/status
- Installed and configured model routes: /api/v1/models
- Interactive API docs: /docs
- Advanced agent / task console: /console

The voice UI shows whether Ollama and Whisper are ready. Automatic voice chat is local-only: if no Ollama model is installed, FRIDAY explains how to install one and does not silently route your voice to a cloud provider. It does not fake an answer: if the model is missing, offline transcription is not installed, or a selected route fails, it displays the actual failure.

## Add additional local models

Use Ollama to download a model, then refresh FRIDAY:

    ollama pull qwen2.5-coder:1.5b
    ollama pull llama3.2:1b
    ollama list

Only tags actually returned by Ollama are offered as local model routes. Use ollama list to see exact installed tags. Model sizes and capabilities differ; verify the exact model in the [Ollama library](https://ollama.com/library) before downloading it.

## Voice runtime behavior

- Speech recognition: optional faster-whisper, installed from requirements-voice.txt, running locally with CPU int8 inference. The selected Whisper model (tiny by default for memory-constrained machines) downloads on first use if not already cached.
- Speech output: browser/OS speechSynthesis, not ElevenLabs. This works without a hosted TTS key when the browser has an installed system voice.
- Conversation inference: automatic voice mode is strictly local Ollama. If no model is installed, FRIDAY stops with setup instructions instead of hidden cloud fallback. Cloud routes remain optional and must be selected explicitly through the advanced API.
- Skills and agents: the separate operator console retains reviewed skills and guarded Codex coding worktrees. Agent inventories are not proof of a working integration. FRIDAY's local voice actions are deliberately limited to explicit allowlisted app launches and opening a URL. They do not mean arbitrary shell access, unrestricted desktop control, or automatic control of other applications.
- API secrets belong in .env or environment secrets only. Never commit secrets or paste them into chat.
