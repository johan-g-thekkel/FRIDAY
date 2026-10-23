# FRIDAY — Native Voice-First AI Desktop Assistant

FRIDAY is a Windows-first Flutter desktop assistant with a Python local service. The user interface is native Flutter/Dart; there are no HTML, CSS, or browser-JavaScript UI assets. The default interaction is voice, not a typing-first chat page.

## What is in this branch

- **Native Flutter desktop UI** in `desktop_app/`: animated holographic humanoid core, movable stage orb and status chips, connection settings, diagnostics, and spoken conversation history.
- **Voice-first hands-free loop**: records microphone audio until a pause, sends it to the local transcription endpoint, submits the transcript to a real selected model, speaks the answer with the installed Windows speech voice, and resumes listening until stopped.
- **Local model routing**: the API discovers installed Ollama model tags and exposes only routes it knows about. Automatic voice mode stays local-only and does not quietly fall back to a hosted model.
- **Local Python backend**: FastAPI retains task history, model routing, skills, bots, the optional Codex worker, voice transcription, and explicit allowlisted desktop actions.
- **Saved connection configuration**: the Flutter app stores the API address, Ollama address, project folder, model route and voice preferences in a local `connection.json` settings file. The path is shown in Diagnostics.
- **Windows setup and build scripts**: create a Python virtual environment, install offline speech dependencies, pull a small starter model, generate Flutter Windows runner files and launch the desktop application.

## Run on Windows

Install these prerequisites first:

1. Python 3.11 or newer.
2. Flutter stable SDK and Windows desktop build prerequisites. In Visual Studio Installer, include **Desktop development with C++**. See the official [Flutter Windows setup guide](https://docs.flutter.dev/platform-integration/windows/setup).
3. Ollama for Windows. The setup script can try the Windows Package Manager install option, or install it from [ollama.com/download/windows](https://ollama.com/download/windows).

Then open PowerShell in the repository root and run:

```powershell
.\scripts\setup_friday_windows.ps1 -InstallOllama
.\scripts\run_friday_windows.ps1
```

The first setup downloads the small `qwen2.5:1.5b` starter model and installs `faster-whisper`. This requires an internet connection once for packages/model downloads. Subsequent inference and transcription can run offline while the downloaded weights remain on the machine.

To skip the starter model download, run `.`\scripts\setup_friday_windows.ps1 `-SkipModelDownload`. To skip the Whisper package, run `.`\scripts\setup_friday_windows.ps1 `-SkipOfflineSpeech`; voice capture will report that local transcription needs setup until the package is installed.

The main launcher sets `FRIDAY_PROJECT_ROOT` and `FRIDAY_PYTHON`, runs the Flutter desktop app, and lets the client start the local FastAPI sidecar. The sidecar reads repo-local `.env` settings. The app's Settings panel can also choose the repository folder and edit both connection URLs.

## Development commands

From the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m pip install -r requirements-voice.txt
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

In another terminal:

```powershell
cd desktop_app
flutter create --platforms=windows .
flutter pub get
dart format lib test
flutter analyze
flutter test
flutter run -d windows
flutter build windows --release
```

The Windows build output is under `desktop_app/build/windows/x64/runner/Release/`. The generated Windows runner files are created by the setup script / Flutter command rather than hand-written source templates.

## How local voice works

1. Click **Activate FRIDAY** and allow microphone access in Windows privacy settings.
2. Speak naturally and pause. The desktop app records a short WAV utterance using the Windows recording stack.
3. The local FastAPI process calls `faster-whisper` to transcribe the audio, then sends the text and recent conversation turns to `/api/v1/chat`.
4. Automatic routing calls an actually installed Ollama model. The app displays real API/provider errors instead of inventing a response.
5. The answer is spoken using the installed Windows text-to-speech voice, and FRIDAY resumes listening while the voice session is active.

The audio file is temporary and deleted after the turn. The small Whisper model is downloaded on first use and cached for later offline runs. Text-to-speech uses the local Windows voice engine; no hosted speech API key is required.

## API endpoints

- `GET /` — API metadata for native clients (JSON; no web UI).
- `GET /health` — service health.
- `GET /api/v1/voice/status` — Ollama and Whisper readiness.
- `GET /api/v1/models` — installed local model routes and configured optional routes.
- `POST /api/v1/voice/transcribe` — local Whisper transcription.
- `POST /api/v1/chat` — conversation inference or an exact allowlisted desktop action.
- `GET /docs` — FastAPI API explorer.

## Safety and current boundaries

FRIDAY's automatic voice route is local-only. Optional cloud routes require an explicit route selection and provider credentials. The first local desktop actions are allowlisted app-open and URL-open intents; they do not enable arbitrary command execution, unrestricted desktop control, device control, email/WhatsApp automation or deployment.

The Python APIs for task planning, task history, bots, skills, and the guarded Codex worker remain in the backend. This Flutter migration replaces the previous HTML screens; the old task/Bot/Skills dashboard has **not yet been fully ported to native Flutter views**. Use the API docs until those native screens are added. Likewise, Hermes Agent and Claude Code are not made operational just by appearing in an integration inventory: each needs a working, tested adapter and the relevant runtime installed.

## Repository layout

```text
backend/                     FastAPI, local inference, skills and agent adapters
desktop_app/                 Flutter/Dart native desktop client
scripts/setup_friday_windows.ps1
scripts/run_friday_windows.ps1
requirements.txt             Python API dependencies
requirements-voice.txt       Optional offline Whisper dependency
tests/                       Python API and safety tests
```

All provider keys belong in local environment variables or `.env`; never commit credentials.
