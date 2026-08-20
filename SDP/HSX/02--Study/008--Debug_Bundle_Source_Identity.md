# HSX-ST-008 — Debug Bundle and Source Identity Canonicalization

- Status: **COMPLETE FOR MASTER SYNTHESIS**
- Spawned from: `HSX-ST-003`, review `HSX-RVW-001-001-004`
- Coordinator: `HSX-ST-001`
- Debugger dependency: `DBG-ST-006`
- Issue: #47; cross-track gate: #38
- Iteration: `DBG-IT-001-003`
- Evidence baseline: `bc8f2aac128b173adb763370f0d67b82438aa480`
- Scope authority: Study/design documentation and conformance-fixture planning only
- Product/AVR authority: **NONE**

## 1. Question and bounded scope

What portable, non-recursive identity and digest contract lets the same debug bundle be reused
for multiple loaded instances while proving that symbols, source identities, architecture and
ABI metadata belong to the exact load being inspected? What source identity remains stable
when build and checkout paths move, and how must case collisions, duplicate basenames and
local-resolution ambiguity behave?

This Study resolves the debug-bundle/source questions routed by `HSX-RVW-001-001-004`. It
defines the relationships and canonicalization boundaries for:

- immutable executable `ArtifactRef`;
- target-bound `LoadedImageRef`;
- reusable `ImageDebugBundleRef`;
- target-specific `ImageDebugBinding`;
- artifact-relative source identity and content evidence;
- canonical serialization/digest scopes, mismatch/stale outcomes, profiles and fixtures.

It does not allocate new numeric HSX IDs, redesign HXE/HXO, select an AVR representation,
define local debugger path-search UX, freeze `DBG-D-*`, or authorize product/AVR work.
`HSX-ST-007` owns the ABI/profile/recipe/register questions from the same review.

## 2. Authority and evidence classification

The durable authorities read before analysis were `AGENTS.md`, `SDP/README.md`,
`SDP/Shared/Process.md`, both track READMEs and `Traceability/CurrentIndex.yaml` files,
issues #47/#38, `HSX-RVW-001-001-004`, `HSX-ST-002/003`, the proposed HSX
Requirements/Architecture/Design package, `DBG-ST-006`, the proposed Debugger contracts and
both active Handoffs.

Evidence is classified as follows:

| Class | Meaning in this Study |
|---|---|
| Current Python oracle | Observable HXE/linker/source-map/symbol-consumer behavior; useful for compatibility and tests, not portable authority. |
| Legacy/documented intent | Existing format and workflow documents; provenance that may contain gaps or contradictions. |
| Proposed portable target | Recommended input for Master synthesis into the already allocated HSX R/A/D IDs. |
| Debugger-owned | Local path search, user overrides, display names and frontend presentation after HSX identity has been preserved. |
| AVR-owned | Target storage, transport, digest acceleration and constrained caching choices; not decided here. |

### 2.1 Evidence inspected

- formats/workflow: `docs/hxe_format.md`, `docs/symbol_format.md`,
  `docs/sources_json.md`, and `docs/portable_debug_workflow.md`;
- producers: `python/hld.py`, `python/hsx-llc.py`, and `python/hsx-cc-build.py`;
- runtime/consumers: `python/execd.py`, `python/source_map.py`, and
  `python/hsx_dbg/symbols.py`;
- focused tests: linker symbol output, deterministic build metadata, HXE v2 metadata,
  source-map relocation, symbol lookup and current debugger symbol loading;
- cross-track contracts: `HSX-R-004`, `HSX-R-015`, `HSX-A-001/002`,
  `HSX-D-001/002`, and `DBG-D-003/004/006`.

The focused current-oracle run was read-only:

```text
c:/Users/hanse/miniconda3/python.exe -m pytest \
  python/tests/test_linker.py \
  python/tests/test_source_map.py \
  python/tests/test_hsx_dbg_symbols.py \
  python/tests/test_build_determinism.py \
  python/tests/test_hxe_v2_metadata.py -q

18 passed, 1 skipped in 0.24s
```

This proves the current linker/source-map/symbol/HXE fixtures pass. It does not prove the
proposed canonical digest, non-recursive binding, collision handling or source-content
verification; those are the new fixtures required by section 10.

## 3. Current evidence and gaps

### 3.1 HXE and `.sym` provide integrity hints, not a closed identity chain

