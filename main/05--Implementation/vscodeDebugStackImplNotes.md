# VS Code Debug Stack Implementation Notes

## 2025-11-10 — Kickoff

- Scope: Toolkit Phase 1 alignment for VS Code debugger stack.
- References reviewed: `04.06--Toolkit.md`, `04.09--Debugger.md`, `TUI-SourceDisplay-VSCode.md`, `main/05--Implementation/vscodeDebugStackPlan.md`.
- Decision: focus hsxdbg deliverables on transport/session/command layers needed by the DAP adapter, defer TUI-specific panels and Textual layouts.
- Action items:
  - Create `python/hsxdbg/` package scaffold with placeholders for transport/session/events/cache/commands`.`
    - ✅ Added package structure plus smoke test (`python/hsxdbg/*`, `python/tests/test_hsxdbg_package.py`).
  - Update toolkit plan checklist to flag VS Code priorities vs. deferred TUI work.
  - Establish test harness for hsxdbg components (pytest-based).
- Follow-ups:
  - Executive readiness audit for debugger RPC completeness (pending).
  - Document any deviations from toolkit plan once implementation begins.
