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

## 2025-11-10 — Transport Layer

- Scope: Toolkit Implementation Plan Phase 1.2 (`hsxdbg.transport`) in support of VS Code debug stack.
- Highlights:
  - Implemented resilient JSON-over-TCP transport with reconnect/backoff, request FIFO correlation, state callbacks, and async event hook (`python/hsxdbg/transport.py`).
  - Added richer dummy debugger server plus transport regression suite covering round-trip, reconnect, and event delivery scenarios (`python/tests/test_hsxdbg_transport.py`).
  - Updated plan + implementation notes to reflect completed checklist items; documented tests (`PYTHONPATH=. pytest python/tests/test_hsxdbg_transport.py python/tests/test_hsxdbg_package.py`).
- Follow-ups:
  - Thread transport event hook into forthcoming `hsxdbg.events` module.
  - Align session manager payload parsing with executive responses before layering command helpers.

## 2025-11-10 — Session Manager Alignment

- Scope: Toolkit Implementation Plan Phase 1.3 (Session manager) in service of the VS Code adapter prerequisites.
- Highlights:
  - `SessionManager.open()` now parses the real executive envelope (`{status:\"ok\", session:{...}}`), tracking heartbeat, max_events, warnings, and pid lock lists inside `SessionState`. `SessionConfig` gained optional `max_events`/`heartbeat_s` knobs.
  - Dummy debugger server/test harness updated to emit/validate the richer payload (`python/tests/test_hsxdbg_transport.py`), ensuring clients observe heartbeat + warning metadata.
  - Implementation notes/plan updated; regressions run via `PYTHONPATH=. pytest python/tests/test_hsxdbg_transport.py python/tests/test_hsxdbg_package.py`.
- Follow-ups:
  - Propagate session warnings and heartbeat guidance to CLI/DAP UX.
  - Begin command layer work so hsxdbg clients no longer craft raw RPC dictionaries.

## 2025-11-10 — Event Bus Hookup

- Scope: Toolkit plan Phase 2.1 groundwork—wire hsxdbg transport events into the shared EventBus so VS Code/DAP consumers can subscribe without custom socket plumbing.
- Highlights:
  - `SessionManager` now accepts/attaches an `EventBus`, calling `HSXTransport.set_event_handler` under the hood; `attach_event_bus()` lets adapters swap buses at runtime.
  - Added regression `test_session_manager_event_bus_receives_events` validating that dummy executive events reach EventBus subscribers once `bus.pump()` runs.
  - Tests executed: `PYTHONPATH=. pytest python/tests/test_hsxdbg_transport.py python/tests/test_hsxdbg_package.py`.
- Follow-ups:
  - Implement actual `events.subscribe` / `events.ack` RPC helpers plus background dispatcher thread so EventBus pumping becomes automatic.
  - Define typed event objects (trace_step, debug_break, etc.) for the forthcoming state cache and DAP adapter.

## 2025-11-10 — Event Subscription & ACK Loop

- Scope: Continue Toolkit Phase 2.1—expose `events.subscribe` helpers, auto-ACK, and optional EventBus worker for VS Code adapters.
- Highlights:
  - `SessionManager.subscribe_events()` now negotiates subscriptions (filters + cursor), tracks delivered sequences, and spawns a background thread that periodically issues `events.ack` RPCs. `unsubscribe_events()` is invoked automatically during `session.close`.
  - `EventBus.start()/stop()` provide a background dispatcher thread; tests spin it up to ensure subscribers receive callbacks without manual pumps.
  - Dummy executive + transport tests extended to cover subscribe + ACK flows; executed `PYTHONPATH=. pytest python/tests/test_hsxdbg_transport.py python/tests/test_hsxdbg_package.py`.
- Follow-ups:
  - Layer event schema parsing atop the raw events (Phase 2.2) so the VS Code adapter can bind typed handlers.
  - Explore exposing ACK metrics to frontends for slow-consumer diagnostics once back-pressure hooks land.

