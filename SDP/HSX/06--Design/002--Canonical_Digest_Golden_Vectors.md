# HSX-D-002 Appendix — Canonical Structured-Digest Golden Vectors

- Status: ACCEPTED / FROZEN `HSX-D-002` TARGET APPENDIX
- Parent contract: `HSX-D-002`
- Evidence: `HSX-ST-008`, `HSX-RVW-001-001-005`
- State: target; not implemented or frozen
- Product/AVR authority: **NONE**

This appendix makes the structured identity bytes in `HSX-D-002` interoperable. It allocates
no new `HSX-D-*` ID. A conforming producer/consumer must reproduce every canonical byte string
and SHA-256 below before advertising `hsx.debug.image-bundle/1`.

## Normative serializer

Validation happens before serialization. Unknown mandatory fields, duplicate raw or
NFC-normalized object keys/logical IDs, invalid Unicode, values outside schema range and
non-canonical reference fields fail without producing bytes.

1. Normalize every string and object key to Unicode NFC. Identity strings containing
   U+0000..U+001F or U+007F are invalid.
2. Sort object keys by Unicode scalar-value sequence. Emit `{`, each canonical key/value with
   `:` and comma separators, then `}`. Emit no spaces, BOM or trailing newline.
3. Preserve schema-defined array order. Sort source-manifest records by UTF-8 logical ID and
   set-like string arrays by UTF-8 bytes. Do not de-duplicate after validation.
4. Emit strings between ASCII quotes. Encode U+0022 as `\"`, U+005C as `\\`, do not escape
   `/`, and emit every other Unicode scalar directly in UTF-8. Canonical output never contains
   a `\u` escape.
5. Encode every signed/unsigned integer-valued identity field as a JSON **string** in minimal
   base-10 form. Unsigned is `0` or `[1-9][0-9]*`; signed additionally permits
   `-[1-9][0-9]*`. JSON numeric tokens, `+`, leading zeroes and hexadecimal integer forms are
   invalid. This applies to versions, widths, offsets, lengths, generations, revisions and
   sequences. Digest values alone use exactly 64 lowercase hexadecimal characters. Opaque IDs
   remain exact schema-governed NFC strings and are never numerically reformatted.
6. Emit schema-declared booleans only as `true`/`false`. `null`, floating point, NaN and
   infinity are forbidden in identity payloads. Omit absent optional fields.
7. Hash `UTF8(literal_domain_tag)`, one `0x00` byte, then the canonical JSON bytes. The result
   is lowercase SHA-256 hex. A record's own digest, signatures, timestamps, audit data and
   local locator/provenance fields are excluded by its schema before serialization.

## Literal domain-tag registry

| Structured payload | Literal ASCII/UTF-8 domain tag |
|---|---|
| Source identity manifest | `hsx.source-identity-manifest/1` |
| Canonical symbol component | `hsx.debug-component.symbol-model/1` |
| Canonical unwind component | `hsx.debug-component.unwind-recipe/1` |
| Canonical location component | `hsx.debug-component.location-recipe/1` |
| Image debug bundle identity payload | `hsx.image-debug-bundle/1` |
| Image debug binding payload | `hsx.image-debug-binding/1` |

Tags are literal bytes, not derived from a filename, media type, schema field or class name.
Future incompatible schemas allocate new literal tags.

## Golden vector 1 — source manifest

Domain tag: `hsx.source-identity-manifest/1`

Canonical UTF-8 bytes, shown as text without a trailing newline:

```json
{"records":[],"schema":"hsx.source-identity-manifest/1"}
```

SHA-256:

```text
6caa23594d6f57fb795a2e73648f5c8ed9928a5e25798d3bb48545412ca164a0
```

## Golden vector 2 — canonical symbol component

Domain tag: `hsx.debug-component.symbol-model/1`

```json
{"component_schema":"hsx.debug-component.symbol-model/1","records":[]}
```

SHA-256:

```text
767ad5f9e1ae49abdc33dfd990e81fc3a5a6b064e23d2e44992dfe20f0d94a73
```

The unwind/location component domains use the same serializer and their own literal tags;
component schema fixtures must independently prove both tags and full record validation.

