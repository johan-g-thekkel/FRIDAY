"""Read-only metadata inventory for imported agent skills.

Only SKILL.md frontmatter is read. Skill bodies and associated scripts are never
executed by this module. All discovered skills start disabled pending review.
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any

from backend.settings import get_settings

MAX_SKILL_FILES = 1500
MAX_SKILL_BYTES = 128 * 1024
MAX_NAME_CHARS = 120
MAX_DESCRIPTION_CHARS = 700


def _clean_scalar(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        value = value[1:-1]
    return re.sub(r"\s+", " ", value).strip()


def _frontmatter(text: str) -> tuple[str | None, str | None]:
    """Read simple name/description scalars without unsafe YAML deserialization."""
    if not text.startswith("---\n"):
        return None, None

    end = text.find("\n---", 4)
    if end < 0:
        return None, None

    lines = text[4:end].splitlines()
    name: str | None = None
    description: str | None = None
    description_parts: list[str] = []
    in_multiline_description = False

    for line in lines:
        if line.startswith((" ", "\t")):
            if in_multiline_description:
                description_parts.append(line.strip())
            continue

        in_multiline_description = False
        match = re.match(r"^(name|description):\s*(.*)$", line)
        if not match:
            continue

        key, raw_value = match.group(1), match.group(2).strip()
        if key == "name":
            name = _clean_scalar(raw_value)[:MAX_NAME_CHARS]
        elif not raw_value or raw_value in {"|", ">", "|-", ">-", "|+", ">+"}:
            in_multiline_description = True
            description_parts = []
        else:
            description = _clean_scalar(raw_value)[:MAX_DESCRIPTION_CHARS]

    if description_parts:
        description = _clean_scalar(" ".join(description_parts))[:MAX_DESCRIPTION_CHARS]
    return name, description


def list_skill_metadata() -> dict[str, Any]:
    """List skill metadata under SKILLS_ROOT without enabling or running skills."""
    configured_root = Path(get_settings().skills_root).expanduser()
    if not configured_root.exists() or not configured_root.is_dir():
        return {
            "skills": [],
            "count": 0,
            "root_available": False,
            "truncated": False,
            "note": "No imported skills directory found. Skills have not been loaded or enabled.",
        }

    try:
        resolved_root = configured_root.resolve(strict=True)
    except OSError:
        return {
            "skills": [],
            "count": 0,
            "root_available": False,
            "truncated": False,
            "note": "The configured skills directory could not be accessed.",
        }

    skills: list[dict[str, Any]] = []
    truncated = False

    for path in configured_root.rglob("SKILL.md"):
        if len(skills) >= MAX_SKILL_FILES:
            truncated = True
            break

        # Do not follow symlinks or allow files to resolve outside the root.
        if path.is_symlink():
            continue
        try:
            resolved_path = path.resolve(strict=True)
            resolved_path.relative_to(resolved_root)
            if not resolved_path.is_file() or resolved_path.stat().st_size > MAX_SKILL_BYTES:
                continue
            text = resolved_path.read_text(encoding="utf-8", errors="replace")
        except (OSError, ValueError, RuntimeError):
            continue

        name, description = _frontmatter(text)
        relative = path.relative_to(configured_root).as_posix()
        source_parts = relative.split("/")
        source = source_parts[0] if len(source_parts) > 1 else "imported"
        skill_name = name or path.parent.name
        skill_id = hashlib.sha256(relative.encode("utf-8")).hexdigest()[:16]

        skills.append({
            "id": skill_id,
            "name": skill_name,
            "description": description or "No description supplied in skill metadata.",
            "source": source,
            "path": relative,
            "status": "disabled_pending_review",
            "compatible_runtimes": [],
            "required_tools": [],
        })

    skills.sort(key=lambda item: (item["name"].casefold(), item["source"], item["path"]))
    return {
        "skills": skills,
        "count": len(skills),
        "root_available": True,
        "truncated": truncated,
        "note": "Metadata only. Skills remain disabled until reviewed and explicitly enabled.",
    }
