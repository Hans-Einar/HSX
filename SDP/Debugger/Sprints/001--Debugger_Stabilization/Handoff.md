# DBG-SPR-001 Handoff

Status: `rf004_trace_only_correction_applied_awaiting_rereview039`

## Current gate

`DBG-RF-004` is **SUSPENDED AT `awaiting_fresh_independent_rereview_DBG-RVW-001-005-039`**.

Frozen candidate authority remains:

- branch: `master/rf004-v13-candidate`
- exact frozen head: `514f7f1cdf8420ccaf6ae84d14b20e4d13931cdc`
- Batch005 completion result: issue #38 comment `5381169826`
- independent review: `DBG-RVW-001-005-037`
- review result: **REWORK — Routing C**
- review comment: issue #38 `5381348250`
- remediation review: `DBG-RVW-001-005-038`
- exact remediation-reviewed head: `010ff7bea3c414d73f63c87580d0e91c76c8b965`
- remediation-review result: **REWORK — RETURN_TO_STEERING** for trace/current-state only
- remediation-review comment: issue #54 `5381873491`
- Steering disposition: bounded trace-only correction, no second nesting, issue #54 `5382237149`
- PR #50 remains Draft on authoritative `codex/dbg-rf-004`; the candidate branch is not promoted wholesale.

Current remediation work is isolated on:

- branch: `master/rf004-routing-c-remediation`
- origin: exact frozen head `514f7f1cdf8420ccaf6ae84d14b20e4d13931cdc`
- coordination CodeReview/Gap issue: #54
- child Refactor #55: `DBG-RF-010`
- child Refactor #56: `DBG-RF-011`

`DBG-RF-005..DBG-RF-009` remain blocked. No Executive/VM/AVR/DAP/CLI/VS Code/frontend migration is authorized.

## Why RF-004 is suspended now

Origin review `DBG-RVW-001-005-037` found three product findings:

1. `DBG-F-027` — **Medium** — CALL proof was not fenced to the exact checked call-site address.
2. `DBG-F-028` — **Medium** — `InspectionService.create` supplied forbidden implicit composition defaults.
3. `DBG-F-029` — **Low** — LocationRow validator TypeError names `UnwindRow`.

The bounded F-029 worker correction completed at
`1bc99e0f7b986de3878c88e75c1f1d927974679c`. Routing-C aggregate execution already completed
with PASS classification at exact product/test head
`045f1cf58beaf393680e1f4118cfa76de65220b2`; the execution report is issue #54 comment
`5381602329`.

Review038 technically closed all three origin findings:

- `DBG-F-027` / RF-010 — technically closed;
- `DBG-F-028` / RF-011 — technically closed;
- `DBG-F-029` / bounded parent correction — technically closed.

Review038 returned `REWORK — RETURN_TO_STEERING` solely for two trace/current-state findings:

- `DBG-F-030` — aggregate execution was incorrectly represented as formal verification under
  invalid identity `DBG-VER-ROUTING-C-AGGREGATE`;
- `DBG-F-031` — this Handoff and the Sprint README still routed the already-completed F-029
  worker and aggregate tester work.

Steering comment `5382237149` authorized only the bounded six-file trace correction. No
product, interface, state, concurrency, ownership, runtime or architecture defect was found.

## Nested remediation model

Durable policy: issue #38 comment `5381273659`.

The review is captured as:

- `DBG-CR-002` — `SDP/Debugger/CodeReview/002--RF004_Frozen_Candidate/01--CodeReview.md`
- `DBG-GAP-002` — `SDP/Debugger/GapAnalysis/002--RF004_Review_Remediation/01--GapAnalysis.md`

Medium findings fan out by ownership:

- `DBG-RF-010` / #55 — Slice005 exact CALL-site evidence fence for `DBG-F-027`;
- `DBG-RF-011` / #56 — Slice006 explicit InspectionService factory dependencies for `DBG-F-028`.

`DBG-F-029` remains a bounded parent-RF004 Low correction and must not widen either corrective child.

This is one nested remediation level only. `DBG-F-030` and `DBG-F-031` are owned directly by
the suspended parent RF-004 review gate. They do not create CR-003, GAP-003, RF-012 or any
second corrective tree.

## Corrective implementation state

The product corrections are technically closed by review038. Formal reconstructed Slice
review, verification and exact-head signoff remain mandatory.

### DBG-RF-010

