# DBG-SPR-001 Handoff

## Current objective

Obtain Steering acceptance of the corrected SDP baseline, then execute only
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
- Exact product baseline provenance and the planned execution contracts are being added.

## Not done

- Steering acceptance is not yet recorded against the corrected PR head.
- No product-code worker has started.
- Review and verification records are planned only.

## Exact next step

Commit/push the documentation corrections, re-audit the exact PR head, and record the gate
decision in issue #36. Only an accepted state permits worker dispatch.

## Traceability state

- Active evidence: `DBG-ST-001`, `DBG-CR-001`, `DBG-GAP-001`
- Planned execution: `DBG-SPR-001`, `DBG-IT-001-001`, `DBG-SL-001-001-001`
- Planned review/verification: `DBG-RVW-001-001-001`, `DBG-VER-001-001-001`
- CurrentIndex/Relations are updated in the correction change.
- Ledger still needs the correction/freeze events appended before commit.

## Agents and worktree

No worker or reviewer is open. The user's original dirty `Implementation/vscode` worktree
must remain untouched; controlled work uses a separate clean worktree/branch.

## Risks

- `DBG-RF-004` and `DBG-RF-006` remain blocked on stable HSX cross-track contracts to be
  produced from `HSX-ST-001`.
- Structural debugger work remains blocked by `DBG-DA-001` and accepted `DBG-D-*` contracts.
