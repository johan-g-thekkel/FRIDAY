# TEDDY Uploaded Integration Inventory

This document records what has actually been inspected, what it contains, and what is still only a planned integration. A source archive is not the same as an installed runtime, downloaded model weights, API credentials, or a verified connection.

## Received and inspected

### `needle-main.zip`

- **What it is:** the Cactus Compute Needle 3 Python source project, package metadata, model utilities, a playground, and tests.
- **License:** the included license is Apache-2.0.
- **Package metadata:** `cactus-needle` version 3.2.1; its declared base runtime dependency is `huggingface_hub`.
- **Potential TEDDY role:** a small structured tool-call/extraction component, for narrow tasks such as classifying intents, extracting typed fields, or proposing calls against a short schema. It should not be treated as the main general-reasoning brain.
- **Important missing assets:** the uploaded archive does not contain `.cact`, `.safetensors`, `.gguf`, or other model-weight files. Download/install the matching official model and platform engine separately, then run a small test before routing tasks to it.
- **Privacy check:** the project's README says telemetry is enabled by default in its binary; it documents `NEEDLE_TELEMETRY=0` and `DO_NOT_TRACK=1` to disable it. TEDDY should set those explicitly for its worker before testing the binary.
- **Integration rule:** use the supported package/runner interface rather than copying its playground UI into TEDDY. Validate its JSON tool proposals against TEDDY's own allow-list and approval policy before any tool can run.

References:
- https://github.com/cactus-compute/needle
- https://huggingface.co/Cactus-Compute/needle3

### `tesseract-main.zip`

- **What it is:** source code for the Tesseract OCR engine (`libtesseract` and the `tesseract` command-line program).
- **License:** the included project README identifies Apache-2.0.
- **Potential TEDDY role:** OCR for screenshots, scanned documents, and selected video frames, if the OCR engine and language data are installed.
- **What it is not:** this archive is not an AI video-editing application. Do not wire it into a video-editing adapter or claim it can edit/compose videos.
- **Integration rule:** prefer a packaged binary or a narrow OCR adapter. Do not compile the entire source tree into TEDDY's API process without need.

Reference:
- https://github.com/tesseract-ocr/tesseract

## Named integrations still awaiting runtime setup or separate files

### Claude Fable 5.1

No Claude/Fable source archive or skill pack was included with the two ZIP files reviewed here. Fable 5.1 is a hosted model API route, not a frontend package. Planned route ID: `claude-fable-5-1`.

- Use it only for tasks where a more capable long-horizon reasoning route is warranted.
- Keep it entirely behind the orchestration/provider layer; never use it to render the TEDDY web interface.
- Require explicit model-provider setup, bounded context/output, logging of model ID and cost estimates, and a hard per-task budget. No silent retries to this route.
- Do not send user files or skill contents to this hosted model unless the task requires them and the user has authorized that use.

Reference: https://platform.claude.com/docs/en/models/fable-5-1/overview

### Nex-N2.5

No Nex-N2.5 source or weight archive was received. Treat it as a separate model/agent route with variants such as Mini, Pro, and Max—not as a library already installed inside TEDDY. The exact hosted endpoint, model ID, license/terms, availability, and pricing must be checked for whichever variant is chosen.

Reference: https://github.com/nex-agi/Nex-N2.5

### tmux

A development launcher has been added at `scripts/tmux-dev.sh`. It starts the TEDDY API in one tmux window and a shell in another, then attaches to the session.

- Run it with `bash scripts/tmux-dev.sh` after creating `.venv` and installing `requirements.txt`.
- Detach with **Ctrl+B**, then **D**; reattach with `tmux attach -t teddy-dev`.
- tmux keeps processes alive while a terminal disconnects, but a stopped/rebuilt Codespace stops the processes too. tmux is not public hosting, a sandbox, or a security boundary.
- Agent jobs should get separate session/task IDs, output logs, bounded runtime, cancellation, workspace isolation, and approval gates.

### Tesseract AI video editor

The exact video tool is not present in the uploaded Tesseract OCR ZIP. Keep the video-editing adapter separate. It can be linked once the correct repository/package or skill is provided.

### Blynk

The Blynk connection library/method has not been uploaded yet. Keep it behind an explicit IoT adapter, with device allow-lists, state verification, logs, and user approval for physical actions.

### Broad AI-model skill library

The two reviewed ZIPs are source repositories, not the promised directory of all model skills. The skills archive remains pending. When it arrives, inspect its index/manifests and licenses, list every skill's instructions and required tools, and preview the inventory before enabling anything.

## Current project rule

The `GET /api/v1/integrations` endpoint reports readiness metadata. A listed integration is not considered operational just because a name appears: verify its executable/package, credentials, model ID, health, error paths, and policy boundaries. Never execute a file simply because it is inside an uploaded archive.
