# DBG-SL-001-001-001 — DAP Protocol and Product-Entrypoint Baseline

Status: `verified_pending_master_signoff`

Worker base: `e5a50ab45acdcb515ccd3602ce99487bd668cdfd` on
`codex/dbg-rf-001`.

Reviewed implementation head: `208063e344b767f82790ce579eba6327e2cdd0ce` by
`DBG-RVW-001-001-001`.

Verified repository head: `fefd4b0c427dfa71d637e4f4cce9e4a345912591` by
`DBG-VER-001-001-001`; no product/test diff exists between it and the reviewed
implementation head.

## Goal

Make the exact DAP wrapper launched by the VS Code extension protocol-pure, lifecycle-correct
for initialize ordering, and covered by a black-box framing/handshake regression test.

## Why this Slice exists now

`DBG-F-001..DBG-F-003` prevent the real product path and its tests from serving as a trusted
oracle. This narrow correctness Slice is the only product change permitted before
`DBG-DA-001`.

## Expected files or modules

- `vscode-hsx/debugAdapter/hsx-dap.py`
- `python/hsx_dap/__init__.py`
- `python/tests/test_hsx_dap_cli.py`
- closely related existing DAP test fixtures only when the required assertions cannot be
  expressed in the primary test file
- this sprint's status/notes plus Debugger CurrentIndex, Relations, Ledger, and verification
  record

Any product file outside that set requires a Master contract amendment before modification.

## Invariants

- stdout is exclusively DAP framing and payload bytes;
- initialize response precedes the `initialized` event;
- extension wrapper CLI/environment behavior remains compatible;
- unrelated DAP requests and legacy fallback behavior remain unchanged;
- no accepted structural design is implied by this fix.

## Non-goals

- state ownership, threading model, stop epochs, stepping, lifecycle ownership, resource
  reconciliation, symbols/source/address behavior, module decomposition, extension UI, and
  packaging redesign;
- `DBG-RF-002..DBG-RF-009` and `DBG-DA-001` work.

## SharedUI rule

Not applicable: this Slice changes Python DAP protocol/bootstrap and tests, not a SharedUI
consumer page. The general anti-monolith and no-half-wired rules still apply.

## Traceability

- Parent: `DBG-RF-001`
- Study/evidence: `DBG-ST-001`, `DBG-CR-001`, `DBG-GAP-001`
- Findings: `DBG-F-001`, `DBG-F-002`, `DBG-F-003`
- Requirements: `DBG-R-001`, `DBG-R-002`, `DBG-R-032`, `DBG-R-033`, `DBG-R-036`
- Sprint/iteration: `DBG-SPR-001`, `DBG-IT-001-001`
- Slice: `DBG-SL-001-001-001`
- Review: `DBG-RVW-001-001-001`
- Verification: `DBG-VER-001-001-001`

## Verification required

- production wrapper initialize handshake through real stdio framing;
- initialize response observed before `initialized`;
- launch/attach fixture handshake through the same wrapper;
- strict parser/assertion rejects any non-DAP preamble or trailing unframed stdout;
- targeted DAP CLI/harness/backend tests;
- broader Python test suite in proportion to runtime;
- Windows execution in this work cycle; Linux execution if available, otherwise record the
  residual platform evidence obligation under `DBG-RF-009` without claiming it passed.

## Expected completion signal

One exact implementation commit has a fresh independent review PASS, rerunnable verification
evidence, no unresolved Blocking/High/Medium findings, updated traceability/sprint records,
and Master exact-head sign-off in issue #37.

## Verification result

`DBG-VER-001-001-001` is PASS for the contracted Windows evidence. Targeted tests reported
`36 passed`; production-wrapper framing/lifecycle cases reported `3 passed`; direct raw
preamble and trailing-byte controls were both rejected. The broad suite's two failures were
classified outside Slice ownership. Linux remains a `DBG-RF-009` residual and is not claimed
as PASS. The Slice awaits Master exact-head sign-off only.
