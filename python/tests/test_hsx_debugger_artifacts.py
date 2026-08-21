from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from hsx_debugger import *


ZERO = "0" * 64
FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "rf004"


def _address(space: str, value: int) -> dict[str, str]:
    return {"space_id": space, "unsigned_value": str(value)}


def _range(space: str, start: int, length: int) -> dict[str, object]:
    return {"start": _address(space, start), "length_units": str(length)}


def _expression(role: str, special: str) -> dict[str, object]:
    return {
        "role": role,
        "opcodes": [{"opcode": "special_value", "special": special}],
        "required_result": "address",
    }


def _rule(role: str, special: str) -> dict[str, object]:
    return {"kind": "expression", "expression": _expression(role, special)}


def _terminal_location(reason: str = "not materialized") -> dict[str, str]:
    return {"kind": "unavailable", "reason": reason}


def _architecture(*, code_width: int = 24) -> ArchitectureDescriptor:
    code = AddressSpaceId("code")
    data = AddressSpaceId("data")
    code_length = 1 << code_width
    return ArchitectureDescriptor(
        ArchitectureDescriptorRef("hsx.arch.vm-byte24-gpr32/1", ZERO),
        CanonicalUInt64(1),
        "hsx.fixed32/1",
        ByteOrder.LITTLE,
        ByteOrder.LITTLE,
        32,
        ByteOrder.LITTLE,
        3,
        (
            AddressSpaceDescriptor(
                code,
                "byte",
                8,
                code_width,
                (HsxAddressRange(HsxAddress(code, 0), code_length),),
                ByteOrder.LITTLE,
                4,
                WrapPolicy.FORBIDDEN,
                frozenset({Permission.READ, Permission.EXECUTE}),
            ),
            AddressSpaceDescriptor(
                data,
                "byte",
                8,
                24,
                (HsxAddressRange(HsxAddress(data, 0), 1 << 24),),
                ByteOrder.LITTLE,
                1,
                WrapPolicy.FORBIDDEN,
                frozenset({Permission.READ, Permission.WRITE}),
            ),
        ),
        ("R0", "R1", "R7"),
        code,
        data,
        8,
        4,
    )


def _base_symbol_records() -> list[dict[str, object]]:
    return [
        {
            "record_kind": "type",
            "type_id": "i16",
            "name": "i16",
            "kind": "integer",
            "bit_size": "16",
            "byte_order": "little",
            "members": [],
        },
        {
            "record_kind": "function",
            "function_id": "fn",
            "name": "Main",
            "linkage_name": "_Main",
            "range": _range("code", 0x20, 0x40),
            "definition": {"logical_id": "src/Foo.c", "line": "10"},
        },
        {
            "record_kind": "lexical_scope",
            "lexical_scope_id": "scope",
            "function_id": "fn",
            "pc_range": _range("code", 0x20, 0x20),
            "declaration_order": "0",
        },
        {
            "record_kind": "symbol",
            "symbol_id": "sym-fn",
            "name": "dup",
            "kind": "function",
            "address": _address("code", 0x20),
            "byte_size": "64",
            "function_id": "fn",
            "declaration_order": "0",
        },
        {
            "record_kind": "symbol",
            "symbol_id": "sym-label",
            "name": "dup",
            "kind": "label",
            "address": _address("code", 0x24),
            "byte_size": "0",
            "function_id": "fn",
            "lexical_scope_id": "scope",
            "declaration_order": "1",
        },
        {
            "record_kind": "symbol",
            "symbol_id": "local",
            "name": "value",
            "kind": "local",
            "byte_size": "2",
            "function_id": "fn",
            "lexical_scope_id": "scope",
            "type_id": "i16",
            "declaration_order": "3",
        },
        {
            "record_kind": "symbol",
            "symbol_id": "global",
            "name": "value",
            "kind": "global",
            "byte_size": "2",
            "type_id": "i16",
            "declaration_order": "2",
        },
        {
            "record_kind": "symbol",
            "symbol_id": "constant",
            "name": "constant",
            "kind": "constant",
            "byte_size": "2",
            "type_id": "i16",
            "declaration_order": "4",
        },
        {
            "record_kind": "instruction",
            "instruction_id": "insn-b",
            "address": _address("code", 0x24),
            "byte_size": "4",
            "encoded_word": "2",
            "function_id": "fn",
            "source": {"logical_id": "src/Foo.c", "line": "12", "column": "9"},
            "classification": "user",
        },
        {
            "record_kind": "instruction",
            "instruction_id": "insn-a",
            "address": _address("code", 0x20),
            "byte_size": "4",
            "encoded_word": "1",
            "function_id": "fn",
            "source": {"logical_id": "src/Foo.c", "line": "12", "column": "5"},
            "classification": "user",
        },
        {
            "record_kind": "memory_region",
            "region_id": "data",
            "name": ".data",
            "kind": "data",
            "range": _range("data", 0x100, 0x20),
            "permissions": ["read", "write"],
        },
        {
            "record_kind": "memory_region",
            "region_id": "text",
            "name": ".text",
            "kind": "code",
            "range": _range("code", 0x20, 0x40),
            "permissions": ["read", "execute"],
        },
    ]


