# DBG-RVW-001-005-007 — RF-004 Interface and Slice-Freeze Review

- Status: **REWORK**
- Reviewed exact head: `82154c614a31284723bf3e6a337c5bedfb8aba5d`
- Remote branch: `origin/codex/dbg-rf-004`
- Review mode: fresh independent, read-only
- Scope: Master activation, `dbg.resolver-inspection/1`, six RF-004 Slice contracts and
  durable first-wave/dependency closeout
- Next review: `DBG-RVW-001-005-008`

## Findings

1. **High — public API semantics incomplete.** Placeholder parameters and undefined public
   record/AST schemas still required worker invention. Address arithmetic also lacked the
   explicit wrap-selection parameter required by its own rule.
2. **High — handle ownership contradicted Slice order.** Slice 005 stack output was required
   to contain handles even though Slice 006 exclusively owned handle allocation and treated
   prior modules as read-only.
3. **Medium — RF-002 StopEpoch seam unspecified.** InspectionContext did not consume an exact
   StopEpoch input/adaptation path even though RF-004 is required to consume RF-002's epoch
   port without editing it.
4. **Medium — live dependency relations stale.** Relations still described portable-address
   contracts as blocking RF-004 and the first-wave shared interface as awaiting Steering.

No existing frozen DBG/HSX design contradiction and no product finding was reported. Rework
is limited to the RF-004 candidate interface/Slice documents and current traceability status.

## Independent evidence

- exact HEAD/worktree/remote: PASS and clean;
- base ancestry from `69a54aeb3394d3cd4792bce620748e15bab69f1f`: PASS;
- diff scope: 24 SDP-only paths; no product/runtime/frontend/AVR change;
- `git diff --check`: PASS;
- CurrentIndex, Issues and Relations YAML: PASS;
- Ledger: 114 valid NDJSON records;
- Slice ID/path allocation, changed paths and Markdown fences: PASS;
- exactly one active iteration: `DBG-IT-001-005`.

This is not product verification or Master sign-off.

## Master disposition

REWORK accepted. Master expands the public field/result/query/pagination/expression schemas,
makes address arithmetic mode explicit, makes Slice 005 return handle-free UnwindFrames,
assigns all handle allocation/wrapping to Slice 006, freezes a read-only
`ControllerEpochAdapter` seam for RF-002 StopEpoch, corrects the stale live relations, and
requires fresh exact-head `DBG-RVW-001-005-008` before any product worker.
