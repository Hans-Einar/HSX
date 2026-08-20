# HSX-ST-002 — Runtime Identity, Generations, Lifecycle, and Ownership

- Status: COMPLETE FOR MASTER SYNTHESIS
- Coordinator: `HSX-ST-001`
- Debugger dependency: `DBG-ST-006`
- Issue: #47
- Iteration: `DBG-IT-001-003`
- Evidence baseline: `d135e542b2a959c2ea67e3a1ea65df7e0bcd6baf`
- Scope guard: Study/contract proposal only; no product, Debugger Refactor, or AVR authority

## Question and scope

What portable HSX contract lets a debugger or other control client distinguish an executive
incarnation, an event-sequence namespace, a client session, a task/PID incarnation, and a
particular loaded image, and then use those identities to perform lifecycle operations without
silently controlling a replaced target?

This Study covers:

- executive-instance, event-stream, session, target, PID-generation, image-artifact, and
  loaded-image identity;
- create/load/start/claim, exclusive attach, observer attach, detach/release, disconnect,
  terminate/kill, target continuity/loss, and PID reuse;
- ownership leases, lock authority, ordering, idempotency, generation fencing, failure and
  named degraded behavior;
- conformance fixtures required before the Debugger contracts can consume the portable model.

It does not define event cursor/ACK mechanics beyond their identity scope (`HSX-ST-005`),
execution/stop revisions (`HSX-ST-004`), address or unwind semantics (`HSX-ST-003`), or
breakpoint/watch resource revision semantics (`HSX-ST-006`). It does not choose a Debugger
product default for detach/disconnect and does not design an AVR representation.

## Authority and method

The evidence classes below remain distinct:

1. **Current implementation** is observable Python behavior at the evidence baseline. It is
   useful as a regression oracle, not portable authority.
2. **Documented intent** is legacy `DR-*`/`DG-*` and draft design/protocol material. It is
   provenance, not silently accepted HSX design.
3. **Recommended target contract** is the output of this Study for Master allocation into
   stable proposed HSX requirements/architecture/design IDs.

The recommended model is requirements-driven and fail-closed across uncertainty. Numeric
`HSX-R-*`, `HSX-A-*`, and `HSX-D-*` IDs are intentionally not allocated here.

## Evidence sources

### SDP and Steering inputs

- `AGENTS.md`, `SDP/README.md`, and `SDP/Shared/Process.md`;
- both active `Traceability/CurrentIndex.yaml` files;
- `HSX-ST-001`, `DBG-ST-006`, `DBG-ST-002`, and `DBG-ST-003`;
- proposed `DBG-D-001..DBG-D-006` and accepted target architecture direction;
- issues #47 and #38, including Steering comments `5348192567` and `5348190806`.

### Legacy requirement and design provenance

- `main/02--Study/02--Study.md` and `02.01--Requirements.md`;
- `main/03--Architecture/03.02--Executive.md` and `03.06--Provisioning.md`;
- `main/04--Design/04.02--Executive.md`, `04.07--Provisioning.md`, and
  `04.09--Debugger.md`;
- `main/04--Design/DesignReview.md`;
- `main/05--Implementation/shared/executive_protocol.md`,
  `toolchain/formats/hxe.md`, and the Executive/Provisioning gap material.

Relevant provenance is primarily:

- `DR-1.1` runtime loading, `DR-1.2` unified deployment, `DR-1.3` Python-to-C
  portability, `DR-2.5` ABI/capability handshake, `DR-3.1` HXE contract,
  `DR-5.1` scheduler/lifecycle behavior, and `DR-8.1` session/event behavior;
- `DG-1.1..1.3`, `DG-3.1`, `DG-3.4..3.5`, `DG-5.1..5.4`, and `DG-8.2`;
- the legacy intent that sessions enforce one debugger per PID while allowing observers,
  provisioning validates before activation, streaming load has explicit abort, and reconnect
  uses session/keepalive/replay evidence.

### Current protocol, code, formats, and tests

- `docs/executive_protocol.md`, `docs/hsx_spec-v2.md`, and `docs/hxe_format.md`;
- `python/execd.py` session, task-refresh, load, reload, kill, and request-dispatch paths;
- `platforms/python/host_vm.py` `VMController`, PID allocation/reset, HXE load, streaming load,
  task summary, kill, and debug attach/detach paths;
- `python/vmclient.py`, `python/executive_session.py`, and `python/hsx_dbg/backend.py`;
- `python/hld.py` HXE/sidecar generation;
- `python/tests/test_app_names.py`, `test_executive_sessions.py`,
  `test_executive_session_helpers.py`, `test_vm_pause.py`, and
  `test_vm_stream_loader.py`.

The focused read-only evidence run was:

```text
c:/Users/hanse/miniconda3/python.exe -m pytest \
  python/tests/test_app_names.py \
  python/tests/test_executive_sessions.py \
  python/tests/test_executive_session_helpers.py \
  python/tests/test_vm_pause.py \
  python/tests/test_vm_stream_loader.py -q

90 passed in 0.94s
```

This proves the existing oracles pass. It does not prove generation safety, transactionality,
observer authority, or reconnect continuity; those cases are largely absent from the suite.

## Terminology and identity domains

The target contract must not use these terms interchangeably:

