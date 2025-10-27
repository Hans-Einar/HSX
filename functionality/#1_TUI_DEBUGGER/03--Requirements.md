# Requirements â€” HSX Debugger Toolkit & TUI

> Consolidate the behavioural and system requirements that implementation must satisfy. Derived from `(1)functionality.md` and `(2)study.md`.

## Purpose
- Capture what the debugger must deliver for users and tooling.
- Enumerate prerequisites or changes needed in the current HSX stack.
- Provide traceability between study findings, design decisions, and acceptance tests.

## Requirements Summary
| ID | Category | Description | Source | Notes |
|----|----------|-------------|--------|-------|
| F-1 | Functional | Debugger attaches to an HSX executive (`execd`) session, acquires exclusive control of a PID, and exposes step/run/break workflow. | UC-1, Study Gap: session abstraction | Requires PID locking support in executive. |
| F-2 | Functional | Provide automation-friendly CLI/JSON interface for register, memory, stack, trace, breakpoint, and mailbox inspection. | UC-2, Study Gap: CLI enhancements | Should integrate with existing shell or new `hsx dbg` entry point. |
| F-3 | Functional | Deliver a full-screen TUI with modular panels (registers, disassembly, trace, call stack, memory inspector, watch list, auxiliary panels). | UC-3 | Panels must be toggleable/repositionable; live updates expected. |
| F-4 | Functional | Support breakpoint discovery, insertion/removal, and handling of BRK hits with user feedback and resume controls. | UC-4, Study Gap: breakpoints | Includes persistence within debugger session. |
| F-5 | Functional | Offer stack reconstruction and memory viewing for the selected PID, with symbol-aware presentation when metadata is available. | UC-5, Study Gap: stack/memory | Memory writes optional; reads required. |
| F-6 | Functional | Stream execution/diagnostic events (instruction trace, mailbox activity, scheduler updates) to debugger clients without polling. | Study Gap: event/signalling | Requires new event subscription API. |
| F-7 | Functional | Provide watch list tracking for selected variables/expressions with change notifications. | Study Gap: watch list | Depends on symbol metadata and expression evaluation helpers. |
| N-1 | Non-functional | Operate on Windows, macOS, and Linux terminals (PowerShell, Terminal, GNOME, tmux) using a supported Python runtime (>=3.11). | Constraints | Drives toolkit selection (`textual`, `prompt_toolkit`). |
| N-2 | Non-functional | Maintain compatibility with existing RPC protocol (version 1); new commands must fail gracefully on older servers. | Constraints | Introduce capability negotiation during session handshake. |
| N-3 | Non-functional | Event streaming must remain responsive under high-frequency workloads (hundreds of events/sec) without starving the executive. | Study Gap: performance | Enforce bounded buffers, flow control. |
| S-1 | System | Extend `python/execd.py` with session lifecycle management, event broadcasting (`events.subscribe`), PID locks, and enhanced `ps`/`info`. | Study Gap: session/event | Includes `ps <pid>` support. |
| S-2 | System | Enhance `platforms/python/host_vm.py` to emit structured debug events (breakpoints, stack updates), expose stack-frame helper, and honour virtual breakpoints. | Study Gap: breakpoints/stack | Interacts with MiniVM debug flags. |
| S-3 | System | Ensure toolchain (`asm.py`, `hsx-llc.py`, linker) can provide symbol/line metadata for debugger consumption (sidecar JSON or embedded table). | Study Gap: symbol lookup | Required for disassembly annotations and watch evaluation. |
| S-4 | System | Update documentation/help assets to cover new commands, TUI usage, and event protocol. | Constraints | Link to DoD and packaging tasks. |

## Detailed Requirements

### Functional Requirements
- **F-1: Executive attachment & PID control**
  - Preconditions: Executive exposes attach/detach, PID metadata, and ability to pause/resume specific tasks.
  - Behaviour: Debugger session negotiates with executive, locks a PID, reflects current run state (running/paused/break), and can step N instructions or resume.
  - Postconditions: PID lock released cleanly on detach; session teardown resets any temporary breakpoints.

- **F-2: Automation-friendly CLI**
  - Command surface must include at minimum: `attach`, `info`, `regs`, `stack`, `mem read`, `mem write (optional)`, `break/set`, `break/clear`, `watch/add|rm`, `trace/tail`, `mailbox/listen`.
  - CLI output supports both human-readable and JSON modes (selectable via flag or environment variable).
  - Commands return exit codes signalling success/failure for scripting jobs.

- **F-3: TUI experience**
  - Layout: default view shows registers, disassembly/trace, call stack, status bar; auxiliary panels (mailbox, watch, scheduler, stdout) accessible via tabs/hotkeys.
  - Interaction: keyboard navigation for panel focus, step/run controls, breakpoint toggling on selected lines.
  - Responsiveness: state updates appear within 200 ms of event receipt under nominal workloads.

