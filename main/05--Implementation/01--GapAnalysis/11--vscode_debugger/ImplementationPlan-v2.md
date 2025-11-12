# VS Code Debugger Implementation Plan (v2)

## Why v2?

The original plan (02--ImplementationPlan.md) assumed the VS Code adapter would talk
directly to the executive RPCs. Since then we have delivered a feature-rich CLI
debugger (`hsx-dbg`) that owns session management, symbol resolution, breakpoints,
and resilient transport logic. The adapter has drifted from both the design
documents and the CLI feature set, leading to duplicated logic (e.g., breakpoint
mapping), brittle event handling, and inconsistent UX (decimal vs hex output, no
auto-reconnect).

v2 re-centers the VS Code debugger on the CLI debugger contracts described in
[04.09--Debugger.md](../../../04--Design/04.09--Debugger.md) and the refreshed
implementation notes. The adapter should reuse the same context/helpers as
`hsx-dbg` wherever possible so that fixes (e.g., connection loss recovery,
symbol caches, watch support) land in one place.

## Design & References

- **Design:** [04.09--Debugger.md](../../../04--Design/04.09--Debugger.md),
  [04.11--vscode_debugger.md](../../../04--Design/04.11--vscode_debugger.md)
- **Implementation notes:** [09--Debugger/03--ImplementationNotes.md](../09--Debugger/03--ImplementationNotes.md),
  [11--vscode_debugger/03--ImplementationNotes.md](./03--ImplementationNotes.md)
- **CLI debugger:** `python/hsx_dbg/*`
- **Executive session helper:** `python/executive_session.py`

## Guiding Principles

1. **Single source of truth:** VS Code adapter should import and reuse
   `hsx_dbg.context.DebuggerContext`, `SymbolIndex`, and `HistoryStore`
   equivalents instead of re-implementing RPC glue.
2. **Feature parity:** Everything exposed via CLI (breakpoints, watches, stack,
   memory, disassembly, observer mode) must surface in the IDE with matching
   semantics.
3. **Robust transport:** Error handling, keepalive, and reconnect logic must
   match the CLI’s new Phase 5.4 behavior.
4. **Traceability:** Every DAP event/request must map to a documented debugger
   command so tests can leverage both CLI and adapter fixtures.

---

## Phase 0 – Inventory & Alignment

**Goal:** Capture the current shape of the adapter, document drifts from the CLI
debugger, and ground the plan in the latest study/design notes.

- [ ] Review the existing adapter stack (`vscode-hsx/src/extension.ts`,
      `debugAdapter/hsx-dap.py`, `python/hsx_dap/*`, legacy `python/hsxdbg/*`)
      and document findings in `11--vscode_debugger/03--ImplementationNotes.md`.
- [ ] Cross-reference design expectations from
      [04.11--vscode_debugger.md](../../../04--Design/04.11--vscode_debugger.md)
      and debugger protocol details from
      [04.09--Debugger.md](../../../04--Design/04.09--Debugger.md); record mismatches.
- [ ] Use `01--Study-v2.md` + the original study to enumerate which CLI features
      (auto-reconnect, observer mode, symbol handling) must be reused and ensure
      the notes explicitly map the adapter gaps back to those requirements.
- [ ] Define the adapter/CLI API boundary (shared backend module, event bridge,
      breakpoint/store reuse) and log decisions in ImplementationNotes.

---

## Phase 1 – Adapter Core Refactor

**Focus:** Replace bespoke RPC glue with shared debugger infrastructure.

1. **Shared context module**
   - [ ] Extract a reusable `DebuggerBackend` (wrapping `DebuggerContext`) that
         exposes async-friendly APIs for DAP handlers.
   - [ ] Ensure backend exposes cancellation-aware helpers for attach/detach,
         symbol loading, breakpoint operations, and event subscription.
   - [ ] Update CLI + adapter to import the shared backend (no logic forks).
2. **DAP transport cleanup**
   - [ ] Harden the DAP base class with message validation, logging, and JSON
         schema enforcement (carry over Phase 5 logging improvements).
   - [ ] Add unit tests for content-length parsing, cancellation tokens, and
         error replies.

Deliverable: Adapter boots, initializes, and shares the same context/symbol
stores as CLI. No functional parity yet.

