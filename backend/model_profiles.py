"""Configuration-backed OpenAI-compatible model profiles.

Profiles let TEDDY add named model endpoints without editing the router. Secrets
are read only from the environment variable named by api_key_env. Profile JSON
is local operator configuration, never user-uploaded input.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from backend.settings import get_settings

MAX_PROFILE_FILE_BYTES = 64 * 1024
MAX_PROFILES = 30
RESERVED_IDS = {
    "auto", "nebius", "nvidia_nim", "openai_compatible", "claude_fable"
}
PROFILE_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,47}$")
ENV_NAME_RE = re.compile(r"^[A-Z][A-Z0-9_]{1,79}$")
ALLOWED_CAPABILITIES = {
    "text", "reasoning", "coding", "vision", "audio", "video",
    "tool-calling", "embeddings",
}


def _safe_base_url(value: Any) -> str | None:
    if not isinstance(value, str) or len(value) > 500:
        return None
    value = value.strip().rstrip("/")
    try:
        parsed = urlsplit(value)
        if parsed.scheme not in {"https", "http"} or not parsed.hostname:
            return None
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            return None
        # Non-TLS endpoints are allowed only for loopback development servers.
        if parsed.scheme == "http" and parsed.hostname not in {
            "localhost", "127.0.0.1", "::1"
        }:
            return None
        if parsed.port is not None and not (1 <= parsed.port <= 65535):
            return None
    except ValueError:
        return None
    return value


def load_model_profiles() -> list[dict[str, Any]]:
    """Return enabled profiles with readiness and (for internal use) API keys."""
    path = Path(get_settings().model_profiles_path).expanduser()
    if path.is_symlink() or not path.is_file():
        return []
    try:
        if path.stat().st_size > MAX_PROFILE_FILE_BYTES:
            return []
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError):
        return []

    if not isinstance(raw, list) or len(raw) > MAX_PROFILES:
        return []

    profiles: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in raw:
        if not isinstance(item, dict) or item.get("enabled", True) is not True:
            continue
        profile_id = item.get("id")
        name = item.get("name")
        model = item.get("model")
        base_url = _safe_base_url(item.get("base_url"))
        api_key_env = item.get("api_key_env")
        if (
            not isinstance(profile_id, str)
            or not PROFILE_ID_RE.fullmatch(profile_id)
            or profile_id in RESERVED_IDS
            or profile_id in seen
            or not isinstance(name, str)
            or not name.strip()
            or len(name) > 120
            or not isinstance(model, str)
            or not model.strip()
            or len(model) > 300
            or base_url is None
            or not isinstance(api_key_env, str)
            or not ENV_NAME_RE.fullmatch(api_key_env)
        ):
            continue

        api_key = os.getenv(api_key_env)
        capabilities = item.get("capabilities", ["text"])
        if not isinstance(capabilities, list):
            capabilities = ["text"]
        capabilities = sorted({
            value for value in capabilities
            if isinstance(value, str) and value in ALLOWED_CAPABILITIES
        })
        priority = item.get("priority", 100)
        if not isinstance(priority, int) or isinstance(priority, bool):
            priority = 100

        profiles.append({
            "id": profile_id,
            "name": name.strip(),
            "provider": "openai-compatible-profile",
            "base_url": base_url,
            "model": model.strip(),
            "api_key_env": api_key_env,
            "_api_key": api_key,
            "priority": priority,
            "capabilities": capabilities or ["text"],
            "available": bool(api_key),
            "status": "configured_not_tested" if api_key else "needs_api_key",
        })
        seen.add(profile_id)

    return sorted(profiles, key=lambda profile: (profile["priority"], profile["id"]))


def public_model_profiles() -> list[dict[str, Any]]:
    """Return safe, non-secret profile metadata for API clients."""
    return [
        {
            "id": profile["id"],
            "name": profile["name"],
            "provider": profile["provider"],
            "model": profile["model"] if profile["available"] else None,
            "available": profile["available"],
            "status": profile["status"],
            "capabilities": profile["capabilities"],
            "details": (
                "OpenAI-compatible route. Configured but not live-tested; "
                "explicit selections use this exact endpoint/model ID."
                if profile["available"]
                else f"Set the environment variable {profile['api_key_env']} to enable this profile."
            ),
        }
        for profile in load_model_profiles()
    ]


def get_model_profile(profile_id: str) -> dict[str, Any] | None:
    """Return a configured named profile by its ID, including key for internal calls."""
    return next(
        (profile for profile in load_model_profiles() if profile["id"] == profile_id),
        None,
    )
