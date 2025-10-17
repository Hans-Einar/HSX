# Implementation Playbook — HSX Debugger Toolkit & TUI

> Use this document to coordinate day-to-day work. Update it whenever tasks start, finish, or change.

## Overview
- Feature: Unified debugger (CLI + shell + TUI) for HSX runtime
- Current status: not started
- Last updated: 2025-10-16

## Task Tracker

### F1 Architecture & platform study (`not started`)
- [ ] Step 1 — Evaluate transport abstraction (execd RPC vs direct VM) and session lifecycle
  - Notes:
  - Artifacts:
- [ ] Step 2 — Compare cross-platform TUI libraries (curses, textual, prompt_toolkit) and recommend choice

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
- Suggested next action when resuming: Complete `(2)study.md`, shortlist frameworks, and draft `(3)design.md`.
