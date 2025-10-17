# Feature Study — HSX Debugger Toolkit & TUI

> Purpose: capture the baseline behaviour, explore solution options, and agree on the approach before detailed design.

## Study Participants
- Lead: Codex (assistant)
- Contributors / reviewers: Hans Einar, Runtime/Tooling team
- Date(s): 2025-10-16

## Current Behaviour / Baseline
- **Transport & control:** The Python executive (`python/execd.py`) exposes RPC commands (`attach`, `clock`, `step`, `dumpregs`, `trace`, `sched`) over TCP. The HSX shell (`python/shell_client.py`) is the primary consumer, offering manual commands but no persistent debugger session state (no call stack, breakpoints, or watch facilities).
- **State inspection:** `dumpregs` prints register snapshots; memory reads require `peek`/`poke` on raw addresses. There is no unified API for stack inspection, symbol lookup, or structured variable display.
- **Execution trace:** `execd` records a scheduler trace (last N scheduler events) but not a per-instruction execution log. Instruction trace requires running the VM with `--trace` which writes logs to stdout/file, outside of the executive.
- **Breakpoints:** The VM understands `BRK` instructions but there is no interface to insert/remove virtual breakpoints or manage BRK hits from the executive.
- **UI tooling:** There is no TUI; current interfaces are CLI only (HSX shell, `blinkenlights.py`). Layout management, panel toggling, and resize handling are unimplemented.
- **Events:** Executive currently pushes events over HTTP? No, it emits JSON responses; there is no mailbox-based event channel for debugger notifications. Clients poll by issuing commands.
- **ps command:** `ps` returns all tasks; there is no `ps <pid>` filter, so clients must iterate to find metadata. No pretty-print integration for status bars.

### Gap Analysis (vs. `(1)functionality.md`)
- **Debugger session abstraction:** Need a reusable core (session, transport, event bus) instead of ad-hoc CLI calls. Current code lacks modular session management.
- **Breakpoints/BRK control:** Add virtual breakpoint table, API endpoints, and BRK handling pipeline. VM/executive changes required.
- **Call stack & memory inspector:** Need call-frame reconstruction (e.g., by walking saved return addresses or stack frames). Memory inspector requires hexdump helpers and optional edit support.
- **Watch list & variable change logging:** Need symbol binding, expression parsing, and delta tracking infrastructure.
- **Trace logging:** Must introduce instruction-level tracing within executive or VM when debugger attached, with storage and streaming.
- **Event/signalling layer:** Executive should push state changes (PC updates, breakpoint hits, mailbox updates) via mailbox or streaming channel; debugger also requires internal refresh tick.
- **TUI framework & layout:** Choose a library that supports panels, resizing, keyboard navigation (e.g., textual, prompt_toolkit). Need layout manager abstractions mapping to requested panels.
- **CLI enhancements:** Extend HSX shell (or new CLI entry point) with stack/memory/watch commands, `ps <pid>` filter, and JSON output for new data structures.
- **Documentation/testing:** Current docs have no debugger coverage; test suite lacks acceptance for these features.

### Supporting Evidence
- `python/shell_client.py` command set and existing help files.
- `docs/executive_protocol.md` describing available RPC endpoints.
- Issue #2 scheduler evidence showing current clock/trace outputs.
- Existing VM tracing (`--trace`) resides in `platforms/python/host_vm.py` but is not surfaced through the executive.

## Solution Options
| Option | Description | Pros | Cons / Risks |
|--------|-------------|------|--------------|
| A | Layered “debugger core” package: transport/session layer + adapters for CLI shell, scripted API, and TUI (e.g., built on `textual`). | Single source of truth for state, clean separation of concerns, easier to extend with future UIs. | Requires significant refactor of current shell; must design event bus and state cache carefully. |
| B | Standalone TUI app with minimal shared core; CLI remains mostly as-is. | Allows rapid UI iteration without large shell changes. | Duplicated logic between shell and TUI; harder to maintain consistent behaviour; automation needs may lag. |
| C | Incrementally extend HSX shell to embed debugger session and pseudo-TUI (e.g., curses). | Lower initial effort, leverages existing command parsing. | Shell code already complex; mixing TUI and CLI might reduce maintainability and portability. |

## Decision
- **Chosen approach:** `<Option pending detailed evaluation>`
- **Rationale:** To be finalised after assessing TUI library feasibility, debugger-core abstraction, and executive event channel design.
- **Open questions:** Choice of TUI framework (`textual`, `prompt_toolkit`, etc.), event streaming mechanism (`svc:debug.events` mailbox vs. custom channel), strategy for instruction trace capture (VM instrumentation vs. executive logging), approach for call-stack reconstruction, and packaging/distribution on Windows.
- **Dependencies:** Executive RPC stability, MiniVM trace instrumentation, mailbox subsystem updates, symbol metadata availability (LLC JSON), performance impact of single-step mode.

## Next Steps
- Evaluate candidate TUI frameworks (textual, prompt_toolkit, textualize) for Windows compatibility and layout capabilities.
- Draft debugger-core architecture: session manager, event bus, data cache, breakpoint/watch services.
- Prototype executive signalling channel (mailbox or push socket) and minimal client subscriber.
- Audit VM/executive code to confirm feasibility of call-stack reconstruction and memory inspector APIs.
- Update `(3)design.md` with selected architecture, sequencing, and required executive/VM changes once decisions are made.
