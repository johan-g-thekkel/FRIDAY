import os
from pathlib import Path

from fastapi.testclient import TestClient

from backend.settings import get_settings


def _client_for_test(tmp_path: Path):
    os.environ["SQLITE_PATH"] = str(tmp_path / "teddy-test.db")
    os.environ.pop("NEBIUS_API_KEY", None)
    os.environ.pop("NEBIUS_MODEL", None)
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

        fetched = client.get(f"/api/v1/tasks/{body['id']}")
        assert fetched.status_code == 200
        assert fetched.json()["id"] == body["id"]


def test_blank_prompt_is_rejected(tmp_path):
    with _client_for_test(tmp_path) as client:
        response = client.post("/api/v1/tasks", json={"prompt": "   "})
        assert response.status_code == 422
