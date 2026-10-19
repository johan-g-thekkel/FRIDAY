from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


TaskStatus = Literal["planned", "failed"]
TaskCategory = Literal["coding", "research", "iot", "personal", "creative", "general"]
TaskRisk = Literal["low", "medium", "high", "critical"]
ModelRoute = Literal["auto", "nebius", "claude_fable"]


class TaskCreate(BaseModel):
    prompt: str = Field(min_length=1, max_length=8000)
    session_id: str | None = Field(default=None, max_length=128)
    # Explicit skill selections must already be locally approved.
    skill_ids: list[str] = Field(default_factory=list, max_length=5)
    model_route: ModelRoute = "auto"


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


class BackendStatus(BaseModel):
    name: str
    status: str
    model_provider: str
    configured_model: str | None
    execution_enabled: bool
    note: str
