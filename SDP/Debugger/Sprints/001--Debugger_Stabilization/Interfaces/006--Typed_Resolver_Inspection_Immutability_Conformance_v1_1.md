# DBG-CF-001-005-001 — `dbg.resolver-inspection/1.1` Immutability Conformance

- Status: **CONTRACT PASS / TRACE-CORRECTED CANDIDATE / REVIEW 030 PENDING**
- Authority: issue #38 comment `5368017338`
- Interface: `dbg.resolver-inspection/1.1`
- Scope: supported-mutation and recursively contract-safe immutable semantics only
- Public schema delta from version `1`: none

## Contract-safe accepted values

The generic/result boundary accepts only recursively contract-safe immutable values:

- exact immutable scalars and `bytes`;
- exact canonical members of closed contract Enum types named by Interface 004, when their
  schema-visible value is recursively contract-safe;
- frozen public value/identity DTOs whose declared fields are recursively contract-safe;
- tuples and frozensets containing only recursively contract-safe values;
- explicitly frozen value objects admitted by a named Interface 004 schema.

Caller-owned lists, dicts, sets or other mutable containers must be copied/normalized before
publication: list to same-order tuple, dict to insertion-ordered tuple of recursively frozen
`(key, value)` tuples, and set to frozenset. No unnamed read-only mapping is published. Mutable
implementation records, arbitrary caller Enums, objects with mutable non-schema state and
unapproved duck-typed DTOs are rejected.

The closed Enum projection types already owned by Slice 002 are exactly:

- `SnapshotStability`;
- `ByteOrder`, `WrapPolicy`, `AddressArithmeticMode` and `Permission` (`ArithmeticMode` is an
  alias of `AddressArithmeticMode`, not another type);
- `ResolutionStatus`, `InspectionStatus`, `ContextBindingStatus`, `InspectionOpenStatus`,
  `InvalidationStatus`, `ServiceCloseStatus`, `AddressStatus`, `ValueAvailability`,
  `ValuePieceStatus`, `ExpressionKind` and `MemorySegmentStatus`;
- `SymbolKind`, `TypeKind` and `InstructionClassification`.

Later RF-004 Slices may admit only their exact public Enum projection classes whose member sets
are already named by Interface 004; they must add those types to the same private approval
registry and conformance matrix before publishing them. A test-only or caller-defined Enum is
never implicitly approved by subclassing `Enum` or by using scalar values.

## Required positive fixtures

| ID | Construction | Required observation |
|---|---|---|
| `CS-IMM-001` | Result/status/public DTO contains a closed contract Enum | Exact Enum type and canonical member identity are preserved. |
| `CS-IMM-002` | Caller supplies a list that is normalized to a tuple | Later ordinary list mutation does not change the accepted result. |
| `CS-IMM-003` | Caller supplies a dict/set admitted for normalization | Dict becomes an insertion-ordered tuple of frozen `(key, value)` tuples; set becomes frozenset; later ordinary source mutation changes neither result. |
| `CS-IMM-004` | Nested tuple/frozenset/frozen public DTO graph | Every declared field remains stable after ordinary mutation of all original caller containers. |
| `CS-IMM-005` | Result and nested frozen DTO fields | Supported field reassignment raises the normal frozen/attribute error. |
| `CS-IMM-006` | Closed contract Enum with scalar or recursively contract-safe tuple value | Construction succeeds without clone/proxy/token replacement. |
| `CS-IMM-007` | Existing public identity/address/result/metadata DTO set | Version `1` exact field types, equality and Enum identity remain unchanged. |
| `CS-IMM-008` | Caller-owned mutable construction record is admitted for normalization to a named frozen public DTO | Later ordinary mutation of the source record does not change the published DTO/result. |

## Required rejection fixtures

| ID | Construction | Required outcome |
|---|---|---|
| `CS-IMM-101` | Mutable implementation record is supplied as a generic payload | Construction/classification rejects it; no reference is published. |
| `CS-IMM-102` | Mutable or non-frozen duck-typed DTO is supplied | Reject. |
| `CS-IMM-103` | Arbitrary caller Enum or custom Enum whose schema-visible value is mutable/non-contract-safe | Reject. |
| `CS-IMM-104` | Frozen DTO contains a mutable/non-contract-safe declared field | Reject recursively. |
| `CS-IMM-105` | Nested container graph contains a mutable/non-contract-safe leaf or cycle | Reject with no partial publication. |

## Explicit non-conformance cases

These operations are outside the supported mutation model and no fixture may use them to fail
snapshot immutability:

- cloning an Enum or requiring result isolation through a cloned/proxy/wrapper/token member;
- monkey-patching/rebinding an Enum class, member, descriptor or module/class definition;
- editing Enum runtime internals such as `_member_map_`, `_value_` or metadata storage;
- using `object.__setattr__` or equivalent reflection/runtime bypass against frozen values;
- observing mutable external/global state solely through a non-contract custom property;
- replacing Python type-system/runtime objects after result construction.

Tests may validate that arbitrary/custom Enum types are outside the approved generic boundary,
but they must do so at construction time. They must not mutate an approved closed contract Enum
or Python type definition after acceptance and call that a snapshot-isolation failure.

## Review and product gates

Review `DBG-RVW-001-005-028` returned REWORK for unnamed mapping output and stale review-027
allocation text. Review 029 confirmed those technical closures but returned REWORK trace-only
for two stale Relations gates. Fresh `DBG-RVW-001-005-030` reviews the unchanged corrected
matrix/interface semantics plus reconciled trace. Product
implementation remains stopped until that review passes. After PASS, a fresh Slice 002 worker
updates only its existing owned files and test fixtures; historical `DBG-RVW-001-005-026`
remains REWORK, and `DBG-RVW-001-005-027` reviews only the new post-refreeze product head.