## 2025-11-10 — Typed Event Schemas

- Scope: Toolkit Phase 2.2 – define debugger event schemas & parsing helpers for the VS Code stack.
- Highlights:
  - Introduced dataclasses for core event categories (trace_step, debug_break, scheduler/task_state, mailbox_*, watch_update, stdout/stderr, warning) plus `parse_event()` so adapters consume structured data.
  - EventBus now delivers typed events, and new unit tests cover both the parser and the background dispatcher (`python/tests/test_hsxdbg_events.py`).
  - HSX builder tests adjusted to account for the stdlib flag to keep the suite green.
- Follow-ups:
  - Document the event schemas in the public toolkit docs and propagate them into the upcoming cache/state layers.
  - Add typed helpers for any future executive event categories (e.g., telemetry/logpoints).

## 2025-11-10 — Runtime Cache Core

- Scope: Toolkit Phase 3.1 – implement the shared state cache backing the VS Code debug adapter.
- Highlights:
  - `python/hsxdbg/cache.py` now tracks per-PID registers, memory blocks, call stacks, watch values, and mailbox descriptors via dataclasses, with helpers to seed/clear snapshots.
  - Added coverage (`python/tests/test_hsxdbg_cache.py`) to ensure cache mutations work as expected; broader hsxdbg test suite still green.
- Follow-ups:
  - Wire the cache to typed events for automatic invalidation (Phase 3.2) and surface query helpers/fallbacks as part of Phase 3.3.

## 2025-11-10 — Cache Invalidation

- Scope: Toolkit Phase 3.2, ensuring cache stays coherent with executive events and control commands.
- Highlights:
  - `RuntimeCache.apply_event()` consumes typed events (trace_step/watch_update/debug_break), and `CacheController` + SessionManager wiring feed the cache via EventBus subscriptions automatically.
  - `CommandClient` now invalidates register/stack caches on `step/pause/resume`, preventing stale reads before the next trace_step arrives.
  - Added regression coverage for both SessionManager + CommandClient behaviors.
- Follow-ups:
  - Phase 3.3 to expose cache query APIs plus RPC fallbacks, and revisit memory/register write invalidation once those commands exist.

## 2025-11-10 — Cache Query API

- Scope: Toolkit Phase 3.3 – make cache data easily consumable by the VS Code adapter.
- Highlights:
  - `RuntimeCache` now exposes query helpers (registers/memory/stack/watches) with optional fallback loaders; documented in `CacheAPI.md`.
  - `CommandClient` offers high-level accessors (`get_register_state`, `get_call_stack`, `list_watches`, `read_memory`) that tap the cache first and fall back to RPCs (`dumpregs`, `stack`, `watch list`, `peek`), auto-populating the cache when stale.
  - Expanded unit tests confirm the fallbacks and cache updates.
- Follow-ups:
  - Wire these helpers into the upcoming VS Code debug adapter to avoid bespoke RPCs.
  - Extend invalidation to cover memory/register mutation commands when those land.

## 2025-11-10 — hsx-dap Scaffold

- Scope: VS Code plan Phase 2 – create the initial debug adapter entry point.
- Highlights:
  - Added `python/hsx_dap/__init__.py` (with entry script `python/hsx-dap.py`), implementing a stdio-based DAP server that bridges to `SessionManager`/`CommandClient`. Supports initialize/launch/continue/pause/step/threads/stackTrace/scopes/variables/setBreakpoints requests, emits stopped/output events, and streams executive events via the shared `EventBus`.
  - Reused the RuntimeCache + command helpers to satisfy DAP variable/scopes requests without redundant RPCs.
  - Added protocol unit tests to verify Content-Length framing and JSON parsing.
- Follow-ups:
  - Build the VS Code extension skeleton that spawns this adapter and wires launch configurations.
  - Enhance the adapter with variables/evaluate/memory requests plus better breakpoint line mapping.
