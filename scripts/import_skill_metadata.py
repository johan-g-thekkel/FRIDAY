#!/usr/bin/env python3
"""Import SKILL.md files from known TEDDY source archives for local inventory.

This script copies only selected canonical SKILL.md files. It does not install
packages, import Python/Node code, run shell scripts, or enable any skill.
The imported folder is gitignored by default.
"""
from __future__ import annotations

import argparse
import re
import sys
import zipfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
DESTINATION = ROOT / "skills" / "imported"
MAX_TOTAL_ARCHIVE_BYTES = 260 * 1024 * 1024
MAX_SKILL_BYTES = 128 * 1024
MAX_SKILLS = 500

# Canonical portable locations; avoid duplicate agent adapters and localized docs.
RULES = (
    ("teddy-skill-candidates.zip", ("TEDDY_SKILLS", "ECC"), "ECC"),
    ("teddy-skill-candidates.zip", ("TEDDY_SKILLS", "Astra"), "Astra"),
    ("teddy-skill-candidates.zip", ("TEDDY_SKILLS", "GLM-V"), "GLM-V"),
    ("teddy-skill-candidates.zip", ("TEDDY_SKILLS", "REA"), "REA"),
    ("ECC-main.zip", ("ECC-main", "skills"), "ECC"),
    ("Desktop2222.zip", ("Desktop2222", "GLM-V-main", "skills"), "GLM-V"),
    ("Desktop2222.zip", ("Desktop2222", "Astra-main", ".agent", "skills"), "Astra"),
    ("Desktop2222.zip", ("Desktop2222", "rea-main", "rea-main", ".agents", "skills"), "REA"),
)


def safe_segment(value: str) -> str:
    value = re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("-.")
    return value[:100] or "unnamed"


def candidates_for(archive_name: str, member: str) -> tuple[str, str] | None:
    parts = PurePosixPath(member).parts
    if not parts or PurePosixPath(member).is_absolute() or ".." in parts:
        return None
    if not parts[-1].casefold() == "skill.md" or len(parts) < 3:
        return None

    archive = Path(archive_name).name
    for expected_archive, prefix, source in RULES:
        if archive != expected_archive or tuple(parts[: len(prefix)]) != prefix:
            continue
        # Accepted paths must be exactly <canonical prefix>/<skill-name>/SKILL.md.
        tail = parts[len(prefix):]
        if len(tail) != 2 or tail[-1].casefold() != "skill.md":
            continue
        # Astra's .claude copy is intentionally omitted; .agent is canonical.
        if source == "Astra" and ".claude" in parts:
            continue
        return source, safe_segment(tail[0])
    return None


def is_symlink(info: zipfile.ZipInfo) -> bool:
    unix_mode = (info.external_attr >> 16) & 0xFFFF
    return (unix_mode & 0o170000) == 0o120000


def _emit(messages: list[str] | None, message: str) -> None:
    if messages is None:
        print(message)
    else:
        messages.append(message)


def import_archive(
    path: Path,
    seen: set[tuple[str, str]],
    destination: Path | None = None,
    messages: list[str] | None = None,
) -> tuple[int, int]:
    """Import only approved canonical SKILL.md paths into a chosen local root."""
    target = destination or DESTINATION
    if not path.is_file() or not zipfile.is_zipfile(path):
        _emit(messages, f"SKIP {path}: not a readable ZIP archive")
        return 0, 1

    target.mkdir(parents=True, exist_ok=True)
    imported = skipped = 0
    with zipfile.ZipFile(path) as archive:
        total_uncompressed = sum(item.file_size for item in archive.infolist())
        if total_uncompressed > MAX_TOTAL_ARCHIVE_BYTES:
            raise ValueError(f"{path.name} exceeds the total uncompressed archive size budget")

        for info in archive.infolist():
            if info.is_dir():
                continue
            candidate = candidates_for(path.name, info.filename)
            if candidate is None:
                continue
            source, skill_name = candidate
            key = (source, skill_name.casefold())
            if key in seen:
                skipped += 1
                continue
            if is_symlink(info) or info.file_size > MAX_SKILL_BYTES:
                _emit(messages, f"SKIP {info.filename}: symlink or SKILL.md too large")
                skipped += 1
                continue
            if imported >= MAX_SKILLS:
                raise ValueError(f"too many skill files in {path.name}; limit is {MAX_SKILLS}")

            member_path = PurePosixPath(info.filename)
            if member_path.is_absolute() or ".." in member_path.parts:
                skipped += 1
                continue

            raw = archive.read(info)
            text = raw.decode("utf-8", errors="replace")
            output = target / source / skill_name / "SKILL.md"
            output.parent.mkdir(parents=True, exist_ok=True)
            if output.exists():
                _emit(messages, f"SKIP {source}/{skill_name}: local destination already exists")
                skipped += 1
                continue
            output.write_text(text, encoding="utf-8")
            seen.add(key)
            imported += 1
            _emit(messages, f"INDEXED {source}/{skill_name}")

    return imported, skipped


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archives", nargs="+", help="ZIP filenames already copied into the Codespace")
    args = parser.parse_args()

    DESTINATION.mkdir(parents=True, exist_ok=True)
    seen: set[tuple[str, str]] = set()
    imported_total = skipped_total = 0

    for archive_arg in args.archives:
        path = Path(archive_arg).expanduser().resolve()
        # Avoid duplicate reads; the path need not live inside the TEDDY repo.
        imported, skipped = import_archive(path, seen)
        imported_total += imported
        skipped_total += skipped

    print()
    print(f"Imported skill metadata files: {imported_total}")
    print(f"Skipped: {skipped_total}")
    print(f"Local inventory directory: {DESTINATION}")
    print("All discovered skills remain disabled_pending_review.")
    print("No scripts, tools, packages, or model weights were executed or installed.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, zipfile.BadZipFile) as exc:
        print(f"Import stopped safely: {exc}", file=sys.stderr)
        raise SystemExit(2)
