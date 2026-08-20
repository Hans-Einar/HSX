# HSX-ST-006 — Breakpoint and Watch Identity, Provenance, and Revisions

- Status: COMPLETE FOR MASTER SYNTHESIS
- Coordinator: `HSX-ST-001`
- Debugger dependency: `DBG-ST-006`
- Issue: #47
- Iteration: `DBG-IT-001-003`
- Evidence baseline: activation head `d135e542b2a959c2ea67e3a1ea65df7e0bcd6baf`
- Scope guard: Study/contract proposal only; no product, Debugger Refactor, or AVR authority

## Question and scope

What portable HSX contract lets a debugger create, observe, update, share, release, reconnect
to, or deliberately adopt a remote breakpoint or persistent live-watch resource without
confusing a PID/address/integer ID with identity or deleting another owner's resource?

This Study owns the portable recommendations for:

- remote resource identity and target/image generation binding;
- owner, control-lease authority, provenance and lifetime policy;
- resource-local, owner-set, effective-binding and inventory revisions;
- compare-and-set mutation, idempotency and ambiguous-result recovery;
- same-location sharing/collision, external observation and non-destructive cleanup;
- reconnect, explicit adoption, release, tombstones and termination cleanup;
- resource lifecycle events, breakpoint-hit evidence and live-watch observation evidence;
- capability/version/limit negotiation and explicit address/ID-only degraded behavior;
- conformance fixtures needed by the Debugger resource reconciler and exact-step planner.

The Study covers **remote concrete HSX resources**, not every debugger-side concept called a
breakpoint or watch. It intentionally keeps these domains separate:

1. the Debugger's logical source/function/instruction breakpoint intent and owner-scoped
   desired state;
2. the Debugger's standard snapshot Watch expression, evaluated against one selected
   stop/frame/snapshot;
3. a concrete remote HSX breakpoint at a typed code location; and
4. an optional persistent remote HSX live watch that samples a typed location and emits
   observations while its lifetime policy permits.

It does not assign numeric HSX Requirement/Architecture/Design IDs, choose frontend UX,
define source-to-address resolution, define the value-expression language for normal Watch,
or design an AVR representation. It does not authorize product implementation.

## Ownership and cross-Study boundary

| Concern | Owning input/output used by this Study |
|---|---|
| Executive, session, target, PID/image generations, attachment/control lease and stable `OwnerId` separation | `HSX-ST-002` |
| Typed code/data/register locations, checked ranges, image/debug-bundle and ABI binding | `HSX-ST-003` |
| Stop/snapshot/inspection revisions, exact step, breakpoint bypass and stop precedence | `HSX-ST-004` |
| Event stream identity, cursor/ACK/gap/resume and profile negotiation continuity | `HSX-ST-005` |
| Remote breakpoint/live-watch identity, provenance, resource revisions and cleanup | this Study |
| Logical desired resources, snapshot expressions, reconciliation and presentation | `DBG-D-005` / Debugger core |
| Source-step plan semantics and temporary-condition intent | `DBG-D-006` / Debugger core |

`HSX-ST-006` supplies a target service and evidence model. It does not move the semantic
owner of source breakpoints, DAP replacement sets, standard Watch expressions, or source-step
algorithms into the Executive.

## Authority and method

Three evidence classes remain distinct:

1. **Current Python implementation behavior** is a regression oracle at the evidence
   baseline. It is not portable authority.
2. **Legacy documents and DR/DG/design intent** are provenance. Their statements are not
   silently promoted to stable contracts.
3. **Recommended target contract** is this Study's requirements-driven proposal for Master
   synthesis and later stable ID allocation.

The recommendation is deliberately fail-closed. It prefers an explicit degraded result to
ownership inferred from a matching address, expression, PID, client name or event.

## Evidence sources

### SDP and Steering inputs

- `AGENTS.md`, `SDP/README.md`, and `SDP/Shared/Process.md`;
- active HSX and Debugger `Traceability/CurrentIndex.yaml` files;
- issues #47 and #38, including Steering comments `5348192567` and `5348190806`;
- `HSX-ST-001..HSX-ST-005`, `DBG-ST-006`, `DBG-ST-003`, and the accepted target
  architecture direction;
- proposed `DBG-D-002..DBG-D-006`, especially the `DBG-D-005` desired-versus-actual
  resource model and `DBG-D-006` one-shot breakpoint interaction.

### Legacy intent and current documentation

- `main/02--Study/02.01--Requirements.md` (`DR-8.1`, `DG-4.2`, `DG-5.2`, `DG-5.3`,
  `DG-8.1`, `DG-8.2` provenance);
- `main/03--Architecture/03.01--VM.md`, `03.02--Executive.md`, and `03.05--Toolkit.md`;
- `main/04--Design/04.01--VM.md`, `04.02--Executive.md`, `04.09--Debugger.md`, and the
  archived Toolkit design;
- `docs/executive_protocol.md` and `docs/hsx_dbg_usage.md`.

These sources intend per-PID breakpoints, session locking, observers, persistent executive
watches, event delivery and reconnect. They do not define stable resource identity,
provenance, revisions, multi-owner collision behavior, safe adoption or a distinction between
standard snapshot Watch and persistent live watch.

### Current implementation and client behavior

- `python/execd.py`: session locks, breakpoint cache/dispatch, live-watch store/evaluation,
  events, task cleanup and request authorization;
- `platforms/python/host_vm.py`: `DebugState`, VM breakpoint sets, attach/detach and debug
  stop behavior;
- `python/executive_session.py`, `python/hsx_dbg/backend.py`,
  `python/hsx_dbg/session.py`, and `python/hsx_dbg/context.py`;
- `python/hsx_dap/__init__.py`: local desired breakpoint maps, remote polling, external
  classification, standard Watch evaluation, reconnect restoration, teardown and temporary
  breakpoint clearing;
- `python/tests/test_executive_sessions.py`, `test_executive_session_helpers.py`,
  `test_hsx_dbg_backend.py`, `test_hsx_dap_harness.py`,
  `test_hsx_dap_reconnect.py`, and `test_debugger_basic.py`.

## Verification evidence

The assigned worker ran the current regression oracles with bytecode and pytest cache
disabled:

```text
$env:PYTHONDONTWRITEBYTECODE='1'
& 'c:/Users/hanse/miniconda3/python.exe' -m pytest -p no:cacheprovider \
  python/tests/test_executive_sessions.py \
  python/tests/test_executive_session_helpers.py \
  python/tests/test_hsx_dbg_backend.py \
  python/tests/test_hsx_dap_harness.py \
  python/tests/test_hsx_dap_reconnect.py -q

114 passed in 0.88s
```

