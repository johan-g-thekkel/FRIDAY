# TEDDY AI Integration Architecture

## Goal

TEDDY is a model- and agent-extensible personal AI operator. It must not be hard-coded to a single model, vendor, or agent runtime. The command center should distinguish what is connected, what is installed, what is configured, and what is merely planned.

## Keep these concepts separate

- **Model providers** run inference: for example, NVIDIA Nemotron through a supported NVIDIA or Nebius endpoint, and other model APIs the user configures.
- **Agent runtimes** can plan and use tools over multiple steps: Hermes Agent, OpenAI Codex, Claude Code, and future compatible agents. These are not interchangeable with a plain chat-completions model. They need their own adapter, runtime installation, login/credentials, and policy handling.
- **Premium reasoning route**: Claude Fable 5.1 is a backend-only hosted model used selectively for long-horizon/high-complexity planning. It is not a UI library and is disabled by default.
- **Compact local tool-call route**: Needle 3 can help with narrow structured tool-selection/extraction tasks; it is not intended to replace a general reasoning model.
- **Vision route**: GLM-V may handle image/video/document understanding and visual grounding through a verified endpoint/runtime; no weights were included in the uploaded archive.
- **Realtime media route**: LiveKit Agents can provide a separate service for streaming voice/video and STT/LLM/TTS coordination; it is not the command-center frontend.
- **Alternative worker runtime**: Astra can be evaluated as a separate long-running, evidence-backed worker, but it overlaps with TEDDY's own orchestrator and execution layer.
- **MCP integrations**: REA is a specialized, optional reverse-engineering MCP tool for owned/authorized targets; VULK is an external app-builder connector that needs current auth-contract verification and approval gates.
- **Skills** are user-supplied instructions and supporting files that describe repeatable capabilities. A skill may be available to an agent only after it is indexed and approved for use. Uploading a skill must never execute it.
- **Tools/integrations** are external capabilities such as GitHub, browser automation, email, messaging, MQTT/Blynk, or Home Assistant. They need their own connector, permissions, and verification.

## Target architecture

1. **TEDDY command center** — one UI for task input, task history, model/agent selection, skill library, system health, and approvals.
2. **Orchestrator** — classify the task; use an explicitly selected route when requested; otherwise choose only among configured and healthy routes whose capabilities fit the task. Return the selected route and reason.
3. **Provider adapters** — a common interface for text/vision inference providers, while preserving provider-specific capability flags, model IDs, cost limits, timeout handling, and error messages.
4. **Agent adapters** — separate adapters for Hermes Agent, Codex, Claude Code, and future agents. Use supported APIs/SDKs or controlled CLI interfaces. Do not pretend a CLI agent is available until its executable and authentication are checked in the worker environment.
5. **Skills registry** — store uploaded skills with an ID, name, description, source, version/hash, trust state, permitted tools, and compatible runtimes. Parse and preview first; quarantine unknown formats and reject path traversal or oversized uploads. Never run scripts simply because they came inside a skill package.
6. **Policy gate** — read-only by default. File writes, command execution, network access, messages, deployments, purchases, and physical IoT actions must be scoped, logged, and approved according to risk.
7. **Isolated workers** — run coding agents and tools outside the web request process, in a per-task workspace with timeouts, output limits, cancellation, and an audit trail.
8. **tmux process supervision** — optionally use tmux for long-running development/agent worker sessions and readable logs. tmux is process/session management, not a sandbox or security boundary, and a stopped Codespace/container still stops its processes.
9. **Verification loop** — plan → execute in a sandbox → collect test/output evidence → diagnose → bounded retry → summarize. Retries are limited; side effects require separate authorization.

## Initial route catalog