- HXE has a versioned container and CRC32. The CRC covers selected header/section bytes and is
  valuable corruption/compatibility evidence, but is not collision-resistant identity.
- `hld.py` emits `.sym` schema version 1 with `hxe_path` and `hxe_crc`. It does not include a
  collision-resistant HXE digest, a debug-bundle digest, an architecture/ABI reference, a
  sources-manifest digest, or a target/load reference.
- `hxe_path` is build-location data. Changing the output directory can change `.sym` bytes
  without changing executable or semantic debug data.
- `execd.py` discovers `<program>.sym` by adjacency or accepts an override, parses it, and
  attaches the resulting table to a numeric PID. It does not validate `hxe_crc`, schema-to-HXE
  compatibility, artifact digest, target/image generation or sources metadata.
- A `.sym` file beside an HXE can therefore be consumed merely because of its path. The
  existing behavior is a compatibility oracle only and cannot claim exact binding.

### 3.2 Current `sources.json` combines identity candidates with local locator hints

`sources.json` version 1 records `project_root`, build-time absolute `path`, relative `file`,
`relative`, `prefix_map`, build time and include paths. The generator de-duplicates resolved
host paths and sorts them, but records no source-content digest or durable source ID.

`SourceMap` indexes path spellings and searches the recorded root, optional roots and current
working directory. It returns the first existing candidate. That is useful relocation
behavior, but it has no checksum validation, ambiguity result or identity boundary.

The symbol consumer is still weaker:

- it lowercases every source lookup key;
- it adds basename aliases;
- it masks PCs to 16 bits;
- same-basename and case-colliding sources can share a lookup key and return combined hits;
- `.sym` instruction records carry `file`/`directory` strings rather than a stable source
  reference.

Consequently, current path equality cannot be promoted to HSX source identity. Absolute
paths, search roots, prefix maps, symlink targets, current working directory, path casing as
interpreted by the host filesystem and basename aliases are locator policy only.

### 3.3 Review 004 exposed a real recursion

The proposed `HSX-D-001` says `LoadedImageRef` includes an accepted debug-bundle digest while
`HSX-D-002` says `ImageDebugBundle` binds the exact `LoadedImageRef`. Constructing either value
would require the other value first. It also prevents one valid bundle from being reused for
two loads of identical artifact bytes.

The recursion must be removed from the type graph, not hidden by hashing a field as zero or by
excluding an undocumented back-reference.

## 4. Alternatives and decisions

| Alternative | Benefit | Failure/risk | Decision |
|---|---|---|---|
| Keep `.sym` adjacency + HXE CRC as binding | No new contract surface. | Collision-prone, path-dependent, PID-only, no source/content/descriptor proof. | Reject as exact identity; retain only in named legacy profile. |
| Put bundle digest in `LoadedImageRef` and LoadedImageRef in bundle | Direct-looking two-way link. | Recursive construction; prevents reusable bundle; unclear digest exclusions. | Reject. |
| Make a bundle target-specific | Easy exact-load lookup. | Duplicates identical metadata for every load and conflates artifact truth with runtime lifecycle. | Reject. |
| Reusable artifact-bound bundle plus separate target binding | Acyclic, cacheable, exact-load safe and independently verifiable. | Requires one additional typed record and explicit validation outcomes. | **Recommend.** |
| Source identity is absolute path or basename | Matches current lookup shortcuts. | Breaks on relocation; aliases duplicates/case collisions; host-specific. | Reject. |
| Case-folded artifact-relative path only | Stable over relocation on many hosts. | Merges distinct case-sensitive sources and still cannot detect changed bytes. | Reject. |
| Case-preserving logical ID plus exact content digest | Relocatable, collision-resistant, supports case-distinct and same-basename sources. | Requires build-time hashing and typed resolver outcomes. | **Recommend.** |
| Hash raw `.sym` and `sources.json` bytes as the only bundle identity | Simple byte verification. | Current files contain build/local path fields; semantically identical relocated builds differ and source identity remains absent. | Reject as target model; raw digests may remain provenance evidence. |

## 5. Canonical digest and serialization rules

### 5.1 Common structured encoding

Every proposed structured identity payload uses one documented schema version and the
following deterministic JSON encoding before hashing:

1. Input must be a parsed schema object; duplicate keys, unknown mandatory fields, invalid
   Unicode and values outside their declared type/range are rejected before canonicalization.
