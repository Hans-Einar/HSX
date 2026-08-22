# DBG-SPR-001 — Debugger Stabilization

- Status: ITERATION 005 ACTIVE — RF-004 SUSPENDED AT ROUTING-C REVIEW REMEDIATION
- Owning track: Debugger
- Root GapAnalysis: `DBG-GAP-001`
- Active corrective GapAnalysis: `DBG-GAP-002`

## Goal

Execute the accepted debugger stabilization program in dependency order while preserving exact
review/verification boundaries and the anti-monolith design.

## Completed iteration 001

- `DBG-IT-001-001` — DAP protocol baseline stabilization
- Slice: `DBG-SL-001-001-001`
- Parent Refactor: `DBG-RF-001`
- Result: complete / independently reviewed / verified / exact-head signed.

## Completed design iteration 002

- `DBG-IT-001-002` — optimal modular debugger DesignAnalysis
- DesignAnalysis: `DBG-DA-001`
- Completed Studies: `DBG-ST-002..DBG-ST-005`
- Follow-up portable-runtime umbrella: `DBG-ST-006`
- Architecture review `DBG-RVW-001-002-001`: REWORK
- Architecture re-review `DBG-RVW-001-002-002`: REWORK
- Final architecture review `DBG-RVW-001-002-003`: PASS at
  `89d95de2d944179219a93895f1ab956f2786a232`

Steering accepted `DBG-A-001..DBG-A-008` as target architecture direction in comment
`5348190806` and froze `DBG-D-001..DBG-D-010` in comment `5356484309`.

## Completed cross-track iteration 003

- `DBG-IT-001-003` — portable debug runtime contract Studies
- Debugger umbrella: `DBG-ST-006`
- HSX coordinator: `HSX-ST-001`, issue #47
- HSX domain Studies: `HSX-ST-002..HSX-ST-008`
- Final review `HSX-RVW-001-001-006`: PASS on exact proposal content `b57e368…`
- Verification `HSX-VER-001-001-001`: PASS
- Steering froze the portable HSX target baseline in #47 comment `5356480919`.

## Completed structural iteration 004

- `DBG-IT-001-004` — controller/gateway first structural wave
- Refactors: `DBG-RF-002`, `DBG-RF-003`
- Frozen shared interface: `dbg.controller-gateway/1.1`
- Steering accepted the remotely published wave complete in issue #38 comment `5362514094`.

## Active iteration 005 — DBG-RF-004

- `DBG-IT-001-005` — typed artifact/source/address/stack/inspection
- Parent Refactor: `DBG-RF-004`
- Parent issue: #38
- Draft integration PR: #50, intentionally still on authoritative `codex/dbg-rf-004`
- Exact product base: `69a54aeb3394d3cd4792bce620748e15bab69f1f`
- Original frozen execution order: `001 -> 002 -> 007 -> 003 -> 004 -> 005 -> 006`
- Signed historical Slices before candidate work: 001, 002, 003, 004 and 007
- Accepted interface baseline: `dbg.resolver-inspection/1.2`
- Candidate bounded projections: `1.3..1.9`, not yet independently accepted as a complete chain
- Frozen candidate: `master/rf004-v13-candidate@514f7f1cdf8420ccaf6ae84d14b20e4d13931cdc`
- Batch005 completion execution: issue #38 comment `5381169826`
- Fresh independent review `DBG-RVW-001-005-037`: **REWORK — Routing C**
- Review comment: issue #38 `5381348250`

### Review-triggered remediation

Steering policy is issue #38 comment `5381273659`.

The frozen candidate review is captured as:

- `DBG-CR-002` — exact candidate evidence snapshot;
- `DBG-GAP-002` — review-gap mapping;
- coordination issue #54.

Findings:

- `DBG-F-027` Medium — checked call-site candidate was not compared against the resolved
  `InstructionRecord.address`;
- `DBG-F-028` Medium — `InspectionService.create` supplied implicit Stack/Location dependencies;
- `DBG-F-029` Low — LocationRow TypeError wording names `UnwindRow`.

Fan-out:

- `DBG-RF-010` / issue #55 — corrective child of RF-004; owns F-027 / Slice005 evidence fence;
- `DBG-RF-011` / issue #56 — corrective child of RF-004; owns F-028 / Slice006 factory seam;
- F-029 remains bounded parent-RF004 Low rework and must not widen either child.

Current remediation branch: `master/rf004-routing-c-remediation`, created from exact frozen
candidate head. The frozen candidate ref itself remains unchanged.

### Reconstruction rule

The remediation branch is a staging/work branch only and must **not** be promoted wholesale.
After corrective review/verification, reconstruct the parent DAG:

1. corrected Slice005 / RF-010 -> fresh independent review -> verification -> exact-head signoff;
2. corrected Slice006 / RF-011 on accepted Slice005 -> fresh review -> verification -> signoff;
3. include the bounded Low correction on the appropriate RF-004 reviewed head;
4. fresh RF-004 interface/product/parent integration review and verification;
5. Steering disposition.

## Iteration 005 non-goals

- no portable HSX runtime/Executive/VM implementation;
- no AVR implementation;
- no production DAP/CLI/VS Code migration;
- no breakpoint/watch ownership (`DBG-RF-005`);
- no lifecycle/stepping (`DBG-RF-006`);
- no RF-007..009 work;
- no hidden fallback/cache/polling/state authority;
- no whole-candidate/remediation-branch promotion that bypasses Slice review boundaries.

## Next gate

Complete Routing-C remediation for `DBG-F-027..029`, execute one aggregate regression gate,
then obtain a **fresh independent exact-head review**. Any new Medium/High/Blocking structural or
public-contract finding returns to Steering rather than creating a second nested remediation
level.

`DBG-RF-005..DBG-RF-009` remain blocked until RF-004 receives parent completion and Steering
acceptance.
