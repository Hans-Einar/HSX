"""Immutable typed outcomes and simple inspection records for RF-004.

This module intentionally contains no resolver, snapshot, or frontend policy.  It only
defines the closed outcome algebra and the small value records that later RF-004 services
exchange.
"""

from __future__ import annotations

from dataclasses import dataclass, fields, is_dataclass
from enum import Enum, EnumMeta
from typing import TYPE_CHECKING, Generic, TypeAlias, TypeVar

if TYPE_CHECKING:
    from .addresses import ByteOrder, HsxAddress, HsxAddressRange
    from .identity import ImageDebugBinding, InspectionContext
    from .metadata import InstructionRecord


T = TypeVar("T")


def _require_nonempty(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field_name} must be a non-empty string")


def _require_optional_nonempty(value: str | None, field_name: str) -> None:
    if value is not None:
        _require_nonempty(value, field_name)


def _require_int(value: int, field_name: str, *, minimum: int = 0) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ValueError(f"{field_name} must be an integer >= {minimum}")


def _require_bool(value: bool, field_name: str) -> None:
    if not isinstance(value, bool):
        raise TypeError(f"{field_name} must be a bool")


def _require_enum(value: object, enum_type: type[Enum], field_name: str) -> None:
    if type(value) is not enum_type:
        raise TypeError(f"{field_name} must be {enum_type.__name__}")
    _require_contract_enum(value, field_name)


def _tuple(value: object, field_name: str) -> tuple:
    if isinstance(value, (str, bytes)) or not isinstance(value, (tuple, list)):
        raise TypeError(f"{field_name} must be a tuple or list")
    return tuple(value)


_IMMUTABLE_PAYLOAD_ATOM_TYPES = frozenset(
    {str, bytes, int, float, complex, bool, type(None)}
)
_APPROVED_CONTRACT_ENUM_TYPES: set[type[Enum]] = set()


def _register_contract_enums(*enum_types: type[Enum]) -> None:
    """Privately admit frozen public Enum projections to generic result payloads.

    Slice modules call this only for their already-frozen public Enum classes.  Approval is
    exact-class based: inheriting from ``Enum`` or reusing an approved scalar value does not
    admit a caller-defined Enum.
    """

    for enum_type in enum_types:
        if not isinstance(enum_type, EnumMeta):
            raise TypeError("contract Enum approval requires an Enum class")
        module_name = enum_type.__module__
        if (
            not (
                module_name.startswith("hsx_debugger.")
                or ".hsx_debugger." in module_name
            )
            or enum_type.__name__.startswith("_")
        ):
            raise TypeError("contract Enum approval requires a public hsx_debugger Enum")
        for declared_name, member in enum_type.__members__.items():
            if (
                type(member) is not enum_type
                or enum_type.__members__[declared_name] is not member
            ):
                raise TypeError("contract Enum members must retain exact canonical identity")
            schema_value = member.value
            frozen_value = _deep_freeze(
                schema_value, f"{enum_type.__name__}.{declared_name}.value"
            )
            if frozen_value is not schema_value:
                raise TypeError(
                    "contract Enum schema-visible values must already be contract-safe immutable"
                )
        _APPROVED_CONTRACT_ENUM_TYPES.add(enum_type)


def _require_contract_enum(value: Enum, field_name: str) -> None:
    enum_type = type(value)
    if enum_type not in _APPROVED_CONTRACT_ENUM_TYPES:
        raise TypeError(f"{field_name} must be an approved closed contract Enum")
    member = enum_type.__members__.get(value.name)
    if member is not value:
        raise TypeError(f"{field_name} must retain exact canonical Enum member identity")
    schema_value = value.value
    frozen_value = _deep_freeze(schema_value, f"{field_name}.value")
    if frozen_value is not schema_value:
        raise TypeError(
            f"{field_name} Enum schema-visible value must be contract-safe immutable"
        )


