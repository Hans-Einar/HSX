# Debugger (CLI/TUI) Implementation Plan

## DR/DG Alignment
- DR-8.1 / DG-8.1–8.3: Event-driven debugger with PID locks, panels, automation.
- DR-5.1 / DG-5.2: Honour scheduler contract + per-step semantics.

## Implementation Notes
- Build hsxdbg core: session manager, event bus, state cache (refactorNotes item on debugger session/event streaming).
- Implement drop-handling/resync logic (events.ack, since_seq) with UI feedback.
- Provide commit log + test harness referencing DO-relay for future on-target adapters.

## Playbook
- [ ] Flesh out hsxdbg.events bus (bounded queues, filtering).
- [ ] Implement CLI REPL + TUI panels (Textual) referencing DG-8.1.
- [ ] Add scripting/JSON mode for automation.

## Commit Log
- _Pending_.
