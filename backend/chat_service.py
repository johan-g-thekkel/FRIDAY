"""FRIDAY central chat service.

Uses the exact configured provider adapter/model ID. It never fabricates a model
answer: if no real inference endpoint is configured, it raises a clear error.
"""
from __future__ import annotations

from openai import AsyncOpenAI

from backend.model_profiles import load_model_profiles
from backend.settings import get_settings


class ChatRouteUnavailable(ValueError):
    """The requested chat model is not configured."""


async def chat_completion(messages: list[dict[str, str]], requested_route: str = "auto") -> dict:
    settings = get_settings()
    profiles = load_model_profiles()
    available_profiles = [p for p in profiles if p.get("available")]
    route = requested_route or "auto"

    if route == "auto":
        if settings.nebius_ready:
            provider, base_url, api_key, model = (
                "nebius-token-factory", settings.nebius_base_url,
                settings.nebius_api_key, settings.nebius_model,
            )
        elif settings.nvidia_ready:
            provider, base_url, api_key, model = (
                "nvidia-nim", settings.nvidia_base_url,
                settings.nvidia_api_key, settings.nvidia_model,
            )
        elif available_profiles:
            selected = available_profiles[0]
            provider, base_url, api_key, model = (
                "profile:" + selected["id"], selected["base_url"],
                selected["_api_key"], selected["model"],
            )
        elif settings.openai_compatible_ready:
            provider, base_url, api_key, model = (
                "openai-compatible", settings.openai_compatible_base_url,
                settings.openai_compatible_api_key, settings.openai_compatible_model,
            )
        else:
            raise ChatRouteUnavailable(
                "No live AI provider is configured. Add a provider key and model in your local .env, "
                "or configure an OpenAI-compatible Chinese model profile in data/model-profiles.json. "
                "Local fallback planning is not a generative chat model."
            )
    elif route == "nebius":
        if not settings.nebius_ready:
            raise ChatRouteUnavailable("Nebius is not configured: set NEBIUS_API_KEY and NEBIUS_MODEL.")
        provider, base_url, api_key, model = (
            "nebius-token-factory", settings.nebius_base_url,
            settings.nebius_api_key, settings.nebius_model,
        )
    elif route == "nvidia_nim":
        if not settings.nvidia_ready:
            raise ChatRouteUnavailable("NVIDIA NIM is not configured: set NVIDIA_API_KEY and NVIDIA_MODEL.")
        provider, base_url, api_key, model = (
            "nvidia-nim", settings.nvidia_base_url, settings.nvidia_api_key, settings.nvidia_model,
        )
    elif route == "openai_compatible":
        if not settings.openai_compatible_ready:
            raise ChatRouteUnavailable(
                "Custom endpoint is not configured: set OPENAI_COMPATIBLE_API_KEY, "
                "OPENAI_COMPATIBLE_BASE_URL and OPENAI_COMPATIBLE_MODEL."
            )
        provider, base_url, api_key, model = (
            "openai-compatible", settings.openai_compatible_base_url,
            settings.openai_compatible_api_key, settings.openai_compatible_model,
        )
    else:
        selected = next((p for p in profiles if p["id"] == route), None)
        if selected is None:
            raise ChatRouteUnavailable(f"Unknown model route '{route}'. Refresh the model list.")
        if not selected["available"]:
            raise ChatRouteUnavailable(
                f"{selected['name']} is not configured. Set the {selected['api_key_env']} environment variable."
            )
        provider, base_url, api_key, model = (
            "profile:" + selected["id"], selected["base_url"],
            selected["_api_key"], selected["model"],
        )

    client = AsyncOpenAI(
        base_url=base_url.rstrip("/"),
        api_key=api_key,
        timeout=90.0,
        max_retries=1,
    )
    try:
        response = await client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.35,
            max_tokens=1800,
        )
        answer = response.choices[0].message.content
        if not isinstance(answer, str) or not answer.strip():
            raise RuntimeError("The provider returned an empty assistant response.")
        usage = getattr(response, "usage", None)
        return {
            "answer": answer.strip(),
            "provider": provider,
            "model": model,
            "usage": {
                "input_tokens": getattr(usage, "prompt_tokens", None),
                "output_tokens": getattr(usage, "completion_tokens", None),
            } if usage else None,
        }
    finally:
        await client.close()
