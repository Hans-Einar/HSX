# DBG-SL-001-005-002 — RF-004 Typed Identity, Binding, Address, and Result Foundation

- Status: **REWORK 2 / FRESH CORRECTIVE WORKER PENDING**
- Implementation head: `4b5837644dc1196accfd8608bc3dbd20980476bb`
- Corrected head: `4280bc6008385042bdff923bd8e5392a1c290fdc`
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

- all values and nested payloads are deeply immutable and validate exact portable fields;
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
interface `dbg.resolver-inspection/1`.

## Verification and completion signal

Test exact mismatch matrices, immutability, digest/logical-ID validation, complete descriptor
version/encoding/serialization/register/special fields, multiple widths and
spaces, GPR+PC/SP/PSW ordering/widths/register byte order, canonical scalar byte encoding and
padding, the frozen StopEpoch binding status/code matrix, every checked
arithmetic/range/alignment/unit-conversion failure, explicit wrap selection, result
cardinality and degraded coherence guards. Run earlier RF-002/RF-003 contract/epoch regressions.
Close only after exact-head review, formal verification and Master sign-off.

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

Corrective result: `results.py` and owned metadata test only; focused 39 passed; all
`test_hsx_debugger*.py` 176 passed/1 WinError 1314 skip; mandated 39 passed/1 same skip;
canonical 2 passed; compile/import/export 129 PASS; stdlib trace 84/85/84/86/86%; scope/diff/
clean PASS.
