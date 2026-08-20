# Portable Debug Runtime Contracts

- Status: REVIEW 005 REWORK CORRECTED — PENDING FRESH REVIEW 006
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
| `ArtifactRef` | `hsx.artifact-ref/1` + HXE media/container version + canonical byte length + SHA-256 of exact accepted HXE bytes; identical accepted bytes may share this value. |
| `LoadedImageRef` | Executive instance + exact TargetRef + opaque never-reused LoadedImageId + ImageGeneration + ArtifactRef. It contains no debug-bundle ref/digest. |
| `AttachmentLease` | Lease ID/revision, session/owner, TargetRef, exclusive/observer mode, expiry/grace and orphan policy. |
| `LifecycleReceipt` | Operation ID, expected refs/revisions, accepted/rejected status and no implied target transition. |
| `LifecycleCommit` | Operation ID, before/after refs, authoritative outcome/revisions and tombstone where terminal. |

### Generation rules

- Executive restart creates a new `ExecutiveInstanceRef` and invalidates sessions, streams,
  leases, targets and resources from the old instance.
- Target creation allocates a never-reused `TargetId` and generation 1. PID reuse cannot reuse
  `TargetId`.
- Every accepted load allocates a distinct opaque `LoadedImageId` scoped by ExecutiveInstance
  and TargetRef. Equal ArtifactRefs and equal generation numbers on different targets cannot
  alias because LoadedImageId and TargetRef remain distinct.
- Reset/reinitialize that preserves deliberate logical target identity increments
  `TargetGeneration` and invalidates stop/snapshot/resource bindings.
- Atomic `replace_image` may preserve `TargetId` only when explicitly supported; it increments
  target and image generations, allocates a new LoadedImageId, and commits only after the new
  image is accepted. Ordinary kill then load creates a new target.
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

### Non-recursive artifact/bundle/binding model

Construction is acyclic:

1. `ArtifactRef` is SHA-256 over exact accepted HXE bytes plus media/container schema/length.
2. `LoadedImageRef` identifies one target-bound accepted load and contains ArtifactRef only.
3. Reusable `ImageDebugBundleRef` is a domain-separated digest of canonical semantic debug
   components, SourceIdentityManifest and architecture/ABI/recipe refs; it contains ArtifactRef
   but no LoadedImageRef.
4. Immutable `ImageDebugBinding` combines exact LoadedImageRef, ImageDebugBundleRef and accepted
   descriptor refs. Its binding digest is over that binding payload and is not part of either
   input ref.

Canonical structured digests are `SHA-256(UTF8(domain_tag) || 0x00 || canonical_json)`.
The [canonical digest appendix](002--Canonical_Digest_Golden_Vectors.md) is normative: it fixes
literal domain-tag bytes, NFC/key/array ordering, minimal decimal-string encoding for every
integer-valued identity field, lowercase Hex64 only for digests, control-character rejection,
one quote/backslash escaping form, exact UTF-8 emission and golden source/component/bundle/
binding bytes and hashes. JSON numeric tokens, alternate escapes and ambiguous hex/decimal
integer choices are invalid. A record's own digest, signatures, timestamps and local locator
paths are excluded from its digest scope. Raw artifact/source/component byte digests cover
exact bytes without newline, encoding, compression or host-path normalization.

`ImageDebugBundleRef` includes canonical symbol model, unwind/location recipes, source identity
manifest and required capability/schema refs. Raw `.sym`/`sources.json` digests may remain
provenance but cannot replace canonical component identity. `ImageDebugBinding` validation
requires exact ArtifactRef and descriptor agreement; failures return typed artifact/bundle/
component/schema/binding mismatch and publish no accepted binding.

### Stable source identity