def _unwind_rows() -> list[dict[str, object]]:
    return [
        {
            "row_id": "uw",
            "pc_range": _range("code", 0x20, 0x40),
            "abi": {"ref": "hsx.abi.llc-r7-word32/1", "digest": ZERO},
            "schema": "hsx.unwind-recipe/1",
            "cfa_expression": _expression("cfa", "SP"),
            "caller_pc_rule": _rule("caller_pc", "PC"),
            "caller_sp_rule": _rule("caller_sp", "SP"),
            "register_rules": [["R7", {"kind": "same"}]],
            "boundary": "ordinary",
            "call_site_adjustment": "-4",
        }
    ]


def _location_rows() -> list[dict[str, object]]:
    common = {
        "declared_type_id": "i16",
        "declared_bit_size": "16",
        "abi": {"ref": "hsx.abi.llc-r7-word32/1", "digest": ZERO},
        "value_byte_order": "little",
        "frame_binding": "selected_frame",
        "schema": "hsx.location-recipe/1",
        "location_form": _terminal_location(),
    }
    return [
        {
            **common,
            "row_id": "loc-local",
            "symbol_id": "local",
            "function_id": "fn",
            "lexical_scope_id": "scope",
            "pc_range": _range("code", 0x20, 0x20),
        },
        {
            **common,
            "row_id": "loc-global",
            "symbol_id": "global",
            "pc_range": _range("code", 0x20, 0x40),
        },
        {
            **common,
            "row_id": "loc-constant",
            "symbol_id": "constant",
            "pc_range": _range("code", 0x20, 0x40),
        },
    ]


def _component(schema: str, domain: str, records: list[dict[str, object]]) -> tuple[DebugComponentInput, str]:
    payload = {"component_schema": schema, "records": records}
    digest = canonical_structured_digest(domain, payload)
    content = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
    return DebugComponentInput(schema, schema, digest, content), digest


def portable_fixture(
    *,
    symbol_records: list[dict[str, object]] | None = None,
    unwind_rows: list[dict[str, object]] | None = None,
    location_rows: list[dict[str, object]] | None = None,
    sources: tuple[SourceIdentityRecord, ...] | None = None,
) -> SimpleNamespace:
    architecture = _architecture()
    abi = AbiDescriptorRef("hsx.abi.llc-r7-word32/1", ZERO)
    source_records = sources if sources is not None else (
        SourceIdentityRecord(
            "src/Foo.c", ContentDigest("sha256", "a" * 64), CanonicalUInt64(12), "c"
        ),
        SourceIdentityRecord(
            "src/foo.c", ContentDigest("sha256", "b" * 64), CanonicalUInt64(13), "c"
        ),
        SourceIdentityRecord(
            "lib/Foo.c", ContentDigest("sha256", "c" * 64), CanonicalUInt64(14), "c"
        ),
    )
    manifest = SourceIdentityManifest("hsx.source-identity-manifest/1", source_records)
    symbol_component, symbol_digest = _component(
        "hsx.debug-component.symbol-model/1",
        "hsx.debug-component.symbol-model/1",
        symbol_records if symbol_records is not None else _base_symbol_records(),
    )
    unwind_component, unwind_digest = _component(
        "hsx.unwind-recipe/1",
        "hsx.debug-component.unwind-recipe/1",
        unwind_rows if unwind_rows is not None else _unwind_rows(),
    )
    location_component, location_digest = _component(
        "hsx.location-recipe/1",
        "hsx.debug-component.location-recipe/1",
        location_rows if location_rows is not None else _location_rows(),
    )
    artifact = ArtifactRef(
        "hsx.artifact-ref/1",
        "application/vnd.hsx.hxe",
        CanonicalUInt64(1),
        CanonicalUInt64(64),
        ContentDigest("sha256", ZERO),
    )
    target = TargetRef("target", ExecutiveInstanceRef("exec"), "opaque", 1, 7, 1)
    image = LoadedImageRef(
        "hsx.loaded-image-ref/1",
        target.executive,
        target,
        "image",
        CanonicalUInt64(1),
        artifact,
    )
    bundle = ImageDebugBundleIdentityPayload(
        "hsx.image-debug-bundle/1",
        artifact,
        DescriptorDigestRef(architecture.ref.ref, architecture.ref.digest),
        DescriptorDigestRef(abi.ref, abi.digest),
        ComponentDigestRef("hsx.debug-component.symbol-model/1", symbol_digest),
        ComponentDigestRef("hsx.unwind-recipe/1", unwind_digest),
        ComponentDigestRef("hsx.location-recipe/1", location_digest),
        StructuredDigest("sha256", manifest.canonical_digest()),
        (),
        (),
    )
    bundle_ref = ImageDebugBundleRef(
        "hsx.image-debug-bundle-ref/1", artifact, "sha256", bundle.canonical_digest()
    )
    binding_payload = ImageDebugBindingPayload(
        "hsx.image-debug-binding/1",
        image,
        bundle_ref,
        architecture.ref.ref,
        abi.ref,
        "hsx.portable-debug-runtime/1",
    )
    binding = ImageDebugBinding(binding_payload, binding_payload.canonical_digest())
    components = (location_component, symbol_component, unwind_component)
    return SimpleNamespace(**locals())


