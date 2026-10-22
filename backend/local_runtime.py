"""Local inference and offline speech helpers used by FRIDAY's voice-first UI."""
from __future__ import annotations

import asyncio
import importlib.util
import os
import re
import tempfile
import threading
from pathlib import Path
from typing import Any

import httpx

from backend.settings import get_settings


_MODEL_LOCK = threading.Lock()
_WHISPER_MODEL: Any = None
_WHISPER_MODEL_NAME: str | None = None


def _ollama_url() -> str:
    return get_settings().ollama_base_url.rstrip("/")


async def list_ollama_models() -> list[str]:
    """Return only model tags actually present in the configured Ollama runtime."""
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(2.5, connect=1.0)) as client:
            response = await client.get(_ollama_url() + "/api/tags")
            response.raise_for_status()
            payload = response.json()
        raw_models = payload.get("models", [])
        names = []
        for item in raw_models if isinstance(raw_models, list) else []:
            if isinstance(item, dict):
                name = item.get("name") or item.get("model")
                if isinstance(name, str) and name.strip() and len(name) <= 200:
                    names.append(name.strip())
        return sorted(set(names), key=str.casefold)
    except (httpx.HTTPError, ValueError, TypeError):
        return []


def ollama_route_id(model_name: str) -> str:
    """Create a route-safe ID for a tag while retaining the exact tag in server state."""
    slug = re.sub(r"[^a-z0-9]+", "_", model_name.casefold()).strip("_")[:42]
    return "ollama_" + (slug or "model")


def select_ollama_model(route: str, models: list[str]) -> str | None:
    """Resolve a requested local route to an exact installed Ollama tag."""
    if not models:
        return None
    settings = get_settings()
    if route == "ollama":
        configured = settings.ollama_model.strip()
        return configured if configured in models else models[0]
    for name in models:
        if route == ollama_route_id(name):
            return name
    return None


def speech_runtime_status() -> dict[str, Any]:
    """Read local speech capability without downloading or loading a model."""
    installed = importlib.util.find_spec("faster_whisper") is not None
    return {
        "transcription_engine": "faster-whisper-local" if installed else None,
        "transcription_ready": installed,
        "transcription_note": (
            "Offline transcription is available; the selected Whisper model may download on first use."
            if installed
            else "Offline transcription package is missing. Install it with: pip install -r requirements-voice.txt"
        ),
    }


def _transcribe_file_sync(filename: str, model_name: str) -> dict[str, Any]:
    global _WHISPER_MODEL, _WHISPER_MODEL_NAME
    from faster_whisper import WhisperModel

    with _MODEL_LOCK:
        if _WHISPER_MODEL is None or _WHISPER_MODEL_NAME != model_name:
            _WHISPER_MODEL = WhisperModel(
                model_name,
                device="cpu",
                compute_type="int8",
                cpu_threads=max(1, min(4, os.cpu_count() or 1)),
            )
            _WHISPER_MODEL_NAME = model_name
        model = _WHISPER_MODEL

    segments, info = model.transcribe(
        filename,
        beam_size=1,
        vad_filter=True,
        condition_on_previous_text=False,
    )
    transcript = " ".join(segment.text.strip() for segment in segments).strip()
    return {"text": transcript, "language": getattr(info, "language", None)}


async def transcribe_audio(data: bytes, filename: str, model_name: str) -> dict[str, Any]:
    """Transcribe one microphone utterance with a local Whisper model."""
    if importlib.util.find_spec("faster_whisper") is None:
        raise RuntimeError(
            "Local speech recognition is not installed. Run: pip install -r requirements-voice.txt"
        )
    if not data:
        raise ValueError("The microphone sent an empty audio recording.")
    if len(data) > 20 * 1024 * 1024:
        raise ValueError("Audio clips must be 20 MB or smaller.")

    suffix = Path(filename or "").suffix.lower()
    if suffix not in {".webm", ".ogg", ".wav", ".mp3", ".m4a", ".mp4", ".flac"}:
        suffix = ".webm"
    temp_name = None
    try:
        with tempfile.NamedTemporaryFile(prefix="friday-voice-", suffix=suffix, delete=False) as audio_file:
            audio_file.write(data)
            temp_name = audio_file.name
        return await asyncio.to_thread(_transcribe_file_sync, temp_name, model_name)
    finally:
        if temp_name:
            try:
                Path(temp_name).unlink(missing_ok=True)
            except OSError:
                pass
