# DBG-SL-001-005-006 — RF-004 Epoch-Bound Inspection Integration

- Status: **FROZEN / PLANNED**
- Parent: `DBG-RF-004`
- Iteration: `DBG-IT-001-005`
- Depends on signed: `DBG-SL-001-005-001..005`, `DBG-SL-001-005-007`
- Review: `DBG-RVW-001-005-006`
- Verification: `DBG-VER-001-005-006`

## Goal and why now

Compose the signed identity/address/artifact/source/stack services into one frontend-neutral
InspectionService covering registers, stack, scopes, variables, side-effect-free snapshot
expressions, memory and disassembly for an
exact coherent epoch/snapshot, with stable domain handles and explicit partial/unavailable
results.

## Owned files

- `python/hsx_debugger/handles.py`
- `python/hsx_debugger/inspection.py`
- relevant additive exports in `python/hsx_debugger/__init__.py`
- `python/tests/test_hsx_debugger_inspection.py`

All earlier RF-004 product modules are read-only consumers. Existing controller/epochs,
gateway, Executive, DAP/CLI and VS Code modules are read-only.

## Required behavior

- every result carries exact TargetRef, LoadedImageRef, StopEpochId, StopToken and
  InspectionSnapshotRef evidence;
- implement exact `InspectionService.create/open_epoch/invalidate_epoch/close`,
  EpochInspectionSession and EpochHandleStore constructor/intern/resolve/invalidate APIs with
  explicit index/read-port/architecture/limit/stack/location dependencies;
- factory validates exact architecture/ABI ref+digest, full portable capability profile and
  profile limits with the frozen status/code matrix;
- allocate every frame/scope/variable DomainHandle here and wrap Slice 005's handle-free
  `UnwindFrame` values without editing the signed stack module;
- registers/stack/scopes/variables/memory/disassembly use one exact snapshot or explicitly
  identified immutable image bytes;
- SnapshotReadPort rejects target/image/token/snapshot/revision mismatches and late data;
- repeated/paged stack/scope/variable queries retain earlier handles in the same epoch;
- variable records preserve exact SymbolRecord.symbol_id, declaration order, VARIABLE handles and
  structural available/missing pieces; duplicate names remain distinct;
- all collections follow the frozen order/page-slice rules and exact object keys intern the
  same handle on repeated queries;
- exact-context unknown/wrong-kind and foreign-context handles are `UNKNOWN_HANDLE`; service-
  history exact-context invalidated handles/sessions are `STALE`; a foreign handle remains
  unknown even when it reuses the same opaque epoch string;
- no fallback to current/top/first frame and no handle reuse across epochs;
- variables use exact selected frame and location row; partial pieces stay partial;
- locals/globals/constants resolve through LocationRow using exact non-null or None/None
  function/scope IDs; stack/register/constant forms require no synthetic address;
- scopes/variables follow the frozen register/local/global composition and artifact
  source/type/lexical-scope/variable queries; Watch requests use separate ExpressionValue;
- REGISTERS return RegisterVariableRecord without synthetic symbols/addresses; LOCALS/GLOBALS
  return SymbolVariableRecord keyed only by SymbolRecord.symbol_id; no child-scope handle;
- every AVAILABLE record/expression returns exact fixed-width raw_bytes using the frozen
  register/location/address/constant byte-order source and non-byte-aligned padding rules;
- snapshot expressions are typed/side-effect-free, selected-frame-bound, and never create a
  persistent live watch or delegate a raw string to runtime;
- memory/disassembly validate typed spaces/ranges/permissions and preserve unavailable bytes;
- memory byte_length converts through the exact address-space unit contract before reads;
- best-effort live evidence cannot create coherent results or stable handles;
- bounded concurrent fixture calls are deterministic and immutable.
- same-context open is idempotent, different valid epoch invalidates old before publish, same
  epoch ID/different context or any previously invalidated ID is stale; close is terminal;
  handles embed complete context and lifecycle/handle mutations are linearizable.

## Invariants and non-goals

- no run control, raw RPC, transport retries, snapshot capture, runtime adapter or frontend
  mapping;
- no DAP integer IDs, VS Code policy, breakpoint/watch/lifecycle/source-step ownership;
- no Executive/VM/AVR edits and no RF-005..009 work;
- no change to any frozen public interface discovered during implementation.

## Traceability

`DBG-R-004`, `DBG-R-021..DBG-R-028`, `DBG-R-034..DBG-R-036`;
`DBG-F-007`, `DBG-F-015`, `DBG-F-017`, inspection portion of `DBG-F-026`;
`DBG-D-003`, `DBG-D-004`, `DBG-D-009`; `HSX-D-001..HSX-D-003`;
interface `dbg.resolver-inspection/1.2`.

## Verification and completion signal

Test registers/stack/scopes/variables/snapshot-expression/memory/disassembly surfaces,
selected-frame variables, repeated/paged/out-of-order and
concurrent queries, unknown/stale handles, resume/new-stop invalidation model, exact mismatch
matrix, partial/unavailable paths, multiple address spaces/widths, cross-service snapshot
consistency and injected late responses. Re-run all signed RF-004 and RF-002/RF-003 regression
suites plus protected-path guards. Close only after exact-head review, formal verification and
Master sign-off.