def build(f: SimpleNamespace) -> ResolutionResult[DebugArtifactIndex]:
    return DebugArtifactIndex.build(
        f.binding, f.bundle, f.manifest, f.architecture, f.abi, f.components
    )


def test_portable_build_verifies_components_and_exposes_fixed_order_and_queries() -> None:
    f = portable_fixture()
    result = build(f)
    assert result.status is ResolutionStatus.RESOLVED
    index = result.values[0]
    assert index.binding() == f.binding
    assert index.bundle_identity() == f.bundle
    assert [source.logical_id for source in index.source_identities()] == [
        "lib/Foo.c",
        "src/Foo.c",
        "src/foo.c",
    ]
    assert [function.function_id for function in index.functions()] == ["fn"]
    assert [record.type_id for record in index.types()] == ["i16"]
    assert index.type_by_id("i16").status is ResolutionStatus.RESOLVED
    assert index.type_by_id("missing").status is ResolutionStatus.UNAVAILABLE
    assert [scope.lexical_scope_id for scope in index.lexical_scopes("fn", HsxAddress(f.architecture.pc_space, 0x24))] == ["scope"]
    assert [symbol.symbol_id for symbol in index.variables_in_scope("scope", HsxAddress(f.architecture.pc_space, 0x24))] == ["local"]
    assert [symbol.symbol_id for symbol in index.global_variables()] == ["global", "constant"]
    assert [region.region_id for region in index.memory_regions()] == ["text", "data"]
    assert index.unwind_rows(HsxAddress(f.architecture.pc_space, 0x24), "fn").values[0].row_id == "uw"
    assert index.location_rows("local", "fn", "scope", HsxAddress(f.architecture.pc_space, 0x24)).values[0].row_id == "loc-local"


def test_empty_canonical_components_and_manifest_publish_an_empty_exact_index() -> None:
    f = portable_fixture(symbol_records=[], unwind_rows=[], location_rows=[], sources=())
    result = build(f)
    assert result.status is ResolutionStatus.RESOLVED
    index = result.values[0]
    assert index.source_identities() == ()
    assert index.functions() == ()
    assert index.types() == ()
    assert index.memory_regions() == ()
    symbol = next(
        item for item in f.components if item.schema == "hsx.debug-component.symbol-model/1"
    )
    assert symbol.canonical_digest == "767ad5f9e1ae49abdc33dfd990e81fc3a5a6b064e23d2e44992dfe20f0d94a73"