### Phase 1 Status (2025-11-11)

- Completed: `python/hsx_dbg/backend.py` now exposes `DebuggerBackend` plus typed
  helpers (registers/stack/watch/memory) and is exported via `hsx_dbg.__init__`;
  regression tests (`python/tests/test_hsx_dbg_backend.py`, existing hsx_dbg
  suites) run cleanly with `python -m pytest`.
- Completed: `hsx_dbg.symbols.SymbolIndex` carries PC metadata, locals/globals,
  and completion helpers, enabling both CLI and adapter clients to resolve
  symbols without the legacy `SymbolMapper`.
- Completed: `hsx-dap` now constructs a `DebuggerBackend`, routes all pause/
  resume/step/stack/watch/memory/breakpoint calls through it, streams events via
  `ExecutiveSession.start_event_stream`, and the obsolete `python/hsxdbg/*`
  modules have been removed.

### Phase 1 – Immediate Work Items

Completed (Nov 2025):

- Adapter now uses `DebuggerBackend` exclusively; all RPC helpers (resume/pause,
  stack/registers, watches/memory, breakpoints) call the shared backend, event
  streaming comes from `ExecutiveSession`, and transport keepalive matches the
  CLI path.
- Legacy `python/hsxdbg/*` (SessionManager, CommandClient, EventBus, caches)
  removed after confirming the backend wiring passes the hsx_dbg regression
  suite. Future adapter tests should rely on backend fakes instead of the
  deleted modules.

---

## Phase 2 – Session & Breakpoint Pipeline

**Focus:** Align all session/breakpoint flows with the CLI debugger.

1. **Session management**
   - [ ] Adapter uses backend attach/detach/observer APIs (no direct RPC).
   - [ ] Support auto-reconnect + keepalive via `executive_session` retry logic.
   - [ ] Surface connection errors to VS Code (status bar + `showErrorMessage`).
2. **Breakpoint orchestration**
   - [ ] Map `setBreakpoints` requests to backend breakpoint APIs, keeping the
         CLI’s symbol resolution, disabled-breakpoint tracking, and hex output.
   - [ ] Ensure breakpoint removal/disable flows clean up both adapter state and
         executive state (per CLI Phase 3.2 fixes).
   - [ ] Add tests comparing CLI vs DAP breakpoint tables (golden JSON fixtures).
3. **Launch/attach parity**
   - [ ] Support both launch (spawn executive) and attach (connect to existing
         executive) using shared code paths.
   - [ ] Reuse CLI `symbols` command logic for `.sym` discovery (workspace
         relative, overrides, fallback prompts).

Deliverable: Breakpoints and session lifecycle behave identically in CLI and
VS Code, with shared caches and logging.

### Phase 2 Readiness (2025-11-11)

- Session lifecycle plumbing now routes through `DebuggerBackend`: launch/attach
  honor observer mode + keepalive/heartbeat overrides, and connection loss
  triggers a reconnect that reapplies breakpoints/watches. Remaining gaps focus
  on surfacing connection state to VS Code (status bar + notifications) and
  ensuring CLI-style auto-retry telemetry is exposed.
- Available inputs: CLI keepalive/retry logic has regression tests
  (`python/tests/test_hsxdbg_session.py`) and `SymbolIndex` now provides the
  same mapping data the CLI `break`/`symbols` commands consume.
- Required setup: once Phase 1 rewiring lands, port the CLI bootstrap flags
  (observer mode, symbol search paths, keepalive interval) into the VS Code
  configuration surface so Phase 2 can immediately validate launch/attach
  parity.

### Phase 2 – Detailed Work Items

1. **Session lifecycle parity**
   - DAP `initialize`/`launch`/`attach` must call into `DebuggerBackend` attach
     helpers, enabling observer mode, PID locks, and heartbeat timers defined in
     04.09 §5.1. Integrate `executive_session` retry callbacks so reconnects
     reuse the CLI-tested logic, and emit VS Code UI notifications for lock
     conflicts or connection loss.