| Term | Meaning | Explicit non-meaning |
|---|---|---|
| Executive incarnation | One continuity domain for executive state and identities | A hostname, port, process name, or protocol version |
| Event stream | One event sequence/cursor namespace | A subscription socket or debugger session |
| Session | A negotiated client lease and capability profile | A TCP connection or ownership of every target |
| Attachment | One session's relationship to one exact target generation | Merely observing a PID in `ps` |
| Control lease | Exclusive mutation authority for one exact target generation | A display PID or client-supplied owner label |
| Target | One logical executable task identity | A reusable PID number or app name |
| PID reference | A local PID plus its allocation generation | A stable target identity by itself |
| Image artifact | Immutable accepted HXE bytes/content | An app display name, path, or CRC alone |
| Loaded image | One committed installation of an artifact into a target | Every target that happens to run identical bytes |
| Target generation | Fence for destructive target-continuity changes | The run/stop revision owned by `HSX-ST-004` |

## Findings — current implementation

### Current identity inventory

| Domain | Current evidence | Resulting limit |
|---|---|---|
| Executive | `ExecutiveState` and `VMController` expose no instance ID | A reconnect cannot prove whether state belongs to the same incarnation |
| Event stream | `event_seq` starts at 1 in each `ExecutiveState`; events have `seq` but no stream ID | A repeated sequence after restart is indistinguishable from an old sequence |
| Session | `session.open` creates a UUID and records client/features/PID locks/timestamps | Useful in-process identity, but not explicitly scoped to an executive instance and no resume/lease generation exists |
| PID | `VMController.next_pid` increments from 1; `reset()` returns it to 1 | PID is unique only until controller reset and cannot prove identity across restart |
| Target | Task dictionaries are keyed only by PID | Target identity and PID are conflated |
| Image artifact | HXE reports format version, CRC32, lengths, flags, `app_name`, and metadata | CRC/name/path are useful integrity/display/provenance fields, not collision-resistant identity |
| Loaded image | Task/load replies contain PID, app instance name, program path, and header summary | Two loads of the same bytes and an in-place replacement have no distinct loaded-image identity/generation |
| Ownership | `pid_locks: pid -> session_id` | No attachment/lease identity, ownership revision, observer authority record, or target-generation fence |
| Operation | Lifecycle calls have no operation/idempotency ID | A lost response cannot distinguish “not applied” from “applied, response lost” |
| Termination | A final `task_state` may be emitted and the task is removed | No stable tombstone keyed by target identity/generation for later confirmation |

Additional evidence:

- `docs/executive_protocol.md` reserves PID 0 for a preloaded image, while ordinary current
  controller loads start from PID 1. This inconsistency reinforces that PID convention is not
  a portable identity contract.
- `session.open` accepts locks for arbitrary non-negative PIDs without proving that a task
  exists; current tests intentionally acquire locks for PIDs 3, 5, 7, 9, and 11 without a task
  table. A session can therefore reserve a future numeric PID rather than claim an existing
  target.
- HXE v2 multiple-instance suffixes (`app`, `app_#0`, ...) are deterministic display names.
  Killing an instance makes a suffix available again, so the suffix is not stable identity.
- The `.sym` sidecar records `hxe_crc`, but HXE CRC32 is an integrity check and not a durable
  artifact/load identity. Current HXE output is deterministic, so a stronger digest can be
  derived without changing guest execution semantics.

### Current lifecycle and ownership behavior

1. `load` parses an HXE, allocates a new PID, registers metadata/mailboxes, inserts a task as
   `running`, and activates it. There are no distinct portable create, load, start, and claim
   commits, and `execd.load` does not require a session or target-control lease.
2. Streaming `load_stream_begin` reserves the future PID and uses that same number as the
   transfer-session key. Failed or aborted attempts consume the number, but no generation or
   separate provisioning-operation identity is exposed.
3. The load path has no explicit encompassing transaction/rollback record. Several resource
   and task side effects occur before completion. Legacy provisioning intent requires staging,
   validation, abort cleanup, atomic activation, and rollback, but that intent is not a current
   portable guarantee.
4. `reload_task` kills the old PID before attempting the new load. A failed load loses the old
   target, and a successful load returns a new PID without a continuity decision or generation
   relation.
5. Global `attach`/`detach` toggles the Executive-to-VM control mode. It is callable without a
   debugger session and is not a per-target ownership operation. Debugger target attach is
   separately approximated by reopening a session with a PID lock. These meanings must not be
   combined in the target contract.
6. The documented observer mode is read-only, but `ensure_pid_access` returns success whenever
   no session currently owns that PID. An observer or sessionless caller can therefore mutate
   an unlocked target; it is blocked only when someone else has already locked the PID.
7. Global attach/detach, load, unscoped clock start/stop, restart, and shutdown bypass a
   target attachment lease. A valid session can also force-close another session without a
   separately negotiated administrative authority.
8. Session close/timeout releases numeric PID locks and event subscriptions but has no explicit
   per-target detach/disconnect/orphan policy. Target execution simply remains in its current
   implementation state.
9. `kill` is synchronous removal in `VMController`; `execd` then refreshes and returns
   `{pid, state: terminated}`. The response is useful current evidence, but no exact target
   identity, lifecycle revision, or queryable tombstone prevents a reused PID from satisfying a
   delayed confirmation.

### Current reconnect behavior

- RPC uses a new TCP connection per request; the server session is intentionally independent
  of a socket and expires by heartbeat.
