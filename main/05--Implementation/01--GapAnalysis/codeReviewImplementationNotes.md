# Code Review Implementation Notes
**Date:** 2025-11-13  
**Scope:** Phase 0 work items from `codeReviewImplamentationPlan.md`

## Adapter Stabilization
- Added per-subsystem backoff timers for remote breakpoint sync and task-state synchronization (`python/hsx_dap/__init__.py:225-228`, `1180-1189`, `1578-1615`, `2163-2189`, `2490-2537`).  
  When `bp list` / `ps` calls time out, we now pause retries (up to 30 s), emit telemetry about the degraded mode, and resume only after the timer expires.
- Updated `_schedule_remote_breakpoint_poll` to honor the backoff delay and keep the timer from hammering the executive during error periods.

## Breakpoint Preservation
- `set_breakpoint` helpers re-raise `DebuggerBackendError`, allowing `_reapply_pending_breakpoints` to detect transport failures and requeue the entire backlog instead of losing user breakpoints (`python/hsx_dap/__init__.py:1708-1752`, `1812-1821`).
- `_reapply_pending_breakpoints` now skips work during backoff, reschedules remaining sources after the first failure, and sends DAP telemetry when we enter degraded mode (`python/hsx_dap/__init__.py:1844-1907`).

## Observability
- Introduced `_emit_transport_warning` to surface backoff state in the VS Code debug console / telemetry stream (`python/hsx_dap/__init__.py:1183-1189`), satisfying the “make degraded modes obvious” requirement.

## Regression Coverage
- Re-ran `pytest python/tests/test_hsx_dap_harness.py` (now 19 passing tests) to ensure the new control flow does not regress existing behaviour.

---

## Phase 1 – Step Semantics & Instruction Control
- Step Over/Into/Out now call `DebuggerBackend.step(..., source_only=True)` and rely on runtime events for final state updates. Synthetic `stopped` events were removed; instead we track `_pending_step` and wait for `task_state`/`debug_break` notifications (`python/hsx_dap/__init__.py:363-476`, `1180-1224`, `1844-1907`, `2310-2395`).
- Added a bounded fallback timer (`_schedule_step_fallback`) so VS Code still updates if the executive fails to emit a pause event. The fallback emits telemetry and reuses `_synchronize_execution_state` for accuracy.
- Instruction stepping retains breakpoint suppression but now also funnels through the new `_after_step_request` flow to stay consistent with the other step types (`python/hsx_dap/__init__.py:441-474`).
- Updated the DAP harness test `test_step_instruction_request` to assert the deferred notification pathway (`python/tests/test_hsx_dap_harness.py:418-451`).
