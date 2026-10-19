from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import BackgroundTasks, FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from backend.database import claim_task_for_agent, get_task, init_db, insert_task, list_tasks, update_task, utc_now
from backend.integration_registry import list_integrations
from backend.model_profiles import public_model_profiles
from backend.model_router import (
    create_plan,
    ModelProviderUnavailableForSkills,
    ModelRouteUnavailable,
)
from backend.skill_registry import list_skill_metadata, SkillNotApprovedError
from backend.schemas import BackendStatus, TaskCreate, TaskResponse
from backend.settings import get_settings
from backend.agent_runner import agent_available, run_codex_task


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


settings = get_settings()
FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"

app = FastAPI(
    title="TEDDY API",
    description=(
        "TEDDY's task planner, persistent task history, and optional sandboxed Codex coding worker. "
        "Other external actions remain disabled unless separately integrated."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

origins = [item.strip() for item in settings.cors_origins.split(",") if item.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Authorization"],
)

# Serve the command-centre UI from the same origin as the API. This keeps
# Codespaces setup simple and avoids exposing API credentials to browser code.
app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR / "static")), name="static")


@app.get("/", tags=["ui"], include_in_schema=False)
async def root():
    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/api", tags=["system"])
async def api_root():
    return {
        "name": "TEDDY",
        "message": "TEDDY backend is running.",
        "docs": "/docs",
        "health": "/health",
        "ui": "/",
    }


@app.get("/health", tags=["system"])
async def health():
    return {"status": "ok", "service": "teddy-backend", "version": "0.1.0"}


@app.get("/api/v1/status", response_model=BackendStatus, tags=["system"])
async def backend_status():
    current = get_settings()
    if current.nebius_ready:
        provider = "nebius-token-factory"
        configured_model = current.nebius_model
        note = "Nebius model configured. This backend still plans tasks only; external actions are not enabled."
    elif current.nvidia_ready:
        provider = "nvidia-nim"
        configured_model = current.nvidia_model
        note = "NVIDIA NIM model configured. This backend still plans tasks only; external actions are not enabled."
    elif current.openai_compatible_ready:
        provider = "openai-compatible"
        configured_model = current.openai_compatible_model
        note = "Custom OpenAI-compatible model configured. This backend still plans tasks only; external actions are not enabled."
    elif current.claude_fable_ready:
        provider = "anthropic-claude-fable"
        configured_model = current.claude_fable_model
        note = "Claude Fable is configured for complex reasoning tasks only. This backend still plans tasks only; external actions are not enabled."
    else:
        provider = "local-fallback"
        configured_model = None
        note = "No external model provider is configured. Deterministic fallback planning is active; no external model is being called."
    return BackendStatus(
        name="TEDDY",
        status="ready" if provider != "local-fallback" else "development-mode",
        model_provider=provider,
        configured_model=configured_model,
        execution_enabled=False,
        note=note,
    )


@app.get("/api/v1/models", tags=["models"])
async def model_routes():
    """List model routes this backend can actually select today."""
    current = get_settings()
    return {
        "default_route": "auto",
        "routes": [
            {
                "id": "auto",
                "name": "Automatic",
                "available": True,
                "model": None,
                "details": "Uses Claude Fable only for complex tasks when enabled and within budget; otherwise uses the configured Nebius or NVIDIA NIM model, then a ready named model profile, the generic OpenAI-compatible model, or the deterministic local fallback.",
            },
            {
                "id": "nebius",
                "name": (
                    "NVIDIA Nemotron via Nebius"
                    if current.nebius_model and "nemotron" in current.nebius_model.casefold()
                    else "Nebius Token Factory"
                ),
                "available": current.nebius_ready,
                "model": current.nebius_model if current.nebius_ready else None,
                "details": "Uses the exact NEBIUS_MODEL value. This may be a Nemotron model if that exact ID is available in the user's Token Factory account.",
            },
            {
                "id": "nvidia_nim",
                "name": (
                    "NVIDIA Nemotron (NIM)"
                    if current.nvidia_model and "nemotron" in current.nvidia_model.casefold()
                    else "NVIDIA NIM"
                ),
                "available": current.nvidia_ready,
                "model": current.nvidia_model if current.nvidia_ready else None,
                "details": "Uses the exact NVIDIA_MODEL value at NVIDIA_BASE_URL. Configure a supported model ID and NVIDIA API key before selecting this route.",
            },
            {
                "id": "openai_compatible",
                "name": current.openai_compatible_name,
                "available": current.openai_compatible_ready,
                "model": current.openai_compatible_model if current.openai_compatible_ready else None,
                "details": "Optional custom endpoint. Configure its base URL, key, and exact model ID; the endpoint must support OpenAI-compatible chat completions.",
            },
            {
                "id": "claude_fable",
                "name": "Claude Fable 5.1",
                "available": current.claude_fable_ready,
                "model": current.claude_fable_model if current.claude_fable_ready else None,
                "details": "Optional premium reasoning route; it is disabled by default and remains behind a prompt-size and approximate-cost guard.",
            },
        ] + public_model_profiles(),
        "note": "NVIDIA NIM supports configured compatible chat models (including Nemotron where available). Additional OpenAI-compatible models can be added in data/model-profiles.json. A supervised Codex CLI worker is available for eligible coding tasks when installed; Hermes and Claude Code remain inventory-only pending separate adapters.",
    }


