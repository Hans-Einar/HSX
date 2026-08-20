# Portable Debug Runtime Contracts

- Status: PROPOSED / PENDING INDEPENDENT REVIEW
- Range: `HSX-D-001..HSX-D-005`
- Architecture: `HSX-A-001..HSX-A-005`
- Requirements: `HSX-R-001..HSX-R-036`
- Debugger dependency: `DBG-ST-006`, `DBG-D-002..DBG-D-006`
- State: target; not implemented or frozen

These contracts define proposed portable wire/domain evidence. They remain non-authoritative
until Steering accepts them in #47/#38.

## HSX-D-001 — Runtime identity, lifecycle, and ownership

### Required references

| Type | Required fields/invariants |
|---|---|
| `ExecutiveInstanceRef` | Opaque instance UUID/digest; changes on process restart; equality only by exact value. |
| `EventStreamRef` | Executive instance + opaque stream ID + stream generation. |
| `SessionRef` | Executive instance + session ID + session generation + negotiated profile. |
| `TargetRef` | Executive instance + opaque target ID + target generation + display PID + PID generation. |
| `ImageRef` | Content digest + image schema/profile + image/load generation + optional accepted artifact-bundle digest. |
| `AttachmentLease` | Lease ID/revision, session/owner, TargetRef, exclusive/observer mode, expiry/grace and orphan policy. |
| `LifecycleReceipt` | Operation ID, expected refs/revisions, accepted/rejected status and no implied target transition. |
| `LifecycleCommit` | Operation ID, before/after refs, authoritative outcome/revisions and tombstone where terminal. |

### Generation rules

- Executive restart creates a new `ExecutiveInstanceRef` and invalidates sessions, streams,
  leases, targets and resources from the old instance.
- Target creation allocates a never-reused `TargetId` and generation 1. PID reuse cannot reuse
  `TargetId`.
- Reset/reinitialize that preserves deliberate logical target identity increments
  `TargetGeneration` and invalidates stop/snapshot/resource bindings.
- Atomic `replace_image` may preserve `TargetId` only when explicitly supported; it increments
  target and image generations and commits only after the new image is accepted. Ordinary kill
  then load creates a new target.
- Termination retains a tombstone sufficient to reject stale operations; target IDs are never
  recycled.

### Lifecycle operations

- `create_load_start_claim(image, start_policy, owner, expected_instance)` is one atomic
  capability or is unavailable. Legacy auto-run load is a degraded operation, not true launch.
- `attach(target, mode, owner, expected_generation)` enforces exclusive/observer rights on the
  server for every mutation/read class.
- `detach/release/disconnect` require explicit policy inputs (`preserve`, `resume`,
  `terminate`, declared orphan/lease handling) and return a commit or rejection. Product
  defaults remain Debugger/Steering policy.
- `terminate/kill` completes only after terminal/removal evidence and tombstone publication.
- reconnect never silently adopts a PID. It proves exact target and lease continuity or returns
  replaced/lost/ownership-lost/capability-changed/unrecoverable.

### Capability and degraded behavior

Full capability: `hsx.runtime.identity-generations/1` plus
`hsx.lifecycle.authority-leases/1`. The `hsx.python-debug-legacy/1` profile exposes session UUID
and PID as display/degraded data, forbids continuity claims and requires conservative
reconciliation. Non-idempotent lifecycle operations are never blindly retried.

## HSX-D-002 — Architecture, ABI, debug bundle, unwind, and locations

### `ArchitectureDescriptor`

The descriptor contains version, instruction encoding, register width/count, and named spaces.
Each space specifies ID, unit (`byte` or other explicit unit), width, legal ranges, byte order,
alignment policy, wrap policy and permissions. Container/header and instruction serialization
are explicit and independent of guest data/register/stack byte order.

Typed values are `{space_id, unsigned_value}` and ranges are checked half-open intervals. No
API silently masks or wraps; overflow/cross-space operations return typed failure. The current
Python profile may describe 16-bit byte-addressed code/data and 32-bit GPRs, but masks are
legacy conversion evidence rather than the universal model.

### `ImageDebugBundle`

The bundle binds exact `ImageRef`, HXE schema/content digest, `.sym` schema/content digest,
sources manifest digest, architecture/ABI descriptor IDs and toolchain/debug schema versions.
Missing/mismatched content is explicit `unavailable`/`mismatch`; adjacent file paths or HXE CRC
alone do not establish binding.

### `AbiDescriptor` and recipes

