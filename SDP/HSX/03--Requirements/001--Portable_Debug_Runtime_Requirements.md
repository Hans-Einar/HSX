# Portable Debug Runtime Requirements

- Status: REWORKED PROPOSAL / PENDING FRESH INDEPENDENT REVIEW
- Range: `HSX-R-001..HSX-R-036`
- Studies: `HSX-ST-001..HSX-ST-006`
- Debugger dependency: `DBG-ST-006`
- State: target; not implemented

These stable IDs are permanent traceability handles. The requirements remain proposed until
Steering accepts them in issues #47/#38. They authorize no product or AVR work.

## Identity, generations, lifecycle, and authority

- **HSX-R-001 — Executive incarnation identity.** Every executive process incarnation SHALL
  expose an opaque `ExecutiveInstanceRef` that changes on restart and is never inferred from
  endpoint, boot time, or protocol version.
- **HSX-R-002 — Event stream identity.** Every event stream SHALL expose an `EventStreamRef`
  bound to one executive incarnation and stream generation; sequence values are meaningful
  only inside that reference.
- **HSX-R-003 — Stable target identity.** Runtime targets SHALL expose an opaque `TargetId`
  plus `TargetGeneration`; PID remains display/scheduling data with an explicit
  `PidGeneration` and SHALL NOT prove continuity.
- **HSX-R-004 — Loaded image identity.** Every accepted load SHALL expose a target-bound
  `LoadedImageRef` containing opaque never-reused `LoadedImageId`, exact `TargetRef`, artifact
  content/schema identity and `ImageGeneration`. Two loads of identical bytes on different
  targets or different load operations SHALL have distinct LoadedImageIds; CRC, path, app name,
  digest alone and display PID are not substitutes for loaded-instance identity.
- **HSX-R-005 — Session and attachment identity.** Sessions and target attachments SHALL have
  stable refs/generations, explicit exclusive/observer modes, owner identity, lease/revision,
  expiry and reconnect fencing.
- **HSX-R-006 — Expected-generation mutation.** Target-mutating lifecycle requests SHALL carry
  expected identity/generation/revision preconditions and fail stale rather than rebind.
- **HSX-R-007 — Atomic create/load/start/claim.** A true launch capability SHALL atomically
  establish target/image identity, accepted image evidence, initial state and ownership; a
  non-atomic legacy load SHALL advertise a degraded profile.
- **HSX-R-008 — Enforced observer authority.** Observer/read-only versus mutator authority
  SHALL be enforced by the Executive for every operation, including currently unlocked PIDs
  and global control commands.
- **HSX-R-009 — Explicit detach/disconnect policy.** Detach, release and disconnect SHALL take
  explicit preserve/resume/terminate/orphan policy inputs and return authoritative outcomes;
  portable semantics SHALL NOT hide a product default.
- **HSX-R-010 — Termination evidence and tombstones.** Kill/terminate SHALL succeed only on
  authoritative removal evidence and SHALL retain a non-reusable target tombstone sufficient
  to reject stale references.
- **HSX-R-011 — Reconnect continuity outcome.** Reconnect SHALL return explicit retained,
  replaced, lost, ownership-lost, capability-changed or unrecoverable outcomes after identity
  and lease reconciliation; socket/session reopen alone is insufficient.

## Address spaces, artifact binding, ABI, unwind, and locations

- **HSX-R-012 — Architecture descriptor.** Every target/image SHALL expose a versioned
  `ArchitectureDescriptor` naming code, data and register spaces, units, widths, legal ranges,
  instruction alignment and register widths.
- **HSX-R-013 — Serialization and alignment.** The descriptor SHALL define byte order and
  alignment separately for container/header, instruction/code, guest data, registers and
  stack, including whether unaligned access succeeds or faults.
- **HSX-R-014 — Checked typed addresses.** APIs SHALL use typed address/range values and
  checked conversions; implicit masking, wrap, truncation or cross-space comparison is
  forbidden outside a named degraded profile.
- **HSX-R-015 — Image/debug bundle binding.** Debug metadata and sources SHALL be bound to an
  exact `LoadedImageRef` through schema/version and content digest evidence; mismatches fail
  closed.
- **HSX-R-016 — ABI descriptor.** Each executable profile SHALL expose an `AbiDescriptor`
  covering argument/return registers, saved sets, SP/FP/LR roles, stack growth/alignment,
  frame/call/return layout and call-site PC interpretation.
- **HSX-R-017 — Versioned unwind recipes.** Stack reconstruction SHALL consume versioned,
  bounded unwind recipes and report complete, partial, unavailable, corrupt or stale results;
  R7 or any fixed frame chain is profile evidence, not a universal debugger rule.
- **HSX-R-018 — Variable-location recipes.** Debug locations SHALL be versioned, image-bound
  and PC-ranged across register/stack/global/constant/optimized-out/unavailable forms with
  explicit type/width/endian/address-space semantics.

