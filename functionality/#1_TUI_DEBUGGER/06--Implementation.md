# Implementation Playbook — HSX Debugger Toolkit & TUI

> Use this document to coordinate day-to-day work. Update it whenever tasks start, finish, or change.

## Overview
- Feature: Unified debugger (CLI + shell + TUI) for HSX runtime
- Current status: not started
- Last updated: 2025-10-16

## Task Tracker

### F1 Architecture & platform study (`in progress`)
- [x] Step 1 — Evaluate transport abstraction (execd RPC vs direct VM) and session lifecycle
  - Notes:
    - Keep the debugger layered on top of the executive RPC: `ExecutiveState` in `python/execd.py:20` already multiplexes MiniVM instances, task state, and log buffers; a debugger session should bind here instead of embedding `MiniVM` directly.
    - Session lifecycle draft: `connect → handshake (protocol/version) → attach (vm + pid selection) → subscribe (event/log/mailbox streams) → run/step` with cached state mirrors → `detach/teardown`. Requires adding first-class session IDs plus long-lived subscriptions in `execd` (e.g., streaming `debug_stop` events emitted from `MiniVM.emit_event` in `platforms/python/host_vm.py:512`).
    - Direct `MiniVM` use is reserved for offline harnesses/tests; even there we route through the existing `VMController` façade to preserve compatibility and respect the single-task MiniVM constraint noted in `functionality/#1_TUI_DEBUGGER/(2)study.md`.
    - Follow-up actions: extend RPC with `session.open/session.close`, add event fan-out (mailbox or websocket-style stream), and document scheduler ownership boundaries in `(4)design.md`.
  - Artifacts:
    - Transport evaluation captured inline here; supporting references: `python/execd.py:20`, `platforms/python/host_vm.py:385`, `python/vmclient.py:1`, `functionality/#1_TUI_DEBUGGER/(2)study.md`.
- [x] Step 2 — Compare cross-platform TUI libraries (curses, textual, prompt_toolkit) and recommend choice
  - Notes:
    - `textual` (Rich-based) provides pane layout, async message pump, CSS-like theming, and Windows/macOS/Linux parity; ideal for live register/trace dashboards and integrates with asyncio loop used by the executive client. Downside: still pre-1.0, so we must pin a tested release and watch API churn.
    - `prompt_toolkit` excels at improving the CLI (multi-line editing, completion) but lacks native multi-pane layout; we can reuse it for enhanced shell mode while delegating full-screen TUI to another layer.
    - Legacy `urwid`/`npyscreen` offer mature curses abstractions but struggle with modern Windows terminals and async I/O; they would slow feature delivery and complicate packaging.
    - Recommendation: adopt `textual` for the debugger TUI, keep `prompt_toolkit` for CLI upgrades, and drop others. Capture dependency, packaging, and minimum Python (≥3.9) requirements in `(3)design.md`.
  - Artifacts:
    - Framework comparison summary above; to be formalised in `(4)design.md` with dependency matrix and acceptance criteria.

### F2 CLI / Interactive shell scaffolding (`not started`)
- [ ] Step 1 — Define command surface (attach, inspect, clock, breakpoints, etc.)
- [ ] Step 2 — Implement core command handlers and output formatting for scripting use

### F3 TUI implementation (`not started`)
- [ ] Step 1 — Build layout (register panel, trace, disassembly, auxiliary widgets)
- [ ] Step 2 — Wire live updates, navigation, and clock control hotkeys

### F4 Documentation, packaging, and validation (`not started`)
- [ ] Step 1 — Author user docs/help topics for CLI, shell, and TUI usage
- [ ] Step 2 — Finalise automated tests and cross-platform manual validation checklist

## Implementation Issues Log

| ID | Title | Status |
|----|-------|--------|
| I1 | _TBD_ | open |

### I1 `_placeholder` (`open`)
- **Summary:** Placeholder for future discoveries during design/implementation.
- **Study:** _pending_
- **Remediation:** _pending_
- **Implementation:**
  - Commits: _pending_
  - Tests: _pending_

> Replace the placeholder entry when the first concrete issue is logged; duplicate the block for subsequent issues.

## Context & Artifacts
- Source files / directories touched: _TBD_
- Tests to run: _TBD_
- Commands / scripts used: _TBD_

## Handover Notes
- Current status: Awaiting detailed study/design.
- Pending questions / blockers: Confirm debugger architecture and TUI framework.
- Suggested next action when resuming: Finalise `(3)requirements.md`, complete `(2)study.md` actions, and feed outcomes into `(4)design.md`.
