"""Explicit degraded adapter for classified ``hsx.python-debug-legacy/1`` symbols.

The adapter is intentionally separate from :mod:`hsx_debugger.artifacts`.  It verifies the
legacy sidecar version and supplied HXE CRC evidence, but it never manufactures a portable
bundle, binding, source identity, unwind row, or location row.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import json
from typing import Generic, Mapping, TypeVar

from .addresses import (
    AddressSpaceId,
    ArchitectureDescriptor,
    HsxAddress,
    HsxAddressRange,
    Permission,
)
from .identity import ContentDigest
from .metadata import MemoryRegion, SymbolKind, SymbolRecord
from .results import (
    AddressStatus,
    Diagnostic,
    ResolutionStatus,
    _deep_freeze,
    _register_contract_enums,
)


T = TypeVar("T")


class LegacyIdentityStatus(str, Enum):
    LEGACY_UNVERIFIED = "legacy_unverified"


_register_contract_enums(LegacyIdentityStatus)


@dataclass(frozen=True, slots=True)
class LegacyArtifactProvenance:
    profile: str
    identity_status: LegacyIdentityStatus
    sym_content_digest: ContentDigest
    hxe_crc32: int

    def __post_init__(self) -> None:
        if self.profile != "hsx.python-debug-legacy/1":
            raise ValueError("profile must be 'hsx.python-debug-legacy/1'")
        if self.identity_status is not LegacyIdentityStatus.LEGACY_UNVERIFIED:
            raise ValueError("identity_status must be LEGACY_UNVERIFIED")
        if not isinstance(self.sym_content_digest, ContentDigest):
            raise TypeError("sym_content_digest must be ContentDigest")
        if (
            isinstance(self.hxe_crc32, bool)
            or not isinstance(self.hxe_crc32, int)
            or not 0 <= self.hxe_crc32 <= 0xFFFFFFFF
        ):
            raise ValueError("hxe_crc32 must be an integer in 0..0xffffffff")


@dataclass(frozen=True, slots=True)
class LegacySourceSpelling:
    file: str
    directory: str | None

    def __post_init__(self) -> None:
        if not isinstance(self.file, str) or not self.file:
            raise ValueError("file must be a non-empty exact string")
        if self.directory is not None and (
            not isinstance(self.directory, str) or not self.directory
        ):
            raise ValueError("directory must be a non-empty exact string or None")


@dataclass(frozen=True, slots=True)
class LegacyFunctionRecord:
    function_id: str
    name: str
    linkage_name: str | None
    range: HsxAddressRange
    definition_spelling: LegacySourceSpelling | None
    definition_line: int | None

    def __post_init__(self) -> None:
        if not isinstance(self.function_id, str) or not self.function_id:
            raise ValueError("function_id must be a non-empty string")
        if not isinstance(self.name, str) or not self.name:
            raise ValueError("name must be a non-empty string")
        if self.linkage_name is not None and (
            not isinstance(self.linkage_name, str) or not self.linkage_name
        ):
            raise ValueError("linkage_name must be a non-empty string or None")
        if not isinstance(self.range, HsxAddressRange) or self.range.length_units < 1:
            raise ValueError("range must be a non-empty HsxAddressRange")
        if self.definition_spelling is not None and not isinstance(
            self.definition_spelling, LegacySourceSpelling
        ):
            raise TypeError("definition_spelling must be LegacySourceSpelling or None")
        if self.definition_line is not None and (
            isinstance(self.definition_line, bool)
            or not isinstance(self.definition_line, int)
            or self.definition_line < 1
        ):
            raise ValueError("definition_line must be an integer >= 1 or None")
        if (self.definition_spelling is None) != (self.definition_line is None):
            raise ValueError("definition spelling and line must both be present or absent")


@dataclass(frozen=True, slots=True)
class LegacyInstructionRecord:
    instruction_id: str
    address: HsxAddress
    byte_size: int
    function_id: str | None
    source_spelling: LegacySourceSpelling | None
    line: int | None
    column: int | None

    def __post_init__(self) -> None:
        if not isinstance(self.instruction_id, str) or not self.instruction_id:
            raise ValueError("instruction_id must be a non-empty string")
        if not isinstance(self.address, HsxAddress):
            raise TypeError("address must be HsxAddress")
        if isinstance(self.byte_size, bool) or not isinstance(self.byte_size, int) or self.byte_size < 1:
            raise ValueError("byte_size must be an integer >= 1")
        if self.function_id is not None and (
            not isinstance(self.function_id, str) or not self.function_id
        ):
            raise ValueError("function_id must be a non-empty string or None")
        if self.source_spelling is not None and not isinstance(
            self.source_spelling, LegacySourceSpelling
        ):
            raise TypeError("source_spelling must be LegacySourceSpelling or None")
        if self.line is not None and (
            isinstance(self.line, bool) or not isinstance(self.line, int) or self.line < 1
        ):
            raise ValueError("line must be an integer >= 1 or None")
        if self.column is not None and (
            isinstance(self.column, bool) or not isinstance(self.column, int) or self.column < 0
        ):
            raise ValueError("column must be an integer >= 0 or None")
        if self.source_spelling is None and (self.line is not None or self.column is not None):
            raise ValueError("source coordinates require LegacySourceSpelling")
        if self.source_spelling is not None and self.line is None:
            raise ValueError("source spelling requires a source line")


@dataclass(frozen=True, slots=True)
class LegacyResolutionResult(Generic[T]):
    status: ResolutionStatus
    provenance: LegacyArtifactProvenance
    values: tuple[T, ...]
    diagnostics: tuple[Diagnostic, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.status, ResolutionStatus):
            raise TypeError("status must be ResolutionStatus")
        if not isinstance(self.provenance, LegacyArtifactProvenance):
            raise TypeError("provenance must be LegacyArtifactProvenance")
        if isinstance(self.values, (str, bytes)) or not isinstance(self.values, (tuple, list)):
            raise TypeError("values must be a tuple or list")
        if isinstance(self.diagnostics, (str, bytes)) or not isinstance(
            self.diagnostics, (tuple, list)
        ):
            raise TypeError("diagnostics must be a tuple or list")
        values = tuple(
            _deep_freeze(value, f"values[{index}]")
            for index, value in enumerate(self.values)
        )
        diagnostics = tuple(self.diagnostics)
        if not all(isinstance(item, Diagnostic) for item in diagnostics):
            raise TypeError("diagnostics must contain Diagnostic values")
        object.__setattr__(self, "values", values)
        object.__setattr__(self, "diagnostics", diagnostics)
        if self.status is ResolutionStatus.RESOLVED:
            if not values:
                raise ValueError("RESOLVED requires one or more values")
        elif self.status is ResolutionStatus.AMBIGUOUS:
            if len(values) < 2:
                raise ValueError("AMBIGUOUS requires at least two values")
        elif values:
            raise ValueError("non-value statuses require no values")


class _LegacyError(ValueError):
    def __init__(self, status: ResolutionStatus, code: str, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.diagnostic = Diagnostic(code, message, component="legacy_symbols")


def _legacy_error(status: ResolutionStatus, code: str, message: str) -> _LegacyError:
    return _LegacyError(status, code, message)


def _mapping(value: object, field_name: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise _legacy_error(
            ResolutionStatus.CORRUPT,
            "malformed_legacy_record",
            f"{field_name} must be an object",
        )
    return value


def _fields(
    value: object,
    required: frozenset[str],
    optional: frozenset[str],
    field_name: str,
) -> Mapping[str, object]:
    item = _mapping(value, field_name)
    keys = frozenset(item.keys())
    if not all(isinstance(key, str) for key in keys):
        raise _legacy_error(
            ResolutionStatus.CORRUPT,
            "malformed_legacy_field",
            f"{field_name} contains a non-string field",
        )
    unknown = keys - required - optional
    if unknown:
        raise _legacy_error(
            ResolutionStatus.SCHEMA_UNSUPPORTED,
            "unsupported_legacy_field",
            f"{field_name} contains unsupported fields {tuple(sorted(unknown))!r}",
        )
    missing = required - keys
    if missing:
        raise _legacy_error(
            ResolutionStatus.CORRUPT,
            "missing_legacy_field",
            f"{field_name} is missing fields {tuple(sorted(missing))!r}",
        )
    return item


def _list(value: object, field_name: str) -> tuple[object, ...]:
    if not isinstance(value, list):
        raise _legacy_error(
            ResolutionStatus.CORRUPT,
            "malformed_legacy_field",
            f"{field_name} must be an array",
        )
    return tuple(value)


def _text(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value:
        raise _legacy_error(
            ResolutionStatus.CORRUPT,
            "malformed_legacy_field",
            f"{field_name} must be a non-empty string",
        )
    return value


def _integer(value: object, field_name: str, *, minimum: int = 0) -> int:
    if isinstance(value, bool):
        raise _legacy_error(
            ResolutionStatus.CORRUPT,
            "malformed_legacy_integer",
            f"{field_name} must be an integer >= {minimum}",
        )
    if isinstance(value, str):
        try:
            parsed = int(value, 0)
        except ValueError as exc:
            raise _legacy_error(
                ResolutionStatus.CORRUPT,
                "malformed_legacy_integer",
                f"{field_name} is not an accepted legacy integer",
            ) from exc
    elif isinstance(value, int):
        parsed = value
    else:
        raise _legacy_error(
            ResolutionStatus.CORRUPT,
            "malformed_legacy_integer",
            f"{field_name} must be an integer",
        )
    if parsed < minimum:
        raise _legacy_error(
            ResolutionStatus.CORRUPT,
            "malformed_legacy_integer",
            f"{field_name} must be >= {minimum}",
        )
    return parsed


def _optional_integer(value: object, field_name: str, *, minimum: int = 0) -> int | None:
    if value is None:
        return None
    return _integer(value, field_name, minimum=minimum)


def _provenance(sym_bytes: bytes, hxe_crc32: int) -> LegacyArtifactProvenance:
    return LegacyArtifactProvenance(
        "hsx.python-debug-legacy/1",
        LegacyIdentityStatus.LEGACY_UNVERIFIED,
        ContentDigest("sha256", hashlib.sha256(sym_bytes).hexdigest()),
        hxe_crc32,
    )


def _address(
    architecture: ArchitectureDescriptor,
    space: AddressSpaceId,
    raw: object,
    field_name: str,
    permission: Permission,
) -> HsxAddress:
    address = HsxAddress(space, _integer(raw, field_name))
    checked = architecture.validate(address, permission)
    if checked.status is not AddressStatus.VALID:
        raise _legacy_error(
            ResolutionStatus.CORRUPT,
            "legacy_address_invalid",
            f"{field_name}: {checked.status.name}/{checked.diagnostics[0].code}",
        )
    return address


def _range_from_bytes(
    architecture: ArchitectureDescriptor,
    start: HsxAddress,
    byte_size: int,
    field_name: str,
    permission: Permission,
) -> HsxAddressRange:
    units = architecture.units_for_bytes(start.space, byte_size)
    if units.status is not AddressStatus.VALID:
        raise _legacy_error(
            ResolutionStatus.CORRUPT,
            "legacy_unit_conversion_invalid",
            f"{field_name}: {units.status.name}/{units.diagnostics[0].code}",
        )
    checked = architecture.range(start, units.value, permission)
    if checked.status is not AddressStatus.VALID or checked.value.length_units < 1:
        code = checked.diagnostics[0].code if checked.diagnostics else "empty_range"
        raise _legacy_error(
            ResolutionStatus.CORRUPT,
            "legacy_range_invalid",
            f"{field_name}: {checked.status.name}/{code}",
        )
    return checked.value


def _legacy_query(
    provenance: LegacyArtifactProvenance,
    values: tuple[T, ...],
    *,
    complete_set: bool = False,
    unavailable_code: str,
    multiple_code: str,
) -> LegacyResolutionResult[T]:
    if not values:
        return LegacyResolutionResult(
            ResolutionStatus.UNAVAILABLE,
            provenance,
            (),
            (Diagnostic(unavailable_code, "no exact legacy record matched", component="legacy_symbols"),),
        )
    if complete_set or len(values) == 1:
        return LegacyResolutionResult(ResolutionStatus.RESOLVED, provenance, values, ())
    return LegacyResolutionResult(
        ResolutionStatus.AMBIGUOUS,
        provenance,
        values,
        (Diagnostic(multiple_code, "multiple exact legacy candidates matched", component="legacy_symbols"),),
    )


@dataclass(frozen=True, slots=True, init=False)
class LegacyDebugArtifactIndex:
    _provenance: LegacyArtifactProvenance
    _functions: tuple[LegacyFunctionRecord, ...]
    _symbols: tuple[SymbolRecord, ...]
    _instructions: tuple[LegacyInstructionRecord, ...]
    _regions: tuple[MemoryRegion, ...]

    def __new__(cls):
        raise TypeError("LegacyDebugArtifactIndex must be constructed by LegacySymbolAdapter.build()")

    @classmethod
    def _from_validated(
        cls,
        provenance: LegacyArtifactProvenance,
        functions: tuple[LegacyFunctionRecord, ...],
        symbols: tuple[SymbolRecord, ...],
        instructions: tuple[LegacyInstructionRecord, ...],
        regions: tuple[MemoryRegion, ...],
    ) -> LegacyDebugArtifactIndex:
        index = object.__new__(cls)
        for field_name, value in (
            ("_provenance", provenance),
            ("_functions", functions),
            ("_symbols", symbols),
            ("_instructions", instructions),
            ("_regions", regions),
        ):
            object.__setattr__(index, field_name, value)
        return index

    def provenance(self) -> LegacyArtifactProvenance:
        return self._provenance

    def functions(self) -> tuple[LegacyFunctionRecord, ...]:
        return self._functions

    def symbols_named(self, name: str) -> LegacyResolutionResult[SymbolRecord]:
        if not isinstance(name, str) or not name:
            raise ValueError("name must be a non-empty exact string")
        values = tuple(record for record in self._symbols if record.name == name)
        return _legacy_query(
            self._provenance,
            values,
            unavailable_code="legacy_symbol_unavailable",
            multiple_code="legacy_symbol_ambiguous",
        )

    def instruction_at(
        self, address: HsxAddress
    ) -> LegacyResolutionResult[LegacyInstructionRecord]:
        if not isinstance(address, HsxAddress):
            raise TypeError("address must be HsxAddress")
        values = tuple(record for record in self._instructions if record.address == address)
        if len(values) > 1:
            return LegacyResolutionResult(
                ResolutionStatus.CORRUPT,
                self._provenance,
                (),
                (Diagnostic("legacy_instruction_overlap", "multiple legacy instructions share one address", component="legacy_symbols"),),
            )
        return _legacy_query(
            self._provenance,
            values,
            unavailable_code="legacy_instruction_unavailable",
            multiple_code="legacy_instruction_overlap",
        )

    def source_spelling_locations(
        self,
        spelling: LegacySourceSpelling,
        line: int,
        column: int | None,
    ) -> LegacyResolutionResult[LegacyInstructionRecord]:
        if not isinstance(spelling, LegacySourceSpelling):
            raise TypeError("spelling must be LegacySourceSpelling")
        if isinstance(line, bool) or not isinstance(line, int) or line < 1:
            raise ValueError("line must be an integer >= 1")
        if column is not None and (
            isinstance(column, bool) or not isinstance(column, int) or column < 0
        ):
            raise ValueError("column must be an integer >= 0 or None")
        values = tuple(
            record
            for record in self._instructions
            if record.source_spelling == spelling
            and record.line == line
            and (column is None or record.column == column)
        )
        return _legacy_query(
            self._provenance,
            values,
            complete_set=True,
            unavailable_code="legacy_source_location_unavailable",
            multiple_code="legacy_source_location_ambiguous",
        )

    def memory_regions(self) -> tuple[MemoryRegion, ...]:
        return self._regions


class LegacySymbolAdapter:
    """Strict version-1 sidecar conversion with explicit descriptor/CRC evidence."""

    @staticmethod
    def build(
        sym_bytes: bytes,
        expected_hxe_crc32: int,
        architecture: ArchitectureDescriptor,
    ) -> LegacyResolutionResult[LegacyDebugArtifactIndex]:
        if not isinstance(sym_bytes, bytes):
            raise TypeError("sym_bytes must be immutable bytes")
        if (
            isinstance(expected_hxe_crc32, bool)
            or not isinstance(expected_hxe_crc32, int)
            or not 0 <= expected_hxe_crc32 <= 0xFFFFFFFF
        ):
            raise ValueError("expected_hxe_crc32 must be an integer in 0..0xffffffff")
        if not isinstance(architecture, ArchitectureDescriptor):
            raise TypeError("architecture must be ArchitectureDescriptor")
        provenance = _provenance(sym_bytes, expected_hxe_crc32)
        try:
            try:
                document = json.loads(sym_bytes.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise _legacy_error(
                    ResolutionStatus.CORRUPT,
                    "malformed_legacy_sym",
                    "legacy .sym content is not valid UTF-8 JSON",
                ) from exc
            root = _fields(
                document,
                frozenset({"version", "hxe_crc", "symbols", "instructions", "memory_regions"}),
                frozenset({"hxe_path"}),
                "legacy .sym document",
            )
            version = _integer(root["version"], "version")
            if version != 1:
                raise _legacy_error(
                    ResolutionStatus.SCHEMA_UNSUPPORTED,
                    "unsupported_legacy_sym_version",
                    f"legacy .sym version {version!r} is unsupported",
                )
            hxe_crc = _integer(root["hxe_crc"], "hxe_crc")
            if hxe_crc > 0xFFFFFFFF:
                raise _legacy_error(
                    ResolutionStatus.CORRUPT,
                    "malformed_legacy_hxe_crc",
                    "legacy hxe_crc must fit uint32",
                )
            provenance = _provenance(sym_bytes, hxe_crc)
            if hxe_crc != expected_hxe_crc32:
                raise _legacy_error(
                    ResolutionStatus.ARTIFACT_MISMATCH,
                    "legacy_hxe_crc_mismatch",
                    "legacy .sym hxe_crc differs from supplied HXE evidence",
                )

            symbols_block = _fields(
                root["symbols"],
                frozenset(),
                frozenset({"functions", "variables", "globals", "locals", "labels"}),
                "symbols",
            )
            raw_functions = _list(symbols_block.get("functions", []), "symbols.functions")
            functions: list[LegacyFunctionRecord] = []
            portable_symbols: list[SymbolRecord] = []
            function_ids_by_name: dict[str, list[str]] = {}
            declaration_order = 0
            for ordinal, raw_function in enumerate(raw_functions):
                item = _fields(
                    raw_function,
                    frozenset({"name", "address", "size"}),
                    frozenset({"linkage_name", "file", "directory", "line"}),
                    "function",
                )
                name = _text(item["name"], "function.name")
                function_id = f"legacy:function:{ordinal}:{name}"
                address = _address(
                    architecture,
                    architecture.pc_space,
                    item["address"],
                    "function.address",
                    Permission.EXECUTE,
                )
                byte_size = _integer(item["size"], "function.size", minimum=1)
                pc_range = _range_from_bytes(
                    architecture,
                    address,
                    byte_size,
                    "function.range",
                    Permission.EXECUTE,
                )
                has_source = "file" in item or "line" in item or "directory" in item
                if has_source and not ("file" in item and "line" in item):
                    raise _legacy_error(
                        ResolutionStatus.CORRUPT,
                        "malformed_legacy_source",
                        "legacy function source requires file and line",
                    )
                spelling = (
                    LegacySourceSpelling(
                        _text(item["file"], "function.file"),
                        _text(item["directory"], "function.directory")
                        if "directory" in item
                        else None,
                    )
                    if has_source
                    else None
                )
                line = _integer(item["line"], "function.line", minimum=1) if has_source else None
                functions.append(
                    LegacyFunctionRecord(
                        function_id,
                        name,
                        _text(item["linkage_name"], "function.linkage_name")
                        if "linkage_name" in item
                        else None,
                        pc_range,
                        spelling,
                        line,
                    )
                )
                portable_symbols.append(
                    SymbolRecord(
                        f"legacy:symbol:function:{ordinal}",
                        name,
                        SymbolKind.FUNCTION,
                        address,
                        byte_size,
                        function_id,
                        None,
                        None,
                        declaration_order,
                    )
                )
                declaration_order += 1
                function_ids_by_name.setdefault(name, []).append(function_id)

            labels = _mapping(symbols_block.get("labels", {}), "symbols.labels")
            for address_spelling, raw_names in labels.items():
                if not isinstance(address_spelling, str):
                    raise _legacy_error(
                        ResolutionStatus.CORRUPT,
                        "malformed_legacy_label_address",
                        "legacy label addresses must be strings",
                    )
                address = _address(
                    architecture,
                    architecture.pc_space,
                    address_spelling,
                    "label.address",
                    Permission.EXECUTE,
                )
                for ordinal, raw_name in enumerate(_list(raw_names, "label names")):
                    name = _text(raw_name, "label.name")
                    portable_symbols.append(
                        SymbolRecord(
                            f"legacy:symbol:label:{address_spelling}:{ordinal}",
                            name,
                            SymbolKind.LABEL,
                            address,
                            0,
                            None,
                            None,
                            None,
                            declaration_order,
                        )
                    )
                    declaration_order += 1

            globals_key = "globals" if "globals" in symbols_block else "variables"
            raw_globals = _list(symbols_block.get(globals_key, []), f"symbols.{globals_key}")
            for ordinal, raw_global in enumerate(raw_globals):
                item = _fields(
                    raw_global,
                    frozenset({"name"}),
                    frozenset({"address", "value", "size", "type"}),
                    "global variable",
                )
                if ("address" in item) == ("value" in item):
                    raise _legacy_error(
                        ResolutionStatus.CORRUPT,
                        "malformed_legacy_global_location",
                        "legacy global requires exactly one address or value",
                    )
                raw_address = item["address"] if "address" in item else item["value"]
                _address(
                    architecture,
                    architecture.sp_space,
                    raw_address,
                    "global.address",
                    Permission.READ,
                )
                portable_symbols.append(
                    SymbolRecord(
                        f"legacy:symbol:global:{ordinal}",
                        _text(item["name"], "global.name"),
                        SymbolKind.GLOBAL,
                        None,
                        _integer(item.get("size", 0), "global.size"),
                        None,
                        None,
                        _text(item["type"], "global.type") if "type" in item else None,
                        declaration_order,
                    )
                )
                declaration_order += 1

            raw_locals = _list(symbols_block.get("locals", []), "symbols.locals")
            for ordinal, raw_local in enumerate(raw_locals):
                item = _fields(
                    raw_local,
                    frozenset({"name", "function", "scope"}),
                    frozenset({"file", "directory", "line", "locations", "size", "type"}),
                    "local variable",
                )
                function_name = _text(item["function"], "local.function")
                candidates = function_ids_by_name.get(function_name, [])
                if len(candidates) != 1:
                    raise _legacy_error(
                        ResolutionStatus.CORRUPT,
                        "legacy_local_function_ambiguous",
                        "legacy local function spelling must resolve exactly once",
                    )
                if "locations" in item:
                    _list(item["locations"], "local.locations")
                portable_symbols.append(
                    SymbolRecord(
                        f"legacy:symbol:local:{ordinal}",
                        _text(item["name"], "local.name"),
                        SymbolKind.LOCAL,
                        None,
                        _integer(item.get("size", 0), "local.size"),
                        candidates[0],
                        _text(item["scope"], "local.scope"),
                        _text(item["type"], "local.type") if "type" in item else None,
                        declaration_order,
                    )
                )
                declaration_order += 1

            code_descriptor = architecture.space_descriptor(architecture.pc_space)
            byte_size_result = architecture.bytes_for_units(
                architecture.pc_space, architecture.instruction_alignment
            )
            if (
                code_descriptor is None
                or byte_size_result.status is not AddressStatus.VALID
                or byte_size_result.value < 1
            ):
                raise _legacy_error(
                    ResolutionStatus.CORRUPT,
                    "legacy_instruction_size_unsupported",
                    "architecture cannot express a whole-byte legacy instruction size",
                )
            instruction_byte_size = byte_size_result.value
            instructions: list[LegacyInstructionRecord] = []
            for ordinal, raw_instruction in enumerate(_list(root["instructions"], "instructions")):
                item = _fields(
                    raw_instruction,
                    frozenset({"pc"}),
                    frozenset(
                        {
                            "word",
                            "mvasm_line",
                            "ordinal",
                            "function",
                            "file",
                            "directory",
                            "file_id",
                            "line",
                            "column",
                            "source_kind",
                        }
                    ),
                    "instruction",
                )
                address = _address(
                    architecture,
                    architecture.pc_space,
                    item["pc"],
                    "instruction.pc",
                    Permission.EXECUTE,
                )
                _range_from_bytes(
                    architecture,
                    address,
                    instruction_byte_size,
                    "instruction.range",
                    Permission.EXECUTE,
                )
                raw_function_name = item.get("function")
                function_id = None
                if raw_function_name is not None:
                    function_name = _text(raw_function_name, "instruction.function")
                    matches = function_ids_by_name.get(function_name, [])
                    if len(matches) == 1:
                        function_id = matches[0]
                has_source = "file" in item or "line" in item or "directory" in item or "column" in item
                if has_source and not ("file" in item and "line" in item):
                    raise _legacy_error(
                        ResolutionStatus.CORRUPT,
                        "malformed_legacy_source",
                        "legacy instruction source requires file and line",
                    )
                spelling = (
                    LegacySourceSpelling(
                        _text(item["file"], "instruction.file"),
                        _text(item["directory"], "instruction.directory")
                        if "directory" in item
                        else None,
                    )
                    if has_source
                    else None
                )
                instructions.append(
                    LegacyInstructionRecord(
                        f"legacy:instruction:{ordinal}",
                        address,
                        instruction_byte_size,
                        function_id,
                        spelling,
                        _integer(item["line"], "instruction.line", minimum=1)
                        if has_source
                        else None,
                        _optional_integer(item.get("column"), "instruction.column"),
                    )
                )

            regions: list[MemoryRegion] = []
            for ordinal, raw_region in enumerate(_list(root["memory_regions"], "memory_regions")):
                item = _fields(
                    raw_region,
                    frozenset({"name", "type", "start", "end"}),
                    frozenset(),
                    "memory region",
                )
                kind = _text(item["type"], "memory_region.type")
                if kind == "text":
                    space = architecture.pc_space
                elif kind in {"data", "rodata", "bss", "stack"}:
                    space = architecture.sp_space
                else:
                    raise _legacy_error(
                        ResolutionStatus.SCHEMA_UNSUPPORTED,
                        "unsupported_legacy_memory_kind",
                        f"unsupported legacy memory region type {kind!r}",
                    )
                descriptor = architecture.space_descriptor(space)
                permission = Permission.EXECUTE if kind == "text" else Permission.READ
                start = _address(
                    architecture, space, item["start"], "memory_region.start", permission
                )
                end = _integer(item["end"], "memory_region.end")
                if end < start.unsigned_value:
                    raise _legacy_error(
                        ResolutionStatus.CORRUPT,
                        "malformed_legacy_memory_range",
                        "legacy memory region end precedes start",
                    )
                pc_range = architecture.range(
                    start, end - start.unsigned_value + 1, permission
                )
                if pc_range.status is not AddressStatus.VALID:
                    raise _legacy_error(
                        ResolutionStatus.CORRUPT,
                        "legacy_memory_range_invalid",
                        pc_range.diagnostics[0].message,
                    )
                regions.append(
                    MemoryRegion(
                        f"legacy:region:{ordinal}:{_text(item['name'], 'memory_region.name')}",
                        _text(item["name"], "memory_region.name"),
                        kind,
                        pc_range.value,
                        descriptor.permissions,
                    )
                )

            index = LegacyDebugArtifactIndex._from_validated(
                provenance,
                tuple(
                    sorted(
                        functions,
                        key=lambda record: (
                            record.range.start.space.value,
                            record.range.start.unsigned_value,
                            record.function_id,
                        ),
                    )
                ),
                tuple(
                    sorted(
                        portable_symbols,
                        key=lambda record: (
                            {
                                SymbolKind.FUNCTION: 0,
                                SymbolKind.LABEL: 1,
                                SymbolKind.GLOBAL: 2,
                                SymbolKind.LOCAL: 3,
                                SymbolKind.CONSTANT: 4,
                            }[record.kind],
                            record.symbol_id,
                        ),
                    )
                ),
                tuple(
                    sorted(
                        instructions,
                        key=lambda record: (
                            record.address.space.value,
                            record.address.unsigned_value,
                            record.instruction_id,
                        ),
                    )
                ),
                tuple(
                    sorted(
                        regions,
                        key=lambda record: (
                            record.range.start.space.value,
                            record.range.start.unsigned_value,
                            record.region_id,
                        ),
                    )
                ),
            )
        except _LegacyError as exc:
            return LegacyResolutionResult(exc.status, provenance, (), (exc.diagnostic,))
        except (TypeError, ValueError) as exc:
            return LegacyResolutionResult(
                ResolutionStatus.CORRUPT,
                provenance,
                (),
                (Diagnostic("malformed_legacy_sym", str(exc), component="legacy_symbols"),),
            )
        return LegacyResolutionResult(ResolutionStatus.RESOLVED, provenance, (index,), ())


__all__ = [
    "LegacyArtifactProvenance",
    "LegacyDebugArtifactIndex",
    "LegacyFunctionRecord",
    "LegacyIdentityStatus",
    "LegacyInstructionRecord",
    "LegacyResolutionResult",
    "LegacySourceSpelling",
    "LegacySymbolAdapter",
]
