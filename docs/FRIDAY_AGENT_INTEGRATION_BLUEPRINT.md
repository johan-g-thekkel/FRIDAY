# FRIDAY multi-model and agent integration blueprint

FRIDAY is the orchestration layer and central UI. Models, coding agents, app builders, skills, research tools, and media pipelines are adapters behind explicit capability and permission boundaries. Do not represent an integration as working until its health check and a real smoke test pass.

## Model providers
- Ollama: local inference runtime. Discover installed models through its local API; do not assume Llama/Qwen is installed. Probe reachability and list actual model tags before marking them available.
- Kimi: configurable hosted provider profile; endpoint, model ID and API key must be user-configured.
- Qwen: configurable hosted profile and/or Ollama-served local model.
- Llama: normally local through Ollama, optionally hosted.
- NVIDIA Nemotron: configured NVIDIA or hosting-provider endpoint; never assume one universal endpoint.
- Hosted provider secrets belong only in environment variables or a secret store.

## Agent workers
- Codex: coding worker in an isolated Git worktree, with timeouts, bounded retries, captured logs, tests and reviewable diffs. Never auto-merge.
- Claude Code: optional CLI worker only when installed and authenticated; use documented CLI permissions.
- Hermes Agent: optional external runtime behind a process/HTTP adapter; check version, configured model and tools.
- NemoClaw: optional sandbox/policy layer where host prerequisites are met; not a model.
- OpenCode: distinct optional coding-agent CLI adapter; detect CLI/auth and isolate workspace.

## App-building and design integrations
- Cursor: editor handoff and workspace workflow; GUI control requires a supported computer-use integration.
- Bolt and Lovable: use documented export/GitHub workflows or user-authorized APIs. Import source into a branch and review/test it; do not assume private APIs.
- Reuse public architecture and open-source components only under their licenses. Never copy proprietary source or credentials.

## Skills and research
- ECC Skills and user uploads enter quarantine; record provenance/license/SHA-256, inspect scripts and instructions, and require explicit approval before enabling. Skill text is untrusted data, never system policy.
- Needle/research extraction must be isolated, size/time limited, and show evidence references.
- REA is for owned or authorized app inspection only; do not bypass authentication, DRM, licensing or access controls.

## Media
Use FFmpeg for deterministic processing and separate adapters for transcription, vision, audio or video generation. Tesseract is OCR, not a video editor. Validate outputs and avoid destructive overwrites without approval.

## Unified adapter contract
Each adapter should expose id, kind, capabilities, configuration status, health check, execute(input, timeout, cancellation), structured result, usage/cost metadata where available, and redacted logs. Route by required capability, user preference, availability and budget. Never silently substitute a model explicitly selected by the user.

## Bounded coding loop
Plan -> inspect workspace -> propose patch -> execute in isolated worktree -> run focused tests -> bounded repair attempts -> run relevant checks -> summarize diff/evidence -> request approval. Stop on permission failures, repeated errors, secrets exposure, destructive operations or missing sandbox. No infinite loops or automatic deployment.

## Acceptance criteria
1. Provider status distinguishes configured, reachable, authenticated and smoke-tested.
2. No credentials in repository files.
3. Missing integrations show actionable setup rather than fake success.
4. Every agent task has timeout, cancellation, logs and retry budget.
5. Imported skills are disabled until reviewed and approved.
6. Coding changes are isolated and reviewable; test evidence is recorded.
7. UI labels reflect verified status, not aspirational capability.
