from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


TaskStatus = Literal["planned", "running", "completed", "failed"]
TaskCategory = Literal["coding", "research", "iot", "personal", "creative", "general"]
TaskRisk = Literal["low", "medium", "high", "critical"]


class TaskCreate(BaseModel):
    prompt: str = Field(min_length=1, max_length=8000)
    session_id: str | None = Field(default=None, max_length=128)
    skill_ids: list[str] = Field(default_factory=list, max_length=5)
    model_route: str = Field(default="auto", min_length=1, max_length=48, pattern=r"^[a-z0-9][a-z0-9_-]{0,47}$")


class TaskResponse(BaseModel):
    id: str
    session_id: str
    prompt: str
    status: TaskStatus
    category: TaskCategory
    provider: str
    model: str | None
    risk: TaskRisk
    approval_required: bool
    plan: list[str]
    created_at: datetime
    skills_used: list[str] = Field(default_factory=list)
    execution_mode: Literal["plan_only", "agent"] = "plan_only"
    agent_name: str | None = None
    workspace_path: str | None = None
    result_text: str | None = None
    execution_log: list[str] = Field(default_factory=list)
    updated_at: datetime | None = None


class BackendStatus(BaseModel):
    name: str
    status: str
    model_provider: str
    configured_model: str | None
    execution_enabled: bool
    note: str
