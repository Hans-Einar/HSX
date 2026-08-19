# DBG-SPR-001 Scrum Iterations

## DBG-IT-001-001 — DAP Protocol Baseline Stabilization

Status: IMPLEMENTATION COMPLETE — AWAITING INDEPENDENT REVIEW

### Slice

`DBG-SL-001-001-001` — see
`Slices/001--DAP_Protocol_Baseline.md`.

### Execution order

1. Master recorded Steering acceptance against PR #49 head
   `403d55c621d50212940b4c8668ac20a3cf8519b5` and froze the contract.
2. Fresh worker records `slice_started` and implements only the Slice.
3. Fresh independent reviewer reviews the exact worker head.
4. Blocking/High/Medium findings cause rework and a fresh exact-head review.
5. Verifier runs the required evidence and records `DBG-VER-001-001-001`.
6. Master reconciles sprint notes, CurrentIndex, Relations, Ledger, issue #37, and exact-head
   sign-off.

### Current result

The bounded worker completed `DBG-SL-001-001-001` on `codex/dbg-rf-001` from base
`e5a50ab45acdcb515ccd3602ce99487bd668cdfd`:

- raw adapter/bootstrap diagnostics now use stderr or configured logging;
- initialize response is serialized before the `initialized` event;
- the black-box subprocess test launches `vscode-hsx/debugAdapter/hsx-dap.py`, exercises
  initialize plus launch and attach, rejects unframed preambles, and runs on Windows;
- targeted Windows evidence: `36 passed` across DAP CLI, harness, and backend tests;
- broader `python/tests` evidence: `534 passed, 2 skipped, 2 failed`; the failures are an
  absent generated demo symbol artifact and an unrelated terminal-width-sensitive shell
  pretty-output assertion.

No independent reviewer or formal verifier has run yet; this is not a review or
verification PASS.