This proves the current single-client happy paths, PID-lock conflict/release, breakpoint
add/list/clear, watch add/change/list/remove, task-kill cleanup, remote-address polling and
breakpoint reapply tests still pass. The suite does **not** prove remote provenance,
same-location multi-owner preservation, conditional revisions, ambiguous-operation recovery,
safe watch restoration, target/image continuity, lifecycle resource events, tombstones or
explicit adoption. Several client tests use mocks whose watch field names are more permissive
than the real server.

## Terminology

| Term | Meaning | Explicit non-meaning |
|---|---|---|
| Logical resource | Debugger-side user/tool intent with a stable logical ID, specification and desired owners | An HSX remote record or a code address |
| Snapshot expression | A normal Watch/hover/evaluate request against one stopped snapshot/frame | A persistent target sampling resource |
| Remote resource | One target-managed concrete breakpoint or live-watch record | Every logical source breakpoint that resolves to it |
| Resource reference | Stable opaque identity plus exact target/image/resource generations | A PID/address, expression text or numeric list position |
| Owner | Stable actor identity separate from session and attachment | A display client name or whichever client most recently observed an event |
| Owner lease | One owner's time/attachment/authority-bounded claim on a remote resource | The target control lease itself |
| Provenance | Authoritative origin, purpose, creator operation, binding and lifetime metadata | A client guess from address or expression equality |
| Resource revision | Monotonic version of one remote record | Event sequence or target execution revision |
| Inventory revision | Monotonic version of the complete resource collection for one target generation | A count or latest resource ID |
| Effective binding revision | Version of the stop-producing set actually effective at one concrete location | One owner's resource revision alone |
| Observation revision | Monotonic live-watch sample/change evidence | A configuration update to the watch resource |
| Tombstone | Retained final evidence for a resource that no longer exists | Permission to reuse the old identity |

## Current implementation findings

### Breakpoints are address-set membership, not resources

The current Executive and VM keep breakpoint state as `Dict[pid, Set[address]]` and
`DebugState.breakpoints`. Addresses are masked to 16 bits in Executive/VM paths. Add is set
insertion, remove is set discard, and list returns sorted addresses. There is no remote
breakpoint ID, creator, owner, purpose, image binding, revision, condition identity or
tombstone.

Consequences:

1. Two owners at the same address collapse into one bit of set membership. Removing either
   removes the only effective breakpoint.
2. A source breakpoint resolving to several locations and several logical breakpoints sharing
   one location cannot be represented faithfully at the remote boundary.
3. A breakpoint at the same numeric address after image replacement or PID reuse is
   indistinguishable from the old one.
4. `clear_all` lists and removes addresses iteratively. It is neither owner-scoped nor an
   atomic compare-and-set operation.
5. `debug_break` emitted by `execd.py` reports PC/phase/reason but no stable matching resource
   reference or resource revision.
6. Executive logs record “added” or “removed,” but no resource lifecycle event supports
   event-driven reconciliation.

The VM's debugger attach is target-global rather than client-owned. The Executive attaches
lazily on the first breakpoint operation and caches the same remote set for every client.
Session close does not detach it. Task disappearance drops cached breakpoint state; VM debug
detach destroys that PID's VM debug state and returns an empty set.

### PID locks are mutation gates, not resource ownership

`session.open(pid_lock=...)` records `pid_locks[pid] = session_id`. Breakpoint/watch mutation
calls `ensure_pid_access`, but that method succeeds for any caller whenever the PID is
currently unlocked. An observer session or a sessionless caller is therefore able to mutate
an unlocked target; it is blocked only when another session already holds the numeric PID
lock.

Closing or timing out a session releases PID locks and event subscriptions. It does not
remove, transfer, mark orphaned or otherwise revise breakpoint/watch records. No resource can
answer which session/owner created it, and the later lock holder gains mutation access to all
existing resources without adoption evidence.

This diverges from the documented read-only-observer intent and proves that current lock
ownership must not be reused as portable resource provenance.

### Live watches are target-global integer records

`execd.py` stores `watchers[pid][watch_id]`, with one process-global counter beginning at 1.
Each record contains expression, resolved type/address or local metadata, length and last
bytes. It contains no owner/session, target generation, image generation, specification
digest, lifetime, resource revision or sample revision.

- Identical expressions can be added repeatedly and receive different IDs.
- Any caller that passes the current PID mutation gate can remove any ID.
- Session close/timeout leaves watches running; task removal deletes all records.
- Executive restart restarts the ID namespace without an Executive/resource-generation
  fence.
- Local watches cache symbol/location metadata and re-evaluate live registers/memory after
  steps; image/frame lifetime is not represented.
- Watch changes emit `watch_update` with integer ID, old/new bytes and optional expression,
  address/symbol/location. The event has a global event sequence but no resource, target,
  image, inspection or observation revision.
- Read failures only log a warning. The resource does not transition to an observable
  degraded/error state.

The configuration record and the sampled value are therefore conflated. A value change
silently mutates `last_value`, while clients cannot prove which resource generation or target
state the observation belongs to.

### Current client behavior transfers or guesses ownership

The legacy DAP adapter keeps frontend-local breakpoint specifications and actual addresses.
Every five seconds it lists the global remote address set, subtracts locally known addresses,
and labels the remainder external. An external and local breakpoint at the same address are
indistinguishable and the external one disappears from that classification.

- Normal teardown clears addresses recorded under local entries.
- the custom `clearAllBreakpoints` path force-clears both local and read-only external entries;
- the step fallback lists and temporarily clears every breakpoint at the origin address,
  then attempts to restore it, irrespective of owner or provenance;
- reconnect reopens by cached PID and reapplies stored logical specifications without target
  or image generation evidence.

For watches, DAP evaluation with context `watch` may call `add_watch`, turning a standard DAP
Watch request into a persistent Executive resource. `watch_update` events populate the same
expression-to-ID maps used for locally created watches; observation can therefore become
local ownership. Teardown later attempts to delete every mapped ID.

Reconnect snapshots the locally remembered watch expressions, opens a new session, and adds
them again. Since the old server-side watches survive session loss, this can duplicate live
watches. No current test exercises that collision.

There is also concrete real-client/server schema drift: the server exports an added watch as
`id`, while `DebuggerBackend.add_watch()` reads only `watch_id` and can return zero;
`DebuggerBackend.remove_watch()` sends `watch_id`, while the server dispatch accepts `id` or
`watch`. Mock-based helper tests do not expose this mismatch. The mismatch is product-code
evidence, not a change authorized by this Study.

### Current reconnect and cleanup cannot prove safety

The current reconnect tests prove that a stored breakpoint address is sent to a new backend.
They do not prove it is the same Executive, target generation, PID generation or image. A
matching PID is treated as continuity.