def test_duplicate_names_and_multiple_line_addresses_are_complete_ordered_candidates() -> None:
    f = portable_fixture()
    index = build(f).values[0]
    duplicate = index.symbols_named("dup")
    assert duplicate.status is ResolutionStatus.AMBIGUOUS
    assert [symbol.symbol_id for symbol in duplicate.values] == ["sym-fn", "sym-label"]
    variable_name = index.symbols_named("value")
    assert variable_name.status is ResolutionStatus.AMBIGUOUS
    assert [symbol.symbol_id for symbol in variable_name.values] == ["global", "local"]
    source = next(item for item in index.source_identities() if item.logical_id == "src/Foo.c")
    locations = index.source_locations(source, 12, None)
    assert locations.status is ResolutionStatus.RESOLVED
    assert [record.instruction_id for record in locations.values] == ["insn-a", "insn-b"]
    assert [record.instruction_id for record in index.source_locations(source, 12, 9).values] == ["insn-b"]


def test_exact_source_identity_has_no_case_or_basename_alias() -> None:
    f = portable_fixture()
    index = build(f).values[0]
    refs = {source.logical_id: source for source in index.source_identities()}
    assert refs["src/Foo.c"] != refs["src/foo.c"]
    assert refs["src/Foo.c"] != refs["lib/Foo.c"]
    assert index.source_locations(refs["src/foo.c"], 12, None).status is ResolutionStatus.UNAVAILABLE
    foreign = replace(refs["src/Foo.c"], logical_id="lib/Foo.c")
    assert index.source_locations(foreign, 12, None).status is ResolutionStatus.UNAVAILABLE


def test_index_and_caller_inputs_are_immutable_after_build() -> None:
    records = _base_symbol_records()
    f = portable_fixture(symbol_records=records)
    index = build(f).values[0]
    records.clear()
    assert len(index.functions()) == 1
    with pytest.raises(FrozenInstanceError):
        index._functions = ()
    with pytest.raises(FrozenInstanceError):
        index.source_identities()[0].logical_id = "changed.c"
    with pytest.raises(TypeError):
        DebugArtifactIndex()


@pytest.mark.parametrize(
    ("replacement", "code"),
    [
        (lambda f: replace(f.binding, binding_digest="f" * 64), "binding_digest_mismatch"),
        (
            lambda f: replace(
                f.binding,
                payload=replace(
                    f.binding.payload,
                    accepted_architecture_descriptor_ref="other-architecture",
                ),
            ),
            "binding_digest_mismatch",
        ),
    ],
)
def test_binding_mismatch_is_first_and_publishes_no_index(replacement, code: str) -> None:
    f = portable_fixture()
    malformed = replace(f.components[0], content=b"not-json")
    f.components = (malformed, *f.components[1:])
    f.binding = replacement(f)
    result = build(f)
    assert result.status is ResolutionStatus.ARTIFACT_MISMATCH
    assert result.values == ()
    assert result.diagnostics[0].code == code


def test_manifest_and_component_digest_mismatches_publish_no_index() -> None:
    f = portable_fixture()
    f.manifest = SourceIdentityManifest(
        "hsx.source-identity-manifest/1",
        (
            SourceIdentityRecord(
                "different.c", ContentDigest("sha256", "d" * 64), CanonicalUInt64(1)
            ),
        ),
    )
    result = build(f)
    assert (result.status, result.diagnostics[0].code) == (
        ResolutionStatus.ARTIFACT_MISMATCH,
        "source_manifest_digest_mismatch",
    )

    f = portable_fixture()
    f.components = (replace(f.components[0], canonical_digest="f" * 64), *f.components[1:])
    result = build(f)
    assert (result.status, result.diagnostics[0].code) == (
        ResolutionStatus.ARTIFACT_MISMATCH,
        "component_digest_ref_mismatch",
    )

    f = portable_fixture()
    original = f.components[0]
    f.components = (replace(original, content=original.content + b" "), *f.components[1:])
    assert build(f).status is ResolutionStatus.RESOLVED
    f.components = (replace(original, content=original.content.replace(b"loc-local", b"loc-changed")), *f.components[1:])
    result = build(f)
    assert (result.status, result.diagnostics[0].code) == (
        ResolutionStatus.ARTIFACT_MISMATCH,
        "component_digest_mismatch",
    )


