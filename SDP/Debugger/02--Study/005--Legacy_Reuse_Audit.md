# DBG-ST-005 — Legacy Reuse, Adapt, Replace, and Regression-Oracle Audit

- Status: **COMPLETE FOR MASTER SYNTHESIS**
- DesignAnalysis: `DBG-DA-001`
- Iteration: `DBG-IT-001-002`
- Owning issue: #38
- Study baseline: activation head `ea2b53728de5abfe9e9482560390bd1a2de6c9d2`
- Product evidence baseline: `Implementation/vscode` at
  `a1daa1c62605c44ac67e58e2b71320006f73cdd9`, plus signed `DBG-RF-001`
  implementation head `208063e344b767f82790ce579eba6327e2cdd0ce`

## Question and decision vocabulary

Which current debugger components and behaviors should be reused, adapted/extracted,
replaced, or retired without allowing legacy file boundaries to dictate the target
architecture?

- **Reuse** means the implementation and its present responsibility are suitable to carry
  forward behind a frozen interface and stronger tests.
- **Adapt/extract** means useful semantics, data, or algorithms survive, but state ownership,
  API shape, or module location must change.
- **Replace** means the current ownership/mechanism is inconsistent with accepted requirements;
  only explicitly selected external behavior may be used as a regression oracle.
- **Retire** means the behavior or compatibility surface is not part of the target product and
  is removed only after its stated migration condition is proven.

These are Study recommendations for Master synthesis. Descriptive target-owner names below
are concepts, not allocated `DBG-A-*` or `DBG-D-*` identifiers and not implementation
authority.

## Evidence inspected

Primary code evidence:

- `python/hsx_dbg/backend.py` — typed RPC façade and `RegisterState`, `StackFrame`, and
  `WatchValue` data;
- `python/hsx_dbg/session.py` — one-backend connection ownership and reconnect inputs;
- `python/hsx_dbg/symbols.py` — `.sym` parsing and lookup caches;
- `python/hsx_dbg/context.py`, CLI commands, and entrypoints — the other current frontend;
- `python/executive_session.py` — session negotiation, per-request sockets, keepalive,
  capability probes, caches, event stream, retries, and legacy command fallback;
- `python/hsx_dap/__init__.py` — DAP framing, dispatch, lifecycle, controller-like state,
  recovery, resources, inspection, evaluation, source mapping, and event translation;
- `python/hsx-dap.py` and `vscode-hsx/debugAdapter/hsx-dap.py` — development and production
  launch paths;
- `vscode-hsx/src/extension.ts` and `vscode-hsx/package.json` — configuration, runtime launch,
  status/coordinator state, custom views, breakpoint projection, commands, and package surface.

Primary test/oracle evidence:

- `python/tests/test_hsx_dbg_backend.py`, `test_hsx_dbg_symbols.py`,
  `test_executive_session_helpers.py`, and relevant `test_executive_sessions.py` scenarios;
- `python/tests/test_hsx_dap_harness.py`, `test_hsx_dap_reconnect.py`, and
  `test_hsx_dap_cli.py`;
- `python/tests/dap_stubs.py`, `fixtures/sample_debug.sym`, and
  `fixtures/breakpoints_golden.json`;
- `vscode-hsx/src/test/configProvider.test.ts` and the extension package scripts.

Normative/evidence inputs were `DBG-ST-001`, `DBG-CR-001` including `DBG-F-001..026`,
accepted `DBG-GAP-001`, accepted `DBG-R-001..036`, the active `DBG-DA-001` and
`DBG-IT-001-002` contracts, and issue #38 including Steering directive `5345600066`.
Matrix shorthand `F-*` and `R-*` below always means the Debugger-track identifiers
`DBG-F-*` and `DBG-R-*`.

## Component audit — shared Python core and executive boundary