- On a transport loss, `ExecutiveSession` discards its session ID, opens a new session, and
  retries the original request. It does not compare executive, target, PID-generation, or image
  identity first.
- The old server session may retain its PID lock until timeout, so the new session can conflict
  with the client's own orphaned lock.
- Retry is not restricted to declared idempotent operations. If a server applies `load`,
  `start`, or another mutation and the response is lost, a blind retry can duplicate or alter
  lifecycle effects.
- Event-stream EOF unsubscribes the stream but does not close the session. The present client
  does not carry a stream identity/last authoritative lifecycle revision through a designed
  reconciliation barrier.

The only safe current conclusion after uncertain reconnect is **continuity unknown**. PID,
app name, path, PC, or a fresh session lock cannot upgrade that to retained target identity.

## Findings — documented intent

The legacy catalogue and designs provide useful direction:

- runtime HXE loading and a Python-to-C portable interface are explicit (`DR-1.1`, `DR-1.3`);
- HXE version/integrity and capability negotiation are intended (`DR-2.5`, `DR-3.1`);
- one debugger per PID and read-only observers are intended (`DR-8.1`, `DG-5.3`);
- session open/keepalive/close, event replay, and reconnect are documented;
- provisioning is intended to validate/stage, transition `LOADING -> VERIFY -> READY`, abort
  cleanly, and atomically activate/roll back;
- provisioning should block or require explicit release when a target is under debug;
- target exit/kill should clean scheduling and debugger resources.

But the intent has unresolved contradictions or missing detail:

- some documents describe a VM standalone/detached mode while the later Executive design says
  the Executive is always present and global attach/detach is legacy;
- “preserve session state for reconnection” does not define executive/target continuity,
  fencing of the prior connection, or ownership recovery;
- “PID lock” does not define target generations, nonexistent PID handling, lease transfer,
  session loss policy, or observer enforcement;
- “load” sometimes starts immediately and sometimes ends in READY awaiting activation;
- `app_name`, PID, filepath, CRC, manifest version, and `.sym` `hxe_crc` exist, but none is
  specified as collision-resistant image or load identity;
- target replacement may either preserve a logical target or create a new target, but the
  decision is not explicit.

These gaps require a new stable contract; copying the legacy JSON shapes is insufficient.

## Alternatives compared

### Identity model

| Alternative | Advantages | Risks | Decision |
|---|---|---|---|
| PID/app-name/path identity | Minimal fields; matches current code | Reuse, renaming, reload, restart, multiple instances, and path aliases silently rebind clients | Reject as full contract; retain only as named legacy display/degraded data |
| Executive incarnation plus local opaque IDs and monotonic generations | Compact, portable, deterministic fencing; no durable global registry required | Requires fields on every lifecycle/event/snapshot/resource envelope | **Recommend** |
| Permanently persisted global target IDs across every executive restart | Can preserve long-lived identity across controller replacement | Requires durable storage, boot/recovery rules, anti-cloning and target-specific policy not yet designed | Optional future capability only |

### Image identity

| Alternative | Advantages | Risks | Decision |
|---|---|---|---|
| HXE CRC32 plus app name | Already available | CRC collisions; app name is mutable/display; two load instances remain indistinguishable | Reject as exact identity |
| SHA-256 of exact accepted HXE bytes plus unique loaded-image ID | Strong artifact identity; two instances and reloads are distinguishable; derivable today | Adds wire/storage fields and digest computation | **Recommend** |
| Toolchain-generated build UUID only | Human-friendly build correlation | Nondeterministic unless carefully controlled; duplicated/malformed IDs; does not identify a load instance | May be metadata, never sole identity |

### Lifecycle/ownership model

| Alternative | Advantages | Risks | Decision |
|---|---|---|---|
| Session UUID with optional numeric PID lock | Current implementation; small | Session, observer, claim, target and transport concerns remain conflated; no generation fence | Reject as full contract |
| Exact target references plus attachment/control leases | Separates read authority, mutation authority and target identity; reconnect can reconcile mechanically | Requires lease state, expiry/policy, revisions, and explicit errors | **Recommend** |
| Socket ownership | Automatic release on disconnect | Current protocol uses multiple sockets; transient loss destroys authority; event and RPC sockets differ | Reject |

### Launch and reload

| Alternative | Advantages | Risks | Decision |
|---|---|---|---|
| Independent create/load/start/claim calls only | Flexible provisioning | Partial failure exposes unowned/half-loaded/running targets; hard client compensation | Keep as privileged staged primitives, not Debugger Launch |
| Atomic launch-and-claim transaction | One authoritative commit; safe lost-response recovery with idempotency key | Requires staging and rollback | **Require when `Launch` capability is advertised** |
| Kill then load for reload | Current simple behavior | Failure destroys old target and loses continuity | Reject as portable replace-image contract |

### Reconnect matching

| Alternative | Advantages | Risks | Decision |
|---|---|---|---|
| Reattach to same numeric PID | Simple | Can control unrelated reused target | Reject |
| Match app/image/path heuristically | Sometimes recovers user intent | Ambiguous multiple instances and replacements; no authority proof | Reject |
| Exact identities/generations, otherwise retained/lost/replaced/unknown | Fail-closed and testable | Some legacy sessions cannot auto-recover | **Recommend** |

## Recommended portable target contract