def test_component_cardinality_unknown_schema_and_unknown_fields_are_classified() -> None:
    f = portable_fixture()
    f.components = f.components[:-1]
    assert build(f).status is ResolutionStatus.CORRUPT

    f = portable_fixture()
    f.components = (*f.components, f.components[0])
    assert build(f).status is ResolutionStatus.CORRUPT

    f = portable_fixture()
    unknown = DebugComponentInput("future", "hsx.future/1", "f" * 64, b"{}")
    f.components = (*f.components, unknown)
    assert build(f).status is ResolutionStatus.SCHEMA_UNSUPPORTED

    records = _base_symbol_records()
    records[0]["future"] = "mandatory"
    f = portable_fixture(symbol_records=records)
    result = build(f)
    assert (result.status, result.diagnostics[0].code) == (
        ResolutionStatus.SCHEMA_UNSUPPORTED,
        "unsupported_component_field",
    )


@pytest.mark.parametrize(
    "content",
    [
        b"not-json",
        b'{"component_schema":"hsx.debug-component.symbol-model/1","records":[],"records":[]}',
        b'{"component_schema":"hsx.debug-component.symbol-model/1","records":1}',
        b'{"component_schema":"hsx.debug-component.symbol-model/1","records":null}',
    ],
)
def test_malformed_duplicate_numeric_and_null_component_content_is_corrupt(content: bytes) -> None:
    f = portable_fixture()
    symbol = next(item for item in f.components if item.schema == "hsx.debug-component.symbol-model/1")
    digest = canonical_structured_digest(
        "hsx.debug-component.symbol-model/1",
        {"component_schema": "hsx.debug-component.symbol-model/1", "records": []},
    )
    # Keep both supplied and accepted refs coherent so the parser, not ref validation, classifies it.
    changed = replace(symbol, canonical_digest=digest, content=content)
    f.components = tuple(changed if item is symbol else item for item in f.components)
    f.bundle = replace(f.bundle, symbol_model=replace(f.bundle.symbol_model, canonical_component_digest=digest))
    bundle_ref = replace(f.binding.payload.image_debug_bundle_ref, bundle_digest=f.bundle.canonical_digest())
    payload = replace(f.binding.payload, image_debug_bundle_ref=bundle_ref)
    f.binding = ImageDebugBinding(payload, payload.canonical_digest())
    assert build(f).status is ResolutionStatus.CORRUPT


@pytest.mark.parametrize(
    ("mutate", "diagnostic"),
    [
        (
            lambda records: records.append(dict(records[1])),
            "duplicate_record_identity",
        ),
        (
            lambda records: records.__setitem__(5, {**records[5], "function_id": "missing"}),
            "variable_scope_join_mismatch",
        ),
        (
            lambda records: records.__setitem__(5, {**records[5], "type_id": "missing"}),
            "symbol_type_join_missing",
        ),
        (
            lambda records: records.append(
                {
                    **records[10],
                    "region_id": "data-overlap",
                    "range": _range("data", 0x110, 0x20),
                }
            ),
            "overlapping_memory_regions",
        ),
    ],
)
def test_duplicate_overlap_and_join_failures_are_corrupt(mutate, diagnostic: str) -> None:
    records = _base_symbol_records()
    mutate(records)
    result = build(portable_fixture(symbol_records=records))
    assert result.status is ResolutionStatus.CORRUPT
    assert result.diagnostics[0].code == diagnostic


def test_instruction_identity_overlap_is_query_corrupt_but_distinct_candidate_is_retained() -> None:
    records = _base_symbol_records()
    duplicate_address = {**records[8], "instruction_id": "insn-alias", "encoded_word": "3"}
    records.append(duplicate_address)
    f = portable_fixture(symbol_records=records)
    result = build(f)
    assert result.status is ResolutionStatus.RESOLVED
    queried = result.values[0].instruction_at(HsxAddress(f.architecture.pc_space, 0x24))
    assert queried.status is ResolutionStatus.CORRUPT
    assert queried.values == ()


def test_unwind_and_location_overlap_and_abi_mismatch_are_corrupt() -> None:
    unwind = _unwind_rows()
    unwind.append({**unwind[0], "row_id": "uw-overlap", "pc_range": _range("code", 0x24, 4)})
    result = build(portable_fixture(unwind_rows=unwind))
    assert result.status is ResolutionStatus.CORRUPT
    assert result.diagnostics[0].code == "overlapping_unwind_rows"

    locations = _location_rows()
    locations.append({**locations[0], "row_id": "loc-overlap", "pc_range": _range("code", 0x24, 4)})
    result = build(portable_fixture(location_rows=locations))
    assert result.status is ResolutionStatus.CORRUPT
    assert result.diagnostics[0].code == "overlapping_location_rows"

    unwind = _unwind_rows()
    unwind[0] = {**unwind[0], "abi": {"ref": "other", "digest": "f" * 64}}
    result = build(portable_fixture(unwind_rows=unwind))
    assert result.status is ResolutionStatus.CORRUPT
    assert result.diagnostics[0].code == "row_abi_mismatch"


