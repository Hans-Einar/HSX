# DBG-SPR-001 Handoff

## Current objective

Execute only
`DBG-SL-001-001-001` through worker, independent reviewer, verification, and exact-head
Master sign-off.

## Authority

- issue #36 — Steering acceptance
- issue #37 — `DBG-RF-001`
- `SDP/Debugger/Traceability/CurrentIndex.yaml`
- `SDP/Debugger/Refactor/001--DAP_Protocol_Baseline_Stabilization/README.md`
- `SDP/Debugger/Sprints/001--Debugger_Stabilization/Slices/001--DAP_Protocol_Baseline.md`

## Done

- Master audited PR #49 head `43168e9fee21ba48fbd7b0964b153ef0b6bc51bc`.
- Findings were recorded durably in issue #36.
- Exact product baseline provenance and the execution contracts were added and re-audited at
  PR #49 head `403d55c621d50212940b4c8668ac20a3cf8519b5`.
- Steering acceptance was recorded in issue #36; the Slice contract is frozen.
- A fresh bounded worker completed `DBG-SL-001-001-001` from base
  `e5a50ab45acdcb515ccd3602ce99487bd668cdfd` on `codex/dbg-rf-001`.
- The production wrapper now keeps raw diagnostics off stdout, initialize response precedes
  `initialized`, and strict Windows black-box coverage exercises initialize plus launch and
  attach through `vscode-hsx/debugAdapter/hsx-dap.py`.
- Worker evidence:
  - `c:/Users/hanse/miniconda3/python.exe -m pytest python/tests/test_hsx_dap_cli.py python/tests/test_hsx_dap_harness.py python/tests/test_hsx_dbg_backend.py -q`
    — `36 passed`.
  - `c:/Users/hanse/miniconda3/python.exe -m pytest python/tests -q`
    — `534 passed, 2 skipped, 2 failed`; failures were
    `test_break_add_symbol_line` (missing generated
    `examples/demos/build/debug/longrun/main.sym`) and
    `test_pretty_dmesg_assigns_session_numbers` (unrelated terminal-width-sensitive output).

## Not done

- Independent exact-head review has not run.
- `DBG-VER-001-001-001` has not been created and no formal verification PASS is claimed.
- Master exact-head sign-off has not occurred.

## Exact next step

Assign a fresh independent reviewer to `DBG-RVW-001-001-001` against the exact worker commit.
Blocking/High/Medium findings require rework and a fresh exact-head review.

## Traceability state

- Active evidence: `DBG-ST-001`, `DBG-CR-001`, `DBG-GAP-001`
- Implementation complete: `DBG-SPR-001`, `DBG-IT-001-001`, `DBG-SL-001-001-001`
- Ready for review: `DBG-RVW-001-001-001`
- Planned verification: `DBG-VER-001-001-001`
- CurrentIndex and Ledger are current through worker completion; Relations required no change.

## Agents and worktree

The bounded worker implementation is complete in the controlled worktree on
`codex/dbg-rf-001`; no reviewer is open. The user's original dirty
`Implementation/vscode` worktree remains untouched.

## Risks

- `DBG-RF-004` and `DBG-RF-006` remain blocked on stable HSX cross-track contracts to be
  produced from `HSX-ST-001`.
- Structural debugger work remains blocked by `DBG-DA-001` and accepted `DBG-D-*` contracts.
- Linux product-wrapper execution was not available in this Windows worker cycle; the
  remaining cross-platform evidence obligation stays assigned to `DBG-RF-009`.
- The two broader-suite failures listed above remain non-Slice evidence for the reviewer/
  verifier to classify; no out-of-scope product changes were made for them.