### Wire representation rules

- Opaque incarnation, session, attachment, target, loaded-image, and operation IDs are at least
  128 bits of collision-resistant identity within their documented domain.
- Generations and revisions are unsigned monotonic 64-bit values. They never wrap within an
  executive incarnation; the producer starts a new incarnation before exhaustion.
- JSON transports encode opaque IDs and 64-bit generations in a canonical lowercase hex or
  decimal **string**, not a JSON number that a JavaScript client may round.
- A full reference is a structured DTO, never a colon-concatenated string parsed differently by
  clients. Unknown fields are ignored only when the negotiated profile permits extension;
  missing required identity fields fail the profile.
- Display PID, app name, instance suffix, source path, symbol path, host/port, timestamps, and
  CRC are never identity or authority.

Exact binary encoding and constrained-target storage belong to later design/target work. The
semantic widths and comparison rules are portable.

### Identity DTOs

The following descriptive contract concepts are proposed for Master allocation:

```text
ExecutiveRef {
  executive_instance_id: OpaqueId128
}

EventStreamRef {
  executive: ExecutiveRef
  stream_id: OpaqueId128
  stream_generation: UInt64
}

SessionRef {
  executive: ExecutiveRef
  session_id: OpaqueId128
  session_generation: UInt64
}

PidRef {
  pid: UInt32
  pid_generation: UInt64
}

TargetRef {
  executive: ExecutiveRef
  target_id: OpaqueId128
  target_generation: UInt64
  pid: PidRef
}

ArtifactRef {
  digest_algorithm: "sha256"
  digest: Bytes32
  hxe_format_version: UInt16
  integrity_crc32: UInt32?       # diagnostic/integrity only
}

LoadedImageRef {
  target_id: OpaqueId128
  target_generation: UInt64
  loaded_image_id: OpaqueId128
  image_generation: UInt64
  artifact: ArtifactRef
}

AttachmentRef {
  executive: ExecutiveRef
  session: SessionRef
  attachment_id: OpaqueId128
  attachment_generation: UInt64
  target: TargetRef
  mode: "exclusive" | "observer"
  authority: set<Authority>
  ownership_revision: UInt64
}

LifecycleOperationRef {
  executive: ExecutiveRef
  operation_id: OpaqueId128
  idempotency_key: OpaqueId128
  expected_session_generation: UInt64
  expected_target: TargetRef?
}
```

`TargetRef`, `LoadedImageRef`, and `AttachmentRef` are echoed on all affected command results,
events, snapshots, and resource observations. A bare PID may be accepted only by a named legacy
adapter that immediately resolves it to an exact reference before mutation.

### Generation and identity change rules

| Event | Required identity/generation effect |
|---|---|
| Executive starts or loses continuity state | New `ExecutiveInstanceId`; new event stream; all old sessions/attachments are fenced |
| Event cursor namespace is recreated/reset | New `EventStreamId` or stream generation; sequence values may restart only under the new reference |
| Session opens | New `SessionId`, generation 1 |
| Session resumes after authenticated/authorized transient loss | Same `SessionId`, incremented session generation; prior transport/generation is fenced |
| Capability/authority profile changes materially | New session generation or new session; profile is immutable within one generation |
| New PID number is allocated | `PidGeneration` advances for that numeric PID; generation 0 is not reused within the executive incarnation |
| Target is created | New `TargetId`; target generation starts at 1 |
| Target execution state changes only | No target-generation change; `HSX-ST-004` state/stop revision advances |
| Target reset recreates execution state while preserving logical target | Same `TargetId`, incremented target generation; all stop/snapshot/resource bindings are stale |
| Image is committed/replaced in an existing logical target | New `LoadedImageId`, incremented image generation and target generation |
| Failed staged load/replace | No externally visible target/image generation advances; staging operation ends failed/aborted |
| Normal kill followed by unrelated load | Old target terminates; new target gets a new `TargetId`, even if PID/app/artifact are equal |
| Ownership is acquired/released/transferred | Attachment/control-lease and ownership revision advance; target generation does not |
| Target terminates | Final exact `TargetRef` is retained in a tombstone; that `TargetId` is never reused |

For an explicit **replace-image** operation, this Study recommends preserving `TargetId` only
when the runtime deliberately promises logical-target continuity and atomically increments
target/image generations. Ordinary kill-then-load never preserves identity. Master/Steering
must confirm this policy.

### Authority model

1. A session negotiates capabilities but owns no target merely by existing.
2. An attachment binds one exact session generation to one exact target generation.
3. `observer` grants only declared read/event/inspection authorities. It cannot pause, resume,
   step, write memory/registers, alter resources, load/replace, or terminate, even if no
   exclusive owner exists.
4. `exclusive` may grant control authorities. Exactly one active control lease exists per
   target generation unless a future shared-control capability explicitly redesigns this rule.
5. Mutation requests carry `AttachmentRef` and expected generations. The executive rejects a
   stale session, target, image, attachment, or ownership revision before any side effect.
6. An attachment to a nonexistent PID/target is rejected; sessions cannot reserve future PID
   numbers by locking them.
7. A stable `OwnerId` used by resources is distinct from `SessionId` and `AttachmentId`.
   `HSX-ST-006` owns its issuance/provenance/revision semantics. Mutation authority still
   requires the active attachment lease, not merely an owner label.
