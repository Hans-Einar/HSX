# `dbg.resolver-inspection/1.1` — Typed Resolver and Inspection Interface

- Status: **STEERING REFROZEN / REVIEW 028 REWORK / REVIEW 029 PENDING**
- Iteration: `DBG-IT-001-005`
- Parent Refactor: `DBG-RF-004`
- Steering authority: issue #38 comment `5362514094`
- Dependency clarification: issue #42 comment `5362515750`
- Frozen design: `DBG-D-003`, `DBG-D-004`, `DBG-D-009`
- Portable contracts: `HSX-D-001..HSX-D-003`, especially `HSX-D-002`
- Review `DBG-RVW-001-005-007`: REWORK at `82154c614a31284723bf3e6a337c5bedfb8aba5d`
- Review `DBG-RVW-001-005-008`: REWORK at `8d6c0f571f46a10ce6db7331618ef7600d6a8203`
- Review `DBG-RVW-001-005-009`: REWORK at `07f7e16040bec1c225d263c682066f65b173e6aa`
- Review `DBG-RVW-001-005-010`: REWORK at `72b06ad0bae53b70bc3d64edad91591998d2408d`
- Review `DBG-RVW-001-005-012`: REWORK at `573f396e29de728f69abb0961e9b79a2fdb3c29d`
- Review `DBG-RVW-001-005-013`: REWORK at `1e8fb7e74c92a69711bd48809696552cf2f982db`
- Review `DBG-RVW-001-005-014`: REWORK at `96daa3a5dffa6b80b2b5687b9cd0429ffaa402c8`
- Review `DBG-RVW-001-005-015`: REWORK at `18c0a26cad4c2d82e4a23ef0ec3e6409b022cb95`
- Review `DBG-RVW-001-005-016`: REWORK at `e330a7b344715dfdbae0de46e44f4720b4387d4e`
- Review `DBG-RVW-001-005-017`: REWORK at `cb88b62b7c45ea6ebfe31c40e522daa3adcf8896`
- Review `DBG-RVW-001-005-018`: REWORK at `08719457a341b01ca8f64ea568e1ab04678dd10d`
- Review `DBG-RVW-001-005-019`: PASS at `058c3383593553aa1497d024d41285d44d9c67a8`
- Steering refreeze: issue #38 comment `5368017338`
- Prior public interface/review: `dbg.resolver-inspection/1` / `DBG-RVW-001-005-019` PASS
- Public interface ID: `dbg.resolver-inspection/1.1`
- Conformance fixture matrix: `DBG-CF-001-005-001`

This document freezes the public Python-domain interface to be implemented by the seven bounded
RF-004 Slices. It is frontend-neutral and side-by-side: it does not migrate DAP, CLI, VS Code,
the Executive, VM, or AVR paths.

Version `1.1` preserves every public DTO/result schema, exact typed Enum member, identity,
coherence/address/outcome rule, ownership boundary and public method from version `1`. The only
normative change is the supported-mutation/contract-safe immutability definition and its
conformance fixtures. The stable filename is retained for review-history continuity.

Any implementation discovery that requires changing an identity field, coherence rule,
address rule, result category, ownership boundary, or public method below stops the active
Slice and returns to Master/Steering. Additive private helpers are allowed only when they do
not change observable semantics.

## 1. Boundary and module ownership

The target package remains `python/hsx_debugger/`, but RF-004 must preserve these responsibility
boundaries:

| Module boundary | Owns | Must not own |
|---|---|---|
| `identity.py` | Immutable target, image, artifact, bundle, binding, stop/snapshot refs and shared DebugBindingValidator | Parsing, filesystem lookup, target reads, frontend IDs |
| `addresses.py` | Address-space descriptors, typed addresses/ranges, checked arithmetic and formatting | Symbol lookup, masks hidden in adapters, memory reads |
| `results.py` | Typed resolver/inspection statuses, diagnostics and contract-safe immutable result envelopes | Service algorithms or policy fallbacks |
| `snapshot.py` | SnapshotReadPort Protocol and exact context/result fencing helpers | Runtime adapter, live reads, transport/retry |
| `metadata.py` | Pure source/function/symbol/type/scope/instruction/memory record DTOs | Parsing/indexes, recipe rows/evaluation, target reads |
| `artifacts.py` | Verified bundle/component parsing and immutable debug indexes | Local source selection, live reads, stack walking, frontend mapping |
| `legacy_symbols.py` | Explicit `hsx.python-debug-legacy/1` `.sym` adaptation behind classified evidence | Portable conformance claims, implicit masks/case/basename policy |
| `sources.py` | Exact source identity and content-verified locator resolution | Symbol parsing, target state, UI navigation |
| `recipes.py` | Unwind/Location row DTOs, bounded recipe validation and evaluation | Artifact component parsing/index, stack traversal policy, raw live reads, implicit ABI guesses |
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

- `LoadedImageRef.target_ref == TargetRef`;
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
revisions; and controller/snapshot evidence grades must be `PORTABLE` and equal. The adapter
does not decode strings/dictionaries, infer identity or fetch replacements.

Mismatch classification is frozen and first-match ordered:

| Condition | Status | Diagnostic code |
|---|---|---|
| stop token or snapshot is absent/not the typed RF-004 record | `UNAVAILABLE` | `coherent_snapshot_unavailable` |
| controller or snapshot evidence grade is not `PORTABLE`, grades differ, or stability is `BEST_EFFORT_LIVE` | `UNAVAILABLE` | `portable_snapshot_evidence_unavailable` |
| GenerationStamp executive instance, target ID or target generation differs from TargetRef | `STALE` | `controller_epoch_target_stale` |
| image/token/snapshot TargetRef differs after the prior check | `STALE` | `epoch_target_stale` |
| loaded-image ID or image generation differs among image/token/snapshot | `STALE` | `loaded_image_stale` |
| ArtifactRef differs among image/token/snapshot | `ARTIFACT_MISMATCH` | `epoch_artifact_mismatch` |
| controller StopToken differs from snapshot StopToken, or transition revisions differ | `STALE` | `stop_token_stale` |
| all checks match exactly | `BOUND` | none |

Every non-BOUND outcome publishes no InspectionContext. This preserves RF-002 as read-only
while making its exact consumption contract executable.

`best_effort_live` is a named degraded grade. It may produce a typed unavailable/degraded
diagnostic, but it can never set `coherent=true`, allocate durable epoch handles, or be returned
as if it were one coherent snapshot. A late result for another target, image, epoch, token,
snapshot token, transition revision or inspection revision is `STALE`.

## 3. Identity and address value types

All types are contract-safe frozen value objects with exact equality. String identities are non-empty and
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

The Python records below are exact projections of the frozen `HSX-D-001`/`HSX-D-002` model,
not alternate digest models. `CanonicalUInt64` stores a validated Python integer in
`0..2^64-1` and serializes to the required minimal decimal JSON string. `ContentDigest` and
`StructuredDigest` store the exact algorithm/value object. `canonical_payload()` on
ArtifactRef, bundle identity/ref and binding payload emits the exact normative key names,
omits no mandatory field, adds no convenience field and delegates byte/key/string/integer
encoding to the frozen canonical appendix. Convenience properties are derived only and are
excluded from equality/digest scope.

