# Code Review Implementation Plan
**Date:** 2025-11-13  
**Owner:** HSX Debug Stack Team  
**Scope:** Close the gaps documented in `codeReview.md` across VS Code extension, `python/hsx_dap`, `python/hsx_dbg`, executive session helpers, and `execd.py`.

## Phase 0 – Containment & Stabilization
**Goal:** Stop user-visible thrash (endless reconnects, phantom continued events) while deeper fixes land.

- [x] Add exponential/back-off gating around `_sync_remote_breakpoints` / `_synchronize_execution_state` retries so transient `bp list` / `ps` failures do not trigger reconnect storms (`python/hsx_dap/__init__.py:1521-1566`, `2068-2108`).
- [x] Preserve the last known-good breakpoint set during reconnect and only reapply when the executive reports drift (`hsx-dap-debug.log:929-968` evidence).
- [x] Emit telemetry/output warnings whenever the adapter enters degraded transport mode so users understand why stepping pauses.

## Phase 1 – Step Semantics & Instruction Control
**Goal:** Match the design’s source-vs-instruction behaviour so single-stepping assembler/source is reliable again.

- [x] Route Step Over/Into/Out through `DebuggerBackend.step(..., source_only=True)` and fall back to instruction stepping when `source_kind` metadata is missing (`python/tests/test_executive_sessions.py:1342-1350`).
- [x] Remove synthetic `stopped` events from `_handle_next`/`_handle_stepIn`/`_handle_stepOut` and wait for `debug_break`/`task_state` confirmation (with bounded timeout) before notifying VS Code.
- [x] Keep instruction-step breakpoint suppression but guarantee disabled breakpoints are restored even if the backend call fails.

## Phase 2 – Pause & Task-State Synchronization
**Goal:** Ensure VS Code mirrors the executive when pausing, sleeping, or waiting on IPC.

- [ ] Invoke `_schedule_pause_fallback` before issuing `pause`, emit DAP `stopped` when the executive confirms or when the fallback timer fires (`python/hsx_dap/__init__.py:379-425`).
- [ ] Stop calling `_synchronize_execution_state` immediately after `pause`; rely on streamed events and trigger resync only on reconnect.
- [ ] Initialize `pc_int = None` in `_emit_stopped_event` so PC-less states (wait/sleep) do not crash the adapter (`python/hsx_dap/__init__.py:2207-2246`).
- [ ] Treat `waiting_mbx`, `sleeping`, scheduler transitions, etc., as stoppable reasons and surface descriptor/deadline details in the DAP event.

## Phase 3 – Event & Telemetry Coverage
**Goal:** Expose the runtime information promised by the architecture/design docs.

- [ ] Handle `mailbox_wait/wake/timeout`/`sleep_*` events in `_handle_exec_event`, updating thread state and stop descriptions with descriptor/timeout metadata.
- [ ] Add `trace_step` to `_EVENT_CATEGORIES` and drive disassembly/PC follow logic from streamed trace events instead of polling.
- [ ] Use backend/session caches (e.g., `DebuggerBackend.list_tasks`, `ExecutiveSession.stack_info`) instead of synchronous `ps` after every stop.

## Phase 4 – Regression Tests & Tooling
**Goal:** Prevent recurrence and document guarantees for IDE users.

- [ ] Extend `python/tests/test_hsx_dap_harness.py` with pause/step/mailbox cases to lock in the new behaviour.
- [ ] Capture an end-to-end VS Code scenario (e.g., `examples/demos/longrun`) demonstrating source-level stepping, mailbox waits, and reconnect recovery.
- [ ] Update `vscodeDebugStackImplNotes.md`, VS Code README, and release notes to describe the pause fallback, event coverage, and remaining limitations.
- [ ] Emit structured telemetry when fallback paths trigger (pause timeout, reconnect thrash) so logs remain actionable.

## Dependencies & Coordination
- Executive already supports the required protocols (`execd.py` `step(source_only=True)`, mailbox events). No runtime changes are necessary beyond optional logging.
- Ensure VS Code extension packaging pulls the updated adapter Python files (`vscode-hsx/debugAdapter/hsx-dap.py` launcher still loads `python/hsx_dap`).
- Coordinate with toolkit team if shared `hsx_dbg` helpers need API tweaks (e.g., exposing cached task snapshots).

## Definition of Done

- [ ] All phase tasks above implemented and code-reviewed.
- [ ] Adapter + CLI regression suites pass locally and in CI.
- [ ] Manual validation covers pause/resume, source/instruction stepping, mailbox waits, and reconnect-after-restart (documented in `main/05--Implementation/vscodeDebugStackImplNotes.md`).
- [ ] Documentation and changelog entries updated in `vscode-hsx`.