The bundle-internal `SourceIdentityRecord` contains an NFC artifact-relative logical ID,
SHA-256 exact source bytes and byte length. An external `SourceRef` adds the exact
`ImageDebugBundleRef`; this one-way construction avoids source/bundle recursion. `/` is the
separator; case is preserved; absolute/drive/UNC/empty/dot/dot-dot/backslash/NUL IDs are
invalid, as are all U+0000..U+001F/U+007F controls. Duplicate basenames and casefold
collisions remain distinct or typed ambiguous.
Prefix maps, search roots, symlinks and local overrides are resolver-only, excluded from
identity/digests, and candidate bytes must match SourceRef before use.

### `AbiDescriptor` and current profile

`hsx.abi-descriptor/1` supplies the envelope. The current narrow profile
`hsx.abi.llc-r7-word32/1` specifies: 32-bit slots/GPRs; args R1..R3; scalar return R0; only R7
callee-preserved; R0..R6/R8..R14 and flags caller-clobbered; PC/SP/PSW separate; R15 derived SP
mirror/reserved; 4-byte descending stack; caller overflow high-to-low; CALL pushes little-endian
resume PC; after `PUSH R7; MOV R7,R15`, `[FP]=old R7`, `[FP+4]=resume PC`, physical arg4 is
`[FP+8]`, and call-site PC is checked `resume_pc-4`.

The current compiled callee does not consume stack arguments; live-across-call saving beyond
R7, aggregates, multiword values/returns, varargs, dynamic/tail/inline frames are unsupported,
not implied by physical caller layout.

Conforming one-word f16 values use the low 16 bits and zero upper 16 bits. Current Python
`FADD`/`FSUB`/`FMUL`/`FDIV`/`I2F` preserve the destination's old upper half, and allocator
reuse can expose it across a call/return. Those paths are explicit
`hsx.python-debug-legacy/1` nonconformance and cannot advertise this ABI until the
zero-extension removal fixture passes.

| Value | Exact profile role |
|---|---|
| `R0` | one-word scalar result; caller-clobbered |
| `R1..R3` | first three one-word arguments; caller-clobbered |
| `R4..R6`, `R8..R14` | compiler/scratch values; caller-clobbered |
| `R7` | only callee-preserved GPR and conventional emitted frame pointer |
| `R15` | reserved derived mirror of authoritative SP; never independently writable |
| `PC`, `SP`, `PSW` | separate descriptor-governed architectural values |

The ABI slot and minimum stack/call alignment are 4 bytes. At callee entry, return PC is
`[SP]` and physical overflow argument 4 begins at `[SP+4]`; after the emitted prologue,
`[R7]` is caller R7, `[R7+4]` is resume PC and physical argument 4 is `[R7+8]`. Checked
`resume_pc-4` yields call-site PC only when it is aligned, in the same image and names a CALL.
SVC module/function register inputs, outputs and clobbers require separate exact signature
descriptors and are never inferred from this call ABI.

### Unwind/location recipe schemas

`hsx.unwind-recipe/1` and `hsx.location-recipe/1` are bounded typed declarative recipe schemas,
selected by exact ImageDebugBinding/ABI/scope/frame/PC ranges. Schema v1 uses canonical symbolic
postfix opcodes: `reg_value`, `special_value`, `const_u`, `const_s`, `static_address`,
`to_address`, `cfa`, `frame_base`, `add_sconst_checked`, `deref_u`, and `bit_slice`.
Non-expression terminals are `same`, `undefined`, `unavailable(reason)` and
`optimized_out(reason)`; piece composition is structural. Schema v1 has no loops, branches,
recursive recipe calls, host-endian reads, implicit casts, masks or wrapping.

| Negotiated bound for `hsx.abi.llc-r7-word32/1` | Limit |
|---|---:|
| opcodes / evaluator stack / dereferences per expression | 32 / 8 / 4 |
| bytes per dereference | 16 |
| unwind frames / total opcodes / total dereferenced bytes | 64 / 4096 / 1024 |
| location pieces / declared result bits / location dereferenced bytes | 16 / 4096 / 512 |

The selected compiler emits non-overlapping rows for entry before `PUSH R7`, after that push,
stable body/local release, after `POP R7` at `RET`, and terminal top-level entry/return. These
rows recover CFA, caller SP/PC/R7 from the exact snapshot and return resume PC separately from
checked call-site PC. Location entries bind exact image, ABI, function/lexical scope, frame,
declared type/bit size and half-open PC range, and use `address`, `value`, bounded `pieces`,
`optimized_out` or `unavailable` forms.

