# DBG-SL-001-005-005 — RF-004 Bounded Recipes, Locations, and Stack

- Status: **FROZEN / PLANNED**
- Parent: `DBG-RF-004`
- Iteration: `DBG-IT-001-005`
- Depends on signed: `DBG-SL-001-005-001..004`
- Review: `DBG-RVW-001-005-005`
- Verification: `DBG-VER-001-005-005`

## Goal and why now

Implement the frozen bounded recipe/location evaluator and snapshot-bound stack service so
callers and selected-frame variables are reconstructed without fixed ABI guesses or live reads.

## Owned files

- `python/hsx_debugger/recipes.py`
- `python/hsx_debugger/stack.py`
- relevant additive exports in `python/hsx_debugger/__init__.py`
- `python/tests/test_hsx_debugger_recipes.py`
- `python/tests/test_hsx_debugger_stack.py`

Earlier RF-004 modules, existing epoch/controller contracts, Executive and legacy stack code
are read-only.

## Required behavior

- validate and execute only frozen `hsx.unwind-recipe/1` and
  `hsx.location-recipe/1` opcodes, terminals and piece forms;
- enforce exact opcode/stack/deref/byte/frame/total/location-piece/result-bit bounds;
- use descriptor byte order, declared widths and checked typed-address operations only;
- select non-overlapping half-open rows by exact image/ABI/function/scope/frame/PC;
- reconstruct entry/push/body/pop/RET and terminal rows from immutable snapshot fixtures;
- return handle-free `UnwindFrame` values; Slice 006 alone allocates/wraps domain handles;
- return resume PC separately from checked call-site PC;
- return partial/unavailable/unsupported/corrupt/stale/limit-exceeded distinctly;
- evaluate selected non-top-frame variables from that frame/context;
- never retry with a fixed R7 chain or invent/pad a caller/value.

## Invariants and non-goals

- SnapshotReadPort is a fixture/Protocol consumer only; no runtime adapter is added;
- no stack cache, frontend frame IDs, DAP shape or current-frame fallback;
- no artifact/source parsing and no lifecycle/step/resource policy;
- no Executive/VM/AVR or RF-005..009 product work.

## Traceability

`DBG-R-021..DBG-R-025`, `DBG-R-028`, `DBG-R-035..DBG-R-036`;
`DBG-F-007`, `DBG-F-015`; `DBG-D-003`, `DBG-D-004`; `HSX-D-002..HSX-D-003`;
interface `dbg.resolver-inspection/1`.

## Verification and completion signal

Test every opcode/terminal class, corrupt operands/rows, unsupported schema/opcode, every
bound, endian/width/address failures, current ABI entry/body/epilogue rows, cycles/top-level,
partial reads, stale context, selected non-top-frame locals and no fixed-R7 fallback. Run
legacy stack diagnostics as an oracle. Close only after exact-head review, formal verification
and Master sign-off.