After an uncertain disconnect:

- the old session may retain its lock until timeout;
- breakpoints and watches continue independently of that session;
- the client cannot distinguish its old resources from another client's or runtime's;
- a repeated watch ID after restart may denote another record;
- reapplying a breakpoint to the same address can affect a replacement image;
- deleting restored resources can remove state required by another owner.

The only honest full-contract result is `continuity_unknown`. A conservative legacy adapter
may preserve observations, but may not claim ownership or destructive convergence.

## Findings from documented intent

Legacy requirements/designs provide useful direction: one debugger should control a PID while
observers remain read-only; breakpoint comparisons belong in the Executive/VM rather than
guest code patching; breakpoints should survive normal run/stop and disappear on task exit;
watches are persistent Executive-side sampling records; sessions negotiate capabilities and
reconnect; and tooling should share a debugger core.

The material does not resolve resource ownership after timeout/reconnect, generation or reuse
of integer IDs, collision/sharing, cleanup, revision/CAS, inventory-to-stream consistency,
live-watch sampling failures, or snapshot-Watch separation. A new stable contract is required.

## Alternatives compared

### Resource identity

| Alternative | Advantages | Risks | Decision |
|---|---|---|---|
| PID + address for breakpoint, PID + integer ID for watch | Matches current protocol; tiny records | PID/image/ID reuse, collisions, no provenance/revision, unsafe reconnect/delete | Reject as full contract; named degraded profile only |
| Canonical specification hash as identity | Deterministic deduplication | Identical intent from distinct owners collapses; updates and conditional semantics are awkward; hash does not prove runtime creation | Use as comparison/provenance field only, never identity |
| Opaque non-recycled `ResourceRef` bound to exact target/image/resource generation | Collision-safe, versionable, reconnect and stale-reference checks are mechanical | Adds wire/storage state | **Recommend** |

### Ownership

| Alternative | Advantages | Risks | Decision |
|---|---|---|---|
| Current session/PID lock owns every resource | Simple exclusive model | Session, attachment, target and resource owner are conflated; close/reconnect semantics remain ambiguous | Reject |
| Every resource is session-ephemeral and auto-deleted on disconnect | Easy cleanup | Transient transport loss destroys state; sharing and adoption are impossible; socket/session distinction is lost | Optional lifetime policy, not universal model |
| Stable `OwnerId` plus resource owner lease authorized by exact `AttachmentRef` | Separates identity, authority, lifetime and recovery; supports sharing and explicit adoption | Requires owner-set revisions, expiry and policy | **Recommend** |

### Collision representation

| Alternative | Advantages | Risks | Decision |
|---|---|---|---|
| One target-global bit/record per concrete address | Minimal implementation | Owners, conditions, hit counts and reasons collapse; deleting one affects all | Reject as full semantics |
| One public remote record per owner intent, with runtime-private physical coalescing | Correct provenance and stop evidence; hardware sharing is hidden | More logical records and limits | **Recommend minimum** |
| One shared public record with a mutable owner set | Efficient identical sharing | One owner update can affect everyone unless divergence creates a new record | Allow only through explicit share policy/CAS; never implicit address merge |

### Mutation and reconciliation

| Alternative | Advantages | Risks | Decision |
|---|---|---|---|
| List then unconditional add/remove | Current simple flow | Lost updates and destructive races | Reject as full contract |
| Resource-local CAS only | Protects updates/deletes | Cannot prove a complete desired-vs-actual inventory or absence at create | Necessary but insufficient |
| Resource-local CAS plus target inventory revision and idempotent operations | Bounded client reconciliation, safe ambiguous-result recovery and inventory snapshots | Conflict/retry handling required | **Recommend baseline** |
| Atomic owner-scoped batch reconcile | Strongest efficient convergence | More complex and may exceed constrained targets | Optional capability implementing the same baseline semantics |

### Reconnect and adoption

| Alternative | Advantages | Risks | Decision |
|---|---|---|---|
| Match PID/address/expression and adopt | User-friendly appearance | Can seize unrelated resources/targets | Reject |
| Always recreate and later clear | Simple | Duplicates watches; clears shared/external resources | Reject |
| Retain lease only with exact session/attachment resumption; otherwise observe or explicitly adopt with proof | Fail-closed and testable | Some legacy sessions cannot auto-recover | **Recommend** |

## Recommended portable resource contract

### Identity and wire representation

This Study consumes the `ExecutiveRef`, `SessionRef`, `TargetRef`, `LoadedImageRef`,
`AttachmentRef` and stable `OwnerId` separation proposed by `HSX-ST-002`.

Opaque resource, owner-lease, operation and tombstone IDs follow the same recommended
collision-resistant representation. Generations and revisions are unsigned monotonic 64-bit
values. JSON transports encode opaque IDs and 64-bit integers as canonical strings so a
JavaScript client cannot round them. They never wrap silently; the owning generation is
recreated before exhaustion.

The descriptive reference proposed for Master synthesis is:

```text
ResourceRef {
  executive: ExecutiveRef
  target: TargetRef
  loaded_image: LoadedImageRef
  resource_kind: execute_breakpoint | live_watch
  resource_id: OpaqueId128
  resource_generation: UInt64
}
```

Rules:

1. `resource_id` is never reused within one Executive incarnation. If a constrained
   implementation uses a recyclable slot internally, `resource_generation` changes and is
   mandatory on every external reference.
2. The full reference, not the ID alone, appears on get/list/mutate results, lifecycle events,
   hit/observation evidence and tombstones.
3. Breakpoints and live watches in the initial portable debug profile bind to one exact
   target and loaded-image generation. Image replacement makes the old reference stale.
4. A future target-lifetime resource not tied to an image must advertise a distinct binding
   scope and typed address semantics. It may not omit image binding by accident.
5. PID, app name, image path, expression text, address, client name, event sequence and DAP ID
   are display/correlation values only.
6. Unknown resource kinds or mandatory schema versions are typed unsupported results; clients
   do not reinterpret them as breakpoint/watch variants.

### Debugger logical resources remain outside the HSX record

The Debugger core keeps `OwnerId`, `LogicalResourceId`, source/function/instruction
specification, enabled state, frontend replacement-set semantics, resolution diagnostics and
zero or more `ResourceRef` bindings. HSX receives only resolved concrete resource specs.

- One logical source breakpoint may resolve to zero, one or many concrete HSX resources.
- Several logical resources may intentionally bind separate remote resources at the same
  typed location.
- A client correlation key may be echoed by HSX for an operation, but it is not remote
  identity or proof of ownership.
- Source-file paths, lines, symbol lookup and ambiguity policy are Debugger-owned.

