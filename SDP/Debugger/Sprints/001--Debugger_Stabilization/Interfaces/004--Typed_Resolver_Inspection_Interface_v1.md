# `dbg.resolver-inspection/1` — Typed Resolver and Inspection Interface

- Status: **FROZEN FOR `DBG-RF-004` IMPLEMENTATION REVIEW**
- Iteration: `DBG-IT-001-005`
- Parent Refactor: `DBG-RF-004`
- Steering authority: issue #38 comment `5362514094`
- Dependency clarification: issue #42 comment `5362515750`
- Frozen design: `DBG-D-003`, `DBG-D-004`, `DBG-D-009`
- Portable contracts: `HSX-D-001..HSX-D-003`, especially `HSX-D-002`
- Planned independent interface review: `DBG-RVW-001-005-007`
- Public interface ID: `dbg.resolver-inspection/1`

This document freezes the public Python-domain interface to be implemented by the six bounded
RF-004 Slices. It is frontend-neutral and side-by-side: it does not migrate DAP, CLI, VS Code,
the Executive, VM, or AVR paths.

Any implementation discovery that requires changing an identity field, coherence rule,
address rule, result category, ownership boundary, or public method below stops the active
Slice and returns to Master/Steering. Additive private helpers are allowed only when they do
not change observable semantics.

## 1. Boundary and module ownership

The target package remains `python/hsx_debugger/`, but RF-004 must preserve these responsibility
boundaries:

| Module boundary | Owns | Must not own |
|---|---|---|
| `identity.py` | Immutable target, image, artifact, bundle, binding, stop and snapshot references | Parsing, filesystem lookup, target reads, frontend IDs |
| `addresses.py` | Address-space descriptors, typed addresses/ranges, checked arithmetic and formatting | Symbol lookup, masks hidden in adapters, memory reads |
| `results.py` | Typed resolver/inspection statuses, diagnostics and immutable result envelopes | Service algorithms or policy fallbacks |
| `artifacts.py` | Verified bundle/component parsing and immutable debug indexes | Local source selection, live reads, stack walking, frontend mapping |
| `legacy_symbols.py` | Explicit `hsx.python-debug-legacy/1` `.sym` adaptation behind classified evidence | Portable conformance claims, implicit masks/case/basename policy |
| `sources.py` | Exact source identity and content-verified locator resolution | Symbol parsing, target state, UI navigation |
| `recipes.py` | Bounded unwind/location recipe validation and evaluation | Stack traversal policy, raw live reads, implicit ABI guesses |
| `stack.py` | Snapshot-bound unwind/stack reconstruction and partial diagnostics | Artifact parsing, frontend frames, fixed R7 fallback |
| `inspection.py` | Epoch-bound registers/scopes/variables/memory/disassembly composition | Run control, transport retry, artifact parsing, frontend/DAP policy |
| `handles.py` | Domain handle allocation/validation for one StopEpoch | DAP integer allocation or lifetime ownership |

No module may combine artifact parsing/indexing, filesystem source resolution, unwind/stack,
epoch inspection, and frontend mapping. `python/hsx_debugger/contracts.py`, controller, gateway,
ExecutiveSession, existing DAP/CLI and VS Code files are read-only in RF-004 unless a later
Steering refreeze explicitly changes ownership.

## 2. Exact evidence tuple

Every successful or partial inspection result carries one immutable `InspectionContext`:

```text
InspectionContext {
  target: TargetRef,
  image: LoadedImageRef,
  stop_epoch_id: StopEpochId,
  stop_token: StopToken,
  snapshot: InspectionSnapshotRef,
}
```

Construction fails unless all embedded identities agree exactly:

- `LoadedImageRef.target == TargetRef`;
- snapshot TargetRef and LoadedImageRef equal the context refs;
- StopEpoch target/image/generation and snapshot refs equal the context refs;
- transition and inspection revisions are non-negative and exact;
- snapshot stability is `immutable` or `revision_pinned` for coherent inspection.