The ABI descriptor specifies argument/return registers, caller/callee saved sets, SP/FP/LR
roles, stack growth/alignment, frame/call/return layout, overflow arguments and call-site PC
adjustment. Unwind uses bounded versioned recipes with termination/cycle/range/read-failure
rules and returns complete/partial/unavailable/corrupt/stale. The current R7 frame chain may be
one profile recipe only.

Variable locations are image/PC-ranged recipes for register, stack/frame offset, global typed
address, constant, composite/piece, optimized-out or unavailable. Reads preserve declared
width/endian/type and report partial/stale rather than padding/truncating silently.

### Capabilities

`hsx.architecture-descriptor/1`, `hsx.debug-image-bundle/1`, and versioned ABI/unwind/location
recipe capabilities are negotiated per image. Legacy symbols use checked adapters and cannot
claim portable unwind/location conformance.

## HSX-D-003 — Execution evidence, snapshots, exact step, and blocked states

### Evidence records

| Record | Purpose |
|---|---|
| `CommandReceipt` | Accept/reject request with operation ID and expected refs; never target-state proof. |
| `TransitionEvidence` | Target/image refs, monotonic transition revision, previous/new state, cause, operation correlation and structured details. |
| `StableStopEvidence` | StopToken, transition revision, PC/address, cause, resource/step evidence and inspection stability. |
| `InspectionSnapshotRef` | Target/image refs, transition + inspection revisions, snapshot token, supported read sets and stability grade. |
| `StepOutcome` | Operation/origin stop, retired_count 0/1, final transition/stop evidence, bypass evidence and preemption/terminal result. |

### Snapshot contract

Preferred full profile publishes an immutable snapshot covering registers/context plus a
revision-fenced view of memory, stack, disassembly and resources. A revision-pinned alternative
is conformant only if every read checks the same stable transition/inspection revision and
fails stale on mutation. Best-effort live reads are explicitly degraded and cannot back a
Debugger stop epoch.

Resume, wake, mutation, target/image generation change or invalidated revision makes reads
stale. Late responses cannot populate another snapshot.

### Exact step and precedence

Exact step retires zero or one guest instruction. Zero is valid only for preempting
breakpoint/BRK/fault/terminal conditions before retirement. One-shot origin breakpoint bypass
is fenced by TargetRef, origin StopToken, PC, operation ID and effective resource revision; it
does not remove shared resources.

Authoritative precedence is terminal/target-loss, fault, independent explicit pause,
independent user/external breakpoint, runtime block, requested step completion, then ordinary
running progress as applicable. Duplicate evidence uses identity/revision, not timing.

HSX exposes instruction retirement, transition/snapshot/unwind/resource primitives. Debugger
owns source into/over/out plan algorithms and internal resource orchestration.

### Blocked-state matrix

WAIT_MBX/SLEEPING are inspection-stable only under `hsx.blocked-snapshot/1`, which publishes a
frozen SnapshotRef and invalidates it atomically before wake/timeout/deadline mutation. Without
that capability, they are state events only and inspection is unavailable or best-effort
degraded.

## HSX-D-004 — Event stream continuity, ACK, gaps, health, and profiles

### Canonical records

- `EventStreamRef` scopes all sequence/cursor/checkpoint/gap records.
- Canonical sequence is unsigned and wire-safe; JSON representations avoid precision loss.
- `EventCursor` contains stream ref, selection/filter digest and last canonical applied seq.
- Canonical event commit allocates sequence, stores history and exposes subscriber visibility
  as one total-order operation.
- Delivery/checkpoint envelopes reference canonical sequence and cannot redefine domain truth.

### Subscription/resume

Subscribe declares selection and optional cursor. The server returns contiguous replay or a
typed `seq_evicted`, `cursor_ahead`, `stream_replaced`, `selection_changed`, unsupported or
gap outcome including retained bounds/missing interval and required reconciliation baseline.
Resume is permitted only on the exact stream generation and compatible selection.

### ACK and back-pressure

ACK advances only after serialized consumer application/classification, never merely callback
attempt. Future, undelivered, unselected or gapped sequences are rejected. Per-subscriber
overflow preserves canonical history and emits exact delivery gap intervals without fabricating
ACK or silently displacing another event.

### Health and reconciliation

Same-stream checkpoints/heartbeats distinguish healthy idle from half-open loss. EOF,
malformed input, ACK/keepalive failure, cursor gap and stream replacement are typed health
evidence. Contiguous resume replays; all other discontinuity requires an explicit state,
resource and event reconciliation baseline before health can be restored.