## Run/stop evidence, snapshots, exact stepping, and blocked states

- **HSX-R-019 — Ordered transition evidence.** Every authoritative runtime transition SHALL
  carry `TargetRef`, monotonic transition revision, prior/new state, cause, command/operation
  correlation where applicable, and ordered terminal/fault details.
- **HSX-R-020 — Stable stop evidence.** An inspection-stable stop SHALL carry `StopToken`,
  target/image generations, transition revision, PC/address space and causal resource/step
  evidence. Command acceptance alone never proves a stop or running state.
- **HSX-R-021 — Terminal and fault ordering.** Fault, breakpoint, explicit pause, block,
  return, kill and termination evidence SHALL have deterministic causal precedence and SHALL
  not be deduplicated by timing heuristics.
- **HSX-R-022 — Inspection snapshot reference.** Coherent inspection SHALL use an immutable
  `InspectionSnapshotRef` or revision-pinned read set bound to target/image/transition and
  inspection revision.
- **HSX-R-023 — Stale inspection rejection.** Resume, mutation, wake, target/image generation
  change or invalidated revision SHALL make affected reads/handles fail stale; data from
  different revisions SHALL NOT be presented as one snapshot.
- **HSX-R-024 — Blocked-state inspection capability.** WAIT_MBX, SLEEPING and other blocked
  states are inspection-stable only when a named capability supplies frozen snapshot/revision
  evidence; otherwise they are runtime-state notifications only.
- **HSX-R-025 — Exact instruction-step outcome.** Exact step SHALL return authoritative
  accepted/completed evidence with `retired_count` in `{0,1}`, origin/final PC, target/image
  refs, revisions, cause and terminal/preempting condition.
- **HSX-R-026 — One-shot breakpoint bypass.** Origin-breakpoint bypass SHALL be scoped to one
  operation, target generation, stop token, PC and resource/effective-binding revision; it
  SHALL never delete or disable unrelated/shared breakpoints.
- **HSX-R-027 — Source-step prerequisites.** HSX SHALL expose the portable instruction,
  transition, snapshot, unwind and resource evidence required by Debugger source-step plans;
  source into/over/out algorithms remain Debugger-owned.

## Event stream continuity and capability profiles

- **HSX-R-028 — Scoped event cursor.** `EventCursor` SHALL include `EventStreamRef`, canonical
  unsigned sequence and selection/filter identity; cursors from another generation or
  selection fail explicitly.
- **HSX-R-029 — Atomic canonical publish order.** Sequence allocation, canonical event commit,
  retention and subscriber visibility SHALL form one total-order operation; delivery/checkpoint
  envelopes cannot create independent truth.
- **HSX-R-030 — Typed resume and gap outcomes.** Subscribe/resume SHALL return contiguous
  replay or typed `seq_evicted`, `cursor_ahead`, `stream_replaced`, `selection_changed` or
  explicit gap/drop evidence with the missing interval and required reconciliation baseline.
- **HSX-R-031 — ACK after application.** ACK SHALL advance only through events successfully
  applied/classified by the serialized consumer, SHALL reject future/undelivered/gapped values,
  and SHALL never be fabricated by queue overflow.
- **HSX-R-032 — Back-pressure isolation.** Bounded subscriber overflow SHALL preserve canonical
  history, identify exact lost delivery intervals and affected selection, and avoid silently
  displacing another event or mutating ACK state.
- **HSX-R-033 — Event health and profiles.** The runtime SHALL advertise explicit current and
  named degraded event profiles, checkpoints/health evidence, resume capability and removal
  criteria. Broad `events` or version guessing is not sufficient capability negotiation.

## Debug resource identity, provenance, revisions, and legacy limits

- **HSX-R-034 — Remote resource identity and ownership.** Persistent breakpoint/live-watch
  resources SHALL expose stable `ResourceRef`, kind, target/image generation, Executive-authored
  provenance and explicit `OwnerClaim`/lease; observing a resource never creates ownership.
- **HSX-R-035 — Revisioned resource lifecycle.** Resource, owner, effective-binding and
  inventory revisions SHALL support conditional mutation, same-location sharing/collision,
  owner-scoped release, tombstones, reconnect/adoption evidence and ordered lifecycle events.
- **HSX-R-036 — Resource profiles and Watch boundary.** Persistent live-watch semantics SHALL
  be separate from Debugger snapshot Watch expressions. Address/ID-only legacy profiles SHALL
  advertise conservative no-adoption/no-unowned-delete limits and evidence-based removal gates.

## Conformance requirement

Every requirement above SHALL have current-profile positive/negative fixtures and a declared
unsupported/degraded result. The Python oracle supplies evidence, but no fixture may normalize
away identity, generation, ordering, revision, stale outcome, provenance or causal reason.