`best_effort_live` is a named degraded grade. It may produce a typed unavailable/degraded
diagnostic, but it can never set `coherent=true`, allocate durable epoch handles, or be returned
as if it were one coherent snapshot. A late result for another target, image, epoch, token,
snapshot token, transition revision or inspection revision is `STALE`.

## 3. Identity and address value types

All types are frozen value objects with exact equality. String identities are non-empty and
case-sensitive. Digest strings use the frozen lowercase Hex64 representation only where the
portable contract specifies a digest; other identity strings are opaque and are not
lowercased, path-normalized or parsed for meaning.

Required public values:

- `ExecutiveInstanceRef`
- `TargetRef` including executive instance, opaque target ID, target generation, display PID
  and PID generation;
- `ArtifactRef` including schema/media version, exact byte length and SHA-256 of accepted HXE
  bytes;
- `LoadedImageRef` including TargetRef, never-reused loaded-image ID, image generation and
  ArtifactRef;
- `ArchitectureDescriptorRef`, `AbiDescriptorRef`, `RecipeSchemaRef`;
- `ImageDebugBundleRef` and exact `ImageDebugBinding`;
- `SourceRef` including exact bundle ref, NFC logical ID, source-byte SHA-256 and byte length;
- `StopEpochId`, `StopToken`, and `InspectionSnapshotRef`;
- `InspectionContext`;
- `AddressSpaceId`, `HsxAddress`, and half-open `HsxAddressRange`.

`ArchitectureDescriptor` contains named spaces with unit, width, legal half-open ranges,
byte order, alignment, permissions and wrap policy. Public operations are checked:

```text
validate(address) -> AddressResult
add(address, unsigned_delta) -> AddressResult
subtract(address, unsigned_delta) -> AddressResult
range(start, byte_length) -> AddressRangeResult
format(address) -> str
```

No public or private RF-004 operation may apply `0xFFFF`, `0xFFFFFFFF`, modulo, truncation or
wrap unless an explicit descriptor space declares wrap and the caller selected that operation.
Overflow, underflow, wrong space, misalignment, range crossing and permission failure are typed
failures. Addresses in different spaces never compare as interchangeable.

## 4. Typed outcome algebra

Domain failures are returned, not hidden by `None`, first-candidate selection or fallback.

`ResolutionStatus`:

- `RESOLVED`
- `UNAVAILABLE`
- `AMBIGUOUS`
- `CONTENT_MISMATCH`
- `CASE_COLLISION`
- `ARTIFACT_MISMATCH`
- `SCHEMA_UNSUPPORTED`
- `CORRUPT`

`InspectionStatus`:

- `COMPLETE`
- `PARTIAL`
- `UNAVAILABLE`
- `UNKNOWN_HANDLE`
- `STALE`
- `UNSUPPORTED`
- `CORRUPT`
- `LIMIT_EXCEEDED`

Every result is immutable and contains status, exact input/evidence identity, zero or more
typed values/candidates, and ordered structured diagnostics. `RESOLVED`/`COMPLETE` requires
exactly the evidence required by the service. `AMBIGUOUS` never contains a preferred or
silently selected candidate. `PARTIAL` names the missing pieces and never pads, truncates or
invents values.

## 5. Debug artifact index

`DebugArtifactIndex` consumes only an exact `ImageDebugBinding` plus components whose digests,
schemas, architecture, ABI, recipe and SourceIdentityManifest refs have already been verified
against that binding. The index is immutable after construction.

Public queries:

```text
binding() -> ImageDebugBinding
functions() -> tuple[FunctionRecord, ...]
symbols_named(name: str) -> ResolutionResult[SymbolRecord]
instruction_at(address: HsxAddress) -> ResolutionResult[InstructionRecord]
source_locations(source: SourceRef, line: int, column: int | None) -> ResolutionResult[InstructionRecord]
memory_regions() -> tuple[MemoryRegion, ...]
unwind_rows(function_or_pc) -> ResolutionResult[UnwindRow]
location_rows(variable_or_scope, frame_pc) -> ResolutionResult[LocationRow]
```

