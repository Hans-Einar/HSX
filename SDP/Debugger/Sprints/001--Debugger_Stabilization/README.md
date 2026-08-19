# DBG-SPR-001 — Debugger Stabilization

- Status: ACTIVE PROGRAM — ITERATION 002 REVIEW PASS / STEERING PACKAGE PENDING
- Owning track: Debugger
- Owning GapAnalysis: `DBG-GAP-001`

## Goal

Execute the accepted debugger stabilization program in dependency order. The first and only
authorized pre-design product activity is `DBG-RF-001`.

## Completed iteration

- `DBG-IT-001-001` — DAP protocol baseline stabilization
- Slice: `DBG-SL-001-001-001`
- Parent Refactor: `DBG-RF-001`

## Active iteration

- `DBG-IT-001-002` — optimal modular debugger DesignAnalysis
- DesignAnalysis: `DBG-DA-001`
- Completed Studies: `DBG-ST-002..DBG-ST-005`
- Proposed required follow-up: `DBG-ST-006`
- Architecture review `DBG-RVW-001-002-001`: REWORK
- Architecture re-review `DBG-RVW-001-002-002`: REWORK
- Final architecture review `DBG-RVW-001-002-003`: PASS at
  `89d95de2d944179219a93895f1ab956f2786a232`
- Stop gate: issue #38 Steering acceptance

## Non-goals for this iteration

- no `DBG-DA-001` analysis before `DBG-RF-001` exact-head sign-off;
- no structural debugger product refactor;
- no work on `DBG-RF-002..DBG-RF-009`.

## Completed iteration 001 exit

`DBG-IT-001-001` closed after worker implementation, independent exact-head review,
verification evidence, traceability updates, and Master exact-head sign-off for
`DBG-RF-001`.

## Iteration 002 exit

`DBG-IT-001-002` closes only when the complete corrected proposal has a fresh exact-head
architecture-review PASS, SDP/traceability/Handoff agree, and the reviewed decision package
is posted to issue #38 with status `awaiting_steering_acceptance`. No `DBG-D-*` acceptance or
Refactor implementation authority is part of this exit.