| Current component/responsibility | Decision | Useful semantics/API/data to preserve | Proposed target responsibility owner | Primary evidence mapping | Risk | Prerequisite / regression oracle | Migration or retirement condition |
|---|---|---|---|---|---|---|---|
| `python/hsx_dbg/backend.py`: `RegisterState`, `StackFrame`, `WatchValue`, error normalization, and typed command/result conversion | **Adapt/extract** | Named data shapes; integer normalization; full-width breakpoint preservation; typed pause/resume, register, stack, memory, watch, trace, symbol, and breakpoint calls | **Debugger-facing Executive Gateway** for typed executive commands; immutable snapshot/result types owned by an **Inspection Model** | F-017, F-019, F-026; R-021..R-028, R-034, R-036 | Current class also owns a session and attached PID, exposes unrestricted `request`, and mixes protocol fallback with domain calls; data are mutable and not stop-epoch tagged | Preserve backend unit vectors and add typed success/error/unsupported, address-width, cancellation, session-generation, and snapshot-version tests | Keep imports through a compatibility façade while consumers move to typed interfaces. Remove generic frontend `request` only when no DAP/CLI caller constructs RPC payloads and compatibility commands live solely in the gateway |
| `backend.py`: `_attached_pid`, `ensure_session`, `configure`, and direct lifecycle ownership | **Replace** | Host/port/client/features configuration inputs only | **Connection/Session Supervisor**, with target identity owned by the authoritative **Debugger Controller** | F-008, F-013, F-025, F-026; R-005..R-013, R-027..R-028 | Competes with `DebuggerSession`, `HSXDebugAdapter.current_pid`, `backend/client`, and executive session state | Contract tests for connect/attach/observer/disconnect plus controller state-transition tests | Retire local attached-PID truth after every frontend obtains session and target state from the controller snapshot |
| `python/hsx_dbg/session.py`: `DebuggerSession` connection factory and saved `connection_config` | **Adapt/extract** | Single connection handle; explicit connect/disconnect; observer, keepalive, heartbeat, and reconnect inputs; defensive idempotent teardown | **Connection/Session Supervisor** beneath the controller | F-005, F-008, F-010, F-013, F-025; R-005..R-013, R-027, R-034 | It currently combines attach with connect, catches teardown failures, retains stale reconnect inputs, and has no lifecycle or health model | Existing connect/disconnect unit test, extended with launch-vs-attach, stream-loss, target-loss, generation, and teardown assertions | Keep a façade for current imports until DAP and CLI use the controller. Retire the class as a second state owner once the supervisor exposes the accepted session API |
| `python/hsx_dbg/symbols.py`: `.sym` JSON parsing, instruction/source map, functions/labels/locals/globals, completion, and lookup aliases | **Adapt/extract** | Parser coverage, lookup indexes, de-duplication order, PC metadata, locals/globals data, `lookup` alias during migration | **Symbol/Source Service**, parameterized by a portable **Address Model** and a case-aware **Source Identity/Mapper** | F-007, F-019, F-020; R-004, R-021..R-025, R-036 | `0xFFFF` masks silently truncate; global lowercase collapses distinct files; filename-only aliases may be ambiguous; no schema/version diagnostics | Preserve fixture lookups, then add >16-bit, case-sensitive collision, directory/remap, duplicate-basename, malformed metadata, and reload/version tests | Load through the new service in parallel and compare results. Remove masks/lowercase behavior only with accepted HSX address/source contracts and golden migration cases |
| `python/hsx_dbg/context.py` target/session, breakpoint, stack, and symbol state used by CLI commands | **Replace policy; adapt CLI shell** | REPL, parser, history, output modes, command registry, aliases, scripting, and user-facing command vocabulary | **Thin CLI Frontend** consuming the same controller/query/command API as DAP | F-014, F-019, F-020, F-026; R-014..R-030, R-036 | CLI currently bypasses `DebuggerBackend`/`DebuggerSession`, owns independent breakpoint IDs, stack/frame selection, 16-bit masks, and event policy | Existing CLI parser/history/completion/command/script tests remain UI oracles; add cross-frontend controller contract scenarios | Retain the legacy CLI runnable while commands are migrated one vertical behavior at a time. Remove `DebuggerContext` domain caches only after CLI/DAP parity tests use one controller |
| `python/executive_session.py`: `session.open/close`, PID locks, request/retry, keepalive, protocol-version errors, and per-request JSON transport | **Adapt/extract** | Session negotiation fields; explicit `ConnectionLostError`/`ProtocolVersionError`; PID-lock validation; bounded retry intent; keepalive; negotiated features; deep-copy result isolation | **Executive Transport** owns sockets/framing; **Session Supervisor** owns session/keepalive/capability generation; neither owns debugger policy | F-010, F-011, F-013, F-017, F-026; R-005, R-008..R-013, R-026..R-028, R-034 | Blocking sleeps, force-reopen during requests, locks plus background joins, implicit retry side effects, and feature state can create hidden transitions | Existing helper/session tests plus deterministic fault injection for timeout, loss during request, re-open, keepalive death, and protocol mismatch | Preserve wire compatibility behind the typed gateway. Replace internals incrementally; retire direct construction by frontends when the supervisor is the only owner |
| `executive_session.py`: event socket, buffer, callback thread, acking, and stream cleanup | **Replace** | Event envelope and sequence/ack semantics; bounded recent-event buffer may survive as diagnostics only | **Executive Event Transport** reports ordered events and explicit health transitions into the controller's serialized inbox | F-008, F-010, F-011, F-013; R-007..R-013, R-020, R-028 | EOF has no health callback; malformed JSON and callback/ack exceptions are swallowed; callback mutates DAP state on the worker thread; stream truth can go stale | Add EOF, malformed frame, callback failure, ack failure/backpressure, duplicate/out-of-order sequence, and resubscribe tests | Legacy worker stays available behind a compatibility adapter until new transport proves event ordering and health/recovery. Remove silent catches when diagnostics and failure transitions are asserted |
| `executive_session.py`: stack/symbol/memory/watch/disassembly helpers, support flags, stack cache, and `disasm.read`→`disasm` fallback | **Adapt/extract** | Typed payload construction; defensive copies; unsupported detection; stack/disassembly compatibility behavior; feature probe results | **Debugger-facing Executive Gateway**; compatibility selection owned by a version/capability registry; snapshot caches owned by inspection/controller, not transport | F-010, F-013, F-017; R-009..R-013, R-021..R-028, R-034 | Cache lacks stop epoch; support flags can outlive a reconnected server generation; duplicate helpers exist in backend/DAP; error-string parsing is fragile | Existing helper tests plus negotiated-version matrix, reconnect-generation invalidation, no-cross-epoch cache, and legacy/current golden RPC tests | Keep named fallbacks only for declared executive versions. Remove each fallback when the minimum supported executive version guarantees the typed command and release telemetry shows no legacy use |

## Component audit — DAP adapter and entrypoints