Duplicate symbol names and multiple executable addresses remain candidate sets. Source records
are keyed by exact `SourceRef`; no basename alias is part of the portable index. All code/data
values are typed addresses. Malformed fields, overlap where forbidden, unsupported schemas and
binding/component mismatch are explicit outcomes and publish no accepted index.

The legacy `.sym` adapter is a separate, named compatibility input. It may preserve only
behaviors classified by `DBG-SL-001-005-001` golden evidence. It must validate schema version
and supplied HXE CRC evidence, convert every integer through an explicit descriptor, preserve
duplicate candidates and exact spelling, and mark its result `hsx.python-debug-legacy/1` /
degraded. It may not claim `hsx.debug.image-bundle/1` conformance.

## 6. Source resolver

`SourceResolver` keeps identity and local locator policy separate:

```text
resolve(source: SourceRef, policy: SourceLocatorPolicy) -> SourceResolution
```

`SourceLocatorPolicy` contains only explicit local locators: exact logical-ID overrides,
prefix mappings and ordered search roots. Candidate discovery may use the exact logical ID
and explicit mappings. It must not use basename guessing or global lowercase/casefold identity.

Before returning `RESOLVED`, the resolver reads the candidate bytes and verifies exact byte
length and SHA-256 from `SourceRef`. It returns all exact candidates for ambiguity, reports
case collisions separately, and returns content mismatch when a locator exists but bytes do
not match. Symlink and relocation support are locator behaviors; the returned identity remains
the original SourceRef. NFC validation, `/` separators and the portable rejection rules for
absolute/drive/UNC/empty/dot/dot-dot/backslash/NUL/control logical IDs are mandatory.

## 7. Snapshot read port

RF-004 defines, but does not implement against Executive/VM, this frontend-neutral port:

```text
SnapshotReadPort.read_registers(context, register_ids) -> InspectionResult[RegisterValue]
SnapshotReadPort.read_memory(context, address, byte_length) -> InspectionResult[bytes]
SnapshotReadPort.read_disassembly(context, address, instruction_count) -> InspectionResult[InstructionBytes]
```

Every call carries the complete `InspectionContext`; returned evidence must match it exactly.
The port exposes no generic `request(dict)` and no live-current-frame method. Test fixtures may
implement the port with immutable snapshot data. Runtime adapters belong to later authorized
work and may not be added in RF-004.

## 8. Recipes, locations and stack

`RecipeEvaluator` implements only the frozen `hsx.unwind-recipe/1` and
`hsx.location-recipe/1` declarative schemas. Allowed opcodes, terminal forms and bounds are
exactly those in `HSX-D-002`; there are no branches, loops, recursive recipe calls, host-endian
reads, implicit casts, masks or wrapping.

`StackService.unwind(context, index, read_port, limits)` returns immutable `FrameRecord`s bound
to the same context. Each frame has a stable domain handle, typed PC/SP/CFA/frame-base values,
function/source metadata where resolved, resume PC distinct from checked call-site PC, and
per-frame diagnostics. Terminal top level is explicit. Missing data returns partial/unavailable;
unsupported, corrupt, stale and limit-exceeded remain distinct. The service never retries with
a fixed R7 chain or invents a caller.

`LocationEvaluator.evaluate(context, frame, variable, row, read_port)` selects the exact
half-open PC row for the selected frame and returns register, address, value, bounded pieces,
optimized-out or unavailable results with declared width/endian/type preserved. A non-top-frame
local is evaluated from that frame/context, never current live registers.

## 9. Epoch-bound inspection service and handles

`InspectionService` is composition over the frozen services and SnapshotReadPort:

