# Proposed Debugger Design Contracts

- Status: ACCEPTED / FROZEN DEBUGGER V1 DESIGN BASELINE
- DesignAnalysis: `DBG-DA-001`
- Architecture: `DBG-A-001..DBG-A-008`
- Architecture-direction review: `DBG-RVW-001-002-003` — PASS at
  `89d95de2d944179219a93895f1ab956f2786a232`
- Portable dependency evidence: `DBG-ST-006`, `HSX-ST-001..HSX-ST-008`
- Review 005: REWORK at `84df21d763b73209efd0292990799f469283460a`
- Planned fresh cross-track review: `HSX-RVW-001-001-006`
- Steering acceptance: issue #38 comment `5356484309`
- State: implementation-authoritative only through explicitly authorized Refactor/Slice contracts

The contracts below are the frozen Debugger v1 design baseline. Only RF-002, RF-003 and their
early integration Slice are authorized in the first structural wave.

## Contract registry

| ID | Proposed contract | Primary architecture | Downstream work |
|---|---|---|---|
| `DBG-D-001` | Controller command/event/effect model, serialized state machines, queue/back-pressure, operation correlation, shutdown | A-001 | RF-002 |
| `DBG-D-002` | Executive Gateway session/capability/event-health/cursor/reconnect contract | A-002 | RF-003 |
| `DBG-D-003` | Target/image/address identity, stop epoch, snapshot, and reference-lifetime contract | A-003 | RF-002, RF-004 |
| `DBG-D-004` | Debug artifact, source resolver, and epoch-bound inspection contract | A-004 | RF-004 |
| `DBG-D-005` | Breakpoint and live-watch ownership/reconciliation contract | A-005 | RF-005 |
| `DBG-D-006` | Lifecycle intents, execution plans, and canonical run/stop-reason contract | A-006 | RF-006 |
| `DBG-D-007` | Shared frontend port, thin CLI/DAP, DAP phase/capability/handle/output contract | A-007 | RF-007 |
| `DBG-D-008` | VS Code presentation, runtime launcher, package manifest, and custom protocol contract | A-007 | RF-008 |
| `DBG-D-009` | Compatibility registry, oracle classification, and strangler migration contract | A-008 | RF-002..RF-008 |
| `DBG-D-010` | Immutable artifact verification and Windows/Linux release sign-off contract | A-008 | RF-009 |

All contracts are `accepted_frozen_debugger_v1`.

The `DBG-ST-006` dependency gate is satisfied by the frozen portable HSX target contracts.
Implementation remains bounded by the Steering-authorized Refactor/Slice wave.

## DBG-D-001 — Serialized controller contract

### Public shape

```text
Controller.start() -> None
Controller.submit(command: DebuggerCommand) -> Future[CommandResult]
Controller.snapshot() -> Future[ControllerSnapshot]
Controller.subscribe(filter: EventFilter) -> ControllerSubscription
Controller.close() -> Future[CloseResult]
```

Commands include connection, attach/launch, lifecycle, execution, inspection, desired
resources, recovery, cancellation, and disconnect intents. Every command carries a command ID
and optional expected controller revision. Effects and completions carry operation ID,
session generation, target generation, and capability profile generation.

### Rules

- one bounded controller inbox and one actor/reducer are the only authoritative state writer;
- blocking RPC/event reads, timers, and frontend callbacks execute outside the actor;
- timer callbacks enqueue `DeadlineExpired`; elapsed time cannot create target state;
- an accepted command creates a pending operation only; `RunPending`, `StepPending`, and
  `StopPending` advance solely on authoritative completion/event/reconciliation evidence;
- output subscribers use bounded queues and cannot block the controller;
- shutdown is idempotent, rejects new commands, resolves pending Futures once, cancels effects,
  and joins workers without self-join or lock inversion;
- typed errors include `InvalidTransition`, `SessionUnavailable`, `TargetLost`,
  `OwnershipLost`, `CapabilityUnavailable`, `OperationTimeout`, `StaleEpoch`,
  `UnknownHandle`, `RecoveryFailed`, and `Cancelled`.

### Acceptance evidence

