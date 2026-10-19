import os
from pathlib import Path

from fastapi.testclient import TestClient

from backend.settings import get_settings


def _client_for_test(tmp_path: Path):
    os.environ["SQLITE_PATH"] = str(tmp_path / "teddy-test.db")
    os.environ["SKILLS_ROOT"] = str(tmp_path / "skills")
    os.environ["SKILLS_POLICY_PATH"] = str(tmp_path / "data" / "skills-policy.json")
    os.environ["MODEL_PROFILES_PATH"] = str(tmp_path / "data" / "model-profiles.json")
    os.environ.pop("NEBIUS_API_KEY", None)
    os.environ.pop("NEBIUS_MODEL", None)
    os.environ.pop("NVIDIA_API_KEY", None)
    os.environ.pop("NVIDIA_MODEL", None)
    os.environ.pop("OPENAI_COMPATIBLE_API_KEY", None)
    os.environ.pop("OPENAI_COMPATIBLE_BASE_URL", None)
    os.environ.pop("OPENAI_COMPATIBLE_MODEL", None)
    os.environ.pop("ANTHROPIC_API_KEY", None)
    os.environ["CLAUDE_FABLE_ENABLED"] = "false"
    get_settings.cache_clear()

    # Import after environment is set so module-level configuration is fresh.
    from backend.main import app
    return TestClient(app)


def test_health(tmp_path):
    with _client_for_test(tmp_path) as client:
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"


def test_create_and_read_task(tmp_path):
    with _client_for_test(tmp_path) as client:
        created = client.post(
            "/api/v1/tasks",
            json={"prompt": "Help me debug my Python API"},
        )
        assert created.status_code == 200
        body = created.json()
        assert body["status"] == "planned"
        assert body["category"] == "coding"
        assert body["plan"]
        assert body["provider"] == "local-fallback"
        assert body["skills_used"] == []

        fetched = client.get(f"/api/v1/tasks/{body['id']}")
        assert fetched.status_code == 200
        assert fetched.json()["id"] == body["id"]


def test_blank_prompt_is_rejected(tmp_path):
    with _client_for_test(tmp_path) as client:
        response = client.post("/api/v1/tasks", json={"prompt": "   "})
        assert response.status_code == 422



def test_integrations_endpoint_reports_status(tmp_path):
    with _client_for_test(tmp_path) as client:
        response = client.get("/api/v1/integrations")
        assert response.status_code == 200

        items = response.json()["integrations"]
        by_id = {item["id"]: item for item in items}
        assert {
            "local_fallback",
            "nvidia_nim",
            "openai_compatible",
            "claude_fable_5_1",
            "nex_n2_5",
            "needle_3",
            "tmux",
            "tesseract_ocr",
            "tesseract_video_editor",
            "blynk",
            "user_skills",
            "livekit_agents",
            "astra_runtime",
            "glm_v",
            "rea_mcp",
            "vulk_mcp",
            "cl4r1t4s_prompt_archive",
        }.issubset(by_id.keys())
        assert by_id["nvidia_nim"]["status"] == "needs_setup"
        assert by_id["openai_compatible"]["status"] == "needs_setup"
        assert by_id["blynk"]["status"] == "firmware_library_received_backend_adapter_pending"
        assert by_id["cl4r1t4s_prompt_archive"]["status"] == "quarantined_not_enabled"
        assert all(item.get("status") for item in items)
        assert all(
            "api_key" not in item and "token" not in item
            for item in items
        )


