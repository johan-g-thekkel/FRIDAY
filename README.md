# TEDDY

**TEDDY** is a personal AI operator prototype for the Nebius Global AI Hackathon. The intended product combines a minimal command-centre UI, model routing, specialized Bots, policy-controlled tools, and a verified coding loop.

## Backend status

The initial backend is now in the repository:

- FastAPI health and status routes
- Task planning and persistent SQLite task history
- Deterministic fallback planner so development can continue without cloud credentials
- Optional Nebius Token Factory model adapter
- Risk/approval flags for requests that may cause external or physical actions
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
