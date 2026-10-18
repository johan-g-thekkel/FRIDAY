"""Truthful runtime inventory for TEDDY's planned integrations.

This registry reports whether an integration is implemented, installed, or
still awaiting setup. It never exposes environment variable values and does
not execute agent CLIs or imported skill code.
"""
from __future__ import annotations

import importlib.util
import shutil
from typing import Any

from backend.settings import get_settings


def _cli_status(command: str) -> str:
    return "installed_needs_verification" if shutil.which(command) else "not_installed"


def _package_available(package: str) -> bool:
    try:
        return importlib.util.find_spec(package) is not None
    except (ImportError, ValueError):
        return False


def list_integrations() -> list[dict[str, Any]]:
    """Return non-secret readiness metadata for configured/planned routes."""
    settings = get_settings()
    nebius_status = (
        "configured_not_tested" if settings.nebius_ready else "needs_setup"
    )

    return [
        {
            "id": "local_fallback",
            "name": "TEDDY Local Planner",
            "kind": "model",
            "status": "available",
            "purpose": "Deterministic development-mode task planning",
            "details": "Active when no cloud inference route is configured.",
        },
        {
            "id": "nebius_token_factory",
            "name": "Nebius Token Factory",
            "kind": "model_provider",
            "status": nebius_status,
            "purpose": "Configured model inference",
            "details": "Credentials are never returned by this endpoint.",
        },
        {
            "id": "claude_fable_5_1",
            "name": "Claude Fable 5.1",
            "kind": "model_provider",
            "status": (
                "configured_not_tested"
                if settings.claude_fable_ready
                else "disabled_by_default"
                if settings.anthropic_api_key
                else "needs_setup_disabled_by_default"
            ),
            "purpose": "Selective high-effort reasoning and long-horizon tasks",
            "details": "Backend-only route; it remains off unless CLAUDE_FABLE_ENABLED=true and an API key is configured.",
        },
        {
            "id": "nex_n2_5",
            "name": "Nex-N2.5",
            "kind": "model_or_agent_route",
            "status": "adapter_pending",
            "purpose": "Potential long-horizon and visually grounded agent tasks",
            "details": "Exact hosted endpoint/model ID or compatible local runtime must be selected and tested.",
        },
        {
            "id": "needle_3",
            "name": "Needle 3",
            "kind": "compact_tool_call_model",
            "status": (
                "runtime_detected_needs_test"
                if _package_available("needle")
                else "source_received_package_not_installed"
            ),
            "purpose": "Small structured tool selection, extraction, and local routing",
            "details": "Needle source was reviewed separately; install the package and obtain matching model weights/engine before use.",
        },
        {
            "id": "hermes_agent",
            "name": "Hermes Agent",
            "kind": "agent_runtime",
            "status": _cli_status("hermes"),
            "purpose": "Multi-step agent orchestration and tools",
            "details": "Installed CLI presence alone does not prove credentials or safe execution are ready.",
        },
        {
            "id": "codex_cli",
            "name": "OpenAI Codex CLI",
            "kind": "coding_agent",
            "status": _cli_status("codex"),
            "purpose": "Supervised coding, tests, and bounded repair loops",
            "details": "Requires separate workspace isolation, authentication, and approval checks.",
        },
        {
            "id": "claude_code",
            "name": "Claude Code",
            "kind": "coding_agent",
            "status": _cli_status("claude"),
            "purpose": "Optional coding-agent runtime",
            "details": "Separate from the Claude Fable model API adapter.",
        },
        {
            "id": "tmux",
            "name": "tmux",
            "kind": "worker_process_manager",
            "status": _cli_status("tmux"),
            "purpose": "Persistent terminal sessions for supervised long-running workers",
            "details": "A Codespace/container stop still stops its processes; tmux is not 24/7 hosting.",
        },
        {
            "id": "tesseract_ocr",
            "name": "Tesseract OCR",
            "kind": "utility",
            "status": (
                "installed_needs_test"
                if shutil.which("tesseract")
                else "source_received_build_required"
            ),
            "purpose": "Text extraction from images, documents, and selected video frames",
            "details": "Tesseract OCR source was reviewed separately; build/install the OCR engine and language data before use. It is not the video editor.",
        },
        {
            "id": "tesseract_video_editor",
            "name": "Tesseract AI Video Editor",
            "kind": "video_tool",
            "status": "awaiting_correct_source",
            "purpose": "Video editing automation",
            "details": "The uploaded archive does not contain this video editor; keep it separate from Tesseract OCR.",
        },
        {
            "id": "blynk",
            "name": "Blynk / IoT",
            "kind": "device_integration",
            "status": "awaiting_user_library",
            "purpose": "Authorized IoT control via a separate adapter",
            "details": "No device commands are enabled in this backend.",
        },
        {
            "id": "user_skills",
            "name": "User Skills Library",
            "kind": "skills_registry",
            "status": "awaiting_skill_archives",
            "purpose": "Discover and index skill packages for compatible agents",
            "details": "Only inspected and explicitly enabled skills may be used; upload never triggers execution.",
        },
    ]
