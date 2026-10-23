# FRIDAY — local Windows voice assistant

The supported desktop client is now a native Flutter application in `desktop_app/`. The FastAPI process is an API service, not an HTML site. It can be started by the Flutter app from the repository root or started manually for API testing.

## One-time Windows setup

Prerequisites:
- Python 3.11 or newer
- Flutter stable
- Visual Studio with the **Desktop development with C++** workload
- Ollama for Windows

Official Flutter setup instructions: https://docs.flutter.dev/platform-integration/windows/setup

From the repository root in PowerShell:

    .\scripts\setup_friday_windows.ps1 -InstallOllama
    .\scripts\run_friday_windows.ps1

The setup script creates the repository `.venv`, installs the API dependencies and optional `faster-whisper` package, ensures the small `qwen2.5:1.5b` Ollama model is downloaded, generates the Windows runner files, and runs `flutter pub get`. A first setup requires internet access to download packages and model weights. After these downloads are cached, voice inference and transcription can run without cloud inference services.

The `-InstallOllama` switch asks Windows Package Manager to install Ollama if it is missing. If winget is unavailable, install Ollama from https://ollama.com/download/windows and rerun setup.

To skip the local model pull, use:

    .\scripts\setup_friday_windows.ps1 -SkipModelDownload

To skip optional offline Whisper installation, use:

    .\scripts\setup_friday_windows.ps1 -SkipOfflineSpeech

The app can still open without these optional pieces, but it reports exactly which local component is missing rather than acting like a model is connected.

## Start the application

    .\scripts\run_friday_windows.ps1

The launcher sets `FRIDAY_PROJECT_ROOT` and `FRIDAY_PYTHON`, runs the Flutter desktop application, and lets the client launch the Python backend. The Flutter app opens its connection settings from the tune icon. You can set the API URL, Ollama URL, repository path, local model route, language and whether listening resumes after each spoken answer.

The connection configuration is saved to `connection.json` in the Windows application-support directory. The Diagnostics screen displays its exact path.

## Developer commands

From PowerShell in the repository root:

    python -m venv .venv
    .\.venv\Scripts\Activate.ps1
    python -m pip install -r requirements.txt
    python -m pip install -r requirements-voice.txt

Then in the Flutter project:

    cd desktop_app
    flutter create --platforms=windows .
    flutter pub get
    dart format lib test
    flutter analyze
    flutter test
    flutter run -d windows
    flutter build windows --release

The build output is under `desktop_app/build/windows/x64/runner/Release/`.

## Local voice flow

1. Click **Activate FRIDAY**. Microphone permission is handled by Windows privacy settings.
2. Speak a phrase and pause. The client records a temporary WAV utterance.
3. The local API uses `faster-whisper` to transcribe the clip, then calls the selected model via `/api/v1/chat`.
4. Automatic routing only uses Ollama models actually installed in the configured runtime. It does not silently fall back to cloud providers.
5. The answer is spoken using the installed Windows voice and FRIDAY resumes listening until you stop the session.

Whisper weights are downloaded once by faster-whisper on first use and then cached. The temporary recording is removed after the turn. Browser/Web Speech API is not used by the native client.

## API-only routes

- `GET /` — JSON metadata for the native app.
- `GET /health` — service health.
- `GET /api/v1/voice/status` — local model and speech readiness.
- `GET /api/v1/models` — actually installed Ollama model routes and optional configured routes.
- `POST /api/v1/voice/transcribe` — local speech transcription.
- `POST /api/v1/chat` — local model inference or an exact allowlisted desktop action.
- `GET /docs` — FastAPI API explorer.

The task planning, history, bot, skill and guarded Codex endpoints remain in the backend, but their old HTML dashboard was removed and their complete native Flutter views are not yet ported. Use the API explorer for those endpoints until the corresponding native views are implemented.

FRIDAY currently has an explicit allowlist for opening certain desktop apps and URLs; it does not enable arbitrary shell execution or unrestricted device/desktop control. Hermes Agent and Claude Code require separate working adapters and are not treated as connected just because they are listed in the integration inventory.
