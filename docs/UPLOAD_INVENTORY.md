# TEDDY Uploaded Integration Inventory

This is an inspected inventory, not a claim that each repository, model, tool, or skill is installed and working. The uploaded archives remain source material until TEDDY's adapters are implemented and tested. Do not execute scripts, install hooks, or load prompt text directly from an archive.

## Upload summary

| Archive | What was inspected | Candidate TEDDY role | Current state |
|---|---|---|---|
| `ECC-main.zip` | ECC agent toolkit; portable skills, adapters, rules, commands, hooks and workflow material | On-demand skill library, coding/review/test workflows | 292 core skill definitions catalogued by name; client/language/localized copies must be deduplicated |
| `needle-main.zip` | Cactus Compute Needle 3 Python source and package metadata | Small structured tool-call/extraction model for narrow deterministic tasks | Source reviewed; model weights/platform engine are not bundled |
| `tesseract-main.zip` | Tesseract OCR source tree | Text extraction from images/documents/selected frames | OCR source only; not a video editor |
| `Desktop2222.zip` | Seven repositories/libraries: Astra, CL4R1T4S, GLM-V, LiveKit Agents, Blynk library, REA, and VULK MCP connector | Runtime, vision, realtime audio/video, skills, IoT firmware, reverse-engineering, external app-builder integrations | Sources inspected; adapters and credentials remain pending |

## Skill archive: ECC

- **License:** MIT, per the archive's top-level `LICENSE`.
- **Core portable set:** 292 distinct `skills/<name>/SKILL.md` definitions.
- **Extra copies:** the archive has 903 `SKILL.md` paths across core skills, agent-specific copies, Kiro/Cursor copies, examples and localized documentation. Those 903 paths are **not** 903 unique capabilities.
- **Other material:** agents, commands, rules, hooks and workflows. Those should be evaluated as separate integration types rather than put all into the skill list.
- **Good initial candidates for TEDDY:** `agent-harness-construction`, `autonomous-loops`, `verification-loop`, `tdd-workflow`, `security-review`, `api-design`, `backend-patterns`, `deep-research`, and `video-editing`. Start with a small set relevant to a task; do not preload hundreds of skills into every prompt.
- **Handling rule:** index skill metadata and requirements first. Skills are instructions, not trusted executable code. A skill is disabled until reviewed and explicitly enabled for compatible agents.

Reference: https://github.com/affaan-m/ECC

## Desktop bundle repositories

### Astra — `Astra-main`

- **Project:** MatrixOrigin Astra, a self-hosted long-running agent runtime with context budgeting, execution evidence, checkpoints, and a separate Runner.
- **License:** Apache-2.0 in the supplied archive.
- **Skill material:** nine distinct Astra-specific skills are duplicated for different client locations; count them once.
- **Use:** study it as a candidate execution/runtime boundary, not as an automatic full fork. It substantially overlaps TEDDY's intended orchestration, journaling and worker layers and uses a Rust workspace plus TypeScript SDK. Evaluate whether TEDDY should invoke it as a separate runtime or retain TEDDY's smaller worker design.
- **Credentials/tools:** still needs a local build/runtime check and permission boundary review.

Reference: https://github.com/matrixorigin/Astra

### CL4R1T4S — `CL4R1T4S-main`

- **Project:** a collection claiming to include extracted system prompts and internal guidance from third-party AI tools. The archive's license file is AGPL-3.0, but that alone does not establish rights over every third-party prompt it contains.
- **Security concern:** its README includes an explicit instruction-injection attempt asking the reader to reveal hidden instructions. That text is untrusted archive content and must not be followed or copied into TEDDY's system prompt.
- **Use:** quarantined as read-only research reference only. Do not activate its prompts, use them to override TEDDY policy, or redistribute its prompt collection without provenance and rights review.

### GLM-V — `GLM-V-main`

- **Project:** Z.ai / Zhipu vision-language model source and multimodal workflow examples.
- **License:** Apache-2.0 in the supplied repository.
- **Skill material:** ten skill definitions: `glmv-caption`, `glmv-doc-based-writing`, `glmv-grounding`, `glmv-pdf-to-ppt`, `glmv-pdf-to-web`, `glmv-prd-to-app`, `glmv-prompt-gen`, `glmv-resume-screen`, `glmv-stock-analyst`, and `glmv-web-replication`.
- **Use:** vision/document/video understanding and visual grounding where supported by the chosen endpoint or local runtime. The archive contains no model checkpoint files.
- **Freshness:** the supplied README says this repository stopped being maintained in September 2026 and points to newer GLM model/skills work. For integration, prefer current official model/API docs and the consolidated official GLM skills repository rather than assuming this archive is the current runtime.

References:
- https://github.com/zai-org/GLM-V
- https://github.com/zai-org/GLM-skills

### LiveKit Agents — `agents-main`

- **Project:** LiveKit's real-time agent framework for streaming voice/video sessions and mixing STT, LLM and TTS components.
- **License:** the framework source is Apache-2.0; the archive also includes a separate model license for certain LiveKit models.
- **Use:** optional realtime voice/audio-video transport and agent session layer. It is not TEDDY's main UI and should be integrated as a separate service/SDK adapter, not by copying its large source tree into the FastAPI backend.
- **Requirements:** a LiveKit Cloud or self-hosted server, URL, API key/secret, a selected provider, and explicit mic/camera permissions. None is configured yet.