Pure transition-table/property tests, adversarial command/event/completion/deadline schedules,
stale-generation rejection, bounded-queue behavior, shutdown/reconnect stress, and proof that
all authoritative mutations occur on one context.

## DBG-D-002 — Executive Gateway contract

The gateway exposes typed request/effect APIs and immutable event/health envelopes. It owns
wire/session mechanics only.

### Required state and evidence

- separate RPC health and event-stream health;
- negotiated capability profile scoped to session generation;
- executive-instance/stream identity and last applied event cursor;
- ACK only after controller application;
- duplicate/gap/drop/`seq_evicted` handling;
- explicit EOF, malformed input, callback/parser/reducer/ACK/keepalive failures;
- request retry only for declared idempotent operations;
- typed descriptor, bundle/binding, snapshot, resource and optional register-mutation envelopes
  are transported unchanged; successful legacy RPC calls never imply portable capability;
- no hidden debugger-level reconnect or automatic claim of restored health.

### Reconciliation barrier

Recovery is healthy only after executive/target identity, ownership, capabilities, event
cursor or full refresh, resources, run state, and stop epoch are reconciled. Results are typed
as retained, target lost, ownership lost, incompatible capability, or exhausted recovery.

`DBG-ST-006` must confirm the portable stream/identity/cursor semantics before acceptance of
the full contract.

## DBG-D-003 — Target identity and stop-epoch contract

### Identity values

`ExecutiveInstanceRef`, `SessionRef`, `TargetRef`, `PidGeneration`, `ArtifactRef`, target-bound
`LoadedImageRef`, accepted `ImageDebugBinding`, `ArchitectureDescriptorRef`, `StopToken`,
`InspectionSnapshotRef`, and `StopEpochId` are distinct types. A PID, path, CRC, artifact digest
or address integer alone is not target/load identity.

### Epoch rules

- one active epoch belongs to one target generation and authoritative inspection-stable stop;
- snapshot objects and domain handles are immutable;
- repeated/paged inspection requests may allocate more handles without invalidating earlier
  handles in the same epoch;
- resume, termination, target/image generation change, or uncertain recovery invalidates the
  epoch before effects are issued;
- accepted register mutation is a serialized stopped-to-stopped transition that invalidates
  the origin epoch and installs only the returned replacement stop/snapshot evidence;
- late reads cannot populate a newer epoch;
- stale/unknown handles fail explicitly and never fall back to another object;
- DAP integer IDs map to domain handles within one DAP session but do not own lifetime.

Atomic snapshots or stopped-revision validation, address spaces, and ABI semantics are
dependencies on `DBG-ST-006`/HSX contracts.

## DBG-D-004 — Artifact, source, and inspection contract

### Services

- `DebugArtifactIndex` consumes only a verified `ImageDebugBinding`/`ImageDebugBundleRef`, then
  exposes immutable functions, symbols, instructions, source identities, type/location lists,
  bounded unwind/location recipes, and memory regions for the exact LoadedImageRef.
- `SourceResolver` keys exact case-preserving NFC `SourceRef`/logical ID, keeps local locators
  separate, verifies candidate byte digest/length, and returns typed unavailable, ambiguous,
  content-mismatch and case-collision outcomes.
- `InspectionService` returns registers, stack, scopes, variables, memory, and disassembly for
  one epoch/snapshot with explicit partial/unavailable diagnostics.

### Prohibitions

No scattered `0xFFFF`/`0xFFFFFFFF` masks, unconditional lowercase identity, basename-first
selection, request-time live reads presented as one snapshot, raw RPC in frontends, or hidden
fallback from an unknown frame to the current frame.

### Acceptance evidence

Multiple address widths/spaces, case-colliding files, relocation/prefix/symlink mappings,
duplicate symbols/basenames, image mismatch, malformed metadata, partial unwind, selected
non-top-frame locals, unsupported recipe/schema/bounds, epoch stability/staleness, and
cross-service snapshot consistency.

## DBG-D-005 — Resource ownership contract

### Model

`OwnerId` scopes frontend intent. A logical resource has `LogicalResourceId`, kind,
specification, owner set, target/image generation, resolved locations, desired revision, and
remote bindings. Observed remote resources have stable remote identity/provenance/revision
when supported.