A normal Watch/hover/evaluate is a `SnapshotExpression` owned by Debugger inspection. It uses
the stop/snapshot, frame and location contracts from `HSX-ST-003/004` and creates **no remote
resource**. `live_watch` is an optional, explicit product action with separate capability,
owner, lifetime, sampling and event semantics. A frame-relative live local is unsupported in
the baseline unless a later contract defines frame identity, frame exit and rebinding.

### Resource specification and state

The portable target record is conceptually:

```text
ResourceRecord {
  ref: ResourceRef
  specification: ConcreteResourceSpec
  specification_digest: Digest
  lifecycle_state: active | degraded | disabled | orphaned
  provenance: ResourceProvenance
  owners: OwnerClaim[]
  lifetime_policy: LifetimePolicy
  resource_revision: UInt64
  owner_set_revision: UInt64
  effective_binding_revision: UInt64
  created_inventory_revision: UInt64
  last_inventory_revision: UInt64
  capability_profile_generation: UInt64
  diagnostics: Diagnostic[]
}
```

`ConcreteResourceSpec` uses typed locations from `HSX-ST-003`:

- an execute breakpoint names an exact code-space address and optional explicitly supported
  condition/action fields;
- a live watch names an exact data/register/location recipe, byte/type interpretation,
  sampling trigger/policy and declared observation size;
- checked ranges are half-open and cannot be silently masked, wrapped or cast between spaces;
- unsupported conditions, actions, location kinds or sizes fail at create/update rather than
  being ignored.

The canonical specification digest detects equality and supports diagnostics/deduplication.
It is never identity. Runtime-private physical breakpoint/watchpoint slots may be coalesced,
but the public records and owner evidence remain distinct.

### Provenance

```text
ResourceProvenance {
  origin: client_managed | runtime_managed | system | external_unknown
  purpose: user | step_internal | diagnostic | other
  creator_owner: OwnerRef?
  creator_attachment: AttachmentRef?
  creator_operation_id: OpaqueId128?
  created_target: TargetRef
  created_image: LoadedImageRef
  created_resource_revision: UInt64
  created_cursor: EventCursor?
  adoption_history_digest: Digest?
}
```

Provenance is Executive-authored evidence. A client cannot set `origin=external_unknown` to
escape policy or set another owner as creator. Client-supplied labels may be stored as
untrusted annotations only.

An observed record with missing/unsupported provenance is `external_unknown`. Listing or
receiving an event never changes that classification or adds an owner. Purpose
`step_internal` is tied to one exact execution operation/stop token and is never adopted as a
user breakpoint.

### Owner, lease and mutation authority

`HSX-ST-002` requires a stable resource `OwnerId` distinct from `SessionId` and
`AttachmentId`. This Study refines the resource claim:

```text
OwnerClaim {
  owner_id: OwnerId
  owner_generation: UInt64
  owner_lease_id: OpaqueId128
  owner_lease_generation: UInt64
  authorized_by_attachment: AttachmentRef
  authority: observe | update_claim | release_claim | admin_delete
  acquired_resource_revision: UInt64
  lease_expiry_or_policy: ...
}
```

Rules:

1. An owner label has no mutation authority by itself. Create, claim, update, release and
   delete require an exact active `AttachmentRef`/control authority and expected generations.
2. Observers may list resources/events when capability and access policy allow, but cannot
   acquire ownership merely because no exclusive controller exists.
3. Multiple claims are permitted only under an advertised share policy. Releasing one claim
   never releases another.
4. A resource specification update that would affect other owners requires their explicit
   compatible policy or creates a new resource; one owner cannot silently rewrite a shared
   record.
5. Session/attachment resumption may retain an owner lease only through the exact resumption
   proof defined by `HSX-ST-002`. A new session/client name is not proof.
6. Owner-lease expiry is an ordered resource mutation with revisions/event evidence, not an
   in-memory timeout side effect hidden from clients.
7. Administrative target-wide deletion is a separately authorized operation. It is never
   used to implement DAP owner-scoped replacement or ordinary disconnect cleanup.

### Lifetime policies and cleanup

The resource declares one policy rather than inheriting undocumented session behavior:

| Policy | Owner/session loss | Last owner release | Target/image change |
|---|---|---|---|
| `attachment_ephemeral` | Release the affected claim after the negotiated orphan/resume policy resolves | Tombstone/delete | Tombstone as stale binding |
| `owner_ephemeral` | Follow owner-lease grace/resumption, not raw socket loss | Tombstone/delete | Tombstone as stale binding |
| `target_persistent_adoptable` | Mark orphaned; preserve without mutation | Preserve orphaned until explicit adoption/delete/target cleanup | Tombstone on target/image incompatibility |
| `system_managed` | No client cleanup effect | Runtime/system policy | Runtime/system policy with evidence |
| `external_unknown` | Preserve | Preserve | Observe resulting disappearance only |

Persistent means persistent according to this declared policy; it does not mean immortal or
silently inherited by the next debugger.

Disconnect/release processing is owner-scoped and ordered:

1. resolve the attachment orphan/resume policy;
2. release only claims proven to belong to that owner lease;
3. preserve other owners and all external/unknown resources;
4. tombstone an unowned ephemeral record; or mark a persistent record orphaned;
5. emit the same revisioned evidence through command result and event stream;
6. apply any target run-state policy separately through `HSX-ST-002/004`.

Target termination or committed image replacement invalidates/tombstones every incompatible
resource for that exact generation. A resource belonging to a reused PID is not migrated.

### Revisions and compare-and-set semantics

At least four revision dimensions are required:

| Revision | Scope and advancement rule |
|---|---|
| `resource_revision` | One record; advances for specification, lifecycle, provenance, owner, policy, enabled/degraded or equivalent authoritative change |
| `owner_set_revision` | One record's claims; advances for claim acquire/release/transfer/expiry even when concrete specification is unchanged |
| `effective_binding_revision` | The effective stop-producing/sampling binding at one location; advances whenever the matching set/physical effectiveness changes |
| `resource_inventory_revision` | Complete resource collection for one target generation; advances for every create, material update, owner-set change, tombstone or disappearance |

Live-watch sample/value changes use a separate `observation_revision`; they do not pretend
the watch configuration changed. Target execution/inspection revisions remain owned by
`HSX-ST-004`, and event sequence/cursor remains owned by `HSX-ST-005`.

Mutation rules:

1. Create carries operation/idempotency identity, exact target/image/attachment generations
   and, where absence matters, expected inventory revision.
2. Repeating an identical create operation after a lost response returns the same committed
   `ResourceRef` and revisions. Reuse with a different payload is an idempotency conflict.