@app.get("/api/v1/integrations", tags=["system"])
async def integration_status():
    """Report integration readiness without exposing credentials or running tools."""
    return {"integrations": list_integrations()}


@app.get("/api/v1/skills", tags=["skills"])
async def skill_inventory():
    """Return imported skill metadata; discovered skills are never enabled automatically."""
    return list_skill_metadata()


@app.post("/api/v1/tasks", response_model=TaskResponse, tags=["tasks"])
async def create_task(request: TaskCreate):
    prompt = request.prompt.strip()
    if not prompt:
        raise HTTPException(status_code=422, detail="Prompt cannot be blank.")

    try:
        plan = await create_plan(
            prompt,
            requested_skill_ids=request.skill_ids,
            requested_route=request.model_route,
        )
    except SkillNotApprovedError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ModelRouteUnavailable as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ModelProviderUnavailableForSkills as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:
        # Avoid leaking credentials or provider response internals.
        raise HTTPException(
            status_code=502,
            detail=(
                "Model-provider request failed. Check the configured "
                "provider key, model ID, and endpoint URL."
            ),
        ) from exc

    now = datetime.now(timezone.utc)
    task = {
        "id": str(uuid4()),
        "session_id": request.session_id or str(uuid4()),
        "prompt": prompt,
        "status": "planned",
        "category": plan["category"],
        "provider": plan["provider"],
        "model": plan["model"],
        "risk": plan["risk"],
        "approval_required": plan["approval_required"],
        "plan": plan["plan"],
        "created_at": now,
        "skills_used": plan.get("skills_used", []),
        "execution_mode": "plan_only",
        "agent_name": None,
        "workspace_path": None,
        "result_text": None,
        "execution_log": ["Task plan created. No tools or commands have run."],
        "updated_at": now.isoformat(),
    }
    insert_task({
        **task,
        "created_at": now.isoformat(),
    })
    return TaskResponse(**task)


@app.post("/api/v1/tasks/{task_id}/run", response_model=TaskResponse, tags=["tasks"])
async def run_task_with_agent(task_id: str, background_tasks: BackgroundTasks):
    """Run an eligible coding task inside a disposable Codex-controlled Git worktree."""
    task = get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found.")
    if task["status"] != "planned" or task.get("execution_mode") != "plan_only":
        raise HTTPException(status_code=409, detail="This task has already been submitted to an agent or is not in a runnable state.")
    if task["category"] != "coding":
        raise HTTPException(status_code=409, detail="Only coding tasks can be sent to the isolated coding worker. Other task categories remain plan-only.")
    if task["risk"] in {"high", "critical"} or task["approval_required"]:
        raise HTTPException(status_code=409, detail="This task is marked high-risk or requires approval. The coding worker will not run it automatically.")
    if not agent_available():
        raise HTTPException(status_code=409, detail="OpenAI Codex CLI is not installed or not on PATH. Install and authenticate Codex CLI, then restart TEDDY.")
    log = list(task.get("execution_log", []))
    log.append("Queued for Codex CLI in a separate Git worktree. The main working tree will not be edited by this run.")
    if not claim_task_for_agent(task_id, "OpenAI Codex CLI", log):
        raise HTTPException(status_code=409, detail="Another request already claimed this task. Refresh task history and inspect its status.")
    updated = get_task(task_id)
    background_tasks.add_task(run_codex_task, task_id)
    return TaskResponse(**updated)


@app.get("/api/v1/tasks", response_model=list[TaskResponse], tags=["tasks"])
async def get_tasks(limit: int = Query(default=30, ge=1, le=100)):
    rows = list_tasks(limit)
    return [TaskResponse(**row) for row in rows]


@app.get("/api/v1/tasks/{task_id}", response_model=TaskResponse, tags=["tasks"])
async def get_task_by_id(task_id: str):
    task = get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found.")
    return TaskResponse(**task)
