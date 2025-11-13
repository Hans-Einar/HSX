# HSX VS Code Debug Stack – Code Review & Gap Analysis
**Date:** 2025-11-13  
**Reviewer:** Codex (GPT-5)  
**Scope:** `vscode-hsx` extension, `python/hsx_dap`, `python/hsx_dbg`, `python/executive_session.py`, `python/execd.py`, `platforms/python/host_vm.py`

## References
- VS Code debugger design ([main/04--Design/04.11--vscode_debugger.md](../../04--Design/04.11--vscode_debugger.md))
- Source/disassembly supplement ([main/04--Design/TUI-SourceDisplay-VSCode.md](../../04--Design/TUI-SourceDisplay-VSCode.md))
- Executive architecture ([main/03--Architecture/03.02--Executive.md](../../03--Architecture/03.02--Executive.md))
- VS Code implementation plan v2 ([main/05--Implementation/01--GapAnalysis/11--vscode_debugger/ImplementationPlan.md](./11--vscode_debugger/ImplementationPlan.md))

## Key Findings
- Step requests sent by the VS Code adapter never enable the executive’s source-aware stepping path, so “step over/into” degrade to raw single-instruction steps and drift from the documented UX.
- Pause handling emits a synthetic `stopped` event before the executive confirms the halt, then immediately re-queries `ps`; a stale `running` snapshot produces a `continued` event and the real `task_state` notification is suppressed. This exactly matches the “paused in executive, running in VS Code” symptom.
- `_emit_stopped_event` can raise `UnboundLocalError` when the executive pauses without a PC field, cutting the debug session.
- Mailbox/sleeping states and `trace_step` events are ignored even though the design requires the UI to show why execution halted, so VS Code stays in “running” while the executive is blocked on IPC.
- Remote-breakpoint and task-list polling treat transient `bp list` / `ps` timeouts as fatal. The adapter falls into an endless reconnect/reapply loop (`hsx-dap-debug.log:929-968`), which also prevents the user from single-stepping assembler code reliably.
- `_schedule_pause_fallback` is dead code; there is no recovery path if the executive drops a `user_pause` event, contradicting the new adapter plan’s “robust transport” goal.

## Detailed Findings by Layer

### 1. VS Code Debug Adapter (`python/hsx_dap/__init__.py`)
1. **Source-level stepping not wired.** `_handle_next`, `_handle_stepIn`, `_handle_stepOut`, and `_handle_stepInstruction` always call `DebuggerBackend.step(..., source_only=False)` and immediately synthesize a `stopped` event (`python/hsx_dap/__init__.py:427-460`). The executive already implements `source_only` skipping of compiler-only instructions (`python/execd.py:3435-3479`, validated by `python/tests/test_executive_sessions.py:1329-1351`) and the design explicitly distinguishes “Step Source” vs “Step Instruction” (`main/04--Design/TUI-SourceDisplay-VSCode.md:121-129`). Because the adapter never flips the flag nor waits for the executive’s `task_state/debug_break` reply, the VS Code UX can neither step per source line nor preserve mailbox pauses, which explains the “single stepping assembler” regression.