| Route | Type | Integration approach | Initial state |
|---|---|---|---|
| Nebius Token Factory | Model API | OpenAI-compatible provider adapter; use exact model ID from the user's account | Optional; not connected until configured |
| NVIDIA Nemotron | Model family | Use a supported endpoint such as Token Factory or NVIDIA NIM; select an available Nemotron model ID | Not connected until configured |
| Claude Fable 5.1 | Hosted reasoning model | Anthropic API adapter; use only for selected complex tasks with input/output caps and an approximate cost guard | Implemented as opt-in planning route; disabled until configured |
| Nex-N2.5 | Agentic model family | Integrate through a verified hosted endpoint or compatible runtime; pin the exact variant and ID | Adapter pending; no weights/source archive received |
| Needle 3 | Compact structured tool-call model | Use the official package/runner and schema-limited tool proposals, with telemetry disabled and policy validation | Source reviewed; weights/engine and runtime installation remain pending |
| Hermes Agent | Agent runtime / orchestrator | Controlled worker adapter; can route to multiple configured providers | Not installed/connected until checked |
| OpenAI Codex | Coding-agent runtime | Supported Codex CLI/SDK adapter with sandbox and approvals | Not installed/connected until checked |
| Claude Code | Coding-agent runtime | Supported Claude Code CLI/SDK adapter with its own authentication | Not installed/connected until checked |
| tmux | Worker process/session manager | Development launcher in scripts/tmux-dev.sh; separate task sessions and logs in future | Launcher committed; tmux must be installed locally |
| GLM-V | Vision-language model | Supported hosted endpoint or verified local runtime; load compatible skills for visual grounding/document work | Source + 10 skills received; model weights not in archive |
| LiveKit Agents | Realtime voice/media agent SDK | Separate service using LiveKit server/cloud and provider credentials | Source received; SDK adapter and credentials pending |
| Astra | Long-running agent runtime | Evaluate through separate Runner/runtime process with isolated workspaces and evidence logs | Apache-2.0 source received; build and security review pending |
| REA MCP | Reverse-engineering tools | Optional MCP server for authorized app/binary analysis only | MIT source + 5 skills received; Node.js/target engine setup pending |
| VULK MCP | External app-building connector | Use current official contract and scoped account auth; require approval for credit-consuming operations | MIT connector source received; auth/version verification pending |
| Tesseract OCR | Utility | Install OCR binary and language data; invoke through a constrained OCR adapter | Source archive reviewed; not built/installed by TEDDY |
| Tesseract AI video editor | Video-editing tool | Separate adapter once the correct project/package is identified | Awaiting correct source; ECC's video-editing skill is guidance only |
| Blynk / IoT | Device integration | C++ library is firmware-side; TEDDY needs separate cloud/bridge adapter with state readback and action approvals | MIT Blynk v1.3.2 library received; backend adapter pending |
| ECC skills | Capability definitions | Deduplicate the 292 core definitions, review dependencies, index metadata, then explicitly enable per agent | MIT archive received; not executed or enabled |
| Astra / GLM-V / REA skills | Capability definitions | Source/compatibility metadata plus review; enable only per compatible runtime | 9 Astra, 10 GLM-V and 5 REA skill definitions found |
| CL4R1T4S prompts | Untrusted reference data | Quarantine, read-only only, never use as system policy | AGPL-3.0 archive has prompt provenance/licensing risks and instruction-injection text |

This is an extensible route catalog, not a claim that every integration is already working. The status API and UI must mark each route as **connected**, **needs setup**, **not installed**, **unavailable**, or **planned**, based on actual checks.

The uploaded skill sources contain **316 named candidates** before deeper cross-source review: 292 core ECC skills, 9 Astra skills, 10 GLM-V skills, and 5 REA skills. ECC's 903 SKILL.md file paths include copies for agents, Kiro/Cursor, examples, and translated docs; do not count those copies as 903 unique skills.

## Routing rules

1. An explicit user selection takes priority, but the request must still pass policy checks.
2. Otherwise choose by required capability (coding, reasoning, vision, browser, local-file access, etc.), configured credentials, health, and user preferences.
3. Keep a configurable primary route and fallback route. Fail over only where the task is safe to retry; do not repeat non-idempotent side effects automatically.
4. Log the route, model/agent ID, duration, result status, and relevant errors without recording secrets.
5. Never label a request as model-generated if the local fallback handled it. Never claim a tool ran unless there is execution evidence.

## Delivery order

- **Phase 1:** Working backend and command-center UI; status and task history; real, explicitly labelled local fallback.
- **Phase 2:** Configure and verify one real inference endpoint (Nemotron through an available NVIDIA/Nebius route), then test the optional Fable route using a clearly complex prompt while keeping it budget-gated.
- **Phase 3:** Install/check tmux and one available agent runtime; implement the first supervised worker adapter with cancellation and bounded output.
- **Phase 4:** Add Needle 3 for a narrow, low-cost structured tool-call task after retrieving the correct weights/engine and checking telemetry/privacy.
- **Phase 5:** Add agent adapters one by one, starting with the runtime that is available in the Codespace and has an authorized login. Test each adapter independently before routing user tasks to it.
- **Phase 6:** Import the user's skill files, inspect their formats, build a safe skills index/preview and compatibility matching.
- **Phase 7:** Add tools and the bounded, sandboxed coding/verification loop. Keep external side effects approval-gated.

## Requirements before enabling an adapter

- Confirm the exact command/API/SDK supported by its official documentation.
- Confirm runtime installation and authentication in the environment where it will run.
- Keep API keys and OAuth credentials in environment secrets, not source code or browser storage.
- Test success, authentication failure, timeout, malformed output, cancellation, and unavailable-route behavior.
- Enforce task-scoped permissions and human approval before sensitive side effects.

## Official integration references

- Hermes Agent integrations/providers: https://hermes-agent.nousresearch.com/docs/integrations
- NVIDIA NIM LLM API reference: https://docs.api.nvidia.com/nim/reference/llm-apis
- OpenAI Codex CLI: https://github.com/openai/codex
- Codex sandbox/approval concepts: https://github.com/openai/codex/blob/main/docs/sandbox.md
- Claude Code CLI usage: https://docs.anthropic.com/en/docs/claude-code/cli-usage
