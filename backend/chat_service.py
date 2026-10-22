"""Model routing for local Ollama first, then explicitly configured provider routes.

FRIDAY never invents a model response. Local model availability is discovered from
the Ollama runtime at request time; credentials are loaded server-side only.
"""
from __future__ import annotations

from anthropic import AsyncAnthropic
from openai import AsyncOpenAI

from backend.local_runtime import list_ollama_models, select_ollama_model
from backend.model_profiles import load_model_profiles
from backend.settings import get_settings


class ChatRouteUnavailable(ValueError):
    """The requested chat model is not configured or not currently available."""


async def _openai_compatible_completion(
    messages: list[dict[str, str]],
    *,
    provider: str,
    base_url: str,
    api_key: str,
    model: str,
) -> dict:
    url = base_url.rstrip("/")
    if not url.endswith("/v1"):
        url += "/v1"
    client = AsyncOpenAI(
        base_url=url,
        api_key=api_key or "local",
        timeout=120.0,
        max_retries=0,
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


async def _ollama_completion(
    messages: list[dict[str, str]],
    route: str = "ollama",
) -> dict:
    settings = get_settings()
    installed = await list_ollama_models()
    selected = select_ollama_model(route, installed)
    if not selected:
        raise ChatRouteUnavailable(
            "No matching local Ollama model is installed. Start Ollama in the same runtime as FRIDAY, "
            "then run ollama pull qwen2.5:1.5b. If you selected a specific model, make sure its exact "
            "tag appears in ollama list."
        )
    return await _openai_compatible_completion(
        messages,
        provider="ollama-local",
        base_url=settings.ollama_base_url,
        api_key="ollama",
        model=selected,
    )


def _profile_route(route: str) -> dict | None:
    return next((profile for profile in load_model_profiles() if profile["id"] == route), None)


async def _configured_cloud_route(messages: list[dict[str, str]], route: str) -> dict:
    settings = get_settings()
    if route == "nebius" and settings.nebius_ready:
        return await _openai_compatible_completion(
            messages, provider="nebius-token-factory",
            base_url=settings.nebius_base_url, api_key=settings.nebius_api_key or "",
            model=settings.nebius_model or "",
        )
    if route == "nvidia_nim" and settings.nvidia_ready:
        return await _openai_compatible_completion(
            messages, provider="nvidia-nim",
            base_url=settings.nvidia_base_url, api_key=settings.nvidia_api_key or "",
            model=settings.nvidia_model or "",
        )
    if route == "openai_compatible" and settings.openai_compatible_ready:
        return await _openai_compatible_completion(
            messages, provider="openai-compatible",
            base_url=settings.openai_compatible_base_url or "",
            api_key=settings.openai_compatible_api_key or "",
            model=settings.openai_compatible_model or "",
        )
    raise ChatRouteUnavailable(
        f"The {route} route is not configured. Set its required environment variables and restart FRIDAY."
    )


async def chat_completion(messages: list[dict[str, str]], requested_route: str = "auto") -> dict:
    settings = get_settings()
    profiles = load_model_profiles()
    route = requested_route or "auto"

    # AUTO IS LOCAL-FIRST. Only move to a cloud route when no local model is installed.
    local_models = await list_ollama_models() if route == "auto" else []
    if route == "auto" and local_models:
        return await _ollama_completion(messages, "ollama")

    if route == "ollama" or route.startswith("ollama_"):
        return await _ollama_completion(messages, route)

    if route == "auto":
        # Default auto is deliberately local-only to respect FRIDAY's closed-environment mode.
        # Cloud providers remain accessible only through explicit route selection.
        raise ChatRouteUnavailable(
            "No local Ollama model is available. FRIDAY automatic mode is local-only: start Ollama "
            "in this same runtime, then run ollama pull qwen2.5:1.5b. Cloud providers are never used "
            "as a hidden fallback; select one explicitly through an authorized integration if needed."
        )

    if route in {"nebius", "nvidia_nim", "openai_compatible"}:
        return await _configured_cloud_route(messages, route)

    if route == "claude_fable":
        if not settings.claude_fable_ready:
            raise ChatRouteUnavailable(
                "Claude Fable is disabled or missing ANTHROPIC_API_KEY. Configure it explicitly before use."
            )
        system_text = "\n\n".join(item["content"] for item in messages if item.get("role") == "system")
        conversation = [
            {"role": item["role"], "content": item["content"]}
            for item in messages if item.get("role") in {"user", "assistant"}
        ]
        client = AsyncAnthropic(api_key=settings.anthropic_api_key, timeout=90.0, max_retries=0)
        try:
            response = await client.messages.create(
                model=settings.claude_fable_model,
                system=system_text,
                messages=conversation,
                max_tokens=settings.claude_fable_max_output_tokens,
            )
            answer = "\n".join(
                block.text for block in response.content
                if getattr(block, "type", None) == "text"
            ).strip()
            if not answer:
                raise RuntimeError("The provider returned an empty assistant response.")
            return {
                "answer": answer,
                "provider": "anthropic-claude-fable",
                "model": settings.claude_fable_model,
                "usage": {
                    "input_tokens": getattr(response.usage, "input_tokens", None),
                    "output_tokens": getattr(response.usage, "output_tokens", None),
                },
            }
        finally:
            await client.close()

    selected = _profile_route(route)
    if selected is None:
        raise ChatRouteUnavailable(
            "The requested model route is unknown. Refresh the model list and select an available route."
        )
    if not selected["available"]:
        raise ChatRouteUnavailable(
            f"{selected['name']} is not configured. Set the {selected['api_key_env']} environment variable."
        )
    return await _openai_compatible_completion(
        messages,
        provider="profile:" + selected["id"],
        base_url=selected["base_url"],
        api_key=selected["_api_key"] or "",
        model=selected["model"],
    )