2. Text is Unicode NFC. Object keys are NFC-normalized and sorted by Unicode scalar value.
   Two raw keys or logical IDs that normalize to the same NFC value are duplicates and fail.
3. Strings preserve case. `/` is the only separator in logical IDs. Opaque IDs, UInt64
   generations/revisions and other wire-sensitive integers use their already required
   canonical lowercase-hex or unsigned-decimal **string** representation. Schema/version and
   other bounded integers may use minimal base-10 JSON integers.
4. No insignificant whitespace or BOM is emitted. Strings use JSON escaping only where
   required; non-ASCII text is encoded as UTF-8, not host-locale bytes. Floating point,
   `NaN`, infinities and implementation-specific numeric formatting are forbidden in an
   identity payload. Optional absent values are omitted, not serialized as interchangeable
   `null`/empty values.
5. Arrays preserve schema-defined order. Set-like arrays declare a canonical sort key; source
   records sort by UTF-8 bytes of `logical_id`. Producers may not silently de-duplicate
   records after hashing.
6. A structured digest is
   `SHA-256(UTF8(domain-tag) || 0x00 || canonical-json-bytes)`. Domain tags are type/schema
   specific, so equal JSON from different domains cannot alias.
7. The field that carries a record's own digest, signatures over that digest, local locator
   hints and audit timestamps are excluded by the schema, never by ad-hoc implementation
   choice. A supplied digest is compared after recomputation; it is not replaced silently.

SHA-256 digests use exactly 64 lowercase hexadecimal characters on JSON/wire surfaces.
Algorithm name, domain tag and schema version are part of the reference. Future algorithms or
encodings require a negotiated schema/profile; clients must not guess.

### 5.2 Exact byte-content digests

Raw artifact/source/component bytes use `SHA-256(exact-byte-sequence)` without newline,
Unicode, path, archive, compression or host-text normalization. The associated typed
reference supplies domain and media/schema context. This preserves the `HSX-ST-002`
recommendation for exact accepted HXE bytes.

- HXE digest scope is every exact byte accepted by the loader, including its stored CRC and
  metadata. It is computed before target-specific load state is added.
- Source digest scope is the exact source bytes used to produce/declare the debug mapping.
  A line-ending or encoding change is a content-identity change even when text appears alike.
- A canonical debug component may itself be a structured artifact. Its digest covers its
  canonical semantic serialization, not current `.sym` build paths.
- Raw input `.sym`/`sources.json` byte digests may be retained as provenance, but they do not
  replace the canonical component/source-manifest digests below.

## 6. Non-recursive reference and binding model

### 6.1 Construction order

The portable graph is deliberately one-way:

```text
exact accepted HXE bytes
        |
        v
   ArtifactRef <-------------------------------+
        |                                      |
        +--> LoadedImageRef (target/load)       |
        |                                      |
        +--> ImageDebugBundleRef (reusable)     |
                       |                        |
                       +----> SourceIdentityManifestRef
                                                |
LoadedImageRef + ImageDebugBundleRef + accepted descriptor refs
        |
        v
 ImageDebugBinding (target-specific immutable receipt)
```

`LoadedImageRef` never contains a bundle reference/digest. The reusable bundle never contains
`LoadedImageRef`, target, session, PID, stop/snapshot or resource identity. Only the final
binding contains both exact references.

### 6.2 `ArtifactRef`

```text
ArtifactRef {
  ref_schema: "hsx.artifact-ref/1"
  media_type: "application/vnd.hsx.hxe"
  container_version: bounded canonical value
  byte_length: UInt64 decimal string
  content_digest: { algorithm: "sha256", value: lowercase Hex64 }
}
```

Equality is exact field equality after validation. `content_digest` is SHA-256 of the exact
accepted HXE bytes. HXE internal CRC, app/display name, requested load name, build UUID,
filesystem path, URI and timestamps are diagnostic/provenance only and excluded from the
reference. A parser must verify container version independently; a matching digest does not
authorize an unsupported schema.

### 6.3 `LoadedImageRef`

```text
LoadedImageRef {
  ref_schema: "hsx.loaded-image-ref/1"
  executive_instance_ref
  target_ref
  loaded_image_id: opaque never-reused ID
  image_generation: UInt64 decimal string
  artifact_ref: ArtifactRef
}
```

