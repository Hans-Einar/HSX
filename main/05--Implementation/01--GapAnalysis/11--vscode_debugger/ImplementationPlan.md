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

- [x] Review the existing adapter stack (`vscode-hsx/src/extension.ts`,
      `debugAdapter/hsx-dap.py`, `python/hsx_dap/*`, legacy `python/hsxdbg/*`)
      and document findings in `11--vscode_debugger/03--ImplementationNotes.md`.
- [x] Cross-reference design expectations from
      [04.11--vscode_debugger.md](../../../04--Design/04.11--vscode_debugger.md)
      and debugger protocol details from
      [04.09--Debugger.md](../../../04--Design/04.09--Debugger.md); record mismatches.
- [x] Use `01--Study-v2.md` + the original study to enumerate which CLI features
      (auto-reconnect, observer mode, symbol handling) must be reused and ensure
      the notes explicitly map the adapter gaps back to those requirements.
- [x] Define the adapter/CLI API boundary (shared backend module, event bridge,
      breakpoint/store reuse) and log decisions in ImplementationNotes.

---

## Phase 1 – Adapter Core Refactor

**Focus:** Replace bespoke RPC glue with shared debugger infrastructure.

1. **Shared context module**
   - [x] Extract a reusable `DebuggerBackend` (wrapping `DebuggerContext`) that
         exposes async-friendly APIs for DAP handlers.
   - [x] Ensure backend exposes cancellation-aware helpers for attach/detach,
         symbol loading, breakpoint operations, and event subscription.
   - [x] Update CLI + adapter to import the shared backend (no logic forks).
2. **DAP transport cleanup**
   - [x] Harden the DAP base class with message validation, logging, and JSON
         schema enforcement (carry over Phase 5 logging improvements).
   - [x] Add unit tests for content-length parsing, cancellation tokens, and
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
  (`python/tests/test_hsx_dbg_backend.py`) and `SymbolIndex` now provides the
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

### Phase 2 – In-flight Updates (2025-11-11)

- Function breakpoints now resolve via `SymbolIndex`, hit the shared
  `DebuggerBackend` for installation, and persist their specs so reconnects
  reapply them alongside source breakpoints/watch expressions.
- The new lightweight DAP harness exercises launch/observer plumbing,
  reconnect behavior, stackTrace/scopes/variables, and both source/function
  breakpoints without requiring a live executive, giving us fast regression
  coverage as Phase 2 continues.

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

## Phase 6 – Breakpoint & Connection Resiliency (migrated from CLI plan)

**Context:** Phase 8 from the CLI debugger plan described adapter-specific resiliency work. The detailed todo list now lives here so the VS Code stack owns the end-to-end experience.

### 6.1 PID Loss & Reconnect UX

- [x] Detect `unknown pid` errors after reconnect, rerun `ps`, and either update `current_pid` or emit a fatal “target exited” status/console message.
- [x] Emit telemetry + VS Code notifications when a PID disappears so users know to relaunch.
- [x] Extend the hsx_dap harness with a backend stub that simulates PID loss mid-session to cover the new logic (`python/tests/test_hsx_dap_harness.py`).

### 6.2 Instruction Breakpoints & Disassembly Refresh

- [x] Implement `setInstructionBreakpoints` to allow breakpoints directly from the disassembly tree (reusing `DebuggerBackend` APIs).
- [x] Auto-refresh disassembly on every `stopped` event (breakpoint hits included) and ensure requests always send a non-zero `instructionCount`.
- [x] Add harness tests verifying instruction breakpoints hit and the disassembly panel populates after breakpoint stops.

### 6.3 Breakpoint Synchronization

- [x] Subscribe to executive breakpoint events (or poll) so VS Code reflects breakpoints created outside the adapter (CLI/executive UI).
- [x] Reconcile local vs remote breakpoint sets after reconnect, removing stale entries and surfacing newly added ones via `_sync_remote_breakpoints()`.
- [x] Document mixed breakpoint workflows and add telemetry when external breakpoints are synced (docs + VS Code notifications).

Deliverable: VS Code cleanly handles PID exits, cross-source breakpoints, and post-stop disassembly refresh without relying on the CLI plan for tracking.

---

## Phase 7 – Disassembly Remediation & VS Code Parity

**Priority:** HIGH  
**Dependencies:** Phase 4 (disassembly CLI), Executive Phase 1.6 (Disassembly API), Toolchain Phase 3 (.sym metadata), VS Code adapter Phase 2.6  
**Estimated Effort:** 5-7 days