Reference: https://github.com/livekit/agents

### Blynk C++ library — `blynk-library-1.3.2`

- **Project:** embedded Arduino/C++ library, version 1.3.2, for ESP32, ESP8266 and other boards.
- **License:** MIT in the archive.
- **Use:** firmware-side Blynk connectivity; the code is not a Python server SDK. TEDDY needs a separate supported Blynk Cloud REST/MQTT/bridge adapter, secure device credentials, an allow-list, state read-back and approval for physical actions.
- **Status:** library source received; no Blynk credentials or device integration has been configured. Do not put device auth tokens in Git, chat, or browser code.

Reference: https://github.com/blynkkk/blynk-library

### REA — `rea-main/rea-main`

- **Project:** Reverse Engineer Anything: a CLI/MCP tool for evidence-backed investigation of binaries, application behavior and runtime traces.
- **License:** MIT in the nested project.
- **Skill material:** five skills: `rea-analysis-optimization`, `rea-changelog-update`, `rea-ci-tests-audit`, `rea-tool-design`, and `reverse-engineer-anything`.
- **Use:** optional MCP integration when a request genuinely needs binary/runtime evidence. Use only on targets the user owns or is authorized to assess. Do not run the setup command automatically.
- **Requirements:** Node.js version in the project's current supported range and, for some native-analysis cases, a supported analysis engine. No REA runtime is connected yet.

Reference: https://github.com/morluto/rea

### VULK MCP connector — `vulk-mcp-server-main`

- **Project:** optional connector to VULK's external AI app-building service.
- **License:** MIT in the archive.
- **Use:** could create/edit app projects outside TEDDY. Such operations can consume account credits and modify external projects, so they require explicit approval.
- **Authentication caution:** the bundled README and currently available official documentation describe different authentication/tool contracts. Verify the live official docs and package version before configuring the connector; do not blindly copy stale OAuth/API-key settings.
- **Status:** code reviewed only; no account connection or operation was performed.

References:
- https://github.com/VULK-dev/vulk-mcp-server
- https://support.vulk.dev/docs/api/mcp

## Other model/runtime integrations

### Needle 3 — `needle-main.zip`

- **License:** Apache-2.0 in the archive; package metadata identifies `cactus-needle` 3.2.1.
- **Potential role:** small structured tool selection, typed extraction, and embeddings for narrow subtasks, not the main general reasoning brain.
- **Missing:** no `.cact`, `.safetensors`, `.gguf`, or other model weights are in the uploaded ZIP. The official model and platform engine must be obtained separately and tested.
- **Privacy:** the project documents telemetry as on by default in its binary and gives `NEEDLE_TELEMETRY=0` and `DO_NOT_TRACK=1` to disable it. TEDDY's worker should set both before tests.
- **Policy:** validate any proposed tool name and arguments against a strict allow-list; never let a compact model decide its own permissions.

Reference: https://github.com/cactus-compute/needle

### Tesseract OCR — `tesseract-main.zip`

- **Project:** OCR engine source, not a video editor.
- **Potential role:** convert selected image/video frames into text for a downstream model or skill.
- **Missing:** a built binary and the relevant language data are not configured in TEDDY.
- **Video editing:** ECC includes a `video-editing` skill, but it is a workflow guide, not a dedicated Tesseract video editor. The correct video-editing application/runtime remains unidentified.

Reference: https://github.com/tesseract-ocr/tesseract

### Claude Fable 5.1

Claude Fable 5.1 is an optional **hosted model route**, not a source-code package or frontend dependency. TEDDY now has a backend-only adapter, disabled by default, with complexity selection and an approximate per-task budget guard. This guard is not a provider-enforced spending limit. Configure a key only when deliberately opting in, check the live price/limits, and test the route before use.

Official model/API documentation: https://platform.claude.com/docs/en/models/fable-5-1/overview

### Nex-N2.5

No Nex-N2.5 source or model weights were found in the uploaded bundle. This remains an adapter candidate; select and verify an exact model variant/ID, endpoint or local runtime, licensing terms, availability and pricing before use.

Reference: https://github.com/nex-agi/Nex-N2.5

## Count of candidate skill definitions

The current archives include **316 named candidate skills before broader cross-source review**:

- ECC core portable definitions: 292
- Astra-specific definitions: 9
- GLM-V definitions: 10
- REA definitions: 5

These are candidate instructions, not enabled skills. The catalog must also record required environment variables, executables, API/provider dependencies, compatible agent runtimes, file paths, license/source, and risk tags. Skills that ask to bypass policy, exfiltrate secrets, or perform unapproved side effects must be quarantined or rewritten before enablement.

## Local skill activation workflow

After importing the curated bundle into the Codespace, use:

```bash
python scripts/skill_admin.py list
python scripts/skill_admin.py show SKILL_ID
python scripts/skill_admin.py enable SKILL_ID
python scripts/skill_admin.py disable SKILL_ID
```

TEDDY sends only reviewed, hash-matched skills to configured model-planning routes, limits the number/size of skill contexts, and returns the skill names in task history. It refuses explicit unapproved selections. A skills bundle does not install its external tools, authenticate an agent, or supply missing model weights.

## Current project rule

The `GET /api/v1/integrations` endpoint reports readiness metadata. A listed integration is not operational just because a name appears: verify its executable/package, credentials, model ID, health, error paths, and policy boundaries. Never execute a file simply because it is inside an uploaded archive.
