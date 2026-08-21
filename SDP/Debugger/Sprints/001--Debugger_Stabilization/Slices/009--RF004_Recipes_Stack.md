# DBG-SL-001-005-005 — RF-004 Snapshot-Bound Stack Service

- Status: **FROZEN / PLANNED**
- Parent: `DBG-RF-004`
- Iteration: `DBG-IT-001-005`
- Depends on signed: `DBG-SL-001-005-001..004`, `DBG-SL-001-005-007`
- Review: `DBG-RVW-001-005-005`
- Verification: `DBG-VER-001-005-005`

## Goal and why now

Implement the snapshot-bound StackService over the already signed recipe evaluator so callers
are reconstructed without fixed ABI guesses or live reads.

## Owned files

- `python/hsx_debugger/stack.py`
- relevant additive exports in `python/hsx_debugger/__init__.py`
- `python/tests/test_hsx_debugger_stack.py`

Earlier RF-004 modules including `recipes.py`, existing epoch/controller contracts, Executive
and legacy stack code are read-only.

## Required behavior

- consume the signed Slice 007 recipe DTO/validator/evaluator without editing it;
- require/pass exact ArchitectureDescriptor/AbiDescriptorRef to every evaluator call;
- validate index binding+bundle+architecture+ABI before selecting/evaluating any row;
- enforce exact frame/total request bounds through the signed evaluator budget/results;
- use descriptor byte order, declared widths and checked typed-address operations only;
- select non-overlapping half-open rows by exact image/ABI/function/scope/frame/PC;
- reconstruct entry/push/body/pop/RET and terminal rows from immutable snapshot fixtures;
- return handle-free `UnwindFrame` values; Slice 006 alone allocates/wraps domain handles;
- return resume PC separately from checked call-site PC;
- return partial/unavailable/unsupported/corrupt/stale distinctly; every bound exhaustion is
  `UNSUPPORTED` with diagnostic `limit_exceeded`;
- never retry with a fixed R7 chain or invent/pad a caller/value.

## Invariants and non-goals

- SnapshotReadPort is a fixture/Protocol consumer only; no runtime adapter is added;
- no stack cache, frontend frame IDs, DAP shape or current-frame fallback;
- no artifact/source parsing and no lifecycle/step/resource policy;
- no Executive/VM/AVR or RF-005..009 product work.

## Traceability

`DBG-R-021..DBG-R-025`, `DBG-R-028`, `DBG-R-035..DBG-R-036`;
`DBG-F-007`, `DBG-F-015`; `DBG-D-003`, `DBG-D-004`; `HSX-D-002..HSX-D-003`;
interface `dbg.resolver-inspection/1.1`.

## Verification and completion signal

Test current ABI entry/body/epilogue rows, terminal top-level, cycles/non-progress, frame/total
budgets, endian/width/address failures propagated from the signed evaluator, partial frame
prefixes, stale context and no fixed-R7 fallback. Run legacy stack diagnostics as an oracle.
Close only after exact-head review, formal verification and Master sign-off.
