# DBG-SPR-001 — Debugger Stabilization

- Status: ACTIVE — ISSUE #36 ACCEPTED
- Owning track: Debugger
- Owning GapAnalysis: `DBG-GAP-001`

## Goal

Execute the accepted debugger stabilization program in dependency order. The first and only
authorized pre-design product activity is `DBG-RF-001`.

## Active iteration

- `DBG-IT-001-001` — DAP protocol baseline stabilization
- Slice: `DBG-SL-001-001-001`
- Parent Refactor: `DBG-RF-001`

## Non-goals for this iteration

- no `DBG-DA-001` analysis before `DBG-RF-001` exact-head sign-off;
- no structural debugger product refactor;
- no work on `DBG-RF-002..DBG-RF-009`.

## Sprint exit for the current gate

The current iteration closes only after worker implementation, independent exact-head
review, verification evidence, traceability updates, and Master exact-head sign-off for
`DBG-RF-001`. The Master then stops; issue #38 / `DBG-DA-001` is the next gate.