This is lifecycle identity, not a content hash. A distinct accepted load gets a distinct
`LoadedImageId` even if TargetRef, ArtifactRef or display PID/name is equal to an earlier
load. Loads of identical bytes on different targets share `ArtifactRef` but not
`LoadedImageRef`. The Executive/Target references and generations follow `HSX-ST-002`.

### 6.4 Reusable `ImageDebugBundleRef`

The bundle identity payload is artifact-bound but target-independent:

```text
ImageDebugBundleIdentityPayload {
  bundle_schema
  artifact_ref
  architecture_descriptor_ref + digest
  abi_descriptor_ref + digest
  symbol_model_schema + canonical_component_digest
  unwind_recipe_schema + canonical_component_digest
  location_recipe_schema + canonical_component_digest
  source_identity_manifest_ref
  required_debug_capabilities[]        # canonical sorted set
  interpretation_schema_versions{}     # canonical key order
}

ImageDebugBundleRef {
  ref_schema: "hsx.image-debug-bundle-ref/1"
  artifact_ref
  digest_algorithm: "sha256"
  bundle_digest: structured digest of ImageDebugBundleIdentityPayload
}
```

The bundle digest excludes its own digest/reference, signatures, raw input paths,
`hxe_path`, `project_root`, `prefix_map`, search roots, local source overrides, current
working directory, target/session/PID/load/epoch identities, acceptance status and audit
time. Descriptive producer/build-host/version-control provenance is also outside identity
unless a future interpretation schema declares a field semantically mandatory.

The canonical symbol model replaces `.sym` `file`/`directory` locator pairs with exact
source logical IDs from the source identity manifest. It preserves typed code/data locations
and schema-governed symbol/line/location content. A legacy `.sym` importer may create this
model only after validating its schema, resolving every referenced source spelling without
ambiguity and projecting away `hxe_path`/`hxe_crc`; it records the raw sidecar digest and CRC
as provenance. Unknown mandatory semantics, duplicate source mapping or an unresolved source
reference makes the relevant component unsupported or invalid, not heuristically repaired.

The same `ImageDebugBundleRef` may bind every target load whose exact `ArtifactRef` and
descriptor/profile inputs match. It changes if any identity payload component/schema/digest
changes. Packaging, copying or relocating unchanged component bytes does not change it.

### 6.5 Target-specific `ImageDebugBinding`

```text
ImageDebugBindingPayload {
  binding_schema: "hsx.image-debug-binding/1"
  loaded_image_ref
  image_debug_bundle_ref
  accepted_architecture_descriptor_ref
  accepted_abi_descriptor_ref
  accepted_image_debug_capability_profile
}

ImageDebugBinding {
  payload
  binding_digest: structured digest of ImageDebugBindingPayload
}
```

A trusted Executive/coordinator emits an immutable binding only after verifying:

1. bundle and loaded-image `ArtifactRef` values are exactly equal and the accepted HXE bytes
   recompute that ArtifactRef;
2. bundle and target architecture/ABI references/digests are supported and exactly agree;
3. every mandatory component and source-identity manifest recomputes its claimed digest;
4. the loaded image's accepted debug-capability profile permits every mandatory
   schema/recipe.

The binding digest excludes itself, signatures and timestamps. Revalidating identical inputs
produces the same binding digest. A failed validation returns a typed result and **no**
binding. Local file resolution is never part of the binding; it can change without changing
runtime/artifact truth.

## 7. Stable source identity

### 7.1 Source identity manifest

The bundle contains or references a canonical `SourceIdentityManifest` distinct from locator
hints:

```text
SourceIdentityRecord {
  logical_id: artifact-relative logical path
  content_digest: { algorithm: "sha256", value: lowercase Hex64 }
  byte_length: UInt64 decimal string
  media_type_or_language: optional schema value
}

SourceIdentityManifest {
  schema
  records[] sorted by UTF-8(logical_id)
}
```

The manifest ref is a domain-separated structured digest over the canonical manifest. A
portable external `SourceRef` is constructed only after the bundle exists:

```text
SourceRef {
  image_debug_bundle_ref
  logical_id
  content_digest
  byte_length
}
```

The bundle-internal record does not contain the bundle ref, so there is no source/bundle
recursion. Line tables and symbol records refer to `logical_id`; consumers form and verify
the full `SourceRef` using the accepted bundle.

### 7.2 Logical-ID rules

