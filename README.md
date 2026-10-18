# TEDDY

**TEDDY** is a personal AI operator prototype for the Nebius Global AI Hackathon. The intended product combines a minimal command-centre UI, model routing, specialized Bots, policy-controlled tools, and a verified coding loop.

## Backend status

The initial backend is now in the repository:

- FastAPI health and status routes
- Task planning and persistent SQLite task history
- Deterministic fallback planner so development can continue without cloud credentials
- Optional Nebius Token Factory model adapter
- Risk/approval flags for requests that may cause external or physical actions
- Integration-readiness endpoint that distinguishes configured, missing, and planned routes
- Optional Claude Fable 5.1 reasoning route, disabled by default and gated by complexity/budget heuristics
- tmux development launcher for supervising the API terminal and a shell
- No external action execution is enabled yet

This is a working **backend foundation**, not the complete assistant. It does not yet execute shell commands, send messages, control devices, use a webcam, or provide the final UI.

## Run in GitHub Codespaces

Open the repository in GitHub Codespaces, then run in the terminal:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

In Codespaces, open the **Ports** tab and open port **8000** in your browser. FastAPI's interactive API explorer is at `/docs`.

On Windows PowerShell (if running outside Codespaces), activate the environment with:

```powershell
.\.venv\Scripts\Activate.ps1
```

## Quick test

Health check:

```bash
curl http://127.0.0.1:8000/health
```

Create a task:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/tasks \
  -H "Content-Type: application/json" \
  -d '{"prompt":"Help me debug my Python API"}'
```

List recent tasks:

```bash
curl http://127.0.0.1:8000/api/v1/tasks
```

List actual integration readiness:

```bash
curl http://127.0.0.1:8000/api/v1/integrations
```

The integration registry does not execute agents or expose credentials. A command being installed is not enough to mark it fully operational.

Get a task by its ID:

```bash
curl http://127.0.0.1:8000/api/v1/tasks/TASK_ID
```

When no model credentials are configured, TEDDY uses a deterministic fallback planner and explicitly reports that no external model was called.

## Configure Nebius Token Factory later

1. Copy `.env.example` to `.env`.
2. Set `NEBIUS_API_KEY`.
3. Set `NEBIUS_MODEL` to the exact model ID available in your Token Factory account.
4. Keep `.env` out of Git.

The configured default base URL is `https://api.tokenfactory.nebius.com/v1`.

The backend calls the configured model for task planning only. Model output is validated before it is stored. External actions and tool execution remain disabled.


## Optional Claude Fable 5.1 reasoning route

Claude Fable 5.1 is a backend-only hosted reasoning route, not a UI component. It is disabled by default and will only be considered when both `ANTHROPIC_API_KEY` is present and `CLAUDE_FABLE_ENABLED=true`. It is selected only when the task text matches a narrow set of complex/long-horizon signals and the estimated-cost/prompt/output caps pass; ordinary tasks stay on the configured Nebius route or the local fallback.

Add these settings to your ignored local `.env` only after choosing to use the paid API:

```dotenv
ANTHROPIC_API_KEY=your_key_here
CLAUDE_FABLE_MODEL=claude-fable-5-1
CLAUDE_FABLE_ENABLED=true
CLAUDE_FABLE_MAX_OUTPUT_TOKENS=900
CLAUDE_FABLE_MAX_PROMPT_CHARS=8000
CLAUDE_FABLE_MAX_ESTIMATED_COST_USD=0.10
```

The budget calculation is approximate, not a provider-enforced billing cap. Keep credentials private, inspect provider pricing, and leave the route disabled when it is not needed. Model calls are for planning only; they do not directly execute tools. See [Claude Fable 5.1 API docs](https://platform.claude.com/docs/en/models/fable-5-1/overview).

## tmux development sessions

tmux can keep the API and shell sessions available when the terminal connection drops, as long as the Codespace/container itself keeps running. It is not 24/7 hosting.

```bash
sudo apt-get update && sudo apt-get install -y tmux
bash scripts/tmux-dev.sh
```

Detach without stopping the session with **Ctrl+B**, then **D**. Reattach with `tmux attach -t teddy-dev`. Stop it with `tmux kill-session -t teddy-dev`.

## Integration inventory

- [AI integration architecture](docs/AI_INTEGRATION_ARCHITECTURE.md)
- [Inspected uploads and pending files](docs/UPLOAD_INVENTORY.md)

Needle 3 source has been inspected for possible compact structured tool calling, but its weights/engine are not bundled in the uploaded ZIP. The separate Tesseract ZIP is an OCR engine; it is not the video-editing tool. Nex-N2.5, the user's broad skills directory, the actual Tesseract video tool, and the Blynk library still require their exact source/credentials or files before connection.

## Tests

```bash
pytest -q
```

## Security

- Never commit API keys, tokens, or private credentials.
- Model output is untrusted input and is not executed.
- External actions are intentionally disabled in this initial backend.
- Before enabling tools, add isolated workers, authorization checks, audit logs, and a bounded verification loop.

## License

TEDDY's original code is distributed under the MIT License. Third-party repositories, libraries, and models retain their own licenses and terms.