8. Closing another session requires a separately negotiated administrative authority; a normal
   control session can close only itself.
9. The Executive-to-VM global attached mode is an internal runtime-control capability and is
   not the target attachment/control-lease API.

### Lifecycle operation rules

All lifecycle mutations use a unique operation ID, client idempotency key, explicit expected
references, and an authoritative commit record. Request acceptance means **pending**, not
committed state.

#### Create/load/start/claim

- Portable provisioning may expose separately authorized staged `create`, `load`, `start`, and
  `claim` primitives with explicit staging identity and rollback.
- A Debugger `Launch` is advertised only with an atomic **launch-and-claim** capability. The
  runtime stages/validates the image and resources before making the target visible/runnable.
- Success commits one target, loaded-image reference, initial run/stop state revision, and
  exclusive attachment lease. Response and lifecycle event carry the same operation ID and
  commit revision, so either arrival order can be deduplicated.
- Failure creates no externally controllable target or lease and advances no committed target
  or image generation. All staged resources are reclaimed or a typed rollback failure is
  reported.
- A retried idempotency key returns the original pending/result/tombstone; it never creates a
  second target.
- `ArtifactRef` is computed from the exact accepted HXE bytes. Requested app name and path are
  recorded as display/provenance only.

#### Attach/claim and observe

- `Attach(exact TargetRef, mode)` never creates or replaces a target.
- Exclusive attach atomically verifies target continuity and absence of another control lease,
  then returns `AttachmentRef` and ownership revision.
- Observer attach returns an observer attachment and cannot later mutate without an explicit
  claim transition.
- Upgrading observer to exclusive and transferring control are explicit operations with
  expected ownership revision; they are not side effects of reconnect.
- Attach/claim responses include the current `LoadedImageRef`, lifecycle state, negotiated
  target capabilities, and enough state revision evidence for `HSX-ST-004` reconciliation.

#### Detach/release

- `Detach` releases one attachment while leaving the session usable.
- Observer detach has no target-state effect.
- Exclusive detach requires an explicit supported target-state policy input such as preserve,
  resume, or pause-at-safe-boundary. The portable contract has no hidden product default.
- Release is complete only when the ownership revision proves the lease is no longer
  authoritative and any requested target-state policy has authoritative outcome evidence.

#### Disconnect/session close and unexpected loss

- `Disconnect` closes one debugger/runtime session; it is not an alias for detach or terminate.
- Graceful close supplies an explicit action for every exclusive attachment. Missing or
  unsupported policy is rejected before partial close.
- Exclusive attach/claim registers a required **orphan policy** and lease/grace inputs for
  unexpected transport/client loss. Observer loss simply releases the observer attachment.
- A TCP/RPC/event socket loss does not alone prove session loss. The session may remain within
  its lease grace and may be resumed only with the negotiated resumption proof.
- Successful resume retains the session ID, increments session generation, fences the old
  connection, and returns exact target/attachment continuity evidence.
- If resume is unsupported or fails, the client opens a new session and explicitly reattaches;
  it may not inherit ownership merely because client name/PID match.
- Execution effects of preserve/resume/pause/terminate policies require state evidence owned by
  `HSX-ST-004`; policy availability is capability-driven. Product defaults remain a Steering
  decision.

#### Terminate and kill

- `Terminate` means actual target terminal/removal intent; `Kill` is a forced termination mode,
  not pause.
- The command requires an exact target and control lease, unless separately authorized
  administrative policy says otherwise.
- Acceptance yields pending operation evidence only. Success requires an authoritative final
  lifecycle commit/tombstone with the exact final target/image references, terminal cause,
  exit status when available, removal status, and lifecycle revision.
- `unknown_pid` is not termination success. A repeated idempotency key can return the matching
  stored tombstone; a reused PID with another generation is `pid_reused`/`stale_target`.
- A target may reach guest exit before a kill request; the result distinguishes already
  terminated exact target from unknown/replaced target.

### Ordering and causal evidence

Each lifecycle commit record contains at least:

```text
LifecycleCommit {
  operation: LifecycleOperationRef
  lifecycle_revision: UInt64
  previous_target: TargetRef?
  target: TargetRef?
  loaded_image: LoadedImageRef?
  attachment: AttachmentRef?
  transition: typed enum
  outcome: committed | failed | aborted | uncertain
  cause: typed enum
  event_stream: EventStreamRef
  event_seq: EventSequence?
  terminal: bool
  diagnostics: typed list
}
```

Rules:

- lifecycle revisions are monotonically ordered within one executive incarnation;
- authoritative response and event copies of one commit have the same operation/revision and
  are idempotently applied once;
- a completion for an old executive/session/target/attachment generation is rejected and
  cannot mutate current state;
- commands include expected references/revisions (compare-and-set semantics);
- the event stream supplies delivery ordering, while the lifecycle revision supplies domain
  ordering; `HSX-ST-005` owns cursor/ACK/gap recovery details;
- no clock time, response arrival order, PID observation, or app-name comparison establishes
  lifecycle causality;
- only operations declared idempotent or carrying a server-recognized idempotency key may be
  retried automatically after uncertain transport loss.

### Reconnect continuity outcomes

Reconciliation returns exactly one typed outcome:

