# DBG-CR-001 — Legacy VS Code Debugger Code Review

Status: COMPLETE FOR GAP ANALYSIS  
Review date: 2026-08-19  
Reviewed baseline: `Implementation/vscode`  
Review purpose: evidence for `DBG-GAP-001`, not final implementation sign-off

## Scope

- DAP adapter and stdio transport
- shared debugger backend/session/symbol layers
- executive session/event transport used by debugger
- VS Code extension lifecycle and custom views
- debugger tests and packaging path
- legacy debugger design/implementation-plan consistency

## Severity model

- **Blocking/P0** — can invalidate the debug protocol/product path or its verification.
- **High/P1** — incorrect semantics, race, ownership/lifecycle error, or major structural risk.
- **Medium/P2** — maintainability/traceability/packaging/capability gap that must be resolved
  before Debugger 1.0 but need not precede the first baseline fixes.
- **Low/P3** — cleanup or minor hardening.

## Findings

### DBG-F-001 — Raw stdout corrupts the DAP transport

Severity: **Blocking/P0**  
Requirements: DBG-R-001, DBG-R-032

`vscode-hsx/debugAdapter/hsx-dap.py` prints argv and selected repo root to stdout.
`python/hsx_dap/__init__.py` also contains raw stdout prints for path/bootstrap/CLI/EOF
messages. DAP-over-stdio requires stdout to remain a framed protocol stream.

Risk: a valid VS Code launch can receive non-DAP bytes before a `Content-Length` header,
causing intermittent or immediate protocol failure.

### DBG-F-002 — `initialized` is emitted before the initialize response

Severity: **Blocking/P0**  
Requirements: DBG-R-002

`_handle_initialize()` emits the DAP `initialized` event inside the handler, while the
common request dispatcher sends the initialize response only after the handler returns.

Risk: invalid lifecycle ordering and breakpoint-configuration races.

### DBG-F-003 — Black-box test does not start the entrypoint used by VS Code

Severity: **Blocking/P0**  
Requirements: DBG-R-032, DBG-R-033, DBG-R-036

`python/tests/test_hsx_dap_cli.py` starts `python/hsx-dap.py`. The extension starts
`vscode-hsx/debugAdapter/hsx-dap.py`, which has different bootstrap behavior and is where
DBG-F-001 is directly observable.

Risk: CI can be green while the production launch path is broken.

### DBG-F-004 — Step into, over, and out currently share the same operation

Severity: **High/P1**  
Requirements: DBG-R-017, DBG-R-018, DBG-R-019, DBG-R-020

`_handle_next`, `_handle_stepIn`, and `_handle_stepOut` all call the same backend
`step(..., source_only=True)` path. The backend receives no requested step semantic.

Risk: VS Code labels three distinct operations that cannot be distinguished by the runtime.

### DBG-F-005 — Launch and attach are semantically collapsed

Severity: **High/P1**  
Requirements: DBG-R-005, DBG-R-006

`_handle_attach()` delegates directly to `_handle_launch()`, while launch itself requires an
already-existing PID. The VS Code manifest/snippet likewise uses `request: "launch"` for an
operation named Attach.

Risk: ownership, load/start behavior, disconnect policy, and error handling are ambiguous.

### DBG-F-006 — Terminate does not terminate the target

Severity: **High/P1**  
Requirements: DBG-R-006

The terminate path disables debug state, attempts to pause the current PID, sends a DAP
`terminated` event, and disconnects. It does not define or perform target termination.

Risk: UI intent and target behavior diverge; a supposedly stopped application can remain
alive and paused.

### DBG-F-007 — Frame/scope reference lifetimes are unsafe

Severity: **High/P1**  
Requirements: DBG-R-004, DBG-R-021, DBG-R-022

Each `stackTrace` clears the frame table and restarts IDs from 1. Each `scopes` request clears
all scope references and restarts IDs from 1.

Risk: VS Code can request variables for an earlier still-valid frame/scope reference after a
subsequent request has rebound or removed that numeric ID.

### DBG-F-008 — Mutable debugger state has multiple concurrent writers

Severity: **High/P1**  
Requirements: DBG-R-007, DBG-R-008

Adapter state can be mutated from the DAP request thread, executive event-stream callback
thread, pause/step timers, remote-breakpoint timer, and reconnect paths. State includes PID,
thread states, breakpoints, watches, pending step/pause flags, source refs, caches, and
connection state.