- source/function/instruction breakpoints remain logical resources even when they share an
  address or resolve to multiple addresses;
- standard Watch expressions are snapshot evaluations, not persistent resources;
- persistent live watches are an optional HSX resource with explicit capability/ownership;
- disconnect removes only the departing owner's desire and never deletes an external/shared
  resource;
- reconnect reconciles only after target identity and resource generation are known;
- event-capable health uses resource events, not periodic polling.

### Legacy mode

Address-only or ID-only executives use a named degraded compatibility profile. Unknown remote
resources are external and preserved; destructive convergence is forbidden. The UI surfaces
degraded ownership rather than claiming full convergence.

## DBG-D-006 — Lifecycle, execution, and stop-reason contract

### Lifecycle intents

- `Attach` claims or observes an existing stable target and never creates one.
- `Launch` atomically creates/loads/starts and claims a new target; until this exists, clients
  expose attach only rather than relabel attach as launch.
- `Detach` releases ownership according to an explicit target-state policy.
- `Disconnect` closes the debugger session with an explicit preserve/resume/terminate policy.
- `Terminate` requests actual target removal and succeeds only on authoritative confirmation.

Product defaults for disconnect/detach remain a Steering decision; they may not be hidden in
frontend spelling.

### Execution plans

`Instruction`, `SourceInto`, `SourceOver`, and `SourceOut` are distinct plan kinds with origin
epoch/frame/source location, owned internal conditions, instruction/time budgets, and typed
completion/preemption.

Submitting a continue/pause/step command and receiving request acceptance creates a pending
operation; it does not establish `Running`, `Stopped`, or plan completion. The controller
invalidates the old epoch before an accepted target-mutating effect and waits for authoritative
evidence. A direct stopped completion may move `StepPending` to a new `Stopped` epoch without
an intermediate observed `Running` state.

- instruction step retires exactly the accepted HSX primitive;
- into stops at the next distinct source location and may enter a callee;
- over ignores deeper frames and completes in the origin frame at a distinct mapped location;
- out completes in the caller after the origin frame returns;
- independent user/external breakpoints, pause, block, fault, termination, and target loss
  preempt a plan and retain their real reason;
- missing source/unwind capability yields unavailable/incomplete, not a mislabeled instruction
  step;
- source plans require a valid ImageDebugBinding, exact source-content mapping and applicable
  bounded unwind/location rows; any missing/mismatch/unsupported input is typed unavailable;
- register mutation cannot race an active plan; a successful write invalidates the plan origin
  and any later plan starts from the replacement StopToken;
- internal conditions are owner-scoped resources and never clear user/external breakpoints.

### State and reason

`TargetRunState` is orthogonal to `TransitionCause`/`StopCause`. Mailbox wait/sleep/wake,
timeout, pause, breakpoint, each step kind, fault, termination, and target loss map from
ordered authoritative evidence. Duplicate stops use causal identity, never time windows.

## DBG-D-007 — Frontend and DAP contract

### Shared frontend port

CLI and DAP consume typed controller commands, queries, immutable snapshots, domain events,
capabilities, and typed failures. The port exposes no `request(dict)` escape hatch.

### DAP modules

- `DapReader`: strict bounded framing and decoded envelopes;
- `DapSession`: DAP protocol phase, request correlation, client capabilities, launch/attach
  configuration ordering, and error mapping only;
- capability broker: intersection of verified adapter/core capability and client support;
- typed mappers by lifecycle, execution, resources, inspection, and output;
- epoch-aware DAP handle registry;
- one outbound queue/writer that allocates `seq` immediately before atomic wire write.

DAP policy is limited to DAP protocol state. It does not own debugger lifecycle truth,
reconnect, resources, symbols, stepping, caches, polling, or timers.

### CLI

The CLI preserves parser/history/completion/script/text/JSON ergonomics but obtains all target
behavior through the same frontend port. CLI and DAP must pass parity scenarios against one
controller fixture.

## DBG-D-008 — VS Code and package contract

### Extension modules

