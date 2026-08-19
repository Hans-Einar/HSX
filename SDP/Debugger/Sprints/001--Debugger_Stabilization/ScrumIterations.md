# DBG-SPR-001 Scrum Iterations

## DBG-IT-001-001 — DAP Protocol Baseline Stabilization

Status: `verified_pending_master_signoff`

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
  absent generated demo symbol artifact and an unrelated shell pretty-output assertion on
  the untouched optional-`tabulate` rendering path.

Fresh independent review `DBG-RVW-001-001-001` inspected exact implementation head
`208063e344b767f82790ce579eba6327e2cdd0ce` and returned PASS with no
Blocking/High/Medium findings. Reviewer Windows evidence repeated the targeted `36 passed`,
ran the production-wrapper subprocess cases ten times without a cleanup hang, and confirmed
strict rejection of both injected preamble and trailing unframed bytes.

Formal `DBG-VER-001-001-001` passed against repository head
`fefd4b0c427dfa71d637e4f4cce9e4a345912591`, with no product/test diff from independently
reviewed implementation head `208063e344b767f82790ce579eba6327e2cdd0ce`:

- targeted Windows DAP CLI/harness/backend evidence: `36 passed`;
- production wrapper initialize ordering plus launch/attach: `3 passed`;
- raw preamble and trailing-byte negative controls: `2/2 rejected`;
- broader `python/tests`: `534 passed, 2 skipped, 2 failed`, both independently classified
  outside Slice ownership;
- traceability YAML and Ledger NDJSON validation: PASS.

Linux execution is not claimed and remains assigned to `DBG-RF-009`. Master exact-head
sign-off has not occurred, and `DBG-DA-001` remains blocked.
