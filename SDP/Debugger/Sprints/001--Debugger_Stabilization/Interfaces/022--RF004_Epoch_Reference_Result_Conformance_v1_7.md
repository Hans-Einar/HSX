# RF-004 Epoch Reference Result Conformance — `dbg.resolver-inspection/1.7`

Status: Steering-refrozen candidate contract. Not promoted/signed.
Authority: issue #38 Steering comment `5380356912`.
Supersedes only the result-envelope projection for epoch-reference-bearing Handle/Scope/Variable values. Interfaces 1.3–1.6 otherwise remain unchanged.

## Purpose

Preserve the signed generic result immutability boundary while allowing RF-004 to publish values that intentionally carry an exact `InspectionContext` / stop epoch.

`EvidenceGrade` is an RF-002 controller contract Enum embedded in the coherent epoch graph. It is not admitted as an arbitrary direct generic payload Enum by RF-004. A package-import side effect that globally adds `EvidenceGrade` to the generic result Enum catalog is therefore non-conformant.

## Frozen rule

Generic `ResolutionResult[T]` / `InspectionResult[T]` remain unchanged. In particular CS-IMM-103 remains authoritative: direct arbitrary/controller Enums such as `EvidenceGrade.PORTABLE` are rejected as generic payload values.

Values whose public identity deliberately includes the exact `InspectionContext` use dedicated immutable envelopes instead:

### `HandleInternResult`

Fields:
- `status: InspectionStatus` limited to `COMPLETE | CORRUPT | STALE`;
- `context: InspectionContext`;
- `handle: DomainHandle | None`;
- `diagnostics: tuple[Diagnostic, ...]`.

Algebra:
- `COMPLETE`: exact-context handle, no diagnostics;
- `CORRUPT` / `STALE`: no handle, one or more diagnostics.

### `ScopeQueryResult`

Fields:
- `status: InspectionStatus`;
- `context: InspectionContext`;
- `value: ScopeSet | None`;
- `diagnostics: tuple[Diagnostic, ...]`.

Algebra:
- `COMPLETE`: exact-context ScopeSet, no diagnostics;
- `PARTIAL`: exact-context ScopeSet plus one or more diagnostics;
- all other statuses: no value and one or more diagnostics.

Every `frame_handle`, scope handle and `ScopeRecord.context` must equal the result context.

### `VariableQueryResult`

Fields mirror `ScopeQueryResult` with `value: VariablePage | None`.

Every page scope handle, variable handle, scope handle and record context must equal the result context.

## Existing dedicated envelopes

Unchanged:
- lifecycle/control: 1.4;
- stack trustworthy-prefix/page: 1.6.

## Generic InspectionResult remains appropriate for

Context-free immutable value results, including:
- RegisterSet;
- EvaluatedValue / ExpressionValue;
- MemoryBlock;
- DisassemblyBlock;
- failure-only responses carrying no reference-bearing value.

## Concurrency and lifetime

Dedicated envelopes do not create ownership. They snapshot immutable references only.
Epoch invalidation remains owned by `InspectionService` / `EpochHandleStore`; a value from an invalidated epoch is stale even though the DTO itself remains immutable.

No generic result, dedicated result or frontend may rebind a handle to a new context/epoch.

## Required conformance

Fresh-process evidence must prove:
1. `EvidenceGrade.PORTABLE` remains rejected as a direct generic InspectionResult and ResolutionResult payload.
2. Handle/Scope/Variable dedicated envelopes accept exact-context values without package import-order side effects.
3. mismatched context/value combinations are rejected by construction.
4. failed outcomes publish no reference-bearing value.
5. PARTIAL Scope/Variable outcomes require a typed value and diagnostics.
6. stale/corrupt handle interning consumes no new identity when failure occurs before allocation.
7. existing signed CS-IMM and RF-004 regression tests remain unchanged/passing.

## Non-responsibilities

This refreeze changes no portable HSX contract, runtime protocol, controller/gateway contract, artifact schema/digest, Executive/VM/AVR behavior or frontend mapping.
