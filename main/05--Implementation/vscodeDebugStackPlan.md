# VS Code Debug Stack Plan

## Context
- Primary designs: `04--Design/04.06--Toolkit.md` (hsxdbg core), `04--Design/04.09--Debugger.md` (protocol + CLI), and `04--Design/TUI-SourceDisplay-VSCode.md` (DAP/VS Code supplement).
- Toolchain pre-requisites already in place: `.dbg/.sym` line maps, value/command metadata, and stdlib bundle.
- Executive exposes the JSON/TCP RPC interface (`python/execd.py`) that debugger clients consume.
- We are deferring the Textual/TUI front-end; focus shifts to a VS Code experience built on the same debugger protocol.

## Overall Goals
1. Deliver a reliable debugging stack for VS Code that reuses the `hsxdbg` core and the executive RPC protocol.
2. Ensure all debugger capabilities (sessions, events, stepping, stack/locals, breakpoints, watches) are available to the debug adapter.
3. Package the adapter as a VS Code extension with documentation and samples.

## Dependencies & Inputs
| Area | Dependency |
|------|------------|
| Executive | Session RPCs, breakpoint/watch APIs, event streaming (`docs/executive_protocol.md`, `04.02--Executive.md`). |
| Toolkit | `hsxdbg` package (transport, session, events, cache, command helpers) per `04.06--Toolkit.md` and toolkit implementation plan (Phase 1 & 2). |
| Debugger Spec | Protocol semantics, CLI expectations, PID locking (`04.09--Debugger.md`). |
| VS Code Design | DAP integration details, file structure (`TUI-SourceDisplay-VSCode.md`). |
| Toolchain | `.sym` line_map with `source_kind`, variable metadata (already implemented). |

## Phase Breakdown

### Phase 0 – Readiness Audit
1. Verify executive protocol coverage vs. debugger requirements (session keepalive, `events.subscribe`, watch metadata, source-only stepping).
2. Identify any remaining executive gaps (e.g., conditional breakpoints, logpoints) and raise follow-up issues.
3. Confirm `.sym` schema surfaced via `execd` now carries `source_kind` and locals (from recent toolchain work).

### Phase 1 – `hsxdbg` Core Library (Toolkit Plan Phases 1 & 2)
> Refer to toolkit ImplementationPlan Phase 1 (sections 1.1–1.5) & Phase 2 (event streaming).  
Deliverables: `hsxdbg.transport/session/events/cache/commands` plus protocol docs.

Implementation steps:
- Stand up package structure and tests (`python/hsxdbg/`).
- Transport: TCP connection manager, JSON framing, request IDs, reconnect/backoff (Toolkit §4.2.1).
- Session manager: capability negotiation, PID lock semantics, keepalive (Debugger §5.1).
- Command layer: typed wrappers for execution control, breakpoints, memory/regs, stack, watches, disassembly.
- Event bus: async queue with filters & back-pressure (Toolkit §5.2).
- State cache: helper for register/memory snapshots, symbol lookups using `.sym`.
- Documentation: update `docs/executive_protocol.md` with JSON schemas (Toolkit plan 1.5).

### Phase 2 – Debug Adapter Layer (`hsx-dap`)
> Design reference: `toolchain/vscode_debugger.md` Phase 1–3.

Tasks:
- Scaffold `python/hsx-dap.py` with DAP protocol handling (stdio transport, request dispatcher).
- Implement adapters for DAP requests mapping to `hsxdbg` commands:
  - Initialize/launch/attach
  - Continue/pause/terminate
  - Breakpoint set/clear (including verifying via executive response)
  - StackTrace/Scopes/Variables (leveraging `hsxdbg.cache` + `.sym`)
  - StepIn/StepOver/StepOut, run-to-line (using source-only stepping behaviour)
  - Evaluate/hover & watch expressions (reuse `hsxdbg.commands.watch_*`)
- Event bridging: map executive `debug_break`, `trace_step`, `watch_update`, `stdout/stderr` events to DAP events.
- Error handling/logging, configuration (ports, auth, paths).
- Unit tests covering DAP request/response flows (see file structure section in design doc).

### Phase 3 – VS Code Extension Package
Tasks:
- Create `vscode-hsx` extension scaffold (`package.json`, activation, contributes.debuggers entry).
- Add launch configuration snippets, default debug type (e.g., `"type": "hsx"`).
- Wire extension to spawn `hsx-dap.py` (using `DebugAdapterExecutable`).
- Provide syntax highlighting/snippets for MVASM (reuse existing TextMate file).
- Provide example `.vscode/launch.json` for sample projects (mailbox, hello world).
- Add documentation (README, CHANGELOG) referencing hsxdbg CLI & exec setup.

### Phase 4 – Advanced Features & Polish
Tasks (from design Phase 3):
- Conditional & hit-count breakpoints (needs executive support; file follow-up if missing).
- Logpoints (emit messages via DAP without halting).
- Multi-process debugging (attach to multiple PIDs; requires hsxdbg sessions per PID).
- Exception/event translation (map executive error events to DAP `stopped` reasons).
- Performance tuning: event buffering, symbol caching, large memory reads.

### Phase 5 – Distribution & QA
Tasks:
- Package VS Code extension (.vsix), publish to marketplace.
- CI integration (build/test adapter + extension).
- Document end-to-end workflow (hsx-cc-build → execd/manager → VS Code).
- Collect user feedback, iterate.

## Open Questions / Follow-Ups
1. **Executive gaps:** confirm availability of conditional/log breakpoints; if absent, capture in executive backlog.
2. **Source availability:** ensure `sources.json` generated by `hsx-cc-build` is consumed by hsxdbg for path remapping (tie-in with `hsx_std` packaging).
3. **Security:** decide whether DAP adapter talks to executive via local TCP only or needs auth tokens (document in protocol section).
4. **Multi-platform packaging:** confirm Windows/macOS installers include Python runtime or rely on system interpreter.

## Next Steps
1. Kick off Toolkit Phase 1 tasks (`hsxdbg` core) – prerequisite for everything else.
2. Schedule executive review to validate debugger RPC completeness.
3. Draft backlog tickets per phase (Toolkit, exec, adapter, VS Code extension).
