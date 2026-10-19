from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


TaskStatus = Literal["planned", "running", "completed", "failed"]
TaskCategory = Literal["coding", "research", "iot", "personal", "creative", "general"]
TaskRisk = Literal["low", "medium", "high", "critical"]
BotRuntime = Literal["plan_only", "codex_cli"]


class TaskCreate(BaseModel):
    prompt: str = Field(min_length=1, max_length=8000)
    session_id: str | None = Field(default=None, max_length=128)
    skill_ids: list[str] = Field(default_factory=list, max_length=5)
    bot_id: str | None = Field(default=None, max_length=64)
    model_route: str = Field(default="auto", min_length=1, max_length=48, pattern=r"^[a-z0-9][a-z0-9_-]{0,47}$")


class BotCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    description: str = Field(default="", max_length=300)
    instructions: str = Field(min_length=1, max_length=6000)
    memory: str = Field(default="", max_length=4000)
    default_model_route: str = Field(default="auto", min_length=1, max_length=48, pattern=r"^[a-z0-9][a-z0-9_-]{0,47}$")
    runtime: BotRuntime = "plan_only"
    skill_ids: list[str] = Field(default_factory=list, max_length=5)
    enabled: bool = True


class BotUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    description: str | None = Field(default=None, max_length=300)
    instructions: str | None = Field(default=None, min_length=1, max_length=6000)
    memory: str | None = Field(default=None, max_length=4000)
    default_model_route: str | None = Field(default=None, min_length=1, max_length=48, pattern=r"^[a-z0-9][a-z0-9_-]{0,47}$")
    runtime: BotRuntime | None = None
    skill_ids: list[str] | None = Field(default=None, max_length=5)
    enabled: bool | None = None


class BotResponse(BaseModel):
    id: str
    name: str
    description: str
    instructions: str
    memory: str
    default_model_route: str
    runtime: BotRuntime
    skill_ids: list[str] = Field(default_factory=list)
    enabled: bool
    created_at: datetime
    updated_at: datetime


class SkillReviewRequest(BaseModel):
    content_sha256: str = Field(min_length=64, max_length=64, pattern=r"^[a-f0-9]{64}$")
    confirmation: str = Field(min_length=1, max_length=100)


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
    skill_ids: list[str] = Field(default_factory=list)
    bot_id: str | None = None
    bot_name: str | None = None
    bot_runtime: BotRuntime | None = None
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