3. Update/release/delete names the exact `ResourceRef` and expected resource/owner-set
   revision. Mismatch returns a typed conflict plus current reference/revisions and performs
   no side effect.
4. Delete of a record with other owners fails `resource_shared` unless a distinct
   administrative operation is authorized. Ordinary owner cleanup uses release, not delete.
5. List returns an immutable inventory snapshot at one target/inventory revision, including
   tombstone/continuation policy and the `EventCursor` at which the snapshot linearized.
6. Pagination is pinned to that snapshot/revision. It may not combine pages from changing
   live state.
7. A bounded reconciler refetches on CAS conflict. Unbounded retries, last-writer-wins and
   clearing unknown resources are prohibited.
8. An optional atomic owner-scoped batch operation may implement the same rules and return
   per-item outcomes plus one inventory revision. Capability absence leaves baseline CRUD.

Typed outcomes include stale executive/session/target/image/attachment/resource generation,
revision conflict, ownership conflict/lost, observer read-only, unsupported spec/policy,
capacity exhausted, resource shared, already released/tombstoned, operation outcome unknown
and tombstone evicted.

### Sharing, collisions and effective bindings

Equal concrete location does not imply equal identity or shared ownership.

- Distinct resource records may coexist at one address with different owners, purpose,
  condition, action or lifetime.
- Identical records may share a physical implementation slot, but each public `ResourceRef`
  remains observable and independently releasable unless owners explicitly chose one shared
  public record.
- Runtime limits report logical-record capacity separately from physical-slot capacity.
- Create failure due to slot/collision policy is typed and leaves the prior inventory
  unchanged.
- A breakpoint stop contains every matching `ResourceRef`, current resource revision,
  provenance/purpose and the `effective_binding_revision` that was evaluated.
- Conditions are evaluated independently. The runtime reports which matches requested stop,
  log, count or another supported action. One primary stop cause may contain several matching
  resource contributions.
- Removing, disabling or changing one record must not create a gap in another record's
  effectiveness, even if the target privately reprograms a shared slot.

This lets the Debugger show several logical/user/internal/external matches while the
Executive remains free to optimize physical resources.

### Resource lifecycle event evidence

This Study adopts the `HSX-ST-005` stream terms:

- `EventStreamRef { ExecutiveRef, stream_id, stream_generation }`;
- `EventCursor { stream, position, selection_digest }`;
- `SubscriptionRef` and `EventEnvelope { cursor_before, cursor_after, event_seq, event_type,
  target?, causal_ref?, state_revision?, resource_revision?, data }`;
- `CheckpointEnvelope` and `GapEnvelope { first/last_unavailable,
  retained/committed_watermarks, cause, recovery }`.

The stream cursor proves ordered delivery, not the semantic truth of a resource record.
Resource lifecycle and live-watch observation are different event classes.

```text
ResourceChangeEvidence {
  stream: EventStreamRef
  cursor_before: EventCursor
  cursor_after: EventCursor
  event_seq
  target: TargetRef
  loaded_image: LoadedImageRef
  resource: ResourceRef
  change_kind: created | updated | claim_added | claim_released |
               orphaned | degraded | reactivated | tombstoned
  before_resource_revision: UInt64?
  after_resource_revision: UInt64
  owner_set_revision: UInt64
  effective_binding_revision: UInt64
  resource_inventory_revision: UInt64
  operation_id: OpaqueId128?
  provenance_summary: ...
  tombstone_reason: ...?
}
```

The event is the same authoritative commit evidence returned by the corresponding command,
not a second mutation. It is deduplicated by stream cursor/event and commit identities. ACK
advances only after the controller applies or explicitly classifies the resource revision.

Any authoritative gap, `seq_evicted` or stream replacement suspends resource-event truth.
Recovery verifies Executive, target/image and owner-lease continuity, then performs a
non-destructive full resource reconcile. The reconcile pairs a baseline `EventCursor` with an
authoritative inventory revision/snapshot, either as one atomic bundle or with subscribe-first
revision fencing, then applies only later revisions before declaring Healthy. If the profile
cannot provide either, reconciliation remains degraded. Time, polling interval or equal list
content does not prove continuity.

Resource-event capability does not forbid an explicit low-rate audit, but healthy event-capable
operation cannot use periodic polling as the primary ownership truth.

### Breakpoint-hit and exact-step evidence

Breakpoint hit evidence composes this Study with `HSX-ST-004`:

```text
BreakpointMatchEvidence {
  target/image generations
  stop_token and execution/inspection revisions
  typed_pc
  matched_resources[]: {
    ResourceRef, resource_revision, effective_binding_revision,
    owner/provenance/purpose summary, condition/action outcome
  }
  primary_stop_cause
  secondary_contributions[]
}
```

An origin-breakpoint bypass is bound to the exact stop token, typed PC, operation and
effective binding revision. It bypasses the already-observed gate once; it never clears,
disables, changes owner claims or hides a guest BRK. If the matching resource set changes,
the stale revision rejects the bypass.

Temporary source-step conditions are ordinary owner-scoped remote resources with
`purpose=step_internal`, exact plan/operation/stop-token lifetime and conditional cleanup.
They cannot clear, overwrite, adopt or relabel a user/system/external breakpoint. If an
independent breakpoint matches a step condition, the independent cause remains visible and
preempts normal step completion according to `HSX-ST-004/DBG-D-006`.

### Persistent live-watch observation evidence

A live-watch record has configuration/resource revisions plus a separate observation stream:

```text
LiveWatchObservation {
  ResourceRef
  resource_revision
  observation_revision
  target/image generations
  trigger execution_transition_revision and inspection_revision?
  typed location and declared value encoding
  previous/current value or explicit unavailable status
  sample coherence: atomic | revision_pinned | best_effort
  EventCursor before/after
}
```

Rules:

1. Observation revisions are monotonic within one resource generation. Missing event ranges
   mean intermediate changes may be lost; the runtime must not synthesize complete history.
2. The observation reports its coherence/trigger. A sequential live read is not silently
   called an atomic task snapshot.
3. Location invalidation, out-of-scope locals, image change, read fault and unsupported value
   encoding yield explicit unavailable/degraded lifecycle or observation evidence.
4. Listing a live watch returns current resource state and, if advertised, the latest
   observation plus its revision. It does not transfer ownership.
5. Snapshot Watch expressions use the stop/snapshot inspection contract and produce no
   `LiveWatchObservation` resource lifecycle.

### Tombstones

A tombstone retains enough final evidence to reject stale operations and reconcile loss:

