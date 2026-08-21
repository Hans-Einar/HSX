# DBG-SL-001-005-002 — RF-004 Typed Identity, Binding, Address, and Result Foundation

- Status: **POST-REFREEZE CORRECTED / REVIEW 027 PENDING**
- Implementation head: `4b5837644dc1196accfd8608bc3dbd20980476bb`
- Corrected head: `4280bc6008385042bdff923bd8e5392a1c290fdc`
- Corrected head 2: `6c933ea6b11e42d58da52faf0997f8c978dad54b`
- Post-refreeze corrected head: `c7bc39057469f1aa62a78f409753ec0213631214`
- Parent: `DBG-RF-004`
- Iteration: `DBG-IT-001-005`
- Depends on signed: `DBG-SL-001-005-001`
- Review: `DBG-RVW-001-005-002`
- Verification: `DBG-VER-001-005-002`

## Goal and why now

Implement the immutable public value/result foundation required by every later resolver and
inspection Slice, with exact Target/Image/StopEpoch/Snapshot binding and descriptor-checked
typed HSX addresses.

## Owned files

- `python/hsx_debugger/identity.py`
- `python/hsx_debugger/addresses.py`
- `python/hsx_debugger/results.py`
- `python/hsx_debugger/snapshot.py`
- `python/hsx_debugger/metadata.py`
- relevant additive exports in `python/hsx_debugger/__init__.py`
- `python/tests/test_hsx_debugger_identity.py`
- `python/tests/test_hsx_debugger_addresses.py`
- `python/tests/test_hsx_debugger_metadata.py`

Existing `contracts.py`, controller/model/epochs/gateway/runtime files are read-only.

## Required behavior

- all values and nested payloads are recursively contract-safe immutable under the supported
  mutation model and validate exact portable fields;
- ArtifactRef/bundle identity/ref/binding Python projections reproduce the frozen canonical
  key/digest model and golden vectors without folding component fields into a ref;
- shared DebugBindingValidator freezes canonical bundle digest plus architecture/ABI
  binding/ref/digest outcomes for every later public entrypoint;
- `InspectionContext` rejects any target/image/epoch/stop/snapshot mismatch;
- `ControllerEpochAdapter` consumes RF-002 `contracts.StopEpoch` read-only and binds only
  already-typed portable StopToken/SnapshotRef values with an exact GenerationStamp match;
  legacy/untyped inputs return unavailable and no context;
- equality is exact and case-sensitive; only frozen digest fields require lowercase Hex64;
- descriptor operations validate named spaces, widths, units, half-open ranges, alignment,
  permissions and explicit wrap policy;
- address/range/arithmetic values use declared units; byte conversion is exact for whole-byte
  units and returns typed unsupported/misaligned outcomes otherwise;
- ArchitectureDescriptor requires version, encoding, independent container/instruction
  serialization, GPR width/count/order, PC/SP spaces and PSW width;
- checked arithmetic returns typed overflow/underflow/wrong-space/misalignment/range failures;
- result envelopes enforce candidate/cardinality/status rules and retain structured diagnostics;
- pure metadata DTOs freeze source/function/symbol/type/scope/instruction/memory records without
  parsing/index policy; recipe row DTOs remain Slice 007-owned;
- best-effort live evidence cannot be marked coherent or allocate stable epoch handles.
- SnapshotReadPort is frozen as a Protocol with exact context/result fencing; no runtime/live
  adapter is implemented in this Slice or RF-004.

## Invariants and non-goals

- no artifact parsing, filesystem lookup, snapshot reads, stack or frontend mapping;
- no implicit `0xFFFF`/`0xFFFFFFFF`, modulo, truncation or cross-space comparison;
- no change to `dbg.controller-gateway/1.1` or earlier signed modules;
- no runtime adapter or Executive/VM/DAP/CLI/VS Code/AVR change.

## Traceability

`DBG-R-004`, `DBG-R-021..DBG-R-025`, `DBG-R-028`, `DBG-R-035..DBG-R-036`;
`DBG-F-007`, `DBG-F-019`; `DBG-D-003`, `DBG-D-004`; `HSX-D-001..HSX-D-003`;
interface `dbg.resolver-inspection/1.1`; conformance `DBG-CF-001-005-001`.

## Verification and completion signal

Test exact mismatch matrices, `DBG-CF-001-005-001` supported-mutation immutability,
caller-container detachment, exact approved Enum identity, non-contract-safe payload rejection,
digest/logical-ID validation, complete descriptor
version/encoding/serialization/register/special fields, multiple widths and
spaces, GPR+PC/SP/PSW ordering/widths/register byte order, canonical scalar byte encoding and
padding, the frozen StopEpoch binding status/code matrix, every checked
arithmetic/range/alignment/unit-conversion failure, explicit wrap selection, result
cardinality and degraded coherence guards. Run earlier RF-002/RF-003 contract/epoch regressions.
Close only after exact-head review, formal verification and Master sign-off.

No conformance fixture may require Enum cloning or isolation from reflection/monkey-patching of
the Python type system, Enum class/member internals, descriptors or `object.__setattr__` bypasses.

