# `dbg.resolver-inspection/1` — Typed Resolver and Inspection Interface

- Status: **REFROZEN CANDIDATE — REVIEW 007 REWORK / REVIEW 008 PENDING**
- Iteration: `DBG-IT-001-005`
- Parent Refactor: `DBG-RF-004`
- Steering authority: issue #38 comment `5362514094`
- Dependency clarification: issue #42 comment `5362515750`
- Frozen design: `DBG-D-003`, `DBG-D-004`, `DBG-D-009`
- Portable contracts: `HSX-D-001..HSX-D-003`, especially `HSX-D-002`
- Review `DBG-RVW-001-005-007`: REWORK at `82154c614a31284723bf3e6a337c5bedfb8aba5d`
- Fresh independent re-review: `DBG-RVW-001-005-008`
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
  epoch: EpochBinding,
}

EpochBinding {
  stop_epoch_id: StopEpochId,
  controller_generation: GenerationStamp,
  stop_token: StopToken,
  snapshot: InspectionSnapshotRef,
  evidence_grade: EvidenceGrade,
}
```

Construction fails unless all embedded identities agree exactly:

- `LoadedImageRef.target == TargetRef`;
- snapshot TargetRef and LoadedImageRef equal the context refs;
- EpochBinding controller generation and snapshot refs equal the context refs;
- transition and inspection revisions are non-negative and exact;
- snapshot stability is `immutable` or `revision_pinned` for coherent inspection.

### RF-002 StopEpoch consumption seam

RF-004 does not edit RF-002's frozen `contracts.StopEpoch`. `ControllerEpochAdapter` in
Slice 002 is the only seam from that record to `EpochBinding`:

```text
ControllerEpochAdapter.bind(
  controller_epoch: contracts.StopEpoch,
  target: TargetRef,
  image: LoadedImageRef,
) -> ContextBindingResult
```

For a coherent result, `controller_epoch.generation` must exactly match TargetRef executive,
target and target-generation fields; `controller_epoch.stop_token` must already be a typed
`StopToken`; `controller_epoch.snapshot_ref` must already be a typed
`InspectionSnapshotRef`; both typed values must embed the same TargetRef/LoadedImageRef and
revisions; and controller/typed evidence grades must be portable and equal. The adapter does
not decode strings/dictionaries, infer identity or fetch replacements. Any untyped/degraded
legacy token/snapshot returns `UNAVAILABLE` with diagnostic
`coherent_snapshot_unavailable`; a mismatch returns the relevant `STALE` or
`ARTIFACT_MISMATCH` binding status and publishes no InspectionContext. This preserves RF-002 as
read-only while making its exact consumption contract executable.

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

Exact identity/binding schemas (field meanings and digest construction remain those frozen by
`HSX-D-001`/`HSX-D-002` and its canonical digest appendix):

```text
ExecutiveInstanceRef { value: str }
TargetRef { executive: ExecutiveInstanceRef, target_id: str,
            target_generation: int >= 1, display_pid: int,
            pid_generation: int >= 1 }
ArtifactRef { ref_schema: "hsx.artifact-ref/1",
              media_type: "application/vnd.hsx.hxe", container_version: str,
              byte_length: int >= 0, sha256: Hex64 }
LoadedImageRef { ref_schema: "hsx.loaded-image-ref/1",
                 executive: ExecutiveInstanceRef, target: TargetRef,
                 loaded_image_id: str, image_generation: int >= 1,
                 artifact: ArtifactRef }
ArchitectureDescriptorRef { schema: str, profile_id: str, digest: Hex64 }
AbiDescriptorRef { schema: "hsx.abi-descriptor/1", profile_id: str, digest: Hex64 }
RecipeSchemaRef { schema: hsx.unwind-recipe/1 | hsx.location-recipe/1,
                  digest: Hex64 }
ImageDebugBundleRef { ref_schema: "hsx.image-debug-bundle-ref/1", digest: Hex64,
                      bundle_schema: "hsx.image-debug-bundle/1",
                      artifact: ArtifactRef, architecture: ArchitectureDescriptorRef,
                      abi: AbiDescriptorRef, recipe_schemas: tuple[RecipeSchemaRef, ...],
                      component_digests: tuple[tuple[str, Hex64], ...],
                      source_manifest_digest: Hex64 }
