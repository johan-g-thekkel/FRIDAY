"""Small, explicit local desktop actions for voice commands.

This module intentionally does not accept arbitrary shell commands. The backend
must be running on the user's machine for these actions to affect its desktop.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import webbrowser
from typing import Any
from urllib.parse import urlparse

from backend.settings import get_settings


APP_ALIASES = {
    "calculator": "calculator",
    "calc": "calculator",
    "notepad": "notepad",
    "text editor": "notepad",
    "file explorer": "file_explorer",
    "files": "file_explorer",
    "explorer": "file_explorer",
    "paint": "paint",
    "microsoft paint": "paint",
    "browser": "browser",
    "web browser": "browser",
}
OPEN_APP_RE = re.compile(
    r"^(?:friday[,:]?\s+)?(?:please\s+)?open\s+(?:the\s+)?"
    r"(calculator|calc|notepad|text editor|file explorer|files|explorer|paint|microsoft paint|browser|web browser)"
    r"[.!?\s]*$",
    re.IGNORECASE,
)
OPEN_URL_RE = re.compile(
    r"^(?:friday[,:]?\s+)?(?:please\s+)?open\s+(?:the\s+)?"
    r"(https?://[^\s]+|(?:www\.)?[a-z0-9][a-z0-9.-]*\.[a-z]{2,}(?:/[^\s]*)?)[.!?\s]*$",
    re.IGNORECASE,
)


def _action_enabled() -> bool:
    settings = get_settings()
    return bool(getattr(settings, "enable_local_desktop_actions", False))


def resolve_voice_action(prompt: str) -> dict[str, str] | None:
    """Recognize a small allowlist of explicit, unambiguous app-launch commands."""
    value = re.sub(r"\s+", " ", str(prompt or "").strip())
    if not value or len(value) > 500:
        return None

    app_match = OPEN_APP_RE.fullmatch(value)
    if app_match:
        alias = app_match.group(1).casefold()
        return {"kind": "open_app", "target": APP_ALIASES[alias]}

    url_match = OPEN_URL_RE.fullmatch(value)
    if url_match:
        raw = url_match.group(1).rstrip(".,!?;")
        if not raw.casefold().startswith(("http://", "https://")):
            raw = "https://" + raw
        parsed = urlparse(raw)
        if parsed.scheme in {"http", "https"} and parsed.hostname and not parsed.username and not parsed.password:
            return {"kind": "open_url", "target": raw}
    return None


def _launch_app(app: str) -> str:
    """Launch only fixed application targets, never a user-supplied command."""
    if app == "browser":
        if not webbrowser.open("https://www.google.com", new=2):
            raise RuntimeError("The default browser could not be opened on this machine.")
        return "Opened your default web browser."

    if os.name == "nt":
        executables = {
            "calculator": "calc.exe",
            "notepad": "notepad.exe",
            "file_explorer": "explorer.exe",
            "paint": "mspaint.exe",
        }
    elif os.name == "darwin":
        applications = {
            "calculator": "Calculator",
            "notepad": "TextEdit",
            "file_explorer": "Finder",
            "paint": "Preview",
        }
        result = subprocess.run(
            ["open", "-a", applications[app]],
            capture_output=True, text=True, timeout=5, check=False,
        )
        if result.returncode:
            raise RuntimeError("The application could not be opened on this Mac.")
        return "Opened " + applications[app] + "."

    else:
        commands = {
            "calculator": ("gnome-calculator", "kcalc", "xcalc"),
            "notepad": ("mousepad", "gedit", "kate", "leafpad"),
            "file_explorer": ("xdg-open",),
            "paint": ("pinta", "kolourpaint"),
        }
        executable = next((shutil.which(name) for name in commands[app] if shutil.which(name)), None)
        if executable is None:
            raise RuntimeError("No supported desktop application was found in this Linux environment.")
        args = [executable, str(__import__("pathlib").Path.home())] if app == "file_explorer" else [executable]
        subprocess.Popen(args, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, close_fds=True)
        return "Started the selected desktop application."

    executable = shutil.which(executables[app])
    if not executable:
        raise RuntimeError("The application executable was not found in this Windows environment.")
    subprocess.Popen(
        [executable],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        close_fds=True,
    )
    return "Opened " + executables[app].removesuffix(".exe").replace("_", " ") + "."


def handle_voice_action(prompt: str) -> dict[str, Any] | None:
    """Execute a recognized allowlisted action on the host running the backend."""
    action = resolve_voice_action(prompt)
    if action is None:
        return None

    if not _action_enabled():
        return {
            "answer": (
                "I recognized that local action, but local desktop control is disabled on this host. "
                "Run FRIDAY on your laptop and set FRIDAY_ENABLE_LOCAL_DESKTOP_ACTIONS=true. "
                "A Codespace cannot open applications on your laptop."
            ),
            "provider": "local-action-guard",
            "model": None,
            "action": {"status": "disabled", "kind": action["kind"], "target": action["target"]},
        }

    try:
        if action["kind"] == "open_app":
            description = _launch_app(action["target"])
        else:
            # URLs are passed only to the machine's default browser; never interpreted as shell commands.
            if not webbrowser.open(action["target"], new=2):
                raise RuntimeError("The default browser could not open the requested URL.")
            description = "Opened " + action["target"] + " in your default browser."
        return {
            "answer": description,
            "provider": "local-desktop-action",
            "model": None,
            "action": {"status": "completed", "kind": action["kind"], "target": action["target"]},
        }
    except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
        return {
            "answer": "I recognized the local action but could not complete it: " + str(exc),
            "provider": "local-desktop-action",
            "model": None,
            "action": {"status": "failed", "kind": action["kind"], "target": action["target"]},
        }