2. **Breakpoint orchestration**
   - Replace the remaining `CommandClient` breakpoint RPC calls with
     `DebuggerBackend` equivalents, feed every `setBreakpoints`/`setFunctionBreakpoints`
     request through `SymbolIndex`, and reuse the CLI disabled-breakpoint tracking
     so VS Code and CLI share identical breakpoint IDs/hex formatting. Add golden
     JSON fixtures comparing CLI vs adapter tables.
3. **Launch/attach workflow**
   - Teach the adapter to reuse the CLI symbol discovery rules (workspace-root
     defaults, `symbolPath` overrides, prompts when missing) and to share the
     same logging + history metadata when spawning or attaching to an executive.
     Update `vscode-hsx` configuration snippets so users can opt into observer
     mode, keepalive overrides, and custom symbol search paths.

---

## Phase 3 – Event, Stack, and Watch Integration

**Focus:** Stream executive events through the backend and translate them into
DAP notifications.

1. **Event bus refactor**
   - [ ] Adapter subscribes via backend `start_event_stream()` and registers a
         queue that feeds `stopped`, `continued`, `output`, and custom telemetry.
   - [ ] Implement backlog draining + acknowledgement identical to CLI worker,
         preventing the “events unsubscribed session_id=None” issue.
2. **Stack/variables/watch parity**
   - [ ] `stackTrace`, `scopes`, `variables`, and watch expressions leverage
         backend caches; no duplicate symbol lookups.
   - [ ] Provide disassembly/memory context when source is unavailable (reuse
         CLI formatting so addresses appear in hex).
3. **Error/notification UX**
   - [ ] Translate backend `ConnectionLostError`/`ProtocolVersionError` into
         DAP `error` responses with actionable VS Code messages.
   - [ ] Add telemetry for retry counts, reconnect success/failure.

Deliverable: Stepping, stack inspection, watches, and events feel the same as
the CLI, and the adapter no longer drops subscriptions.

---

## Phase 4 – VS Code UX & Configuration

1. **Launch configs & settings**
   - [ ] Update `package.json` configuration snippets to match new backend
         options (`observerMode`, `symbolPath`, `keepaliveInterval`, etc.).
   - [ ] Provide quick-pick UI for selecting running tasks / sessions.
2. **Views & decorations**
   - [ ] Align register/memory/disassembly views with CLI formatting
         (hex addresses, ASCII gutters).
   - [ ] Add log channel that mirrors CLI `hsx-dbg` output (timestamps, levels).
3. **Documentation**
   - [ ] Author `docs/vscode_adapter.md` describing architecture, shared
         backend, reconnection behavior, and debugging tips.
   - [ ] Update README/CHANGELOG with migration notes for existing users.

Deliverable: VS Code extension that feels first-class, with settings/docs that
mirror the CLI debugger.

---

## Phase 5 – Testing & Automation

1. **Unit & integration tests**
   - [ ] Add adapter-level tests using DAP client harness (cover initialize,
         launch, breakpoints, stepping, failure paths).
   - [ ] End-to-end tests that drive both CLI and VS Code adapter against the
         same simulated executive to ensure parity.
2. **CI integration**
   - [ ] Extend existing pipelines to run adapter tests on Linux/macOS/Windows.
   - [ ] Publish HTML/JSON test artifacts for VS Code’s “Run Tests” tab.

Deliverable: Automated coverage preventing regressions between CLI and adapter.

---

## Definition of Done

- Shared debugger backend module used by both CLI and VS Code adapter.
- VS Code extension supports all CLI debugger features (session mgmt, symbols,
  breakpoints, watches, stack, memory, disassembly, observer mode).
- Robust error handling with auto-reconnect and clear protocol mismatch
  messaging.
- Documentation updated (architecture, settings, troubleshooting).
- Tests cover both CLI parity and DAP-specific behaviors.
- Git logs capture each phase as commits (reference this v2 plan in PR).

---

## Next Steps

1. Kick off Phase 2 using the new backend: migrate session/keepalive flows,
   breakpoint orchestration, and launch/attach parity directly on top of
   `DebuggerBackend`.
2. Fill out adapter-level tests (DAP harness) that exercise the backend wiring
   before layering on Phase 2 behavior, then automate them in CI.
3. Continue updating `03--ImplementationNotes.md` and this plan as each phase
   lands; retire 02--ImplementationPlan.md once all v2 phases are complete.
