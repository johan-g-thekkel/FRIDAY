from contextlib import asynccontextmanager
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from backend.database import get_task, init_db, insert_task, list_tasks
from backend.model_router import create_plan
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


@app.post("/api/v1/tasks", response_model=TaskResponse, tags=["tasks"])
async def create_task(request: TaskCreate):
    prompt = request.prompt.strip()
    if not prompt:
        raise HTTPException(status_code=422, detail="Prompt cannot be blank.")

    try:
        plan = await create_plan(prompt)
    except Exception as exc:
        # Avoid leaking credentials or provider response internals.
        raise HTTPException(
            status_code=502,
            detail=(
                "Nebius Token Factory request failed. Check the configured "
                "API key, model ID, and endpoint URL."
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
