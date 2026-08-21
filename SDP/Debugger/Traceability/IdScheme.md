# Debugger Traceability ID Scheme

Namespace: `DBG`

Stable IDs:

- `DBG-ST-###` — Study
- `DBG-R-###` — requirement
- `DBG-A-###` — architecture boundary/decision
- `DBG-DA-###` — DesignAnalysis
- `DBG-D-###` — detailed design contract/decision
- `DBG-FEAT-###` — Feature work domain
- `DBG-CR-###` — CodeReview
- `DBG-F-<CR>-###` — CodeReview finding (for example `DBG-F-001-004` may be
  abbreviated in review prose as `DBG-F-004` when the owning review is unambiguous)
- `DBG-GAP-###` — GapAnalysis
- `DBG-RF-###` — Refactor work domain
- `DBG-SPR-###` — sprint
- `DBG-IT-###-###` — iteration
- `DBG-SL-###-###-###` — bounded implementation slice
- `DBG-RVW-###-###-###` — independent review record
- `DBG-VER-###-###-###` — verification record

Substantial debugger product-code work should normally belong to either a `DBG-FEAT-*`
or `DBG-RF-*` domain and be executed through one or more `DBG-SL-*` slices.

IDs are never recycled after use in traceability, a GitHub issue/PR, or the ledger.

Cross-track references retain their own namespace (`HSX-*`, `AVR-*`).
Legacy `DR-*`/`DG-*` references remain provenance IDs and are mapped to the new stable
track IDs rather than silently renamed in historical documents.

## Allocated first structural wave IDs

- `DBG-IT-001-004` — RF-002/RF-003 controller/gateway first wave
- `DBG-SL-001-004-001` — controller/state/epoch foundation
- `DBG-SL-001-004-002` — typed legacy gateway/health/recovery foundation
- `DBG-SL-001-004-003` — early controller/gateway integration
- `DBG-RVW-001-004-001..DBG-RVW-001-004-003` — independent Slice reviews
- `DBG-RVW-001-004-004` — fresh independent `dbg.controller-gateway/1.1` refreeze review
- `DBG-RVW-001-004-005` — RF-002 fresh exact-head re-review after Slice findings
- `DBG-RVW-001-004-006` — RF-003 fresh exact-head re-review after Slice findings
- `DBG-RVW-001-004-007` — RF-002 fresh exact-head review after parent terminal-result finding
- `DBG-RVW-001-004-008` — RF-002 fresh exact-head review after saturated-inbox finding
- `DBG-RVW-001-004-009` / `DBG-VER-001-004-005` — RF-003 fresh Slice review/verification
  after implicit-reopen finding
- `DBG-RVW-001-004-010` / `DBG-VER-001-004-006` — dependent integration re-review and
  verification after RF-003 correction
- `DBG-RVW-001-004-011` — RF-003 fresh review after failed replacement-OPEN finding
- `DBG-VER-001-004-001..DBG-VER-001-004-003` — formal Slice verifications
- `DBG-VER-001-004-004` — RF-002 fresh formal Slice verification after parent finding
- `DBG-RVW-002-001-001` — RF-002 premature parent review, REWORK
- `DBG-RVW-002-001-002` — RF-002 final parent attempt, REWORK on trace
- `DBG-RVW-002-001-003` — RF-002 parent attempt, REWORK on trace
- `DBG-RVW-002-001-004` — RF-002 parent attempt, REWORK on initial-status trace
- `DBG-RVW-002-001-005` — RF-002 parent attempt, REWORK on global-state trace
- `DBG-RVW-002-001-006` — RF-002 parent attempt, REWORK on gate label
- `DBG-RVW-002-001-007` / `DBG-VER-002-001-001` — RF-002 final parent review/verification
- `DBG-RVW-003-001-001` — RF-003 premature parent review, REWORK on gate order
- `DBG-RVW-003-001-002` — RF-003 final parent attempt, REWORK
- `DBG-RVW-003-001-003` — RF-003 parent attempt, REWORK on trace
- `DBG-RVW-003-001-004` — RF-003 parent attempt, REWORK on mandatory-state trace
- `DBG-RVW-003-001-005` — RF-003 parent attempt, REWORK on issue state
- `DBG-RVW-003-001-006` / `DBG-VER-003-001-001` — RF-003 final parent review/verification
- `DBG-VER-003-001-001` — RF-003 parent verification attempt, FAIL trace-only
- `DBG-VER-003-001-002` — RF-003 fresh parent verification after current-state correction

## Allocated RF-004 wave IDs

- `DBG-IT-001-005` — typed artifact/source/address/stack/inspection iteration
- `DBG-SL-001-005-001` — classified legacy symbol/source/stack oracle
- `DBG-SL-001-005-002` — immutable identity/binding/address/result foundation
- `DBG-SL-001-005-003` — verified artifact index and legacy `.sym` adapter
- `DBG-SL-001-005-004` — exact content-verified source resolver
- `DBG-SL-001-005-005` — snapshot-bound stack service over signed recipe foundation
- `DBG-SL-001-005-006` — epoch-bound inspection integration
- `DBG-SL-001-005-007` — early recipe schema/validator/evaluator foundation
- `DBG-RVW-001-005-001..DBG-RVW-001-005-006` — exact-head Slice reviews
- `DBG-RVW-001-005-001` — Slice 001 initial review, REWORK
- `DBG-RVW-001-005-002` — Slice 002 initial review, REWORK
- `DBG-RVW-001-005-007` — first `dbg.resolver-inspection/1` review, REWORK
- `DBG-RVW-001-005-008` — corrected interface re-review, REWORK
- `DBG-RVW-001-005-009` — interface review attempt 3, REWORK
- `DBG-RVW-001-005-010` — interface review attempt 4, REWORK
- `DBG-RVW-001-005-011` — exact-head Slice review for `DBG-SL-001-005-007`
- `DBG-RVW-001-005-012` — interface review attempt 5, REWORK
- `DBG-RVW-001-005-013` — interface review attempt 6, REWORK
- `DBG-RVW-001-005-014` — interface review attempt 7, REWORK
- `DBG-RVW-001-005-015` — interface review attempt 8, REWORK
- `DBG-RVW-001-005-016` — interface review attempt 9, REWORK
- `DBG-RVW-001-005-017` — interface review attempt 10, REWORK
- `DBG-RVW-001-005-018` — interface review attempt 11, REWORK
- `DBG-RVW-001-005-019` — final interface review, PASS
- `DBG-RVW-001-005-020` — Slice 001 fresh corrective re-review, PASS
- `DBG-RVW-001-005-021` — Slice 002 corrective re-review, REWORK
- `DBG-RVW-001-005-022` — Slice 002 second corrective review, REWORK trace-only
- `DBG-RVW-001-005-023` — Slice 002 review attempt 4, REWORK
- `DBG-RVW-001-005-024` — Slice 002 fresh review after attribute-concealment correction
- `DBG-VER-001-005-001..DBG-VER-001-005-007` — formal Slice verifications
- `DBG-VER-001-005-001` — Slice 001 verification attempt, FAIL trace-only
- `DBG-VER-001-005-008` — Slice 001 reverification attempt 2, FAIL trace-only
- `DBG-VER-001-005-009` — Slice 001 final reverification, PASS
- `DBG-RVW-004-001-001` / `DBG-VER-004-001-001` — RF-004 parent review/verification

Public interface string `dbg.resolver-inspection/1` is a versioned contract identifier rather
than a numeric execution ID. It is produced by `DBG-RF-004` and becomes a satisfied dependency
for RF-005 only after RF-004 parent sign-off and remote publication.