| Outcome | Required proof | Client consequence |
|---|---|---|
| `retained` | Same executive, target, PID generation, target generation, loaded image, and control lease/session generation (or proven resumed successors) | Continue after cursor/state/resource reconciliation |
| `target_restarted` | Same logical target ID but incremented target/image generation with an explicit replacement commit | Invalidate epochs/resources; require explicit reattach/reconcile policy |
| `pid_reused` | Numeric PID matches but generation/target ID differs | Never bind automatically; present as different target |
| `target_lost` | Exact prior target tombstone/removal proof | End attachment and surface terminal/lost state |
| `ownership_lost` | Target retained but lease owner/revision no longer matches | Fall back to observer only if explicitly allowed; never mutate |
| `executive_replaced` | Executive instance differs and no cross-incarnation continuity proof exists | Invalidate all prior refs; full discovery, no automatic mutation |
| `continuity_unknown` | Required identity/generation/event evidence unavailable or gapped | Fail closed; legacy degraded mode may display observations only |
| `incompatible_profile` | Required identity/lifecycle capabilities are absent | Refuse full-mode operation or enter named degraded profile |

Cross-incarnation target continuity is not part of the minimum profile. A future capability may
preserve stable target identity across executive replacement only if it supplies durable,
unambiguous continuity proof; PID/app/image heuristics are insufficient.

## Capability and degraded behavior

### Recommended full capability concepts

Master should allocate/version a coherent portable profile whose descriptive capabilities
cover:

- executive/stream/session/target/PID-generation/loaded-image identity DTOs;
- exact-reference mutation fencing and lifecycle revisions;
- exclusive and observer attachments with enforced authority;
- idempotent lifecycle operations and queryable operation results/tombstones;
- explicit detach/disconnect/orphan policies;
- authoritative termination confirmation;
- atomic launch-and-claim when Debugger Launch is offered;
- session resumption with generation fencing when transparent transient recovery is offered;
- optional cross-incarnation target continuity only when actually implemented.

Capabilities are negotiated explicitly and are immutable within one session generation.
Protocol version alone does not imply them. If the coherent identity/lifecycle profile is
partially advertised or required fields are missing, negotiation fails rather than mixing
full and PID-only semantics.

### Named legacy degraded profile

The current migration oracle should be represented by a specifically named/tested
**PID/session legacy profile**, not guessed from “version 1.” In that profile:

- PID, app name, program path, current session UUID, HXE CRC, and snapshots are weak
  observations only;
- no target or loaded-image continuity is claimed across reconnect, executive/VM restart,
  reset, reload, event gap, or PID disappearance/reappearance;
- observer clients are kept read-only by the Debugger even though the current server does not
  enforce that rule for unlocked PIDs;
- non-idempotent load/start/reload/kill is never blindly retried;
- Debugger Launch is unavailable because atomic launch-and-claim is absent;
- terminate success requires same-connection response plus immediate absence reconciliation,
  but remains explicitly degraded/unconfirmed compared with a stable tombstone;
- ownership reacquisition after connection loss is explicit and may fail on the orphaned old
  session; no recovered-health claim occurs before full task/lock refresh;
- resource reconciliation is nondestructive because owner/target/image generations are absent;
- removal criteria are implementation of the coherent full profile and passing the fixtures
  below. The profile is not indefinite compatibility authority.

### Failure vocabulary

The target contract needs typed failures, each carrying available exact references, operation
ID, observed revision, and retry disposition:

- `incompatible_capability_profile`, `unsupported_policy`, `policy_required`;
- `stale_executive`, `stale_session`, `stale_attachment`, `stale_target`, `stale_image`;
- `target_not_found`, `target_lost`, `target_replaced`, `pid_reused`,
  `continuity_unknown`;
- `ownership_conflict`, `ownership_lost`, `observer_read_only`, `lease_expired`;
- `invalid_lifecycle_state`, `operation_conflict`, `operation_unknown`,
  `operation_outcome_uncertain`;
- `image_validation_failed`, `resource_allocation_failed`, `rollback_failed`;
- `termination_unconfirmed`, `already_terminated`, `administrative_authority_required`.

Errors must not collapse into an unstructured string for full-profile consumers. Diagnostic
text remains supplementary and clients tolerate unknown diagnostic fields, not unknown
authority outcomes.

## Conformance fixture plan

The proposed contracts need portable golden request/response/event fixtures plus an in-memory
reference state machine. The same scenarios should run against Python first and later any
other HSX implementation.

### Identity and generation fixtures

1. **Executive incarnation:** restart/reinitialize identity state; prove new
   `ExecutiveInstanceId`, stream identity, and rejection of every old reference.
2. **PID reuse:** terminate target A, reuse its numeric PID for B, increment PID generation,
   and reject delayed A pause/kill/resource/inspection operations.
3. **Controller reset:** allow numeric PID counter reset only under a new executive
   incarnation; prove no alias with pre-reset references.
4. **Multiple instances:** load identical HXE bytes twice; artifact digest is equal while
   TargetId, LoadedImageId, PID reference, and attachment are distinct. App suffix is ignored
   by identity comparisons.
5. **Different metadata/name:** prove the exact accepted-byte digest changes when accepted HXE
   bytes change; CRC/name are reported but never used as the comparator.
6. **Serialization:** round-trip maximum 64-bit generations through Python and JavaScript-safe
   JSON strings; reject malformed/truncated/rounded identifiers.

### Load/replace/launch fixtures

