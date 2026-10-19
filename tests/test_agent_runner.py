import json
import os

from backend.agent_runner import _restricted_child_environment, _safe_event_summary


def test_worker_child_environment_excludes_provider_secrets(monkeypatch):
    monkeypatch.setenv("PATH", "/usr/bin")
    monkeypatch.setenv("HOME", "/tmp/teddy-home")
    monkeypatch.setenv("NEBIUS_API_KEY", "do-not-pass-this")
    monkeypatch.setenv("NVIDIA_API_KEY", "do-not-pass-this-either")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "another-secret")
    monkeypatch.setenv("OPENAI_COMPATIBLE_API_KEY", "custom-secret")
    monkeypatch.setenv("OPENAI_API_KEY", "also-not-forwarded")
    child = _restricted_child_environment()
    assert child["PATH"] == "/usr/bin"
    assert child["HOME"] == "/tmp/teddy-home"
    assert "NEBIUS_API_KEY" not in child
    assert "NVIDIA_API_KEY" not in child
    assert "ANTHROPIC_API_KEY" not in child
    assert "OPENAI_COMPATIBLE_API_KEY" not in child
    assert "OPENAI_API_KEY" not in child


def test_codex_event_log_does_not_store_command_arguments_or_secrets():
    line = json.dumps({
        "type": "item.started",
        "item": {"type": "command_execution", "command": "cat .env"},
        "debug": {"api_key": "fake-secret"},
    })
    summary = _safe_event_summary(line)
    assert summary == "Codex event: item.started (command_execution)."
    assert ".env" not in summary
    assert "fake-secret" not in summary


def test_worktree_inspection_reports_tracked_and_untracked_changes(tmp_path, monkeypatch):
    import subprocess

    from backend import agent_runner
    from backend.database import insert_task, update_task, utc_now

    repo = tmp_path / "source-repo"
    repo.mkdir()
    def git(*args):
        subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)
    git("init")
    git("config", "user.name", "TEDDY Test")
    git("config", "user.email", "teddy-tests@example.invalid")
    (repo / "example.py").write_text("value = 1\n", encoding="utf-8")
    git("add", "example.py")
    git("commit", "-m", "initial")
    worktree = repo / ".teddy-worktrees" / "inspect-test"
    worktree.parent.mkdir()
    git("worktree", "add", "--detach", str(worktree), "HEAD")
    (worktree / "example.py").write_text("value = 2\n", encoding="utf-8")
    (worktree / "added.py").write_text("def answer():\n    return 42\n", encoding="utf-8")
    monkeypatch.setattr(agent_runner, "REPO_ROOT", repo)

    from backend.settings import get_settings
    os.environ["SQLITE_PATH"] = str(tmp_path / "inspect-test.db")
    get_settings.cache_clear()
    from backend.database import init_db
    init_db()
    insert_task({
        "id": "inspect-test", "session_id": "s", "prompt": "Change a file",
        "status": "completed", "category": "coding", "provider": "test",
        "model": None, "risk": "low", "approval_required": False,
        "plan": ["Change it"], "created_at": utc_now(), "execution_mode": "agent",
        "agent_name": "OpenAI Codex CLI", "workspace_path": str(worktree),
        "execution_log": [],
    })
    changes = agent_runner.inspect_codex_worktree_changes("inspect-test")
    assert any("example.py" in line for line in changes["files"])
    assert any("added.py" in line for line in changes["files"])
    assert "value = 2" in changes["diff"]
    assert "return 42" in changes["diff"]
    assert changes["truncated"] is False


