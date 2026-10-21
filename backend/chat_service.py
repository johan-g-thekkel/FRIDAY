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
        # FRIDAY chat defaults to configured named profiles (for example a Chinese
        # provider or a local Ollama-compatible endpoint), not paid premium routes.
        if not available_profiles:
            raise ChatRouteUnavailable(
                "No named chat profile is configured. Copy data/model-profiles.example.json "
                "to data/model-profiles.json, add a valid provider key in .env, and confirm "
                "the provider currently offers the selected model/free quota."
            )
        selected = available_profiles[0]
    else:
        selected = next((p for p in profiles if p["id"] == route), None)
        if selected is None:
            raise ChatRouteUnavailable(
                "FRIDAY central chat only uses named OpenAI-compatible profiles. "
                "Configure a Chinese provider profile or a local model profile."
            )
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