Risk: race-dependent contradictory DAP events and difficult-to-reproduce corruption.

### DBG-F-009 — DAP sequence assignment is outside the write lock

Severity: **High/P1**  
Requirements: DBG-R-008

`send_event`/`send_response` allocate/increment `seq` before `_send_message()` takes the
writer lock. Different threads can therefore allocate seq values and acquire the write lock
in the opposite order.

Risk: wire order may not match sequence order and the transport has no single serialized
outbound owner.

### DBG-F-010 — Event-stream death is not a first-class debugger state

Severity: **High/P1**  
Requirements: DBG-R-009, DBG-R-011, DBG-R-012

`ExecutiveSession` can exit the event worker and clear its internal stream, but the adapter
has no explicit stream-lost callback/state transition. `_event_stream_active` may remain
stale at the adapter level.

Risk: debugger appears connected while stop/output/watch events no longer arrive.

### DBG-F-011 — Event callback failures can be silently swallowed

Severity: **High/P1**  
Requirements: DBG-R-011, DBG-R-012

`ExecutiveSession._event_stream_worker()` catches exceptions from the registered event
callback and continues without surfacing the failure.

Risk: a bug in adapter event handling can make state updates disappear without a useful
failure signal.

### DBG-F-012 — Watches observed from other clients can become locally owned

Severity: **High/P1**  
Requirements: DBG-R-015

`watch_update` events populate the adapter's local expression/id maps even when the watch was
not created by this adapter. Shutdown cleanup then removes IDs from those maps.

Risk: closing VS Code may remove CLI/external watches.

### DBG-F-013 — Runtime state has competing event, polling, cache, and timer authorities

Severity: **High/P1**  
Requirements: DBG-R-007, DBG-R-009, DBG-R-010, DBG-R-013, DBG-R-020

The adapter consumes executive task/debug events while also polling `ps`/breakpoint state,
using cached task snapshots, synthesizing pause/step completion via timers, and suppressing
duplicate stop events.

Risk: a late event, stale poll, or fallback can contradict another state source; added fixes
create further compensating logic.

### DBG-F-014 — Breakpoint policy/reconciliation remains adapter-owned and duplicated

Severity: **High/P1**  
Requirements: DBG-R-014, DBG-R-027, DBG-R-028

The adapter owns source/function/instruction breakpoint specs, pending/reapply state, remote
breakpoint polling, readonly external entries, temporary disable/restore, reconnect replay,
and DAP mapping. This is debugger-core policy rather than DAP translation.

Risk: CLI and DAP behavior can diverge and future fixes must be replicated.

### DBG-F-015 — `python/hsx_dap/__init__.py` is a responsibility monolith

Severity: **High/P1**  
Requirements: DBG-R-007, DBG-R-027, DBG-R-028

The module owns DAP framing/dispatch, lifecycle, reconnect, state synchronization, stepping,
breakpoints, watches, symbol/source interpretation, frame/scope references, memory/register
formatting, disassembly, telemetry, and compatibility fallbacks.

Risk: structural comprehension degrades and local fixes produce cross-feature regressions.

### DBG-F-016 — `vscode-hsx/src/extension.ts` is a second responsibility monolith

Severity: **High/P1**  
Requirements: DBG-R-028, DBG-R-029, DBG-R-030

The file owns configuration, adapter launch/bootstrap, status tracking, coordinator state,
memory/register/stack/disassembly/trace views, breakpoint UI, and many commands.

Risk: UI lifecycle and debug-state behavior are difficult to isolate/test and can drift from
DAP/core semantics.

### DBG-F-017 — Adapter still leaks raw executive RPC through the backend abstraction

Severity: **Medium/P2**  
Requirements: DBG-R-026, DBG-R-027, DBG-R-034

For example, disassembly constructs `disasm.read`/legacy `disasm` payloads and calls generic
backend `request` directly even though `ExecutiveSession`/backend already contain disassembly
helpers and compatibility logic.

Risk: frontend code owns RPC compatibility decisions and bypasses typed/shared contracts.

### DBG-F-018 — DAP capability declaration has drifted from implemented handlers

Severity: **Medium/P2**  
Requirements: DBG-R-003

