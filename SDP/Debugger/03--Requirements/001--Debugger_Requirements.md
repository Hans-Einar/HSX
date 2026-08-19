# DBG-R Requirements Baseline

Status: ACCEPTED DEBUGGER STABILIZATION BASELINE
Date: 2026-08-19  
Scope: debugger subsystem only

These requirements convert the useful intent from legacy `DR-8.1`, `DG-8.1`,
`DG-8.2`, `DG-8.3`, the debugger/DAP design documents, and the current code review
into a stable debugger-specific namespace. They are intentionally implementation-neutral
unless a boundary is itself required for maintainability/correctness.

## Protocol correctness

- **DBG-R-001 — DAP transport purity.** When DAP uses stdio, stdout SHALL contain only
  correctly framed DAP protocol bytes. Diagnostics SHALL use stderr, log files, or DAP
  output/telemetry events.
- **DBG-R-002 — DAP lifecycle ordering.** `initialize`, `initialized`, launch/attach,
  breakpoint configuration, `configurationDone`, stop/continue, disconnect, and terminate
  SHALL follow DAP lifecycle ordering and shall not rely on VS Code tolerating invalid order.
- **DBG-R-003 — Capability truthfulness.** Every advertised DAP capability SHALL have a
  working implementation and verification; implemented capabilities intended for client use
  SHALL be advertised when supported. Client capabilities SHALL be respected before sending
  optional events/features that require negotiation.
- **DBG-R-004 — Stop-epoch reference stability.** Frame IDs, scope IDs, variable references,
  source references, and related DAP handles SHALL remain valid for the lifetime required by
  the current stopped state and SHALL NOT be silently rebound to unrelated objects.

## Lifecycle and target ownership

- **DBG-R-005 — Explicit attach semantics.** Attaching to an existing HSX PID SHALL have
  explicit lock/observer semantics and SHALL not be disguised as a launch operation.
- **DBG-R-006 — Explicit launch/terminate/disconnect semantics.** Launch, terminate, kill,
  detach, and disconnect SHALL each have documented ownership/effect semantics. A UI action
  named terminate/stop SHALL not merely pause a live target unless that behavior is explicitly
  selected and surfaced.

## State, events, concurrency, and recovery

- **DBG-R-007 — Single authoritative debugger state model.** Debugger lifecycle, target run
  state, stop reason, connection state, breakpoint/watch desired state, and stop epochs SHALL
  have one authoritative debugger-controller owner rather than competing caches/timers/UI state.
- **DBG-R-008 — Serialized state transitions and DAP output.** Concurrent DAP requests,
  executive events, reconnect callbacks, keepalive, and fallback timers SHALL not race on
  mutable debugger state or produce out-of-order DAP sequence numbers/messages.
- **DBG-R-009 — Event-authoritative runtime state.** When the executive advertises reliable
  event support, task/debug state changes SHALL be driven by executive events. Polling SHALL
  not be a second competing source of truth.
- **DBG-R-010 — Designed fallback behavior.** Polling, fallback timers, cache refresh, retry,
  and compatibility fallbacks SHALL be capability-driven, bounded, observable, and tested.
  They SHALL not be added as local fixes without an owning design contract.
- **DBG-R-011 — Connection loss and event-stream recovery.** Loss of RPC transport or event
  stream SHALL be detected and surfaced. Reconnect SHALL either restore a consistent session
  (locks, target, breakpoints, watches, event subscription) or fail clearly without pretending
  the debugger remains healthy.
- **DBG-R-012 — Diagnostic observability.** Exceptions in event callbacks/background workers
  SHALL be logged with actionable context. Silent exception swallowing SHALL not hide a
  degraded debugger state.
- **DBG-R-013 — Healthy-idle efficiency.** A healthy event-capable debug session SHALL not
  continuously poll task/breakpoint state merely to remain synchronized.

## Breakpoints and watches

- **DBG-R-014 — Breakpoint ownership and reconciliation.** Source, function, instruction, CLI,
  and externally-created breakpoints SHALL have explicit ownership/provenance. Reconciliation
  SHALL preserve external breakpoints and converge desired vs remote state after reconnect.
- **DBG-R-015 — Watch ownership and reconciliation.** Watches SHALL have explicit
  ownership/provenance. A debugger client SHALL not delete a watch merely because it observed
  an event for a watch created by another client.

## Execution control and stepping

- **DBG-R-016 — Instruction step.** Instruction stepping SHALL execute exactly the defined
  HSX instruction-step semantic and stop with deterministic PC/state evidence.
- **DBG-R-017 — Source step into.** Step-into SHALL advance according to source mapping and
  enter called functions when source information permits.
- **DBG-R-018 — Source step over.** Step-over SHALL advance to the next source-level location
  in the current frame without stopping inside a called function unless execution faults or
  hits an independently active breakpoint.
- **DBG-R-019 — Source step out.** Step-out SHALL run until the current frame returns to its
  caller, or until another independently valid stop condition occurs.