| Exact current-profile PC row | CFA and caller recovery |
|---|---|
| before entry `PUSH R7` | `CFA=SP+4`; caller PC=`[CFA-4]`; caller SP=CFA; caller R7=`same` |
| after push, at `MOV R7,R15` | `CFA=SP+8`; caller PC=`[CFA-4]`; caller SP=CFA; caller R7=`[CFA-8]` |
| stable body through pre-`POP R7` release | `CFA=R7+8`; caller PC=`[CFA-4]`; caller SP=CFA; caller R7=`[CFA-8]` |
| after `POP R7`, at `RET` | `CFA=SP+4`; caller PC=`[CFA-4]`; caller SP=CFA; caller R7=`same` |
| top-level entry/return | terminal; no fabricated caller |

Unknown schema/opcode/mandatory field is `unsupported`; malformed operands, overlapping rows,
bad types/ranges or cycles are `corrupt`; bound exhaustion is `unsupported(limit_exceeded)`;
missing snapshot bytes/registers are `unavailable` or a structured piece-only `partial`;
generation/revision mismatch is `stale`. Every result carries the exact terminating category
and diagnostic row/op/frame context. The evaluator never retries with a fixed R7 chain.

Variable locations are image/PC-ranged recipes for register, stack/frame offset, global typed
address, constant, composite/piece, optimized-out or unavailable. Reads preserve declared
width/endian/type and report partial/stale rather than padding/truncating silently.

### Capabilities

Negotiated capability names are `hsx.architecture.descriptor/1`,
`hsx.abi.descriptor/1`, `hsx.debug.image-bundle/1`,
`hsx.debug.unwind-recipes/1`, and `hsx.debug.location-recipes/1`. Their accepted records use
the schema/profile IDs `hsx.abi-descriptor/1`, `hsx.abi.llc-r7-word32/1`,
`hsx.unwind-recipe/1`, and `hsx.location-recipe/1`. The image-bundle capability includes the
source-identity manifest and target-specific binding; ST-008 introduces no extra capability
name. Legacy symbols use checked adapters and cannot claim portable unwind/location/source
conformance.

`hsx.debug.register-write/1` is optional. D-002 owns descriptor/register validation; D-001
owns attachment authority and D-003 owns stopped-state linearization, revision increments and
replacement stop/snapshot evidence. Successful legacy RPC calls never imply this capability.

## HSX-D-003 — Execution evidence, snapshots, exact step, and blocked states

### Evidence records

| Record | Purpose |
|---|---|
| `CommandReceipt` | Accept/reject request with operation ID and expected refs; never target-state proof. |
| `TransitionEvidence` | Target/image refs, monotonic transition revision, previous/new state, cause, operation correlation and structured details. |
| `StableStopEvidence` | StopToken, transition revision, PC/address, cause, resource/step evidence and inspection stability. |
| `InspectionSnapshotRef` | Target/image refs, transition + inspection revisions, snapshot token, supported read sets and stability grade. |
| `StepOutcome` | Operation/origin stop, retired_count 0/1, final transition/stop evidence, bypass evidence and precondition/preemption/terminal result. |

### Snapshot contract

Preferred full profile publishes an immutable snapshot covering registers/context plus a
revision-fenced view of memory, stack, disassembly and resources. A revision-pinned alternative
is conformant only if every read checks the same stable transition/inspection revision and
fails stale on mutation. Best-effort live reads are explicitly degraded and cannot back a
Debugger stop epoch.

Resume, wake, mutation, target/image generation change or invalidated revision makes reads
stale. Late responses cannot populate another snapshot.

### Exact step and precedence

