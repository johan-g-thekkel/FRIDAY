"""Public, inspectable autonomy policy for TEDDY.

This describes intended behavior; it does not grant tools extra permissions or
enable unimplemented runtimes. Execution adapters must enforce sandbox and
approval checks independently.
"""
from __future__ import annotations


def public_autonomy_policy() -> dict:
    """Return a JSON-safe policy description suitable for the command centre."""
    return {
        "version": 1,
        "coordination": {
            "mode": "dynamic_specialist_teams",
            "parallelize_independent_work": True,
            "share_relevant_context": True,
            "reallocate_from_observed_results": True,
            "disagreement_resolution": "competitive_execution",
            "disagreement_details": (
                "When alternatives can be tested safely, run isolated competing "
                "approaches and compare tests, benchmarks, and task criteria. "
                "For non-testable claims, prefer traceable evidence and disclose "
                "remaining uncertainty instead of inventing consensus."
            ),
        },
        "profiles": [
            {"id": "supervised", "label": "Supervised", "autonomy": "low",
             "description": "Plan and prepare work; ask before executing changes."},
            {"id": "builder", "label": "Builder", "autonomy": "medium",
             "description": "Implement and test in an isolated workspace with bounded repair attempts."},
            {"id": "researcher", "label": "Researcher", "autonomy": "medium",
             "description": "Research, compare evidence, and report source-backed findings."},
            {"id": "trusted_automation", "label": "Trusted Automation", "autonomy": "high",
             "description": "Automate pre-authorized, reversible tasks within configured limits."},
        ],
        "safeguards": {
            "high_risk_actions_require_approval": True,
            "credentials_are_not_personal_memory": True,
            "untrusted_skills_execute_automatically": False,
            "external_side_effects_enabled_by_default": False,
            "coding_runs_use_isolated_worktrees": True,
            "bounded_timeouts_and_retries": True,
            "report_only_verified_outcomes": True,
            "protect_credentials_and_critical_system_files": True,
        },
        "implementation_status": {
            "policy_endpoint": "implemented",
            "task_planning": "implemented",
            "codex_worker": "optional_adapter_requires_local_install_and_authentication",
            "hermes_agent": "inventory_only_pending_tested_adapter",
            "claude_code": "inventory_only_pending_tested_adapter",
            "automatic_merge_or_deploy": "not_enabled",
            "webcam_emotion_inference": "not_implemented",
            "device_control_and_messaging": "not_enabled",
        },
        "notice": (
            "Profiles describe intended operating modes; they do not bypass existing "
            "approval checks, sandbox limits, runtime availability, or provider configuration."
        ),
    }
