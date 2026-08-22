# DBG-SPR-001 Handoff

Status: `rf004_routing_c_remediation_active`

## Current gate

`DBG-RF-004` is **SUSPENDED AT FRESH INDEPENDENT REVIEW REWORK**.

Frozen candidate authority remains:

- branch: `master/rf004-v13-candidate`
- exact frozen head: `514f7f1cdf8420ccaf6ae84d14b20e4d13931cdc`
- Batch005 completion result: issue #38 comment `5381169826`
- independent review: `DBG-RVW-001-005-037`
- review result: **REWORK — Routing C**
- review comment: issue #38 `5381348250`
- PR #50 remains Draft on authoritative `codex/dbg-rf-004`; the candidate branch is not promoted wholesale.

Current remediation work is isolated on:

- branch: `master/rf004-routing-c-remediation`
- origin: exact frozen head `514f7f1cdf8420ccaf6ae84d14b20e4d13931cdc`
- coordination CodeReview/Gap issue: #54
- child Refactor #55: `DBG-RF-010`
- child Refactor #56: `DBG-RF-011`

`DBG-RF-005..DBG-RF-009` remain blocked. No Executive/VM/AVR/DAP/CLI/VS Code/frontend migration is authorized.

## Why RF-004 is suspended

Fresh GPT-5.6 independent review found three stable findings:

1. `DBG-F-027` — **Medium** — CALL proof was not fenced to the exact checked call-site address.
2. `DBG-F-028` — **Medium** — `InspectionService.create` supplied forbidden implicit composition defaults.
3. `DBG-F-029` — **Low** — LocationRow validator TypeError names `UnwindRow`.

The review reproduced 69 focused tests PASS read-only, so these are boundary gaps missed by the green Batch005 matrix rather than broad instability.

## Nested remediation model

Durable policy: issue #38 comment `5381273659`.

The review is captured as:

- `DBG-CR-002` — `SDP/Debugger/CodeReview/002--RF004_Frozen_Candidate/01--CodeReview.md`
- `DBG-GAP-002` — `SDP/Debugger/GapAnalysis/002--RF004_Review_Remediation/01--GapAnalysis.md`

Medium findings fan out by ownership:

- `DBG-RF-010` / #55 — Slice005 exact CALL-site evidence fence for `DBG-F-027`;
- `DBG-RF-011` / #56 — Slice006 explicit InspectionService factory dependencies for `DBG-F-028`.

`DBG-F-029` remains a bounded parent-RF004 Low correction and must not widen either corrective child.

This is one nested remediation level only. Any new structural/public-contract problem found inside RF-010/RF-011 returns to Steering instead of recursively nesting another corrective tree.

## Corrective implementation state

Master corrective implementation is permitted by the Routing-C handoff while fresh independent review and verification remain mandatory.

### DBG-RF-010

Implemented on `master/rf004-routing-c-remediation`:

- `stack.py` now requires exact `record.address == checked_candidate` before `prove_call`;
- mismatch returns `CORRUPT / call_site_index_contract`;
- rejection occurs before caller-SP/frame-base/GPR recovery;
- dedicated adversarial test `test_hsx_debugger_rf010_call_site_fence.py` is present;
- no interface/HSX/runtime/frontend change.

### DBG-RF-011

Implemented on the same remediation branch:

- `InspectionService.create` now requires explicit `stack_service` and `location_evaluator` arguments;
- no factory default composition dependency remains;
- dedicated signature/omission test `test_hsx_debugger_rf011_factory_dependencies.py` is present;
- lifecycle/state/concurrency and binding -> profile -> limits validation are unchanged.

### DBG-F-029

Not yet closed in this handoff revision. It is intentionally reserved as the tiny Low worker exercise allowed by the nested-remediation policy. Any worker may change only the incorrect LocationRow TypeError wording and its strict-XFAIL guard. A changed head must receive fresh independent review; the original reviewer cannot self-approve its own patch.

## Required next sequence

1. Synchronize current traceability for `DBG-CR-002`, `DBG-GAP-002`, `DBG-RF-010`, `DBG-RF-011`, `DBG-F-027..029` and the suspended RF-004 gate.
2. Dispatch one bounded Low WORKER for `DBG-F-029` only, or have Master perform it if usage conservation is preferred; do not combine it with Medium code ownership.
3. Run one aggregate read-only TESTER batch over RF-010/RF-011/F-029 plus the complete Batch005 regression matrix.
4. If execution is clean, obtain fresh independent exact-head review. The reviewer must check the two adversarial Medium boundaries, Low closure, child ownership and no contract drift.
5. Reconstruct/promote in the original parent DAG rather than promoting the remediation branch wholesale:
   - corrected Slice005/RF-010 -> independent review -> verification -> sign-off;
   - corrected Slice006/RF-011 on accepted Slice005 -> independent review -> verification -> sign-off;
   - bounded Low correction included in the appropriate RF-004 reviewed head;
   - fresh RF-004 parent/interface/product review -> verification -> exact-head sign-off.
6. Return to Steering. Only after RF-004 acceptance may RF-005 become eligible.

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

The candidate P002 strict XFAIL corresponds to `DBG-F-029` and must disappear when that Low finding is closed. No other candidate XFAIL/skip is authorized except previously classified platform-specific skips.

## Durable coordination

- parent issue / Steering: #38
- `DBG-CR-002` / `DBG-GAP-002`: #54
- `DBG-RF-010`: #55
- `DBG-RF-011`: #56
- PR #50: Draft, intentionally not candidate/remediation authority

A fresh agent should read this Handoff, `SDP/Shared/Process.md`, CurrentIndex/Issues/Relations, issues #38/#54/#55/#56, then the CR/GAP/child-Refactor documents before acting.