**Rationale:**  
Design §5.5.7 in [04.09--Debugger.md](../../../04--Design/04.09--Debugger.md#L459) and the HXE format spec (`docs/hxe_format.md`) require the executive to return real MVASM instructions with symbol/source annotations. Current output shows all-zero words in the VS Code disassembly panel (`hsx-dap-debug.log` sample), meaning the adapter cannot render mnemonics or operands. Root causes: the executive decodes from the task RAM mirror instead of the immutable code image (`python/execd.py:2099-2199`), `_format_disassembly` drops operand strings, and the RPC surface still exposes the legacy `cmd:"disasm"`/`mode:"cached"` contract rather than the documented `disasm.read` around-PC behavior. This phase restores spec compliance and keeps the VS Code extension in lockstep with the CLI tooling.

### 7.1 Executive Instruction Source & Annotation

**Priority:** HIGH  
**Dependencies:** Executive VM controller (`platforms/python/host_vm.py`), symbol loader  
**Estimated Effort:** 2 days

**Todo:**
- [x] Document the current mismatch (code lives in `MiniVM.code`, `disasm_read` reads `vm.read_mem`) and capture reproduction steps in `main/05--Implementation/01--GapAnalysis/09--Debugger/03--ImplementationNotes.md`.
- [x] Introduce a safe way to fetch instruction bytes (e.g., `MiniVM.read_code` or copying the HXE code section into the task snapshot) so `disasm_read` always decodes from the executable image, not mutable RAM.
- [x] Ensure symbol and source annotations are preserved when switching buffers (`symbol_lookup_addr/line` already provide metadata; keep offsets so labels render only at function entries).
- [x] Update caching/invalidation so cached disassembly is keyed on code bytes + pid; expire caches automatically on reload/unload.
- [x] Extend `python/tests/test_executive_sessions.py::test_disasm_read_basic` (and add new tests) to assert the byte stream mirrors the .sym metadata and that BRK/JMP opcodes round-trip.

### 7.2 VS Code Adapter & Tree View Formatting

**Priority:** HIGH  
**Dependencies:** Phase 2.6 (DAP backend reuse)  
**Estimated Effort:** 1-2 days

**Todo:**
- [x] Update `HSXDebugAdapter._format_disassembly` to consume operand *strings* as emitted by `disasm_util.format_operands` (fallback to list join when structured operands are added later) so mnemonics render as `LDI R1 <- 0x5`.
- [x] Ensure location metadata uses the canonical `{directory, file}` pairs coming from the executive rather than only `line.file` strings.
- [x] Expand adapter unit tests to cover operand rendering, symbol labels, and source click-through (e.g., add fixtures under `python/tests/test_hsx_dap_disassembly.py`).
- [x] Refresh the VS Code tree view copy/highlight logic so the PC-highlight icon only appears when the decoded address matches `referenceAddress`, and ensure copy-to-clipboard paths include operands and `; file:line` annotations.

### 7.3 Protocol Alignment & Client UX

**Priority:** MEDIUM  
**Dependencies:** Executive RPC layer, DAP transport  
**Estimated Effort:** 1-2 days

**Todo:**
- [x] Add the documented `cmd:"disasm.read"` entry point alongside the legacy `disasm` command; honor `mode:"around_pc"` (split `count` before/after the PC) and `mode:"from_addr"` semantics from the design.
- [x] Have the adapter request `mode:"around_pc"` + `addr: current_pc` by default to reduce bespoke window math in the extension, but keep backward-compatible behavior when running against older executives.
- [x] Update CLI (`hsx-dbg`) and VS Code docs to mention the new capability negotiation flag so other clients can detect when disassembly is unavailable.
- [x] Extend RPC tests (e.g., `python/tests/test_executive_sessions.py`) to cover the new request shape, cached/on-demand paths, and error handling when code bytes cannot be read.

### 7.4 Documentation & Telemetry

**Priority:** MEDIUM  
**Dependencies:** Completion of 7.1-7.3  
**Estimated Effort:** 1 day

**Todo:**
- [x] Update `docs/hsx_dbg_usage.md` (disassembly section) and `docs/hxe_format.md` (code/rodata handling) to reflect the fixed pipeline and any new flags.
- [x] Add troubleshooting notes to `main/04--Design/04.11--vscode_debugger.md` describing how the adapter surfaces disassembly errors in the Run/Debug view.
- [x] Instrument the adapter with debug logs summarizing opcode/operand counts (sampling) so regressions surface quickly in `hsx-dap-debug.log`.
- [x] Capture verification steps (CLI disasm, VS Code panel screenshot references) in Implementation Notes for traceability.

Deliverable: Disassembly requests (CLI + VS Code) now render full mnemonics/operands sourced from the immutable code image, with telemetry/tests guarding regressions.

---

## Phase 8 – Breakpoint & Connection Resiliency

**Priority:** HIGH  
**Dependencies:** Phase 3 (breakpoint/variable plumbing), Phase 7 (disassembly parity), vscode-hsx extension  
**Estimated Effort:** 5 days

**Rationale:**  
Phase 8 tracks the shared breakpoint/disassembly resiliency work that primarily lives inside the VS Code adapter. The CLI debugger already exposes the raw data; this section keeps the adapter’s status transparent so Phase 6 work remains auditable.

### 8.1 PID Loss & Reconnect UX

- **Status:** ✅ Completed. The adapter detects stale PIDs, emits telemetry/status notifications, and the `python/tests/test_hsx_dap_harness.py` suite exercises PID-loss scenarios.
- **CLI impact:** None. CLI `ps`/`status` already surface exited tasks; no extra work required.

### 8.2 Instruction Breakpoints & Disassembly Refresh

- **Status:** ◻ In progress. `setInstructionBreakpoints` support and harness coverage are complete, while the auto-refresh-on-stop behavior remains open inside this plan.
- **CLI impact:** The CLI disassembly commands already request non-zero instruction counts; no duplicate tracking is needed here.

### 8.3 Breakpoint Synchronization

- **Status:** ◻ In progress. Remote breakpoint reconciliation/telemetry stays owned by the adapter. `_sync_remote_breakpoints()` is implemented, but mixed-source UX/telemetry still needs final documentation polish.
- **CLI impact:** Continue exposing accurate `break list` output so adapter telemetry has a single source of truth.

Deliverable: VS Code stays resilient when PIDs churn, instruction breakpoints originate from multiple sources, and remote breakpoint reconciliation never diverges from the executive’s truth.

---

## Phase 9 – DAP ↔ Executive Interface Polish

**Goal:** Close the correctness gaps discovered during the dap → debugger → executive review so the adapter and backend report accurate state and expose the capabilities they already implement.

### 9.1 Preserve Full Breakpoint Addresses

References: Review Finding “list_breakpoints truncates addresses to 16 bits” (`python/hsx_dbg/backend.py:235-247`).

- [x] Update `DebuggerBackend.list_breakpoints` to mask addresses to `0xFFFFFFFF` (not `0xFFFF`) so high-memory breakpoints round-trip correctly.
- [x] Add regression coverage (unit test or harness fixture) that injects a breakpoint > `0x0001FFFF` and asserts the adapter receives the full address.
- [ ] Verify `_sync_remote_breakpoints` no longer reports phantom add/remove events when executive breakpoints live above 64 KiB.

### 9.2 Honor terminate Requests

References: Review Finding “supportsTerminateRequest advertised without handler” (`python/hsx_dap/__init__.py:251-266`).

- [x] Implement `_handle_terminate` to perform a graceful pause/detach/cleanup (reuse `_handle_disconnect` logic where possible) before emitting `terminated`.
- [ ] Wire VS Code’s stop button to call the new handler and document expected executive behavior (process exits vs detach).
- [x] Add a DAP harness test ensuring `terminate` succeeds and leaves the executive in a known state.

### 9.3 Advertise Instruction Breakpoints

References: Review Finding “instruction breakpoint capability hidden” (feature implemented in `_handle_setInstructionBreakpoints`, `python/hsx_dap/__init__.py:613-662`, but not advertised in `initialize`).

- [x] Set `supportsInstructionBreakpoints: true` in `_handle_initialize` and ensure capabilities mirror the adapter’s real surface.
- [ ] Confirm VS Code surfaces the native instruction breakpoint UX (gutter + palette command) without relying on custom tree view commands.
- [x] Extend existing capability tests to cover the new flag so regressions surface if the handler is removed.

### 9.4 Fail writes When Executive Rejects Them

References: Review Finding “writeMemory swallows backend errors” (`python/hsx_dap/__init__.py:785-831`).

- [x] Let `_handle_writeMemory` rethrow `DebuggerBackendError` (or convert it into a `success=false` response) instead of returning `bytesWritten: 0`.
- [ ] Surface the executive error message in VS Code so users know the write failed (notification + DAP response).
- [x] Add a harness test that forces a backend write failure and asserts the adapter reports the error to the client.

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

1. Finish the remaining Phase 6/8 work: ensure mixed-source breakpoint sync UX + documentation are complete and auto-refresh logic is verified end-to-end.
2. Track Phase 7 regressions by adding disassembly smoke tests to CI and capturing new troubleshooting docs/screenshots.
3. Expand adapter-level tests (Phase 5) so the harness covers the new breakpoint/disassembly flows and integrate them into CI.
4. Continue updating `03--ImplementationNotes.md` and this plan as each phase lands; retire 02--ImplementationPlan.md once all v2 phases are complete.
