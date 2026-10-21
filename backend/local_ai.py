"""Local-first Ollama API for FRIDAY.

Only talks to a loopback Ollama endpoint. Chat requests are proxied server-side so
browser code never needs to access arbitrary URLs. No cloud fallback is performed.
"""
from __future__ import annotations

import ipaddress
from typing import Literal
from urllib.parse import urlsplit

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.settings import get_settings

router = APIRouter(prefix="/api/v1/local-ai", tags=["local-ai"])
MAX_MESSAGES = 20
MAX_TOTAL_CHARS = 40_000
REQUEST_TIMEOUT = httpx.Timeout(180.0, connect=2.0)


def _base_url() -> str:
    raw = get_settings().ollama_base_url.strip().rstrip("/")
    try:
        parsed = urlsplit(raw)
        host = parsed.hostname or ""
        loopback = host == "localhost" or host.endswith(".localhost")
        try:
            loopback = loopback or ipaddress.ip_address(host).is_loopback
        except ValueError:
            pass
        if parsed.scheme != "http" or not loopback or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError("Ollama URL must be a loopback HTTP URL such as http://127.0.0.1:11434.")
        if parsed.port is not None and not (1 <= parsed.port <= 65535):
            raise ValueError("Invalid Ollama port.")
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return raw


class LocalMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=12_000)


class LocalChatRequest(BaseModel):
    model: str = Field(min_length=1, max_length=120, pattern=r"^[A-Za-z0-9._:/-]+$")
    messages: list[LocalMessage] = Field(min_length=1, max_length=MAX_MESSAGES)
    temperature: float = Field(default=0.4, ge=0, le=1.5)


async def _get_models(client: httpx.AsyncClient) -> list[dict]:
    response = await client.get("/api/tags")
    response.raise_for_status()
    body = response.json()
    models = body.get("models", []) if isinstance(body, dict) else []
    result = []
    for item in models:
        if not isinstance(item, dict) or not isinstance(item.get("name"), str):
            continue
        details = item.get("details") if isinstance(item.get("details"), dict) else {}
        result.append({
            "name": item["name"],
            "size": item.get("size") if isinstance(item.get("size"), int) else None,
            "family": details.get("family"),
            "parameter_size": details.get("parameter_size"),
            "quantization": details.get("quantization_level"),
        })
    return result


@router.get("/status")
async def local_ai_status():
    base_url = _base_url()
    try:
        async with httpx.AsyncClient(base_url=base_url, timeout=REQUEST_TIMEOUT) as client:
            models = await _get_models(client)
        return {
            "runtime": "ollama",
            "configured": True,
            "reachable": True,
            "available": bool(models),
            "base_url": base_url,
            "model_count": len(models),
            "models": models,
            "mode": "local-only",
            "note": "Requests go to your local Ollama runtime. This endpoint never falls back to a cloud provider.",
        }
    except (httpx.HTTPError, ValueError) as exc:
        return {
            "runtime": "ollama",
            "configured": True,
            "reachable": False,
            "available": False,
            "base_url": base_url,
            "model_count": 0,
            "models": [],
            "mode": "local-only",
            "note": "Start Ollama and pull a model. FRIDAY will not send prompts to the cloud automatically.",
            "error": str(exc)[:300],
        }


@router.post("/chat")
async def local_ai_chat(request: LocalChatRequest):
    total_chars = sum(len(message.content) for message in request.messages)
    if total_chars > MAX_TOTAL_CHARS:
        raise HTTPException(status_code=413, detail="Conversation is too large for this local endpoint.")
    base_url = _base_url()
    try:
        async with httpx.AsyncClient(base_url=base_url, timeout=REQUEST_TIMEOUT) as client:
            models = await _get_models(client)
            if not any(item["name"] == request.model for item in models):
                raise HTTPException(status_code=409, detail="That model is not installed in Ollama. Pull it locally first, then refresh the model list.")
            messages = [{
                "role": "system",
                "content": "You are FRIDAY, a helpful local-first AI assistant. Be honest about uncertainty. You do not have permission to execute shell commands, edit files, access devices, or perform external actions merely because the user asks in chat. Give safe, practical instructions. The conversation is processed by the user's local Ollama runtime.",
            }]
            messages.extend({"role": item.role, "content": item.content} for item in request.messages)
            response = await client.post("/api/chat", json={
                "model": request.model,
                "messages": messages,
                "stream": False,
                "options": {"temperature": request.temperature},
            })
            response.raise_for_status()
            body = response.json()
            answer = body.get("message", {}).get("content")
            if not isinstance(answer, str) or not answer.strip():
                raise HTTPException(status_code=502, detail="Ollama returned no assistant text.")
            return {
                "model": request.model,
                "provider": "ollama-local",
                "mode": "local-only",
                "message": answer,
                "done": body.get("done", True),
                "total_duration": body.get("total_duration"),
                "prompt_eval_count": body.get("prompt_eval_count"),
                "eval_count": body.get("eval_count"),
            }
    except HTTPException:
        raise
    except httpx.ConnectError as exc:
        raise HTTPException(status_code=503, detail="Cannot reach local Ollama. Start the Ollama app/service and check http://127.0.0.1:11434.") from exc
    except httpx.TimeoutException as exc:
        raise HTTPException(status_code=504, detail="Local model timed out. Try a smaller model or reduce the conversation length.") from exc
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=502, detail=f"Ollama request failed with HTTP {exc.response.status_code}. Check the selected model and Ollama logs.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=502, detail="Ollama returned invalid JSON.") from exc