| Current component/responsibility | Decision | Useful semantics/API/data to preserve | Proposed target responsibility owner | Primary evidence mapping | Risk | Prerequisite / regression oracle | Migration or retirement condition |
|---|---|---|---|---|---|---|---|
| `python/hsx_dap/__init__.py`: `DAPProtocol` framing/parser and response/event writing | **Adapt/extract** | Correct `Content-Length` wire shape, strict stdio purity established by `DBG-RF-001`, response/event builders | **DAP Wire Transport** with exactly one outbound serializer that allocates sequence numbers and writes in the same serialized operation | F-001, F-002, F-009; R-001, R-002, R-008, R-032, R-036 | Sequence allocation is still outside `_write_lock`; parser treats malformed/missing length as EOF rather than a surfaced protocol error | Signed production-wrapper framing/order tests; add concurrent response/event order, partial read, malformed header/body, oversized input, EOF, and writer failure tests | Route legacy adapter output through the extracted transport first. Delete old writer only after exact product-entrypoint concurrency tests prove monotonic wire-order sequence values |
| DAP reflection dispatch, initialize capabilities, request error mapping, and `initialized` sequencing | **Adapt/extract**, with capability policy **replaced** | Request/response envelope mapping and post-response `initialized` ordering from `DBG-RF-001` | **DAP Router** validates/dispatches; **DAP Capability/Lifecycle Mapper** derives claims from accepted controller capabilities and client negotiation | F-002, F-018; R-002, R-003, R-027..R-030, R-032, R-036 | Reflection exposes accidental handlers/aliases; capability list drifts; client capabilities are not retained/gated | Production initialize oracle plus capability-to-handler matrix and optional-event negotiation tests | Keep command names stable while handlers delegate to new mappers. Retire reflection and hard-coded capability claims when the explicit registry is complete |
| Adapter `_connect`, `backend/client`, current PID, reconnect, thread/run caches, polling, timers, backoff, duplicate-stop suppression, and event callback mutation | **Replace** | User-visible connection/degraded/error status; cached reconnect inputs as command intent; useful event-to-stop evidence | Single serialized **Debugger Controller** owns connection/target/run/stop state, stop epoch, recovery, and emits frontend-neutral events; **Session Supervisor** performs I/O | F-008, F-010, F-011, F-013, F-025, F-026; R-007..R-013, R-020, R-027..R-028 | This is the principal multi-writer/compensating-mechanism cluster; timers and event thread can contradict requests/polls, and dual aliases can split | State-transition/property tests across DAP requests, executive events, timers, target loss, reconnect and shutdown; healthy-idle no-poll measurement | Run the new controller behind a feature-selectable adapter path while the legacy adapter remains executable. Remove legacy state fields only after black-box traces match intended—not defective—behavior |
| Frame IDs, scope/variable references, source references, `_FrameRecord`, `_ScopeRecord`, and scope formatting | **Replace handles; adapt data/mapping** | DAP response shapes; frame/source metadata; register/local/global/watch presentation concepts | **Stop-Epoch Snapshot Store** owns immutable target data and handle lifetimes; **DAP Inspection Mapper** allocates DAP handles for one epoch without fetching policy | F-007, F-015; R-004, R-021, R-022, R-025, R-027..R-028, R-036 | `stackTrace` and `scopes` clear and reuse IDs; `_resolve_frame` silently falls back to another frame; values are fetched at different times | Add repeated/paged stackTrace, out-of-order scopes/variables, stale-epoch rejection, selected-frame, concurrent inspection, and unavailable-data tests | Preserve wire shapes, not ID values. Switch inspection requests to epoch handles; retire fallback-to-first-frame and mutable maps after lifecycle tests cover resume/re-stop |
| Source/function/instruction breakpoint specs, remote poll/reapply, readonly entries, temporary disable/restore, clear-all, and watch maps/cleanup | **Replace policy; adapt translation** | DAP request parsing/result shapes; source/function/instruction resolution inputs; reconnect intent; external-resource visibility; breakpoint events | Frontend-neutral **Resource Catalog/Reconciler** owns desired vs observed resources, owner/provenance, identities, and reconciliation; DAP only maps requests/events | F-012, F-014, F-015, F-026; R-014, R-015, R-027..R-030, R-034, R-036 | Observed watches can be adopted and deleted; external breakpoints can be cleared; extension also owns instruction sets; polling competes with events | Extend golden cases to multi-client ownership, external preservation, idempotence, reconnect, replace-by-owner, observer mode, temporary step behavior, and clear-only-owned | Introduce provenance alongside legacy collections and compare remote results. Retire adapter cleanup/polling after reconciler convergence and external-resource tests pass |
| Instruction step, source next/into/out, pause/continue, launch/attach, disconnect/terminate, debug-state toggling, and step/pause fallback timers | **Replace semantics; retain request names** | Instruction-step request plumbing; explicit source vs instruction intent; debug-state compatibility signal; stop descriptions as candidate UX | **Lifecycle and Execution Service** under controller, backed by accepted HSX execution/stack/address contracts; DAP mapper remains semantic-free | F-004, F-005, F-006, F-013, F-015; R-005, R-006, R-010, R-016..R-020, R-026..R-030, R-034, R-036 | Source steps are identical; attach calls launch; terminate pauses; timers fabricate stops; breakpoint suppression can alter external resources | Do **not** preserve the known-bad terminate/step tests as normative. Add accepted launch/attach/kill/detach ownership, instruction PC, into/over/out call-depth/source, independent breakpoint/fault, and stop-reason golden scenarios | Keep legacy operations only on the legacy adapter path. Enable each new semantic only after the required HSX contract exists; remove timers/fallbacks only when event capability or an explicitly versioned fallback proves completion |
| Symbol loading, source path/root resolution, evaluate, locals/globals/register formatting, memory, and disassembly formatting/raw RPC | **Adapt/extract** | DAP shape conversion, expression vocabulary (`register`, address/deref, symbol), source rendering, disassembly operand normalization, base64 memory encoding | **Symbol/Source and Inspection Services** own meaning/snapshots; **DAP Inspection Mapper** owns only DAP encoding; typed gateway owns disassembly compatibility | F-007, F-015, F-017, F-019, F-020; R-004, R-021..R-028, R-030, R-034, R-036 | Mixed stop times; hard-coded masks/format widths; workspace inference; DAP constructs RPC; expression evaluation can mutate watches | Existing stack/scope/disassembly/memory/evaluate fixtures plus address-width, stale epoch, source remap/case, unavailable memory, malformed symbols, and pure-evaluate tests | Move pure formatters first, then queries. Retire DAP raw `request`, global lowercase identity, and implicit evaluate→watch creation when typed/query contracts cover all callers |
| Custom telemetry for connection, debug state, breakpoint sync, and disassembly refresh; output event forwarding | **Adapt/extract** | Connection status text, output category mapping, degraded-state observability, refresh hints where DAP lacks a standard event | **Frontend Event Mapper** converts controller events; VS Code status/views consume presentation events without owning truth | F-010..F-013, F-016, F-023; R-009..R-013, R-020, R-029, R-030, R-036 | Ad-hoc telemetry schema is unversioned; it can expose contradictory state and custom UI depends on it | Golden frontend-event traces, schema/version tests, standard DAP-event priority, and degraded/recovered lifecycle tests | Retain named telemetry only while custom UI requires information unavailable in standard DAP. Remove each event after its view uses a standard DAP surface or a versioned extension contract |
| `python/hsx-dap.py` development entrypoint and `vscode-hsx/debugAdapter/hsx-dap.py` production wrapper | **Adapt, then converge** | CLI options, clean stderr diagnostics, strict stdio, production wrapper location as the current oracle | One installed, versioned **Debugger Runtime Entrypoint** used by VS Code and black-box tests; thin development alias may call it | F-001, F-003, F-021, F-022; R-001, R-031..R-036 | Two bootstrap paths drift; wrapper searches arbitrary repo/workspace trees and prints implementation detail; import identity differs (`python.hsx_dap`/`hsx_dap`) | Signed `DBG-RF-001` launch+attach subprocess oracle, repeated shutdown, clean-install, no-workspace-source, mismatch, Windows and Linux tests | Preserve current wrapper until packaged entrypoint passes the same strict oracle. Retire repo-root probing and duplicate script only after the extension invokes the bundled/version-locked runtime |