def test_claude_fable_route_is_opt_in_and_selective():
    from backend.model_router import _requires_claude_fable
    from backend.settings import Settings

    disabled = Settings(
        claude_fable_enabled=False,
        anthropic_api_key="test-key",
    )
    assert not _requires_claude_fable(
        "Design a multi-agent system architecture for a coding workflow.",
        disabled,
    )

    enabled = Settings(
        claude_fable_enabled=True,
        anthropic_api_key="test-key",
    )
    assert _requires_claude_fable(
        "Design the system architecture for a multi-agent coding workflow.",
        enabled,
    )
    assert not _requires_claude_fable("What is 2 + 2?", enabled)

    over_budget = Settings(
        claude_fable_enabled=True,
        anthropic_api_key="test-key",
        claude_fable_max_estimated_cost_usd=0.000001,
    )
    assert not _requires_claude_fable(
        "Design the system architecture for a multi-agent coding workflow.",
        over_budget,
    )


def test_skill_inventory_reads_metadata_and_keeps_skills_disabled(tmp_path):
    skill_dir = tmp_path / "skills" / "sample-source" / "verification-loop"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\n"
        "name: verification-loop\n"
        "description: Verify task output with tests before reporting success.\n"
        "---\n"
        "# Verification Loop\n"
        "This body is never executed by the inventory endpoint.\n",
        encoding="utf-8",
    )

    with _client_for_test(tmp_path) as client:
        response = client.get("/api/v1/skills")
        assert response.status_code == 200
        body = response.json()
        assert body["count"] == 1
        skill = body["skills"][0]
        assert skill["name"] == "verification-loop"
        assert skill["source"] == "sample-source"
        assert "text-model" in skill["compatible_runtimes"]
        assert skill["status"] == "disabled_pending_review"
        assert skill["description"].startswith("Verify task output")
        assert body["note"].startswith("Metadata only")


def test_approved_skill_context_is_selected_and_hash_pinned(tmp_path):
    import hashlib
    import json

    from backend.skill_registry import (
        SkillNotApprovedError,
        get_enabled_skill_context,
        list_skill_metadata,
    )

    skill_dir = tmp_path / "skills" / "ECC" / "verification-loop"
    skill_dir.mkdir(parents=True)
    skill_file = skill_dir / "SKILL.md"
    skill_text = (
        "---\n"
        "name: verification-loop\n"
        "description: Verify code changes with focused tests before reporting success.\n"
        "---\n"
        "# Verification Loop\n"
        "Run focused tests and report evidence.\n"
    )
    skill_file.write_text(skill_text, encoding="utf-8")
    skill_hash = hashlib.sha256(skill_file.read_bytes()).hexdigest()

    with _client_for_test(tmp_path):
        inventory = list_skill_metadata()
        assert inventory["count"] == 1
        skill = inventory["skills"][0]
        assert skill["status"] == "disabled_pending_review"

        with __import__("pytest").raises(SkillNotApprovedError):
            get_enabled_skill_context(
                "Add Python unit tests", requested_skill_ids=[skill["id"]]
            )

        policy_path = tmp_path / "data" / "skills-policy.json"
        policy_path.parent.mkdir(parents=True, exist_ok=True)
        policy_path.write_text(
            json.dumps({
                "version": 1,
                "skills": {
                    "ECC/verification-loop/SKILL.md": {
                        "enabled": True,
                        "content_sha256": skill_hash,
                        "reviewed_at": "2026-10-19T00:00:00Z",
                    }
                },
            }),
            encoding="utf-8",
        )
        selected = get_enabled_skill_context(
            "Add Python unit tests and verify the changes",
            requested_skill_ids=[skill["id"]],
        )
        assert len(selected) == 1
        assert selected[0]["name"] == "verification-loop"
        assert "Run focused tests" in selected[0]["content"]

        skill_file.write_text(skill_text + "\nChanged after review.\n", encoding="utf-8")
        with __import__("pytest").raises(SkillNotApprovedError):
            get_enabled_skill_context(
                "Add Python unit tests", requested_skill_ids=[skill["id"]]
            )


