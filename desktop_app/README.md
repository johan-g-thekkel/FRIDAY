# FRIDAY Desktop — Flutter for Windows

This is the native Windows client. The old HTML/CSS/JavaScript UI has been removed; FastAPI remains a local API service for model inference, transcription, task history, skills, and guarded local actions.

## First-time setup

Prerequisites: Windows 10/11, Python 3.11+, Flutter stable, Visual Studio with the **Desktop development with C++** workload, and Ollama. Flutter's official Windows setup guide: https://docs.flutter.dev/platform-integration/windows/setup

From the repository root in PowerShell:

    .\scripts\setup_friday_windows.ps1
    .\scripts\run_friday_windows.ps1

The setup script creates the repository .venv, installs the API and offline speech dependencies, downloads a small Ollama model (unless skipped), generates Windows runner files using Flutter, and runs flutter pub get. The speech-recognition model weights are downloaded by faster-whisper on first transcription and are cached for later offline use.

To let the setup script install Ollama using winget where available:

    .\scripts\setup_friday_windows.ps1 -InstallOllama

To skip the model download:

    .\scripts\setup_friday_windows.ps1 -SkipModelDownload

## Settings and connections

The connection service lives under `lib/services/`:
- `friday_settings.dart` saves the API URL, Ollama URL, repo path, model route, language and voice-loop preferences.
- `friday_backend.dart` checks health, discovers model routes, starts the local API/Ollama services when possible, uploads microphone recordings to local Whisper, and submits conversations to FRIDAY's API.
- `widgets/holographic_orb.dart` implements the animated holographic core.

User configuration is saved in the platform application-support directory under `FRIDAY/connection.json` (for example, under the current Windows user's AppData). Settings can be changed from the sliders/tune icon. Set the repository folder to the directory containing `backend/main.py` if automatic detection fails.

## What runs locally

- Flutter desktop UI (Dart).
- FastAPI backend started as a local Python sidecar, if the repo and Python environment are detected.
- Ollama chat completion using models installed in that Ollama runtime.
- faster-whisper transcription, using its cached Whisper weights after the first download.
- Windows text-to-speech via the installed Windows speech voices.

The audio recording is saved temporarily, transcribed by the local backend, and deleted after the turn. FRIDAY's automatic model route is local-only. The UI does not silently fall back to a cloud model. Cloud providers are outside this voice app's default path.

## Run, analyze and test

From `desktop_app`:

    flutter pub get
    dart format lib test
    flutter analyze
    flutter test
    flutter run -d windows
    flutter build windows --release

The release files are under `build/windows/x64/runner/Release` after a Windows build. The repository's launcher sets `FRIDAY_PROJECT_ROOT` and `FRIDAY_PYTHON` so the desktop client can find the Python API.

## Interactive UI

The holographic core can be dragged inside the stage. The model and speech-runtime tiles are also movable. Voice activation records speech until a pause, transcribes it locally, sends the text to the selected local model, speaks the answer with Windows TTS, and resumes listening until the session is stopped.

This build is a local voice assistant foundation—not unrestricted computer control. It supports the existing allowlisted open-app / open-URL actions; broader desktop automation and every third-party agent still require separately implemented adapters and permissions.