ImageDebugBinding { schema: "hsx.image-debug-binding/1", loaded_image: LoadedImageRef,
                    bundle: ImageDebugBundleRef,
                    architecture: ArchitectureDescriptorRef,
                    abi: AbiDescriptorRef, binding_digest: Hex64 }
SourceRef { bundle: ImageDebugBundleRef, logical_id: str,
            sha256: Hex64, byte_length: int >= 0 }
AddressSpaceId { value: str }
HsxAddress { space: AddressSpaceId, unsigned_value: int >= 0 }
HsxAddressRange { start: HsxAddress, byte_length: int >= 0 }
AddressSpaceDescriptor { space: AddressSpaceId, unit: str, width_bits: int >= 1,
                         legal_ranges: tuple[HsxAddressRange, ...],
                         byte_order: LITTLE | BIG, alignment: int >= 1,
                         wrap_policy: FORBIDDEN | EXPLICIT,
                         permissions: frozenset[READ | WRITE | EXECUTE] }
ArchitectureDescriptor { ref: ArchitectureDescriptorRef,
                         spaces: tuple[AddressSpaceDescriptor, ...],
                         instruction_alignment: int >= 1 }
```

Exact stop/snapshot schemas:

```text
StopToken {
  target: TargetRef,
  image: LoadedImageRef,
  opaque_token: str,
  transition_revision: int,
}

InspectionSnapshotRef {
  target: TargetRef,
  image: LoadedImageRef,
  stop_token: StopToken,
  snapshot_token: str,
  transition_revision: int,
  inspection_revision: int,
  supported_read_sets: frozenset[str],
  stability: IMMUTABLE | REVISION_PINNED | BEST_EFFORT_LIVE,
}
```

`StopEpochId` is one opaque non-empty exact string; it is never parsed for generation.
`supported_read_sets` uses the frozen names `registers`, `memory`, `disassembly`, `stack`, and
`resources`; a service requiring an absent set returns `UNAVAILABLE`.

`ArchitectureDescriptor` contains named spaces with unit, width, legal half-open ranges,
byte order, alignment, permissions and wrap policy. Public operations are checked:

```text
validate(address) -> AddressResult
add(address, unsigned_delta, mode: CHECKED | WRAP) -> AddressResult
subtract(address, unsigned_delta, mode: CHECKED | WRAP) -> AddressResult
range(start, byte_length) -> AddressRangeResult
format(address) -> str
```

No public or private RF-004 operation may apply `0xFFFF`, `0xFFFFFFFF`, modulo, truncation or
wrap unless an explicit descriptor space declares wrap and the caller passes `WRAP`.
`CHECKED` never wraps and neither operation has an implicit/default mode.
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

`ContextBindingStatus`:

- `BOUND`
- `UNAVAILABLE`
- `STALE`
- `ARTIFACT_MISMATCH`

`AddressStatus`:

- `VALID`
- `UNKNOWN_SPACE`
- `OVERFLOW`
- `UNDERFLOW`
- `MISALIGNED`
- `OUT_OF_RANGE`
- `PERMISSION_DENIED`
- `WRAP_FORBIDDEN`

Every result is immutable and contains status, exact input/evidence identity, zero or more
typed values/candidates, and ordered structured diagnostics. `RESOLVED`/`COMPLETE` requires
exactly the evidence required by the service. `AMBIGUOUS` never contains a preferred or
silently selected candidate. `PARTIAL` names the missing pieces and never pads, truncates or
invents values.

### Frozen envelope and record schemas

All tuples below are ordered and immutable. IDs are opaque non-empty exact strings.

```text
Diagnostic {
  code: str,
  message: str,
  component: str | None,
  row_id: str | None,
  frame_index: int | None,
  operation_index: int | None,
}

ResolutionResult[T] {
  status: ResolutionStatus,
  binding: ImageDebugBinding | None,
  query_id: str,
  values: tuple[T, ...],
  diagnostics: tuple[Diagnostic, ...],
}

InspectionResult[T] {
  status: InspectionStatus,
  context: InspectionContext,
  value: T | None,
  diagnostics: tuple[Diagnostic, ...],
}