def test_explicit_unapproved_skill_is_rejected_by_api(tmp_path):
    skill_dir = tmp_path / "skills" / "ECC" / "unsafe-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: unsafe-skill\ndescription: Test-only skill.\n---\n"
        "This file is just test guidance.\n",
        encoding="utf-8",
    )
    with _client_for_test(tmp_path) as client:
        inventory = client.get("/api/v1/skills").json()
        skill_id = inventory["skills"][0]["id"]
        response = client.post(
            "/api/v1/tasks",
            json={
                "prompt": "Add unit tests to my Python project",
                "skill_ids": [skill_id],
            },
        )
        assert response.status_code == 422
        assert "not approved" in response.json()["detail"].lower()


def test_model_routes_report_only_configured_providers(tmp_path):
    with _client_for_test(tmp_path) as client:
        response = client.get("/api/v1/models")
        assert response.status_code == 200
        body = response.json()
        assert body["default_route"] == "auto"
        routes = {item["id"]: item for item in body["routes"]}
        assert routes["auto"]["available"] is True
        assert routes["nebius"]["available"] is False
        assert routes["nvidia_nim"]["available"] is False
        assert routes["openai_compatible"]["available"] is False
        assert routes["claude_fable"]["available"] is False


def test_unconfigured_explicit_model_route_returns_conflict(tmp_path):
    with _client_for_test(tmp_path) as client:
        response = client.post(
            "/api/v1/tasks",
            json={
                "prompt": "Explain a Python unit-test strategy",
                "model_route": "nebius",
            },
        )
        assert response.status_code == 409
        assert "not configured" in response.json()["detail"].lower()


def test_unconfigured_nvidia_route_returns_conflict(tmp_path):
    with _client_for_test(tmp_path) as client:
        response = client.post(
            "/api/v1/tasks",
            json={
                "prompt": "Summarize this task",
                "model_route": "nvidia_nim",
            },
        )
        assert response.status_code == 409
        assert "nvidia" in response.json()["detail"].lower()


def test_unconfigured_custom_model_route_returns_conflict(tmp_path):
    with _client_for_test(tmp_path) as client:
        response = client.post(
            "/api/v1/tasks",
            json={
                "prompt": "Summarize this task",
                "model_route": "openai_compatible",
            },
        )
        assert response.status_code == 409
        assert "openai-compatible" in response.json()["detail"].lower()


def test_root_serves_command_centre_ui(tmp_path):
    with _client_for_test(tmp_path) as client:
        response = client.get("/")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        assert "TEDDY" in response.text
        assert 'id="task-form"' in response.text

        css = client.get("/static/app.css")
        script = client.get("/static/app.js")
        assert css.status_code == 200
        assert "text/css" in css.headers["content-type"]
        assert script.status_code == 200
        assert "application/javascript" in script.headers["content-type"] or "text/javascript" in script.headers["content-type"]


def test_api_root_remains_available(tmp_path):
    with _client_for_test(tmp_path) as client:
        response = client.get("/api")
        assert response.status_code == 200
        assert response.json()["ui"] == "/"

 
def test_new_tasks_have_explicit_plan_only_lifecycle(tmp_path):
    with _client_for_test(tmp_path) as client:
        response = client.post("/api/v1/tasks", json={"prompt": "Help me debug my Python API"})
        assert response.status_code == 200
        body = response.json()
        assert body["execution_mode"] == "plan_only"
        assert body["agent_name"] is None
        assert body["execution_log"]
        fetched = client.get(f"/api/v1/tasks/{body['id']}").json()
        assert fetched["execution_mode"] == "plan_only"
        assert fetched["execution_log"]


def test_agent_run_is_refused_when_codex_is_not_installed(tmp_path, monkeypatch):
    import backend.main as main_module
    monkeypatch.setattr(main_module, "agent_available", lambda: False)
    with _client_for_test(tmp_path) as client:
        created = client.post("/api/v1/tasks", json={"prompt": "Build a Python calculator with unit tests"})
        assert created.status_code == 200
        task_id = created.json()["id"]
        run = client.post(f"/api/v1/tasks/{task_id}/run")
        assert run.status_code == 409
        assert "Codex CLI is not installed" in run.json()["detail"]
        assert client.get(f"/api/v1/tasks/{task_id}").json()["status"] == "planned"