- A logical ID is relative to one declared artifact source root. It is not a host path.
- It uses `/`, contains no empty, `.` or `..` segments, drive letter, UNC prefix, URI scheme,
  leading/trailing slash, NUL or backslash, and is Unicode NFC.
- Case is preserved and equality is exact code-point equality after NFC normalization.
  Locale-sensitive lowercase/case-fold operations are forbidden for identity.
- Two exact/NFC-equal logical IDs in one manifest are invalid duplicates.
- Casefold-colliding IDs such as `src/Foo.c` and `src/foo.c` are valid **distinct** records.
  Their collision is discoverable metadata for resolvers; it is never collapsed.
- Duplicate basenames such as `a/main.c` and `b/main.c` are valid and distinct. Basename is
  display/search text only, never an alias or identity key.
- Identical bytes at two logical IDs share a content digest but remain distinct SourceRefs.
  Changed bytes at one logical ID produce a different SourceRef and bundle digest.

Generated and out-of-tree sources need an explicit artifact-relative namespace assigned by
the producer (for example a schema-governed generated/external root); embedding an absolute
build path as logical ID is forbidden in the full profile.

### 7.3 Locator/relocation separation

The current `sources.json` fields can seed an optional `SourceLocatorManifest`, but that
manifest is not HSX identity and is excluded from the bundle and source digests. It may carry
build paths, prefix maps, checkout roots, search roots, source-server URIs, archive members,
symlink hints and user overrides.

A Debugger-owned resolver consumes an exact `SourceRef` and applies locator tiers. At each
highest applicable tier it must:

1. keep mappings keyed by exact logical ID, never an unconditional lowercase or basename key;
2. collect candidates rather than return the first filesystem hit;
3. read candidate bytes and require exact content digest/length before the candidate can
   satisfy the SourceRef;
4. return one of `source_resolved_exact`, `source_unavailable`, `source_ambiguous`,
   `source_content_mismatch`, `source_case_collision`, or `source_locator_invalid` with
   candidate diagnostics.

Multiple distinct paths in the same winning tier are ambiguous unless an explicit per-
SourceRef override chooses one. A symlink is acceptable only as a local locator whose final
bytes match; its target path is not identity. On a case-insensitive filesystem, automatic
resolution of a case-collision set is disabled unless each SourceRef can be mapped and
verified separately. One physical file is not silently reused for two case-distinct IDs.

Source breakpoint placement, source stepping and source annotation require
`source_resolved_exact`. A frontend may show mismatched local text as explicitly untrusted
display material, but it must not use it to claim line/address binding.

## 8. Validation, mismatch and staleness outcomes

| Code/category | Detection | Required outcome |
|---|---|---|
| `artifact_digest_mismatch` | Accepted HXE bytes do not recompute ArtifactRef. | Reject ArtifactRef/load binding; CRC/path/name cannot override. |
| `artifact_ref_mismatch` | Bundle ArtifactRef differs from LoadedImageRef ArtifactRef. | No ImageDebugBinding; do not search for a same-name/PID image. |
| `bundle_digest_mismatch` | Canonical payload does not recompute bundle digest. | Reject bundle as corrupt/mismatched. |
| `component_digest_mismatch` | Symbol/unwind/location/source manifest component differs. | Reject affected mandatory component/binding; optional capability becomes explicitly unavailable only if profile permits. |
| `schema_unsupported` | Mandatory container/component/canonicalization schema is unknown. | Typed unsupported; no version guessing or partial parse presented as conformance. |
| `architecture_mismatch` / `abi_mismatch` | Target accepted descriptor ref differs from bundle. | No binding; no masks/legacy R7 heuristic in full profile. |
| `bundle_incomplete` | Full profile lacks a mandatory referenced component. | No full-profile binding; negotiate an explicitly weaker profile or report unavailable. |
| `binding_stale` | Executive/Target/LoadedImage ID or generation no longer names the active exact load. | Invalidate binding and all derived epochs/handles/resources; same ArtifactRef does not revive it. |
| `source_unknown` | Line/symbol record names no manifest logical ID. | Component invalid/unsupported; never fall back to basename. |
| `source_unavailable` | No local candidate exists. | Keep SourceRef valid; source presentation/step unavailable. |
| `source_ambiguous` | Multiple candidates/logical-ID aliases remain at winning locator tier. | Require explicit mapping; do not choose first. |
| `source_content_mismatch` | Local bytes/length differ from SourceRef. | Reject local file for authoritative mapping. |
| `source_case_collision` | Host locator cannot distinguish a valid case-collision set. | Per-ID explicit/content-addressed mapping or typed unavailable; never collapse. |
| `legacy_unverified` | Only PID/path/HXE CRC/adjacency evidence exists. | No exact bundle/load/source-continuity claim; conservative Debugger behavior. |