## Worker result

- exact nine owned files; append-only prior exports preserved;
- focused identity/address/metadata: 35 passed;
- all `test_hsx_debugger*.py`: 172 passed, 1 classified WinError 1314 skip;
- mandated contracts/epochs/Slice001 regressions: 39 passed, 1 same skip;
- import/export smoke: 129 unique exports PASS;
- stdlib trace coverage: identity 84.2%, addresses 85.2%, results 82.5%, snapshot 84.3%,
  metadata 86.5%, aggregate 84.2%;
- diff-check, exact scope and clean status: PASS.

Review `DBG-RVW-001-005-002`: REWORK. Next review after bounded correction:
`DBG-RVW-001-005-021` — REWORK. Next fresh review after correction: `DBG-RVW-001-005-022`.

`DBG-RVW-001-005-022`: REWORK trace-only; all code findings PASS. Fresh review:
`DBG-RVW-001-005-023` — REWORK. Next review after correction: `DBG-RVW-001-005-024`.

Third correction at `373d786a983252d5b1735b599596293557adba5a`: raw, non-overridable
dataclass/enum state inspection; custom attribute access rejected across relevant MRO; hidden
extra/mutable state, direct frozen inheritance, enum concealment and legitimate DTO regressions.
Focused 45, debugger 182+1 classified skip, mandated 39+1 same skip, canonical 2, compile/import/
export 129, diff/fsck/exact scope/clean PASS. Review 024: REWORK because `__dict__` descriptors
and mutated `__slots__` metadata can still hide live storage. Next review after bounded storage-
descriptor correction: `DBG-RVW-001-005-025`.

Fourth correction at `bbc5c8ba3be960bcb7d522edbf3d5ae12dbe8c2a`: raw class mapping,
exact built-in storage descriptors, direct storage reads and layout cross-checks reject filtered
dict descriptors plus slot metadata/descriptor concealment for dataclass and Enum. Focused 51,
debugger 188+1 classified skip, mandated 39+1 same skip, canonical 2, adversarial 7, exports 129,
diff/fsck/exact scope/clean PASS. Review 025 is pending.

Review 025: REWORK. Review 024 storage-descriptor findings are closed, but Enum validation
must traverse every actual non-value instance storage cell before retaining the member. Fresh
bounded correction 5 is followed by `DBG-RVW-001-005-026`.

Fifth correction at `0bedb2d110147f3f34c5846d14ee9b9581926f2d`: complete canonical
Enum/status storage validation, mutable/inconsistent metadata and extra-state rejection, with
standard HSX/status Enum and public DTO acceptance. Focused 60, debugger 197+1 classified skip,
mandated 39+1 same skip, oracle 16+1, canonical 2, exports 129, exact scope/git PASS. Review 026
is pending.

Review 026: REWORK. Pre-construction Enum/storage findings are closed, but retaining the Enum
singleton does not snapshot post-construction member/property changes. Fresh corrective worker
6 first performs a frozen-contract feasibility assessment; review 027 is conditional on a
private type-preserving correction, otherwise work stops for Steering.

Feasibility result: NEGATIVE with no edits. Exact Python Enum singleton identity and an
independent post-construction immutable snapshot cannot both be preserved under the frozen
schemas. See `Interfaces/005--RF004_Enum_Immutability_Steering_Blocker.md`. Review 027,
verification and later Slices are not started.

Steering comment `5368017338` accepts the blocker and refreezes supported-mutation /
contract-safe immutability as interface `1.1` with every public schema and exact Enum member
unchanged. Review 028 returned REWORK on the fixture/trace candidate; product correction remains
stopped until fresh interface review 030 PASS. Review 030 passed at `ae49435…`; a fresh
post-refreeze corrective worker may now start. Historical review 026 remains REWORK; review 027
is reserved only for the new product head.

Fresh post-refreeze worker committed `c7bc39057469f1aa62a78f409753ec0213631214`, changing only
`results.py`, the owning identity/address/metadata Enum registration points and the owned
metadata test. The private registry contains the exact 19 approved types; canonical Enum
identity, list/dict/set normalization, recursive frozen DTO admission and unsafe payload
rejection follow `DBG-CF-001-005-001`. Reflection/type-system assertions were retired. Public
surface/129 exports are unchanged. Evidence: focused 47; debugger 184+1 classified skip;
mandated 39+1; oracle 16+1; canonical 2; hashseed 0/1 each 26; compile/import/scope/git PASS.
Fresh product-only review is `DBG-RVW-001-005-027`.

Second correction: exact atom types; directly declared frozen dataclasses only; all fields
deep-traversed; undeclared dict/slot state rejected. Focused 43, debugger 180+1 skip, mandated
39+1, canonical 2, compile/import/export 129, diff/fsck/scope/clean PASS.

Corrective result: `results.py` and owned metadata test only; focused 39 passed; all
`test_hsx_debugger*.py` 176 passed/1 WinError 1314 skip; mandated 39 passed/1 same skip;
canonical 2 passed; compile/import/export 129 PASS; stdlib trace 84/85/84/86/86%; scope/diff/
clean PASS.
