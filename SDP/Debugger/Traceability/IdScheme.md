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
- `DBG-VER-001-004-001..DBG-VER-001-004-003` — formal Slice verifications
- `DBG-RVW-002-001-001` / `DBG-VER-002-001-001` — RF-002 parent final review/verification
- `DBG-RVW-003-001-001` / `DBG-VER-003-001-001` — RF-003 parent final review/verification