def test_unknown_recipe_schema_and_opcode_are_unsupported() -> None:
    unwind = _unwind_rows()
    unwind[0] = {**unwind[0], "schema": "hsx.unwind-recipe/2"}
    result = build(portable_fixture(unwind_rows=unwind))
    assert result.status is ResolutionStatus.SCHEMA_UNSUPPORTED
    assert result.diagnostics[0].code == "unsupported_recipe_schema"

    unwind = _unwind_rows()
    unwind[0]["cfa_expression"] = {
        **unwind[0]["cfa_expression"],
        "opcodes": [{"opcode": "future_opcode"}],
    }
    result = build(portable_fixture(unwind_rows=unwind))
    assert result.status is ResolutionStatus.SCHEMA_UNSUPPORTED
    assert result.diagnostics[0].code == "unsupported_opcode"


def test_variable_rows_are_mandatory_and_address_bearing_symbols_cannot_own_them() -> None:
    result = build(portable_fixture(location_rows=_location_rows()[:-1]))
    assert result.status is ResolutionStatus.CORRUPT
    assert result.diagnostics[0].code == "variable_location_join_missing"

    locations = _location_rows()
    locations[0] = {
        **locations[0],
        "symbol_id": "sym-label",
        "function_id": "fn",
        "lexical_scope_id": "scope",
        "declared_type_id": "i16",
    }
    result = build(portable_fixture(location_rows=locations))
    assert result.status is ResolutionStatus.CORRUPT
    assert result.diagnostics[0].code == "invalid_location_symbol_kind"


def test_multiple_spaces_and_widths_are_descriptor_checked_without_masks() -> None:
    records = _base_symbol_records()
    records[1] = {**records[1], "range": _range("code", 0x10020, 4)}
    records[3] = {**records[3], "address": _address("code", 0x10020), "byte_size": "4"}
    records[2] = {**records[2], "pc_range": _range("code", 0x10020, 4)}
    for index in (8, 9):
        records[index] = {**records[index], "address": _address("code", 0x10020 + (index - 9) * 4)}
    records[10] = {**records[10], "range": _range("data", 0x100, 0x20)}
    records[11] = {**records[11], "range": _range("code", 0x10020, 4)}
    # Location/unwind PC rows are still outside the relocated function, so join validation is exact.
    result = build(portable_fixture(symbol_records=records))
    assert result.status is ResolutionStatus.CORRUPT

    narrow = replace(
        _architecture(code_width=16),
        ref=ArchitectureDescriptorRef("hsx.arch.vm-byte16-gpr32/1", "f" * 64),
    )
    f = portable_fixture()
    f.architecture = narrow
    result = build(f)
    assert result.status is ResolutionStatus.ARTIFACT_MISMATCH
    assert result.diagnostics[0].code == "binding_architecture_ref_mismatch"


def legacy_build(*, architecture: ArchitectureDescriptor | None = None):
    return LegacySymbolAdapter.build(
        (FIXTURE_DIR / "legacy_symbols_v1.sym").read_bytes(),
        0x12345678,
        architecture or _architecture(),
    )


def test_legacy_v1_adapter_preserves_classified_candidates_and_provenance() -> None:
    result = legacy_build()
    assert result.status is ResolutionStatus.RESOLVED
    index = result.values[0]
    provenance = index.provenance()
    raw = (FIXTURE_DIR / "legacy_symbols_v1.sym").read_bytes()
    assert provenance.profile == "hsx.python-debug-legacy/1"
    assert provenance.identity_status is LegacyIdentityStatus.LEGACY_UNVERIFIED
    assert provenance.sym_content_digest.value == hashlib.sha256(raw).hexdigest()
    assert provenance.hxe_crc32 == 0x12345678
    assert [function.name for function in index.functions()] == ["main", "shared", "wide_address"]
    duplicate = index.symbols_named("shared")
    assert duplicate.status is ResolutionStatus.AMBIGUOUS
    assert [symbol.kind for symbol in duplicate.values] == [
        SymbolKind.FUNCTION,
        SymbolKind.LABEL,
        SymbolKind.GLOBAL,
    ]
    assert index.instruction_at(HsxAddress(AddressSpaceId("code"), 0x10004)).status is ResolutionStatus.RESOLVED
    assert [region.name for region in index.memory_regions()] == ["code", "rodata"]


