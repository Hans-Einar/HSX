# DBG-SPR-001 — Debugger Stabilization

- Status: ITERATION 005 ACTIVE — SLICE 001 SIGNED / SLICE 002 RE-REVIEW
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
`5348190806` and froze `DBG-D-001..DBG-D-010` in comment `5356484309`.

## Completed cross-track iteration

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
- Steering froze the portable HSX target baseline in #47 comment `5356480919` and accepted
  `DBG-ST-006` complete in #38 comment `5356484309`.

## Completed structural iteration

- `DBG-IT-001-004` — controller/gateway first structural wave
- Authorized Refactors: `DBG-RF-002`, `DBG-RF-003`
- Frozen Slices: `DBG-SL-001-004-001`, `DBG-SL-001-004-002`,
  `DBG-SL-001-004-003`
- Frozen shared interface: `dbg.controller-gateway/1.1`
- Existing Executive profile: `hsx.python-debug-legacy/1`
- Steering accepted the remotely published wave complete in issue #38 comment `5362514094`.

## Non-goals for iteration 004

- no portable HSX runtime/Executive/VM implementation;
- no production DAP/CLI/VS Code migration;
- no artifact/inspection/resource/lifecycle/source-step work;
- no work on `DBG-RF-004..DBG-RF-009`.

## Active RF-004 iteration

- `DBG-IT-001-005` — typed artifact/source/address/stack/inspection
- Authorized Refactor: `DBG-RF-004` only
- Frozen interface: `dbg.resolver-inspection/1`
- Frozen Slices: `DBG-SL-001-005-001..DBG-SL-001-005-007`
- Frozen execution order: `001 -> 002 -> 007 -> 003 -> 004 -> 005 -> 006`
- Interface reviews 007..010/012..018: REWORK; `DBG-RVW-001-005-019`: PASS at
  `058c3383593553aa1497d024d41285d44d9c67a8`
- Exact product base: `69a54aeb3394d3cd4792bce620748e15bab69f1f`
- Authority: issue #38 comment `5362514094`
- Dependency clarification: issue #42 comment `5362515750`
- Still blocked: `DBG-RF-005..DBG-RF-009`

Iteration 005 is side-by-side and frontend-neutral. It may add typed identity/address/result,
artifact/index, source resolver, recipe/stack and epoch-inspection modules plus isolated tests.
It may not edit Executive/VM/AVR, migrate DAP/CLI/VS Code, implement resource ownership or
lifecycle/stepping, or change a frozen design/interface.

## Completed iteration 001 exit

`DBG-IT-001-001` closed after worker implementation, independent exact-head review,
verification evidence, traceability updates, and Master exact-head sign-off for
`DBG-RF-001`.

## Iteration 002 exit

`DBG-IT-001-002` closes only when the complete corrected proposal has a fresh exact-head
architecture-review PASS, SDP/traceability/Handoff agree, and the reviewed decision package
is posted to issue #38 with status `awaiting_steering_acceptance`. No `DBG-D-*` acceptance or
Refactor implementation authority is part of this exit.
