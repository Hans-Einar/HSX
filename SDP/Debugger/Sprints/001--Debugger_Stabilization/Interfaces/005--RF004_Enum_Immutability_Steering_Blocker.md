# DBG-BLK-001-005-001 — RF-004 Typed Enum Immutability Steering Blocker

- Status: **CLOSED — STEERING REFREEZE / REVIEW 030 PASS**
- Refactor/Iteration/Slice: `DBG-RF-004` / `DBG-IT-001-005` / `DBG-SL-001-005-002`
- Frozen interface at discovery: `dbg.resolver-inspection/1`
- Steering resolution: `dbg.resolver-inspection/1.1`
- Triggering review: `DBG-RVW-001-005-026` — REWORK
- Last product head: `0bedb2d110147f3f34c5846d14ee9b9581926f2d`
- Feasibility head: `71b471abc8544fa40b138a12e746b11b94e34e8c`
- Product changes during feasibility: none
- Steering escalation: issue #38 comment `5365959417`
- Steering refreeze: issue #38 comment `5368017338`
- Published refreeze content head: `94a59f3738fadc0b6230fc3dc69cf36ca8b9202e`
- Corrected refreeze content head: `4c581a740ee95c3362aa77de85630ba001013e1c`
- Trace-corrected refreeze head: `ae49435ebb24198ad1fb2017e5998bbad305792f`

## Frozen contradiction

Interface 004 section 7 simultaneously requires:

1. every result is immutable after construction;
2. `ResolutionResult[T].values` and `InspectionResult[T].value` retain exact typed `T` values;
3. status fields and multiple public record fields use exact closed Enum types.

In Python an exact Enum member is its class-owned canonical singleton. Constructor lookup,
`copy.copy` and `copy.deepcopy` retain that same member. Keeping exact type/member identity
therefore keeps shared member and class behavior; a later member, class-property or referenced
property-state change is observable through an already accepted result. A distinct forged
instance is not the canonical member and still shares class descriptors. A proxy, wrapper,
scalar or cloned type changes the frozen public representation. Global sealing changes caller-
owned types, is non-portable and does not provide the absolute guarantee under reflective
mutation. Revalidation cannot revoke a reference already returned.

The same conflict applies to Enum status fields and Enum fields nested in public frozen DTOs.
Copying the outer DTO only retains the same Enum singleton.

## Evidence

- `DBG-RVW-001-005-026` independently reproduced post-construction observable changes after all
  pre-construction storage and canonical metadata checks passed.
- Fresh corrective-feasibility worker reproduced singleton copy/deepcopy identity, noncanonical
  forged instances, shared class-property behavior, external property state, status Enum and
  nested public DTO cases.
- Worktree, local/tracking/live remote remain clean and exact at `71b471a…`; feasibility made no
  product, test, interface or SDP change.

## Steering decision

Steering selected the supported-mutation direction in comment `5368017338`:

1. public DTO/result schemas and exact typed Enum members remain unchanged;
2. closed contract Enums are contract-safe immutable atoms under the supported mutation model;
3. generic/nested payloads are bounded to recursively contract-safe immutable values;
4. reflection/type-system mutation is outside conformance.

Master refreezes only those semantics as `1.1` plus `DBG-CF-001-005-001`. Review 028 returned
REWORK; review 029 passed contract semantics but returned REWORK trace-only. Fresh interface
review `DBG-RVW-001-005-030` passed at `ae49435…`. Historical review 026 remains REWORK; review
027 is reserved only for the later post-refreeze product head. RF-005..009 remain blocked.
