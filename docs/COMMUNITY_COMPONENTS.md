# FRIDAY Community Components and Integration Status

This file distinguishes source code integrated into FRIDAY from upstream projects we can optionally run or import. A GitHub link is not an installed adapter. The backend integration registry uses explicit readiness labels so FRIDAY does not claim a tool is connected merely because it is listed.

## Model runtime

### Ollama
- Upstream: https://github.com/ollama/ollama
- Website: https://ollama.com/
- Role: local inference runtime, not a model. Users must install Ollama and pull model weights separately.
- FRIDAY code: `backend/integration_registry.py` now detects whether the `ollama` CLI exists. This is only a first readiness check; the API health probe and installed-model discovery still need to be wired to the model router before a local model is marked usable.

### Kimi, Qwen, Llama, NVIDIA Nemotron
These are model families/provider choices, not one interchangeable code repository. Configure each exact model ID, endpoint, credentials and capabilities in a provider profile. Qwen/Llama may also be served through Ollama. Hosted free quotas are provider-specific and can change. Never commit API keys.

## Coding agents and runtimes

| Project | Upstream | License verified from upstream LICENSE | Intended FRIDAY use |
|---|---|---|---|
| OpenCode | https://github.com/anomalyco/opencode | MIT | Optional CLI coding worker in isolated worktrees |
| Hermes Agent | https://github.com/NousResearch/hermes-agent | MIT | Optional agent runtime behind a controlled adapter |
| NVIDIA NemoClaw | https://github.com/NVIDIA/NemoClaw | Apache-2.0 | Optional sandbox/policy layer; not a model |
| Codex CLI | https://github.com/openai/codex | Verify upstream terms before vendoring | Coding worker with a reviewable patch/test loop |
| Claude Code | https://github.com/anthropics/claude-code | Verify current upstream terms before vendoring | Optional authenticated external CLI worker |

The FRIDAY integration registry now detects the OpenCode, Hermes, NemoClaw, Codex, and Claude CLI commands where applicable. CLI detection does not establish that authentication, runtime prerequisites, sandboxing, or a smoke test passed. These workers must not share unrestricted host access; run them with explicit timeouts, isolated worktrees, bounded repair attempts, captured logs, and human review before applying changes.

## App-building services

- Cursor: https://cursor.com/ — optional editor handoff. The `cursor` command check only confirms a CLI may be present; it does not give FRIDAY remote GUI control.
- Bolt: https://bolt.new/ — use supported export or repository workflows to import generated source. FRIDAY has no private Bolt API or account session.
- Lovable: https://lovable.dev/ — use its supported GitHub integration/export workflow. Review imported dependencies and run tests.
- These hosted products have their own accounts, policies, usage limits and pricing; FRIDAY cannot promise their hosted features are free.

## Spatial camera and hand gestures

FRIDAY's current page is `frontend/static/vision.html`, implemented with Three.js and MediaPipe Tasks Vision. It contains its own procedural solar-system scene and browser-side hand tracking. The camera starts only after a user click and can be stopped; the page does not upload video frames.

Community references:
- https://github.com/mrgehlot/hand_gesture_solar_system
- https://github.com/Sheharyar2000/hand-gesture-universe
- https://github.com/Shri7ul/Gesture-Controlled-Solar-System-v2
- https://github.com/n07eo/Earth-in-Your-Hand

The upstream license files for some gesture-demo repositories were not found at the conventional `LICENSE` path during inspection. Do not copy their source or assets until their actual license and asset terms are verified. The current FRIDAY page does not claim to contain copied code from these projects; it uses the Three.js and MediaPipe browser libraries.

## Skills and research

### ECC (Everything Claude Code)
- Upstream: https://github.com/affaan-m/ECC
- The upstream LICENSE file inspected in this integration task is MIT.
- Use the upstream repository as a source archive, then import skill definitions through FRIDAY's existing ZIP import and review workflow.
- Review each skill's instructions, source provenance, referenced scripts and tool permissions. Keep imported skills disabled until explicitly approved. Never treat skill text as system instructions or run imported scripts automatically.
- Preserve the upstream copyright/license notice for any copied substantial code or skill content. Skill definitions may have additional referenced resources that need separate review.

### Needle and REA
Use the existing project-specific adapters and uploaded source review. Needle is a research/extraction candidate; REA is only for owned or explicitly authorized application inspection. Do not bypass login, DRM, licensing, access controls or security restrictions.

## Video and media

Use FFmpeg for deterministic cutting, transcoding, muxing and frame extraction; Tesseract is OCR, not a video editor. Speech transcription, visual understanding and generative video must be separate model adapters with explicit input/output limits and licenses. Never overwrite original media without confirmation.

## Implementation status added in this change

- The backend inventory now lists Ollama, OpenCode, NemoClaw, Cursor, Bolt, Lovable, ECC upstream and gesture-solar-system references.
- Readiness statuses are conservative and do not imply a successful provider call or GUI connection.
- Existing Three.js/MediaPipe spatial interface remains the local gesture demo.
- This change does not vendor all third-party repositories into the main application, install large models, log into cloud accounts, or automatically run imported skill scripts.
- Runtime/browser tests must be executed in the actual development environment before merging.