7. **Atomic launch success:** stage, validate, commit target+image+start-state+claim once; event
   and response share operation/revision and either arrival order reduces once.
8. **Atomic launch failure:** inject bad CRC, unsupported capability, metadata registration
   error, mailbox allocation error, and start failure; no target/lease is externally visible
   and all reservations are reclaimed.
9. **Lost launch response:** repeat idempotency key; return the original result and create no
   second target.
10. **Replace success:** same deliberate logical TargetId, new target/image generations and
    LoadedImageId; every old epoch/resource/attachment mutation is stale.
11. **Replace failure:** inject failure before commit; old target/image remains usable and
    committed generations do not change.
12. **Kill then load:** prove this creates a new TargetId even when PID, app name, path, and
    artifact later match.
13. **Streaming staging:** transfer/session ID is distinct from PID/TargetId; abort consumes no
    externally committed target generation.

### Attachment and policy fixtures

14. **Exclusive conflict:** first exact claim succeeds; second exclusive claim returns
    ownership conflict with current revision and no side effect.
15. **Observers:** multiple observers attach; every mutation fails `observer_read_only` both
    with and without an exclusive owner.
16. **Nonexistent target:** attachment to an unallocated PID/reference fails and cannot reserve
    a future PID.
17. **Upgrade/transfer:** observer-to-exclusive and owner transfer require expected ownership
    revision; stale contenders are fenced.
18. **Detach:** observer detach does not change target; each supported exclusive policy yields
    authoritative release/state evidence; missing policy fails before release.
19. **Graceful disconnect:** per-attachment policy is complete-or-rejected; session closure,
    lease release, and target effects have ordered commits.
20. **Unexpected loss:** exercise each supported orphan policy and lease grace. A resumed
    session increments generation and fences the old transport; a new session does not inherit
    authority.
21. **Global VM attach distinction:** raw Executive-to-VM attached mode never grants or revokes
    a target control lease.

### Termination and reconnect fixtures

22. **Termination pending/commit:** command response acceptance is not terminal; final exact
    tombstone is. Guest exit, requested terminate, and force kill retain distinct causes.
23. **Lost kill response:** query/retry by operation/idempotency key; receive the original exact
    tombstone without affecting a reused PID.
24. **Unknown vs already terminated:** unknown reference is error; matching tombstone is
    `already_terminated`; same PID with another generation is `pid_reused`.
25. **Reconnect matrix:** cover retained, target restarted, PID reused, target lost, ownership
    lost, executive replaced, continuity unknown, and incompatible profile.
26. **Stale completion:** deliver lifecycle response/event after session/target generation has
    advanced; prove it cannot mutate current state.
27. **Legacy degraded:** remove identity capabilities and prove no automatic launch,
    non-idempotent retry, ownership claim, destructive reconciliation, or continuity assertion.

### Existing oracles to retain

- current session open/conflict/keepalive/timeout/close tests;
- app-name uniqueness and multiple-instance suffix tests;
- monolithic/streaming HXE validation and abort tests;
- pause/resume/kill and task-state terminal event tests;
- deterministic HXE output tests.

They remain regression inputs, but the new fixtures must assert exact identities, generations,
authority and commit evidence rather than only PIDs and status strings.

## Cross-study and Debugger mapping

### `DBG-ST-006` question coverage

| Question | Contribution from this Study | Remaining owner |
|---|---|---|
| 1. Executive/stream/target/PID/image identity | Full identity DTO, scope, generation, serialization, and continuity proposal | `HSX-ST-005` finalizes stream/cursor relation |
| 2. Address/ABI | `ArtifactRef`/`LoadedImageRef` bind address metadata to exact image generation only | `HSX-ST-003` |
| 3. Ordered run/stop/block/fault/termination evidence | Lifecycle revision, operation correlation, exact termination/tombstone and target-loss boundary | `HSX-ST-004` owns run/stop/state tokens; `HSX-ST-005` delivery ordering |
| 4. Event cursor/gap/ACK | `EventStreamRef` defines the sequence namespace and changes on reset | `HSX-ST-005` owns cursor/ACK/gap semantics |
| 5. Snapshot consistency | Target/image generations fence snapshots and invalidate them on replacement/loss | `HSX-ST-004` owns snapshot revision/atomicity |
| 6. ABI/unwind/location | Exact image generation binds debug artifacts/ABI | `HSX-ST-003` |
| 7. Exact stepping | Exact target/attachment generations fence control operations | `HSX-ST-004` owns retirement/precedence |
| 8. Create/load/start/claim and lifecycle ownership | Full lifecycle/lease/policy/termination proposal | Master synthesis |
| 9. Resource identity/provenance/revision | Distinct OwnerId, attachment authority, target/image generation inputs | `HSX-ST-006` |
| 10. Blocked-state inspection | Target continuity and lease validity do not imply snapshot stability | `HSX-ST-004` decides inspection-stable blocked states |

### Proposed Debugger design dependencies

| Debugger contract | Required output from this Study |
|---|---|
| `DBG-D-001` | Session/target/attachment generation tags on commands/effects/completions; stale-generation and idempotency rules |
| `DBG-D-002` | Executive/session/stream identity, immutable capability profile per session generation, resumption/reconciliation outcomes, idempotent-retry boundary |
| `DBG-D-003` | Exact Target/PID/LoadedImage/Artifact identity and generation invalidation rules |
| `DBG-D-004` | Artifact/image binding so symbols/source/inspection cannot cross image generations |
| `DBG-D-005` | Separate OwnerId from session/lease, exact target/image generation, nondestructive degraded behavior |
| `DBG-D-006` | Attach/launch/detach/disconnect/terminate meanings, explicit policy inputs, ownership lease, authoritative terminal confirmation |

