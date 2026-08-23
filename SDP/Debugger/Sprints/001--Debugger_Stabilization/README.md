# DBG-SPR-001 — Debugger Stabilization

- Status: ITERATION 005 ACTIVE — RF-004 SUSPENDED AT `awaiting_fresh_independent_rereview_DBG-RVW-001-005-040`
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
- Bounded F-029 worker correction: complete at `1bc99e0f7b986de3878c88e75c1f1d927974679c`
- Routing-C aggregate execution: PASS at exact product/test head
  `045f1cf58beaf393680e1f4118cfa76de65220b2`, issue #54 comment `5381602329`
- Remediation review `DBG-RVW-001-005-038`: **REWORK — RETURN_TO_STEERING** for trace/current-state only
- Review038 head/comment: `010ff7bea3c414d73f63c87580d0e91c76c8b965` / issue #54 `5381873491`
- Steering disposition: bounded trace-only correction, no second nesting, issue #54 `5382237149`

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

Review038 technically closed F-027, F-028 and F-029. Review039 closed trace finding F-030 and
returned one residual routing omission under the existing F-031 identity. That omission is now
corrected and awaits review040. RF-010/RF-011 remain formally unverified and unsigned pending
their reconstructed formal gates.

### Review038 bounded trace correction

Steering assigned F-030 and F-031 directly to the suspended parent RF-004 review gate. Review039
closed F-030. Steering comment `5385170864` retained F-031 for its residual post-review route
omission and authorized one consolidated six-file correction followed by review040. No CR-003,
GAP-003, RF-012, F-032 or second nested remediation exists. The F-029 worker must not be
re-dispatched and aggregate product/test execution must not be repeated unless product/test
code changes.

Current remediation branch: `master/rf004-routing-c-remediation`, created from exact frozen
candidate head. The frozen candidate ref itself remains unchanged.

### Reconstruction rule

The remediation branch is a staging/work branch only and must **not** be promoted wholesale.
After corrective review/verification, reconstruct the parent DAG:

1. corrected Slice005 / RF-010 -> fresh independent review -> formal verification -> exact-head signoff;
2. corrected Slice006 / RF-011 on signed Slice005 -> fresh independent review -> formal
   verification -> exact-head signoff;
3. include the bounded Low correction on the appropriate RF-004 reviewed head;
4. fresh independent RF-004 interface/product/parent integration review -> formal verification
   -> exact-head signoff;
5. Steering disposition; RF-005..009 remain blocked until that parent acceptance.

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

Obtain fresh independent trace-only rereview `DBG-RVW-001-005-040` of the consolidated six-file
correction; the current gate is
`awaiting_fresh_independent_rereview_DBG-RVW-001-005-040`. Reviewer040 must confirm review039
closure of F-030, correction of the sole actionable F-031 routing omission, append-only Ledger
semantics, zero product/test drift after `045f1cf...`, unsigned child state and the preserved
reconstruction DAG. Do not re-dispatch the F-029 worker or repeat aggregate product/test
execution unless product/test code changes.

If review040 passes, return to the existing reconstruction sequence: RF-010/Slice005 -> fresh
independent review -> formal verification -> exact-head signoff; then RF-011/Slice006 on signed
Slice005 -> fresh independent review -> formal verification -> exact-head signoff; integrate the
bounded F-029 correction into the appropriate RF-004 reconstruction; then parent RF-004 -> fresh
independent review -> formal verification -> exact-head signoff -> Steering disposition.

`DBG-RF-005..DBG-RF-009` remain blocked until RF-004 receives parent completion and Steering
acceptance.