def test_non_coding_tasks_cannot_be_sent_to_coding_worker(tmp_path, monkeypatch):
    import backend.main as main_module
    monkeypatch.setattr(main_module, "agent_available", lambda: True)
    with _client_for_test(tmp_path) as client:
        created = client.post("/api/v1/tasks", json={"prompt": "Research recent discoveries in astronomy"})
        assert created.status_code == 200
        response = client.post(f"/api/v1/tasks/{created.json()['id']}/run")
        assert response.status_code == 409
        assert "Only coding tasks" in response.json()["detail"]


def test_task_lifecycle_fields_can_be_updated_and_read(tmp_path):
    from backend.database import get_task, init_db, insert_task, update_task, utc_now
    os.environ["SQLITE_PATH"] = str(tmp_path / "task-lifecycle.db")
    get_settings.cache_clear()
    init_db()
    insert_task({
        "id": "lifecycle-test", "session_id": "session-test",
        "prompt": "Build a Python calculator", "status": "planned",
        "category": "coding", "provider": "local-fallback", "model": None,
        "risk": "medium", "approval_required": False, "plan": ["Implement", "Test"],
        "created_at": utc_now(), "skills_used": [], "execution_log": ["Plan created"],
        "execution_mode": "plan_only",
    })
    assert update_task("lifecycle-test", status="running", execution_mode="agent",
                       agent_name="OpenAI Codex CLI", execution_log=["Queued", "Running"],
                       updated_at=utc_now())
    saved = get_task("lifecycle-test")
    assert saved["status"] == "running"
    assert saved["execution_mode"] == "agent"
    assert saved["agent_name"] == "OpenAI Codex CLI"
    assert saved["execution_log"] == ["Queued", "Running"]

 
def test_coding_task_is_dispatched_to_worker_when_available(tmp_path, monkeypatch):
    import backend.main as main_module
    from backend.database import update_task, utc_now

    monkeypatch.setattr(main_module, "agent_available", lambda: True)

    async def fake_worker(task_id):
        update_task(task_id, status="completed", result_text="Mock worker complete",
                    execution_log=["Mock worker completed"], updated_at=utc_now())

    monkeypatch.setattr(main_module, "run_codex_task", fake_worker)
    with _client_for_test(tmp_path) as client:
        created = client.post("/api/v1/tasks", json={"prompt": "Build a Python calculator with tests"})
        assert created.status_code == 200
        task_id = created.json()["id"]
        started = client.post(f"/api/v1/tasks/{task_id}/run")
        assert started.status_code == 200
        assert started.json()["execution_mode"] == "agent"
        saved = client.get(f"/api/v1/tasks/{task_id}").json()
        assert saved["status"] == "completed"
        assert saved["result_text"] == "Mock worker complete"


def test_interrupted_agent_tasks_are_recovered_on_restart(tmp_path):
    from backend.database import fail_interrupted_agent_tasks, get_task, init_db, insert_task, update_task, utc_now
    os.environ["SQLITE_PATH"] = str(tmp_path / "recover.db")
    get_settings.cache_clear()
    init_db()
    insert_task({
        "id": "recover-test", "session_id": "session-test",
        "prompt": "Build a Python helper", "status": "running", "category": "coding",
        "provider": "local-fallback", "model": None, "risk": "medium",
        "approval_required": False, "plan": ["Implement"], "created_at": utc_now(),
        "skills_used": [], "execution_log": ["Worker started"],
        "execution_mode": "agent", "agent_name": "OpenAI Codex CLI",
    })
    assert fail_interrupted_agent_tasks() == 1
    saved = get_task("recover-test")
    assert saved["status"] == "failed"
    assert "restarted" in saved["result_text"].lower()
    assert any("restarted" in line.lower() for line in saved["execution_log"])