## Component audit — Python tests and fixtures

| Current component/responsibility | Decision | Useful semantics/API/data to preserve | Proposed target responsibility owner | Primary evidence mapping | Risk | Prerequisite / regression oracle | Migration or retirement condition |
|---|---|---|---|---|---|---|---|
| `test_hsx_dbg_backend.py`, `test_hsx_dbg_symbols.py`, and session/helper tests | **Reuse and extend**, then retarget to extracted interfaces | Typed payload/result conversion; observer/session inputs; full-width breakpoints; stack/register/memory parsing; symbol/PC/locals/globals lookup; unsupported capability behavior | Component contract suites for **Gateway**, **Session Supervisor**, and **Symbol/Source Service** | F-017, F-019, F-020, F-025, F-026; R-005, R-011, R-021..R-028, R-034, R-036 | Coverage is shallow and synchronous; current assertions can freeze class layout instead of behavior; no epoch/generation model | Preserve vectors as characterization tests and add boundary/fault/address/source cases before moving code | Delete legacy-class-specific tests only after equivalent target-interface tests retain every intentional vector and a coverage mapping identifies intentional changes |
| `test_hsx_dap_harness.py` and `test_hsx_dap_reconnect.py` white-box handler/state tests | **Adapt into contract/golden tests** | Breakpoint/source/function/instruction scenarios; stack/scopes shape; disassembly normalization; memory error; trace/register requests; reconnect intent; stop/output/status events | **DAP Mapper** contract tests plus controller scenario fixtures | F-004..F-018, F-025, F-026; R-002..R-020, R-027..R-030, R-034, R-036 | Private-method coupling locks in the monolith; several tests encode known defects/compensations, notably terminate-as-pause, identical source steps, timer fallbacks, clear-all external resources, and duplicate suppression | Classify every case as preserve/change/retire before refactor. Capture message-level request→controller command→DAP result/event traces | Keep legacy tests runnable but do not require known-bad assertions on the new path. Retire private-layout tests only when black-box/contract replacements exist and intentional divergences are documented |
| `test_hsx_dap_cli.py` strict production-entrypoint subprocess test from `DBG-RF-001` | **Reuse as the anchor oracle and extend** | Exact wrapper launch, strict frame parser, initialize-response-before-event, launch and attach handshake, breakpoint configuration, clean EOF/shutdown, Windows execution | Product-path black-box suite for the packaged **DAP Runtime** | F-001..F-003, F-022; R-001, R-002, R-032, initial R-033/R-036 | Stubbed executive omits real event/concurrency/recovery behavior; only a small lifecycle; no Linux PASS yet | Keep exact-head signed baseline; add concurrent events, full lifecycle, faults/reconnect, standard UI capabilities, packaged install, Windows/Linux | Never weaken framing. Change only the invoked entrypoint when the packaged path is ready, running old and new in parallel first |
| `dap_stubs.py`, `sample_debug.sym`, and `breakpoints_golden.json` | **Adapt and version** | Deterministic typed target data; known source/function address mapping; backend injection seam | Versioned **Debugger Scenario Fixtures** shared across controller, DAP, CLI, and product-path suites | F-003, F-004, F-007, F-012..F-020; R-004, R-014..R-025, R-032..R-036 | Stub silently masks breakpoints to 16 bits, lacks events/health/ownership/generations, and its `add_watch` signature differs from production; fixture schema is too small | Add explicit architecture profile, >16-bit values, call-depth, multi-client resources, event sequences, source collisions, malformed/partial data, and capability versions | Preserve current fixture version for legacy comparisons. Remove implicit 16-bit/method-signature quirks once both paths use a declared fixture contract |
| `test_executive_sessions.py` server-side event/session/stack/watch/disassembly/step cases | **Reuse as HSX-side evidence; extend cross-boundary tests** | Lock/heartbeat/session, event queue/ack/backpressure, task stop reasons, breakpoint/watch, source-only step, stack/disassembly behavior | Executive protocol contract suite consumed by **Gateway/Controller** fixtures; portable runtime semantics remain an HSX-track dependency | F-004, F-010..F-014, F-017; R-005, R-009..R-020, R-021..R-026, R-034, R-036 | Server unit success does not prove client recovery, exact stepping semantics, multi-client provenance, or packaging | Cross-track accepted address, execution, event-health, lock/kill/detach, symbol/debug metadata contracts plus client/server integration tests | Retain permanently as server regression evidence; debugger may not infer missing guarantees merely because these unit tests pass |

## Component audit — VS Code extension, package, tests, and custom behaviors

