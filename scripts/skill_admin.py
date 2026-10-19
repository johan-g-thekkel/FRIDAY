#!/usr/bin/env python3
"""Review, inspect, and locally enable imported TEDDY skills.

This tool modifies only the local skills policy file. It never runs scripts
referenced by a skill. Enable only skills you have inspected.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from backend.settings import get_settings
from backend.skill_registry import list_skill_metadata

MAX_DISPLAY_CHARS = 18000


def _paths() -> tuple[Path, Path]:
    settings = get_settings()
    return Path(settings.skills_root).expanduser(), Path(settings.skills_policy_path).expanduser()


def _policy(policy_path: Path) -> dict:
    if not policy_path.exists():
        return {"version": 1, "skills": {}}
    if policy_path.is_symlink() or policy_path.stat().st_size > 256 * 1024:
        raise ValueError("Policy file is a symlink or exceeds the size limit; refusing to edit it.")
    data = json.loads(policy_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("skills", {}), dict):
        raise ValueError("Policy file is malformed; refusing to overwrite it.")
    data.setdefault("version", 1)
    data.setdefault("skills", {})
    return data


def _find(skill_id: str) -> tuple[dict, Path, bytes]:
    root, _ = _paths()
    root = root.resolve(strict=True)
    inventory = list_skill_metadata()
    match = next((skill for skill in inventory["skills"] if skill["id"] == skill_id), None)
    if match is None:
        raise ValueError(f"Unknown skill ID: {skill_id}. Run python scripts/skill_admin.py list.")
    path = root / match["path"]
    if path.is_symlink():
        raise ValueError("Skill file is a symlink; refusing to inspect it.")
    resolved = path.resolve(strict=True)
    resolved.relative_to(root)
    if not resolved.is_file() or resolved.stat().st_size > 128 * 1024:
        raise ValueError("Skill file is not regular or exceeds the size limit.")
    raw = resolved.read_bytes()
    return match, resolved, raw


def show_skill(skill_id: str) -> tuple[dict, Path, bytes]:
    match, path, raw = _find(skill_id)
    print(f"Name: {match['name']}")
    print(f"ID: {match['id']}")
    print(f"Source: {match['source']}")
    print(f"Path: {match['path']}")
    print(f"SHA-256: {hashlib.sha256(raw).hexdigest()}")
    print(f"Current state: {match['status']}")
    print(f"Description: {match['description']}")
    print("\n--- SKILL CONTENT (UNTRUSTED; INSPECT BEFORE ENABLE) ---\n")
    content = raw.decode("utf-8", errors="replace")
    print(content[:MAX_DISPLAY_CHARS])
    if len(content) > MAX_DISPLAY_CHARS:
        print(f"\n[DISPLAY TRUNCATED after {MAX_DISPLAY_CHARS} characters]")
    print("\n--- END SKILL CONTENT ---\n")
    print("Review referenced scripts, dependencies, external endpoints, licenses, and permissions separately.")
    print("Enabling a skill only allows its instruction text to be supplied to selected model-planning calls.")
    print("It does not install tools or execute any code.")
    return match, path, raw


def enable_skill(skill_id: str) -> int:
    root, policy_path = _paths()
    if not root.exists():
        raise ValueError(f"Skill root not found: {root}. Import the ZIP first.")
    match, path, raw = show_skill(skill_id)

    expected = f"ENABLE {skill_id}"
    typed = input(f"After review, type exactly '{expected}' to enable this skill: ").strip()
    if typed != expected:
        print("Not enabled.")
        return 1

    policy = _policy(policy_path)
    relative = path.relative_to(root.resolve(strict=True)).as_posix()
    policy["skills"][relative] = {
        "enabled": True,
        "content_sha256": hashlib.sha256(raw).hexdigest(),
        "reviewed_at": datetime.now(timezone.utc).isoformat(),
        "review_note": "Explicitly enabled through scripts/skill_admin.py after terminal review.",
    }
    policy_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = policy_path.with_suffix(policy_path.suffix + ".tmp")
    temporary.write_text(json.dumps(policy, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(policy_path)
    print(f"Enabled locally: {match['name']}")
    print(f"Policy: {policy_path}")
    return 0


def disable_skill(skill_id: str) -> int:
    root, policy_path = _paths()
    match, path, _ = _find(skill_id)
    policy = _policy(policy_path)
    relative = path.relative_to(root.resolve(strict=True)).as_posix()
    entry = policy["skills"].get(relative)
    if not isinstance(entry, dict):
        print(f"Already disabled: {match['name']}")
        return 0
    entry["enabled"] = False
    policy_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = policy_path.with_suffix(policy_path.suffix + ".tmp")
    temporary.write_text(json.dumps(policy, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(policy_path)
    print(f"Disabled locally: {match['name']}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("list", help="List skill IDs and their state")
    show = subparsers.add_parser("show", help="Inspect full SKILL.md content")
    show.add_argument("skill_id")
    enable = subparsers.add_parser("enable", help="Inspect and explicitly enable a skill")
    enable.add_argument("skill_id")
    disable = subparsers.add_parser("disable", help="Disable a previously enabled skill")
    disable.add_argument("skill_id")
    args = parser.parse_args()

    try:
        if args.command == "list":
            inventory = list_skill_metadata()
            print(inventory["note"])
            for item in inventory["skills"]:
                print(f"{item['id']}  [{item['status']}]  {item['source']}/{item['name']} — {item['description']}")
            print(f"\nTotal: {inventory['count']}")
            return 0
        if args.command == "show":
            show_skill(args.skill_id)
            return 0
        if args.command == "enable":
            return enable_skill(args.skill_id)
        if args.command == "disable":
            return disable_skill(args.skill_id)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"Skill admin stopped safely: {exc}", file=sys.stderr)
        return 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
