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

## Not done

- No product-code worker has started.
- Review and verification records are planned only.

## Exact next step

Dispatch one fresh worker with the exact Slice contract and require it to record
`slice_started` before product implementation.

## Traceability state

- Active evidence: `DBG-ST-001`, `DBG-CR-001`, `DBG-GAP-001`
- Planned execution: `DBG-SPR-001`, `DBG-IT-001-001`, `DBG-SL-001-001-001`
- Planned review/verification: `DBG-RVW-001-001-001`, `DBG-VER-001-001-001`
- CurrentIndex/Relations/Ledger are current through Steering acceptance and contract freeze.

## Agents and worktree

No worker or reviewer is open. The user's original dirty `Implementation/vscode` worktree
must remain untouched; controlled work uses a separate clean worktree/branch.

## Risks

- `DBG-RF-004` and `DBG-RF-006` remain blocked on stable HSX cross-track contracts to be
  produced from `HSX-ST-001`.
- Structural debugger work remains blocked by `DBG-DA-001` and accepted `DBG-D-*` contracts.
