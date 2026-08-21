# DBG-BLK-001-005-001 — RF-004 Typed Enum Immutability Steering Blocker

- Status: **AWAITING STEERING DECISION**
- Refactor/Iteration/Slice: `DBG-RF-004` / `DBG-IT-001-005` / `DBG-SL-001-005-002`
- Frozen interface: `dbg.resolver-inspection/1`
- Triggering review: `DBG-RVW-001-005-026` — REWORK
- Last product head: `0bedb2d110147f3f34c5846d14ee9b9581926f2d`
- Feasibility head: `71b471abc8544fa40b138a12e746b11b94e34e8c`
- Product changes during feasibility: none

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

## Steering decision required

Steering must explicitly choose and refreeze one mutation/representation rule before RF-004 can
continue. Non-exhaustive decision directions are:

1. define closed contract Enum members as immutable atoms under a stated supported-mutation
   model, exclude later reflective/member/class monkey-patching, and bound accepted generic `T`
   to contract-safe DTO/atom types;
2. replace public Enum-bearing result/record fields with a detached immutable value token or
   literal representation and refreeze the affected schemas;
3. otherwise revise the post-construction immutability requirement and its conformance tests.

Master makes no choice and changes no frozen interface. `DBG-RVW-001-005-027`, formal
verification, Slice 007 and every later RF-004 Slice are not started. RF-005..009 remain blocked.