`mismatch` means supplied evidence contradicts an identity claim. `unavailable` means identity
may remain valid but a non-mandatory component/local copy is absent. `stale` means a formerly
valid target-specific binding no longer matches current lifecycle generations. Consumers
must not turn one category into another to enable fallback.

## 9. Capability and degraded profiles

### Full portable profile

`hsx.portable-debug-runtime/1` consumes the existing capabilities as follows:

- `hsx.runtime.identity-generations/1` supplies exact Executive/Target/LoadedImage refs and
  the non-recursive ArtifactRef relation;
- `hsx.architecture.descriptor/1` supplies accepted architecture/ABI descriptor refs;
- `hsx.debug.image-bundle/1` supplies the canonical reusable bundle, source identity manifest,
  target-specific binding and typed validation outcomes.

Full-profile source/unwind/location claims require a valid `ImageDebugBinding` and validated
mandatory component digests. Instruction-only inspection may advertise a deliberately
smaller negotiated capability set, but it must report source/unwind/location as unavailable
rather than fabricate them.

### Current named degraded behavior

`hsx.python-debug-legacy/1` may use HXE CRC, adjacent/overridden `.sym`, PID and current path
mapping as compatibility evidence. It must label bundle/load/source identity
`legacy_unverified`, forbid reconnect continuity/resource rebinding claims based on those
fields, preserve ambiguous resources/sources, and require explicit warnings. A CRC match or
same basename never upgrades the profile.

The degraded profile exits only when producer, loader/Executive and debugger fixtures prove
ArtifactRef, LoadedImageRef, canonical bundle/binding, source content identity and typed
failure behavior end to end. No additional capability name is introduced by this Study.

## 10. Required conformance fixtures

### 10.1 Canonical serialization and identity

1. Hash a fixed HXE byte vector and verify identical ArtifactRef results across at least
   Python and a language/runtime used by a debugger consumer; change one byte and require a
   different digest.
2. Serialize structured payloads with permuted object-key order/whitespace and require one
   canonical digest; reject duplicate keys, non-NFC duplicates, malformed UInt64/digest text,
   floats and unknown mandatory fields.
3. Change every identity field/component digest independently and require the relevant
   structured digest to change. Add/change excluded local path, timestamp and signature
   fields and require identity to remain unchanged.
4. Prove construction order: ArtifactRef first; independent LoadedImageRef and bundle refs;
   binding last. No input graph contains a self field or back-reference.

### 10.2 Reuse, load fencing and mismatch

5. Load identical HXE bytes twice on different targets: ArtifactRef and bundle ref equal;
   LoadedImageIds/refs and ImageDebugBindings distinct.
6. Reload identical bytes into a deliberately preserved TargetId: new LoadedImageId and image
   generation make the old binding stale even though ArtifactRef/bundle ref remain equal.
7. Bind bundle A to loaded artifact B, alter architecture/ABI descriptor refs, corrupt each
   mandatory component, omit a mandatory component and present an unsupported schema; verify
   the exact typed outcomes and absence of a binding.
8. Present a `.sym` with matching HXE CRC but wrong HXE SHA-256 and prove full-profile binding
   rejects it. Present CRC collision/equal path/app name/PID fixtures and prove none are
   identity comparators.
9. Change legacy `.sym.hxe_path`, `sources.json.project_root`, prefix map and checkout location
   while leaving canonical semantic components/logical IDs/source bytes unchanged; canonical
   bundle/source refs remain equal while raw provenance digests may differ.

### 10.3 Sources and local resolution

10. Manifest contains `src/Foo.c` and `src/foo.c` with different bytes. Preserve two
    SourceRefs; verify exact mappings on a case-sensitive host and typed collision handling on
    a case-insensitive host.
11. Manifest contains `a/main.c` and `b/main.c`; a basename-only query returns ambiguity and
    never line hits for both. Exact logical IDs resolve independently.