```text
ExecutiveInstanceRef { value: str }
TargetRef { canonical_ref: str, executive: ExecutiveInstanceRef, target_id: str,
            target_generation: int >= 1, display_pid: int,
            pid_generation: int >= 1 }
CanonicalUInt64 { value: int in 0..2^64-1 }
ContentDigest { algorithm: "sha256", value: Hex64 }
StructuredDigest { algorithm: "sha256", value: Hex64 }
DescriptorDigestRef { ref: str, digest: Hex64 }
ComponentDigestRef { schema: str, canonical_component_digest: Hex64 }

ArtifactRef { ref_schema: "hsx.artifact-ref/1",
              media_type: "application/vnd.hsx.hxe",
              container_version: CanonicalUInt64,
              byte_length: CanonicalUInt64,
              content_digest: ContentDigest }
LoadedImageRef { ref_schema: "hsx.loaded-image-ref/1",
                 executive_instance_ref: ExecutiveInstanceRef,
                 target_ref: TargetRef, loaded_image_id: str,
                 image_generation: CanonicalUInt64,
                 artifact_ref: ArtifactRef }
ArchitectureDescriptorRef { ref: str, digest: Hex64 }
AbiDescriptorRef { ref: str, digest: Hex64 }
RecipeSchemaRef { schema: hsx.unwind-recipe/1 | hsx.location-recipe/1,
                  digest: Hex64 }

ImageDebugBundleIdentityPayload {
  bundle_schema: "hsx.image-debug-bundle/1",
  artifact_ref: ArtifactRef,
  architecture_descriptor: DescriptorDigestRef,
  abi_descriptor: DescriptorDigestRef,
  symbol_model: ComponentDigestRef(schema="hsx.debug-component.symbol-model/1"),
  unwind_recipe: ComponentDigestRef(schema="hsx.unwind-recipe/1"),
  location_recipe: ComponentDigestRef(schema="hsx.location-recipe/1"),
  source_identity_manifest_ref: StructuredDigest,
  required_debug_capabilities: tuple[str, ...],
  interpretation_schema_versions: tuple[tuple[str, CanonicalUInt64], ...],
}
ImageDebugBundleRef { ref_schema: "hsx.image-debug-bundle-ref/1",
                      artifact_ref: ArtifactRef,
                      digest_algorithm: "sha256", bundle_digest: Hex64 }
ImageDebugBindingPayload {
  binding_schema: "hsx.image-debug-binding/1",
  loaded_image_ref: LoadedImageRef,
  image_debug_bundle_ref: ImageDebugBundleRef,
  accepted_architecture_descriptor_ref: str,
  accepted_abi_descriptor_ref: str,
  accepted_image_debug_capability_profile: str,
}
ImageDebugBinding { payload: ImageDebugBindingPayload, binding_digest: Hex64 }
SourceRef { image_debug_bundle_ref: ImageDebugBundleRef, logical_id: str,
            content_digest: ContentDigest, byte_length: CanonicalUInt64 }
AddressSpaceId { value: str }
HsxAddress { space: AddressSpaceId, unsigned_value: int >= 0 }
HsxAddressRange { start: HsxAddress, length_units: int >= 0 }
AddressSpaceDescriptor { space: AddressSpaceId, unit: str,
                         bits_per_unit: int >= 1, width_bits: int >= 1,
                         legal_ranges: tuple[HsxAddressRange, ...],
                         byte_order: LITTLE | BIG, alignment: int >= 1,
                         wrap_policy: FORBIDDEN | EXPLICIT,
                         permissions: frozenset[READ | WRITE | EXECUTE] }
ArchitectureDescriptor { ref: ArchitectureDescriptorRef,
                         descriptor_version: CanonicalUInt64,
                         instruction_encoding: str,
                         container_header_byte_order: LITTLE | BIG,
                         instruction_serialization_byte_order: LITTLE | BIG,
                         register_width_bits: int >= 1,
                         register_byte_order: LITTLE | BIG,
                         register_count: int >= 1,
                         spaces: tuple[AddressSpaceDescriptor, ...],
                         register_order: tuple[str, ...],
                         pc_space: AddressSpaceId,
                         sp_space: AddressSpaceId,
                         psw_width_bits: int >= 1,
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
  evidence_grade: PORTABLE | LEGACY_DEGRADED,
}
```

Portable bundle construction always carries both
`ImageDebugBundleIdentityPayload` and its resulting `ImageDebugBundleRef`; the ref does not
absorb descriptor/component fields. Binding validation recomputes the identity payload digest,
requires it to equal `bundle_digest`, then recomputes the exact binding payload including
`accepted_image_debug_capability_profile`. Any mapping that changes a normative key, excludes
a mandatory field or includes a local/provenance field is `CORRUPT` and produces no ref/binding.

`TargetRef.canonical_ref` is the opaque canonical scalar reference supplied with the frozen
HSX TargetRef; it is not derived from PID, target_id or display data. LoadedImageRef retains
the complete TargetRef as its Python field, but `canonical_payload()` emits
`executive_instance_ref.value` for `executive_instance_ref` and
`target_ref.canonical_ref` for the scalar `target_ref` key exactly as canonical vector 4.
Within one accepted identity registry, reuse of one canonical_ref with different TargetRef
fields is `CORRUPT`; absence of canonical_ref prevents canonical LoadedImageRef construction.

ArchitectureDescriptor.register_order contains exactly register_count unique GPR IDs, every
listed GPR value uses register_width_bits, and
pc_space/sp_space must name declared address spaces. `instruction_encoding` is the exact
opaque accepted encoding/profile ID; container-header and instruction serialization byte order
are independent from guest data/register/stack space byte order. Missing/unknown version,
encoding or serialization fields make the descriptor unsupported and it cannot drive address,
register or disassembly behavior.
The declared register order exposed to RegisterSelection is
`register_order + ("PC", "SP", "PSW")`. PC width is pc_space.width_bits, SP width is
sp_space.width_bits, PSW width is psw_width_bits, and GPRs use register_width_bits. Explicit
selection accepts only those declared IDs.

`StopEpochId` is one opaque non-empty exact string; it is never parsed for generation.
`supported_read_sets` uses the frozen names `registers`, `memory`, `disassembly`, `stack`, and
`resources`; a service requiring an absent set returns `UNAVAILABLE`.

`ArchitectureDescriptor` contains named spaces with unit, width, legal half-open ranges,
byte order, alignment, permissions and wrap policy. Public operations are checked:

```text
validate(address) -> AddressResult
add(address, delta_units: int >= 0, mode: CHECKED | WRAP) -> AddressResult
subtract(address, delta_units: int >= 0, mode: CHECKED | WRAP) -> AddressResult
range(start, length_units: int >= 0) -> AddressRangeResult
units_for_bytes(space: AddressSpaceId, byte_length: int >= 0) -> UnitCountResult
bytes_for_units(space: AddressSpaceId, length_units: int >= 0) -> ByteLengthResult
format(address) -> str

DebugBindingValidator.validate(binding: ImageDebugBinding,
                               bundle_identity: ImageDebugBundleIdentityPayload,
                               architecture: ArchitectureDescriptor,
                               abi: AbiDescriptorRef)
    -> ResolutionResult[ImageDebugBinding]
```

No public or private RF-004 operation may apply `0xFFFF`, `0xFFFFFFFF`, modulo, truncation or
wrap unless an explicit descriptor space declares wrap and the caller passes `WRAP`.
`CHECKED` never wraps and neither operation has an implicit/default mode.
Overflow, underflow, wrong space, misalignment, range crossing and permission failure are typed
failures. Addresses in different spaces never compare as interchangeable.

HsxAddress.unsigned_value and every range/arithmetic delta are measured in the named space's
declared address units; a half-open range ends at `start.unsigned_value + length_units`.
AddressSpaceDescriptor.alignment and legal-range endpoints use those same units, while
width_bits constrains unsigned_value itself. `format` uses width_bits and never bits_per_unit.
`unit="byte"` requires bits_per_unit=8. Other exact unit names are allowed, but byte conversion
is supported only when bits_per_unit is divisible by 8: bytes_per_unit=bits_per_unit/8,
byte_length must be an exact multiple for units_for_bytes, and multiplication/division is
checked. Non-byte-aligned units return UNIT_CONVERSION_UNSUPPORTED; a non-multiple byte request
returns MISALIGNED. Snapshot memory reads take byte_length and must perform this conversion
before range validation; no delta is silently interpreted as bytes.

