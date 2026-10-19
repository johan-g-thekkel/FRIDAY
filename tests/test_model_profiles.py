import json
from types import SimpleNamespace

from fastapi.testclient import TestClient

from backend.settings import get_settings


def _client(tmp_path, monkeypatch):
    policy_dir = tmp_path / "data"
    policy_dir.mkdir(parents=True, exist_ok=True)
    profile_path = policy_dir / "model-profiles.json"
    monkeypatch.setenv("MODEL_PROFILES_PATH", str(profile_path))
    monkeypatch.setenv("SQLITE_PATH", str(policy_dir / "test.db"))
    monkeypatch.setenv("SKILLS_ROOT", str(tmp_path / "skills"))
    monkeypatch.setenv("SKILLS_POLICY_PATH", str(policy_dir / "skills-policy.json"))
    for key in (
        "NEBIUS_API_KEY",
        "NEBIUS_MODEL",
        "NVIDIA_API_KEY",
        "NVIDIA_MODEL",
        "OPENAI_COMPATIBLE_API_KEY",
        "OPENAI_COMPATIBLE_BASE_URL",
        "OPENAI_COMPATIBLE_MODEL",
        "ANTHROPIC_API_KEY",
    ):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("CLAUDE_FABLE_ENABLED", "false")
    get_settings.cache_clear()

    from backend.main import app
    return TestClient(app), profile_path


def _profile():
    return [{
        "id": "nex_n2_5",
        "name": "Nex-N2.5",
        "base_url": "https://models.example.test/v1",
        "model": "nex-n2.5-exact",
        "api_key_env": "TEDDY_TEST_NEX_KEY",
        "priority": 25,
        "capabilities": ["text", "reasoning", "coding"],
        "enabled": True,
    }]


def test_named_profile_appears_without_exposing_credentials(tmp_path, monkeypatch):
    monkeypatch.setenv("TEDDY_TEST_NEX_KEY", "do-not-return-this")
    client, profile_path = _client(tmp_path, monkeypatch)
    profile_path.write_text(json.dumps(_profile()), encoding="utf-8")
    get_settings.cache_clear()

    with client:
        models = client.get("/api/v1/models")
        assert models.status_code == 200
        profile = next(item for item in models.json()["routes"] if item["id"] == "nex_n2_5")
        assert profile["available"] is True
        assert profile["model"] == "nex-n2.5-exact"
        assert "do-not-return-this" not in models.text

        integrations = client.get("/api/v1/integrations").json()["integrations"]
        matching = next(item for item in integrations if item["id"] == "model-profile-nex_n2_5")
        assert matching["status"] == "configured_not_tested"
        assert "do-not-return-this" not in json.dumps(integrations)


def test_named_profile_missing_api_key_is_not_selectable(tmp_path, monkeypatch):
    monkeypatch.delenv("TEDDY_TEST_NEX_KEY", raising=False)
    client, profile_path = _client(tmp_path, monkeypatch)
    profile_path.write_text(json.dumps(_profile()), encoding="utf-8")
    get_settings.cache_clear()

    with client:
        model_list = client.get("/api/v1/models").json()["routes"]
        profile = next(item for item in model_list if item["id"] == "nex_n2_5")
        assert profile["available"] is False
        assert profile["status"] == "needs_api_key"

        response = client.post(
            "/api/v1/tasks",
            json={"prompt": "Create a coding plan", "model_route": "nex_n2_5"},
        )
        assert response.status_code == 409
        assert "TEDDY_TEST_NEX_KEY" in response.json()["detail"]


def test_named_profile_routes_task_through_openai_compatible_adapter(tmp_path, monkeypatch):
    monkeypatch.setenv("TEDDY_TEST_NEX_KEY", "fake-test-key")
    client, profile_path = _client(tmp_path, monkeypatch)
    profile_path.write_text(json.dumps(_profile()), encoding="utf-8")
    get_settings.cache_clear()

    class FakeCompletions:
        async def create(self, **kwargs):
            assert kwargs["model"] == "nex-n2.5-exact"
            assert kwargs["messages"][-1]["content"] == "Create a coding plan"
            data = {
                "category": "coding",
                "risk": "low",
                "approval_required": False,
                "plan": ["Implement the change", "Run unit tests"],
            }
            return SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(content=json.dumps(data))
                    )
                ]
            )

    class FakeClient:
        def __init__(self, *, base_url, api_key, timeout, max_retries):
            assert base_url == "https://models.example.test/v1"
            assert api_key == "fake-test-key"
            self.chat = SimpleNamespace(completions=FakeCompletions())

        async def close(self):
            return None

    monkeypatch.setattr("backend.model_router.AsyncOpenAI", FakeClient)

    with client:
        response = client.post(
            "/api/v1/tasks",
            json={"prompt": "Create a coding plan", "model_route": "nex_n2_5"},
        )
        assert response.status_code == 200
        task = response.json()
        assert task["provider"] == "openai-compatible-profile:nex_n2_5"
        assert task["model"] == "nex-n2.5-exact"
        assert task["skills_used"] == []


def test_model_profile_rejects_insecure_external_http_endpoint(tmp_path, monkeypatch):
    monkeypatch.setenv("TEDDY_TEST_NEX_KEY", "fake-test-key")
    client, profile_path = _client(tmp_path, monkeypatch)
    profile = _profile()
    profile[0]["base_url"] = "http://public-model.example.test/v1"
    profile_path.write_text(json.dumps(profile), encoding="utf-8")
    get_settings.cache_clear()

    with client:
        routes = client.get("/api/v1/models").json()["routes"]
        assert all(item["id"] != "nex_n2_5" for item in routes)
