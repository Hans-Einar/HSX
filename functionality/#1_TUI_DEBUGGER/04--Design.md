# Feature Design — HSX Debugger Toolkit & TUI

> Detailed specification for the agreed solution. Update as the design playbook (D1–D6) progresses.

## Overview
- Feature ID: `#1_TUI_DEBUGGER`
- Design status: `in progress`
- Last updated: `2025-10-16`
- Related docs: `(1)functionality.md`, `(2)study.md`, `(3)requirements.md`

## Architecture & Components
- **Debugger core package (`hsxdbg`):** Python module that wraps the existing executive RPC (`python/vmclient.py`) with richer session management, state caching, and event streaming. Exposes high-level APIs (`attach(pid)`, `step()`, `watch.add(expr)`, etc.) that both CLI and TUI consume.
- **Session manager:** Tracks connection metadata (host, port, protocol version), negotiates capabilities (`session.open`), owns per-PID attachments, and guards exclusive access. Maintains heartbeats and reconnect logic.
- **Event bus:** Async dispatcher that multiplexes VM/executive events (`debug_stop`, `mailbox_*`, scheduler updates) to interested subscribers (CLI output, TUI panels, scripting hooks). Backed by bounded queues to avoid unbounded growth.
- **State cache:** Mirrors registers, memory ranges, call stacks, watch variables, mailbox descriptors, and scheduler info per PID. Updated from event bus and explicit fetches; provides snapshot views to UI layers without repeated RPC polling.
- **CLI (`hsx dbg`):** Thin command-line frontend that delegates to the debugger core. Supports interactive REPL (via `prompt_toolkit`) and JSON-formatted subcommands for scripting.
- **TUI frontend:** Full-screen interface implemented with `textual`. Composes reusable widgets (registers, disassembly, trace, call stack, mailbox activity, watch list, status bar). Subscribes to the event bus and issues commands through the core.
- **Executive/VM extensions:** Adds session-aware RPC endpoints, event subscription streaming, breakpoint table manipulation, stack frame extraction, and memory inspector helpers. Instrument `platforms/python/host_vm.py` to surface BRK hits and stack metadata; extend `python/execd.py` to fan-out events and enforce PID locks.

## Detailed Design Tasks

### D1 Evaluate TUI frameworks (`complete`)
- **Summary:** `textual` selected for full-screen TUI, `prompt_toolkit` retained for enhanced CLI interactions. `urwid`/`npyscreen` rejected due to Windows support gaps and lack of async integration.
- **Key findings:**
  - `textual` offers high-level layout primitives, async message handling compatible with our event bus, and modern terminal support across Windows/macOS/Linux.
  - `prompt_toolkit` excels at line editing and tab completion but cannot drive multi-pane dashboards; we will use it solely for the CLI REPL.
  - `urwid` lacks native Windows support (requires extra dependencies) and complicates asyncio integration.
  - `curses` bindings block Windows out of the box and require extensive layout scaffolding.
- **Actions:** Pin `textual>=0.58` (verify latest stable) and `prompt_toolkit>=3.0`; record dependencies in `docs/python_version.md` and packaging notes during D6.

### D2 Draft debugger-core architecture (`in progress`)
- **Core package layout:**
  - `hsxdbg.transport`: wraps existing RPC client with session negotiation (`session.open`, `session.close`, capability handshake) while preserving backwards-compatible command routing.
  - `hsxdbg.session`: manages connection lifecycle, PID attachments, breakpoint/watch registries, and cached snapshots. Provides async context manager for attach/detach operations.
  - `hsxdbg.events`: implements event bus with subscription channels (e.g., `Registers`, `Trace`, `Scheduler`, `Mailboxes`) and ack/resume semantics for back-pressure.
  - `hsxdbg.commands`: exposes typed command helpers (e.g., `step`, `resume`, `set_breakpoint`, `read_memory`) that shield clients from raw JSON.
  - `hsxdbg.adapters`: UI-specific adapters (CLI, TUI) that map user input to core commands and render state updates.
- **Data flow:**
  1. CLI/TUI instantiates `DebuggerSession` with connection params.
  2. `DebuggerSession.open()` performs protocol handshake, registers event subscription preferences, and locks a PID (or waits until available).
  3. Event stream is fed into `EventBus`, which updates `StateCache` and notifies subscribers.
  4. User actions (step, resume, breakpoint toggle) call into `hsxdbg.commands`, which dispatch RPC requests via transport layer.
  5. On detach/shutdown, event stream unsubscribes, caches persist to disk if requested (e.g., for post-mortem).
- **Concurrency model:** Use `asyncio` tasks for event consumption and UI integration. Provide synchronous wrappers for scripting (run event loop internally).
- **Open items:** Define serialization of watch expressions (likely referencing symbol metadata from `.hxe` or debug JSON), design stack frame schema, and align CLI command surface with existing shell aliasing.

### D3 Prototype executive signalling channel (`planned`)
- **Transport:** Add long-lived `events.subscribe` RPC (JSON lines). Executive streams event objects until unsubscribed or connection drops.
- **Event schema:** Each event includes `seq`, `ts`, `type`, `pid`, and payload fields (`pc`, `opcode`, `mailbox`, etc.). Standardize `debug_stop`, `break_hit`, `trace_step`, `mailbox_*`, `clock_tick`, `watch_update`.
- **Executive changes (`python/execd.py`):**
  - Introduce `EventStreamer` thread that tails `ExecutiveState.log_buffer` and new debug queues, pushing to subscribers.
  - Add PID lock table to ensure only one active debugger per task; provide shared-read mode for passive listeners.
  - Provide `session.keepalive` and `session.unsubscribe` commands.
