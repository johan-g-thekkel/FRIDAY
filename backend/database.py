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
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                prompt TEXT NOT NULL,
                status TEXT NOT NULL,
                category TEXT NOT NULL,
                provider TEXT NOT NULL,
                model TEXT,
                risk TEXT NOT NULL,
                approval_required INTEGER NOT NULL,
                plan_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )


def insert_task(task: dict[str, Any]) -> None:
    with _connect() as connection:
        connection.execute(
            """
            INSERT INTO tasks (
                id, session_id, prompt, status, category, provider, model,
                risk, approval_required, plan_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                task["id"],
                task["session_id"],
                task["prompt"],
                task["status"],
                task["category"],
                task["provider"],
                task["model"],
                task["risk"],
                int(task["approval_required"]),
                json.dumps(task["plan"]),
                task["created_at"],
            ),
        )


def _row_to_task(row: sqlite3.Row) -> dict[str, Any]:
    task = dict(row)
    task["approval_required"] = bool(task["approval_required"])
    task["plan"] = json.loads(task.pop("plan_json"))
    return task


def get_task(task_id: str) -> dict[str, Any] | None:
    with _connect() as connection:
        row = connection.execute(
            "SELECT * FROM tasks WHERE id = ?", (task_id,)
        ).fetchone()
    return _row_to_task(row) if row else None


def list_tasks(limit: int = 30) -> list[dict[str, Any]]:
    with _connect() as connection:
        rows = connection.execute(
            "SELECT * FROM tasks ORDER BY created_at DESC LIMIT ?",
            (max(1, min(limit, 100)),),
        ).fetchall()
    return [_row_to_task(row) for row in rows]
