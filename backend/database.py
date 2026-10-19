import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.settings import get_settings


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _connect() -> sqlite3.Connection:
    settings = get_settings()
    db_path = Path(settings.sqlite_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(str(db_path), timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA journal_mode=WAL")
    return connection


def init_db() -> None:
    with _connect() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS tasks (
                id TEXT PRIMARY KEY, session_id TEXT NOT NULL, prompt TEXT NOT NULL,
                status TEXT NOT NULL, category TEXT NOT NULL, provider TEXT NOT NULL,
                model TEXT, risk TEXT NOT NULL, approval_required INTEGER NOT NULL,
                plan_json TEXT NOT NULL, created_at TEXT NOT NULL,
                skills_used_json TEXT NOT NULL DEFAULT '[]', skill_ids_json TEXT NOT NULL DEFAULT '[]',
                execution_mode TEXT NOT NULL DEFAULT 'plan_only', agent_name TEXT,
                workspace_path TEXT, result_text TEXT,
                execution_log_json TEXT NOT NULL DEFAULT '[]', updated_at TEXT
            )
            """
        )
        columns = {row["name"] for row in connection.execute("PRAGMA table_info(tasks)").fetchall()}
        migrations = {
            "skills_used_json": "TEXT NOT NULL DEFAULT '[]'",
            "skill_ids_json": "TEXT NOT NULL DEFAULT '[]'",
            "execution_mode": "TEXT NOT NULL DEFAULT 'plan_only'",
            "agent_name": "TEXT",
            "workspace_path": "TEXT",
            "result_text": "TEXT",
            "execution_log_json": "TEXT NOT NULL DEFAULT '[]'",
            "updated_at": "TEXT",
        }
        for column, sql_type in migrations.items():
            if column not in columns:
                connection.execute(f"ALTER TABLE tasks ADD COLUMN {column} {sql_type}")


def insert_task(task: dict[str, Any]) -> None:
    with _connect() as connection:
        connection.execute(
            """
            INSERT INTO tasks (
                id, session_id, prompt, status, category, provider, model, risk,
                approval_required, plan_json, created_at, skills_used_json, skill_ids_json,
                execution_mode, agent_name, workspace_path, result_text,
                execution_log_json, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                task["id"], task["session_id"], task["prompt"], task["status"],
                task["category"], task["provider"], task["model"], task["risk"],
                int(task["approval_required"]), json.dumps(task["plan"]),
                task["created_at"], json.dumps(task.get("skills_used", [])),
                json.dumps(task.get("skill_ids", [])), task.get("execution_mode", "plan_only"), task.get("agent_name"),
                task.get("workspace_path"), task.get("result_text"),
                json.dumps(task.get("execution_log", [])), task.get("updated_at"),
            ),
        )


def update_task(task_id: str, **fields: Any) -> bool:
    """Update only allowed lifecycle fields; arbitrary SQL columns are never accepted."""
    allowed = {
        "status", "execution_mode", "agent_name", "workspace_path",
        "result_text", "execution_log", "updated_at",
    }
    updates = {key: value for key, value in fields.items() if key in allowed}
    if not updates:
        return False
    assignments: list[str] = []
    values: list[Any] = []
    for key, value in updates.items():
        if key == "execution_log":
            key, value = "execution_log_json", json.dumps(value or [])
        assignments.append(f"{key} = ?")
        values.append(value)
    values.append(task_id)
    with _connect() as connection:
        cursor = connection.execute(
            f"UPDATE tasks SET {', '.join(assignments)} WHERE id = ?", tuple(values)
        )
        return cursor.rowcount > 0


def fail_interrupted_agent_tasks() -> int:
    """Mark workers interrupted by a server restart as failed while retaining their worktrees."""
    with _connect() as connection:
        rows = connection.execute(
            "SELECT id, execution_log_json, result_text FROM tasks "
            "WHERE status = 'running' AND execution_mode = 'agent'"
        ).fetchall()
        for row in rows:
            try:
                log = json.loads(row["execution_log_json"] or "[]")
            except (ValueError, TypeError):
                log = []
            log.append("TEDDY restarted while this worker was marked running. Status was recovered to failed; inspect the retained worktree before retrying.")
            connection.execute(
                "UPDATE tasks SET status = 'failed', result_text = ?, execution_log_json = ?, updated_at = ? WHERE id = ?",
                ("Backend restarted during agent execution. The worktree, if created, was retained for inspection.",
                 json.dumps(log[-80:]), utc_now(), row["id"]),
            )
        return len(rows)


def claim_task_for_agent(task_id: str, agent_name: str, log_entries: list[str]) -> bool:
    """Atomically claim a planned task so concurrent requests cannot launch two workers."""
    with _connect() as connection:
        cursor = connection.execute(
            """UPDATE tasks
               SET status = 'running', execution_mode = 'agent', agent_name = ?,
                   execution_log_json = ?, updated_at = ?
               WHERE id = ? AND status = 'planned' AND execution_mode = 'plan_only'""",
            (agent_name, json.dumps(log_entries[-80:]), utc_now(), task_id),
        )
        return cursor.rowcount == 1


def _row_to_task(row: sqlite3.Row) -> dict[str, Any]:
    task = dict(row)
    task["approval_required"] = bool(task["approval_required"])
    task["plan"] = json.loads(task.pop("plan_json"))
    task["skills_used"] = json.loads(task.pop("skills_used_json", "[]") or "[]")
    task["skill_ids"] = json.loads(task.pop("skill_ids_json", "[]") or "[]")
    task["execution_log"] = json.loads(task.pop("execution_log_json", "[]") or "[]")
    task.setdefault("execution_mode", "plan_only")
    task.setdefault("agent_name", None)
    task.setdefault("workspace_path", None)
    task.setdefault("result_text", None)
    task.setdefault("updated_at", None)
    return task


def get_task(task_id: str) -> dict[str, Any] | None:
    with _connect() as connection:
        row = connection.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    return _row_to_task(row) if row else None


def list_tasks(limit: int = 30) -> list[dict[str, Any]]:
    with _connect() as connection:
        rows = connection.execute(
            "SELECT * FROM tasks ORDER BY created_at DESC LIMIT ?",
            (max(1, min(limit, 100)),),
        ).fetchall()
    return [_row_to_task(row) for row in rows]