```text
registers(context, selection) -> InspectionResult[RegisterSet]
stack(context, page) -> InspectionResult[FramePage]
scopes(context, frame_handle) -> InspectionResult[ScopeSet]
variables(context, scope_handle, page) -> InspectionResult[VariablePage]
evaluate_snapshot(context, frame_handle, expression: SnapshotExpression) -> InspectionResult[VariableValue]
memory(context, address, byte_length) -> InspectionResult[MemoryBlock]
disassemble(context, address, instruction_count) -> InspectionResult[DisassemblyBlock]
```

All returned frames, scopes and variables retain the complete evidence tuple. `EpochHandleStore`
allocates opaque domain handles monotonically within one StopEpoch. Repeated/paged requests may
allocate more handles without invalidating earlier handles in the same epoch. Unknown handles
return `UNKNOWN_HANDLE`; invalidated or different-epoch handles return `STALE`; neither falls back
to a current/top/first frame. DAP integer IDs are outside this interface and later map to domain
handles without owning their lifetime.

`SnapshotExpression` is a typed, side-effect-free AST over registers, selected-frame variables,
symbols/constants and explicit typed memory dereference. String parsing and DAP Watch policy
belong to later frontends; persistent live watches belong to RF-005 and are not created here.

Registers, stack, variables, snapshot expressions, memory and disassembly returned for one context must use one exact
snapshot or immutable image bytes explicitly identified in the result. Cross-service tests
must prove that a mixed target/image/epoch/snapshot response is rejected rather than merged.

## 10. Legacy evidence, retention and retirement

RF-004 may adapt only these classified seeds:

- `SymbolIndex` parser/index concepts, fixture lookup ordering, PC metadata, locals/globals;
- `SourceMap` explicit prefix-map, relocation-root and symlink behavior;
- existing partial stack diagnostics and location-list concepts as regression evidence only.

The following are intentional-change or retirement behavior and have no retain condition:

- hidden `0xFFFF`/`0xFFFFFFFF` masks or wrap;
- unconditional lowercase/casefold source identity;
- basename-first or first-candidate source/symbol selection;
- unknown-frame fallback;
- request-time live reads presented as a coherent stop snapshot;
- fixed-R7 unwinding without a selected ABI/recipe row;
- raw frontend RPC, DAP handles/policy, Executive/VM mutation, or VS Code presentation.

Legacy files remain runnable and unchanged during RF-004. A compatibility adapter may be
retired only after its classified preserved cases pass through the new typed interface and
the parent RF-004 review accepts the retirement status. This wave does not delete the legacy
DAP/CLI consumers.

## 11. Slice mapping and freeze

| Slice | Frozen interface responsibility |
|---|---|
| `DBG-SL-001-005-001` | Classify and capture legacy symbol/source/stack evidence; no new service implementation |
| `DBG-SL-001-005-002` | Implement identity/address/result/binding values and descriptor checks |
| `DBG-SL-001-005-003` | Implement verified artifact index and explicit legacy `.sym` adapter |
| `DBG-SL-001-005-004` | Implement exact content-verified SourceResolver |
| `DBG-SL-001-005-005` | Implement bounded recipes, locations and snapshot-bound stack service |
| `DBG-SL-001-005-006` | Implement handles and integrated epoch-bound InspectionService |

Each Slice has a fresh worker, independent exact-head review, formal verification and Master
sign-off. Later Slices consume earlier signed interfaces. No RF-005 product work starts from
this frozen document: RF-005 remains blocked until RF-004 parent sign-off, remote publication
and a later Steering authorization.

## 12. Interface completion signal

`dbg.resolver-inspection/1` is accepted only when all six Slices and RF-004 parent review,
verification and exact-head Master sign-off pass on remote-resolvable history. The decision
package must state exact interfaces, address/source/stack/variables/memory/disassembly
coverage, legacy reuse/retirement, degraded behavior and every review/verification/sign-off
head. Until then the interface is frozen for implementation but not an accepted prerequisite
for RF-005.