## Golden vector 3 — image debug bundle identity payload

The all-zero values are fixture data, not accepted artifact/component evidence. The source and
symbol digests are the outputs of vectors 1 and 2.

Domain tag: `hsx.image-debug-bundle/1`

```json
{"abi_descriptor":{"digest":"0000000000000000000000000000000000000000000000000000000000000000","ref":"abi-01"},"architecture_descriptor":{"digest":"0000000000000000000000000000000000000000000000000000000000000000","ref":"arch-01"},"artifact_ref":{"byte_length":"0","container_version":"1","content_digest":{"algorithm":"sha256","value":"0000000000000000000000000000000000000000000000000000000000000000"},"media_type":"application/vnd.hsx.hxe","ref_schema":"hsx.artifact-ref/1"},"bundle_schema":"hsx.image-debug-bundle/1","interpretation_schema_versions":{},"location_recipe":{"canonical_component_digest":"0000000000000000000000000000000000000000000000000000000000000000","schema":"hsx.location-recipe/1"},"required_debug_capabilities":[],"source_identity_manifest_ref":{"algorithm":"sha256","value":"6caa23594d6f57fb795a2e73648f5c8ed9928a5e25798d3bb48545412ca164a0"},"symbol_model":{"canonical_component_digest":"767ad5f9e1ae49abdc33dfd990e81fc3a5a6b064e23d2e44992dfe20f0d94a73","schema":"hsx.debug-component.symbol-model/1"},"unwind_recipe":{"canonical_component_digest":"0000000000000000000000000000000000000000000000000000000000000000","schema":"hsx.unwind-recipe/1"}}
```

SHA-256:

```text
61bc53ef9bf46d87dd6f434ddb43e9307921751faa37471323ea734f87105007
```

## Golden vector 4 — target-specific image debug binding payload

Domain tag: `hsx.image-debug-binding/1`

```json
{"accepted_abi_descriptor_ref":"abi-01","accepted_architecture_descriptor_ref":"arch-01","accepted_image_debug_capability_profile":"hsx.portable-debug-runtime/1","binding_schema":"hsx.image-debug-binding/1","image_debug_bundle_ref":{"artifact_ref":{"byte_length":"0","container_version":"1","content_digest":{"algorithm":"sha256","value":"0000000000000000000000000000000000000000000000000000000000000000"},"media_type":"application/vnd.hsx.hxe","ref_schema":"hsx.artifact-ref/1"},"bundle_digest":"61bc53ef9bf46d87dd6f434ddb43e9307921751faa37471323ea734f87105007","digest_algorithm":"sha256","ref_schema":"hsx.image-debug-bundle-ref/1"},"loaded_image_ref":{"artifact_ref":{"byte_length":"0","container_version":"1","content_digest":{"algorithm":"sha256","value":"0000000000000000000000000000000000000000000000000000000000000000"},"media_type":"application/vnd.hsx.hxe","ref_schema":"hsx.artifact-ref/1"},"executive_instance_ref":"exec-01","image_generation":"1","loaded_image_id":"image-01","ref_schema":"hsx.loaded-image-ref/1","target_ref":"target-01"}}
```

SHA-256:

```text
b84f9e6618dea2f8c688bc4930a9915c80c1eea1be22b4233375616d272472f2
```

## Negative and cross-runtime fixtures

- Permuted input key order and arbitrary input whitespace reproduce the exact bytes above.
- JSON numeric `1`, strings `"01"`, `"+1"`, `"0x1"`, uppercase digest hex, control-valued
  strings, duplicate/NFC-colliding keys, floats and `null` are rejected. A non-control input
  `\u` escape is parsed to its scalar and re-emitted directly; canonical output never uses
  `\/` or `\u`.
- Changing a domain tag changes the digest even when canonical JSON bytes are identical.
- Python and the Debugger-consumer runtime must reproduce all four hashes byte-for-byte.
- Full schema fixtures separately reject the zero fixture digests as untrusted content where
  actual component/artifact validation is required; serializer conformance does not create an
  accepted `ImageDebugBinding`.

This appendix remains target/proposed. It authorizes no serializer implementation, product
change, AVR representation or Debugger design freeze.
