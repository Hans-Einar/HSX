# DBG-RF-011 — RF-004 Explicit Inspection Factory Dependencies

- Status: **ACTIVE CORRECTIVE CHILD / IMPLEMENTATION CANDIDATE**
- `corrective_child_of: DBG-RF-004`
- Origin: `DBG-CR-002` -> `DBG-GAP-002`
- Finding: `DBG-F-028` (Medium)
- Issue: #56
- Frozen review baseline: `514f7f1cdf8420ccaf6ae84d14b20e4d13931cdc`

## Objective

Restore the accepted explicit composition contract at the Slice006 factory boundary.

`InspectionService.create()` must require both `stack_service` and `location_evaluator` as explicit arguments. No module-global default service may silently become dependency authority.

## Owned scope

- `python/hsx_debugger/inspection.py` factory signature only;
- dedicated RF-011 public-signature/omission tests;
- SDP evidence for this corrective child.

## Required behavior

1. `stack_service` is a required factory argument;
2. `location_evaluator` is a required factory argument;
3. omission of either/both fails at the ordinary Python call boundary before construction;
4. explicitly supplied objects/classes are stored unchanged;
5. existing first-match validation order remains binding -> capability profile -> profile limits;
6. no hidden cache, default port, default limits, or alternative service is introduced.

## Non-responsibilities

- no lifecycle/state/concurrency redesign;
- no StackService algorithm change;
- no interface refreeze;
- no Executive/VM/AVR/frontend change;
- no RF-005..009 work.

## Verification

Focused tests must prove:

- omission of `stack_service` fails at the Python signature;
- omission of `location_evaluator` fails at the Python signature;
- omission of both fails at the Python signature;
- explicit injection resolves successfully and the service retains exact supplied dependencies;
- binding/profile/limit precedence remains unchanged.

## Review/sign-off

This corrective child requires fresh independent exact-head review, formal verification evidence, and Master sign-off. It is consumed only after the corrected Slice005/RF-010 boundary has converged, preserving the parent RF-004 reconstruction DAG.
