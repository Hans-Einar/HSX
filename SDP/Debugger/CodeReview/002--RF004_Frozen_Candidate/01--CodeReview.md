# DBG-CR-002 — RF-004 Frozen Candidate Independent Review Snapshot

- Status: **COMPLETE / REWORK ROUTED**
- Parent Refactor: `DBG-RF-004`
- Exact reviewed head: `514f7f1cdf8420ccaf6ae84d14b20e4d13931cdc`
- Independent review: `DBG-RVW-001-005-037`
- Durable review result: issue #38 comment `5381348250`
- Coordination issue: #54
- Review mode: read-only / fresh independent reviewer

## Scope

This CodeReview is an evidence snapshot of the frozen RF-004 candidate after Batch005 completion evidence. It does not redesign the debugger and does not authorize RF-005..009.

Reviewed authority included accepted `dbg.resolver-inspection/1.2`, candidate projections `1.3..1.9`, HSX-D-001..003, HSX-ST-007, Slice005/006 contracts, frozen Debugger design/process/anti-monolith rules, and Batch005 evidence.

## Stable findings

### DBG-F-027 — Medium — CALL proof is not fenced to the checked candidate address

`StackService._checked_call_site()` accepts a resolved `InstructionRecord` without proving `record.address == checked_candidate`. A valid CALL record for another address can therefore authorize fabricated caller continuation.

Observed adversarial evidence: query candidate `0x120`, return valid CALL record at `0x124`; frozen candidate produced COMPLETE with caller frame at `0x120`.

Required result: mismatch must terminate `CORRUPT / call_site_index_contract`, preserve only the already-proven stack prefix, and perform no caller-SP/frame-base/GPR work after mismatch.

Ownership: Slice005 / StackService. Proposed remediation: `DBG-RF-010`.

### DBG-F-028 — Medium — InspectionService factory silently supplies forbidden defaults

`InspectionService.create()` provides default `StackService` and `LocationEvaluator` dependencies. Accepted interface 1.2 requires every composition dependency to be explicit and stored unchanged; no hidden default service is permitted.

Required result: remove both defaults so omission fails at the Python call boundary; explicit injection and existing binding -> capability -> profile-limit precedence remain unchanged.

Ownership: Slice006 factory/composition seam. Proposed remediation: `DBG-RF-011`.

### DBG-F-029 — Low — LocationRow validator diagnostic names the wrong row type

`RecipeComponentValidator.validate_location_row()` raises a TypeError naming `UnwindRow` instead of `LocationRow`.

Ownership: bounded local parent-RF004 cleanup in the already-established recipe foundation. This Low finding must not widen RF-010 or RF-011.

## Positive evidence

- 69 focused candidate tests independently reproduced PASS read-only.
- Batch005 remains useful execution evidence but did not cover F-027/F-028 adversarial boundaries.
- Reviewed diff stayed within `SDP/Debugger/`, `python/hsx_debugger/`, and `python/tests/`.
- No Executive/VM/AVR/DAP/CLI/VS Code/frontend or RF-005..009 product paths changed.
- Frozen candidate branch remained exact and clean.

## Routing decision

Per Steering policy issue #38 comment `5381273659`, verdict is **REWORK — Routing C**.

Route through `DBG-GAP-002`, then fan out into two corrective ownership domains:

- `DBG-RF-010` -> `DBG-F-027`;
- `DBG-RF-011` -> `DBG-F-028`.

`DBG-F-029` is a bounded Low parent correction. RF-004 remains suspended at its review gate until corrective work is independently reviewed, verified, and a fresh exact-head RF-004 review passes.
