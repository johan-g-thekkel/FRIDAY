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


def test_root_serves_voice_first_ui(tmp_path):
    with _client_for_test(tmp_path) as client:
        response = client.get("/")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        assert "FRIDAY" in response.text
        assert "Activate FRIDAY" in response.text
        assert 'id="activate-button"' in response.text

        console = client.get("/console")
        assert console.status_code == 200
        assert "Command centre" in console.text
        assert 'id="task-form"' in console.text

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

 
 
def test_requested_skill_ids_are_persisted_with_task(tmp_path, monkeypatch):
    import backend.main as main_module

    async def fake_plan(prompt, requested_skill_ids=None, requested_route="auto", additional_context=None):
        return {
            "category": "coding", "provider": "test-provider", "model": "test-model",
            "risk": "medium", "approval_required": False, "plan": ["Implement"],
            "skills_used": ["verification-loop"] if requested_skill_ids else [],
        }

    monkeypatch.setattr(main_module, "create_plan", fake_plan)
    requested_id = "0123456789abcdef"
    with _client_for_test(tmp_path) as client:
        response = client.post(
            "/api/v1/tasks",
            json={"prompt": "Add code tests", "skill_ids": [requested_id]},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["skill_ids"] == [requested_id]
        fetched = client.get(f"/api/v1/tasks/{body['id']}").json()
        assert fetched["skill_ids"] == [requested_id]


def test_bot_crud_and_task_attachment(tmp_path, monkeypatch):
    import backend.main as main_module

    contexts = []
    async def fake_plan(prompt, requested_skill_ids=None, requested_route="auto", additional_context=None):
        contexts.append(additional_context)
        return {
            "category": "coding", "provider": "local-fallback", "model": None,
            "risk": "medium", "approval_required": False,
            "plan": ["Inspect code", "Implement and test"],
            "skills_used": [],
        }

    monkeypatch.setattr(main_module, "create_plan", fake_plan)
    with _client_for_test(tmp_path) as client:
        created = client.post("/api/v1/bots", json={
            "name": "Python Helper",
            "description": "Works on small Python utilities.",
            "instructions": "Prefer clear Python code and focused unit tests.",
            "memory": "Use beginner-friendly explanations.",
            "default_model_route": "auto",
            "runtime": "plan_only",
        })
        assert created.status_code == 200
        bot = created.json()
        assert bot["enabled"] is True
        assert bot["runtime"] == "plan_only"
        assert client.get("/api/v1/bots").json()[0]["id"] == bot["id"]

        task = client.post("/api/v1/tasks", json={
            "prompt": "Build a Python calculator",
            "bot_id": bot["id"],
        })
        assert task.status_code == 200
        assert task.json()["bot_id"] == bot["id"]
        assert task.json()["bot_name"] == "Python Helper"
        assert client.get(f"/api/v1/tasks/{task.json()['id']}").json()["bot_runtime"] == "plan_only"
        assert contexts and '"name": "Python Helper"' in contexts[-1]

        changed = client.patch(f"/api/v1/bots/{bot['id']}", json={"runtime": "codex_cli", "enabled": False})
        assert changed.status_code == 200
        assert changed.json()["runtime"] == "codex_cli"
        assert changed.json()["enabled"] is False

        disabled_task = client.post(
            "/api/v1/tasks",
            json={"prompt": "Build a Python calculator", "bot_id": bot["id"]},
        )
        assert disabled_task.status_code == 409
        assert "disabled" in disabled_task.json()["detail"].lower()

        deleted = client.delete(f"/api/v1/bots/{bot['id']}")
        assert deleted.status_code == 200
        assert client.get("/api/v1/bots").json() == []


def test_skill_archive_upload_imports_only_canonical_metadata(tmp_path):
    import io
    import zipfile

    payload = io.BytesIO()
    with zipfile.ZipFile(payload, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "ECC-main/skills/demo-review-loop/SKILL.md",
            "---\nname: demo-review-loop\ndescription: Test uploaded skill.\n---\nRun focused tests.\n",
        )
        archive.writestr(
            "ECC-main/skills/demo-review-loop/install.sh",
            "#!/bin/sh\necho must-not-be-copied-or-executed\n",
        )
        archive.writestr(
            "ECC-main/skills/../../outside/SKILL.md",
            "---\nname: outside\ndescription: traversal\n---\n",
        )

    with _client_for_test(tmp_path) as client:
        response = client.post(
            "/api/v1/skills/import",
            files={"file": ("ECC-main.zip", payload.getvalue(), "application/zip")},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["imported"] == 1
        assert body["inventory_count"] == 1
        inventory = client.get("/api/v1/skills").json()
        assert inventory["skills"][0]["name"] == "demo-review-loop"
        assert inventory["skills"][0]["status"] == "disabled_pending_review"
        imported_root = tmp_path / "skills" / "ECC"
        assert (imported_root / "demo-review-loop" / "SKILL.md").is_file()
        assert not (imported_root / "demo-review-loop" / "install.sh").exists()


def test_skill_archive_upload_rejects_unknown_names_and_non_zip(tmp_path):
    with _client_for_test(tmp_path) as client:
        unsupported = client.post(
            "/api/v1/skills/import",
            files={"file": ("random.zip", b"fake-zip", "application/zip")},
        )
        assert unsupported.status_code == 422
        non_zip = client.post(
            "/api/v1/skills/import",
            files={"file": ("ECC-main.zip", b"not really zip", "application/zip")},
        )
        assert non_zip.status_code == 422


def test_ui_skill_review_requires_exact_confirmation_and_pins_hash(tmp_path):
    import hashlib

    skill_path = tmp_path / "skills" / "ECC" / "verification-loop" / "SKILL.md"
    skill_path.parent.mkdir(parents=True)
    skill_content = (
        "---\nname: verification-loop\ndescription: Verify changes with tests.\n---\n"
        "# Verification Loop\nRun focused tests and report evidence.\n"
    )
    skill_path.write_text(skill_content, encoding="utf-8")
    skill_id = hashlib.sha256("ECC/verification-loop/SKILL.md".encode()).hexdigest()[:16]
    full_hash = hashlib.sha256(skill_content.encode()).hexdigest()

    with _client_for_test(tmp_path) as client:
        detail = client.get(f"/api/v1/skills/{skill_id}")
        assert detail.status_code == 200
        assert detail.json()["content_sha256"] == full_hash
        assert "Run focused tests" in detail.json()["content"]

        rejected = client.post(f"/api/v1/skills/{skill_id}/enable", json={
            "content_sha256": full_hash, "confirmation": "ENABLE wrong-id",
        })
        assert rejected.status_code == 422

        enabled = client.post(f"/api/v1/skills/{skill_id}/enable", json={
            "content_sha256": full_hash, "confirmation": f"ENABLE {skill_id}",
        })
        assert enabled.status_code == 200
        assert enabled.json()["status"] == "enabled_reviewed"
        assert client.get("/api/v1/skills").json()["skills"][0]["status"] == "enabled_reviewed"

        changed_content = skill_content + "\nAn unreviewed edit.\n"
        skill_path.write_text(changed_content, encoding="utf-8")
        assert client.get("/api/v1/skills").json()["skills"][0]["status"] == "changed_since_review"
        stale = client.post(f"/api/v1/skills/{skill_id}/enable", json={
            "content_sha256": full_hash, "confirmation": f"ENABLE {skill_id}",
        })
        assert stale.status_code == 409


def test_ui_can_disable_a_reviewed_skill(tmp_path):
    import hashlib
    import json

    skill_path = tmp_path / "skills" / "ECC" / "sample-skill" / "SKILL.md"
    skill_path.parent.mkdir(parents=True)
    content = "---\nname: sample-skill\ndescription: A safe test skill.\n---\nUse relevant hints.\n"
    skill_path.write_text(content, encoding="utf-8")
    skill_id = hashlib.sha256("ECC/sample-skill/SKILL.md".encode()).hexdigest()[:16]
    policy_path = tmp_path / "data" / "skills-policy.json"
    policy_path.parent.mkdir()
    policy_path.write_text(json.dumps({"version": 1, "skills": {
        "ECC/sample-skill/SKILL.md": {
            "enabled": True, "content_sha256": hashlib.sha256(content.encode()).hexdigest()
        }
    }}), encoding="utf-8")
    with _client_for_test(tmp_path) as client:
        response = client.post(f"/api/v1/skills/{skill_id}/disable")
        assert response.status_code == 200
        assert response.json()["status"] == "disabled_pending_review"
        assert client.get("/api/v1/skills").json()["skills"][0]["status"] == "disabled_pending_review"

def test_plan_only_tasks_cannot_access_agent_changes_endpoint(tmp_path):
    with _client_for_test(tmp_path) as client:
        created = client.post("/api/v1/tasks", json={"prompt": "Help me debug my Python API"})
        response = client.get(f"/api/v1/tasks/{created.json()['id']}/changes")
        assert response.status_code == 409
        assert "no agent worktree" in response.json()["detail"].lower()




def test_autonomy_policy_endpoint_exposes_profiles_and_safeguards(tmp_path):
    with _client_for_test(tmp_path) as client:
        response = client.get("/api/v1/policy")
        assert response.status_code == 200
        policy = response.json()
        assert policy["coordination"]["mode"] == "dynamic_specialist_teams"
        assert policy["coordination"]["disagreement_resolution"] == "competitive_execution"
        assert {item["id"] for item in policy["profiles"]} == {
            "supervised", "builder", "researcher", "trusted_automation"
        }
        assert policy["safeguards"]["high_risk_actions_require_approval"] is True
        assert policy["safeguards"]["untrusted_skills_execute_automatically"] is False
        assert policy["implementation_status"]["hermes_agent"] == "inventory_only_pending_tested_adapter"

def test_root_serves_voice_first_home_and_console(tmp_path):
    with _client_for_test(tmp_path) as client:
        home = client.get("/")
        assert home.status_code == 200
        assert "Activate FRIDAY" in home.text
        assert 'id="activate-button"' in home.text

        console = client.get("/console")
        assert console.status_code == 200
        assert "Command centre" in console.text


def test_local_ollama_routes_reflect_installed_models(tmp_path, monkeypatch):
    from backend import main

    async def fake_local_models():
        return ["qwen2.5:1.5b", "llama3.2:1b"]

    monkeypatch.setattr(main, "list_ollama_models", fake_local_models)
    with _client_for_test(tmp_path) as client:
        response = client.get("/api/v1/models")
        assert response.status_code == 200
        routes = {item["id"]: item for item in response.json()["routes"]}
        assert routes["ollama"]["available"] is True
        assert routes["ollama"]["model"] == "qwen2.5:1.5b"
        assert routes["ollama_qwen2_5_1_5b"]["model"] == "qwen2.5:1.5b"
        assert routes["ollama_llama3_2_1b"]["model"] == "llama3.2:1b"


def test_voice_status_exposes_local_model_and_speech_readiness(tmp_path, monkeypatch):
    from backend import main

    async def fake_local_models():
        return ["qwen2.5:1.5b"]

    monkeypatch.setattr(main, "list_ollama_models", fake_local_models)
    with _client_for_test(tmp_path) as client:
        response = client.get("/api/v1/voice/status")
        assert response.status_code == 200
        body = response.json()
        assert body["ollama_reachable"] is True
        assert body["models"] == ["qwen2.5:1.5b"]
        assert "transcription_ready" in body

def test_voice_action_recognizer_only_accepts_explicit_allowlisted_intents():
    from backend.local_actions import resolve_voice_action

    assert resolve_voice_action("FRIDAY, open Notepad") == {
        "kind": "open_app",
        "target": "notepad",
    }
    assert resolve_voice_action("please open file explorer") == {
        "kind": "open_app",
        "target": "file_explorer",
    }
    assert resolve_voice_action("open https://example.com") == {
        "kind": "open_url",
        "target": "https://example.com",
    }
    assert resolve_voice_action("run powershell and delete files") is None
    assert resolve_voice_action("open notepad and type my password") is None


def test_voice_chat_routes_allowlisted_action_without_calling_a_model(tmp_path, monkeypatch):
    from backend import main

    expected = {
        "answer": "Opened notepad.",
        "provider": "local-desktop-action",
        "model": None,
        "action": {"status": "completed", "kind": "open_app", "target": "notepad"},
    }
    monkeypatch.setattr(main, "handle_voice_action", lambda prompt: expected if prompt == "open notepad" else None)

    with _client_for_test(tmp_path) as client:
        response = client.post(
            "/api/v1/chat",
            json={"messages": [{"role": "user", "content": "open notepad"}], "model_route": "auto"},
        )
        assert response.status_code == 200
        assert response.json() == expected

def test_auto_voice_chat_never_falls_back_to_cloud(tmp_path, monkeypatch):
    from backend import chat_service

    async def no_local_models():
        return []

    monkeypatch.setattr(chat_service, "list_ollama_models", no_local_models)
    with _client_for_test(tmp_path) as client:
        response = client.post(
            "/api/v1/chat",
            json={"messages": [{"role": "user", "content": "Please explain gravity."}], "model_route": "auto"},
        )
        assert response.status_code == 503
        assert "local-only" in response.json()["detail"]