ContextBindingResult {
  status: ContextBindingStatus,
  context: InspectionContext | None,
  diagnostics: tuple[Diagnostic, ...],
}

AddressResult { status: AddressStatus, value: HsxAddress | None,
                diagnostics: tuple[Diagnostic, ...] }
AddressRangeResult { status: AddressStatus, value: HsxAddressRange | None,
                     diagnostics: tuple[Diagnostic, ...] }
```

`RESOLVED` has one or more values (duplicate candidates are allowed only when the query itself
asks for all exact matches); `AMBIGUOUS` has at least two candidates; non-value resolution
statuses have no preferred value. `COMPLETE` has one value and no missing-piece diagnostic;
`PARTIAL` has a value plus at least one missing-piece diagnostic; all other InspectionStatus
values have no value except explicitly structured partial-memory segments inside a `PARTIAL`
MemoryBlock.

Artifact/index record schemas:

```text
DebugComponentInput { component_id: str, schema: str,
                      canonical_digest: Hex64, content: bytes }
FunctionRecord { function_id: str, name: str, linkage_name: str | None,
                 range: HsxAddressRange,
                 definition: SourceLocation | None }
SymbolRecord { symbol_id: str, name: str,
               kind: FUNCTION | LABEL | GLOBAL | LOCAL | CONSTANT,
               address: HsxAddress, byte_size: int >= 0,
               function_id: str | None, lexical_scope_id: str | None,
               type_id: str | None }
SourceLocation { source: SourceRef, line: int >= 1, column: int >= 1 | None,
                 discriminator: int | None }
InstructionRecord { instruction_id: str, address: HsxAddress, byte_size: int >= 1,
                    encoded_word: int | None, function_id: str | None,
                    source: SourceLocation | None,
                    classification: USER | COMPILER_GENERATED | UNMAPPED }
MemoryRegion { region_id: str, name: str, kind: str, range: HsxAddressRange,
               permissions: frozenset[READ | WRITE | EXECUTE] }
UnwindRow { row_id: str, binding: ImageDebugBinding, pc_range: HsxAddressRange,
            abi: AbiDescriptorRef, schema: RecipeSchemaRef, cfa_recipe,
            caller_pc_recipe, caller_sp_recipe,
            register_recipes: tuple[tuple[str, Recipe], ...], terminal: bool }
LocationRow { row_id: str, binding: ImageDebugBinding, variable_id: str,
              lexical_scope_id: str, function_id: str,
              pc_range: HsxAddressRange, declared_type_id: str | None,
              declared_bit_size: int >= 1, schema: RecipeSchemaRef, location_form }
```

Pagination and inspection record schemas:

```text
PageRequest { offset: int >= 0, limit: int in 1..256 }
RegisterSelection { all_declared: bool, register_ids: tuple[str, ...] }
RegisterValue { register_id: str, bit_width: int >= 1,
                unsigned_value: int | None, available: bool }
RegisterSet { registers: tuple[RegisterValue, ...] }

UnwindFrame { context: InspectionContext, frame_index: int >= 0,
              pc: HsxAddress, sp: HsxAddress, cfa: HsxAddress,
              frame_base: HsxAddress | None, resume_pc: HsxAddress | None,
              call_site_pc: HsxAddress | None, function: FunctionRecord | None,
              source: SourceLocation | None, terminal: bool,
              diagnostics: tuple[Diagnostic, ...] }
DomainHandle { stop_epoch_id: StopEpochId,
               kind: FRAME | SCOPE | VARIABLE, serial: int >= 1 }
FrameRecord { context: InspectionContext, handle: DomainHandle, unwind: UnwindFrame }
FramePage { total_frames: int >= 0, offset: int >= 0,
            frames: tuple[FrameRecord, ...] }
ScopeRecord { context: InspectionContext, handle: DomainHandle,
              frame_handle: DomainHandle,
              kind: REGISTERS | LOCALS | GLOBALS | WATCH,
              name: str, expensive: bool }
ScopeSet { frame_handle: DomainHandle, scopes: tuple[ScopeRecord, ...] }
VariableValue { name: str, declared_type_id: str | None, display_value: str,
                raw_bytes: bytes | None, bit_size: int >= 1 | None,
                location_status: AVAILABLE | PARTIAL | OPTIMIZED_OUT | UNAVAILABLE,
                child_scope_handle: DomainHandle | None }