| Current component/responsibility | Decision | Useful semantics/API/data to preserve | Proposed target responsibility owner | Primary evidence mapping | Risk | Prerequisite / regression oracle | Migration or retirement condition |
|---|---|---|---|---|---|---|---|
| `extension.ts`: `HSXConfigurationProvider` defaults and validation | **Adapt/extract** | Host/port/PID/interpreter/log/observer/heartbeat inputs and integer validation | Small **VS Code Debug Configuration** module, with separate launch and attach schemas generated/validated against lifecycle contracts | F-005, F-016, F-023; R-002, R-005, R-006, R-028..R-032, R-036 | Default `request: launch` and attach snippet using launch encode wrong ownership; manifest and TypeScript validation can drift | Existing config test, expanded to launch/attach required fields, observer semantics, invalid values, variable expansion, and manifest parity | Keep legacy config accepted through a named migration normalizer. Remove launch-as-attach mapping after users receive a migration diagnostic and true attach/launch pass product tests |
| `extension.ts`: `HSXAdapterFactory` interpreter selection, arguments, logs, environment merge, and fingerprint | **Adapt launcher; replace bootstrap contract** | Configurable Python interpreter, isolated stderr/log destination, deterministic args, extension version/fingerprint concept | **Version-Coherent Runtime Launcher** that resolves only the bundled/declared runtime and performs an explicit compatibility handshake | F-016, F-021, F-022; R-001, R-031..R-034, R-036 | Injecting workspace root/PYTHONPATH permits arbitrary version skew; fingerprint covers extension assets but not the loaded external runtime | Clean VSIX install with unrelated workspace, missing interpreter/runtime, version match/mismatch, env isolation, paths with spaces, Windows/Linux | Preserve interpreter override only if it runs the same installed runtime package. Remove workspace repo probing/PYTHONPATH injection after package tests pass |
| `extension.ts`: `HSXStatusTracker` and `HSXDebugViewCoordinator` message fan-out | **Adapt/extract presentation; retire state authority** | Status rendering, per-session routing, view registration/refresh, frame metadata as a presentation hint | **VS Code Session Presenter** consumes standard DAP plus versioned optional presentation events; no target/controller truth | F-008, F-013, F-016, F-023; R-007, R-020, R-028..R-030, R-036 | `sessionStates`/`debugState` duplicate controller state; initialized is assumed stopped; refresh fan-out may race or overfetch; `instanceof` couples modules | Tracker trace tests for multiple sessions, stopped/continued/terminated/degraded sequences, disposal, refresh coalescing, and no state-derived target commands | Extract views one at a time. Remove run/debug state maps once commands use VS Code standard state/actions and presenters render controller-derived events only |
| Extension play/pause, stop, step, clear-all, address resolution, memory/register helper commands | **Replace control policy; adapt UI commands** | User commands, warnings/errors, clipboard/formatting, and standard DAP `readMemory`/`writeMemory`/`evaluate` use | **Command Presentation** invokes standard VS Code debug commands/DAP where available; optional HSX requests are versioned presentation extensions only | F-006, F-012, F-014, F-016, F-023; R-006, R-014..R-020, R-025, R-029, R-030, R-034, R-036 | `stop` sends known-bad terminate semantics; global clear removes all VS Code/remote resources; `singleStepInFlight` is extension-owned execution state | Command-level fake-session tests and VS Code integration scenarios for standard stop/continue/pause/step/breakpoint behavior and ownership | Preserve command IDs during migration. Remove custom control requests and local in-flight truth when standard DAP commands provide accepted semantics |
| Memory custom view | **Adapt as optional expert view** | Base-address persistence, 128-byte/16-byte-row visualization, write bytes, ASCII/hex formatting | Isolated **Memory View Presenter** over standard DAP memory requests and controller-consistent stopped snapshot | F-016, F-023; R-025, R-028..R-030, R-036 | Auto-refresh can read while running or from a different epoch; duplicates some standard memory UX; errors are collapsed | Presenter unit tests, stopped/running/unavailable state, epoch change, read/write error, formatting, and standard memory-view comparison | Retain only as additive HSX UX. Retire if standard VS Code memory UI reaches parity and no HSX-specific value remains |
| Registers custom view | **Retire as required UI; optionally retain a thin expert formatter** | Copy/export and HSX-specific register naming may remain useful | Standard **Variables/Registers DAP Surface** first; optional stateless presenter only | F-016, F-023; R-022, R-025, R-029, R-030, R-036 | Duplicates Registers scope through a custom request and may show a different-time snapshot | Standard Variables/Registers and selected-frame/epoch tests; optional view comparison | Remove custom `readRegisters` dependency when standard scopes expose all registers with parity; keep copy-only convenience only if requested |
| Raw stack-memory custom view | **Adapt/rename as optional Stack Memory view**, not Call Stack | SP-relative memory rows, ASCII/word formatting, copy behavior | **Stack Memory Presenter** over standard memory/evaluate; standard Call Stack remains authoritative | F-007, F-016, F-023; R-021, R-022, R-025, R-029, R-030, R-036 | Name can imply reconstructed frames; reads SP and memory separately; currently ignores selected frame and stop epoch | Standard Call Stack parity plus explicit top/selected-frame stack-memory snapshot tests | Retain only with clear labeling and same-epoch data. Retire if it cannot consume an atomic snapshot or adds no value beyond standard views |
| Disassembly custom view: follow PC/manual base, source links, copy, windowing, and formatting | **Adapt/extract as optional expert view** | Follow/manual navigation, source/symbol annotation, copy formatting, PC highlight, graceful unavailable state | **Disassembly View Presenter** over standard DAP disassemble and standard instruction breakpoint APIs | F-014, F-016, F-023; R-014, R-023..R-025, R-028..R-030, R-036 | Uses separate evaluate/read timing, hard-coded max instruction bytes/window arithmetic, and locally caches resource truth | Pure formatter/window tests plus address-profile, selected frame, epoch, source link, standard disassembly parity, and unavailable data cases | Retain additive navigation UX; remove local address assumptions and resource sets before target path becomes default |
| Trace custom view: enable state, record retrieval, per-address disassembly cache, copy/highlight | **Adapt/extract as HSX-specific view** | Trace toggle/copy, bounded history presentation, disassembly-enriched records, breakpoint highlight | **Trace View Presenter** over a versioned trace capability and immutable trace records; controller/gateway owns acquisition/capability | F-013, F-016, F-023; R-003, R-020, R-025, R-028..R-030, R-034, R-036 | Workspace state can contradict target trace state; cache is not target/session/version scoped; errors are swallowed; refresh only while inferred stopped | Trace capability/state/session-generation tests, cache invalidation, running/stopped behavior, import/export schema, and unavailable capability | Retain because standard DAP has no equivalent, but only behind advertised versioned capability. Remove local enabled truth when target/controller is authoritative |
| `HSXDisassemblyBreakpointDocumentProvider` and `HSXDisassemblyBreakpointManager` pseudo-source projection, local sets, and change listener | **Replace ownership; conditionally adapt projection** | Visual breakpoint icon/metadata and user toggle affordance if VS Code cannot show native instruction breakpoints adequately | **Breakpoint Presenter** projects Resource Catalog/controller truth; it never invents, clears, or reconciles target resources | F-012, F-014, F-016, F-023; R-014, R-015, R-028..R-030, R-036 | A second desired-state store, pseudo-source breakpoint feedback loops, clears, init replay, and enable toggles can conflict with DAP/external owners | Multi-client/provenance, add/remove/change loop, reconnect, multiple sessions, standard breakpoint panel, and no-unowned-delete tests | Keep pseudo-doc projection only as a tested UI workaround. Retire it when VS Code native instruction breakpoints supply equivalent visibility; in either case remove target ownership from extension |
| `vscode-hsx/package.json` debugger schemas, contributions, activation, package scripts, and workspace-dependent wrapper/runtime arrangement | **Adapt manifest; replace runtime packaging** | Debugger/view/command IDs for compatibility; compile/package flow; declared extension version | **Extension Package Contract** bundles or pins the Python runtime and declares protocol/runtime compatibility | F-005, F-016, F-021..F-023; R-003, R-005, R-006, R-028..R-036 | Only launch schema exists; activation list is incomplete relative to views/commands; package does not contain a coherent runtime; no install verification | Manifest-schema tests, `vsce` artifact inspection, clean install, runtime checksum/version handshake, no-workspace-source, Windows/Linux product path | Preserve public IDs through a deprecation window. Remove workspace runtime dependency only after installed VSIX is self-consistent and rollback artifact is available |
| `vscode-hsx/src/test/configProvider.test.ts` and current `npm test` | **Replace harness and extend coverage**, retaining three useful config cases | Default/custom config and non-integer PID assertions | Layered **Extension Unit + VS Code Integration + Packaged Product** test suites | F-016, F-021..F-023; R-005, R-006, R-029..R-036 | Mock supplies too little VS Code API for most extension code; only one file runs; no launcher/coordinator/views/breakpoints/lifecycle/package test | Export modules without activating VS Code; fake-session unit tests; `@vscode/test-electron`-equivalent integration; packaged VSIX smoke on Windows/Linux | Keep current test green while extracting modules. Replace the script only when it runs a superset; no monolith split is complete based on TypeScript compile alone |