```text
ResourceTombstone {
  ref: ResourceRef
  final_resource_revision: UInt64
  final_owner_set_revision: UInt64
  final_effective_binding_revision: UInt64
  tombstoned_inventory_revision: UInt64
  reason: owner_released | lease_expired | explicit_delete |
          image_replaced | target_terminated | capacity_policy | other
  operation/owner/transition evidence
  retention/eviction metadata
}
```

The identity is never reused. Query/mutation by the old ref returns the tombstone while
retained. After negotiated eviction it returns `tombstone_evicted`/unknown with current target
and inventory evidence, never a newly created resource. Retention bounds are capability/limit
metadata and later resource-budget design; they cannot be undocumented implementation
accidents.

### Reconnect, resumption and adoption

Reconnection follows the `HSX-ST-002` continuity classes:

| Outcome | Resource action |
|---|---|
| Exact session/attachment/owner lease resumed and target/image retained | Reconcile inventory/events by revisions; retain claims; do not recreate blindly |
| New session, old owner lease still active/orphaned | Observe only until explicit authorized adoption/resumption; no PID/name match claim |
| Ownership lost but target/image retained | Preserve actual resources as external to the new owner; optionally request explicit adoption |
| Target/image generation changed or PID reused | All old refs are stale; re-resolve Debugger logical desires against the new image before any new create |
| Executive incarnation changed | Old refs, inventory revisions and watch IDs are invalid; perform full capability/identity negotiation and non-destructive refresh |
| Event continuity gapped | Resource truth unknown until inventory snapshot plus stream reconciliation succeeds |
| Continuity unknown | No mutation, adoption, replay of non-idempotent operations or destructive cleanup |

Explicit adoption is a separate mutation, never an inference. It requires exact
Executive/target/image/resource identity and current revisions, an active authorized
attachment/control lease, adoptable policy, an adoption credential/prior-owner resumption
proof or separately negotiated administration, expected owner-set revision, and an idempotent
operation ID. It records provenance history and event evidence.

Unauthorized, already-owned, policy-forbidden, stale and conflicting adoption fail without
side effects. Matching address, expression, client label, prior DAP ID or integer watch ID is
never sufficient proof.

Ambiguous create/update/release outcomes are reconciled by operation/idempotency query and
inventory revisions. Blind replay is permitted only for operations declared idempotent under
the exact generations.

## Capabilities, versioning and limits

Capability names below are synthesis candidates, not claims that the current protocol
implements them:

| Capability/profile | Minimum semantics |
|---|---|
| `debug.resources/1` | Full `ResourceRef`, target/image binding, provenance, owner claims, resource/inventory revisions, CAS CRUD and typed stale/conflict outcomes |
| `hsx.debug-resource.events` | Revisioned lifecycle events using `HSX-ST-005` cursor/gap/ACK semantics |
| `hsx.reconcile-baseline` | Authoritative resource snapshot/revision paired atomically or by subscribe-first fencing with a baseline `EventCursor` |
| `debug.resource-sharing/1` | Multiple same-location records/owners, non-destructive release and all-match stop evidence |
| `debug.resource-adoption/1` | Policy/authority/proof-based conditional adoption with provenance history |
| `debug.resource-batch/1` | Optional atomic owner-scoped batch mutations at expected inventory revision |
| `debug.execute-breakpoint/1` | Typed code-space breakpoint specs, effective-binding revision and match evidence |
| `debug.live-watch/1` | Explicit persistent resource, typed location/sampling/coherence, observation revision and events |
| `portable-debug/full-v1` | Requires stable identities/lifecycle, typed addresses, execution evidence, `hsx.event-stream.core`, `hsx.event-stream.health`, and `debug.resources/1`; resume and live-watch remain explicit capabilities |
| `python-legacy-debug-resources/v1` | Address-set breakpoints and integer-ID watches only; no stable provenance/revision/generation; conservative non-destructive behavior described below |

`HSX-ST-005` additionally proposes `hsx.event-stream.resume`; it is required only when a
profile promises resume rather than full reconcile after loss. Capabilities and maximums are
immutable within one negotiated session/profile generation. Material change fences that
generation.

Negotiated limits include:

- logical resources and physical slots by kind;
- owners/claims per resource;
- inventory page/snapshot lifetime;
- tombstone count/retention;
- condition/action/value schema versions;
- live-watch byte size, sample trigger/rate and observation retention;
- batch size and idempotency/operation retention;
- resource event availability and supported lifecycle policies.

Absence is `unsupported`, not an invitation to probe by mutation or guess version from
protocol number. Resource schema, event schema, condition/action schema and live-watch value
schema evolve independently and name mandatory/optional fields.

## Explicit legacy degraded behavior

The present Python profile exposes address-only breakpoints, PID/global integer-ID live
watches, session locks and a coarse `watch` feature. It cannot truthfully satisfy full remote
ownership/revision contracts.

### Address-only breakpoint rules

- Treat every listed address as `external_unknown` unless this controller has an uninterrupted
  same-target/image/attachment creation witness from the current connection generation.
- Adding a desired address may be used as an idempotent effectiveness request, but it does not
  prove exclusive ownership when an identical address already existed.
- Never adopt because an address appears in a list or event.
- Never delete an address that was pre-existing, collided with external state, survived a
  reconnect/gap, or lacks an uninterrupted exclusive creation witness.
- After continuity loss, all observed addresses become external/unknown and are preserved.
- Same-address owner cleanup may intentionally leave the effective address installed; report
  `degraded_not_converged` rather than claim successful deletion.
- Target-wide `clear all` is an explicit administrative/destructive action, not DAP
  replacement-set cleanup.
- Polling may display best-effort external changes but is not resource event continuity.

Even an uninterrupted creation witness is weaker than provenance. It is usable only under a
continuously held exclusive current attachment, known target/image identity supplied by a
higher compatibility layer, no event/transport uncertainty, and documented exit criteria.

### Integer-ID live-watch rules

- An integer ID is valid only within the current known Executive process/target observation;
  no owner, generation or image continuity is inferred.
- Listing/event observation never creates ownership.
- A client may remove only an ID returned by its own successful create in the uninterrupted
  current exclusive session, and only while the real protocol field mapping is verified.
- After reconnect, event gap, Executive uncertainty, image change or target uncertainty,
  automatic adoption/removal/restoration is unsafe. Preserve old records as unknown.
- Do not recreate persistent watches automatically by expression: identical expressions are
  not identity and current recreation produces duplicates.
- If safe cleanup/adoption cannot be proven, persistent live watch becomes unavailable or
  requires explicit user-authorized leak/duplicate behavior. Normal snapshot Watch remains
  available through coherent or labeled best-effort inspection.
- The current `watch` feature flag is insufficient for full capability; adapters advertise
  the named legacy profile and surface its cleanup/history limitations.

### Removal criteria for the legacy profile