VariablePage { scope_handle: DomainHandle, total_variables: int >= 0,
               offset: int >= 0,
               variables: tuple[VariableValue, ...] }
MemorySegment { offset: int >= 0, requested_length: int >= 1,
                data: bytes, status: COMPLETE | UNAVAILABLE }
MemoryBlock { start: HsxAddress, requested_length: int >= 1,
              segments: tuple[MemorySegment, ...] }
InstructionBytes { address: HsxAddress, encoded: bytes }
DisassembledInstruction { address: HsxAddress, encoded: bytes,
                          instruction: InstructionRecord | None, text: str | None }
DisassemblyBlock { start: HsxAddress, requested_count: int >= 1,
                   instructions: tuple[DisassembledInstruction, ...] }
```

`RegisterSelection` requires exactly one of `all_declared=true` with no IDs, or
`all_declared=false` with unique explicit IDs. Pagination returns the same deterministic total
and order for one immutable context. Memory segments are ordered, non-overlapping and exactly
cover the requested range when status is COMPLETE; gaps are explicit UNAVAILABLE segments in
a PARTIAL result.

`SnapshotExpression` is a closed typed union:

```text
RegisterExpression { register_id }
VariableExpression { variable_id, lexical_scope_id }
SymbolExpression { symbol_id }
ConstantExpression { unsigned_value, bit_width }
MemoryExpression { address: HsxAddress, bit_width, byte_order }
```

There are no call, assignment, mutation, persistent-watch or raw-string variants. Frontend
string parsing and presentation remain outside this interface.

Source locator schemas:

```text
ExactSourceOverride { source: SourceRef, locator: str }
SourcePrefixMapping { logical_prefix: str, local_root: str }
SourceLocatorPolicy { exact_overrides: tuple[ExactSourceOverride, ...],
                      prefix_mappings: tuple[SourcePrefixMapping, ...],
                      search_roots: tuple[str, ...] }
SourceCandidate { locator: str, discovery: OVERRIDE | PREFIX | SEARCH_ROOT,
                  byte_length: int >= 0, sha256: Hex64,
                  content_matches: bool }
SourceResolution { status: ResolutionStatus, source: SourceRef,
                   candidates: tuple[SourceCandidate, ...],
                   resolved_locator: str | None,
                   diagnostics: tuple[Diagnostic, ...] }
```

Only `RESOLVED` has one `resolved_locator`, whose candidate has `content_matches=true`.
Ambiguous/collision/mismatch/unavailable outcomes have no selected locator.

## 5. Debug artifact index

`DebugArtifactIndex` consumes only an exact `ImageDebugBinding` plus components whose digests,
schemas, architecture, ABI, recipe and SourceIdentityManifest refs have already been verified
against that binding. The index is immutable after construction.

Construction entrypoints are exact:

```text
DebugArtifactIndex.build(binding: ImageDebugBinding,
                         components: tuple[DebugComponentInput, ...])
    -> ResolutionResult[DebugArtifactIndex]
LegacySymbolAdapter.build(binding: ImageDebugBinding,
                          sym_bytes: bytes,
                          expected_hxe_crc32: int,
                          architecture: ArchitectureDescriptor)
    -> ResolutionResult[DebugArtifactIndex]
```

Portable build rechecks each input byte digest/schema against the bundle before parsing.
Legacy build requires `.sym` version 1 and exact `hxe_crc == expected_hxe_crc32`; its returned
index/result diagnostics carry profile `hsx.python-debug-legacy/1` and never claim portable
bundle capability.

Public queries:

```text
binding() -> ImageDebugBinding
functions() -> tuple[FunctionRecord, ...]
symbols_named(name: str) -> ResolutionResult[SymbolRecord]
instruction_at(address: HsxAddress) -> ResolutionResult[InstructionRecord]
source_locations(source: SourceRef, line: int, column: int | None) -> ResolutionResult[InstructionRecord]
memory_regions() -> tuple[MemoryRegion, ...]
unwind_rows(pc: HsxAddress, function_id: str | None) -> ResolutionResult[UnwindRow]
location_rows(variable_id: str, lexical_scope_id: str,
              frame_pc: HsxAddress) -> ResolutionResult[LocationRow]
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
SnapshotReadPort.read_registers(context: InspectionContext,
                                selection: RegisterSelection) -> InspectionResult[RegisterSet]
