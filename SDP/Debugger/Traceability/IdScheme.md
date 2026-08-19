# Debugger Traceability ID Scheme

Namespace: `DBG`

Stable IDs:

- `DBG-ST-###` — Study
- `DBG-R-###` — requirement
- `DBG-A-###` — architecture boundary/decision
- `DBG-DA-###` — DesignAnalysis
- `DBG-D-###` — detailed design contract/decision
- `DBG-CR-###` — CodeReview
- `DBG-F-<CR>-###` — CodeReview finding (for example `DBG-F-001-004` may be
  abbreviated in review prose as `DBG-F-004` when the owning review is unambiguous)
- `DBG-GAP-###` — GapAnalysis
- `DBG-RF-###` — Refactor workstream
- `DBG-SPR-###` — sprint
- `DBG-IT-###-###` — iteration
- `DBG-SL-###-###-###` — bounded implementation slice
- `DBG-RVW-###-###-###` — independent review record
- `DBG-VER-###-###-###` — verification record

IDs are never recycled after use in traceability, a GitHub issue/PR, or the ledger.

Cross-track references retain their own namespace (`HSX-*`, `AVR-*`).
Legacy `DR-*`/`DG-*` references remain provenance IDs and are mapped to the new stable
track IDs rather than silently renamed in historical documents.
