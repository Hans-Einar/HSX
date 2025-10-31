# Feature Brief — HSX Debugger Toolkit & TUI

- Feature ID: `#1`
- Created by: Hans Einar / Codex
- Date opened: `2025-10-16`

## Summary
- Deliver a unified debugger that attaches to the HSX executive (`execd`) and controls individual PIDs (standalone MiniVM support may follow later).
- Provide both automation-friendly CLI/script commands (JSON output) and an interactive debugger shell that expose stack/memory/watch controls.
- Introduce a cross-platform TUI with real-time insight into registers, trace history, disassembly, pluggable auxiliary panels, and dedicated views for call stack, memory inspector, and variable watch list, plus a status bar that surfaces connection/program metadata.

## Use Cases / Scenarios
| ID | Scenario | Trigger | Desired behaviour |
|----|----------|---------|-------------------|
| UC-1 | Attach via executive | Operator targets a running PID managed by `execd`. | Debugger connects via RPC, acquires a PID lock, displays live state, and controls execution (step/run/break). |
| UC-2 | Automation / scripting | CI or tooling pipeline needs quick inspection. | Invoke debugger non-interactively; emit JSON snapshots of registers/trace/mailboxes. |
| UC-3 | Visual monitoring | Operator wants live, navigable state in the terminal. | TUI shows register panel, execution trace, disassembly, and tabbed auxiliary widgets (mailbox/dmesg/stdio/scheduler/watch list). |
| UC-4 | Breakpoint management | Developer encodes BRK instructions and wants to skip/break interactively. | Debugger discovers BRKs, toggles them at runtime, and integrates with clock controls. |
| UC-5 | Stack & memory inspection | Developer needs to inspect call stack frames and memory snapshots in context. | Alternate register pane reveals call stack and memory inspector; supports navigation and editing (future). |

## Constraints & Assumptions
- Initial release requires an `execd` connection; standalone MiniVM debugging is optional future work.
- One debugger instance controls a single PID; multiple debugger sessions can attach to different PIDs concurrently (enforce locking per PID).
- Choose a TUI framework compatible with Windows PowerShell (ANSI-capable terminal libraries acceptable).
- Reuse existing HSX RPC protocols; extend without breaking current shell behaviour.
- Target Python 3.11 environment currently used by tooling.
- Ship as part of the HSX tooling suite; retain JSON/TCP transport (serial link for future C port out of scope).
- Update the HSX shell `ps` command to accept an optional PID argument (`ps <pid>`) so debugger sessions can retrieve per-task metadata directly.
- Integrate an event/signaling layer: the executive emits state-change events; the debugger maintains an internal refresh clock to drive UI updates (registers/trace/auxiliary panels).
- Provide a dedicated executive mailbox/event channel that publishes debugger-relevant state changes so clients can subscribe without polling.
- TUI layout should treat views as modular panels (registers/stack/memory/watch list) that can be repositioned or toggled, with automatic resizing support from the chosen framework.
- CLI and TUI should allow at least read access to memory inspector (write/edit support can be phased in).

## Success Metrics / Acceptance Signals
- Debugger attaches to a PID through `execd`, showing live register values, trace history, and disassembly.
- CLI/script mode returns JSON suitable for automation.
- CLI/shell expose commands for stack inspection, memory viewing, watch list management, and trace logging.
- TUI updates panels in real time, supports navigation, and allows BRK/clock control.
- Auxiliary panels (mailboxes, dmesg, stdio, scheduler stats, watch list) can be toggled/tabbed.
- Status bar displays mode/PID/runtime counters and program information (mirroring `ps <pid>` output).
- Event-driven updates keep registers/trace/auxiliary panels current without manual refresh.
- Call stack, memory inspector, and watch list views operate as first-class panels within the TUI layout.
- Trace/logger captures execution history and variable changes for offline analysis.
- Documentation provides walkthroughs for CLI, shell, and TUI usage with examples.

## References
- Related issues: `issues/#2_scheduler` (context switching improvements), `issues/#3_PC_ERROR` (decoder fixes influence disassembly), potential future feature requests.
- Docs/specs: `docs/executive_protocol.md`, `docs/hsx_spec-v2.md` (execution model), existing HSX shell help files.
- Prior art or prototypes: Current HSX shell (`python/shell_client.py`), `platforms/python/host_vm.py` CLI, external terminal UI libraries (`textual`, `urwid`, `prompt_toolkit`).

> Keep this brief up to date when scope changes or new stakeholders join.
