# TEDDY

**TEDDY** is a personal AI operator prototype for the Nebius Global AI Hackathon. The intended product combines a minimal command-centre UI, model routing, specialized Bots, policy-controlled tools, and a verified coding loop.

## Command-centre UI

The web UI is served directly by FastAPI at `/` (CSS and JavaScript under `/static`). In Codespaces, open the forwarded port 8000 to use the command centre; no separate npm/Vite server is required. It loads `/health`, `/api/v1/status`, `/api/v1/models`, `/api/v1/integrations`, `/api/v1/skills`, and `/api/v1/tasks`, then polls for updates every eight seconds while the tab is visible. Task submission creates a persisted plan and task history entry.

**Current execution boundary:** this interface does not pretend that planning is code execution. The backend's task endpoint still stores plans only; Hermes/Codex/Claude Code worker execution, isolated workspaces, terminal streaming, automatic repair, and device actions are not enabled yet. Skills remain read-only in the UI and must be hash-approved with the guarded CLI.

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

List available model routes:

```bash
curl http://127.0.0.1:8000/api/v1/models
```

POST `/api/v1/tasks` accepts `model_route` values `auto`, `nebius`, or `claude_fable`. The `nebius` route uses the exact model ID configured in `NEBIUS_MODEL`; set it to a supported Nemotron ID in your Token Factory account to route tasks to Nemotron. Unconfigured explicit routes return HTTP 409 rather than silently falling back.

List actual integration readiness:

```bash
curl http://127.0.0.1:8000/api/v1/integrations
```

List metadata for local imported skills (does not activate or execute them):

```bash
curl http://127.0.0.1:8000/api/v1/skills
```

Set `SKILLS_ROOT=./skills/imported` in `.env` or leave the default. Copy reviewed skill folders into that local directory; it is ignored by Git so your imported skill content is not published automatically. The endpoint reads only small `SKILL.md` metadata and marks every discovered skill `disabled_pending_review`.

The integration registry does not execute agents or expose credentials. A command being installed is not enough to mark it fully operational.

### Import skill metadata from your ZIPs

Download the curated TEDDY skill candidates ZIP attached to the project handoff, then upload it to your Codespace under `/workspaces/TEDDY/incoming/`. Run:

```bash
python scripts/import_skill_metadata.py incoming/teddy-skill-candidates.zip
curl http://127.0.0.1:8000/api/v1/skills
```

The bundle contains 316 canonical `SKILL.md` files from ECC, Astra, GLM-V, and REA plus source-license files and a provenance manifest. It intentionally excludes executable scripts, model weights, environment files, and CL4R1T4S prompt dumps. The importer copies only canonical `SKILL.md` files into the local ignored directory `skills/imported/`; it does not install dependencies, execute scripts, or enable skills. All discovered skills start as `disabled_pending_review`. The original `ECC-main.zip` and `Desktop2222.zip` archives can also be scanned directly if copied into the Codespace.

Review and enable a skill from the terminal:

```bash
python scripts/skill_admin.py list
python scripts/skill_admin.py show SKILL_ID
python scripts/skill_admin.py enable SKILL_ID
```

The enable command prints the skill content and requires you to type `ENABLE SKILL_ID` after review. It writes a local, gitignored hash-pinned policy; if the skill file changes, it is disabled automatically until reviewed again. You can use `python scripts/skill_admin.py disable SKILL_ID` at any time.

When a provider is configured, TEDDY selects at most two hash-approved skills based on prompt/description keyword overlap, capped at 6,000 total skill-content characters by default. The model receives them as untrusted supplemental guidance, not system policy. POST `/api/v1/tasks` also accepts `skill_ids` for explicit selections; requests for unapproved skills are rejected. The task response records `skills_used`. With only the local fallback active, skills are not represented as used because no model receives their instructions.

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

Optional: configure NVIDIA NIM as a separate route (for example, a Nemotron model supported by your NVIDIA API account):

```dotenv
NVIDIA_API_KEY=your_key_here
NVIDIA_BASE_URL=https://integrate.api.nvidia.com/v1
NVIDIA_MODEL=your_exact_nvidia_model_id
```

Then restart the backend and check `GET /api/v1/models`. Select `model_route: "nvidia_nim"` for a task to use that endpoint. NVIDIA's NIM API uses the OpenAI-compatible `/v1/chat/completions` interface; supported model IDs and access vary by model/account ([official API reference](https://docs.api.nvidia.com/nim/reference/llm-apis)).

### Add more hosted model profiles without changing TEDDY's router

For any additional provider that exposes an **OpenAI-compatible chat-completions API**, configure a named profile rather than adding Python code for every model:

```bash
mkdir -p data
cp config/model-profiles.example.json data/model-profiles.json
```

Edit `data/model-profiles.json` and replace each placeholder `base_url` and `model` with the exact endpoint and model ID documented by your provider. Give each profile a unique lowercase `id`; put the **name of an environment variable** in `api_key_env`, not the API key itself; add that secret to your local `.env` or Codespaces secrets; and only set `enabled` to `true` after validating the endpoint. Example profile:

```json
{
  "id": "nex_n2_5",
  "name": "Nex-N2.5",
  "base_url": "https://YOUR_VERIFIED_ENDPOINT/v1",
  "model": "YOUR_EXACT_MODEL_ID",
  "api_key_env": "NEX_N2_5_API_KEY",
  "priority": 50,
  "capabilities": ["text", "reasoning", "coding"],
  "enabled": true
}
```

Then add `NEX_N2_5_API_KEY=...` to the local `.env`, restart TEDDY, and check `GET /api/v1/models`. If the profile is configured and its key exists, its `id` becomes a valid `model_route`. With `auto`, TEDDY selects a ready profile after Nebius/NVIDIA routes and before the single custom OpenAI-compatible route. Profiles are only marked `configured_not_tested`; they are not declared healthy until a real call succeeds.

**Important:** this adapter handles text-based chat completions only. A profile's `vision` or `audio` capability is descriptive metadata, not proof that multimodal inputs are implemented. Nex-N2.5 or GLM-V must expose a compatible endpoint for this adapter to call them; raw model source/weights or an agentic API require a separate adapter. The profile file is under `data/`, which is gitignored, and API secrets must never be committed.

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
