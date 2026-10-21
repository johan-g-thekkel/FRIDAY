# FRIDAY — local AI central console

FRIDAY is the renamed user-facing assistant identity for this repository. The backend and its provider adapters remain explicit; changing the name does not magically turn every inventory item into a working agent.

## Run locally

1. Use Python 3.11+ and create a virtual environment.
2. Install dependencies: `python -m pip install -r requirements.txt`.
3. Copy `data/model-profiles.example.json` to `data/model-profiles.json`.
4. Create `.env` in the repository root. Add a key only for a provider/account you actually have:

   ```dotenv
   SQLITE_PATH=./data/friday.db
   MODEL_PROFILES_PATH=./data/model-profiles.json
   SILICONFLOW_API_KEY=your_key_here
   ```

5. Start the API/UI: `python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload`.
6. Open `http://127.0.0.1:8000`. Use **Open FRIDAY** in the header to open the central chat console.
7. Check `http://127.0.0.1:8000/health` and `http://127.0.0.1:8000/docs`.

The sample model ID is an example, not a guarantee that a provider account currently offers that model or free inference. SiliconFlow and other providers change model availability, rate limits, trial quotas and pricing. Check the provider dashboard before relying on a free tier. A key is still required for hosted APIs; this is not equivalent to fully offline inference.

## Provider-specific routing

- FRIDAY chat calls the selected configured model directly through the compatible chat-completions interface.
- Existing task planning retains its stricter JSON-plan contract and risk policy.
- For local inference, configure an OpenAI-compatible loopback server (for example Ollama) as a named profile with `http://127.0.0.1:11434/v1`; never expose an unauthenticated local endpoint publicly.
- Do not commit `.env`, API keys, provider tokens, or private conversation data.

## Architecture and integration status

- **Needle:** keep its multi-parameter research/extraction role as a separately testable adapter; the archive/source is not automatically a running agent or a set of model weights.
- **tmux:** useful for keeping a development process visible during an active machine session. tmux does not keep a stopped Codespace or powered-off computer alive, and it is not itself a reliable autonomous test supervisor.
- **ECC skills:** imported skills remain reviewed/opt-in. Treat all skill text as untrusted input, pin hashes, and do not auto-run scripts from uploaded archives.
- **Claude-style architecture:** FRIDAY can use a plan → act through a registered tool → observe → verify → retry-with-bounds loop. This documents a general agent pattern; it does not include Anthropic proprietary source code, model weights, or an unrestricted Claude Code clone.
- **Video editing:** use a dedicated media pipeline adapter (probe/ingest → scene/shot analysis → edit decision list → render → validate output). Tesseract is OCR, not a video-generation model. Actual rendering requires installed media tools such as FFmpeg and separately configured models/services.
- **REA MCP:** use only with authorization. Do not bypass app access controls, DRM, authentication, or other security boundaries. Prefer documented APIs and authorized test targets.
- **Codex, Claude Code, Hermes, Nemotron and other providers:** inventory status is not proof of a working runtime. Each adapter needs its own auth, version checks, timeout policy, isolated workspace, tests, and explicit capabilities.

## Verification

Run `python -m pytest -q`. A successful test suite checks repository behavior, not real external API availability. To verify live inference, configure a provider and send a small test message from the central chat console.