Exact step retires zero or one guest instruction. Zero is valid for rejected stale/authority/
resource preconditions, a pre-dispatch pause, target loss, a non-bypassed origin breakpoint,
or any other condition linearized before architectural commit. Whether a fault or BRK retires
the attempted instruction is defined by the accepted ISA/fault profile and reported, never
assumed from reason name. One-shot origin breakpoint bypass
is fenced by TargetRef, origin StopToken, PC, operation ID and effective resource revision; it
does not remove shared resources.

Authoritative cause follows phase/linearization rather than one fixed reason order:

1. reject stale identity/stop/authority/resource preconditions without execution;
2. report target terminal/loss, pause/async break or non-bypassed origin breakpoint already
   linearized before dispatch with `retired_count = 0`;
3. after dispatch, the architectural instruction outcome controls fault/exception, BRK/trap,
   return/termination, mailbox wait or sleep and reports its profile-defined retired count;
4. after an otherwise normal commit, independently owned breakpoint/watchpoint or pause at
   the new boundary precedes requested step completion;
5. exact-step completion is primary only when no independent condition preempts.

Target loss discovered only by reconciliation yields unavailable/unknown unless terminal
evidence is independently proven. Duplicate evidence uses identity/revision, not timing.

HSX exposes instruction retirement, transition/snapshot/unwind/resource primitives. Debugger
owns source into/over/out plan algorithms and internal resource orchestration.

### Blocked-state matrix

WAIT_MBX/SLEEPING are inspection-stable only under `hsx.blocked.snapshot/1`, which publishes a
frozen SnapshotRef and invalidates it atomically before wake/timeout/deadline mutation. Without
that capability, they are state events only and inspection is unavailable or best-effort
degraded.

The full execution/inspection contract requires `hsx.execution.evidence/1` and
`hsx.inspection.snapshot/1`; `hsx.blocked.snapshot/1` is optional and governs only the named
blocked states.

### Optional raw register mutation

`hsx.debug.register-write/1` exposes one atomic `WriteRegisterSet` only for an exclusive
mutator at an inspection-stable explicit debug stop. Requests carry operation ID, exact
ExecutiveInstanceRef, SessionRef, AttachmentLease, TargetRef, LoadedImageRef, StopToken,
InspectionSnapshotRef, expected transition/inspection/register-set revisions, exact
architecture/ABI refs and typed register writes. A resume/step/lifecycle operation linearized
first, an observer/running/blocked target, or any stale ref/revision rejects the whole write.

R15 direct write is rejected; SP writes update authoritative SP and R15 mirror coherently;
PC must be aligned/executable in the same load, SP/R7 must satisfy alignment/stack guards, PSW
may change only declared writable bits, and duplicate/unknown/wrong-width entries fail
atomically. Successful mutation keeps target stopped, increments transition/inspection/
register revisions, publishes stopped→stopped `debug_register_write` TransitionEvidence and a
replacement StableStopEvidence/StopToken/SnapshotRef, and invalidates every origin handle.
The commit returns before/after revisions and new evidence; rejection changes no revision.
Ambiguous/partial mutation cannot satisfy the capability. Legacy unfenced raw writes are
unsupported at the portable boundary.

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

`ResourceRef` contains ExecutiveInstanceRef, TargetRef, LoadedImageRef where relevant, kind, opaque
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

The full resource capability is `hsx.debug-resource.revisions/1`; lifecycle events are
negotiated separately as `hsx.debug-resource.events/1` and carried under HSX-D-004.

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
| D-001 | restart/session/stream/target/PID reuse; identical artifact loaded on two targets with distinct LoadedImageIds; atomic launch; failed replace; exclusive/observer; stale generation; detach/disconnect/orphan; kill/tombstone; reconnect retained/lost |
| D-002 | multiple address widths/spaces; endian/alignment; checked overflow; cross-runtime golden canonical artifact/bundle/binding/source/component bytes and recursion rejection; exact-case/basename/casefold/relocation/content outcomes; current ABI register/frame/call rows; f16 allocator-reuse upper-zero expected-nonconformance/removal fixture; unknown/limited/corrupt/stale unwind/location recipes; partial pieces; revision-fenced register mutation validation |
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