- **F-4: Breakpoint lifecycle**
  - Detect static BRK instructions from loaded image.
  - Allow inserting/removing virtual breakpoints at arbitrary addresses (if supported by VM).
  - Notify user on breakpoint hit, show reason (BRK, user stop, async break), capture context snapshot.

- **F-5: Stack & memory inspection**
  - Provide structured stack view including frame index, PC, SP, function/symbol name, optional source line.
  - Support reading arbitrary address ranges with formatting (hex + ASCII).
  - (Optional) gated memory writes with confirmation or `--force`.

- **F-6: Event-driven updates**
  - Executive exposes subscription endpoint delivering `debug_stop`, `trace_step`, `mailbox_*`, `clock_tick`, `log` events.
  - Executive exposes `events.subscribe`/`events.ack` with bounded queues (defaults per `docs/executive_protocol.md`).
  - Event payloads include `seq`, `ts`, `pid`, `type`, and structured `data` for categories (trace_step, debug_break, scheduler, mailbox, watch, stdout/stderr).
  - Tooling must handle back-pressure (acknowledge processed events, resynchronise with `since_seq` after drops).
  - Clients can filter event categories to reduce noise.

- **F-7: Watch list**
  - Allow adding watches by symbol name or address expression.
  - Track value deltas; highlight changes in CLI/TUI.
  - Handle missing symbols gracefully (warn, keep placeholder).

### Non-Functional / Constraints
- **N-1:** Tooling must install and run without extra native dependencies beyond Python packages (`textual`, `prompt_toolkit`, `rich` stack). Document installation steps for Windows (PowerShell) and Unix terminals.
- **N-2:** Introduce capability negotiation (e.g., `session.open` returns available features). Debugger downgrades gracefully if certain capabilities unavailable (falls back to polling).
- **N-3:** Event processing pipeline should apply back-pressure (bounded queue, drop-oldest with warning) and expose metrics (queue depth) for troubleshooting.
- **N-4:** Maintain separation between debugger logic and embedded executive to keep MiniVM single-task constraint intact (no scheduler interference).

### System-Level Requirements / Dependencies
- **S-1:** Executive (`python/execd.py`)
  - Add commands: `session.open`, `session.close`, `events.subscribe`, `stack.info`, `watch.list`.
  - Introduce PID lock table and enforce single debugger per PID.
  - Extend `ps` command (CLI and RPC) to accept PID filter.
  - Persist event log buffers for new categories (trace, breakpoints).

- **S-2:** MiniVM (`platforms/python/host_vm.py`)
  - Emit structured events via `emit_event` for breakpoint hits, single-step completions, sleep/wake transitions.
  - Expose helper APIs for stack frame capture (`collect_stack`) and symbol lookup indexes (if available).
  - Honour temporary breakpoints injected by debugger (skip once semantics).

- **S-3:** Toolchain & metadata
  - Linker outputs optional debug symbol table (function names, source line mapping) consumed by debugger.
  - Provide `hsx-llc` / assembler hooks to emit watchable symbol metadata (type, size).
  - Document `.hxe` compatibility expectations (existing magic/version preserved).

- **S-4:** Documentation & packaging
  - Update CLI help (`help/dbg*.txt`), docs (`docs/executive_protocol.md`, `docs/ARCHITECTURE.md`, `docs/python_version.md`).
  - Ensure `make dev-env` installs debugger dependencies.
  - Provide TUI quick-start guide and troubleshooting appendix.

## Acceptance Criteria
- AC-1: Debugger session attaches to a running PID, shows live registers/stack/trace, and can step/resume without dropping connection.
- AC-2: CLI command `hsx dbg --json regs` outputs machine-readable register data and exits with code 0 on success.
- AC-3: TUI updates panels (<200 ms) when the VM hits a breakpoint or produces STDIO/mailbox output.
- AC-4: Event subscription endpoint handles at least 500 events/sec without backlog growth beyond configured cap.
- AC-5: Breakpoint insertion/removal reflected in both CLI and TUI, with hits logged and exposed via event stream.
- AC-6: Stack view resolves symbol names when metadata present; falls back to hex addresses otherwise, with warning.
- AC-7: Requirements dependencies (S-1â€“S-4) implemented or tracked with explicit backlog items before implementation moves forward.

## Traceability Notes
- Requirements F-1â€¦F-7 originate from functionality use cases and study gaps; they map directly to design tasks D1â€“D6 in `(4)design.md`.
- Acceptance criteria align with success metrics listed in `(1)functionality.md`.
- Each system dependency (S-1â€¦S-4) should link to corresponding implementation tasks in `(6)implementation.md` and DoD checklist entries in `(5)dod.md`.

## Open Questions
- Confirm format and delivery mechanism for symbol metadata (embedded vs. sidecar file).
- Determine whether memory write support ships in initial release or is deferred.
- Decide on policy for concurrent read-only observer sessions (e.g., allow TUI + CLI simultaneously).