## Compatibility mechanisms and explicit exit conditions

| Current mechanism | Posture | Retain condition | Remove condition |
|---|---|---|---|
| `session.open` unsupported → `session_disabled` raw RPC mode | **Retain, name, version-scope** | A declared supported executive version lacks sessions and its reduced guarantees are surfaced to the controller/user | Minimum supported executive requires sessions, or telemetry/release policy proves legacy version support ended |
| `debug.state` → legacy `step.mode` fallback | **Retain temporarily in typed gateway** | Negotiated executive version/capability requires it and instruction-step tests cover breakpoint behavior | All supported executives implement `debug.state`; no frontend constructs either RPC |
| `disasm.read` → `disasm` fallback | **Retain once, centralize** | Legacy executive is explicitly supported and golden results normalize both forms | Minimum version guarantees `disasm.read`; duplicate DAP fallback is removed immediately after gateway coverage exists |
| Unknown `stack`/`symbols`/`memory`/`watch` commands → support flags | **Adapt** | Flags are per connection generation, observable, and capabilities suppress unsupported frontend claims | Explicit negotiation makes probing unnecessary or support is mandatory |
| Event stream unavailable → polling/synthetic pause/step/remote-breakpoint timers | **Replace with a declared compatibility mode** | A named legacy capability profile specifies bounded cadence, source priority, diagnostics, and tests | Reliable event/command-completion capabilities are mandatory. No timer remains merely because an event was late once |
| Automatic request retry/session reopen | **Adapt** | Commands are classified idempotent/retryable, generation changes are emitted, and controller reconciles side effects | Remove retry for non-idempotent commands; retain bounded transport recovery only under explicit policy |
| Cached DAP reconnect config and breakpoint/watch replay | **Replace by controller/session intent and Resource Catalog** | Target/session generation and ownership are known, and replay is idempotent/preserves external resources | Delete adapter-owned config/spec maps after controller/reconciler recovery scenarios pass |
| DAP `threadsRequest` alias and `SymbolIndex.lookup` alias | **Retain as low-risk API shims** | Existing callers are measured or tests depend on them; they delegate without state/policy | Deprecation window ends and repo/package search plus compatibility tests show no supported caller |
| VS Code `request: launch` used for “Attach” | **Do not retain as silent behavior** | Only a migration normalizer may accept it with an actionable warning for an explicit version window | True attach/launch schemas and semantics pass product tests; old config receives a clear migration error |
| `HSX_REPO_ROOT`/`HSX_WORKSPACE_ROOT`/workspace `PYTHONPATH` bootstrap | **Retain only for developer mode** | Explicit opt-in development command/profile, never normal installed extension launch | Packaged runtime is verified from clean VSIX on Windows/Linux |
| Custom `telemetry` subsystems and custom requests | **Inventory and version** | Standard DAP lacks the required HSX presentation capability and extension/runtime versions agree | Standard DAP covers it or a custom view is retired; unversioned events/requests are not retained implicitly |
| Pseudo-source disassembly breakpoints | **Conditional UI compatibility only** | Native VS Code instruction-breakpoint presentation remains insufficient and projection is controller-derived | Native UX reaches parity or projection cannot avoid duplicate ownership/feedback loops |

