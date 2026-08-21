"""Pure immutable portable debug metadata records.

Parsing, indexes, recipe rows/evaluation, filesystem policy, and target reads deliberately do
not belong here.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .addresses import ByteOrder, HsxAddress, HsxAddressRange, Permission
from .identity import (
    CanonicalUInt64,
    ContentDigest,
    SourceRef,
    canonical_structured_digest,
    validate_source_logical_id,
)


def _require_nonempty(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field_name} must be a non-empty string")


def _require_optional_nonempty(value: str | None, field_name: str) -> None:
    if value is not None:
        _require_nonempty(value, field_name)


def _require_int(value: int, field_name: str, *, minimum: int = 0) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ValueError(f"{field_name} must be an integer >= {minimum}")


def _tuple(value: object, field_name: str) -> tuple:
    if isinstance(value, (str, bytes)) or not isinstance(value, (tuple, list)):
        raise TypeError(f"{field_name} must be a tuple or list")
    return tuple(value)


class SymbolKind(str, Enum):
    FUNCTION = "function"
    LABEL = "label"
    GLOBAL = "global"
    LOCAL = "local"
    CONSTANT = "constant"


class TypeKind(str, Enum):
    INTEGER = "integer"
    FLOAT = "float"
    POINTER = "pointer"
    ARRAY = "array"
    STRUCT = "struct"
    UNION = "union"
    OPAQUE = "opaque"


class InstructionClassification(str, Enum):
    USER = "user"
    COMPILER_GENERATED = "compiler_generated"
    UNMAPPED = "unmapped"


@dataclass(frozen=True, slots=True)
class DebugComponentInput:
    component_id: str
    schema: str
    canonical_digest: str
    content: bytes

    def __post_init__(self) -> None:
        _require_nonempty(self.component_id, "component_id")
        _require_nonempty(self.schema, "schema")
        ContentDigest("sha256", self.canonical_digest)
        if not isinstance(self.content, bytes):
            raise TypeError("content must be immutable bytes")


@dataclass(frozen=True, slots=True)
class SourceIdentityRecord:
    logical_id: str
    content_digest: ContentDigest
    byte_length: CanonicalUInt64
    media_type_or_language: str | None = None

    def __post_init__(self) -> None:
        validate_source_logical_id(self.logical_id)
        if not isinstance(self.content_digest, ContentDigest):
            raise TypeError("content_digest must be ContentDigest")
        if not isinstance(self.byte_length, CanonicalUInt64):
            raise TypeError("byte_length must be CanonicalUInt64")
        _require_optional_nonempty(self.media_type_or_language, "media_type_or_language")

    def canonical_payload(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "logical_id": self.logical_id,
            "content_digest": self.content_digest.canonical_payload(),
            "byte_length": self.byte_length.canonical(),
        }
        if self.media_type_or_language is not None:
            payload["media_type_or_language"] = self.media_type_or_language
        return payload


@dataclass(frozen=True, slots=True)
class SourceIdentityManifest:
    schema: str
    records: tuple[SourceIdentityRecord, ...]

    def __post_init__(self) -> None:
        if self.schema != "hsx.source-identity-manifest/1":
            raise ValueError("schema must be 'hsx.source-identity-manifest/1'")
        records = _tuple(self.records, "records")
        if not all(isinstance(item, SourceIdentityRecord) for item in records):
            raise TypeError("records must contain SourceIdentityRecord values")
        ordered = tuple(sorted(records, key=lambda item: item.logical_id.encode("utf-8")))
        ids = tuple(item.logical_id for item in ordered)
        if len(set(ids)) != len(ids):
            raise ValueError("logical IDs must be unique")
        object.__setattr__(self, "records", ordered)

    def canonical_payload(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "records": tuple(item.canonical_payload() for item in self.records),
        }

    def canonical_digest(self) -> str:
        return canonical_structured_digest(self.schema, self.canonical_payload())


@dataclass(frozen=True, slots=True)
class SourceLocation:
    source: SourceRef
    line: int
    column: int | None = None
    discriminator: int | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.source, SourceRef):
            raise TypeError("source must be SourceRef")
        _require_int(self.line, "line", minimum=1)
        if self.column is not None:
            _require_int(self.column, "column", minimum=1)
        if self.discriminator is not None:
            _require_int(self.discriminator, "discriminator")


@dataclass(frozen=True, slots=True)
class FunctionRecord:
    function_id: str
    name: str
    linkage_name: str | None
    range: HsxAddressRange
    definition: SourceLocation | None

    def __post_init__(self) -> None:
        _require_nonempty(self.function_id, "function_id")
        _require_nonempty(self.name, "name")
        _require_optional_nonempty(self.linkage_name, "linkage_name")
        if not isinstance(self.range, HsxAddressRange) or self.range.length_units < 1:
            raise ValueError("range must be a non-empty HsxAddressRange")
        if self.definition is not None and not isinstance(self.definition, SourceLocation):
            raise TypeError("definition must be SourceLocation or None")


@dataclass(frozen=True, slots=True)
class SymbolRecord:
    symbol_id: str
    name: str
    kind: SymbolKind
    address: HsxAddress | None
    byte_size: int
    function_id: str | None
    lexical_scope_id: str | None
    type_id: str | None
    declaration_order: int

    def __post_init__(self) -> None:
        _require_nonempty(self.symbol_id, "symbol_id")
        _require_nonempty(self.name, "name")
        if not isinstance(self.kind, SymbolKind):
            raise TypeError("kind must be SymbolKind")
        if self.address is not None and not isinstance(self.address, HsxAddress):
            raise TypeError("address must be HsxAddress or None")
        _require_int(self.byte_size, "byte_size")
        _require_optional_nonempty(self.function_id, "function_id")
        _require_optional_nonempty(self.lexical_scope_id, "lexical_scope_id")
        _require_optional_nonempty(self.type_id, "type_id")
        _require_int(self.declaration_order, "declaration_order")
        if self.kind is SymbolKind.FUNCTION:
            if self.address is None or self.function_id is None or self.lexical_scope_id is not None:
                raise ValueError("FUNCTION requires address/function_id and no lexical_scope_id")
        elif self.kind is SymbolKind.LABEL:
            if self.address is None:
                raise ValueError("LABEL requires address")
            if self.lexical_scope_id is not None and self.function_id is None:
                raise ValueError("a scoped LABEL requires function_id")
        elif self.kind is SymbolKind.LOCAL:
            if self.address is not None or self.function_id is None or self.lexical_scope_id is None:
                raise ValueError("LOCAL is addressless and requires function/scope IDs")
        elif self.kind is SymbolKind.GLOBAL:
            if self.address is not None or self.function_id is not None or self.lexical_scope_id is not None:
                raise ValueError("GLOBAL is addressless and has no function/scope IDs")
        elif self.kind is SymbolKind.CONSTANT:
            if self.address is not None:
                raise ValueError("CONSTANT is addressless")
            if (self.function_id is None) != (self.lexical_scope_id is None):
                raise ValueError("CONSTANT function/scope IDs must both be present or absent")


@dataclass(frozen=True, slots=True)
class TypeMember:
    name: str
    type_id: str
    bit_offset: int
    bit_size: int

    def __post_init__(self) -> None:
        _require_nonempty(self.name, "name")
        _require_nonempty(self.type_id, "type_id")
        _require_int(self.bit_offset, "bit_offset")
        _require_int(self.bit_size, "bit_size", minimum=1)


@dataclass(frozen=True, slots=True)
class TypeRecord:
    type_id: str
    name: str
    kind: TypeKind
    bit_size: int
    byte_order: ByteOrder
    members: tuple[TypeMember, ...] = ()

    def __post_init__(self) -> None:
        _require_nonempty(self.type_id, "type_id")
        _require_nonempty(self.name, "name")
        if not isinstance(self.kind, TypeKind):
            raise TypeError("kind must be TypeKind")
        _require_int(self.bit_size, "bit_size", minimum=1)
        if not isinstance(self.byte_order, ByteOrder):
            raise TypeError("byte_order must be ByteOrder")
        members = _tuple(self.members, "members")
        if not all(isinstance(item, TypeMember) for item in members):
            raise TypeError("members must contain TypeMember values")
        if self.kind not in {TypeKind.STRUCT, TypeKind.UNION} and members:
            raise ValueError("only STRUCT/UNION may contain members")
        names = tuple(item.name for item in members)
        if len(set(names)) != len(names):
            raise ValueError("member names must be unique")
        for member in members:
            end = member.bit_offset + member.bit_size
            if end > self.bit_size:
                raise ValueError("member exceeds enclosing bit_size")
        if self.kind is TypeKind.STRUCT:
            intervals = sorted(
                (member.bit_offset, member.bit_offset + member.bit_size) for member in members
            )
            if any(current[0] < prior[1] for prior, current in zip(intervals, intervals[1:])):
                raise ValueError("STRUCT members must not overlap")
        object.__setattr__(self, "members", members)


@dataclass(frozen=True, slots=True)
class LexicalScopeRecord:
    lexical_scope_id: str
    function_id: str
    parent_scope_id: str | None
    pc_range: HsxAddressRange
    declaration_order: int

    def __post_init__(self) -> None:
        _require_nonempty(self.lexical_scope_id, "lexical_scope_id")
        _require_nonempty(self.function_id, "function_id")
        _require_optional_nonempty(self.parent_scope_id, "parent_scope_id")
        if self.parent_scope_id == self.lexical_scope_id:
            raise ValueError("a lexical scope cannot parent itself")
        if not isinstance(self.pc_range, HsxAddressRange) or self.pc_range.length_units < 1:
            raise ValueError("pc_range must be a non-empty HsxAddressRange")
        _require_int(self.declaration_order, "declaration_order")


@dataclass(frozen=True, slots=True)
class InstructionRecord:
    instruction_id: str
    address: HsxAddress
    byte_size: int
    encoded_word: int | None
    function_id: str | None
    source: SourceLocation | None
    classification: InstructionClassification

    def __post_init__(self) -> None:
        _require_nonempty(self.instruction_id, "instruction_id")
        if not isinstance(self.address, HsxAddress):
            raise TypeError("address must be HsxAddress")
        _require_int(self.byte_size, "byte_size", minimum=1)
        if self.encoded_word is not None:
            _require_int(self.encoded_word, "encoded_word")
            if self.encoded_word >= 1 << (self.byte_size * 8):
                raise ValueError("encoded_word does not fit byte_size")
        _require_optional_nonempty(self.function_id, "function_id")
        if self.source is not None and not isinstance(self.source, SourceLocation):
            raise TypeError("source must be SourceLocation or None")
        if not isinstance(self.classification, InstructionClassification):
            raise TypeError("classification must be InstructionClassification")


@dataclass(frozen=True, slots=True)
class MemoryRegion:
    region_id: str
    name: str
    kind: str
    range: HsxAddressRange
    permissions: frozenset[Permission]

    def __post_init__(self) -> None:
        _require_nonempty(self.region_id, "region_id")
        _require_nonempty(self.name, "name")
        _require_nonempty(self.kind, "kind")
        if not isinstance(self.range, HsxAddressRange) or self.range.length_units < 1:
            raise ValueError("range must be a non-empty HsxAddressRange")
        if isinstance(self.permissions, str) or not isinstance(
            self.permissions, (set, frozenset, list, tuple)
        ):
            raise TypeError("permissions must be a collection")
        permissions = frozenset(self.permissions)
        if not all(isinstance(item, Permission) for item in permissions):
            raise TypeError("permissions must contain Permission values")
        object.__setattr__(self, "permissions", permissions)


__all__ = [
    "DebugComponentInput",
    "FunctionRecord",
    "InstructionClassification",
    "InstructionRecord",
    "LexicalScopeRecord",
    "MemoryRegion",
    "SourceIdentityManifest",
    "SourceIdentityRecord",
    "SourceLocation",
    "SymbolKind",
    "SymbolRecord",
    "TypeKind",
    "TypeMember",
    "TypeRecord",
]