def test_legacy_source_spelling_is_exact_and_multiple_lines_are_complete() -> None:
    index = legacy_build().values[0]
    exact = LegacySourceSpelling("src/main.c", "build/project")
    rows = index.source_spelling_locations(exact, 12, None)
    assert rows.status is ResolutionStatus.RESOLVED
    assert [row.address.unsigned_value for row in rows.values] == [260, 264]
    assert index.source_spelling_locations(LegacySourceSpelling("main.c", "build/project"), 12, None).status is ResolutionStatus.UNAVAILABLE
    assert index.source_spelling_locations(LegacySourceSpelling("SRC/MAIN.C", "build/project"), 12, None).status is ResolutionStatus.UNAVAILABLE
    assert index.source_spelling_locations(LegacySourceSpelling("src/main.c", None), 12, None).status is ResolutionStatus.UNAVAILABLE


def test_legacy_adapter_has_no_portable_binding_source_or_recipe_surface() -> None:
    index = legacy_build().values[0]
    for name in ("binding", "bundle_identity", "source_identities", "unwind_rows", "location_rows"):
        assert not hasattr(index, name)
    assert all(not hasattr(function, "definition") for function in index.functions())
    instruction = index.instruction_at(HsxAddress(AddressSpaceId("code"), 0x100)).values[0]
    assert isinstance(instruction.source_spelling, LegacySourceSpelling)
    assert not isinstance(instruction, InstructionRecord)


def test_legacy_malformed_version_crc_and_narrow_address_are_classified() -> None:
    malformed = LegacySymbolAdapter.build(
        (FIXTURE_DIR / "legacy_symbols_malformed.sym").read_bytes(),
        0x12345678,
        _architecture(),
    )
    assert malformed.status is ResolutionStatus.CORRUPT
    version = LegacySymbolAdapter.build(
        (FIXTURE_DIR / "legacy_symbols_version2.sym").read_bytes(),
        0x11111111,
        _architecture(),
    )
    assert version.status is ResolutionStatus.SCHEMA_UNSUPPORTED
    mismatch = LegacySymbolAdapter.build(
        (FIXTURE_DIR / "legacy_symbols_image_mismatch.sym").read_bytes(),
        0x22222222,
        _architecture(),
    )
    assert mismatch.status is ResolutionStatus.ARTIFACT_MISMATCH
    narrow = legacy_build(architecture=_architecture(code_width=16))
    assert narrow.status is ResolutionStatus.CORRUPT
    assert narrow.diagnostics[0].code == "legacy_address_invalid"


def test_legacy_adapter_does_not_lowercase_mask_or_choose_first() -> None:
    index = legacy_build().values[0]
    assert index.symbols_named("shared").status is ResolutionStatus.AMBIGUOUS
    assert index.symbols_named("SHARED").status is ResolutionStatus.UNAVAILABLE
    assert index.instruction_at(HsxAddress(AddressSpaceId("code"), 4)).status is ResolutionStatus.UNAVAILABLE
    assert index.instruction_at(HsxAddress(AddressSpaceId("code"), 0x10004)).status is ResolutionStatus.RESOLVED


def test_legacy_public_inputs_are_strict() -> None:
    with pytest.raises(ValueError):
        LegacySymbolAdapter.build(b"{}", -1, _architecture())
    with pytest.raises(TypeError):
        LegacySymbolAdapter.build(bytearray(b"{}"), 0, _architecture())
    with pytest.raises(TypeError):
        LegacyDebugArtifactIndex()
    with pytest.raises(FrozenInstanceError):
        legacy_build().values[0]._functions = ()


def test_public_artifact_exports_are_unique_and_append_only_visible() -> None:
    import hsx_debugger

    expected = {
        "DebugArtifactIndex",
        "LegacyArtifactProvenance",
        "LegacyDebugArtifactIndex",
        "LegacyFunctionRecord",
        "LegacyIdentityStatus",
        "LegacyInstructionRecord",
        "LegacyResolutionResult",
        "LegacySourceSpelling",
        "LegacySymbolAdapter",
    }
    assert expected <= set(hsx_debugger.__all__)
    assert len(hsx_debugger.__all__) == len(set(hsx_debugger.__all__))
