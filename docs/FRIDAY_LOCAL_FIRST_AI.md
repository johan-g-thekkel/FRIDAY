# FRIDAY Local-First AI and Agent Setup

## What works in this change

- `/static/local-ai.html`: a separate local chat workspace with installed-model discovery, chat history for the current page, connection status and explicit local-only behavior.
- `GET /api/v1/local-ai/status`: probes the loopback Ollama API and returns installed model names/metadata.
- `POST /api/v1/local-ai/chat`: checks that the selected model is installed and proxies the chat to Ollama. It never falls back to cloud inference.
- `scripts/setup-local-ai.sh` and `scripts/setup-local-ai.ps1`: check the Ollama runtime and pull a modest starter model.
- Tests cover model listing, local chat, missing-model handling and loopback-only URL validation.

This does not claim that the camera page or the local chat have been browser-tested in this environment. The test suite must be run in the repository's CI/Codespace.

## Install a local model

Install Ollama first: https://ollama.com/download

Windows PowerShell:
```powershell
.scriptssetup-local-ai.ps1
```

Linux / macOS / Codespaces:
```bash
bash scripts/setup-local-ai.sh
```

Default model: `qwen2.5:3b`. This model download needs internet and disk space. After the download completes, local inference does not require internet while Ollama and the model remain installed. Model performance and memory needs depend on quantization, context size, operating system, and available RAM/VRAM. If your machine is memory constrained, use a smaller model supported by Ollama; if it is stronger, set `FRIDAY_OLLAMA_MODEL` to a model you know your hardware can run.

Start FRIDAY:
```bash
python -m pip install -r requirements.txt
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```
Open http://127.0.0.1:8000/static/local-ai.html. The API expects Ollama at `http://127.0.0.1:11434` by default. Set `OLLAMA_BASE_URL` only to a loopback URL if you need another local port. Do not expose Ollama's unauthenticated API to a public network.

## Offline behavior

The local chat is intentionally a separate mode. If Ollama is stopped or a model is missing, FRIDAY displays an error and does not send prompts to Nebius, NVIDIA, OpenAI-compatible endpoints, or another cloud provider. Downloaded model weights are local, but Python dependencies, the frontend itself, and CDN assets for the separate spatial/gesture page may still require an initial internet connection. For a truly offline installation, install Python dependencies and cache all frontend/runtime/model assets before disconnecting; the current spatial page uses external CDNs and is not fully offline yet.

## Open-source agent/tool integrations

These are upstream projects and documented integration targets. They are not all bundled into this repository by this change, and their presence does not prove a live adapter is ready.

- Ollama runtime: https://github.com/ollama/ollama (MIT). Runs local models; it is not itself a coding agent.
- OpenCode: https://github.com/anomalyco/opencode (MIT). Optional coding-agent CLI; configure it to use Ollama's OpenAI-compatible endpoint and the installed model. Keep changes in a Git worktree and review the diff.
- Hermes Agent: https://github.com/NousResearch/hermes-agent (MIT). Optional agent runtime. Install and configure it separately, then test its documented Ollama provider support for the chosen version.
- ECC Skills: https://github.com/affaan-m/ECC (MIT). Skills should be imported into quarantine, reviewed, and explicitly enabled. Never execute arbitrary uploaded skill scripts automatically.
- NVIDIA NemoClaw: https://github.com/NVIDIA/NemoClaw. Optional policy/sandbox stack; verify its license, host requirements and supported runtime version upstream before installation.
- MediaPipe Tasks Vision: https://github.com/google-ai-edge/mediapipe (Apache-2.0). Used by the separate gesture interface via CDN at present.
- Three.js: https://github.com/mrdoob/three.js (MIT). Used by the separate spatial interface via CDN at present.
- Tesseract OCR: https://github.com/tesseract-ocr/tesseract (Apache-2.0). OCR engine, not a video-generation model.
- FFmpeg: https://github.com/FFmpeg/FFmpeg. Media processing; check build/license configuration before redistribution.

Cursor, Bolt, Lovable and Claude Code are not interchangeable open-source code libraries. Their products, APIs, export workflows, licenses and terms differ. FRIDAY can support documented integrations and source import; it must not copy private source, reverse engineer protected APIs, or claim to control another application's GUI without a supported connector.

## Security boundaries

- No chat request triggers shell execution, arbitrary file writes, deployment, device actions, or an agent run.
- Ollama endpoint is restricted to loopback HTTP to reduce SSRF risk.
- Local chat has bounded message count/size and request timeout.
- Coding agents should run in isolated worktrees with timeouts, bounded retries, logs and human review before applying changes.
- Camera is opt-in; gesture input is not wired to destructive actions.
- Skills and third-party repository instructions are untrusted content and cannot override FRIDAY policy.

## Validation checklist

```bash
python -m pytest -q
```

Then start Ollama, pull a model, start FRIDAY and test `/api/v1/local-ai/status`, `/api/v1/local-ai/chat`, and the UI. The implementation should be called working only after these tests pass on the target machine.