### Profiles

Full capabilities include `hsx.event-stream.core/1`, `hsx.event-stream.resume/1`,
`hsx.event-stream.health/1`, `hsx.runtime-state.events/1`,
`hsx.debug-resource.events/1`, and `hsx.reconcile-baseline/1`. Named degraded profiles include
live-nonresumable, `hsx.legacy-event-stream/1`, and legacy-poll with explicit removal evidence.
Broad `events` is not a portable profile.

## HSX-D-005 — Remote debug resource provenance and revisions

### Identity and ownership

`ResourceRef` contains ExecutiveInstanceRef, TargetRef, ImageRef where relevant, kind, opaque
resource ID and generation. `OwnerClaim` contains owner/session/lease/provenance, lifetime
policy and owner revision. Executive-authored provenance distinguishes client-created,
external, runtime/internal and legacy-unknown.

Debugger logical source/function/instruction breakpoint desires are outside this record;
resolved remote bindings point back to logical IDs only as provenance metadata. Standard
snapshot Watch expressions are not persistent resources. Persistent HSX live watches are an
explicit resource kind/capability.

### Revisions and sharing

Resource, owner-claim, effective-binding and inventory revisions are distinct monotonic CAS
preconditions. Same-address breakpoints remain separate logical remote resources or share an
effective binding with an explicit owner set; removal of one owner cannot remove surviving
claims. Ambiguous mutation fails and returns current revisions.

### Lifetime, events, tombstones, reconnect

Lifetime policy is owner-scoped session, lease, target, persistent or explicit. Session close
releases only session-scoped claims. Deletion publishes tombstone/revision and ordered resource
event. Reconnect resumes on exact target/stream/inventory continuity or reconciles from a
revisioned baseline. Adoption of external/unknown resources is explicit and authorized; mere
observation never adopts.

Breakpoint-hit and step-bypass evidence references ResourceRef/effective-binding revision so
shared breakpoints retain causal precedence. Live-watch observation references resource and
sample/transition revisions.

### Degraded profile

`hsx.legacy-debug-resources/1` covers address-set breakpoints and integer-ID watches. Unknown
resources are external, sharing/ownership cannot be proven, no unowned deletion/adoption is
allowed, reconnect is conservative, and the profile has executable removal gates.

## Cross-contract transaction rules

1. Every event/resource/snapshot/lifecycle operation is fenced by `HSX-D-001` identities.
2. Every address, image, unwind and location value consumes `HSX-D-002` descriptors.
3. `HSX-D-003` stop/snapshot revisions are the causal source for events/resources.
4. `HSX-D-004` carries continuity evidence but cannot redefine lifecycle/execution/resource
   domain semantics.
5. `HSX-D-005` effective-binding revisions fence bypass/step/resource evidence.

## Conformance fixture matrix

| Contract | Minimum fixture families |
|---|---|
| D-001 | restart/session/stream/target/PID reuse; atomic launch; failed replace; exclusive/observer; stale generation; detach/disconnect/orphan; kill/tombstone; reconnect retained/lost |
| D-002 | multiple address widths/spaces; endian/alignment; checked overflow; image/debug mismatch; current R7 recipe and alternative/unavailable unwind; ranged/optimized locations |
| D-003 | command receipt vs transition; pause/break/fault/terminal precedence; immutable/revision snapshots; stale reads; exact 0/1 step; fenced bypass; WAIT_MBX/SLEEPING capability |
| D-004 | stream replacement; filter-safe cursors; atomic ordering; future ACK rejection; seq eviction; queue gap intervals; malformed/half-open health; contiguous resume/full reconcile |
| D-005 | same-address multi-owner; owner release; external observation; CAS conflict; tombstones; reconnect/adoption; resource-event gap; live-watch sample revisions; legacy no-delete mode |

Fixtures SHALL run against the Python oracle and be reusable by future native implementations.
Expected current-profile, degraded-profile and unsupported outcomes are all explicit.

## Open Steering decisions

1. Portable contracts require explicit detach/disconnect/orphan policy inputs; product defaults
   remain to be selected by Debugger/Steering.
2. Same `TargetId` across image replacement is permitted only for atomic explicit
   `replace_image`; ordinary kill/load always creates a new target.
3. Current intended event/resource profile minimum and degraded-support lifetime require
   explicit release policy; no indefinite version-guessing compatibility.

No open decision changes the implementation guard on this proposal.
