# Executive Implementation - Agent Guide

Welcome! This guide explains how to pick up work in the Executive module.

## 1. Read First
- `../GrandImplementationPlan.md` for overall sequencing.
- `02--ImplementationPlan.md` for detailed phase tasks.
- `../GrandImplementationNotes.md` (once populated) to see cross-module status.

## 2. Current Priority
- Phase 1 (Python only):
  1. Session management (`session.open/close/keepalive`, PID locks, timeouts).
  2. Event streaming foundation (bounded buffers, subscribe/unsubscribe/ack, routing VM `trace_step` events).
  3. Breakpoint RPCs (depends on #2).

## 3. Workflow
1. Pick an open item from the plan (respect dependencies - session work before events, etc.).
2. Update `ImplementationNotes.md` (see scaffold) with:
   - Date, initials.
   - Task summary.
   - Status: TODO / IN PROGRESS / DONE / BLOCKED.
   - Tests run + outcomes.
3. Keep work Python-only unless the plan explicitly calls for a C port.

## 4. Testing
- Use targeted pytest modules (e.g., `python/tests/test_executive_*` once they exist).
- Document commands and results in `ImplementationNotes.md`.
- If tests cannot run, note blockers and next actions.

## 5. Hand-off
- Ensure `ImplementationNotes.md` reflects current state.
- If a git entry is needed, update `../GrandImplementationNotes.md` or the stack-specific log after changes land.
- Leave TODOs for follow-up agents if work is partial.

Happy hacking!