- **DBG-R-020 — Stop reason fidelity.** User pause, breakpoint, instruction/source step,
  mailbox wait/timeout, sleep, fault, termination, and other supported states SHALL be mapped
  consistently to debugger-visible stop/run state without fabricated contradictory events.

## Inspection, symbols, and source mapping

- **DBG-R-021 — Stack fidelity.** Stack frames SHALL be reconstructed and presented with
  stable frame identity, PC/SP/FP where available, function/source metadata, and explicit
  diagnostics when reconstruction is incomplete.
- **DBG-R-022 — Variable fidelity.** Registers, locals, globals, and watches SHALL be resolved
  against the selected frame/stop epoch and SHALL not silently show stale or cross-frame data.
- **DBG-R-023 — Explicit address model.** HSX code/data address widths and masking rules used by
  debugger tooling SHALL come from an explicit architecture contract rather than hard-coded
  masks scattered through symbol/debugger code.
- **DBG-R-024 — Cross-platform source mapping.** Symbol/source path normalization and workspace
  mapping SHALL work on case-sensitive and case-insensitive filesystems and SHALL not globally
  lowercase source identity as an undocumented assumption.
- **DBG-R-025 — Memory/register/disassembly consistency.** Register, memory, disassembly, symbol,
  and source views SHALL refer to a consistent target snapshot/address model and surface
  unavailable data explicitly.

## Architecture and responsibility boundaries

- **DBG-R-026 — Executive-only runtime control.** Debugger frontends SHALL manipulate runtime
  state through the documented executive/debugger backend contract and SHALL not embed VM
  implementation logic or directly mutate VM internals.
- **DBG-R-027 — Debugger core/frontend separation.** Session/lifecycle policy, reconnect,
  stepping semantics, resource ownership/reconciliation, and snapshot state SHALL live in a
  shared debugger-core/controller layer reusable by CLI and DAP. The DAP adapter SHALL primarily
  translate between DAP and that core contract.
- **DBG-R-028 — Bounded module responsibilities.** Transport framing, lifecycle/state policy,
  symbol interpretation, breakpoint/watch resource policy, and IDE presentation SHALL be
  separate responsibility blocks with explicit interfaces and non-responsibilities.
- **DBG-R-029 — VS Code extension presentation boundary.** VS Code custom views and UI
  coordination SHALL consume debugger/DAP contracts and SHALL not become an independent source
  of target/debugger truth.
- **DBG-R-030 — Standard DAP experience first.** Core Call Stack, Variables, Watch,
  Breakpoints, source navigation, Debug Console, pause/continue, and stepping SHALL work through
  standard VS Code debugging surfaces before custom HSX views are required for normal debugging.

## Packaging, compatibility, and verification

- **DBG-R-031 — Version-coherent debugger package.** The VS Code extension and Python debugger
  runtime it executes SHALL have a defined compatible version relationship. Installing the
  extension SHALL not silently depend on whichever unrelated HSX source tree happens to be the
  current workspace.
- **DBG-R-032 — Production entrypoint verification.** Automated black-box DAP tests SHALL start
  the same adapter entrypoint and packaging path used by the actual VS Code extension.
- **DBG-R-033 — Cross-platform verification.** Required debugger behavior SHALL be verified on
  at least Windows and Linux; platform-specific skips require an explicit tracked gap.
- **DBG-R-034 — Compatibility behavior is contractual.** Legacy RPC fallbacks and compatibility
  shims SHALL be named, tested, version-scoped, and either retained intentionally or assigned a
  removal condition.
- **DBG-R-035 — Exact-head review and sign-off.** A substantial debugger Refactor SHALL not be
  complete until an independent reviewer has reviewed the exact implementation head and the
  required verification evidence is recorded against that head.
- **DBG-R-036 — Regression oracle before structural replacement.** Behavior intentionally
  preserved from the legacy debugger SHALL be captured by black-box/golden tests before the
  owning implementation is substantially replaced or moved.

## Legacy traceability mapping

| Legacy ID | New debugger baseline |
|---|---|
| `DR-8.1` Debug session & event stream | DBG-R-005, DBG-R-007..DBG-R-015, DBG-R-020, DBG-R-026..DBG-R-027 |
| `DG-8.1` CLI/TUI objectives | DBG-R-016..DBG-R-022, DBG-R-027, DBG-R-030 |
| `DG-8.2` Event handling & back-pressure | DBG-R-008..DBG-R-013 |
| `DG-8.3` Packaging & cross-platform | DBG-R-031..DBG-R-035 |
| `DG-3.3` Debug metadata export | dependency for DBG-R-021..DBG-R-025 |
| `DG-4.2` Debug/breakpoint semantics | HSX runtime dependency for DBG-R-014, DBG-R-016..DBG-R-020 |
| `DG-5.2/5.3` Event/session management | HSX executive dependency for DBG-R-005, DBG-R-009..DBG-R-015 |

This mapping does not delete or rewrite the legacy catalogue. It establishes the debugger
track's new stable requirement IDs while preserving provenance.