DebugBindingValidator is the single public check used before artifact parsing,
recipe/location evaluation, stack walking and inspection-service construction. It recomputes
bundle_identity's canonical digest and first-match returns:

| Condition | ResolutionStatus | Diagnostic code |
|---|---|---|
| loaded-image ArtifactRef != bundle-ref ArtifactRef | `ARTIFACT_MISMATCH` | `artifact_ref_mismatch` |
| bundle-identity ArtifactRef != bundle-ref ArtifactRef | `ARTIFACT_MISMATCH` | `artifact_ref_mismatch` |
| recomputed bundle digest != binding payload bundle ref digest | `ARTIFACT_MISMATCH` | `bundle_digest_mismatch` |
| recomputed canonical binding payload digest != binding.binding_digest | `ARTIFACT_MISMATCH` | `binding_digest_mismatch` |
| binding accepted architecture ref != architecture.ref.ref | `ARTIFACT_MISMATCH` | `binding_architecture_ref_mismatch` |
| bundle identity architecture ref or digest != architecture.ref | `ARTIFACT_MISMATCH` | `bundle_architecture_mismatch` |
| binding accepted ABI ref != abi.ref | `ARTIFACT_MISMATCH` | `binding_abi_ref_mismatch` |
| bundle identity ABI ref or digest != abi | `ARTIFACT_MISMATCH` | `bundle_abi_mismatch` |
| every check matches | `RESOLVED` | none |

Failure publishes no validated descriptor and the caller performs no parse/read/evaluation.

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
- `ARTIFACT_MISMATCH`
- `UNSUPPORTED`
- `CORRUPT`

`ContextBindingStatus`:

- `BOUND`
- `UNAVAILABLE`
- `STALE`
- `ARTIFACT_MISMATCH`

`InspectionOpenStatus`: `OPENED`, `UNAVAILABLE`, `STALE`, `ARTIFACT_MISMATCH`

`InvalidationStatus`: `INVALIDATED`, `ALREADY_STALE`, `UNKNOWN_EPOCH`

`ServiceCloseStatus`: `CLOSED`, `ALREADY_CLOSED`

`AddressStatus`:

- `VALID`
- `UNKNOWN_SPACE`
- `OVERFLOW`
- `UNDERFLOW`
- `MISALIGNED`
- `OUT_OF_RANGE`
- `PERMISSION_DENIED`
- `WRAP_FORBIDDEN`
- `UNIT_CONVERSION_UNSUPPORTED`

Every result is contract-safe immutable under the supported mutation model and contains status,
exact input/evidence identity, zero or more typed values/candidates, and ordered structured diagnostics. `RESOLVED`/`COMPLETE` requires
exactly the evidence required by the service. `AMBIGUOUS` never contains a preferred or
silently selected candidate. `PARTIAL` names the missing pieces and never pads, truncates or
invents values.

### Supported-mutation and contract-safe immutability model

Post-construction immutability means that no supported debugger API operation or mutation of
caller-owned construction inputs may change the declared value-state of an accepted result or
DTO after construction. Mutable caller containers and mutable implementation records are
copied/normalized into their declared frozen representation before publication. A generic or
nested payload that cannot satisfy the boundary below fails construction/classification rather
than publishing a mutable reference.

It does not require isolation from hostile or reflection-level mutation of Python type
definitions/runtime internals. The following are outside the supported mutation model and are
not conformance failures for snapshot immutability:

- monkey-patching/rebinding Enum classes, members or descriptors;
- editing Enum internals such as `_member_map_`, `_value_` or other runtime metadata;
- `object.__setattr__`-style bypasses of frozen/public assignment rules;
- module/class replacement or equivalent Python runtime-internal mutation;
- mutable external state reachable only through a non-contract custom property.

Generic result payloads and nested public DTO fields contain only recursively contract-safe
immutable values:

- exact immutable scalar values and `bytes`;
- approved closed Enum atoms named by this interface;
- frozen value/identity DTOs whose every declared field is contract-safe;
- tuples and frozensets whose members are recursively contract-safe;
- explicitly frozen value objects admitted by a named public schema in this interface.

Generic container normalization is exact: a list becomes a same-order tuple; a set becomes a
frozenset; and a dict becomes a tuple of recursively contract-safe `(key, value)` tuples in the
dict's insertion order. No unnamed read-only mapping type is published. When a public field
declares a named frozen DTO rather than a generic container, normalization constructs that DTO
or rejects the input.

An approved closed Enum is a contract-safe immutable atom when the exact canonical member is
retained, its schema-visible value is an immutable scalar or recursively contract-safe
tuple/value, and contract semantics depend only on exact Enum type/member identity plus the
declared schema-visible name/value. Exact member identity is required; cloning, proxying,
wrapping or token replacement is neither required nor permitted. Arbitrary caller Enum types,
custom properties and mutable non-schema state do not become contract-safe merely by being an
`Enum` instance.

The public schemas below are unchanged from version `1`. If an RF-004 required public value
cannot fit this contract-safe boundary without a schema change, implementation stops and
returns to Steering. Normative cases and explicit non-cases are frozen in
`DBG-CF-001-005-001`.

### Frozen envelope and record schemas

All tuples below are ordered and contract-safe immutable. IDs are opaque non-empty exact strings.

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

InspectionOpenResult { status: InspectionOpenStatus,
                       session: EpochInspectionSession | None,
                       diagnostics: tuple[Diagnostic, ...] }
InvalidationResult { status: InvalidationStatus, stop_epoch_id: StopEpochId,
                     diagnostics: tuple[Diagnostic, ...] }
ServiceCloseResult { status: ServiceCloseStatus,
                     invalidation: InvalidationResult | None,
                     diagnostics: tuple[Diagnostic, ...] }
HandleResolution { status: COMPLETE | UNKNOWN_HANDLE | STALE,
                   context: InspectionContext,
                   kind: FRAME | SCOPE | VARIABLE,
                   object_key: tuple | None,
                   diagnostics: tuple[Diagnostic, ...] }

AddressResult { status: AddressStatus, value: HsxAddress | None,
                diagnostics: tuple[Diagnostic, ...] }
AddressRangeResult { status: AddressStatus, value: HsxAddressRange | None,
                     diagnostics: tuple[Diagnostic, ...] }
UnitCountResult { status: AddressStatus, value: int | None,
                  diagnostics: tuple[Diagnostic, ...] }