2. **Pause/continue race reverts the UI to running.** `_handle_pause` sends a synthetic `stopped` event and immediately calls `_synchronize_execution_state` (`python/hsx_dap/__init__.py:379-425`). That sync performs `list_tasks` (`python/hsx_dap/__init__.py:2330-2397`) and feeds the snapshot back into `_handle_task_state_event`. If `ps` still reports `running`, `_handle_task_state_event` emits `continued` (`python/hsx_dap/__init__.py:2249-2297), then the real `user_pause` event is dropped because `_synthetic_pause_pending` is still `True`. The dead `_schedule_pause_fallback` helper (`python/hsx_dap/__init__.py:389-397`, never invoked anywhere) means we have no way to recover when the executive’s notification is delayed, leaving VS Code “running” although the executive is halted—exactly the behaviour described.

3. **`pc_int` may be undefined.** `_emit_stopped_event` references `pc_int` outside the `if pc is not None` block (`python/hsx_dap/__init__.py:2207-2246`). Any `task_state` event without a `pc` (mailbox waits, scheduler stops) will raise `UnboundLocalError`, terminate the adapter, and tear down the debug session. This also prevents the UI from reacting to pauses that lack PC info.

4. **Blocked-state events are ignored.** The adapter subscribes to `mailbox_wait/wake/timeout` (`python/hsx_dap/__init__.py:174-184`) but `_handle_exec_event` treats only `task_state`, `debug_break`, stdio, warnings, and `watch_update` (`python/hsx_dap/__init__.py:1029-1073`). Additionally, `_handle_task_state_event` emits `stopped` events only when `state in {"paused","stopped"}` or `reason == "user_pause"` (`python/hsx_dap/__init__.py:2249-2297`). The executive design says mailbox waits and sleeping states should be observable (`main/03--Architecture/03.02--Executive.md:66-74`), and `_process_vm_events` publishes `mailbox_wait/mailbox_timeout` plus `trace_step` events (`python/execd.py:4304-4326`). Because the adapter drops them, VS Code never shows “waiting on mailbox X” and keeps the thread marked as “running”, hiding the real halt reason.

5. **Trace events never reach the IDE.** `_EVENT_CATEGORIES` omits `trace_step`, so instruction retire events are never streamed, yet `_emit_disassembly_refresh_event` is only fired on manual stops. This contradicts the design’s requirement to drive the disassembly view from the trace stream (same references as above).

6. **Aggressive polling thrashes the executive.** `_sync_remote_breakpoints` and `_synchronize_execution_state` invoke `bp list` and `ps` on timers (`python/hsx_dap/__init__.py:1521-1566`, `2068-2108`, `2330-2397`). When the executive is busy, those RPCs time out, the adapter retries through `_attempt_reconnect`, and it replays the entire breakpoint set on every loop. The live log shows continuous failures (`hsx-dap-debug.log:929-968`), which explains why known-good configurations regress to “step once / reconnect / lose breakpoints.” The implementation plan’s robust transport goal (lines 30-39) is therefore unmet.

### 2. Debugger Backend & Session Layer
- The backend honours `source_only`, `trace`, `watch`, and event-stream contracts (`python/hsx_dbg/backend.py`, `python/executive_session.py`), but the adapter bypasses most of the resilience hooks. For example, `_event_stream_worker` already maintains a buffer and acknowledges sequences, so relying on synchronous `ps` after every pause is unnecessary churn. Aligning the adapter with the backend’s cached stack/task helpers would avoid the `ps` storms seen in the log.

### 3. Executive & VM (`python/execd.py`, `platforms/python/host_vm.py`)
- The executive already exposes the mechanisms we need (source-only stepping, detailed task states, mailbox events, `debug_event` metadata in `_step_once`). None of these are used upstream, so the issues above originate from the adapter layer rather than the runtime.

## Recommendations & Next Steps
1. **Step semantics:** Use `source_only=True` for `next/stepIn/stepOut`, surface the executive’s response (`running`, `events`, `debug_event`), and only emit DAP `stopped` once the runtime reports a halt. Honour instruction stepping (no source-only flag) separately.
2. **Pause flow:** Wire `_schedule_pause_fallback`, delay `_synchronize_execution_state` until either the event stream confirms the halt or the fallback timer fires, and remove the `_synthetic_pause_pending` suppression so the real `task_state` update reaches VS Code.
3. **Stopped-event fix:** Initialize `pc_int = None` outside the conditional and guard `_suppress_duplicate_stop` accordingly.
4. **State coverage:** Treat `waiting_mbx`, `sleeping`, and scheduler reasons as stoppable states (map them to `reason` codes), and handle `mailbox_*`/`trace_step` events to keep the UI in sync with the executive diagram.
5. **Polling discipline:** Replace the periodic `ps`/`bp list` polling with event-driven reconciliation (or at minimum, make failures non-fatal and exponential back-off). The log evidence shows the current loop can never settle.
6. **Document alignment:** Update the adapter backlog (ImplementationPlan §Phase 2) with the issues above so work remains traceable to the design requirements.

Addressing these items will stop the regression loop (“fix one thing, break another”), unblock reliable single-stepping in both source and assembler views, and ensure VS Code reflects the executive’s true state.