Configuration, runtime launcher, session presentation/status, memory/register/stack,
disassembly, trace, and breakpoint presentation are separate modules. Standard DAP Call
Stack, Variables, Watch, Breakpoints, navigation, console, memory/disassembly, and execution
control form the normal product path. Optional HSX views are epoch/session-keyed projections
and own no target/resource truth.

Custom operations/events use one namespaced versioned `hsx/*` presentation schema and explicit
handshake only where standard DAP has no equivalent, such as trace UX.

### Runtime artifact

- build one pure-Python debugger distribution used by both CLI and DAP;
- vendor the exact distribution inside the VSIX;
- initially require a supported external Python 3.10+ interpreter, with fail-closed preflight;
- package manifest records extension/runtime/source versions, protocol/schema versions,
  Python range, compatibility-registry version, and file hashes;
- production launch sanitizes environment/import paths and never imports debugger runtime from
  the debuggee workspace;
- per-platform frozen executables may later implement the same launcher contract;
- generated VSIX is an immutable release artifact, not an unexplained hand-built source file.

The Python support range and release-artifact retention are explicit Steering decisions in
the `DBG-DA-001` package.

## DBG-D-009 — Compatibility and migration contract

Every compatibility entry contains ID, owner, supported version/capability trigger, observable
diagnostic, positive/negative tests, last supported version, and removal condition.

Initial candidates include sessionless RPC, `debug.state` to `step.mode`, `disasm.read` to
`disasm`, unsupported-feature probes, bounded poll-only event compatibility, source-entrypoint
shim, deprecated launch-as-attach config normalization, workspace bootstrap in explicit
developer mode only, and versioned legacy custom requests/events.

Known defects—duplicate backend/client identity, silent callback failure, global lowercase,
fixed masks, terminate-as-pause, identical source steps, observation-to-ownership, unbounded
poll/timer truth—have no retain condition.

Migration follows classified oracles and shadow/strangler steps; no big-bang replacement.

## DBG-D-010 — Verification and release contract

The production oracle is the immutable packaged artifact hash, not a cleaner source wrapper.

1. Static/build: Python import/compile, TypeScript strict compile, manifest/lock/version/hash
   consistency and deterministic inventory.
2. Unit/contracts: reducer/state/epoch/gateway/resource/execution/DAP/CLI/extension modules.
3. Extracted VSIX: sanitized environment, unrelated workspace, strict framing/lifecycle.
4. DAP scenarios: standard lifecycle, resources, execution, inspection, recovery.
5. VS Code extension host: exact VSIX activation, launch, standard UI, optional views.
6. Live executive samples: target-retained/lost reconnect, multi-client ownership, event loss,
   no-poll healthy idle, package mismatch.
7. Release: same artifact on Windows and Linux, complete requirement matrix, independent
   exact-head review and Master sign-off.

Negative controls cover raw stdout, malformed/oversized frames, raced producers, malicious
workspace modules, unsupported Python, manifest/version/hash mismatch, capability absence,
stale handles, event gaps, resource conflicts, and cleanup loops.

## Proposed Refactor interfaces and dependency changes

The current ordering remains structurally sound with these proposed refinements:

- RF-002 and RF-003 may start as parallel domains only after D-001/D-002 envelopes,
  generation tags, health states, and recovery ownership are frozen; their first integration
  Slice proves command/effect/completion/event flow.
- RF-004 consumes RF-002 epoch/target ports and accepted HSX address/snapshot/ABI contracts.
- RF-005 consumes RF-002/RF-003 plus RF-004 typed resolution interfaces; this adds an explicit
  source-resolution interface dependency absent from the current graph.
- RF-006 consumes RF-002..RF-005 because source-step internal conditions must use the accepted
  resource ownership service; this adds RF-005 to the current dependency.
- RF-007 remains one Refactor but must contain separately reviewed CLI-migration, DAP-module,
  and frontend-parity Slices. It cannot begin final migration until RF-002..RF-006 ports are
  stable.
- RF-008 consumes RF-007 packaged entrypoint/DAP/custom-presentation contracts.
- RF-009 consumes RF-002..RF-008 and owns final immutable-artifact/platform convergence, while
  every earlier Refactor still owns fast portable tests.

These dependency refinements are part of the accepted baseline. RF-004..RF-009 remain blocked
until later Steering decisions.