ByteLengthResult { status: AddressStatus, value: int | None,
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
SourceIdentityRecord { logical_id: str, content_digest: ContentDigest,
                       byte_length: CanonicalUInt64,
                       media_type_or_language: str | None }
SourceIdentityManifest { schema: "hsx.source-identity-manifest/1",
                         records: tuple[SourceIdentityRecord, ...] }
FunctionRecord { function_id: str, name: str, linkage_name: str | None,
                 range: HsxAddressRange,
                 definition: SourceLocation | None }
SymbolRecord { symbol_id: str, name: str,
               kind: FUNCTION | LABEL | GLOBAL | LOCAL | CONSTANT,
               address: HsxAddress | None, byte_size: int >= 0,
               function_id: str | None, lexical_scope_id: str | None,
               type_id: str | None, declaration_order: int >= 0 }
SourceLocation { source: SourceRef, line: int >= 1, column: int >= 1 | None,
                 discriminator: int | None }
TypeMember { name: str, type_id: str, bit_offset: int >= 0, bit_size: int >= 1 }
TypeRecord { type_id: str, name: str,
             kind: INTEGER | FLOAT | POINTER | ARRAY | STRUCT | UNION | OPAQUE,
             bit_size: int >= 1, byte_order: LITTLE | BIG,
             members: tuple[TypeMember, ...] }
LexicalScopeRecord { lexical_scope_id: str, function_id: str,
                     parent_scope_id: str | None, pc_range: HsxAddressRange,
                     declaration_order: int >= 0 }
InstructionRecord { instruction_id: str, address: HsxAddress, byte_size: int >= 1,
                    encoded_word: int | None, function_id: str | None,
                    source: SourceLocation | None,
                    classification: USER | COMPILER_GENERATED | UNMAPPED }
MemoryRegion { region_id: str, name: str, kind: str, range: HsxAddressRange,
               permissions: frozenset[READ | WRITE | EXECUTE] }
UnwindRow { row_id: str, binding: ImageDebugBinding, pc_range: HsxAddressRange,
            abi: AbiDescriptorRef, schema: RecipeSchemaRef,
            cfa_expression: RecipeExpression,
            caller_pc_rule: RecipeRule, caller_sp_rule: RecipeRule,
            caller_frame_base_rule: RecipeRule | None,
            register_rules: tuple[tuple[str, RecipeRule], ...],
            boundary: ORDINARY | ENTRY | EPILOGUE | TERMINAL | UNSUPPORTED,
            call_site_adjustment: int | None }
LocationRow { row_id: str, binding: ImageDebugBinding, symbol_id: str,
              lexical_scope_id: str | None, function_id: str | None,
              pc_range: HsxAddressRange, declared_type_id: str | None,
              declared_bit_size: int >= 1, abi: AbiDescriptorRef,
              value_byte_order: LITTLE | BIG,
              frame_binding: SELECTED_FRAME,
              schema: RecipeSchemaRef,
              location_form: LocationForm }
```

Symbol kind invariants are exact. FUNCTION requires address, non-null function_id resolving
to the exact FunctionRecord and lexical_scope_id=None. LABEL requires address; its optional
function_id must resolve to a FunctionRecord, and lexical_scope_id may be non-null only when
it resolves inside that same function. FUNCTION/LABEL have no LocationRow. LOCAL requires
address=None plus non-null function_id/lexical_scope_id. GLOBAL requires
address=None plus function_id=None/lexical_scope_id=None. CONSTANT requires address=None and
either both function/scope IDs non-null or both None. Every GLOBAL/LOCAL/CONSTANT value is
obtained only through a matching LocationRow form (`static_address`, register/frame expression,
value, pieces, optimized_out or unavailable); no static/sentinel address is stored in
SymbolRecord. SymbolExpression is valid only for address-bearing FUNCTION/LABEL; variable
kinds use VariableExpression and LocationEvaluator.
LocationRow is static metadata and `frame_binding=SELECTED_FRAME` is the only `1.1` value;
LocationEvaluator binds it to the explicit UnwindFrame argument and requires matching context,
function and frame PC. No current/top-frame lookup or runtime handle is stored in the artifact.
When declared_type_id is present it must resolve to exactly one TypeRecord whose bit_size and
byte_order equal the LocationRow fields; mismatch or missing type is CORRUPT. A null type ID
still retains explicit declared_bit_size/value_byte_order.

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
DomainHandle { context: InspectionContext,
               kind: FRAME | SCOPE | VARIABLE, serial: int >= 1 }
FrameRecord { context: InspectionContext, handle: DomainHandle, unwind: UnwindFrame }
FramePage { total_frames: int >= 0, offset: int >= 0,
            frames: tuple[FrameRecord, ...] }
ScopeRecord { context: InspectionContext, handle: DomainHandle,
              frame_handle: DomainHandle,
              kind: REGISTERS | LOCALS | GLOBALS,
              name: str, expensive: bool }
ScopeSet { frame_handle: DomainHandle, scopes: tuple[ScopeRecord, ...] }
ValuePiece { destination_bit_offset: int >= 0, bit_size: int >= 1,
             source_bit_offset: int >= 0, raw_bits: bytes | None,
             status: AVAILABLE | UNAVAILABLE, reason: str | None }
EvaluatedValue { symbol_id: str, name: str, declared_type_id: str | None,
                 display_value: str, raw_bytes: bytes | None,
                 bit_size: int >= 1 | None,
                 location_status: AVAILABLE | PARTIAL | OPTIMIZED_OUT | UNAVAILABLE,
                 pieces: tuple[ValuePiece, ...] }
ExpressionValue { expression_kind: REGISTER | VARIABLE | SYMBOL | CONSTANT | MEMORY,
                  source_id: str | None, display_value: str,
                  raw_bytes: bytes | None, bit_size: int >= 1,
                  status: AVAILABLE | PARTIAL | OPTIMIZED_OUT | UNAVAILABLE,
                  pieces: tuple[ValuePiece, ...] }
SymbolVariableRecord { context: InspectionContext, handle: DomainHandle,
                       scope_handle: DomainHandle, symbol_id: str,
                       declaration_order: int >= 0, evaluated: EvaluatedValue }
RegisterVariableRecord { context: InspectionContext, handle: DomainHandle,
                         scope_handle: DomainHandle, register_id: str,
                         register_order: int >= 0, evaluated: ExpressionValue }
ScopeValueRecord = SymbolVariableRecord | RegisterVariableRecord
VariablePage { scope_handle: DomainHandle, total_variables: int >= 0,
               offset: int >= 0,
               variables: tuple[ScopeValueRecord, ...] }
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
`all_declared=false` with unique explicit IDs. Explicit register results follow request order;
all-declared results follow the descriptor GPR order then PC, SP, PSW. Stack frames are ordered
top-first by ascending frame_index; scopes are ordered REGISTERS, LOCALS, GLOBALS;
symbol variables are ordered by `(declaration_order, symbol_id)` and register variables by
`register_order`; disassembly is ordered by checked
ascending code address. `PageRequest` slices the complete ordered collection as
`[offset:min(offset+limit,total)]`; offset at/beyond total returns an empty tuple with the same
total, and every non-empty page contains exactly that slice. Pagination returns the same total
and order for one immutable context. Memory segments are ordered, non-overlapping and exactly
cover the requested range when status is COMPLETE; gaps are explicit UNAVAILABLE segments in
a PARTIAL result.
MemorySegment.offset/requested_length and MemoryBlock.requested_length are bytes relative to
the converted start address; address-space ranges remain unit-counted as defined above.

```text
ScalarBytes.encode(value: int, signed: bool, bit_width: int >= 1,
                   byte_order: LITTLE | BIG) -> bytes
```

ScalarBytes produces exactly `ceil(bit_width/8)` bytes. The value must fit the declared
unsigned or two's-complement signed range. Negative signed values are reduced modulo
`2^bit_width`; unused high padding bits in the most-significant storage byte are sign bits for
negative signed values and zero otherwise; fixed-length output is then emitted in byte_order.
There is no host-endian conversion, truncation or minimal-length form.

For an `AVAILABLE` scalar, `raw_bytes` contains the complete declared value and `pieces` is
empty. `PARTIAL` is legal only for a structural pieces location: `raw_bytes` is None,
ValuePieces have non-overlapping destination ranges within declared `bit_size`, every missing
piece is retained with `UNAVAILABLE` plus reason, and available pieces retain exact source and
destination bit ranges without padding. `OPTIMIZED_OUT`/`UNAVAILABLE` have no raw bytes and no
fabricated piece. SymbolVariableRecord always returns its exact SymbolRecord.symbol_id and
VARIABLE handle; duplicate display names therefore remain distinct. RegisterVariableRecord
uses the exact descriptor register_id/order, ExpressionValue(kind=REGISTER,
source_id=register_id), no symbol/address, and its own VARIABLE handle. RF-004 returns no child
scope handle; compound layout remains available through TypeRecord.members without an invented
handle traversal contract.

Raw-byte source is exact: RegisterVariableRecord/RegisterExpression uses
ArchitectureDescriptor.register_byte_order; VariableExpression uses LocationRow.value_byte_order
and RecipeScalar.signed; SymbolExpression encodes the address unsigned using its
AddressSpaceDescriptor.byte_order/width_bits; ConstantExpression uses its explicit byte_order
and unsigned encoding; MemoryExpression returns the exact bytes read, with its byte_order used
only to interpret display_value. Address/location memory forms preserve exact bytes read; value/
register/constant forms use ScalarBytes. AVAILABLE never leaves raw_bytes unspecified.

`SnapshotExpression` is a closed typed union:

```text
RegisterExpression { register_id: str }
VariableExpression { symbol_id: str, function_id: str | None,
                     lexical_scope_id: str | None }
SymbolExpression { symbol_id: str }
ConstantExpression { unsigned_value: int >= 0, bit_width: int >= 1,
                     byte_order: LITTLE | BIG }
MemoryExpression { address: HsxAddress, bit_width: int >= 1,
                   byte_order: LITTLE | BIG }
```

There are no call, assignment, mutation, persistent-watch or raw-string variants. Frontend
string parsing and presentation remain outside this interface.
ExpressionValue.source_id is the register/variable/symbol ID for those variants and None for
constant/memory. Only a VariableExpression backed by a PIECES LocationForm may be PARTIAL and
carry ValuePieces; a missing register/symbol/scalar/memory value is UNAVAILABLE, never padded.
VariableExpression function/scope IDs must exactly equal its GLOBAL/LOCAL/CONSTANT
SymbolRecord: locals pass both non-null, globals pass None/None, and constants pass the pair
their symbol declares. Evaluation uses the explicit selected frame PC and never invents a
global-scope sentinel.

Source locator schemas:

```text
ExactSourceOverride { source: SourceRef, locator: str }
SourcePrefixMapping { logical_prefix: str, local_root: str }
SourceLocatorPolicy { exact_overrides: tuple[ExactSourceOverride, ...],
                      prefix_mappings: tuple[SourcePrefixMapping, ...],
                      search_roots: tuple[str, ...] }
SourceCandidate { locator: str, discovery: OVERRIDE | PREFIX | SEARCH_ROOT,
                  byte_length: int >= 0, content_digest: ContentDigest,
                  content_matches: bool }
SourceResolution { status: ResolutionStatus, source: SourceRef,
                   candidates: tuple[SourceCandidate, ...],
                   resolved_locator: str | None,
                   diagnostics: tuple[Diagnostic, ...] }
LegacyArtifactProvenance { profile: "hsx.python-debug-legacy/1",
                           identity_status: LEGACY_UNVERIFIED,
                           sym_content_digest: ContentDigest,
                           hxe_crc32: int in 0..0xffffffff }
LegacySourceSpelling { file: str, directory: str | None }
LegacyFunctionRecord { function_id: str, name: str, linkage_name: str | None,
                       range: HsxAddressRange,
                       definition_spelling: LegacySourceSpelling | None,
                       definition_line: int >= 1 | None }
LegacyInstructionRecord { instruction_id: str, address: HsxAddress,
                          byte_size: int >= 1, function_id: str | None,
                          source_spelling: LegacySourceSpelling | None,
                          line: int >= 1 | None, column: int >= 0 | None }
LegacyResolutionResult[T] { status: ResolutionStatus,
                            provenance: LegacyArtifactProvenance,
                            values: tuple[T, ...],
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
                         bundle_identity: ImageDebugBundleIdentityPayload,
                         source_manifest: SourceIdentityManifest,
                         architecture: ArchitectureDescriptor,
                         abi: AbiDescriptorRef,
                         components: tuple[DebugComponentInput, ...])
    -> ResolutionResult[DebugArtifactIndex]
LegacySymbolAdapter.build(sym_bytes: bytes,
                          expected_hxe_crc32: int,
                          architecture: ArchitectureDescriptor)
    -> LegacyResolutionResult[LegacyDebugArtifactIndex]
```

Portable build first requires DebugBindingValidator RESOLVED for exact architecture and ABI,
then rechecks each input byte digest/schema against the bundle
before parsing and validates every typed address/range/row through that descriptor. Ref or
digest mismatch is returned by DebugBindingValidator and publishes no index.
Legacy build requires `.sym` version 1 and exact `hxe_crc == expected_hxe_crc32`; it returns a
different `LegacyDebugArtifactIndex` type with mandatory LegacyArtifactProvenance. That type
has no ImageDebugBinding accessor, no SourceRef, no portable unwind/location rows and no
`hsx.debug.image-bundle/1` claim.

Public queries:

```text
binding() -> ImageDebugBinding
bundle_identity() -> ImageDebugBundleIdentityPayload
source_identities() -> tuple[SourceRef, ...]
functions() -> tuple[FunctionRecord, ...]
types() -> tuple[TypeRecord, ...]
type_by_id(type_id: str) -> ResolutionResult[TypeRecord]
lexical_scopes(function_id: str, frame_pc: HsxAddress)
    -> tuple[LexicalScopeRecord, ...]
variables_in_scope(lexical_scope_id: str, frame_pc: HsxAddress)
    -> tuple[SymbolRecord, ...]
global_variables() -> tuple[SymbolRecord, ...]
symbols_named(name: str) -> ResolutionResult[SymbolRecord]
instruction_at(address: HsxAddress) -> ResolutionResult[InstructionRecord]
source_locations(source: SourceRef, line: int, column: int | None) -> ResolutionResult[InstructionRecord]
memory_regions() -> tuple[MemoryRegion, ...]
unwind_rows(pc: HsxAddress, function_id: str | None) -> ResolutionResult[UnwindRow]
location_rows(symbol_id: str, function_id: str | None,
              lexical_scope_id: str | None,
              frame_pc: HsxAddress) -> ResolutionResult[LocationRow]

LegacyDebugArtifactIndex.provenance() -> LegacyArtifactProvenance
LegacyDebugArtifactIndex.functions() -> tuple[LegacyFunctionRecord, ...]
LegacyDebugArtifactIndex.symbols_named(name: str) -> LegacyResolutionResult[SymbolRecord]
LegacyDebugArtifactIndex.instruction_at(address: HsxAddress)
    -> LegacyResolutionResult[LegacyInstructionRecord]
LegacyDebugArtifactIndex.source_spelling_locations(spelling: LegacySourceSpelling,
                                                    line: int,
                                                    column: int | None)
    -> LegacyResolutionResult[LegacyInstructionRecord]
LegacyDebugArtifactIndex.memory_regions() -> tuple[MemoryRegion, ...]
```

Index ordering is observable and fixed: functions by `(space.value,
range.start.unsigned_value, function_id)`; symbol candidates by
`(symbol_kind_rank, symbol_id)` where ranks are
FUNCTION=0, LABEL=1, GLOBAL=2, LOCAL=3, CONSTANT=4; instructions/source-location candidates by
`(space.value, address.unsigned_value, instruction_id)`; memory regions by
`(space.value, range.start.unsigned_value, region_id)`; unwind/location rows by
`(space.value, pc_range.start.unsigned_value, row_id)`; SourceRefs by logical_id UTF-8; types by type_id;
lexical scopes by `(declaration_order, lexical_scope_id)`; variables by
`(declaration_order, symbol_id)`. Exact duplicate records are rejected as corrupt;
distinct same-name/same-address records remain distinct candidates.

Query cardinality is fixed: direct enumeration methods return their possibly-empty ordered
tuple. `type_by_id`, `instruction_at`, `unwind_rows` and `location_rows` are RESOLVED only for
exactly one value, UNAVAILABLE for zero and CORRUPT for duplicate/overlapping identity.
`symbols_named` is UNAVAILABLE for zero, RESOLVED for one and AMBIGUOUS with every candidate
for more than one. `source_locations` explicitly asks for the complete executable instruction
set, so it is UNAVAILABLE for zero and RESOLVED with the ordered one-or-more set; it never
chooses one address.

`SymbolRecord.symbol_id` is the sole variable identity. Every LocationRow.symbol_id must
resolve to exactly one LOCAL, GLOBAL or CONSTANT SymbolRecord; its nullable function/lexical-
scope fields must exactly equal that record and every variables_in_scope result must have the
requested non-null scope while global_variables returns only GLOBAL or global CONSTANT. Missing,
duplicate or cross-scope joins make the portable component/index `CORRUPT`. VariableExpression,
EvaluatedValue, SymbolVariableRecord, location_rows and symbol VARIABLE handle keys all carry that same
symbol_id unchanged; no secondary variable-ID namespace exists.

Duplicate symbol names and multiple executable addresses remain candidate sets. Source records
are keyed by exact `SourceRef`; no basename alias is part of the portable index. All code/data
values are typed addresses. Malformed fields, overlap where forbidden, unsupported schemas and
binding/component mismatch are explicit outcomes and publish no accepted index.

The legacy `.sym` adapter is a separate, named compatibility input. It may preserve only
behaviors classified by `DBG-SL-001-005-001` golden evidence. It must validate schema version
and supplied HXE CRC evidence, convert every integer through an explicit descriptor, preserve
duplicate candidates and exact spelling, and return only the mandatory
`hsx.python-debug-legacy/1`/LEGACY_UNVERIFIED provenance type. It may not claim
`hsx.debug.image-bundle/1` conformance, produce SourceRef, or be passed where a
DebugArtifactIndex/ImageDebugBinding is required. Legacy functions/instructions use only
LegacySourceSpelling records; portable FunctionRecord/SourceLocation/SourceRef types are never
returned transitively by the legacy index.

## 6. Source resolver

`SourceResolver` keeps identity and local locator policy separate:

```text
resolve(source: SourceRef, policy: SourceLocatorPolicy) -> SourceResolution
```

`SourceLocatorPolicy` contains only explicit local locators: exact logical-ID overrides,
prefix mappings and ordered search roots. Candidate discovery may use the exact logical ID
and explicit mappings. It must not use basename guessing or global lowercase/casefold identity.

Resolution tiers are fixed: one exact per-SourceRef override; otherwise every longest-prefix
mapping for the exact logical ID; otherwise each search root in declared order joined with the
full logical ID. The first tier that yields existing locators is the winning tier, but every
candidate in that tier is collected and content-checked before selection. Multiple matching
prefix rules with the same longest prefix remain candidates; declaration order is diagnostic,
not a tie-breaker. Duplicate physical locators are deduplicated only by exact resolved locator
string plus verified bytes, never by basename or casefold.

Outcome precedence is first-match and frozen. A configured exact SourceRef override is the
only candidate tier and never falls through: invalid locator is CORRUPT/source_locator_invalid,
missing path is UNAVAILABLE, present mismatched bytes is CONTENT_MISMATCH, and one exact match
is RESOLVED. Without override, no existing candidate is UNAVAILABLE. After exact physical
deduplication, a host-filesystem case collision that cannot address each spelling separately is
CASE_COLLISION. More than one remaining distinct existing locator is AMBIGUOUS regardless of
how many candidates match content; all content-match flags remain diagnostic and no candidate
is preferred. Exactly one remaining locator is RESOLVED only when digest+length match,
otherwise CONTENT_MISMATCH. Thus a single matching path among several never silently wins.

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
implement the port with contract-safe immutable snapshot data. Runtime adapters belong to later authorized
work and may not be added in RF-004.

## 8. Recipes, locations and stack

`RecipeEvaluator` implements only the frozen `hsx.unwind-recipe/1` and
`hsx.location-recipe/1` declarative schemas. Allowed opcodes, terminal forms and bounds are
exactly those in `HSX-D-002`; there are no branches, loops, recursive recipe calls, host-endian
reads, implicit casts, masks or wrapping.

The Debugger Python projection is frozen as this closed union; each record rejects unknown
fields and wrong/missing operands:

```text
RegValueOp { opcode: "reg_value", register_id: str }
SpecialValueOp { opcode: "special_value", special: PC | SP | PSW }
ConstUOp { opcode: "const_u", value: int >= 0, bit_width: int >= 1 }
ConstSOp { opcode: "const_s", value: int, bit_width: int >= 1 }
StaticAddressOp { opcode: "static_address", address: HsxAddress }
ToAddressOp { opcode: "to_address", space: AddressSpaceId }
CfaOp { opcode: "cfa" }
FrameBaseOp { opcode: "frame_base" }
AddSConstCheckedOp { opcode: "add_sconst_checked", signed_delta: int }
DerefUOp { opcode: "deref_u", byte_length: 1 | 2 | 4 | 8 | 16,
           byte_order: LITTLE | BIG }
BitSliceOp { opcode: "bit_slice", source_bit_offset: int >= 0,
             bit_size: int >= 1 }
RecipeOpcode = the closed union above
RecipeExpression { role: CFA | CALLER_PC | CALLER_SP | CALLER_FRAME_BASE |
                         REGISTER | LOCATION,
                   opcodes: tuple[RecipeOpcode, ...],
                   required_result: ADDRESS | UNSIGNED_SCALAR | SIGNED_SCALAR | REGISTER,
                   required_bit_width: int >= 1 | None }
RecipeRule { kind: EXPRESSION | SAME | UNDEFINED | UNAVAILABLE | OPTIMIZED_OUT,
             expression: RecipeExpression | None, reason: str | None }
LocationPieceRule { destination_bit_offset: int >= 0, bit_size: int >= 1,
                    expression: RecipeExpression, source_bit_offset: int >= 0 }
LocationForm { kind: ADDRESS | VALUE | PIECES | OPTIMIZED_OUT | UNAVAILABLE,
               expression: RecipeExpression | None,
               pieces: tuple[LocationPieceRule, ...], reason: str | None }
RecipeScalar { signed: bool, bit_width: int >= 1, value: int }
RecipeAddress { address: HsxAddress }
RecipeRegister { register_id: str, bit_width: int >= 1, unsigned_value: int }
RecipeValue = RecipeScalar | RecipeAddress | RecipeRegister
RecipeEvaluationContext { context: InspectionContext, frame_index: int >= 0,
                          binding: ImageDebugBinding,
                          bundle_identity: ImageDebugBundleIdentityPayload,
                          architecture: ArchitectureDescriptor,
                          abi: AbiDescriptorRef,
                          pc: HsxAddress, sp: HsxAddress,
                          psw: RecipeScalar | None,
                          recovered_registers: RegisterSet,
                          cfa: HsxAddress | None, frame_base: HsxAddress | None }
RecipeBudget { opcodes_remaining: int >= 0, dereferences_remaining: int >= 0,
               bytes_remaining: int >= 0 }
RecipeEvaluationResult { status: COMPLETE | UNAVAILABLE | UNSUPPORTED | CORRUPT |
                                STALE | ARTIFACT_MISMATCH,
                         context: InspectionContext, value: RecipeValue | None,
                         budget_after: RecipeBudget,
                         diagnostics: tuple[Diagnostic, ...] }
```

Rule validity is exact: EXPRESSION alone has an expression and no reason; UNAVAILABLE and
OPTIMIZED_OUT alone have a reason; SAME/UNDEFINED have neither. ADDRESS/VALUE forms have one
expression, PIECES has 1..16 pieces, and terminal location forms have only a reason. Piece
destinations are non-overlapping and within declared result size. Unknown opcode/field is
`UNSUPPORTED`; wrong arity/type/width/stack/address/piece coverage is `CORRUPT`.

Before the first opcode, RecipeEvaluator calls DebugBindingValidator with the
evaluation binding/bundle/descriptor/ABI and requires binding.payload.loaded_image_ref ==
evaluation.context.image. Failure returns ARTIFACT_MISMATCH with the validator diagnostic and
executes no opcode/read. StackService performs the same validation from its DebugArtifactIndex,
requires every selected UnwindRow.abi to equal the supplied ABI, then selects rows.
LocationEvaluator requires row.binding == index.binding, validates
index.bundle_identity()/architecture/ABI, requires row.abi == ABI, and performs no evaluation
on mismatch.

Postfix stack transitions and value propagation are normative:

| Opcode | Stack input | Stack output / rule |
|---|---|---|
| `reg_value` | none | Push RecipeRegister with exact recovered register ID, descriptor width and unsigned bits; missing recovery is UNAVAILABLE. |
| `special_value PC` / `SP` | none | Push RecipeAddress in ArchitectureDescriptor pc_space/sp_space from the selected frame; absent value is UNAVAILABLE. |
| `special_value PSW` | none | Push unsigned RecipeScalar of exact psw_width_bits; absent value is UNAVAILABLE. |
| `const_u` | none | Push unsigned RecipeScalar; value must fit `0..2^bit_width-1`. |
| `const_s` | none | Push signed RecipeScalar; value must fit the two's-complement range for bit_width. |
| `static_address` | none | Validate the supplied address against its exact descriptor space/range/alignment and push RecipeAddress. |
| `to_address` | one RecipeScalar | Scalar must be non-negative; validate in the named space and push RecipeAddress. RecipeRegister is not implicitly cast. |
| `cfa` | none | Forbidden in role=CFA as recursive/cyclic CORRUPT; in other roles push already-computed context CFA, and absent CFA is CORRUPT/`cfa_not_computed`. |
| `frame_base` | none | Push context frame_base; absent frame base is UNAVAILABLE. |
| `add_sconst_checked` | one RecipeAddress or RecipeScalar | Checked add preserves address space or scalar signedness/bit_width; under/overflow, range hole or wrong type is CORRUPT. |
| `deref_u` | one RecipeAddress | Checked unit/byte conversion and SnapshotReadPort read exactly byte_length with declared byte_order; push unsigned RecipeScalar of `byte_length*8`; missing bytes are UNAVAILABLE, unsupported unit conversion is UNSUPPORTED, and misalignment is CORRUPT. |
| `bit_slice` | one RecipeScalar or RecipeRegister | Require `source_bit_offset+bit_size <= input width`; push unsigned RecipeScalar of bit_size. |

Each opcode pops exactly the listed inputs and pushes exactly one output. Stack underflow,
extra/wrong input kind, depth overflow or invalid width/value is CORRUPT at that opcode index.
Opcode/dereference/byte-budget exhaustion is UNSUPPORTED with `limit_exceeded` before the
operation. Evaluation succeeds only when all opcodes are consumed and the stack contains
exactly one value matching required_result: RecipeAddress with required_bit_width=None;
signed/unsigned RecipeScalar with exact required_bit_width and signedness; or RecipeRegister
with exact required_bit_width. Zero/multiple final values or any other result kind is CORRUPT.
No implicit extension, truncation, sign change, host endian or address/register cast occurs.

UnwindRow.cfa_expression must have role=CFA; caller_pc/sp/frame-base expression rules use their
matching roles; caller-register rules use REGISTER; every LocationForm expression/piece uses
LOCATION. Row/component validation rejects a role mismatch as CORRUPT. CFA is evaluated first;
snapshot/register/memory absence while computing it returns UNAVAILABLE and prevents dependent
rule evaluation. A `cfa` opcode inside CFA, repeated/non-progressing CFA or a CFA address cycle
is CORRUPT with the exact offending row/op/frame diagnostic, never UNAVAILABLE or fallback.

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
RecipeRequestLimits { max_frames: int in 1..64, max_pieces: int in 1..16 }

RecipeEvaluator.evaluate(evaluation: RecipeEvaluationContext,
                         expression: RecipeExpression,
                         read_port: SnapshotReadPort,
                         limits: RecipeLimits,
                         budget: RecipeBudget) -> RecipeEvaluationResult
```

`RecipeLimits` is the exact immutable accepted profile; an implementation with lower limits
must advertise a different degraded profile and cannot claim this one. A caller may lower only
the request's frame/piece maxima through `RecipeRequestLimits`; attempts to exceed the profile
are `UNSUPPORTED`. `StackService.unwind(context: InspectionContext,
index: DebugArtifactIndex, read_port: SnapshotReadPort,
architecture: ArchitectureDescriptor, abi: AbiDescriptorRef,
profile_limits: RecipeLimits,
request_limits: RecipeRequestLimits) ->
InspectionResult[tuple[UnwindFrame, ...]]` returns handle-free immutable frames bound to the
same context. Each frame has typed PC/SP/CFA/frame-base values,
function/source metadata where resolved, resume PC distinct from checked call-site PC, and
per-frame diagnostics. Terminal top level is explicit. Missing data returns partial/unavailable;
unsupported, corrupt and stale remain distinct. Every bound exhaustion is status
`UNSUPPORTED` with diagnostic code `limit_exceeded`, exactly as `HSX-D-002`; it is never a
separate status or truncated result. The service never retries with
a fixed R7 chain or invents a caller.

`LocationEvaluator.evaluate(context: InspectionContext, frame: UnwindFrame,
index: DebugArtifactIndex, variable: SymbolRecord, row: LocationRow,
read_port: SnapshotReadPort,
architecture: ArchitectureDescriptor,
abi: AbiDescriptorRef,
profile_limits: RecipeLimits, request_limits: RecipeRequestLimits) ->
InspectionResult[EvaluatedValue]` selects the exact
half-open PC row for the selected frame and returns register, address, value, bounded pieces,
optimized-out or unavailable results with declared width/endian/type preserved. A non-top-frame
local is evaluated from that frame/context, never current live registers.

## 9. Epoch-bound inspection service and handles

`InspectionService` is explicit composition over immutable dependencies and owns at most one
active EpochInspectionSession:

```text
InspectionService.create(index: DebugArtifactIndex,
                         read_port: SnapshotReadPort,
                         architecture: ArchitectureDescriptor,
                         abi: AbiDescriptorRef,
                         profile_limits: RecipeLimits,
                         stack_service: StackService,
                         location_evaluator: LocationEvaluator)
    -> ResolutionResult[InspectionService]
InspectionService.active_epoch_id() -> StopEpochId | None
InspectionService.open_epoch(context: InspectionContext,
                             request_limits: RecipeRequestLimits) -> InspectionOpenResult
InspectionService.invalidate_epoch(expected_epoch_id: StopEpochId,
                                   reason: str) -> InvalidationResult
InspectionService.close(reason: str) -> ServiceCloseResult

EpochInspectionSession.context() -> InspectionContext
EpochInspectionSession.is_active() -> bool
EpochInspectionSession.registers(selection: RegisterSelection) -> InspectionResult[RegisterSet]
EpochInspectionSession.stack(page: PageRequest) -> InspectionResult[FramePage]
EpochInspectionSession.scopes(frame_handle: DomainHandle) -> InspectionResult[ScopeSet]
EpochInspectionSession.variables(scope_handle: DomainHandle,
                                 page: PageRequest) -> InspectionResult[VariablePage]
EpochInspectionSession.evaluate_snapshot(frame_handle: DomainHandle,
                                         expression: SnapshotExpression) -> InspectionResult[ExpressionValue]
EpochInspectionSession.memory(address: HsxAddress,
                              byte_length: int) -> InspectionResult[MemoryBlock]
EpochInspectionSession.disassemble(address: HsxAddress,
                                   instruction_count: int) -> InspectionResult[DisassemblyBlock]

EpochHandleStore.create(context: InspectionContext) -> EpochHandleStore
EpochHandleStore.intern(kind: FRAME | SCOPE | VARIABLE,
                        object_key: tuple) -> InspectionResult[DomainHandle]
EpochHandleStore.resolve(handle: DomainHandle,
                         expected_kind: FRAME | SCOPE | VARIABLE) -> HandleResolution
EpochHandleStore.invalidate(reason: str) -> InvalidationResult
```

`create` applies this first-match validation and returns no service on failure:

| Condition | ResolutionStatus | Diagnostic code |
|---|---|---|
| DebugBindingValidator is not RESOLVED | propagate validator status | propagate validator code |
| binding accepted capability profile is not exactly `hsx.portable-debug-runtime/1` | `SCHEMA_UNSUPPORTED` | `inspection_profile_unsupported` |
| profile_limits differ from the exact accepted profile limits | `SCHEMA_UNSUPPORTED` | `recipe_profile_limits_mismatch` |
| every check passes | `RESOLVED` | none |

The successful service stores every dependency unchanged. No hidden default service, port,
limit or cache is constructed. `open_epoch` requires
context.image to equal the binding
payload LoadedImageRef and context.target to equal its TargetRef. Binding/image/artifact
mismatch follows the frozen ContextBinding status categories. The service retains every
invalidated StopEpochId and its exact InspectionContext until that service is closed. Before
opening, it rejects any ID in that stale history as STALE/`epoch_id_previously_invalidated`,
even when no session is active; an epoch ID never rebinds. If there is no active session and
the service is open, it creates one handle store and session. Opening the same exact InspectionContext is
idempotent only when request_limits also match and returns the existing session. Same context
with different limits returns UNAVAILABLE/`epoch_request_limits_conflict` and changes nothing.
Opening a different valid StopEpoch first
linearizes invalidation of the previous session/store, retains its epoch ID as stale, then
publishes the new session. Reusing an active epoch ID with any different context is STALE and
does not replace the active session.

`invalidate_epoch` is exact and idempotent: matching active ID invalidates session/store and
returns INVALIDATED; an ID retained in stale history returns ALREADY_STALE; an unseen ID
returns UNKNOWN_EPOCH. `close` is terminal: the first call invalidates any active epoch,
retains stale history and returns CLOSED plus that optional invalidation; later calls return
ALREADY_CLOSED. A closed service rejects every `open_epoch` as
UNAVAILABLE/`inspection_service_closed`. Direct EpochHandleStore.invalidate returns
INVALIDATED the first time and ALREADY_STALE on every repeat. Every method on an invalidated
session returns STALE with its original InspectionContext and allocates no handle/read.

Slice 006 converts handle-free `UnwindFrame`s from StackService into `FrameRecord`s and is the
only allocator of DomainHandle values. All returned frames, scopes and variables retain the
complete evidence tuple. `EpochHandleStore` allocates opaque domain handles monotonically
within one StopEpoch. Repeated/paged requests may
allocate more handles without invalidating earlier handles in the same epoch. For the exact
active context, an unknown serial or wrong kind returns `UNKNOWN_HANDLE`; an invalidated
session or a handle whose exact InspectionContext is retained in this service's stale history
returns `STALE`; every other foreign context returns `UNKNOWN_HANDLE`, including one with an
equal opaque epoch string. No outcome falls back
to a current/top/first frame. DAP integer IDs are outside this interface and later map to domain
handles without owning their lifetime.

Every DomainHandle embeds the store's complete InspectionContext. Within one epoch the store
interns exact object keys: FRAME uses frame_index; SCOPE uses
`(frame_handle.serial, scope_kind)`; symbol VARIABLE uses
`(scope_handle.serial, "symbol", declaration_order, symbol_id)` and register VARIABLE uses
`(scope_handle.serial, "register", register_order, register_id)`. Repeating the same query returns the
same handle; a new exact key receives the next never-reused serial. A handle kind/key mismatch
is `UNKNOWN_HANDLE`; a known serial from an invalidated epoch is `STALE`.
`intern` rejects a key not matching its declared kind as CORRUPT without allocating a serial;
`resolve` returns the exact interned key only for COMPLETE. A handle whose context differs
from the active store context is never looked up by serial: if its complete context equals a
retained stale context the session returns STALE, otherwise it returns UNKNOWN_HANDLE. Thus
equal opaque epoch strings/serials in independent services/targets/images cannot alias.

InspectionService and EpochHandleStore each serialize only lifecycle/handle-map mutations with
one internal lock. Snapshot reads and immutable index/recipe work may execute concurrently
outside that lock. Handle interning and invalidation are linearizable: invalidation wins before
any later allocation/read, and a completed immutable snapshot read may return only for the
still-matching session context. This is inspection lifetime bookkeeping, not controller/run
state ownership; later controller integration calls invalidate before target-mutating effects.

`SnapshotExpression` is a typed, side-effect-free AST over registers, selected-frame variables,
symbols/constants and explicit typed memory dereference. String parsing and DAP Watch policy
belong to later frontends; persistent live watches belong to RF-005 and are not created here.

Scope composition is fixed, not frontend policy. `scopes()` returns REGISTERS when the snapshot
declares register coverage, LOCALS when the frame resolves to exact function/PC lexical scopes,
and GLOBALS when the index has globals; absent capabilities/data omit that scope and add an
explicit diagnostic. There is no WATCH scope: each standard Watch/hover/evaluate request calls
`evaluate_snapshot()` independently. `variables()` maps the REGISTERS scope in descriptor order
to RegisterVariableRecord without synthesizing SymbolRecord/address; LOCALS come from
`lexical_scopes()` plus `variables_in_scope()` for the selected frame PC, and GLOBALS from
`global_variables()`. Local/global variables select exactly one applicable LocationRow and use
LocationEvaluator using the SymbolRecord's exact nullable function/scope IDs and selected frame
PC; globals pass None/None, locals pass both non-null. Zero rows is unavailable and overlap is
corrupt. No scope query invents a
variable, reads the current top frame or creates a persistent live watch.

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
| `DBG-SL-001-005-007` | Implement recipe DTO parsing/validation and bounded Recipe/Location evaluators |
| `DBG-SL-001-005-003` | Implement verified artifact index and explicit legacy `.sym` adapter |
| `DBG-SL-001-005-004` | Implement exact content-verified SourceResolver |
| `DBG-SL-001-005-005` | Implement snapshot-bound StackService over the signed recipe foundation |
| `DBG-SL-001-005-006` | Implement handles and integrated epoch-bound InspectionService |

Execution order is `001 -> 002 -> 007 -> 003 -> 004 -> 005 -> 006`. Slice 007 was allocated
after review 009 exposed the earlier sequencing contradiction; IDs are not recycled or
renumbered. Artifact Slice 003 consumes the signed recipe DTO/validator and cannot begin first.

Each Slice has a fresh worker, independent exact-head review, formal verification and Master
sign-off. Later Slices consume earlier signed interfaces. No RF-005 product work starts from
this frozen document: RF-005 remains blocked until RF-004 parent sign-off, remote publication
and a later Steering authorization.

## 12. Interface completion signal

`dbg.resolver-inspection/1.1` is accepted only when all seven Slices and RF-004 parent review,
verification and exact-head Master sign-off pass on remote-resolvable history. The decision
package must state exact interfaces, address/source/stack/variables/memory/disassembly
coverage, legacy reuse/retirement, degraded behavior and every review/verification/sign-off
head. Until then the interface is frozen for implementation but not an accepted prerequisite
for RF-005.
