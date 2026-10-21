import asyncio

import pytest
from fastapi import HTTPException

from backend import local_ai


class FakeResponse:
    def __init__(self, body, status=200):
        self._body = body
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            import httpx
            request = httpx.Request("GET", "http://127.0.0.1:11434/api/tags")
            response = httpx.Response(self.status_code, request=request)
            raise httpx.HTTPStatusError("failed", request=request, response=response)

    def json(self):
        return self._body


class FakeClient:
    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def get(self, path):
        return FakeResponse({"models": [{"name": "qwen2.5:3b", "size": 1234, "details": {"family": "qwen2", "parameter_size": "3B", "quantization_level": "Q4_K_M"}}]})

    async def post(self, path, json):
        assert path == "/api/chat"
        assert json["stream"] is False
        assert json["messages"][0]["role"] == "system"
        return FakeResponse({"message": {"content": "Hello from the local model."}, "done": True, "eval_count": 8})


def test_local_ai_status_lists_installed_models(monkeypatch):
    monkeypatch.setattr(local_ai, "_base_url", lambda: "http://127.0.0.1:11434")
    monkeypatch.setattr(local_ai.httpx, "AsyncClient", FakeClient)
    result = asyncio.run(local_ai.local_ai_status())
    assert result["reachable"] is True
    assert result["mode"] == "local-only"
    assert result["models"][0]["name"] == "qwen2.5:3b"


def test_local_chat_uses_only_selected_local_model(monkeypatch):
    monkeypatch.setattr(local_ai, "_base_url", lambda: "http://127.0.0.1:11434")
    monkeypatch.setattr(local_ai.httpx, "AsyncClient", FakeClient)
    request = local_ai.LocalChatRequest(model="qwen2.5:3b", messages=[{"role": "user", "content": "Hello"}])
    result = asyncio.run(local_ai.local_ai_chat(request))
    assert result["provider"] == "ollama-local"
    assert result["mode"] == "local-only"
    assert result["message"] == "Hello from the local model."


def test_local_chat_rejects_model_not_installed(monkeypatch):
    monkeypatch.setattr(local_ai, "_base_url", lambda: "http://127.0.0.1:11434")
    monkeypatch.setattr(local_ai.httpx, "AsyncClient", FakeClient)
    request = local_ai.LocalChatRequest(model="not-installed", messages=[{"role": "user", "content": "Hello"}])
    with pytest.raises(HTTPException) as error:
        asyncio.run(local_ai.local_ai_chat(request))
    assert error.value.status_code == 409


def test_local_url_is_loopback_only(monkeypatch):
    from backend.settings import Settings
    monkeypatch.setattr(local_ai, "get_settings", lambda: Settings(ollama_base_url="http://example.com:11434"))
    with pytest.raises(HTTPException) as error:
        local_ai._base_url()
    assert error.value.status_code == 503
