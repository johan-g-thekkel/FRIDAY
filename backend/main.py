from contextlib import asynccontextmanager
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from backend.database import get_task, init_db, insert_task, list_tasks
from backend.integration_registry import list_integrations
from backend.model_router import (
    create_plan,
    ModelProviderUnavailableForSkills,
    ModelRouteUnavailable,
)
from backend.skill_registry import list_skill_metadata, SkillNotApprovedError
from backend.schemas import BackendStatus, TaskCreate, TaskResponse
from backend.settings import get_settings


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


settings = get_settings()
app = FastAPI(
    title="TEDDY API",
    description=(
        "TEDDY's task-planning backend. The initial version plans tasks and "
        "stores them; execution tools will be added behind policy checks."
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


@app.get("/", tags=["system"])
async def root():
    return {
        "name": "TEDDY",
        "message": "TEDDY backend is running.",
        "docs": "/docs",
        "health": "/health",
    }


@app.get("/health", tags=["system"])
async def health():
    return {"status": "ok", "service": "teddy-backend", "version": "0.1.0"}


@app.get("/api/v1/status", response_model=BackendStatus, tags=["system"])
async def backend_status():
    ready = settings.nebius_ready
    return BackendStatus(
        name="TEDDY",
        status="ready" if ready else "development-mode",
        model_provider="nebius-token-factory" if ready else "local-fallback",
        configured_model=settings.nebius_model if ready else None,
        execution_enabled=False,
        note=(
            "Nebius model configured. This backend still plans tasks only; "
            "external actions are not enabled."
            if ready
            else "No Nebius API key/model configured. Deterministic fallback "
            "planning is active; no external model is being called."
        ),
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
                "details": "Uses Claude Fable only for complex tasks when enabled and within budget; otherwise uses the configured Nebius or NVIDIA NIM model, or the deterministic local fallback.",
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
                "id": "claude_fable",
                "name": "Claude Fable 5.1",
                "available": current.claude_fable_ready,
                "model": current.claude_fable_model if current.claude_fable_ready else None,
                "details": "Optional premium reasoning route; it is disabled by default and remains behind a prompt-size and approximate-cost guard.",
            },
        ],
        "note": "NVIDIA NIM supports configured compatible chat models (including Nemotron where available). Hermes, Codex, Claude Code, Nex-N2.5, Needle 3, and GLM-V still require separate runtime/provider adapters and are not yet selectable from this model-route endpoint.",
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
    }
    insert_task({
        **task,
        "created_at": now.isoformat(),
    })
    return TaskResponse(**task)


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
