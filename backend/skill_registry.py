"""Read-only skill inventory plus explicit, hash-pinned skill selection.

Imported skill text is untrusted data. This module never runs commands, imports
skill code, follows skill-file symlinks, or enables a skill automatically.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from backend.settings import get_settings

MAX_SKILL_FILES = 1500
MAX_SKILL_BYTES = 128 * 1024
MAX_NAME_CHARS = 120
MAX_DESCRIPTION_CHARS = 700
STOP_WORDS = {
    "about", "above", "after", "again", "against", "also", "and", "any",
    "are", "because", "before", "being", "below", "between", "both", "but",
    "can", "could", "did", "does", "doing", "down", "each", "for", "from",
    "further", "had", "has", "have", "having", "here", "how", "into", "its",
    "just", "more", "most", "not", "only", "other", "our", "out", "over",
    "own", "same", "should", "some", "such", "than", "that", "the", "their",
    "them", "then", "there", "these", "they", "this", "those", "through",
    "under", "very", "was", "were", "what", "when", "where", "which", "who",
    "will", "with", "would", "you", "your",
}


class SkillNotApprovedError(ValueError):
    """Raised when a task explicitly requests a skill that is not approved."""


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

    name: str | None = None
    description: str | None = None
    description_parts: list[str] = []
    in_multiline_description = False
    for line in text[4:end].splitlines():
        if line.startswith((" ", "\t")):
            if in_multiline_description:
                description_parts.append(line.strip())
            continue
        in_multiline_description = False
        match = re.match(r"^(name|description):\s*(.*)$", line)
        if not match:
            continue
        key, raw = match.group(1), match.group(2).strip()
        if key == "name":
            name = _clean_scalar(raw)[:MAX_NAME_CHARS]
        elif not raw or raw in {"|", ">", "|-", ">-", "|+", ">+"}:
            in_multiline_description = True
            description_parts = []
        else:
            description = _clean_scalar(raw)[:MAX_DESCRIPTION_CHARS]

    if description_parts:
        description = _clean_scalar(" ".join(description_parts))[:MAX_DESCRIPTION_CHARS]
    return name, description


def _load_policy(policy_path: Path) -> dict[str, Any]:
    try:
        if not policy_path.is_file() or policy_path.is_symlink():
            return {"version": 1, "skills": {}}
        if policy_path.stat().st_size > 256 * 1024:
            return {"version": 1, "skills": {}}
        data = json.loads(policy_path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or not isinstance(data.get("skills", {}), dict):
            return {"version": 1, "skills": {}}
        return data
    except (OSError, ValueError, json.JSONDecodeError):
        return {"version": 1, "skills": {}}


def _iter_skill_files(root: Path):
    if not root.exists() or not root.is_dir():
        return
    try:
        resolved_root = root.resolve(strict=True)
    except OSError:
        return

    seen = 0
    for path in root.rglob("SKILL.md"):
        if seen >= MAX_SKILL_FILES:
            break
        seen += 1
        if path.is_symlink():
            continue
        try:
            resolved = path.resolve(strict=True)
            resolved.relative_to(resolved_root)
            if not resolved.is_file() or resolved.stat().st_size > MAX_SKILL_BYTES:
                continue
            raw = resolved.read_bytes()
            text = raw.decode("utf-8", errors="replace")
        except (OSError, ValueError, RuntimeError):
            continue

        relative = path.relative_to(root).as_posix()
        digest = hashlib.sha256(raw).hexdigest()
        skill_id = hashlib.sha256(relative.encode("utf-8")).hexdigest()[:16]
        name, description = _frontmatter(text)
        parts = relative.split("/")
        yield {
            "id": skill_id,
            "name": name or path.parent.name,
            "description": description or "No description supplied in skill metadata.",
            "source": parts[0] if len(parts) > 1 else "imported",
            "path": relative,
            "content_hash": digest,
            "_text": text,
        }


def list_skill_metadata() -> dict[str, Any]:
    """List local skill metadata and hash-verified enablement state."""
    settings = get_settings()
    root = Path(settings.skills_root).expanduser()
    policy = _load_policy(Path(settings.skills_policy_path).expanduser())
    if not root.exists() or not root.is_dir():
        return {
            "skills": [],
            "count": 0,
            "root_available": False,
            "truncated": False,
            "note": "No imported skills directory found. Import skills locally, then review them before enabling.",
        }

    approvals = policy.get("skills", {})
    skills: list[dict[str, Any]] = []
    for item in _iter_skill_files(root):
        entry = approvals.get(item["path"], {})
        if isinstance(entry, dict) and entry.get("enabled") is True:
            status = (
                "enabled_reviewed"
                if entry.get("content_sha256") == item["content_hash"]
                else "changed_since_review"
            )
        else:
            status = "disabled_pending_review"
        skills.append({
            "id": item["id"],
            "name": item["name"],
            "description": item["description"],
            "source": item["source"],
            "path": item["path"],
            "content_hash": item["content_hash"][:12],
            "status": status,
            "compatible_runtimes": [],
            "required_tools": [],
        })

    skills.sort(key=lambda item: (item["name"].casefold(), item["source"], item["path"]))
    return {
        "skills": skills,
        "count": len(skills),
        "root_available": True,
        "truncated": len(skills) >= MAX_SKILL_FILES,
        "note": "Metadata only. Skills must be explicitly reviewed and hash-matched in the local policy before they can be selected for model planning.",
    }


def _tokens(text: str) -> set[str]:
    return {
        token for token in re.findall(r"[a-z0-9][a-z0-9_-]{1,}", text.casefold())
        if token not in STOP_WORDS
    }


def get_enabled_skill_context(
    prompt: str,
    requested_skill_ids: list[str] | None = None,
) -> list[dict[str, str]]:
    """Return a small set of approved skill bodies for a model call."""
    settings = get_settings()
    root = Path(settings.skills_root).expanduser()
    policy = _load_policy(Path(settings.skills_policy_path).expanduser())
    approvals = policy.get("skills", {})
    enabled = []

    for item in _iter_skill_files(root):
        entry = approvals.get(item["path"], {})
        if not isinstance(entry, dict) or entry.get("enabled") is not True:
            continue
        if entry.get("content_sha256") != item["content_hash"]:
            continue
        enabled.append(item)

    if requested_skill_ids:
        wanted = set(requested_skill_ids)
        matches = [item for item in enabled if item["id"] in wanted]
        if {item["id"] for item in matches} != wanted:
            raise SkillNotApprovedError(
                "One or more requested skills are not approved or changed since review."
            )
        limit = max(1, min(settings.max_active_skills, 5))
        if len(matches) > limit:
            raise SkillNotApprovedError(f"At most {limit} approved skills may be attached to one task.")
        matches.sort(key=lambda item: item["id"])
    else:
        prompt_tokens = _tokens(prompt)
        scored = []
        for item in enabled:
            name_tokens = _tokens(item["name"].replace("-", " "))
            description_tokens = _tokens(item["description"])
            score = 3 * len(prompt_tokens & name_tokens) + len(prompt_tokens & description_tokens)
            if score > 0:
                scored.append((score, item))
        scored.sort(key=lambda pair: (-pair[0], pair[1]["name"].casefold()))
        matches = [item for _, item in scored[:max(1, min(settings.max_active_skills, 5))]]

    result = []
    remaining = max(0, settings.max_skill_context_chars)
    for item in matches:
        if remaining <= 0:
            break
        text = item["_text"]
        if text.startswith("---\n"):
            end = text.find("\n---", 4)
            if end >= 0:
                text = text[end + 4:].lstrip()
        text = text[:min(remaining, 5000)].strip()
        if not text:
            continue
        result.append({
            "id": item["id"],
            "name": item["name"],
            "path": item["path"],
            "content": text,
        })
        remaining -= len(text)
    return result