The duplicated `backend`/`client` alias, global path lowercasing, fixed `0xFFFF` masks,
terminate-as-pause, attach-as-launch, swallowed callback failures, stale caches, and unbounded
ownership of externally observed resources are defects/assumptions, not compatibility
mechanisms. They have no retain condition.

## Regression-oracle policy

The legacy debugger remains executable as a behavioral reference, but an observed legacy
result becomes a preservation oracle only after classification:

1. **Preserve:** protocol framing/order, typed data conversion, accepted UI formatting,
   valid breakpoint/source resolution, output forwarding, and other behavior consistent with
   `DBG-R-*` requirements.
2. **Change intentionally:** source step semantics, launch/attach/terminate effects, stop-epoch
   references, resource ownership, concurrency, event health/recovery, address/path rules,
   capability claims, and package resolution.
3. **Retire:** duplicated state aliases, silent failures, workspace runtime discovery in normal
   installs, redundant custom UI that cannot add value over standard DAP, and local polling or
   timers once their explicit compatibility profile expires.

The signed `DBG-RF-001` production-wrapper suite is the anchor, not the whole oracle. White-box
tests that assert known findings must be kept only on the legacy lane or rewritten to assert
the accepted target behavior. A green legacy test must never veto a deliberate correction
without a requirement-level decision.

## Incremental migration sequence

This order keeps the legacy debugger runnable and avoids a big-bang replacement:

1. **Freeze and classify observable traces.** Keep the signed production wrapper and legacy
   adapter unchanged. Add a preservation/change/retire tag to each existing scenario, then
   capture DAP request/response/event and executive fixture traces for intentional behavior.
2. **Extract wire and typed boundaries without moving policy.** Put all DAP output through one
   serializer and all executive operations through the typed gateway/compatibility registry.
   Legacy `HSXDebugAdapter` continues to call compatibility façades; product-path tests run at
   every step.
3. **Introduce the controller alongside legacy state.** Feed executive events and DAP commands
   into a serialized controller in observation/shadow mode and compare its state-transition
   trace with classified expectations. It does not drive the target until discrepancies are
   resolved.
4. **Introduce epoch-safe inspection and address/source services.** Construct immutable stop
   snapshots and map them through the old DAP response shapes. Run old/new symbol and
   inspection results side by side, explicitly allowing accepted fixes for width, case, and
   stale handles.
5. **Move resource and lifecycle/execution policy into the core.** Migrate one vertical
   scenario at a time—owned instruction breakpoints, external preservation, watches,
   attach/disconnect, instruction step, then source into/over/out/terminate—only after its HSX
   dependency and acceptance oracle exist.
6. **Switch to thin DAP modules behind the same production entrypoint.** Router/mappers consume
   the controller. Keep a deliberate legacy selection for comparison/rollback until the full
   DAP contract suite and exact-wrapper product tests pass.
7. **Modularize VS Code by presentation slice.** Extract configuration/launcher/status first,
   then each view. Make standard Call Stack/Variables/Watch/Breakpoints/control surfaces pass
   before optional custom views. Views consume the new adapter contract and never direct
   migration policy.
8. **Package and verify the coherent runtime.** Test the actual VSIX/runtime on Windows and
   Linux, including clean install, unrelated workspace, version mismatch, event loss,
   multi-client resources, and all lifecycle/step scenarios.
9. **Retire legacy surfaces explicitly.** Remove old adapter modules, workspace bootstrap,
   fallbacks, and redundant views only after their row-specific exit conditions, independent
   review, product-path evidence, and exact-head sign-off. Archive trace fixtures rather than
   deleting the evidence needed to explain intentional differences.

Suggested Refactor dependency effect for Master synthesis: the current ordering remains
substantially sound, but the wire serializer and typed-gateway compatibility seams should be
the earliest bounded interfaces; controller/epoch work then precedes resource and execution
policy; DAP stays after core policies; extension/package follows stable DAP; final product-path
verification spans every earlier track. `DBG-RF-003` transport and `DBG-RF-002` controller
interfaces must be frozen together enough to avoid an event-callback compatibility layer
becoming a new architecture boundary.

## Evidence gaps that block confident final decisions

1. No accepted portable HSX address-space profile or debug-metadata schema proves code/data
   widths, wrapping, instruction alignment, source records, or frame-local locations.
2. No accepted executive contract distinguishes launch/load/start, attach lock/observer,
   detach, disconnect, terminate/kill, and target-retained recovery effects.
3. No accepted source-step contract defines call/return detection, source-line equivalence,
   missing metadata, tail calls, recursion, or independent stop-condition precedence.
4. No client-visible event-stream health message/capability or deterministic reconnect/resume
   cursor contract is proven by integration evidence.
5. No multi-client breakpoint/watch identity and ownership protocol exists; current list APIs
   mostly expose addresses/IDs without provenance.
6. No test proves stable DAP frame/scope/source references across repeated, paged, out-of-order
   inspection requests in one stop epoch or rejection after resume.
7. No concurrent DAP event/response test proves outbound wire order and sequence order.
8. No case-sensitive source collision/remapping, duplicate basename, >16-bit address, or
   malformed `.sym` oracle exists.
9. No full CLI-vs-DAP parity scenario proves both are frontends over one controller.
10. Extension automation covers configuration only; no tracker, coordinator, view, resource,
    command, multiple-session, or VS Code lifecycle integration is tested.
11. No clean packaged VSIX proves the runtime is present and version compatible without an
    HSX repository workspace.
12. No suitable Linux production-entrypoint/extension verification is recorded. Windows
    `DBG-RF-001` evidence must not be generalized to cross-platform PASS.

Until these gaps are resolved by the owning Study/design/cross-track contract, reuse
recommendations preserve only demonstrated algorithms and presentation behavior—not hidden
architecture assumptions.