def _deep_freeze(value: object, field_name: str, active: set[int] | None = None) -> object:
    """Copy supported generic payload containers into deeply immutable values.

    Result envelopes are generic, so their constructors cannot validate one static DTO type.
    They instead accept exact immutable scalar values, approved closed Enum atoms, frozen
    dataclass DTOs, and the exact container forms normalized by interface 1.1.  Mutable or
    structurally duck-typed objects outside those forms are rejected.
    """

    if type(value) in _IMMUTABLE_PAYLOAD_ATOM_TYPES:
        return value

    if isinstance(value, Enum):
        _require_contract_enum(value, field_name)
        return value

    if active is None:
        active = set()
    identity = id(value)
    if identity in active:
        raise ValueError(f"{field_name} must not contain a reference cycle")

    if type(value) in (tuple, list):
        active.add(identity)
        try:
            frozen_items = tuple(
                _deep_freeze(item, f"{field_name}[{index}]", active)
                for index, item in enumerate(value)
            )
        finally:
            active.remove(identity)
        if type(value) is tuple and all(
            frozen is original for frozen, original in zip(frozen_items, value)
        ):
            return value
        return frozen_items

    if type(value) in (set, frozenset):
        active.add(identity)
        try:
            frozen_items = tuple(
                _deep_freeze(item, f"{field_name} item", active) for item in value
            )
        finally:
            active.remove(identity)
        if type(value) is frozenset and all(
            frozen is original for frozen, original in zip(frozen_items, value)
        ):
            return value
        try:
            return frozenset(frozen_items)
        except TypeError as exc:
            raise TypeError(f"{field_name} contains an unhashable frozen value") from exc

    if type(value) is dict:
        active.add(identity)
        try:
            frozen_items = tuple(
                (
                    _deep_freeze(key, f"{field_name} key", active),
                    _deep_freeze(item, f"{field_name}[{key!r}]", active),
                )
                for key, item in value.items()
            )
        finally:
            active.remove(identity)
        return frozen_items

    if is_dataclass(value) and not isinstance(value, type):
        concrete_type = type(value)
        concrete_namespace = type.__getattribute__(concrete_type, "__dict__")
        dataclass_parameters = concrete_namespace.get("__dataclass_params__")
        declared_fields = concrete_namespace.get("__dataclass_fields__")
        if dataclass_parameters is None or declared_fields is None:
            raise TypeError(
                f"{field_name} concrete type must be directly declared as a dataclass"
            )
        if not dataclass_parameters.frozen:
            raise TypeError(f"{field_name} dataclass payload must be frozen")
        record_fields = fields(concrete_type)
        active.add(identity)
        try:
            for record_field in record_fields:
                member = object.__getattribute__(value, record_field.name)
                frozen_member = _deep_freeze(
                    member, f"{field_name}.{record_field.name}", active
                )
                if frozen_member is not member:
                    raise TypeError(
                        f"{field_name}.{record_field.name} must already be deeply immutable"
                    )
        finally:
            active.remove(identity)
        return value

    raise TypeError(
        f"{field_name} must contain immutable scalars, frozen DTOs, or supported containers"
    )


class ResolutionStatus(str, Enum):
    RESOLVED = "resolved"
    UNAVAILABLE = "unavailable"
    AMBIGUOUS = "ambiguous"
    CONTENT_MISMATCH = "content_mismatch"
    CASE_COLLISION = "case_collision"
    ARTIFACT_MISMATCH = "artifact_mismatch"
    SCHEMA_UNSUPPORTED = "schema_unsupported"
    CORRUPT = "corrupt"


