"""Truthful runtime inventory for TEDDY's planned integrations.

This registry reports whether an integration is implemented, installed, or
still awaiting setup. It never exposes environment variable values and does
not execute agent CLIs or imported skill code.
"""
from __future__ import annotations

import importlib.util
import shutil
from pathlib import Path
from typing import Any

from backend.settings import get_settings
from backend.model_profiles import load_model_profiles


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

    integrations = [
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
            "id": "nvidia_nim",
            "name": "NVIDIA NIM",
            "kind": "model_provider",
            "status": "configured_not_tested" if settings.nvidia_ready else "needs_setup",
            "purpose": "Hosted NVIDIA model inference, including Nemotron models when available",
            "details": "Requires NVIDIA_API_KEY and an exact NVIDIA_MODEL ID. Credentials are never returned by this endpoint.",
        },
        {
            "id": "openai_compatible",
            "name": "Custom OpenAI-Compatible Model",
            "kind": "model_provider",
            "status": "configured_not_tested" if settings.openai_compatible_ready else "needs_setup",
            "purpose": "Connect additional served models without changing TEDDY's router",
            "details": "Requires OPENAI_COMPATIBLE_API_KEY, OPENAI_COMPATIBLE_BASE_URL, and OPENAI_COMPATIBLE_MODEL. This is an endpoint adapter, not a model download.",
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
            "details": "If installed, TEDDY offers explicit coding-task dispatch through the Codex CLI in a detached Git worktree with workspace-write sandbox and network disabled. Authentication is still the operator’s responsibility; CLI exit success is not independent test verification.",
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
            "id": "livekit_agents",
            "name": "LiveKit Agents",
            "kind": "realtime_voice_runtime",
            "status": "source_received_sdk_adapter_pending",
            "purpose": "Realtime voice sessions with selectable STT, LLM, and TTS providers",
            "details": "The uploaded repository is the framework source; use the supported SDK as a separate worker. Credentials and voice interaction have not been configured.",
        },
        {
            "id": "astra_runtime",
            "name": "Astra Agent Runtime",
            "kind": "agent_runtime",
            "status": "source_received_evaluation_required",
            "purpose": "Candidate for evidence-backed long-running agent work and governed execution",
            "details": "Apache-2.0 source received; it overlaps TEDDY's orchestrator/worker layer, so evaluate through a separate process instead of copying its source tree into the API.",
        },
        {
            "id": "glm_v",
            "name": "GLM-V Vision Models",
            "kind": "multimodal_model",
            "status": "source_and_skills_received_weights_not_in_archive",
            "purpose": "Image/video/document understanding and visual grounding via a supported endpoint or local runtime",
            "details": "The archive contains model code and 10 skills but no model checkpoint files.",
        },
        {
            "id": "rea_mcp",
            "name": "REA MCP",
            "kind": "reverse_engineering_tool",
            "status": "source_received_node_runtime_and_setup_pending",
            "purpose": "Evidence-backed inspection of owned or authorized binaries, applications, and runtime behavior",
            "details": "Requires supported Node.js and any target-specific analysis tools. Enable only for authorized targets.",
        },
        {
            "id": "vulk_mcp",
            "name": "VULK MCP Connector",
            "kind": "external_app_builder",
            "status": "source_received_auth_and_docs_verification_pending",
            "purpose": "Optional external app-building workflow through VULK",
            "details": "May consume account credits and cause remote side effects; verify the current official auth/tool contract and require approval before project creation or deployment.",
        },
        {
            "id": "cl4r1t4s_prompt_archive",
            "name": "CL4R1T4S Prompt Collection",
            "kind": "untrusted_reference_data",
            "status": "quarantined_not_enabled",
            "purpose": "Optional read-only research reference only",
            "details": "Do not load its contents as system instructions or execute them; the README includes an instruction-injection attempt and the archive describes extracted third-party prompts.",
        },
        {
            "id": "tesseract_ocr",
            "name": "Tesseract OCR",
            "kind": "utility",
            "status": (
                "installed_needs_test"
                if shutil.which("tesseract")
                else "not_installed_or_built"
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
            "status": "firmware_library_received_backend_adapter_pending",
            "purpose": "Authorized IoT control via a separate adapter",
            "details": "Blynk C++ library v1.3.2 (MIT) is included in the uploaded archive. It is for firmware; the TEDDY backend still needs a supported cloud connector, device allow-list, secure credentials, state read-back, and approval gate. No device commands are enabled.",
        },
        {
            "id": "user_skills",
            "name": "User Skills Library",
            "kind": "skills_registry",
            "status": (
                "metadata_only_inventory_available"
                if Path(settings.skills_root).is_dir()
                and next(Path(settings.skills_root).rglob("SKILL.md"), None) is not None
                else "archives_reviewed_not_imported"
            ),
            "purpose": "Discover and index skill packages for compatible agents",
            "details": "ECC has 292 core skill definitions plus 9 Astra, 10 GLM-V and 5 REA skill candidates. Place reviewed folders under SKILLS_ROOT for metadata discovery; skills stay disabled and their scripts are never run by the inventory API.",
        },
    ]
    # Community-built tools are listed with truthful local readiness states.
    # A CLI being installed is not proof of authentication or a successful run.
    integrations.extend([
        {
            "id": "ollama",
            "name": "Ollama Local Runtime",
            "kind": "local_model_runtime",
            "status": _cli_status("ollama"),
            "purpose": "Run installed local models such as Llama and Qwen",
            "details": "Install Ollama and pull a model separately. FRIDAY must probe the local API and list installed tags before marking any model usable; this inventory does not download models.",
        },
        {
            "id": "opencode",
            "name": "OpenCode",
            "kind": "coding_agent",
            "status": _cli_status("opencode"),
            "purpose": "Open-source coding agent with configurable model providers",
            "details": "Requires CLI setup and provider authentication. Execute only in an isolated worktree with timeouts; installed status is not a smoke test.",
        },
        {
            "id": "nemoclaw",
            "name": "NVIDIA NemoClaw",
            "kind": "agent_sandbox",
            "status": _cli_status("nemoclaw"),
            "purpose": "Optional sandbox/policy layer for supported agent workflows",
            "details": "Not a language model. Verify supported host prerequisites and sandbox policy before enabling workers.",
        },
        {
            "id": "cursor",
            "name": "Cursor Editor Handoff",
            "kind": "external_editor",
            "status": _cli_status("cursor"),
            "purpose": "Open the current workspace in Cursor when its CLI is installed",
            "details": "FRIDAY does not claim GUI control. This entry only detects the optional CLI; otherwise use the workspace link or manual editor handoff.",
        },
        {
            "id": "bolt",
            "name": "Bolt",
            "kind": "external_app_builder",
            "status": "external_workflow_not_connected",
            "purpose": "Import application source created through supported Bolt export/Git workflows",
            "details": "No private API or account session is assumed. Export/import source into a review branch, inspect dependencies and run tests before adoption.",
        },
        {
            "id": "lovable",
            "name": "Lovable",
            "kind": "external_app_builder",
            "status": "external_workflow_not_connected",
            "purpose": "Import supported Lovable-generated application source",
            "details": "Use the supported GitHub integration/export flow. FRIDAY cannot claim control of the remote UI without a separately configured authorized connector.",
        },
        {
            "id": "gesture_solar_system_reference",
            "name": "Community Gesture Solar System",
            "kind": "open_source_reference",
            "status": "reference_documented",
            "purpose": "Reference for gesture-controlled planetary visualization",
            "details": "Upstream: https://github.com/mrgehlot/hand_gesture_solar_system and https://github.com/Sheharyar2000/hand-gesture-universe. FRIDAY currently has its own browser implementation; no source from these repositories is represented as copied.",
        },
        {
            "id": "ecc_skills_upstream",
            "name": "Everything Claude Code (ECC) Skills",
            "kind": "skills_catalog",
            "status": "import_review_required",
            "purpose": "Import reusable community skill definitions after license and content review",
            "details": "Upstream: https://github.com/affaan-m/ECC. Download/archive and review SKILL.md content before importing through FRIDAY's existing quarantine workflow; do not execute scripts automatically.",
        },
    ]);
    integrations.extend(
        {
            "id": "model-profile-" + profile["id"],
            "name": profile["name"],
            "kind": "model_provider",
            "status": profile["status"],
            "purpose": "Configured named OpenAI-compatible model route",
            "details": (
                "Model ID: " + profile["model"] + "; "
                "capabilities: " + ", ".join(profile["capabilities"])
                if profile["available"]
                else "Needs environment variable " + profile["api_key_env"] + "."
            ),
        }
        for profile in load_model_profiles()
    )
    return integrations