The compatibility profile is removable only when the supported Executive baseline provides
stable target/image/resource identity, enforced observer/control authority, owner provenance,
CAS revisions, lifecycle events/inventory reconciliation, safe cleanup/tombstones and
explicit live-watch capability. Tests must prove same-location multi-owner, reconnect, PID
reuse, image replacement and gap behavior before the compatibility path is retired.

## Conformance-fixture plan

Fixtures should be transport-neutral and reusable by the Python oracle, future native
runtimes, Executive protocol, Debugger gateway/reconciler and release tests.

### Identity, binding and stale-reference fixtures

1. Create breakpoint and live watch on target A/image generation A; echo exact references on
   list/get/events.
2. Replace image at the same PID/address and reject every old resource get/update/release/hit
   reference as stale.
3. Terminate A, reuse its numeric PID for B, and reject A's delayed resource operation.
4. Restart Executive so IDs/revisions can numerically repeat internally; new Executive ref
   prevents aliasing.
5. Round-trip maximum generations/revisions through Python and JavaScript-safe JSON strings;
   reject lossy numbers and truncated IDs.
6. Present equal numeric offsets in code/data spaces and prove breakpoint/watch specs cannot
   cross-cast.

### CRUD, revision and ambiguous-result fixtures

7. Create with operation/idempotency ID, lose response, repeat identical request and return
   one resource; different payload under the same key conflicts.
8. Two clients update at one expected revision; exactly one commits, the other receives the
   current revisions with no side effect.
9. Owner release races specification update and target termination; authoritative ordering
   produces one final record/tombstone and monotonic inventory revisions.
10. Paginate a changing inventory and prove pages remain pinned to one snapshot/revision or
    fail stale; no torn union.
11. Inject logical/physical capacity exhaustion; failed create leaves no partial owner claim,
    slot or inventory revision unless a failure record is explicitly designed.
12. Exercise optional atomic batch success and per-item/precondition failure with no hidden
    partial convergence.

### Ownership, sharing, cleanup and adoption fixtures

13. DAP and CLI owners create distinct breakpoints at the same address. Hit evidence names
    both; releasing one preserves the other and physical effectiveness.
14. Two owners explicitly share an identical resource. One disconnects/expires; the survivor
    and its owner claim remain.
15. One owner attempts to update a shared spec incompatibly; operation fails or forks a new
    resource according to declared policy, never mutating the other owner silently.
16. Observer and sessionless clients cannot create/update/release/adopt even when no exclusive
    owner currently exists.
17. Attachment-ephemeral, owner-ephemeral, persistent-adoptable, system and external-unknown
    policies each perform their declared close/timeout/target-exit behavior.
18. New session with matching client name/PID/address cannot adopt. Exact proof plus expected
    owner-set revision succeeds once and records provenance; stale/unauthorized adoption fails.
19. Ordinary cleanup preserves external/unknown and shared same-address resources. Explicit
    administrative clear is separately authorized/audited.
20. Target termination emits/tombstones all resources; query returns final evidence until
    retention eviction, then typed tombstone-evicted rather than ID reuse.

### Event, gap and reconciliation fixtures

21. Command result and resource event carry the same commit identity and are deduplicated
    without suppressing a later equal-address event.
22. Deliver duplicate/out-of-order events; apply by stream cursor/revisions, ACK only after
    reducer application.
23. Drop a resource lifecycle interval; `GapEnvelope` marks actual state unknown, an
    inventory snapshot at a fenced baseline cursor restores it, and no destructive mutation
    occurs before the barrier.
24. Change target/image/owner lease while disconnected; reconnect classifies retained,
    restarted, PID-reused, ownership-lost or unknown before resource reconciliation.
25. Event stream retained but one operation response lost; idempotency query plus
    event/inventory evidence resolves applied versus not applied.
26. Resource event capability absent: named degraded polling reports best-effort observations
    and never claims gap-free ownership truth.

### Breakpoint, stepping and collision fixtures

27. Source/function/instruction logical intents resolve to zero/one/many remote resources
    without making the logical ID a remote ID.
28. User, external and step-internal resources share the origin address. Hit evidence lists
    all matching refs/purposes; user/external cause is not relabeled as step completion.
29. One-shot bypass carries the exact effective-binding revision, performs no resource
    mutation, is consumed once, and rejects a changed matching set.
30. Runtime-private physical coalescing/reprogramming produces no effectiveness gap when one
    public record is released.
31. Different conditions/actions at one address remain independently evaluated; unsupported
    condition/action fails closed.
32. Breakpoint at an equal numeric data-space offset cannot match code execution.

### Live-watch and snapshot-expression fixtures

33. Standard DAP Watch/hover/evaluate at repeated stops creates zero remote resources.
34. Explicit live-watch creation emits configuration lifecycle separately from sample/value
    observations and preserves monotonic observation revision.
35. Multiple live-watch owners at the same location release independently; an external
    observation never changes ownership.
36. Lose observation events; latest value may reconcile but missing history remains declared
    missing, not synthesized.
37. Image/location invalidation, out-of-scope local, read fault and unsupported value encoding
    produce explicit degraded/unavailable evidence.
38. Atomic, revision-pinned and best-effort samples are labeled accurately and correlate to
    execution/inspection revision where available.
39. Reconnect with retained owner lease reuses exact resource; new/unknown continuity does not
    add a duplicate by expression.
40. Task termination cleans/tombstones watches and stops sampling without a post-terminal
    event attributed to a reused PID.

### Legacy compatibility fixtures

41. Preserve current Python set/list/clear and watch add/change/list/remove/task-kill happy
    paths as regression oracles.
42. Address already exists before local desire; local owner removal leaves it installed and
    reports degraded non-convergence.
43. External address appears at the same local address; polling cannot transfer ownership.
44. Reconnect/PID reuse/image change makes creation witnesses invalid and suppresses automatic
    destructive cleanup.
45. Identical live-watch expressions return distinct IDs; legacy adapter neither guesses
    equality nor restores automatically after uncertainty.
46. Real `id`/`watch_id` client-server schema fixture prevents mock-only success and proves
    actual create/list/remove behavior for the named supported legacy profile.

## Traceability and consumer mapping

### `DBG-ST-006`

This Study directly answers portable question 9: stable breakpoint/live-watch remote identity,
owner/provenance, resource revisions and conditional update support. It also contributes to:

- question 1 through exact Executive/target/PID/image/resource generations from
  `HSX-ST-002`;
- question 2 by requiring `HSX-ST-003` typed code/data locations and checked ranges;
- questions 3/5/7 through match/resource revisions and one-shot bypass composition with
  `HSX-ST-004` execution/stop/snapshot evidence;