class InspectionStatus(str, Enum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    UNAVAILABLE = "unavailable"
    UNKNOWN_HANDLE = "unknown_handle"
    STALE = "stale"
    ARTIFACT_MISMATCH = "artifact_mismatch"
    UNSUPPORTED = "unsupported"
    CORRUPT = "corrupt"


class ContextBindingStatus(str, Enum):
    BOUND = "bound"
    UNAVAILABLE = "unavailable"
    STALE = "stale"
    ARTIFACT_MISMATCH = "artifact_mismatch"


class InspectionOpenStatus(str, Enum):
    OPENED = "opened"
    UNAVAILABLE = "unavailable"
    STALE = "stale"
    ARTIFACT_MISMATCH = "artifact_mismatch"


class InvalidationStatus(str, Enum):
    INVALIDATED = "invalidated"
    ALREADY_STALE = "already_stale"
    UNKNOWN_EPOCH = "unknown_epoch"


class ServiceCloseStatus(str, Enum):
    CLOSED = "closed"
    ALREADY_CLOSED = "already_closed"


class AddressStatus(str, Enum):
    VALID = "valid"
    UNKNOWN_SPACE = "unknown_space"
    OVERFLOW = "overflow"
    UNDERFLOW = "underflow"
    MISALIGNED = "misaligned"
    OUT_OF_RANGE = "out_of_range"
    PERMISSION_DENIED = "permission_denied"
    WRAP_FORBIDDEN = "wrap_forbidden"
    UNIT_CONVERSION_UNSUPPORTED = "unit_conversion_unsupported"


class ValueAvailability(str, Enum):
    AVAILABLE = "available"
    PARTIAL = "partial"
    OPTIMIZED_OUT = "optimized_out"
    UNAVAILABLE = "unavailable"


class ValuePieceStatus(str, Enum):
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"


class ExpressionKind(str, Enum):
    REGISTER = "register"
    VARIABLE = "variable"
    SYMBOL = "symbol"
    CONSTANT = "constant"
    MEMORY = "memory"


class MemorySegmentStatus(str, Enum):
    COMPLETE = "complete"
    UNAVAILABLE = "unavailable"


_register_contract_enums(
    ResolutionStatus,
    InspectionStatus,
    ContextBindingStatus,
    InspectionOpenStatus,
    InvalidationStatus,
    ServiceCloseStatus,
    AddressStatus,
    ValueAvailability,
    ValuePieceStatus,
    ExpressionKind,
    MemorySegmentStatus,
)


@dataclass(frozen=True, slots=True)
class Diagnostic:
    code: str
    message: str
    component: str | None = None
    row_id: str | None = None
    frame_index: int | None = None
    operation_index: int | None = None

    def __post_init__(self) -> None:
        _require_nonempty(self.code, "code")
        if not isinstance(self.message, str):
            raise TypeError("message must be a string")
        _require_optional_nonempty(self.component, "component")
        _require_optional_nonempty(self.row_id, "row_id")
        if self.frame_index is not None:
            _require_int(self.frame_index, "frame_index")
        if self.operation_index is not None:
            _require_int(self.operation_index, "operation_index")


def _diagnostics(value: object) -> tuple[Diagnostic, ...]:
    items = _tuple(value, "diagnostics")
    if not all(isinstance(item, Diagnostic) for item in items):
        raise TypeError("diagnostics must contain Diagnostic values")
    return items


@dataclass(frozen=True, slots=True)
class ResolutionResult(Generic[T]):
    status: ResolutionStatus
    binding: ImageDebugBinding | None
    values: tuple[T, ...]
    diagnostics: tuple[Diagnostic, ...] = ()

    def __post_init__(self) -> None:
        _require_enum(self.status, ResolutionStatus, "status")
        if self.binding is not None:
            from .identity import ImageDebugBinding

            if not isinstance(self.binding, ImageDebugBinding):
                raise TypeError("binding must be ImageDebugBinding or None")
        values = _tuple(self.values, "values")
        values = tuple(
            _deep_freeze(value, f"values[{index}]") for index, value in enumerate(values)
        )
        diagnostics = _diagnostics(self.diagnostics)
        object.__setattr__(self, "values", values)
        object.__setattr__(self, "diagnostics", diagnostics)
        if self.status is ResolutionStatus.RESOLVED:
            if not values:
                raise ValueError("RESOLVED requires one or more values")
        elif self.status is ResolutionStatus.AMBIGUOUS:
            if len(values) < 2:
                raise ValueError("AMBIGUOUS requires at least two candidates")
        elif values:
            raise ValueError("non-value resolution statuses require no values")


@dataclass(frozen=True, slots=True)
class InspectionResult(Generic[T]):
    status: InspectionStatus
    context: InspectionContext
    value: T | None
    diagnostics: tuple[Diagnostic, ...] = ()

    def __post_init__(self) -> None:
        _require_enum(self.status, InspectionStatus, "status")
        diagnostics = _diagnostics(self.diagnostics)
        object.__setattr__(self, "diagnostics", diagnostics)
        from .identity import InspectionContext

        if not isinstance(self.context, InspectionContext):
            raise TypeError("context must be InspectionContext")
        value = None if self.value is None else _deep_freeze(self.value, "value")
        object.__setattr__(self, "value", value)
        if self.status is InspectionStatus.COMPLETE:
            if value is None:
                raise ValueError("COMPLETE requires one value")
        elif self.status is InspectionStatus.PARTIAL:
            if value is None or not diagnostics:
                raise ValueError("PARTIAL requires a value and a missing-piece diagnostic")
        elif value is not None:
            raise ValueError("non-complete inspection statuses require no value")
        if isinstance(value, MemoryBlock):
            complete_segments = sum(
                segment.status is MemorySegmentStatus.COMPLETE for segment in value.segments
            )
            if self.status is InspectionStatus.COMPLETE:
                if complete_segments != len(value.segments):
                    raise ValueError("COMPLETE MemoryBlock requires every segment complete")
            elif self.status is InspectionStatus.PARTIAL:
                if complete_segments == 0 or complete_segments == len(value.segments):
                    raise ValueError(
                        "PARTIAL MemoryBlock requires available and unavailable segments"
                    )


@dataclass(frozen=True, slots=True)
class ContextBindingResult:
    status: ContextBindingStatus
    context: InspectionContext | None
    diagnostics: tuple[Diagnostic, ...] = ()

    def __post_init__(self) -> None:
        _require_enum(self.status, ContextBindingStatus, "status")
        diagnostics = _diagnostics(self.diagnostics)
        object.__setattr__(self, "diagnostics", diagnostics)
        if self.context is not None:
            from .identity import InspectionContext

            if not isinstance(self.context, InspectionContext):
                raise TypeError("context must be InspectionContext or None")
        if self.status is ContextBindingStatus.BOUND:
            if self.context is None:
                raise ValueError("BOUND requires a context")
            if diagnostics:
                raise ValueError("BOUND carries no diagnostics")
        else:
            if self.context is not None:
                raise ValueError("non-BOUND outcomes publish no context")
            if not diagnostics:
                raise ValueError("non-BOUND outcomes require a diagnostic")


@dataclass(frozen=True, slots=True)
class AddressResult:
    status: AddressStatus
    value: HsxAddress | None
    diagnostics: tuple[Diagnostic, ...] = ()

    def __post_init__(self) -> None:
        diagnostics = _diagnostics(self.diagnostics)
        object.__setattr__(self, "diagnostics", diagnostics)
        _validate_address_envelope(self.status, self.value, diagnostics)
        if self.value is not None:
            from .addresses import HsxAddress

            if not isinstance(self.value, HsxAddress):
                raise TypeError("value must be HsxAddress or None")


@dataclass(frozen=True, slots=True)
class AddressRangeResult:
    status: AddressStatus
    value: HsxAddressRange | None
    diagnostics: tuple[Diagnostic, ...] = ()

    def __post_init__(self) -> None:
        diagnostics = _diagnostics(self.diagnostics)
        object.__setattr__(self, "diagnostics", diagnostics)
        _validate_address_envelope(self.status, self.value, diagnostics)
        if self.value is not None:
            from .addresses import HsxAddressRange

            if not isinstance(self.value, HsxAddressRange):
                raise TypeError("value must be HsxAddressRange or None")


@dataclass(frozen=True, slots=True)
class UnitCountResult:
    status: AddressStatus
    value: int | None
    diagnostics: tuple[Diagnostic, ...] = ()

    def __post_init__(self) -> None:
        diagnostics = _diagnostics(self.diagnostics)
        object.__setattr__(self, "diagnostics", diagnostics)
        _validate_address_envelope(self.status, self.value, diagnostics)
        if self.value is not None:
            _require_int(self.value, "value")


@dataclass(frozen=True, slots=True)
class ByteLengthResult:
    status: AddressStatus
    value: int | None
    diagnostics: tuple[Diagnostic, ...] = ()

    def __post_init__(self) -> None:
        diagnostics = _diagnostics(self.diagnostics)
        object.__setattr__(self, "diagnostics", diagnostics)
        _validate_address_envelope(self.status, self.value, diagnostics)
        if self.value is not None:
            _require_int(self.value, "value")


def _validate_address_envelope(
    status: AddressStatus, value: object | None, diagnostics: object
) -> None:
    _require_enum(status, AddressStatus, "status")
    frozen_diagnostics = _diagnostics(diagnostics)
    if status is AddressStatus.VALID:
        if value is None:
            raise ValueError("VALID requires a value")
        if frozen_diagnostics:
            raise ValueError("VALID carries no diagnostics")
    else:
        if value is not None:
            raise ValueError("failed address outcomes publish no value")
        if not frozen_diagnostics:
            raise ValueError("failed address outcomes require a diagnostic")


@dataclass(frozen=True, slots=True)
class PageRequest:
    offset: int
    limit: int

    def __post_init__(self) -> None:
        _require_int(self.offset, "offset")
        _require_int(self.limit, "limit", minimum=1)
        if self.limit > 256:
            raise ValueError("limit must be <= 256")


@dataclass(frozen=True, slots=True)
class RegisterSelection:
    all_declared: bool
    register_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _require_bool(self.all_declared, "all_declared")
        register_ids = _tuple(self.register_ids, "register_ids")
        for register_id in register_ids:
            _require_nonempty(register_id, "register_id")
        if len(set(register_ids)) != len(register_ids):
            raise ValueError("register_ids must be unique")
        if self.all_declared == bool(register_ids):
            raise ValueError("select all declared registers or an explicit non-empty set")
        object.__setattr__(self, "register_ids", register_ids)


@dataclass(frozen=True, slots=True)
class RegisterValue:
    register_id: str
    bit_width: int
    unsigned_value: int | None
    available: bool

    def __post_init__(self) -> None:
        _require_nonempty(self.register_id, "register_id")
        _require_int(self.bit_width, "bit_width", minimum=1)
        _require_bool(self.available, "available")
        if self.available:
            if self.unsigned_value is None:
                raise ValueError("an available register requires unsigned_value")
            _require_int(self.unsigned_value, "unsigned_value")
            if self.unsigned_value >= 1 << self.bit_width:
                raise ValueError("unsigned_value does not fit bit_width")
        elif self.unsigned_value is not None:
            raise ValueError("an unavailable register has no unsigned_value")


@dataclass(frozen=True, slots=True)
class RegisterSet:
    registers: tuple[RegisterValue, ...]

    def __post_init__(self) -> None:
        registers = _tuple(self.registers, "registers")
        if not all(isinstance(item, RegisterValue) for item in registers):
            raise TypeError("registers must contain RegisterValue values")
        ids = tuple(item.register_id for item in registers)
        if len(set(ids)) != len(ids):
            raise ValueError("register IDs must be unique")
        object.__setattr__(self, "registers", registers)


@dataclass(frozen=True, slots=True)
class ValuePiece:
    destination_bit_offset: int
    bit_size: int
    source_bit_offset: int
    raw_bits: bytes | None
    status: ValuePieceStatus
    reason: str | None = None

    def __post_init__(self) -> None:
        _require_int(self.destination_bit_offset, "destination_bit_offset")
        _require_int(self.bit_size, "bit_size", minimum=1)
        _require_int(self.source_bit_offset, "source_bit_offset")
        _require_enum(self.status, ValuePieceStatus, "status")
        _require_optional_nonempty(self.reason, "reason")
        if self.status is ValuePieceStatus.AVAILABLE:
            if not isinstance(self.raw_bits, bytes):
                raise TypeError("an available piece requires immutable raw_bits")
            if len(self.raw_bits) != (self.bit_size + 7) // 8:
                raise ValueError("raw_bits must have the exact piece storage width")
            if self.reason is not None:
                raise ValueError("an available piece has no reason")
        else:
            if self.raw_bits is not None:
                raise ValueError("an unavailable piece has no raw_bits")
            if self.reason is None:
                raise ValueError("an unavailable piece requires a reason")


def _validate_pieces(
    pieces: object, bit_size: int, *, require_unavailable: bool
) -> tuple[ValuePiece, ...]:
    items = _tuple(pieces, "pieces")
    if not items or not all(isinstance(item, ValuePiece) for item in items):
        raise ValueError("pieces must contain at least one ValuePiece")
    ordered = tuple(sorted(items, key=lambda item: item.destination_bit_offset))
    if items != ordered:
        raise ValueError("pieces must be ordered by destination_bit_offset")
    previous_end = 0
    for item in items:
        if item.destination_bit_offset != previous_end:
            if item.destination_bit_offset < previous_end:
                raise ValueError("piece destination ranges must not overlap")
            raise ValueError("piece destination ranges must explicitly cover every bit")
        end = item.destination_bit_offset + item.bit_size
        if end > bit_size:
            raise ValueError("piece destination range exceeds bit_size")
        previous_end = end
    if previous_end != bit_size:
        raise ValueError("piece destination ranges must explicitly cover every bit")
    if require_unavailable and all(
        item.status is ValuePieceStatus.AVAILABLE for item in items
    ):
        raise ValueError("PARTIAL requires at least one unavailable piece")
    return items


@dataclass(frozen=True, slots=True)
class EvaluatedValue:
    symbol_id: str
    name: str
    declared_type_id: str | None
    display_value: str
    raw_bytes: bytes | None
    bit_size: int | None
    location_status: ValueAvailability
    pieces: tuple[ValuePiece, ...] = ()

    def __post_init__(self) -> None:
        _require_nonempty(self.symbol_id, "symbol_id")
        _require_nonempty(self.name, "name")
        _require_optional_nonempty(self.declared_type_id, "declared_type_id")
        if not isinstance(self.display_value, str):
            raise TypeError("display_value must be a string")
        if self.bit_size is not None:
            _require_int(self.bit_size, "bit_size", minimum=1)
        _require_enum(self.location_status, ValueAvailability, "location_status")
        pieces = _tuple(self.pieces, "pieces")
        if self.location_status is ValueAvailability.AVAILABLE:
            if self.bit_size is None or not isinstance(self.raw_bytes, bytes):
                raise ValueError("AVAILABLE requires bit_size and raw_bytes")
            if len(self.raw_bytes) != (self.bit_size + 7) // 8:
                raise ValueError("raw_bytes must have the exact declared storage width")
            if pieces:
                raise ValueError("AVAILABLE scalar values have no pieces")
        elif self.location_status is ValueAvailability.PARTIAL:
            if self.bit_size is None or self.raw_bytes is not None:
                raise ValueError("PARTIAL requires bit_size and no aggregate raw_bytes")
            pieces = _validate_pieces(pieces, self.bit_size, require_unavailable=True)
        else:
            if self.raw_bytes is not None or pieces:
                raise ValueError("unavailable terminal values have no raw bytes or pieces")
        object.__setattr__(self, "pieces", pieces)


@dataclass(frozen=True, slots=True)
class ExpressionValue:
    expression_kind: ExpressionKind
    source_id: str | None
    display_value: str
    raw_bytes: bytes | None
    bit_size: int
    status: ValueAvailability
    pieces: tuple[ValuePiece, ...] = ()

    def __post_init__(self) -> None:
        _require_enum(self.expression_kind, ExpressionKind, "expression_kind")
        _require_optional_nonempty(self.source_id, "source_id")
        if self.expression_kind in {
            ExpressionKind.REGISTER,
            ExpressionKind.VARIABLE,
            ExpressionKind.SYMBOL,
        }:
            if self.source_id is None:
                raise ValueError("register/variable/symbol expressions require source_id")
        elif self.source_id is not None:
            raise ValueError("constant/memory expressions have no source_id")
        if not isinstance(self.display_value, str):
            raise TypeError("display_value must be a string")
        _require_int(self.bit_size, "bit_size", minimum=1)
        _require_enum(self.status, ValueAvailability, "status")
        pieces = _tuple(self.pieces, "pieces")
        if self.status is ValueAvailability.AVAILABLE:
            if not isinstance(self.raw_bytes, bytes):
                raise TypeError("AVAILABLE requires raw_bytes")
            if len(self.raw_bytes) != (self.bit_size + 7) // 8:
                raise ValueError("raw_bytes must have the exact declared storage width")
            if pieces:
                raise ValueError("AVAILABLE scalar values have no pieces")
        elif self.status is ValueAvailability.PARTIAL:
            if self.expression_kind is not ExpressionKind.VARIABLE:
                raise ValueError("only a variable expression may be PARTIAL")
            if self.raw_bytes is not None:
                raise ValueError("PARTIAL has no aggregate raw_bytes")
            pieces = _validate_pieces(pieces, self.bit_size, require_unavailable=True)
        elif self.raw_bytes is not None or pieces:
            raise ValueError("unavailable terminal values have no raw bytes or pieces")
        object.__setattr__(self, "pieces", pieces)


@dataclass(frozen=True, slots=True)
class MemorySegment:
    offset: int
    requested_length: int
    data: bytes
    status: MemorySegmentStatus

    def __post_init__(self) -> None:
        _require_int(self.offset, "offset")
        _require_int(self.requested_length, "requested_length", minimum=1)
        if not isinstance(self.data, bytes):
            raise TypeError("data must be immutable bytes")
        _require_enum(self.status, MemorySegmentStatus, "status")
        if self.status is MemorySegmentStatus.COMPLETE:
            if len(self.data) != self.requested_length:
                raise ValueError("a complete segment must contain every requested byte")
        elif self.data:
            raise ValueError("an unavailable segment carries no fabricated bytes")


@dataclass(frozen=True, slots=True)
class MemoryBlock:
    start: HsxAddress
    requested_length: int
    segments: tuple[MemorySegment, ...]

    def __post_init__(self) -> None:
        from .addresses import HsxAddress

        if not isinstance(self.start, HsxAddress):
            raise TypeError("start must be HsxAddress")
        _require_int(self.requested_length, "requested_length", minimum=1)
        segments = _tuple(self.segments, "segments")
        if not segments or not all(isinstance(item, MemorySegment) for item in segments):
            raise ValueError("segments must contain at least one MemorySegment")
        expected_offset = 0
        for segment in segments:
            if segment.offset != expected_offset:
                raise ValueError("segments must be ordered, non-overlapping, and gap-explicit")
            expected_offset += segment.requested_length
        if expected_offset != self.requested_length:
            raise ValueError("segments must exactly cover requested_length")
        object.__setattr__(self, "segments", segments)


@dataclass(frozen=True, slots=True)
class InstructionBytes:
    address: HsxAddress
    encoded: bytes

    def __post_init__(self) -> None:
        from .addresses import HsxAddress

        if not isinstance(self.address, HsxAddress):
            raise TypeError("address must be HsxAddress")
        if not isinstance(self.encoded, bytes) or not self.encoded:
            raise ValueError("encoded must be non-empty immutable bytes")


@dataclass(frozen=True, slots=True)
class DisassembledInstruction:
    address: HsxAddress
    encoded: bytes
    instruction: InstructionRecord | None
    text: str | None

    def __post_init__(self) -> None:
        from .addresses import HsxAddress

        if not isinstance(self.address, HsxAddress):
            raise TypeError("address must be HsxAddress")
        if not isinstance(self.encoded, bytes) or not self.encoded:
            raise ValueError("encoded must be non-empty immutable bytes")
        if self.text is not None and not isinstance(self.text, str):
            raise TypeError("text must be a string or None")
        if self.instruction is not None:
            from .metadata import InstructionRecord

            if type(self.instruction) is not InstructionRecord:
                raise TypeError("instruction must be exactly metadata.InstructionRecord or None")
            if self.instruction.address != self.address:
                raise ValueError("instruction address must match address")
            if self.instruction.byte_size != len(self.encoded):
                raise ValueError("instruction byte_size must match encoded length")


@dataclass(frozen=True, slots=True)
class DisassemblyBlock:
    start: HsxAddress
    requested_count: int
    instructions: tuple[DisassembledInstruction, ...]

    def __post_init__(self) -> None:
        from .addresses import HsxAddress

        if not isinstance(self.start, HsxAddress):
            raise TypeError("start must be HsxAddress")
        _require_int(self.requested_count, "requested_count", minimum=1)
        instructions = _tuple(self.instructions, "instructions")
        if not all(isinstance(item, DisassembledInstruction) for item in instructions):
            raise TypeError("instructions must contain DisassembledInstruction values")
        if len(instructions) > self.requested_count:
            raise ValueError("instructions exceed requested_count")
        if instructions:
            start_space = getattr(self.start, "space", None)
            start_value = getattr(self.start, "unsigned_value", None)
            prior = None
            for instruction in instructions:
                if getattr(instruction.address, "space", None) != start_space:
                    raise ValueError("all instructions must use the start address space")
                value = getattr(instruction.address, "unsigned_value", None)
                if not isinstance(value, int) or value < start_value:
                    raise ValueError("instruction addresses must not precede start")
                if prior is not None and value <= prior:
                    raise ValueError("instruction addresses must be strictly ascending")
                prior = value
        object.__setattr__(self, "instructions", instructions)


class ScalarBytes:
    """Exact fixed-width scalar encoding independent of host byte order."""

    @staticmethod
    def encode(value: int, signed: bool, bit_width: int, byte_order: ByteOrder) -> bytes:
        from .addresses import ByteOrder

        if isinstance(value, bool) or not isinstance(value, int):
            raise TypeError("value must be an integer")
        _require_bool(signed, "signed")
        _require_int(bit_width, "bit_width", minimum=1)
        if not isinstance(byte_order, ByteOrder):
            raise TypeError("byte_order must be LITTLE or BIG")
        order = byte_order.value
        if signed:
            minimum = -(1 << (bit_width - 1))
            maximum = (1 << (bit_width - 1)) - 1
        else:
            minimum = 0
            maximum = (1 << bit_width) - 1
        if value < minimum or value > maximum:
            raise OverflowError("value does not fit the declared scalar width")
        byte_length = (bit_width + 7) // 8
        if value < 0:
            # The frozen contract explicitly permits this two's-complement reduction and
            # sign-extension into unused storage padding bits.
            encoded_value = (1 << (byte_length * 8)) + value
        else:
            encoded_value = value
        return encoded_value.to_bytes(byte_length, byteorder=order, signed=False)


@dataclass(frozen=True, slots=True)
class RegisterExpression:
    register_id: str

    def __post_init__(self) -> None:
        _require_nonempty(self.register_id, "register_id")


@dataclass(frozen=True, slots=True)
class VariableExpression:
    symbol_id: str
    function_id: str | None
    lexical_scope_id: str | None

    def __post_init__(self) -> None:
        _require_nonempty(self.symbol_id, "symbol_id")
        _require_optional_nonempty(self.function_id, "function_id")
        _require_optional_nonempty(self.lexical_scope_id, "lexical_scope_id")
        if (self.function_id is None) != (self.lexical_scope_id is None):
            raise ValueError("function_id and lexical_scope_id must both be present or absent")


@dataclass(frozen=True, slots=True)
class SymbolExpression:
    symbol_id: str

    def __post_init__(self) -> None:
        _require_nonempty(self.symbol_id, "symbol_id")


@dataclass(frozen=True, slots=True)
class ConstantExpression:
    unsigned_value: int
    bit_width: int
    byte_order: ByteOrder

    def __post_init__(self) -> None:
        from .addresses import ByteOrder

        _require_int(self.unsigned_value, "unsigned_value")
        _require_int(self.bit_width, "bit_width", minimum=1)
        if self.unsigned_value >= 1 << self.bit_width:
            raise ValueError("unsigned_value does not fit bit_width")
        if not isinstance(self.byte_order, ByteOrder):
            raise TypeError("byte_order must be LITTLE or BIG")


@dataclass(frozen=True, slots=True)
class MemoryExpression:
    address: HsxAddress
    bit_width: int
    byte_order: ByteOrder

    def __post_init__(self) -> None:
        from .addresses import ByteOrder, HsxAddress

        if not isinstance(self.address, HsxAddress):
            raise TypeError("address must be HsxAddress")
        _require_int(self.bit_width, "bit_width", minimum=1)
        if not isinstance(self.byte_order, ByteOrder):
            raise TypeError("byte_order must be LITTLE or BIG")


SnapshotExpression: TypeAlias = (
    RegisterExpression
    | VariableExpression
    | SymbolExpression
    | ConstantExpression
    | MemoryExpression
)


__all__ = [
    "AddressRangeResult",
    "AddressResult",
    "AddressStatus",
    "ByteLengthResult",
    "ConstantExpression",
    "ContextBindingResult",
    "ContextBindingStatus",
    "Diagnostic",
    "DisassembledInstruction",
    "DisassemblyBlock",
    "EvaluatedValue",
    "ExpressionKind",
    "ExpressionValue",
    "InspectionOpenStatus",
    "InspectionResult",
    "InspectionStatus",
    "InstructionBytes",
    "InvalidationStatus",
    "MemoryBlock",
    "MemoryExpression",
    "MemorySegment",
    "MemorySegmentStatus",
    "PageRequest",
    "RegisterExpression",
    "RegisterSelection",
    "RegisterSet",
    "RegisterValue",
    "ResolutionResult",
    "ResolutionStatus",
    "ScalarBytes",
    "ServiceCloseStatus",
    "SnapshotExpression",
    "SymbolExpression",
    "UnitCountResult",
    "ValueAvailability",
    "ValuePiece",
    "ValuePieceStatus",
    "VariableExpression",
]