- **VM hooks (`platforms/python/host_vm.py`):**
  - Ensure `emit_event` is invoked for BRK hits, single-step completions (`debug_stop`), and call stack boundary changes.
- **Back-pressure:** Support `ack` messages from clients to adjust rate; drop events older than configured window with warning.
- **Prototype goals:** CLI `dbg --listen` can receive live events; TUI panels update without manual polling.

### D4 Audit VM/executive for stack/memory support (`in progress`)
- **Stack reconstruction:**
  - Reuse `TaskContext` fields (`pc`, `sp`, `reg_base`, `stack_base`, `stack_limit`) to traverse frames. Document calling convention expectations (saved LR, frame header layout).
  - Extend VM to expose helper `MiniVM.collect_stack(max_frames=32)` returning `[{"pc":..., "sp":..., "fp":..., "symbol":...}]`.
  - Executive caches stack snapshots per PID and exposes via new RPC (`stack.info`, `stack.read`).
- **Memory inspector:**
  - Add ranged read/write commands that respect task sandbox (limit to defined memory segments). Provide typed responses (hex, ASCII preview, f16 reinterpret).
  - Define safe write guard (require explicit `--force` or confirm).
- **Symbol integration:** Hook `.hxe` metadata (symbols, line info) produced by linker to annotate disassembly and stack frames. If unavailable, degrade gracefully.
- **Action items:** Inventory existing helpers in `python/toolchain_util.py` for symbol lookup; record missing pieces in `(5)implementation.md` once design finalises.

### D5 Define MCU `dbg.hsx` relay (`planned`)
- **Purpose:** Lightweight HSX task that attaches to executive mailboxes (`svc:debug.events`) and forwards events over UART/USB to host debugger when running on hardware.
- **Scope for initial release:** Document minimal message set (`HELLO`, `EVENT`, `BREAK`, `ACK`) and ensure host debugger can operate without relay (direct TCP). Actual firmware implementation can follow in subsequent milestone.
- **Resource constraints:** Maintain <8 KB code footprint, avoid dynamic allocation, respect FRAM/flash budgets. Provide handshake so relay can throttle event rate.
- **Deliverables:** Include protocol sketch and backlog tasks referencing Milestone 7.

### D6 Prepare design documentation (`pending`)
- **Actions to close:**
  - Consolidate decisions from D1–D5 into final architecture narrative, diagrams, and sequence charts.
  - Update `(1)functionality.md` success metrics if scope shifts.
  - Review design with Runtime/Tooling stakeholders; capture sign-off notes with owners.
  - Export summary to `docs/hsx_spec-v2.md` (debugger section) and `docs/executive_protocol.md` (new RPC).
- **Exit criteria:** All dependencies enumerated, risks addressed, testing/doc plans agreed.

## Compatibility & Migration Considerations
- Preserve protocol version `1`: new RPC commands (`session.open`, `events.subscribe`, `stack.info`, etc.) are opt-in and must return `unsupported_cmd` on older executives.
- Existing shell clients continue to function; CLI enhancements live under new `dbg` command tree without altering current command names.
- Event streaming must fallback to polling when server lacks `events.subscribe`; document detection handshake.
- `.hxe` format remains unchanged (per constraints); additional symbol/debug metadata transmitted via sidecar JSON or embedded optional section.
- Ensure textual dependency checks run behind feature gate so headless environments (CI) can skip TUI components without import errors.

## Testing Strategy
- **Unit tests:** Cover session manager (handshake, reconnect), event bus routing, breakpoint/watch services, and stack reconstruction utilities.
- **Integration tests:** Extend `python/tests` with fixtures that spin up `execd` + MiniVM stub, validate event streaming, breakpoint hits, and CLI/TUI command flows. Mirror sample `.hxe` apps under `examples/tests/test_dbg_*`.
- **Manual validation:** Checklist for Windows Terminal/PowerShell, macOS Terminal, Linux (GNOME Terminal, tmux). Include attach/detach, BRK handling, watch updates, and mailbox tracing.
- **Performance benchmarks:** Measure event throughput under stress (simulated hundreds of events/sec) to ensure UI remains responsive.
- **Regression:** Re-run existing mailbox/stdio suites to confirm no behavioural regressions.

## Documentation Updates
- Update `docs/executive_protocol.md` with new commands, event schema, and session lifecycle.
- Add debugger usage section to `docs/ARCHITECTURE.md` referencing the new tooling stack.
- Author CLI/TUI help topics (`help/dbg.txt`, `help/dbg_watch.txt`, TUI quick-start).
- Expand `(4)dod.md` with verification artefacts once implementation progresses.
- Capture packaging steps and dependency requirements in `docs/python_version.md` and tooling README.

## Risks & Mitigations
- **Event backlog overload:** High-frequency events could overwhelm clients. Mitigation: bounded queues, drop-oldest policy with telemetry, allow client to adjust sampling rate.
- **Protocol drift:** Introducing new RPC commands risks breaking older executives. Mitigation: capability negotiation during `session.open`, maintain compatibility shim for legacy servers.
- **Textual adoption risk:** Pre-1.0 API churn could destabilise TUI. Mitigation: pin tested version, wrap in thin adapter layer to isolate breaking changes, include smoke tests.
- **Stack reconstruction accuracy:** Incorrect frame parsing could mislead users. Mitigation: document ABI assumptions, add validation tests with known call graphs, offer raw memory view.
- **Resource usage on hardware relay:** MCU relay might starve system if event volume high. Mitigation: optional relay handshake to request reduced frequency, host-side filtering.

## Sign-off
- Approved by: `<pending>`
- Date: `<pending>`
