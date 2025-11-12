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

**Goal:** Identify gaps between the existing adapter implementation and the new
debugger interface.

- [ ] Audit current adapter entry point (`python/hsx_dap/__init__.py`) and note
      where it diverges from `hsx_dbg` context/helpers.
- [ ] Document missing CLI features (observer mode, watch, stack cache, etc.)
      in `11--vscode_debugger/03--ImplementationNotes.md`.
- [ ] Define adapter/CLI API boundary (e.g., shared `SessionManager` module).

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

1. Finish Phase 0 inventory and update ImplementationNotes with identified gaps.
2. Prioritize Phase 1 shared-backend work so later phases inherit the new
   abstractions.
3. Track progress using this v2 plan alongside the legacy plan until migration
   completes; retire 02--ImplementationPlan.md once all phases here are complete.