The adapter implements function breakpoints and evaluation behavior but its initialize
capabilities do not consistently advertise the corresponding DAP support; optional event use
is not consistently gated on client capabilities.

Risk: features remain undiscoverable or are used without negotiated support.

### DBG-F-019 — Symbol/address width is hard-coded in debugger code

Severity: **Medium/P2**  
Requirements: DBG-R-023

`SymbolIndex` masks instruction/symbol addresses with `0xFFFF` in multiple places rather than
consuming a named HSX architecture address contract.

Risk: hidden architecture assumptions and future target/address-space migration bugs.

### DBG-F-020 — Source identity globally lowercases paths

Severity: **Medium/P2**  
Requirements: DBG-R-024

Both adapter/symbol helpers canonicalize source paths by converting them to lowercase.

Risk: incorrect identity/mapping on case-sensitive filesystems and accidental collisions.

### DBG-F-021 — VS Code packaging depends on an external workspace Python tree

Severity: **High/P1**  
Requirements: DBG-R-031, DBG-R-032

The extension packages its wrapper, but the wrapper locates `python/` from the workspace/repo
and the extension injects workspace paths into `PYTHONPATH`. The extension therefore does not
have a clearly version-locked debugger runtime independent of the HSX source workspace.

Risk: extension/runtime version skew and failure when debugging another project/workspace.

### DBG-F-022 — Windows product-path DAP verification is missing

Severity: **High/P1**  
Requirements: DBG-R-033

The subprocess DAP test is explicitly skipped on Windows, while Windows is a required
development platform and the project has historically been exercised there.

Risk: transport/bootstrap/path behavior can regress on the primary platform without CI evidence.

### DBG-F-023 — VS Code automated tests cover little of the extension behavior

Severity: **Medium/P2**  
Requirements: DBG-R-029, DBG-R-030, DBG-R-032, DBG-R-036

The npm test compiles and runs a configuration-provider test. The coordinator, status/event
handling, custom views, adapter wrapper, commands, and extension/debug-session lifecycle do
not have comparable automated coverage.

Risk: large extension changes can compile while behavior regresses.

### DBG-F-024 — Legacy documents are internally inconsistent with current implementation

Severity: **High/P1 traceability risk**  
Requirements: DBG-R-035, DBG-R-036

The legacy debugger/DAP design documents include older direct-RPC structures; implementation
plans contain earlier unchecked work mixed with later prose indicating completion. They are
not a reliable CurrentIndex/source of truth.

Risk: a new agent can implement obsolete work, duplicate logic, or reverse later decisions.

### DBG-F-025 — `backend` and `client` aliases duplicate connection identity in adapter state

Severity: **Medium/P2**  
Requirements: DBG-R-007, DBG-R-027

The adapter stores both `self.backend` and `self.client`, generally pointing to the same
`DebuggerBackend`, and lifecycle methods must keep both synchronized.

Risk: unnecessary state duplication and future split-brain bugs during reconnect/shutdown.

### DBG-F-026 — Debugger core behavior is not yet the sole API used by both frontends

Severity: **High/P1**  
Requirements: DBG-R-027, DBG-R-036

The creation of `hsx_dbg` improved sharing, but DAP still owns substantial policy and the CLI
and DAP do not yet reduce to thin frontends over one stateful controller contract.

Risk: fixes continue to diverge across debugger frontends.

## Positive findings to preserve

1. `DebuggerBackend` is a useful typed boundary over many executive operations.
2. `DebuggerSession` is a useful seed for explicit connection ownership.
3. `SymbolIndex` centralizes much symbol/source lookup behavior and can be evolved rather
   than discarded blindly.
4. `ExecutiveSession` already implements significant session/event/keepalive behavior.
5. The DAP harness contains useful regression scenarios for breakpoints, reconnect, stack,
   scopes, watches, disassembly, and PID loss.
6. The VS Code extension already proves that useful HSX-specific memory/register/stack/
   disassembly/trace UX can be built on top of DAP.

## Review conclusion

The debugger should not receive another feature-by-feature patch pass on its current
responsibility structure. The next work is `DBG-GAP-001`, followed by narrowly scoped P0
baseline repair and then `DBG-DA-001` to design the optimal modular debugger before structural
replacement. Existing code is retained as evidence/reference until replacement behavior is
verified.