## Finding coverage (`DBG-F-001..026`)

| Findings | Audit disposition |
|---|---|
| `DBG-F-001`, `DBG-F-002`, `DBG-F-003` | Preserve signed strict-stdio/order/exact-wrapper oracle; converge entrypoints and extend product-path coverage |
| `DBG-F-004`, `DBG-F-005`, `DBG-F-006` | Replace source-step and lifecycle semantics; legacy tests are change evidence, not normative parity |
| `DBG-F-007` | Replace DAP handle maps with an epoch snapshot store; adapt frame/source data |
| `DBG-F-008`, `DBG-F-009` | Replace multi-writer state; adapt DAP transport into one serialized outbound owner |
| `DBG-F-010`, `DBG-F-011` | Replace silent event worker behavior with explicit ordered health/failure events |
| `DBG-F-012` | Replace watch ownership with provenance-aware Resource Catalog |
| `DBG-F-013` | Replace competing event/poll/cache/timer authority with one controller and named fallback profiles |
| `DBG-F-014` | Replace DAP/extension breakpoint policy; adapt request/event presentation |
| `DBG-F-015` | Split/replace the DAP monolith by wire, router, mapper, controller, inspection, resource, and lifecycle owners |
| `DBG-F-016` | Split extension by configuration, launcher, session presenter, commands, and individual optional views |
| `DBG-F-017` | Retire raw frontend RPC; centralize typed compatibility in the gateway |
| `DBG-F-018` | Replace hard-coded capability claims with negotiated mapper/registry tests |
| `DBG-F-019`, `DBG-F-020` | Adapt SymbolIndex behind explicit address and source-identity contracts |
| `DBG-F-021`, `DBG-F-022` | Replace normal workspace bootstrap; reuse exact-wrapper oracle and require packaged Windows/Linux evidence |
| `DBG-F-023` | Replace one-file config harness with layered extension/package tests |
| `DBG-F-024` | Treat legacy documents/code as classified evidence only; active SDP/issue/design remains authoritative |
| `DBG-F-025` | Retire `backend`/`client` duplicate identity after controller migration |
| `DBG-F-026` | Replace frontend-owned policy in both CLI and DAP with one shared controller API |

## Requirement coverage (`DBG-R-001..036`)

| Requirements | Audit owner/disposition |
|---|---|
| `DBG-R-001`, `DBG-R-002`, `DBG-R-003` | DAP Wire/Router/Capability Mapper; strict product wrapper retained and expanded |
| `DBG-R-004` | Stop-Epoch Snapshot Store and DAP Inspection Mapper; current handles replaced |
| `DBG-R-005`, `DBG-R-006` | Controller Lifecycle/Execution Service; attach/launch/terminate legacy behavior changed intentionally |
| `DBG-R-007`, `DBG-R-008` | One serialized Debugger Controller; one DAP outbound serializer |
| `DBG-R-009`, `DBG-R-010`, `DBG-R-011`, `DBG-R-012`, `DBG-R-013` | Event Transport + Session Supervisor + controller; fallback profiles explicit, bounded, observable, and removable |
| `DBG-R-014`, `DBG-R-015` | Resource Catalog/Reconciler with owner/provenance; DAP/extension state replaced |
| `DBG-R-016`, `DBG-R-017`, `DBG-R-018`, `DBG-R-019`, `DBG-R-020` | Lifecycle/Execution Service plus accepted HSX execution contracts; current source-step/timer policy replaced |
| `DBG-R-021`, `DBG-R-022` | Epoch-safe Inspection Model/Store; useful typed frame/register/watch data adapted |
| `DBG-R-023`, `DBG-R-024` | Explicit Address Model and Source Identity/Mapper; current masks/lowercasing removed after golden migration |
| `DBG-R-025` | Atomic/epoch-consistent Inspection Service; custom views become presenters or retire |
| `DBG-R-026` | Typed Executive Gateway is the only runtime-control boundary; raw DAP/CLI RPC retired |
| `DBG-R-027`, `DBG-R-028` | Shared controller/services and bounded frontend mappers; both monolith layouts rejected as target structure |
| `DBG-R-029`, `DBG-R-030` | VS Code Session/View Presenters consume DAP/controller truth; standard DAP UI is acceptance baseline |
| `DBG-R-031` | Version-Coherent Runtime Launcher and package handshake; workspace runtime bootstrap replaced |
| `DBG-R-032` | Signed exact production entrypoint oracle retained, then moved only to the actual packaged path |
| `DBG-R-033` | Final suite must run packaged path on Windows and Linux; current evidence is Windows-only |
| `DBG-R-034` | Compatibility registry above names every current shim and exit condition |
| `DBG-R-035` | Each downstream Refactor still requires independent exact-head review/sign-off; this Study grants no implementation authority |
| `DBG-R-036` | Classified legacy traces, fixtures, signed wrapper test, and new contract/golden suites precede every responsibility move |

## Conclusion for Master synthesis

The legacy implementation contains substantial reusable **semantics and evidence**, but few
legacy **ownership boundaries** should survive unchanged. The strongest reuse candidates are
typed value shapes and conversion vectors, `.sym` parsing/index algorithms after address/path
repair, DAP wire framing after serialization repair, deterministic fixtures, the signed
production-wrapper oracle, CLI shell ergonomics, and additive HSX-specific memory,
disassembly, and trace presentation.

The strongest replace candidates are the DAP adapter's controller-like state, timer/poll/cache
authority, frame/scope handle stores, resource reconciliation, lifecycle/step policy, event
callback model, frontend raw RPC, the extension's independent run/resource truth, and normal
workspace-dependent runtime discovery. The recommended migration is strangler-style: preserve
one runnable legacy lane, introduce typed and serialized seams, shadow the new controller,
migrate vertical behaviors with classified golden evidence, then retire each legacy mechanism
only at an explicit, reviewed exit condition.

No structural product code was changed or authorized by this Study.