- question 4 through `HSX-ST-005` cursor/gap/ACK/inventory reconciliation;
- question 8 through attachment/control-lease cleanup, reconnect and explicit adoption from
  `HSX-ST-002`.

### Proposed Debugger contracts

| Consumer | Portable input supplied by this Study | Debugger-owned remainder |
|---|---|---|
| `DBG-D-002` | Resource event/inventory revision evidence, continuity/gap recovery inputs and named degraded profile | Gateway transport, health and reconciliation orchestration |
| `DBG-D-003` | Resource references bound to exact target/image generations and stale invalidation | Debugger stop epoch/reference lifetime |
| `DBG-D-004` | Concrete typed location and live-watch result status must use image/address/snapshot inputs | Artifact/source resolution and snapshot expression evaluation |
| `DBG-D-005` | `ResourceRef`, stable owner/provenance, lifetime, CAS revisions, sharing, cleanup, tombstones, reconnect/adoption and degraded rules | `LogicalResourceId`, owner desired sets, source/function resolution, bounded reconciler and UI status |
| `DBG-D-006` | All-match breakpoint evidence, effective-binding revision, safe step-internal resource and mutation-free one-shot bypass | Source into/over/out planning, budgets, cancellation and final plan result |

### Sibling HSX Studies

| Study | Required relation |
|---|---|
| `HSX-ST-002` | Supplies Executive/Session/Target/PID/Image/Attachment identity, stable `OwnerId` separation, lifecycle ownership, resumption/orphan policy and stale-generation rules. This Study does not redefine them. |
| `HSX-ST-003` | Supplies typed code/data/register locations, checked range arithmetic and exact image/debug-bundle binding for every concrete spec. |
| `HSX-ST-004` | Supplies stop/inspection/operation tokens, execution/inspection revisions, exact-step outcome, breakpoint precedence and origin-bypass semantics. This Study supplies resource/effective-binding inputs. |
| `HSX-ST-005` | Supplies `EventStreamRef`, `EventCursor`, subscription/checkpoint/gap/ACK/resume/profile rules. This Study requires resource inventory snapshots to expose a fenced baseline in that model. |
| `HSX-ST-001` | Preserves legacy provenance and coordinates Master synthesis/stable ID allocation. |

## Open synthesis questions

1. Is `debug.resources/1` mandatory in the initial full portable profile, or may an
   eventless-but-revisioned CRUD profile be called full for owner-safe reconciliation? This
   Study recommends lifecycle events for healthy operation and allows explicit bounded audit.
2. Which lifetime policy is the default for user breakpoints and explicit live watches?
   Defaults are product/Steering decisions; wire records must remain explicit.
3. Should identical same-owner specifications create separate public records or return a
   caller-selected deduplicated/shared record? The operation must be explicit either way.
4. Which breakpoint conditions/actions and live-watch location/value recipes enter the first
   version? Unsupported semantics must fail; no product code may guess.
5. What minimum tombstone and idempotency-operation retention is portable, and which bounds
   are profile/target resource limits? AVR sizing remains AVR-owned.
6. Must inventory snapshot and event cursor be produced atomically in the initial stream
   profile, or can a bounded subscribe/query/verify barrier satisfy it? Master synthesis must
   use the final `HSX-ST-005` terms.
7. Does a persistent-adoptable resource require cryptographic adoption capability, a retained
   owner lease secret, administrative authority, or multiple supported policies? Matching
   labels are prohibited in all cases.
8. Which live-watch trigger/coherence modes are portable: after each committed instruction,
   transition-boundary, periodic runtime time, hardware watchpoint, or explicit sample? Each
   has different history and performance semantics.
9. Can target-private physical slot sharing always preserve independent public resource
   semantics, or must some constrained profiles reject same-location condition combinations?
   Rejection must be typed and atomic.
10. Which resource events and tombstones are included in a retained final target snapshot
    versus separate Executive inventory evidence? `HSX-ST-004` excludes resources unless
    snapshot coverage names them.
11. How will authentication/principal identity back `OwnerId` and adoption outside the current
    trusted lab network? Authorization is required semantically; concrete security design may
    require a later first-class Study.
12. Master synthesis must align final DTO spelling, capability dependencies and
    inventory/event linearization with completed `HSX-ST-002..005` before review.

Unresolved questions become explicit proposed-design choices or additional first-class
Studies. None may be left for a product worker to decide implicitly.

## Conclusions and recommendations for Master synthesis

1. PID/address and PID/integer-watch-ID are useful Python regression shapes but cannot be
   portable resource identity.
2. Adopt an opaque, non-recycled `ResourceRef` bound to exact Executive, target, loaded-image
   and resource generations. Use typed code/data/register locations without masks.
3. Keep stable `OwnerId`, session, attachment/control lease and resource owner lease distinct.
   Owner labels do not grant mutation authority.
4. Record Executive-authored provenance, explicit purpose and lifetime policy. Observation
   never becomes ownership.
5. Require resource-local, owner-set, effective-binding and target-inventory revisions with
   CAS mutation and idempotent ambiguous-result recovery. Live-watch observations use a
   separate monotonic revision.
6. Preserve distinct same-location resources/owners and report all matches. Runtime-private
   physical coalescing must not leak destructive semantics.
7. Release only the proven owner's claim; delete only when policy/authority/revisions permit.
   Preserve shared, system and external/unknown resources. Retain bounded tombstones and never
   reuse identity.
8. Bind lifecycle events to the `HSX-ST-005` stream/cursor model and provide a fenced
   inventory baseline for gap recovery. Poll-only behavior is explicitly degraded.
9. Resume claims only with exact continuity proof. A new session may observe or explicitly
   adopt under policy/authority/CAS; matching PID/address/expression/client name is never
   proof.
10. Keep snapshot Watch expressions in Debugger inspection. Persistent live watch is an
    explicit optional HSX resource with owner, lifetime, configuration and observation
    evidence.
11. Bind exact-step bypass and internal conditions to resource/effective-binding revisions;
    never clear shared breakpoints to step.
12. Preserve current Python paths only under `python-legacy-debug-resources/v1`, with
    non-destructive cleanup, invalidated creation witnesses after uncertainty, no automatic
    watch adoption/restoration and visible degraded non-convergence.

## Completion limit

This Study is **COMPLETE FOR MASTER SYNTHESIS**. It provides evidence, alternatives,
descriptive contract recommendations, degraded rules and conformance fixtures. It allocates no
numeric HSX Requirement/Architecture/Design IDs and does not make the proposed contracts
accepted authority.

No `DBG-D-*` is frozen. No Debugger Refactor, product/runtime/native implementation, packaging
change or AVR work is authorized by this Study.
