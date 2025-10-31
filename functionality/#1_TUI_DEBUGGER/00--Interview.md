# Interview Notes — HSX Debugger Enhancements

## Participants
- Stakeholder(s): Hans Einar (runtime/tooling lead)
- Facilitator: Codex (assistant)
- Dates / sessions: 2025-10-16

## Conversation Log
| Timestamp / Session | Highlights | Action Items |
|---------------------|------------|--------------|
| 2025-10-16 21:45 | Stakeholder requests a “greatly upgraded” debugging experience: connect to executive (`execd`) and optionally stand-alone VM; support scripted invocations, interactive debugger shell, and a cross-platform TUI with live register panel (left), execution trace (centre), disassembly view (right), navigable linkage between trace and disassembly, clock control, and configurable lower-left panel (mailboxes/dmesg/stdio). | Draft requirements summary; evaluate feasibility of curses-like TUI on Windows; determine architecture for RPC integration with executive and direct VM mode. |
| 2025-10-16 22:05 | Clarified session model (one debugger per PID, multiple debuggers across PIDs), breakpoint expectations (interactive BRK control targeted but may phase in), reliance on executive connection for initial release, disassembly metadata sources (fallback to `.hxe`, enrich with LLC JSON), and pluggable/tabbed auxiliary panels. Confirmed JSON automation output over existing TCP transport and packaging within HSX tooling suite. | Capture clarified requirements; highlight optional vs must-have debugger controls; note future work for standalone MiniVM debugging and serial transport. |

### Follow-up Q&A (2025-10-16 22:05)
- **Target workflows:** Focus on live tasks managed by `execd`; ability to “take control” of a running process. Interactive handling of BRK instructions is desirable (skip/break), but live breakpoint injection may be deferred.
- **Session model:** One debugger per PID; multiple debugger instances can attach to different PIDs. Shared-PID debugging should be locked to avoid confusion.
- **Trace source:** Initial implementation will rely on `execd`. Standalone MiniVM tracing is optional and can follow later.
- **Disassembly linkage:** Debugger should disassemble raw `.hxe` binaries and enrich output when LLC JSON metadata is available.
- **Clock controls / breakpoints:** Support step/run/stop; conditional stepping and advanced breakpoints should be prioritised based on effort (to be ranked during study).
- **TUI framework constraints:** PowerShell compatibility on Windows is sufficient; ANSI-capable terminal libraries (e.g., textual/prompt_toolkit) acceptable.
- **Auxiliary panels:** Pluggable/tabbed panels (mailboxes/dmesg/stdio/scheduler) with toggles for performance.
- **Task metadata:** Request HSX shell `ps` command to accept `ps <pid>` so debugger can retrieve per-task info for status bar and panels.
- **Automation outputs:** JSON remains the standard format over TCP (serial transport for future C implementation).
- **Security:** No new authentication/sandboxing requirements.
- **Packaging:** Ship as part of the HSX tooling suite.
- **Debugger extras:** Stakeholder wants call stack viewer, memory inspector/editor, watch list, and trace logging with per-variable change history.
- **Signalling & refresh:** Executive should emit signals/events when task state changes; debugger maintains an internal refresh clock that dispatches updates to panels (registers, trace, steps, auxiliary views).
- **Signalling transport:** Investigate using a dedicated executive mailbox (e.g., `svc:debug.events`) that publishes state-change notifications; debugger clients subscribe and drain events as they arrive.

## Requirements Snapshot
- Debugger must attach via executive (`execd`) to a PID for the initial release; standalone MiniVM support can follow later.
- Provide both automation-friendly CLI/script commands (JSON responses) and an interactive debugger shell.
- Deliver a cross-platform TUI (PowerShell-compatible on Windows) showing:
  - Live register panel (left) with ability to swap to call stack view.
  - Execution trace history (centre) with navigation.
  - Disassembly view (right) linked to trace selection.
  - Clock control actions (step/run/pause, future conditional stepping) and configurable auxiliary panel (mailboxes, dmesg, stdio, scheduler stats, watch list, etc.) with tabbed/toggle behaviour.
  - Memory inspector and watch list panels treated as movable/optional panes within the layout grid (supporting automatic resizing).
- Persistent status bar should surface connection mode, PID, runtime counters, and program metadata (pretty output from `ps <pid>`).
- Sessions are one debugger per PID; multiple debugger instances can connect to different PIDs concurrently (lock per PID).
- Manage BRK instructions interactively (skip/break); consider roadmap for live breakpoints and conditional stepping based on effort.
- Disassembly must work directly on `.hxe` binaries and optionally load LLC-generated JSON metadata for symbols/instruction details.
- Automation mode uses JSON over existing TCP/IP transport; future serial support (for C implementation) is out of scope for this iteration.
- Ensure design allows pluggable auxiliary panels and future extensibility.
- No additional authentication/sandboxing required; debugger ships with the HSX tooling suite.
- Implement an event-driven architecture: handle execd signals plus internal refresh ticks to keep UI elements current.

## Interview Conclusions
- Core focus is debugging via the executive; standalone VM mode is optional future work.
- Sessions are PID-scoped with exclusive control to avoid conflicting commands.
- TUI must balance real-time insight (registers/trace/disassembly) with extensibility via pluggable panels.
- Automation and tooling integrations will rely on JSON/TCP, keeping parity with existing HSX shell behaviour.
- Breakpoint management (BRK control) and richer clock features will be prioritised during the upcoming study/design phases.

## Agreed Outcomes
- Produce a debugger toolkit that supports CLI scripting, interactive shell, and TUI front-end while reusing underlying transport (executive RPC or direct VM API).
- Use these notes to seed `(1)functionality.md` and shape multiple solution options in `(2)study.md`, including priority ordering for advanced clock/breakpoint features.

## Next Steps
- Draft `(1)functionality.md` capturing use cases and constraints derived here.
- Begin technical study `(2)study.md` covering current debugging utilities (HSX shell, VMController) and candidate architectures for the new debugger.