### Sibling HSX Study boundaries

- `HSX-ST-003` consumes `ArtifactRef`/`LoadedImageRef` and defines address spaces, ABI, unwind,
  frame and variable-location semantics for that exact image generation.
- `HSX-ST-004` consumes `TargetRef`/`LoadedImageRef` and defines state revision, stop evidence,
  snapshot token, exact stepping, and blocked-state inspection stability.
- `HSX-ST-005` consumes `ExecutiveRef`/`EventStreamRef` and defines cursor, sequence, ACK,
  replay, eviction, gap/drop and recovery semantics.
- `HSX-ST-006` consumes `OwnerId` separation, `AttachmentRef`, `TargetRef`, and
  `LoadedImageRef`, then defines resource IDs, provenance and desired/observed revisions.
- `HSX-ST-001` owns final legacy mapping, stable HSX ID allocation, shared traceability, and
  any decision to split further Studies.

## Uncertainty and open questions

1. **Detach/disconnect/orphan defaults:** portable semantics require explicit policy inputs,
   but the product default is a Steering decision. This Study does not select resume, pause,
   preserve, or terminate.
2. **In-place replacement identity:** recommendation is same TargetId only for an explicit
   transactional replace operation, with target/image generation increments. Master/Steering
   should confirm; ordinary load after kill always receives a new TargetId.
3. **Cross-incarnation continuity:** the minimum profile treats an executive-instance change as
   discontinuity. A future durable-target capability needs a separate persistence/recovery
   contract before it can preserve TargetId.
4. **Session resumption proof/security:** fencing semantics are required here, but credential,
   authentication and authorization design is outside this Study. Until such proof exists,
   reconnection opens a new session and reacquires explicitly.
5. **Tombstone/idempotency retention:** the portable contract needs a minimum query window or
   capacity behavior. Exact bounded retention belongs in later design/resource budgets; expiry
   must return `operation_unknown`, never false success.
6. **Atomic Launch availability:** it may be optional by profile, but the Debugger must expose
   only attach when absent. No fallback may label non-atomic load/attach as Launch.
7. **Pause-at-safe-boundary policy:** its exact instruction/state evidence is owned by
   `HSX-ST-004` and must be unavailable unless that capability is accepted.
8. **ID allocation mechanics:** random 128-bit IDs or executive nonce plus monotonic local
   counters both satisfy semantics if collision/fencing evidence is provided. Master design
   should freeze the wire representation without importing AVR policy.

None of these questions prevents Master synthesis of the identity/lifecycle requirements and
architecture boundary. They prevent premature freezing of selected detailed policies.

## Proposed descriptive contract concepts for Master

Without reserving numeric HSX IDs, this Study recommends that Master create stable proposed
contracts for:

- executive incarnation and event-stream sequence-namespace identity;
- typed session, target, PID-generation, artifact, loaded-image, attachment, and lifecycle
  operation references;
- collision-safe/string-safe identity and monotonic generation serialization;
- exact-reference compare-and-set fencing on every lifecycle mutation;
- exclusive/observer attachment leases with enforced authority and ownership revision;
- transactional image replacement and atomic launch-and-claim capability;
- explicit detach/disconnect/orphan policy inputs and session-resumption fencing;
- idempotency keys, lifecycle revisions, authoritative commits, and target tombstones;
- fail-closed reconnect outcomes and named PID/session legacy degraded behavior;
- the conformance fixtures listed above.

## Conclusions

1. PID, app name, path, HXE CRC, and session UUID are useful current fields but do not compose a
   safe portable target identity.
2. The minimum safe identity is an executive incarnation plus exact target/PID generations and
   a distinct loaded-image/artifact reference. Every event, snapshot, resource and lifecycle
   operation must carry the relevant references.
3. Session, attachment, control lease, owner label, TCP connection, and target are separate
   domains. Observer read-only behavior must be enforced even when no exclusive owner exists.
4. Debugger Launch requires an atomic launch-and-claim capability. Current load/exec and
   kill-then-reload behavior cannot be relabeled as that capability.
5. Lifecycle acceptance is pending evidence. Only a generation-fenced commit/tombstone proves
   creation, replacement, release, target state policy, or termination.
6. Reconnect is retained only with exact continuity and ownership proof. Numeric PID/app/image
   heuristics produce `continuity_unknown` or `pid_reused`, never silent reattachment.
7. Current PID/session behavior can remain a named, tested degraded migration profile with
   fail-closed restrictions and removal criteria; protocol version guessing is not acceptable.
8. The proposed model supplies the identity/lifecycle inputs required by
   `DBG-D-001..DBG-D-006` while leaving cursor, execution/snapshot, ABI and resource details to
   their owning sibling Studies.

## Completion and handoff

Status is **COMPLETE FOR MASTER SYNTHESIS**. Master owns stable HSX requirement/architecture/
design ID allocation, the final capability names and field registry, cross-track relations,
review package, and Steering routing. This Study grants no implementation authority.
