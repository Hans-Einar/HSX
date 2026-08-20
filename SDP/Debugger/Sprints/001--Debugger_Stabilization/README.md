# DBG-SPR-001 — Debugger Stabilization

- Status: ITERATION 003 MASTER SIGN-OFF PASS — ISSUE PACKAGES NEXT
- Owning track: Debugger
- Owning GapAnalysis: `DBG-GAP-001`

## Goal

Execute the accepted debugger stabilization program in dependency order. The first and only
authorized pre-design product activity is `DBG-RF-001`.

## Completed iteration

- `DBG-IT-001-001` — DAP protocol baseline stabilization
- Slice: `DBG-SL-001-001-001`
- Parent Refactor: `DBG-RF-001`

## Completed design iteration

- `DBG-IT-001-002` — optimal modular debugger DesignAnalysis
- DesignAnalysis: `DBG-DA-001`
- Completed Studies: `DBG-ST-002..DBG-ST-005`
- Authorized follow-up: `DBG-ST-006`
- Architecture review `DBG-RVW-001-002-001`: REWORK
- Architecture re-review `DBG-RVW-001-002-002`: REWORK
- Final architecture review `DBG-RVW-001-002-003`: PASS at
  `89d95de2d944179219a93895f1ab956f2786a232`
- Stop gate: issue #38 Steering acceptance

Steering accepted `DBG-A-001..DBG-A-008` as target architecture direction in comment
`5348190806`; all `DBG-D-*` remain proposed.

## Active cross-track iteration

- `DBG-IT-001-003` — portable debug runtime contract Studies
- Debugger umbrella: `DBG-ST-006`
- HSX coordinator: `HSX-ST-001`, issue #47
- HSX domain Studies: `HSX-ST-002..HSX-ST-008`
- Review `HSX-RVW-001-001-001`: REWORK
- Review `HSX-RVW-001-001-002`: REWORK
- Review `HSX-RVW-001-001-003`: REWORK
- Review `HSX-RVW-001-001-004`: REWORK
- Supplemental Studies `HSX-ST-007`, `HSX-ST-008`: complete and resynthesized
- Review `HSX-RVW-001-001-005`: REWORK at `84df21d763b73209efd0292990799f469283460a`
- Review `HSX-RVW-001-001-006`: PASS on exact proposal content `b57e368…` plus trace-only
  assignment head `24beb82…`
- Verification `HSX-VER-001-001-001`: PASS
- Stop gate: Master exact-content sign-off and reviewed/verified decision packages in issues
  #47/#38 before any `DBG-D-*` freeze

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
