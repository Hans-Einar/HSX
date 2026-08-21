"""Binding-verified immutable portable debug artifact index.

This module is deliberately a parsing and indexing boundary.  It does not resolve local
source files, read target state, walk a stack, allocate frontend handles, or provide a
compatibility fallback.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import re
import unicodedata
from typing import Mapping

from .addresses import (
    AddressSpaceId,
    ArchitectureDescriptor,
    ByteOrder,
    HsxAddress,
    HsxAddressRange,
    Permission,
)
from .identity import (
    AbiDescriptorRef,
    DebugBindingValidator,
    ImageDebugBinding,
    ImageDebugBundleIdentityPayload,
    RecipeSchemaRef,
    SourceRef,
    canonical_structured_digest,
)
from .metadata import (
    DebugComponentInput,
    FunctionRecord,
    InstructionClassification,
    InstructionRecord,
    LexicalScopeRecord,
    MemoryRegion,
    SourceIdentityManifest,
    SourceLocation,
    SymbolKind,
    SymbolRecord,
    TypeKind,
    TypeMember,
    TypeRecord,
)
from .recipes import (
    LocationRow,
    RecipeComponentValidator,
    RecipeEvaluationStatus,
    RecipeParseError,
    RecipeParser,
    UnwindRow,
)
from .results import AddressStatus, Diagnostic, ResolutionResult, ResolutionStatus


_SYMBOL_SCHEMA = "hsx.debug-component.symbol-model/1"
_UNWIND_SCHEMA = "hsx.unwind-recipe/1"
_LOCATION_SCHEMA = "hsx.location-recipe/1"
_COMPONENT_DOMAINS = {
    _SYMBOL_SCHEMA: _SYMBOL_SCHEMA,
    _UNWIND_SCHEMA: "hsx.debug-component.unwind-recipe/1",
    _LOCATION_SCHEMA: "hsx.debug-component.location-recipe/1",
}
_UNSIGNED_DECIMAL = re.compile(r"(?:0|[1-9][0-9]*)\Z")
_SIGNED_DECIMAL = re.compile(r"(?:0|-?[1-9][0-9]*)\Z")
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")
_SYMBOL_KIND_RANK = {
    SymbolKind.FUNCTION: 0,
    SymbolKind.LABEL: 1,
    SymbolKind.GLOBAL: 2,
    SymbolKind.LOCAL: 3,
    SymbolKind.CONSTANT: 4,
}


class _ArtifactError(ValueError):
    def __init__(
        self,
        status: ResolutionStatus,
        code: str,
        message: str,
        *,
        component: str = "artifact",
        row_id: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status = status
        self.diagnostic = Diagnostic(code, message, component=component, row_id=row_id)


def _fail(
    status: ResolutionStatus,
    code: str,
    message: str,
    *,
    component: str = "artifact",
    row_id: str | None = None,
) -> _ArtifactError:
    return _ArtifactError(status, code, message, component=component, row_id=row_id)


def _reject_json_number(value: str):
    raise _fail(
        ResolutionStatus.CORRUPT,
        "noncanonical_component_number",
        f"component integer {value!r} must be a minimal decimal JSON string",
        component="component",
    )


def _object_from_pairs(pairs: list[tuple[object, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if not isinstance(key, str):
            raise _fail(
                ResolutionStatus.CORRUPT,
                "malformed_component_key",
                "component object keys must be strings",
                component="component",
            )
        normalized = unicodedata.normalize("NFC", key)
        if normalized in result:
            raise _fail(
                ResolutionStatus.CORRUPT,
                "duplicate_component_key",
                f"component object key {normalized!r} is duplicated or NFC-colliding",
                component="component",
            )
        result[normalized] = value
    return result


def _normalize_json(value: object) -> object:
    if isinstance(value, str):
        normalized = unicodedata.normalize("NFC", value)
        if _CONTROL.search(normalized):
            raise _fail(
                ResolutionStatus.CORRUPT,
                "component_control_character",
                "component strings must not contain control characters",
                component="component",
            )
        try:
            normalized.encode("utf-8")
        except UnicodeEncodeError as exc:
            raise _fail(
                ResolutionStatus.CORRUPT,
                "component_invalid_unicode",
                "component strings must contain Unicode scalar values",
                component="component",
            ) from exc
        return normalized
    if isinstance(value, list):
        return [_normalize_json(item) for item in value]
    if isinstance(value, dict):
        return {key: _normalize_json(item) for key, item in value.items()}
    if isinstance(value, bool):
        return value
    if value is None:
        raise _fail(
            ResolutionStatus.CORRUPT,
            "noncanonical_component_null",
            "absent optional component fields must be omitted, not null",
            component="component",
        )
    raise _fail(
        ResolutionStatus.CORRUPT,
        "malformed_component_value",
        f"unsupported component JSON value {type(value).__name__}",
        component="component",
    )


def _load_component_payload(component: DebugComponentInput) -> Mapping[str, object]:
    try:
        text = component.content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise _fail(
            ResolutionStatus.CORRUPT,
            "component_not_utf8",
            "component content must be UTF-8",
            component=component.component_id,
        ) from exc
    if text.startswith("\ufeff"):
        raise _fail(
            ResolutionStatus.CORRUPT,
            "component_bom_forbidden",
            "component content must not contain a BOM",
            component=component.component_id,
        )
    try:
        value = json.loads(
            text,
            object_pairs_hook=_object_from_pairs,
            parse_int=_reject_json_number,
            parse_float=_reject_json_number,
            parse_constant=_reject_json_number,
        )
    except _ArtifactError:
        raise
    except (json.JSONDecodeError, UnicodeError) as exc:
        raise _fail(
            ResolutionStatus.CORRUPT,
            "malformed_component_json",
            "component content is not valid JSON",
            component=component.component_id,
        ) from exc
    value = _normalize_json(value)
    if not isinstance(value, Mapping):
        raise _fail(
            ResolutionStatus.CORRUPT,
            "malformed_component_document",
            "component document must be an object",
            component=component.component_id,
        )
    return value


def _record(
    value: object,
    required: frozenset[str],
    optional: frozenset[str],
    kind: str,
) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise _fail(
            ResolutionStatus.CORRUPT,
            "malformed_component_record",
            f"{kind} must be an object",
            component="component",
        )
    keys = frozenset(value.keys())
    unknown = keys - required - optional
    if unknown:
        raise _fail(
            ResolutionStatus.SCHEMA_UNSUPPORTED,
            "unsupported_component_field",
            f"{kind} contains unsupported fields {tuple(sorted(unknown))!r}",
            component="component",
        )
    missing = required - keys
    if missing:
        raise _fail(
            ResolutionStatus.CORRUPT,
            "missing_component_field",
            f"{kind} is missing fields {tuple(sorted(missing))!r}",
            component="component",
        )
    return value


def _nonempty(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value:
        raise _fail(
            ResolutionStatus.CORRUPT,
            "malformed_component_field",
            f"{field_name} must be a non-empty string",
            component="component",
        )
    return value


def _uint(value: object, field_name: str, *, minimum: int = 0) -> int:
    if not isinstance(value, str) or _UNSIGNED_DECIMAL.fullmatch(value) is None:
        raise _fail(
            ResolutionStatus.CORRUPT,
            "malformed_component_integer",
            f"{field_name} must be a minimal unsigned decimal string",
            component="component",
        )
    result = int(value, 10)
    if result < minimum:
        raise _fail(
            ResolutionStatus.CORRUPT,
            "malformed_component_integer",
            f"{field_name} must be >= {minimum}",
            component="component",
        )
    return result


def _sint(value: object, field_name: str) -> int:
    if not isinstance(value, str) or _SIGNED_DECIMAL.fullmatch(value) is None:
        raise _fail(
            ResolutionStatus.CORRUPT,
            "malformed_component_integer",
            f"{field_name} must be a minimal signed decimal string",
            component="component",
        )
    return int(value, 10)


def _sequence(value: object, field_name: str) -> tuple[object, ...]:
    if not isinstance(value, list):
        raise _fail(
            ResolutionStatus.CORRUPT,
            "malformed_component_field",
            f"{field_name} must be an array",
            component="component",
        )
    return tuple(value)


def _enum(enum_type, value: object, field_name: str):
    if not isinstance(value, str):
        raise _fail(
            ResolutionStatus.CORRUPT,
            "malformed_component_field",
            f"{field_name} must be a string",
            component="component",
        )
    try:
        return enum_type(value)
    except ValueError as exc:
        raise _fail(
            ResolutionStatus.SCHEMA_UNSUPPORTED,
            "unsupported_component_field_value",
            f"{field_name} has unsupported value {value!r}",
            component="component",
        ) from exc


def _address(value: object, field_name: str) -> HsxAddress:
    item = _record(value, frozenset({"space_id", "unsigned_value"}), frozenset(), field_name)
    return HsxAddress(
        AddressSpaceId(_nonempty(item["space_id"], f"{field_name}.space_id")),
        _uint(item["unsigned_value"], f"{field_name}.unsigned_value"),
    )


def _address_range(value: object, field_name: str) -> HsxAddressRange:
    item = _record(value, frozenset({"start", "length_units"}), frozenset(), field_name)
    return HsxAddressRange(
        _address(item["start"], f"{field_name}.start"),
        _uint(item["length_units"], f"{field_name}.length_units", minimum=1),
    )


def _abi(value: object, field_name: str) -> AbiDescriptorRef:
    item = _record(value, frozenset({"ref", "digest"}), frozenset(), field_name)
    return AbiDescriptorRef(_nonempty(item["ref"], f"{field_name}.ref"), _nonempty(item["digest"], f"{field_name}.digest"))


def _source_location(value: object, source_refs: Mapping[str, SourceRef], field_name: str) -> SourceLocation:
    item = _record(value, frozenset({"logical_id", "line"}), frozenset({"column", "discriminator"}), field_name)
    logical_id = _nonempty(item["logical_id"], f"{field_name}.logical_id")
    source = source_refs.get(logical_id)
    if source is None:
        raise _fail(ResolutionStatus.CORRUPT, "source_identity_join_missing", f"{field_name} names unknown source logical ID {logical_id!r}", component="symbol_model")
    return SourceLocation(
        source,
        _uint(item["line"], f"{field_name}.line", minimum=1),
        _uint(item["column"], f"{field_name}.column", minimum=1) if "column" in item else None,
        _uint(item["discriminator"], f"{field_name}.discriminator") if "discriminator" in item else None,
    )


def _type_member(value: object) -> TypeMember:
    item = _record(value, frozenset({"name", "type_id", "bit_offset", "bit_size"}), frozenset(), "type member")
    return TypeMember(
        _nonempty(item["name"], "member.name"),
        _nonempty(item["type_id"], "member.type_id"),
        _uint(item["bit_offset"], "member.bit_offset"),
        _uint(item["bit_size"], "member.bit_size", minimum=1),
    )


def _parse_symbol_records(payload: Mapping[str, object], source_refs: Mapping[str, SourceRef]) -> tuple[tuple[FunctionRecord, ...], tuple[SymbolRecord, ...], tuple[TypeRecord, ...], tuple[LexicalScopeRecord, ...], tuple[InstructionRecord, ...], tuple[MemoryRegion, ...]]:
    document = _record(payload, frozenset({"component_schema", "records"}), frozenset(), "symbol component")
    if document["component_schema"] != _SYMBOL_SCHEMA:
        raise _fail(ResolutionStatus.SCHEMA_UNSUPPORTED, "unsupported_component_schema", "symbol component_schema is not hsx.debug-component.symbol-model/1", component="symbol_model")
    functions: list[FunctionRecord] = []
    symbols: list[SymbolRecord] = []
    types: list[TypeRecord] = []
    scopes: list[LexicalScopeRecord] = []
    instructions: list[InstructionRecord] = []
    regions: list[MemoryRegion] = []
    for raw in _sequence(document["records"], "symbol component records"):
        if not isinstance(raw, Mapping):
            raise _fail(ResolutionStatus.CORRUPT, "malformed_component_record", "symbol component records must be objects", component="symbol_model")
        record_kind = raw.get("record_kind")
        if not isinstance(record_kind, str):
            raise _fail(ResolutionStatus.CORRUPT, "missing_component_record_kind", "symbol component record_kind must be a string", component="symbol_model")
        if record_kind == "function":
            item = _record(raw, frozenset({"record_kind", "function_id", "name", "range"}), frozenset({"linkage_name", "definition"}), "function record")
            functions.append(FunctionRecord(
                _nonempty(item["function_id"], "function_id"),
                _nonempty(item["name"], "function.name"),
                _nonempty(item["linkage_name"], "function.linkage_name") if "linkage_name" in item else None,
                _address_range(item["range"], "function.range"),
                _source_location(item["definition"], source_refs, "function.definition") if "definition" in item else None,
            ))
        elif record_kind == "symbol":
            item = _record(raw, frozenset({"record_kind", "symbol_id", "name", "kind", "byte_size", "declaration_order"}), frozenset({"address", "function_id", "lexical_scope_id", "type_id"}), "symbol record")
            symbols.append(SymbolRecord(
                _nonempty(item["symbol_id"], "symbol_id"),
                _nonempty(item["name"], "symbol.name"),
                _enum(SymbolKind, item["kind"], "symbol.kind"),
                _address(item["address"], "symbol.address") if "address" in item else None,
                _uint(item["byte_size"], "symbol.byte_size"),
                _nonempty(item["function_id"], "symbol.function_id") if "function_id" in item else None,
                _nonempty(item["lexical_scope_id"], "symbol.lexical_scope_id") if "lexical_scope_id" in item else None,
                _nonempty(item["type_id"], "symbol.type_id") if "type_id" in item else None,
                _uint(item["declaration_order"], "symbol.declaration_order"),
            ))
        elif record_kind == "type":
            item = _record(raw, frozenset({"record_kind", "type_id", "name", "kind", "bit_size", "byte_order", "members"}), frozenset(), "type record")
            types.append(TypeRecord(
                _nonempty(item["type_id"], "type_id"),
                _nonempty(item["name"], "type.name"),
                _enum(TypeKind, item["kind"], "type.kind"),
                _uint(item["bit_size"], "type.bit_size", minimum=1),
                _enum(ByteOrder, item["byte_order"], "type.byte_order"),
                tuple(_type_member(member) for member in _sequence(item["members"], "members")),
            ))
        elif record_kind == "lexical_scope":
            item = _record(raw, frozenset({"record_kind", "lexical_scope_id", "function_id", "pc_range", "declaration_order"}), frozenset({"parent_scope_id"}), "lexical scope record")
            scopes.append(LexicalScopeRecord(
                _nonempty(item["lexical_scope_id"], "lexical_scope_id"),
                _nonempty(item["function_id"], "scope.function_id"),
                _nonempty(item["parent_scope_id"], "scope.parent_scope_id") if "parent_scope_id" in item else None,
                _address_range(item["pc_range"], "scope.pc_range"),
                _uint(item["declaration_order"], "scope.declaration_order"),
            ))
        elif record_kind == "instruction":
            item = _record(raw, frozenset({"record_kind", "instruction_id", "address", "byte_size", "classification"}), frozenset({"encoded_word", "function_id", "source"}), "instruction record")
            instructions.append(InstructionRecord(
                _nonempty(item["instruction_id"], "instruction_id"),
                _address(item["address"], "instruction.address"),
                _uint(item["byte_size"], "instruction.byte_size", minimum=1),
                _uint(item["encoded_word"], "instruction.encoded_word") if "encoded_word" in item else None,
                _nonempty(item["function_id"], "instruction.function_id") if "function_id" in item else None,
                _source_location(item["source"], source_refs, "instruction.source") if "source" in item else None,
                _enum(InstructionClassification, item["classification"], "instruction.classification"),
            ))
        elif record_kind == "memory_region":
            item = _record(raw, frozenset({"record_kind", "region_id", "name", "kind", "range", "permissions"}), frozenset(), "memory region record")
            permissions = frozenset(_enum(Permission, permission, "memory_region.permission") for permission in _sequence(item["permissions"], "memory_region.permissions"))
            regions.append(MemoryRegion(
                _nonempty(item["region_id"], "region_id"),
                _nonempty(item["name"], "memory_region.name"),
                _nonempty(item["kind"], "memory_region.kind"),
                _address_range(item["range"], "memory_region.range"), permissions,
            ))
        else:
            raise _fail(ResolutionStatus.SCHEMA_UNSUPPORTED, "unsupported_component_record_kind", f"unsupported symbol record_kind {record_kind!r}", component="symbol_model")
    return tuple(functions), tuple(symbols), tuple(types), tuple(scopes), tuple(instructions), tuple(regions)


def _opcode_wire(value: object) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise _fail(ResolutionStatus.CORRUPT, "malformed_recipe_opcode", "recipe opcode must be an object", component="recipe")
    opcode = value.get("opcode")
    shapes: dict[str, tuple[frozenset[str], frozenset[str]]] = {
        "reg_value": (frozenset({"opcode", "register_id"}), frozenset()),
        "special_value": (frozenset({"opcode", "special"}), frozenset()),
        "const_u": (frozenset({"opcode", "value", "bit_width"}), frozenset()),
        "const_s": (frozenset({"opcode", "value", "bit_width"}), frozenset()),
        "static_address": (frozenset({"opcode", "address"}), frozenset()),
        "to_address": (frozenset({"opcode", "space"}), frozenset()),
        "cfa": (frozenset({"opcode"}), frozenset()),
        "frame_base": (frozenset({"opcode"}), frozenset()),
        "add_sconst_checked": (frozenset({"opcode", "signed_delta"}), frozenset()),
        "deref_u": (frozenset({"opcode", "byte_length", "byte_order"}), frozenset()),
        "bit_slice": (frozenset({"opcode", "source_bit_offset", "bit_size"}), frozenset()),
    }
    if not isinstance(opcode, str):
        raise _fail(ResolutionStatus.CORRUPT, "malformed_recipe_opcode", "recipe opcode name must be a string", component="recipe")
    shape = shapes.get(opcode)
    if shape is None:
        raise _fail(ResolutionStatus.SCHEMA_UNSUPPORTED, "unsupported_opcode", f"unsupported recipe opcode {opcode!r}", component="recipe")
    item = dict(_record(value, shape[0], shape[1], f"{opcode} opcode"))
    if opcode == "const_u":
        item["value"] = _uint(item["value"], "const_u.value")
        item["bit_width"] = _uint(item["bit_width"], "const_u.bit_width", minimum=1)
    elif opcode == "const_s":
        item["value"] = _sint(item["value"], "const_s.value")
        item["bit_width"] = _uint(item["bit_width"], "const_s.bit_width", minimum=1)
    elif opcode == "static_address":
        item["address"] = _address(item["address"], "static_address.address")
    elif opcode == "to_address":
        item["space"] = AddressSpaceId(_nonempty(item["space"], "to_address.space"))
    elif opcode == "add_sconst_checked":
        item["signed_delta"] = _sint(item["signed_delta"], "signed_delta")
    elif opcode == "deref_u":
        item["byte_length"] = _uint(item["byte_length"], "byte_length", minimum=1)
    elif opcode == "bit_slice":
        item["source_bit_offset"] = _uint(item["source_bit_offset"], "source_bit_offset")
        item["bit_size"] = _uint(item["bit_size"], "bit_size", minimum=1)
    return item


def _expression_wire(value: object) -> Mapping[str, object]:
    item = _record(value, frozenset({"role", "opcodes", "required_result"}), frozenset({"required_bit_width"}), "recipe expression")
    return {
        "role": item["role"],
        "opcodes": tuple(_opcode_wire(opcode) for opcode in _sequence(item["opcodes"], "opcodes")),
        "required_result": item["required_result"],
        "required_bit_width": _uint(item["required_bit_width"], "required_bit_width", minimum=1) if "required_bit_width" in item else None,
    }


def _rule_wire(value: object) -> Mapping[str, object]:
    item = _record(value, frozenset({"kind"}), frozenset({"expression", "reason"}), "recipe rule")
    return {
        "kind": item["kind"],
        "expression": _expression_wire(item["expression"]) if "expression" in item else None,
        "reason": _nonempty(item["reason"], "recipe rule reason") if "reason" in item else None,
    }


def _piece_wire(value: object) -> Mapping[str, object]:
    item = _record(value, frozenset({"destination_bit_offset", "bit_size", "expression", "source_bit_offset"}), frozenset(), "location piece")
    return {
        "destination_bit_offset": _uint(item["destination_bit_offset"], "destination_bit_offset"),
        "bit_size": _uint(item["bit_size"], "piece.bit_size", minimum=1),
        "expression": _expression_wire(item["expression"]),
        "source_bit_offset": _uint(item["source_bit_offset"], "source_bit_offset"),
    }


def _location_form_wire(value: object) -> Mapping[str, object]:
    item = _record(value, frozenset({"kind"}), frozenset({"expression", "pieces", "reason"}), "location form")
    return {
        "kind": item["kind"],
        "expression": _expression_wire(item["expression"]) if "expression" in item else None,
        "pieces": tuple(_piece_wire(piece) for piece in _sequence(item.get("pieces", []), "pieces")),
        "reason": _nonempty(item["reason"], "location reason") if "reason" in item else None,
    }


def _parse_unwind_records(payload: Mapping[str, object], binding: ImageDebugBinding, component_digest: str) -> tuple[UnwindRow, ...]:
    document = _record(payload, frozenset({"component_schema", "records"}), frozenset(), "unwind component")
    if document["component_schema"] != _UNWIND_SCHEMA:
        raise _fail(ResolutionStatus.SCHEMA_UNSUPPORTED, "unsupported_component_schema", "unwind component_schema is unsupported", component="unwind_recipe")
    rows: list[UnwindRow] = []
    for raw in _sequence(document["records"], "unwind records"):
        item = _record(raw, frozenset({"row_id", "pc_range", "abi", "schema", "cfa_expression", "caller_pc_rule", "caller_sp_rule", "register_rules", "boundary"}), frozenset({"caller_frame_base_rule", "call_site_adjustment"}), "unwind row")
        schema = _nonempty(item["schema"], "unwind row schema")
        if schema != _UNWIND_SCHEMA:
            raise _fail(ResolutionStatus.SCHEMA_UNSUPPORTED, "unsupported_recipe_schema", f"unwind row schema {schema!r} is unsupported", component="unwind_recipe")
        register_rules: list[tuple[str, Mapping[str, object]]] = []
        for entry in _sequence(item["register_rules"], "register_rules"):
            if not isinstance(entry, list) or len(entry) != 2:
                raise _fail(ResolutionStatus.CORRUPT, "malformed_recipe_field", "register_rules entries must be two-element arrays", component="unwind_recipe")
            register_rules.append((_nonempty(entry[0], "register rule ID"), _rule_wire(entry[1])))
        parser_input = {
            "row_id": _nonempty(item["row_id"], "unwind.row_id"),
            "binding": binding,
            "pc_range": _address_range(item["pc_range"], "unwind.pc_range"),
            "abi": _abi(item["abi"], "unwind.abi"),
            "schema": RecipeSchemaRef(_UNWIND_SCHEMA, component_digest),
            "cfa_expression": _expression_wire(item["cfa_expression"]),
            "caller_pc_rule": _rule_wire(item["caller_pc_rule"]),
            "caller_sp_rule": _rule_wire(item["caller_sp_rule"]),
            "caller_frame_base_rule": _rule_wire(item["caller_frame_base_rule"]) if "caller_frame_base_rule" in item else None,
            "register_rules": tuple(register_rules),
            "boundary": item["boundary"],
            "call_site_adjustment": _sint(item["call_site_adjustment"], "call_site_adjustment") if "call_site_adjustment" in item else None,
        }
        rows.append(RecipeParser.parse_unwind_row(parser_input))
    return tuple(rows)


def _parse_location_records(payload: Mapping[str, object], binding: ImageDebugBinding, component_digest: str) -> tuple[LocationRow, ...]:
    document = _record(payload, frozenset({"component_schema", "records"}), frozenset(), "location component")
    if document["component_schema"] != _LOCATION_SCHEMA:
        raise _fail(ResolutionStatus.SCHEMA_UNSUPPORTED, "unsupported_component_schema", "location component_schema is unsupported", component="location_recipe")
    rows: list[LocationRow] = []
    for raw in _sequence(document["records"], "location records"):
        item = _record(raw, frozenset({"row_id", "symbol_id", "pc_range", "declared_bit_size", "abi", "value_byte_order", "frame_binding", "schema", "location_form"}), frozenset({"lexical_scope_id", "function_id", "declared_type_id"}), "location row")
        schema = _nonempty(item["schema"], "location row schema")
        if schema != _LOCATION_SCHEMA:
            raise _fail(ResolutionStatus.SCHEMA_UNSUPPORTED, "unsupported_recipe_schema", f"location row schema {schema!r} is unsupported", component="location_recipe")
        parser_input = {
            "row_id": _nonempty(item["row_id"], "location.row_id"),
            "binding": binding,
            "symbol_id": _nonempty(item["symbol_id"], "location.symbol_id"),
            "lexical_scope_id": _nonempty(item["lexical_scope_id"], "location.lexical_scope_id") if "lexical_scope_id" in item else None,
            "function_id": _nonempty(item["function_id"], "location.function_id") if "function_id" in item else None,
            "pc_range": _address_range(item["pc_range"], "location.pc_range"),
            "declared_type_id": _nonempty(item["declared_type_id"], "location.declared_type_id") if "declared_type_id" in item else None,
            "declared_bit_size": _uint(item["declared_bit_size"], "location.declared_bit_size", minimum=1),
            "abi": _abi(item["abi"], "location.abi"),
            "value_byte_order": item["value_byte_order"],
            "frame_binding": item["frame_binding"],
            "schema": RecipeSchemaRef(_LOCATION_SCHEMA, component_digest),
            "location_form": _location_form_wire(item["location_form"]),
        }
        rows.append(RecipeParser.parse_location_row(parser_input))
    return tuple(rows)


def _range_overlaps(left: HsxAddressRange, right: HsxAddressRange) -> bool:
    return left.start.space == right.start.space and left.start.unsigned_value < right.end_unsigned_value and right.start.unsigned_value < left.end_unsigned_value


def _same_range(left: HsxAddressRange, right: HsxAddressRange) -> bool:
    return left.start == right.start and left.length_units == right.length_units


def _require_unique_ids(records: tuple[object, ...], attribute: str, label: str) -> None:
    values = tuple(getattr(record, attribute) for record in records)
    if len(set(values)) != len(values):
        raise _fail(ResolutionStatus.CORRUPT, "duplicate_record_identity", f"{label} identities must be unique", component="symbol_model")


def _validate_range(architecture: ArchitectureDescriptor, value: HsxAddressRange, label: str, *, permission: Permission | None = None, pc_space: bool = False) -> None:
    if pc_space and value.start.space != architecture.pc_space:
        raise _fail(ResolutionStatus.CORRUPT, "record_pc_space_mismatch", f"{label} is not in architecture.pc_space", component="artifact")
    result = architecture.range(value.start, value.length_units, permission)
    if result.status is not AddressStatus.VALID:
        raise _fail(ResolutionStatus.CORRUPT, "invalid_record_range", f"{label}: {result.diagnostics[0].message}", component="artifact")


def _validate_portable_records(architecture: ArchitectureDescriptor, abi: AbiDescriptorRef, source_refs: tuple[SourceRef, ...], functions: tuple[FunctionRecord, ...], symbols: tuple[SymbolRecord, ...], types: tuple[TypeRecord, ...], scopes: tuple[LexicalScopeRecord, ...], instructions: tuple[InstructionRecord, ...], regions: tuple[MemoryRegion, ...], unwind_rows: tuple[UnwindRow, ...], location_rows: tuple[LocationRow, ...]) -> None:
    _require_unique_ids(functions, "function_id", "function")
    _require_unique_ids(symbols, "symbol_id", "symbol")
    _require_unique_ids(types, "type_id", "type")
    _require_unique_ids(scopes, "lexical_scope_id", "lexical scope")
    _require_unique_ids(instructions, "instruction_id", "instruction")
    _require_unique_ids(regions, "region_id", "memory region")
    _require_unique_ids(unwind_rows, "row_id", "unwind row")
    _require_unique_ids(location_rows, "row_id", "location row")
    function_by_id = {record.function_id: record for record in functions}
    symbol_by_id = {record.symbol_id: record for record in symbols}
    type_by_id = {record.type_id: record for record in types}
    scope_by_id = {record.lexical_scope_id: record for record in scopes}
    source_set = frozenset(source_refs)
    for function in functions:
        _validate_range(architecture, function.range, f"function {function.function_id!r}", permission=Permission.EXECUTE, pc_space=True)
        if function.definition is not None and function.definition.source not in source_set:
            raise _fail(ResolutionStatus.CORRUPT, "source_identity_join_missing", "function definition SourceRef is outside the accepted manifest", component="symbol_model")
    ordered_functions = sorted(functions, key=lambda record: (record.range.start.space.value, record.range.start.unsigned_value, record.function_id))
    for prior, current in zip(ordered_functions, ordered_functions[1:]):
        if _range_overlaps(prior.range, current.range) and not _same_range(prior.range, current.range):
            raise _fail(ResolutionStatus.CORRUPT, "overlapping_function_ranges", "function ranges overlap without being exact aliases", component="symbol_model")
    for record in types:
        for member in record.members:
            if member.type_id not in type_by_id:
                raise _fail(ResolutionStatus.CORRUPT, "type_member_join_missing", f"type member names unknown type {member.type_id!r}", component="symbol_model")
    for scope in scopes:
        function = function_by_id.get(scope.function_id)
        if function is None:
            raise _fail(ResolutionStatus.CORRUPT, "scope_function_join_missing", f"scope names unknown function {scope.function_id!r}", component="symbol_model")
        _validate_range(architecture, scope.pc_range, f"scope {scope.lexical_scope_id!r}", permission=Permission.EXECUTE, pc_space=True)
        if not function.range.contains_range(scope.pc_range):
            raise _fail(ResolutionStatus.CORRUPT, "scope_outside_function", "lexical scope range must be contained by its function", component="symbol_model")
        if scope.parent_scope_id is not None:
            parent = scope_by_id.get(scope.parent_scope_id)
            if parent is None or parent.function_id != scope.function_id:
                raise _fail(ResolutionStatus.CORRUPT, "scope_parent_join_missing", "lexical scope parent must exist in the same function", component="symbol_model")
            if not parent.pc_range.contains_range(scope.pc_range):
                raise _fail(ResolutionStatus.CORRUPT, "scope_parent_range_mismatch", "lexical scope must be contained by its parent", component="symbol_model")
        visited: set[str] = set()
        current = scope
        while current.parent_scope_id is not None:
            if current.lexical_scope_id in visited:
                raise _fail(ResolutionStatus.CORRUPT, "lexical_scope_cycle", "lexical scope parent graph contains a cycle", component="symbol_model")
            visited.add(current.lexical_scope_id)
            current = scope_by_id[current.parent_scope_id]
    for symbol in symbols:
        if symbol.type_id is not None and symbol.type_id not in type_by_id:
            raise _fail(ResolutionStatus.CORRUPT, "symbol_type_join_missing", f"symbol names unknown type {symbol.type_id!r}", component="symbol_model")
        if symbol.kind is SymbolKind.FUNCTION:
            function = function_by_id.get(symbol.function_id)
            if function is None or symbol.address != function.range.start:
                raise _fail(ResolutionStatus.CORRUPT, "function_symbol_join_mismatch", "FUNCTION symbol must name and start at its exact FunctionRecord", component="symbol_model")
        elif symbol.kind is SymbolKind.LABEL:
            checked = architecture.validate(symbol.address, Permission.EXECUTE)
            if symbol.address.space != architecture.pc_space or checked.status is not AddressStatus.VALID:
                raise _fail(ResolutionStatus.CORRUPT, "invalid_label_address", "LABEL symbol address must be valid executable pc-space evidence", component="symbol_model")
            if symbol.function_id is not None:
                function = function_by_id.get(symbol.function_id)
                if function is None or not function.range.contains(symbol.address):
                    raise _fail(ResolutionStatus.CORRUPT, "label_function_join_mismatch", "LABEL function must exist and contain its address", component="symbol_model")
            if symbol.lexical_scope_id is not None:
                scope = scope_by_id.get(symbol.lexical_scope_id)
                if scope is None or scope.function_id != symbol.function_id or not scope.pc_range.contains(symbol.address):
                    raise _fail(ResolutionStatus.CORRUPT, "label_scope_join_mismatch", "scoped LABEL must resolve inside its exact function/scope", component="symbol_model")
        elif symbol.kind in {SymbolKind.LOCAL, SymbolKind.CONSTANT} and symbol.function_id is not None:
            function = function_by_id.get(symbol.function_id)
            scope = scope_by_id.get(symbol.lexical_scope_id)
            if function is None or scope is None or scope.function_id != function.function_id:
                raise _fail(ResolutionStatus.CORRUPT, "variable_scope_join_mismatch", "scoped variable must resolve to its exact function and lexical scope", component="symbol_model")
    for instruction in instructions:
        checked = architecture.validate(instruction.address, Permission.EXECUTE)
        if instruction.address.space != architecture.pc_space or checked.status is not AddressStatus.VALID:
            raise _fail(ResolutionStatus.CORRUPT, "invalid_instruction_address", "instruction address must be valid executable pc-space evidence", component="symbol_model")
        units = architecture.units_for_bytes(instruction.address.space, instruction.byte_size)
        if units.status is not AddressStatus.VALID:
            raise _fail(ResolutionStatus.CORRUPT, "invalid_instruction_size", units.diagnostics[0].message, component="symbol_model")
        range_result = architecture.range(instruction.address, units.value, Permission.EXECUTE)
        if range_result.status is not AddressStatus.VALID:
            raise _fail(ResolutionStatus.CORRUPT, "invalid_instruction_range", range_result.diagnostics[0].message, component="symbol_model")
        if instruction.function_id is not None:
            function = function_by_id.get(instruction.function_id)
            if function is None or not function.range.contains_range(range_result.value):
                raise _fail(ResolutionStatus.CORRUPT, "instruction_function_join_mismatch", "instruction function must exist and contain the instruction", component="symbol_model")
        if instruction.source is not None and instruction.source.source not in source_set:
            raise _fail(ResolutionStatus.CORRUPT, "source_identity_join_missing", "instruction SourceRef is outside the accepted manifest", component="symbol_model")
    instruction_ranges: list[tuple[InstructionRecord, HsxAddressRange]] = []
    for instruction in instructions:
        units = architecture.units_for_bytes(instruction.address.space, instruction.byte_size).value
        instruction_ranges.append((instruction, HsxAddressRange(instruction.address, units)))
    instruction_ranges.sort(key=lambda item: (item[1].start.space.value, item[1].start.unsigned_value, item[0].instruction_id))
    for (prior_record, prior), (current_record, current) in zip(instruction_ranges, instruction_ranges[1:]):
        if _range_overlaps(prior, current) and not _same_range(prior, current):
            raise _fail(ResolutionStatus.CORRUPT, "overlapping_instruction_ranges", f"instructions {prior_record.instruction_id!r} and {current_record.instruction_id!r} overlap", component="symbol_model")
    ordered_regions = sorted(regions, key=lambda record: (record.range.start.space.value, record.range.start.unsigned_value, record.region_id))
    for region in ordered_regions:
        descriptor = architecture.space_descriptor(region.range.start.space)
        if descriptor is None or not region.permissions.issubset(descriptor.permissions):
            raise _fail(ResolutionStatus.CORRUPT, "memory_region_permission_mismatch", "memory region permissions exceed its address-space descriptor", component="symbol_model")
        _validate_range(architecture, region.range, f"memory region {region.region_id!r}")
    for prior, current in zip(ordered_regions, ordered_regions[1:]):
        if _range_overlaps(prior.range, current.range):
            raise _fail(ResolutionStatus.CORRUPT, "overlapping_memory_regions", "memory regions must not overlap", component="symbol_model")
    ordered_unwind = sorted(unwind_rows, key=lambda row: (row.pc_range.start.space.value, row.pc_range.start.unsigned_value, row.row_id))
    for row in ordered_unwind:
        if row.abi != abi:
            raise _fail(ResolutionStatus.CORRUPT, "row_abi_mismatch", "unwind row ABI differs from the validated accepted ABI", component="unwind_recipe", row_id=row.row_id)
        diagnostics = RecipeComponentValidator.validate_unwind_row(row, architecture, abi)
        if diagnostics:
            diagnostic = diagnostics[0]
            status = ResolutionStatus.SCHEMA_UNSUPPORTED if diagnostic.code == "limit_exceeded" else ResolutionStatus.CORRUPT
            raise _ArtifactError(status, diagnostic.code, diagnostic.message, component="unwind_recipe", row_id=row.row_id)
    for prior, current in zip(ordered_unwind, ordered_unwind[1:]):
        if _range_overlaps(prior.pc_range, current.pc_range):
            raise _fail(ResolutionStatus.CORRUPT, "overlapping_unwind_rows", "unwind rows must not overlap", component="unwind_recipe")
    location_groups: dict[tuple[str, str | None, str | None], list[LocationRow]] = {}
    for row in location_rows:
        if row.abi != abi:
            raise _fail(ResolutionStatus.CORRUPT, "row_abi_mismatch", "location row ABI differs from the validated accepted ABI", component="location_recipe", row_id=row.row_id)
        variable = symbol_by_id.get(row.symbol_id)
        if variable is None:
            raise _fail(ResolutionStatus.CORRUPT, "location_symbol_join_missing", f"location row names unknown symbol {row.symbol_id!r}", component="location_recipe", row_id=row.row_id)
        diagnostics = RecipeComponentValidator.validate_location_row(row, variable, architecture, abi)
        if diagnostics:
            diagnostic = diagnostics[0]
            status = ResolutionStatus.SCHEMA_UNSUPPORTED if diagnostic.code == "limit_exceeded" else ResolutionStatus.CORRUPT
            raise _ArtifactError(status, diagnostic.code, diagnostic.message, component="location_recipe", row_id=row.row_id)
        if row.declared_type_id is not None:
            declared_type = type_by_id.get(row.declared_type_id)
            if declared_type is None or declared_type.bit_size != row.declared_bit_size or declared_type.byte_order != row.value_byte_order:
                raise _fail(ResolutionStatus.CORRUPT, "location_type_join_mismatch", "location row type width/byte order differs from its exact TypeRecord", component="location_recipe", row_id=row.row_id)
        key = row.symbol_id, row.function_id, row.lexical_scope_id
        location_groups.setdefault(key, []).append(row)
    for rows in location_groups.values():
        rows.sort(key=lambda row: (row.pc_range.start.space.value, row.pc_range.start.unsigned_value, row.row_id))
        for prior, current in zip(rows, rows[1:]):
            if _range_overlaps(prior.pc_range, current.pc_range):
                raise _fail(ResolutionStatus.CORRUPT, "overlapping_location_rows", "location rows for one exact variable identity must not overlap", component="location_recipe")
    location_symbols = {row.symbol_id for row in location_rows}
    for symbol in symbols:
        if symbol.kind in {SymbolKind.GLOBAL, SymbolKind.LOCAL, SymbolKind.CONSTANT}:
            if symbol.symbol_id not in location_symbols:
                raise _fail(ResolutionStatus.CORRUPT, "variable_location_join_missing", f"variable {symbol.symbol_id!r} has no LocationRow", component="location_recipe")
        elif symbol.symbol_id in location_symbols:
            raise _fail(ResolutionStatus.CORRUPT, "address_symbol_has_location_row", "FUNCTION/LABEL symbols must not have LocationRows", component="location_recipe")


def _query_result(binding: ImageDebugBinding, values: tuple[object, ...], *, multiple: ResolutionStatus = ResolutionStatus.CORRUPT, unavailable_code: str, multiple_code: str) -> ResolutionResult:
    if not values:
        return ResolutionResult(ResolutionStatus.UNAVAILABLE, binding, (), (Diagnostic(unavailable_code, "no exact artifact record matched", component="artifact_index"),))
    if len(values) == 1:
        return ResolutionResult(ResolutionStatus.RESOLVED, binding, values, ())
    return ResolutionResult(multiple, binding, values if multiple is ResolutionStatus.AMBIGUOUS else (), (Diagnostic(multiple_code, "more than one exact artifact record matched", component="artifact_index"),))


@dataclass(frozen=True, slots=True, init=False)
class DebugArtifactIndex:
    """One immutable, exact-binding portable debug index."""

    _binding: ImageDebugBinding
    _bundle_identity: ImageDebugBundleIdentityPayload
    _architecture: ArchitectureDescriptor
    _abi: AbiDescriptorRef
    _source_refs: tuple[SourceRef, ...]
    _functions: tuple[FunctionRecord, ...]
    _symbols: tuple[SymbolRecord, ...]
    _types: tuple[TypeRecord, ...]
    _scopes: tuple[LexicalScopeRecord, ...]
    _instructions: tuple[InstructionRecord, ...]
    _regions: tuple[MemoryRegion, ...]
    _unwind_rows: tuple[UnwindRow, ...]
    _location_rows: tuple[LocationRow, ...]

    def __new__(cls):
        raise TypeError("DebugArtifactIndex must be constructed by build()")

    @classmethod
    def _from_validated(cls, binding, bundle_identity, architecture, abi, source_refs, functions, symbols, types, scopes, instructions, regions, unwind_rows, location_rows) -> DebugArtifactIndex:
        index = object.__new__(cls)
        for field_name, value in (
            ("_binding", binding), ("_bundle_identity", bundle_identity), ("_architecture", architecture),
            ("_abi", abi), ("_source_refs", source_refs), ("_functions", functions),
            ("_symbols", symbols), ("_types", types), ("_scopes", scopes),
            ("_instructions", instructions), ("_regions", regions), ("_unwind_rows", unwind_rows),
            ("_location_rows", location_rows),
        ):
            object.__setattr__(index, field_name, value)
        return index

    @classmethod
    def build(cls, binding: ImageDebugBinding, bundle_identity: ImageDebugBundleIdentityPayload, source_manifest: SourceIdentityManifest, architecture: ArchitectureDescriptor, abi: AbiDescriptorRef, components: tuple[DebugComponentInput, ...]) -> ResolutionResult[DebugArtifactIndex]:
        if not isinstance(source_manifest, SourceIdentityManifest):
            raise TypeError("source_manifest must be SourceIdentityManifest")
        if isinstance(components, (str, bytes)) or not isinstance(components, (tuple, list)):
            raise TypeError("components must be a tuple or list")
        component_values = tuple(components)
        if not all(isinstance(component, DebugComponentInput) for component in component_values):
            raise TypeError("components must contain DebugComponentInput values")
        binding_result = DebugBindingValidator.validate(binding, bundle_identity, architecture, abi)
        if binding_result.status is not ResolutionStatus.RESOLVED:
            return binding_result
        try:
            if bundle_identity.source_identity_manifest_ref.algorithm != "sha256" or source_manifest.canonical_digest() != bundle_identity.source_identity_manifest_ref.value:
                raise _fail(ResolutionStatus.ARTIFACT_MISMATCH, "source_manifest_digest_mismatch", "SourceIdentityManifest digest differs from the accepted bundle", component="source_identity_manifest")
            component_ids = tuple(component.component_id for component in component_values)
            if len(set(component_ids)) != len(component_ids):
                raise _fail(ResolutionStatus.CORRUPT, "duplicate_component_id", "component_id values must be unique", component="component")
            unknown_schemas = tuple(component.schema for component in component_values if component.schema not in _COMPONENT_DOMAINS)
            if unknown_schemas:
                raise _fail(ResolutionStatus.SCHEMA_UNSUPPORTED, "unsupported_component_schema", f"unsupported component schemas {unknown_schemas!r}", component="component")
            by_schema: dict[str, list[DebugComponentInput]] = {}
            for component in component_values:
                by_schema.setdefault(component.schema, []).append(component)
            missing = tuple(schema for schema in _COMPONENT_DOMAINS if schema not in by_schema)
            duplicated = tuple(schema for schema, items in by_schema.items() if len(items) != 1)
            if missing or duplicated:
                raise _fail(ResolutionStatus.CORRUPT, "component_cardinality_mismatch", f"mandatory component cardinality mismatch; missing={missing!r}, duplicated={duplicated!r}", component="component")
            expected_digests = {
                _SYMBOL_SCHEMA: bundle_identity.symbol_model.canonical_component_digest,
                _UNWIND_SCHEMA: bundle_identity.unwind_recipe.canonical_component_digest,
                _LOCATION_SCHEMA: bundle_identity.location_recipe.canonical_component_digest,
            }
            payloads: dict[str, Mapping[str, object]] = {}
            for schema, items in by_schema.items():
                component = items[0]
                expected_digest = expected_digests[schema]
                if component.canonical_digest != expected_digest:
                    raise _fail(ResolutionStatus.ARTIFACT_MISMATCH, "component_digest_ref_mismatch", f"component {component.component_id!r} digest differs from the bundle ref", component=component.component_id)
                payload = _load_component_payload(component)
                recomputed = canonical_structured_digest(_COMPONENT_DOMAINS[schema], payload)
                if recomputed != component.canonical_digest:
                    raise _fail(ResolutionStatus.ARTIFACT_MISMATCH, "component_digest_mismatch", f"component {component.component_id!r} content digest differs", component=component.component_id)
                payloads[schema] = payload
            bundle_ref = binding.payload.image_debug_bundle_ref
            source_refs = tuple(SourceRef(bundle_ref, record.logical_id, record.content_digest, record.byte_length) for record in source_manifest.records)
            source_by_id = {source.logical_id: source for source in source_refs}
            functions, symbols, types, scopes, instructions, regions = _parse_symbol_records(payloads[_SYMBOL_SCHEMA], source_by_id)
            unwind_rows = _parse_unwind_records(payloads[_UNWIND_SCHEMA], binding, expected_digests[_UNWIND_SCHEMA])
            location_rows = _parse_location_records(payloads[_LOCATION_SCHEMA], binding, expected_digests[_LOCATION_SCHEMA])
            _validate_portable_records(architecture, abi, source_refs, functions, symbols, types, scopes, instructions, regions, unwind_rows, location_rows)
            index = cls._from_validated(
                binding, bundle_identity, architecture, abi,
                tuple(sorted(source_refs, key=lambda source: source.logical_id.encode("utf-8"))),
                tuple(sorted(functions, key=lambda record: (record.range.start.space.value, record.range.start.unsigned_value, record.function_id))),
                tuple(sorted(symbols, key=lambda record: (_SYMBOL_KIND_RANK[record.kind], record.symbol_id))),
                tuple(sorted(types, key=lambda record: record.type_id)),
                tuple(sorted(scopes, key=lambda record: (record.declaration_order, record.lexical_scope_id))),
                tuple(sorted(instructions, key=lambda record: (record.address.space.value, record.address.unsigned_value, record.instruction_id))),
                tuple(sorted(regions, key=lambda record: (record.range.start.space.value, record.range.start.unsigned_value, record.region_id))),
                tuple(sorted(unwind_rows, key=lambda row: (row.pc_range.start.space.value, row.pc_range.start.unsigned_value, row.row_id))),
                tuple(sorted(location_rows, key=lambda row: (row.pc_range.start.space.value, row.pc_range.start.unsigned_value, row.row_id))),
            )
        except RecipeParseError as exc:
            status = ResolutionStatus.SCHEMA_UNSUPPORTED if exc.status is RecipeEvaluationStatus.UNSUPPORTED else ResolutionStatus.CORRUPT
            return ResolutionResult(status, binding, (), (exc.diagnostic,))
        except _ArtifactError as exc:
            return ResolutionResult(exc.status, binding, (), (exc.diagnostic,))
        except (TypeError, ValueError) as exc:
            return ResolutionResult(ResolutionStatus.CORRUPT, binding, (), (Diagnostic("malformed_component", str(exc), component="artifact"),))
        return ResolutionResult(ResolutionStatus.RESOLVED, binding, (index,), ())

    def binding(self) -> ImageDebugBinding:
        return self._binding

    def bundle_identity(self) -> ImageDebugBundleIdentityPayload:
        return self._bundle_identity

    def source_identities(self) -> tuple[SourceRef, ...]:
        return self._source_refs

    def functions(self) -> tuple[FunctionRecord, ...]:
        return self._functions

    def types(self) -> tuple[TypeRecord, ...]:
        return self._types

    def type_by_id(self, type_id: str) -> ResolutionResult[TypeRecord]:
        if not isinstance(type_id, str) or not type_id:
            raise ValueError("type_id must be a non-empty string")
        values = tuple(record for record in self._types if record.type_id == type_id)
        return _query_result(self._binding, values, unavailable_code="type_unavailable", multiple_code="duplicate_type_identity")

    def lexical_scopes(self, function_id: str, frame_pc: HsxAddress) -> tuple[LexicalScopeRecord, ...]:
        if not isinstance(function_id, str) or not function_id:
            raise ValueError("function_id must be a non-empty string")
        if not isinstance(frame_pc, HsxAddress):
            raise TypeError("frame_pc must be HsxAddress")
        return tuple(scope for scope in self._scopes if scope.function_id == function_id and scope.pc_range.contains(frame_pc))

    def variables_in_scope(self, lexical_scope_id: str, frame_pc: HsxAddress) -> tuple[SymbolRecord, ...]:
        if not isinstance(lexical_scope_id, str) or not lexical_scope_id:
            raise ValueError("lexical_scope_id must be a non-empty string")
        if not isinstance(frame_pc, HsxAddress):
            raise TypeError("frame_pc must be HsxAddress")
        scope = next((record for record in self._scopes if record.lexical_scope_id == lexical_scope_id), None)
        if scope is None or not scope.pc_range.contains(frame_pc):
            return ()
        return tuple(
            symbol for symbol in sorted(self._symbols, key=lambda record: (record.declaration_order, record.symbol_id))
            if symbol.lexical_scope_id == lexical_scope_id and symbol.kind in {SymbolKind.LOCAL, SymbolKind.CONSTANT}
        )

    def global_variables(self) -> tuple[SymbolRecord, ...]:
        return tuple(sorted((symbol for symbol in self._symbols if symbol.kind is SymbolKind.GLOBAL or (symbol.kind is SymbolKind.CONSTANT and symbol.function_id is None and symbol.lexical_scope_id is None)), key=lambda record: (record.declaration_order, record.symbol_id)))

    def symbols_named(self, name: str) -> ResolutionResult[SymbolRecord]:
        if not isinstance(name, str) or not name:
            raise ValueError("name must be a non-empty string")
        values = tuple(record for record in self._symbols if record.name == name)
        return _query_result(self._binding, values, multiple=ResolutionStatus.AMBIGUOUS, unavailable_code="symbol_unavailable", multiple_code="symbol_ambiguous")

    def symbol_by_id(self, symbol_id: str) -> ResolutionResult[SymbolRecord]:
        if not isinstance(symbol_id, str) or not symbol_id:
            raise ValueError("symbol_id must be a non-empty string")
        values = tuple(record for record in self._symbols if record.symbol_id == symbol_id)
        return _query_result(
            self._binding,
            values,
            unavailable_code="symbol_id_unavailable",
            multiple_code="duplicate_symbol_identity",
        )

    def instruction_at(self, address: HsxAddress) -> ResolutionResult[InstructionRecord]:
        if not isinstance(address, HsxAddress):
            raise TypeError("address must be HsxAddress")
        values = tuple(record for record in self._instructions if record.address == address)
        return _query_result(self._binding, values, unavailable_code="instruction_unavailable", multiple_code="instruction_identity_overlap")

    def source_locations(self, source: SourceRef, line: int, column: int | None) -> ResolutionResult[InstructionRecord]:
        if not isinstance(source, SourceRef):
            raise TypeError("source must be SourceRef")
        if isinstance(line, bool) or not isinstance(line, int) or line < 1:
            raise ValueError("line must be an integer >= 1")
        if column is not None and (isinstance(column, bool) or not isinstance(column, int) or column < 1):
            raise ValueError("column must be an integer >= 1 or None")
        values = tuple(record for record in self._instructions if record.source is not None and record.source.source == source and record.source.line == line and (column is None or record.source.column == column))
        if not values:
            return ResolutionResult(ResolutionStatus.UNAVAILABLE, self._binding, (), (Diagnostic("source_location_unavailable", "no executable source location matched", component="artifact_index"),))
        return ResolutionResult(ResolutionStatus.RESOLVED, self._binding, values, ())

    def memory_regions(self) -> tuple[MemoryRegion, ...]:
        return self._regions

    def unwind_rows(self, pc: HsxAddress, function_id: str | None) -> ResolutionResult[UnwindRow]:
        if not isinstance(pc, HsxAddress):
            raise TypeError("pc must be HsxAddress")
        if function_id is not None and (not isinstance(function_id, str) or not function_id):
            raise ValueError("function_id must be a non-empty string or None")
        if function_id is not None:
            functions = tuple(function for function in self._functions if function.function_id == function_id and function.range.contains(pc))
            if len(functions) != 1:
                return _query_result(self._binding, (), unavailable_code="unwind_function_unavailable", multiple_code="unwind_function_overlap")
        values = tuple(row for row in self._unwind_rows if row.pc_range.contains(pc))
        return _query_result(self._binding, values, unavailable_code="unwind_row_unavailable", multiple_code="unwind_row_overlap")

    def location_rows(self, symbol_id: str, function_id: str | None, lexical_scope_id: str | None, frame_pc: HsxAddress) -> ResolutionResult[LocationRow]:
        if not isinstance(symbol_id, str) or not symbol_id:
            raise ValueError("symbol_id must be a non-empty string")
        for value, field_name in ((function_id, "function_id"), (lexical_scope_id, "lexical_scope_id")):
            if value is not None and (not isinstance(value, str) or not value):
                raise ValueError(f"{field_name} must be a non-empty string or None")
        if not isinstance(frame_pc, HsxAddress):
            raise TypeError("frame_pc must be HsxAddress")
        values = tuple(row for row in self._location_rows if row.symbol_id == symbol_id and row.function_id == function_id and row.lexical_scope_id == lexical_scope_id and row.pc_range.contains(frame_pc))
        return _query_result(self._binding, values, unavailable_code="location_row_unavailable", multiple_code="location_row_overlap")


__all__ = ["DebugArtifactIndex"]
