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
| A | Build a layered debugger core (Python package) that exposes transport/session/event APIs with adapters for a dedicated `dbg` CLI, scripting commands, and TUI (e.g., `textual`). HSX shell remains thin but can delegate via `hsx dbg …`. | Clean separation, reusable across interfaces, keeps HSX shell lightweight for MCU porting. | Requires new core architecture (session cache, event bus) and refactors shell to delegate. |
| B | Standalone TUI frontend with minimal shared core; CLI continues largely untouched. | Fastest path to a TUI prototype. | Logic duplication between shell and debugger; inconsistent automation story; harder maintenance. |
| C | Expand HSX shell with debugger features/TUI. | Single entry point, minimal new binaries. | Bloats shell, conflicts with goal of portability, increases coupling. |

## Decision
- **Chosen approach:** Option A — layered debugger core with dedicated `dbg` CLI/TUI while keeping HSX shell minimal and delegating when needed.
- **Rationale:** Preserves separation of concerns, keeps the microcontroller-friendly shell lightweight, and enables richer tooling without entangling existing CLI code.
- **Open questions:** Choice of TUI framework (`textual`, `prompt_toolkit`, etc.), event streaming mechanism (`svc:debug.events` mailbox vs. custom channel), strategy for instruction trace capture (VM instrumentation vs. executive logging), approach for call-stack reconstruction, packaging/distribution on Windows, and expectations for an on-target `dbg.hsx` relay.
- **Dependencies:** Executive RPC stability, MiniVM trace instrumentation, mailbox subsystem updates, symbol metadata availability (LLC JSON), performance impact of single-step mode, availability of BRK-instrumented builds for optional hardware breakpoints.

## Design Playbook

### D1 Evaluate TUI frameworks (`not started`)
- [ ] Survey `textual` capabilities (layout, async, Windows support).
- [ ] Verify `prompt_toolkit` features (panels, resize handling).
- [ ] Investigate `urwid`/`npyscreen` as fallbacks (note limitations).
- [ ] Document pros/cons and recommend primary framework in `(3)design.md`.

### D2 Draft debugger-core architecture (`not started`)
- [ ] Define core components: session manager, transport client, event bus, state cache.
- [ ] Sketch breakpoint/watch service interfaces.
- [ ] Outline APIs exposed to CLI, scripting, and TUI layers.
- [ ] Capture architecture diagram/description for `(3)design.md`.

### D3 Prototype executive signalling channel (`not started`)
- [ ] Specify debug-event mailbox schema (message fields, routing).
- [ ] Implement minimal publisher in `execd` (stub).
- [ ] Build client subscriber that drains events and updates local cache.
- [ ] Measure performance/latency impact (document findings).

### D4 Audit VM/executive for stack/memory support (`not started`)
- [ ] Review current stack frame layout & available metadata.
- [ ] Identify hooks needed for stack reconstruction in `execd`.
- [ ] Assess feasibility of memory inspector APIs (read/write granularity, safety).
- [ ] Log required remediation tasks for `(3)design.md`.

### D5 Define MCU `dbg.hsx` relay (`not started`)
- [ ] Describe minimal functionality (subscribe to event mailbox, forward via serial).
- [ ] Outline message format/commands for host->target interactions.
- [ ] Note resource constraints & implementation considerations.
- [ ] Decide whether to include in initial design or backlog it.

### D6 Prepare design documentation (`not started`)
- [ ] Synthesize outcomes from D1–D5.
- [ ] Update `(3)design.md` with selected architecture, sequencing, and required changes.
- [ ] Review design with stakeholders; capture sign-off.

## Design Definition of Done
- [ ] Design playbook items D1–D6 completed and documented.
- [ ] `(3)design.md` reflects chosen architecture, UI plans, and required executive/VM updates.
- [ ] Stakeholders review/approve the design before implementation begins.