Implemented on `master/rf004-routing-c-remediation`:

- `stack.py` now requires exact `record.address == checked_candidate` before `prove_call`;
- mismatch returns `CORRUPT / call_site_index_contract`;
- rejection occurs before caller-SP/frame-base/GPR recovery;
- dedicated adversarial test `test_hsx_debugger_rf010_call_site_fence.py` is present;
- no interface/HSX/runtime/frontend change.

Review038 confirmed technical closure. RF-010 remains formally unverified and unsigned; this
review is not the reconstructed formal Slice005 gate.

### DBG-RF-011

Implemented on the same remediation branch:

- `InspectionService.create` now requires explicit `stack_service` and `location_evaluator` arguments;
- no factory default composition dependency remains;
- dedicated signature/omission test `test_hsx_debugger_rf011_factory_dependencies.py` is present;
- lifecycle/state/concurrency and binding -> profile -> limits validation are unchanged.

Review038 confirmed technical closure. RF-011 remains formally unverified and unsigned; this
review is not the reconstructed formal Slice006 gate.

### DBG-F-029

Technically closed by review038. The bounded worker correction is commit
`1bc99e0f7b986de3878c88e75c1f1d927974679c`; the LocationRow assertion is an ordinary PASS
and the former P002 strict XFAIL is gone. The F-029 worker must **not** be re-dispatched.

## Required next sequence

1. Obtain fresh independent rereview `DBG-RVW-001-005-039` of this six-file trace-only head,
   with current gate `awaiting_fresh_independent_rereview_DBG-RVW-001-005-039`.
2. Do **not** re-dispatch the F-029 worker.
3. Do **not** repeat aggregate product/test execution unless product or test code changes;
   exact aggregate-tested authority remains `045f1cf58beaf393680e1f4118cfa76de65220b2`.
4. If review039 passes, reconstruct/promote in the original parent DAG rather than promoting
   the remediation branch wholesale:
   - corrected Slice005/RF-010 -> formal verification -> exact-head signoff;
   - corrected Slice006/RF-011 on accepted Slice005 -> fresh review -> formal verification ->
     exact-head signoff;
   - bounded F-029 correction included in the appropriate RF-004 reviewed head;
   - fresh RF-004 parent review -> verification -> exact-head signoff -> Steering disposition.
5. Only after RF-004 acceptance may RF-005 become eligible.

## Frozen contracts that remain authoritative

- accepted debugger architecture/design baseline `DBG-D-001..010`;
- accepted portable HSX `HSX-D-001..005` and `HSX-ST-007` ABI/recipe evidence;
- signed first structural wave `DBG-RF-002` / `DBG-RF-003` and `dbg.controller-gateway/1.1`;
- RF-004 accepted baseline `dbg.resolver-inspection/1.2`;
- candidate-only bounded projections `1.3..1.9`, pending independent acceptance as a complete chain;
- Slice005/006 reconstruction rules in candidate Interfaces 031/032;
- review-triggered nested remediation policy in issue #38 comment `5381273659`.

No finding in `DBG-RVW-001-005-037` requires a new architecture decision or public-interface refreeze. Both Medium findings are implementation conformance defects against already frozen contracts.

## Known baseline/degraded evidence

The broad Python suite may still contain only these accepted unrelated baseline failures:

- `python/tests/test_hsx_dbg_commands.py::test_break_add_symbol_line` — ignored/generated demo `.sym` absent;
- `python/tests/test_shell_client.py::test_pretty_dmesg_assigns_session_numbers` — optional-tabulate formatting baseline.

The former candidate P002 strict XFAIL is removed and its assertion passed in aggregate
execution. No other candidate XFAIL/skip is authorized except previously classified
platform-specific skips.

## Durable coordination

- parent issue / Steering: #38
- `DBG-CR-002` / `DBG-GAP-002`: #54
- `DBG-RF-010`: #55
- `DBG-RF-011`: #56
- review038: issue #54 comment `5381873491`
- Steering trace-only disposition: issue #54 comment `5382237149`
- next gate: `awaiting_fresh_independent_rereview_DBG-RVW-001-005-039`
- PR #50: Draft, intentionally not candidate/remediation authority

A fresh agent should read this Handoff, `SDP/Shared/Process.md`, CurrentIndex/Issues/Relations, issues #38/#54/#55/#56, then the CR/GAP/child-Refactor documents before acting.
