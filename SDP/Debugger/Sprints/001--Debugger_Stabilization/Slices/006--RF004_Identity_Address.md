# DBG-SL-001-005-002 — RF-004 Typed Identity, Binding, Address, and Result Foundation

- Status: **FROZEN / PLANNED**
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
- relevant additive exports in `python/hsx_debugger/__init__.py`
- `python/tests/test_hsx_debugger_identity.py`
- `python/tests/test_hsx_debugger_addresses.py`

Existing `contracts.py`, controller/model/epochs/gateway/runtime files are read-only.

## Required behavior

- all values and nested payloads are deeply immutable and validate exact portable fields;
- `InspectionContext` rejects any target/image/epoch/stop/snapshot mismatch;
- equality is exact and case-sensitive; only frozen digest fields require lowercase Hex64;
- descriptor operations validate named spaces, widths, units, half-open ranges, alignment,
  permissions and explicit wrap policy;
- checked arithmetic returns typed overflow/underflow/wrong-space/misalignment/range failures;
- result envelopes enforce candidate/cardinality/status rules and retain structured diagnostics;
- best-effort live evidence cannot be marked coherent or allocate stable epoch handles.

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

Test exact mismatch matrices, immutability, digest/logical-ID validation, multiple widths and
spaces, every checked arithmetic/range/alignment failure, explicit wrap selection, result
cardinality and degraded coherence guards. Run earlier RF-002/RF-003 contract/epoch regressions.
Close only after exact-head review, formal verification and Master sign-off.
