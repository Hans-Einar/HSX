# DBG-SL-001-005-007 — RF-004 Recipe Schema and Evaluator Foundation

- Status: **FROZEN / PLANNED**
- Parent: `DBG-RF-004`
- Iteration: `DBG-IT-001-005`
- Depends on signed: `DBG-SL-001-005-001..002`
- Review: `DBG-RVW-001-005-011`
- Verification: `DBG-VER-001-005-007`

## Goal and why now

Implement the closed `hsx.unwind-recipe/1` / `hsx.location-recipe/1` Python DTO,
parse/validation, bounded RecipeEvaluator and handle-free LocationEvaluator foundation before
the artifact Slice parses recipe-bearing rows. This resolves schema ownership without merging
artifact parsing, stack traversal or inspection composition into the recipe module.

## Owned files

- `python/hsx_debugger/recipes.py`
- relevant additive exports in `python/hsx_debugger/__init__.py`
- `python/tests/test_hsx_debugger_recipes.py`

Identity/address/result modules from Slice 002 are read-only. Artifact, source, stack,
inspection, legacy product/runtime and frontend files are read-only.

## Required behavior

- implement the exact frozen opcode/rule/location-piece/evaluation-context/budget/result DTOs
  and RecipeEvaluator/LocationEvaluator signatures from `dbg.resolver-inspection/1.1`;
- implement every frozen postfix pop/push, signedness/width propagation, final-stack/result
  rule and exact corrupt/unavailable/unsupported classification;
- enforce expression roles: CFA forbids recursive `cfa`; dependent roles require computed CFA;
  row/form role mismatch and cyclic/non-progressing CFA are corrupt;
- own UnwindRow/LocationRow DTOs and consume Slice 002 metadata SymbolRecord read-only, so no
  future artifact-module import cycle exists;
- require exact AbiDescriptorRef on both row types and reject evaluator row/ABI mismatch before
  any opcode/read;
- validate nullable LocationRow function/scope exactly against LOCAL, GLOBAL or CONSTANT
  SymbolRecord kind invariants; no address sentinel is permitted;
- preserve LocationRow.value_byte_order and exact ScalarBytes encoding for value/register/
  constant forms; address forms preserve exact read bytes;
- reject unknown mandatory schema/field/opcode as unsupported and malformed
  arity/type/width/stack/address/piece coverage as corrupt;
- enforce exact profile limits; every exhaustion is `UNSUPPORTED` with diagnostic
  `limit_exceeded` and never a separate status or truncation;
- keep scalar absence unavailable and allow partial only for structural pieces with exact
  available/missing ranges;
- use SnapshotReadPort only through exact InspectionContext and checked typed addresses;
- carry exact ArchitectureDescriptor in RecipeEvaluationContext for all register/special/
  address/alignment/serialization behavior;
- carry exact binding+bundle identity/architecture/ABI in RecipeEvaluationContext and call
  the shared DebugBindingValidator before any opcode/read;
- expose a pure row/component validator consumed read-only by the artifact Slice.

## Invariants and non-goals

- no artifact/component digest parsing, index/query ownership or local source resolution;
- no stack walk/frame handles, scope/variable enumeration or InspectionService;
- no fixed-R7 fallback, live reads, implicit masks/wrap/endian or frontend expression parsing;
- no Executive/VM/AVR/DAP/CLI/VS Code or RF-005..009 work.

## Traceability

`DBG-R-021..DBG-R-025`, `DBG-R-028`, `DBG-R-035..DBG-R-036`;
`DBG-F-007`, `DBG-F-015`; `DBG-D-003`, `DBG-D-004`; `HSX-D-002..HSX-D-003`;
interface `dbg.resolver-inspection/1.1`.

## Verification and completion signal

Test every opcode/rule/location form, exact result type, unknown/malformed input, evaluator
stack/deref/byte/total/piece bounds, `unsupported(limit_exceeded)`, endian/width/address
failure, stale context and structural partial pieces. Run signed identity/address regressions.
Close only after exact-head review, formal verification and Master sign-off.