SnapshotReadPort.read_memory(context: InspectionContext, address: HsxAddress,
                             byte_length: int) -> InspectionResult[MemoryBlock]
SnapshotReadPort.read_disassembly(context: InspectionContext, address: HsxAddress,
                                  instruction_count: int) -> InspectionResult[tuple[InstructionBytes, ...]]
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

`Recipe`, `cfa_recipe`, `caller_*_recipe`, `register_recipes` and `location_form` above are the
canonical immutable records from `HSX-D-002`: ordered postfix opcode tuples using only
`reg_value`, `special_value`, `const_u`, `const_s`, `static_address`, `to_address`, `cfa`,
`frame_base`, `add_sconst_checked`, `deref_u`, and `bit_slice`; or the exact structural
`same`, `undefined`, `unavailable(reason)`, `optimized_out(reason)` and bounded-piece terminal
forms. Their operands use the referenced register/special/space IDs and explicit widths; an
unknown or extra operand/opcode is `UNSUPPORTED`, and a malformed operand is `CORRUPT`.

```text
RecipeLimits {
  opcodes_per_expression: 32,
  evaluator_stack: 8,
  dereferences_per_expression: 4,
  bytes_per_dereference: 16,
  unwind_frames: 64,
  unwind_total_opcodes: 4096,
  unwind_total_dereferenced_bytes: 1024,
  location_pieces: 16,
  location_declared_result_bits: 4096,
  location_total_dereferenced_bytes: 512,
}
```

The caller supplies the exact accepted profile limits and may only lower them; attempts to
widen a field are `UNSUPPORTED`. `StackService.unwind(context: InspectionContext,
index: DebugArtifactIndex, read_port: SnapshotReadPort, limits: RecipeLimits) ->
InspectionResult[tuple[UnwindFrame, ...]]` returns handle-free immutable frames bound to the
same context. Each frame has typed PC/SP/CFA/frame-base values,
function/source metadata where resolved, resume PC distinct from checked call-site PC, and
per-frame diagnostics. Terminal top level is explicit. Missing data returns partial/unavailable;
unsupported, corrupt, stale and limit-exceeded remain distinct. The service never retries with
a fixed R7 chain or invents a caller.

`LocationEvaluator.evaluate(context: InspectionContext, frame: UnwindFrame,
variable: SymbolRecord, row: LocationRow, read_port: SnapshotReadPort,
limits: RecipeLimits) -> InspectionResult[VariableValue]` selects the exact
half-open PC row for the selected frame and returns register, address, value, bounded pieces,
optimized-out or unavailable results with declared width/endian/type preserved. A non-top-frame
local is evaluated from that frame/context, never current live registers.

## 9. Epoch-bound inspection service and handles

`InspectionService` is composition over the frozen services and SnapshotReadPort:

```text
registers(context: InspectionContext, selection: RegisterSelection) -> InspectionResult[RegisterSet]
stack(context: InspectionContext, page: PageRequest) -> InspectionResult[FramePage]
scopes(context: InspectionContext, frame_handle: DomainHandle) -> InspectionResult[ScopeSet]
variables(context: InspectionContext, scope_handle: DomainHandle,
          page: PageRequest) -> InspectionResult[VariablePage]
evaluate_snapshot(context: InspectionContext, frame_handle: DomainHandle,
                  expression: SnapshotExpression) -> InspectionResult[VariableValue]
memory(context: InspectionContext, address: HsxAddress,
       byte_length: int) -> InspectionResult[MemoryBlock]
disassemble(context: InspectionContext, address: HsxAddress,
            instruction_count: int) -> InspectionResult[DisassemblyBlock]
```

Slice 006 converts handle-free `UnwindFrame`s from StackService into `FrameRecord`s and is the
only allocator of DomainHandle values. All returned frames, scopes and variables retain the
complete evidence tuple. `EpochHandleStore` allocates opaque domain handles monotonically
within one StopEpoch. Repeated/paged requests may
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