12. Reject exact/NFC duplicate logical IDs and illegal absolute, drive, UNC, empty, `.`/`..`,
    backslash and NUL path forms; allow identical content under two valid different IDs.
13. Resolve a relocated file and symlink only when exact bytes/length match. Changed line
    endings, encoding or content produce `source_content_mismatch`, not a successful path hit.
14. Make a line/symbol record reference an absent logical ID and require component rejection;
    make the source locally absent and require valid identity plus `source_unavailable`.
15. Supply multiple exact-content candidates in one locator tier and require ambiguity until
    an explicit per-SourceRef override selects one; prove locator changes do not mutate bundle
    or binding identity.

## 11. Exact synthesis changes required

No new numeric contract ID is needed. Master should make these precise changes to the
existing proposed package.

| Existing contract | Required synthesis change |
|---|---|
| `HSX-R-004` | Keep target-bound opaque LoadedImageId/generation and exact ArtifactRef. Explicitly state LoadedImageRef contains no bundle digest/ref and equal artifacts/bundles never imply equal loads. Define ArtifactRef as exact accepted HXE-byte SHA-256 plus schema/media/length context. |
| `HSX-R-015` | Replace direct “bundle bound inside LoadedImageRef” wording with reusable artifact-bound ImageDebugBundleRef plus exact-load ImageDebugBinding. Require canonical component/source identities, typed mismatch/stale/unavailable outcomes, exact-case logical source IDs and local-content verification. |
| `HSX-A-001` | Own ArtifactRef and lifecycle LoadedImageRef only; explicitly exclude bundle/source construction and local paths. Supply exact refs/generations to A-002. |
| `HSX-A-002` | Own canonical debug components, reusable bundle/source identity and binding validation against A-001 refs/descriptors; explicitly exclude target lifecycle identity and Debugger local resolver policy. |
| `HSX-D-001` | Remove “accepted debug-bundle digest” from LoadedImageRef. Add ArtifactRef exact-byte scope and the invariant that bundle acceptance cannot mutate a LoadedImageRef. |
| `HSX-D-002` | Replace “bundle binds exact LoadedImageRef” with the four-layer model and canonical rules in sections 5–8. Add SourceIdentityManifest/SourceRef, target-specific immutable binding, and full/degraded outcomes. |
| `DBG-D-003` | Every epoch/snapshot carries exact LoadedImageRef and accepted ImageDebugBinding where artifact interpretation is required; replacement invalidates them even for equal bytes. |
| `DBG-D-004` | `DebugArtifactIndex` consumes only a verified binding/bundle. `SourceResolver` keys exact SourceRef/logical ID, validates content, separates locators and returns typed ambiguity/case/mismatch outcomes; no lowercase/basename identity. |
| `DBG-D-006` | Source into/over/out require valid binding plus exact source mapping and required recipe components. Missing/mismatched sources are unavailable/error, never silently relabeled instruction stepping. |

`DBG-D-005` and resource contracts consume the corrected LoadedImageRef/binding transitively,
but this Study does not change their ownership model.

## 12. Traceability relations and conclusion

- `HSX-ST-002` supplies ArtifactRef/LoadedImageRef lifecycle identity and consumes this
  Study's non-recursive correction.
- `HSX-ST-003` supplies architecture/ABI/debug-artifact intent and routed the unresolved
  bundle/source questions here.
- `HSX-ST-007` supplies the concrete descriptor/recipe/profile details referenced by the
  bundle; it does not own bundle/source identity.
- `HSX-ST-008` informs `HSX-R-004`, `HSX-R-015`, `HSX-A-001/002`, `HSX-D-001/002`,
  `DBG-ST-006`, and proposed `DBG-D-003/004/006`.
- `HSX-RVW-001-001-005` must independently review the synthesized exact head.

The recommended model is acyclic and deterministic: executable bytes create ArtifactRef;
runtime lifecycle creates a target-bound LoadedImageRef; artifact/debug/source semantics
create a reusable ImageDebugBundleRef; validation of those two refs creates an immutable
target-specific ImageDebugBinding. Artifact-relative, case-preserving logical IDs plus exact
source-byte digests provide stable source identity, while paths, prefix maps, search roots,
symlinks and overrides remain replaceable local locator policy.

Status is **COMPLETE FOR MASTER SYNTHESIS**. This Study grants no HSX/Debugger design freeze,
product Refactor, AVR implementation or other implementation authority.
