import json

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
