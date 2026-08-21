"""Pure bounded unwind/location recipe records and evaluators for RF-004.

The module owns recipe schemas and evaluation only.  Artifact parsing/indexing, stack
traversal, inspection handles, runtime adapters, and frontend expression parsing live in
later slices.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from typing import TypeAlias

from .addresses import (
    AddressArithmeticMode,
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
    InspectionContext,
    RecipeSchemaRef,
)
from .metadata import FunctionRecord, SourceLocation, SymbolKind, SymbolRecord, TypeRecord
from .results import (
    AddressStatus,
    Diagnostic,
    EvaluatedValue,
    InspectionResult,
    InspectionStatus,
    MemoryBlock,
    MemorySegmentStatus,
    RegisterSet,
    RegisterValue,
    ResolutionResult,
    ResolutionStatus,
    ScalarBytes,
    ValueAvailability,
    ValuePiece,
    ValuePieceStatus,
    _register_contract_enums,
)
from .snapshot import SnapshotReadPort, fence_snapshot_result, require_snapshot_read_set


def _require_nonempty(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field_name} must be a non-empty string")


def _require_optional_nonempty(value: str | None, field_name: str) -> None:
    if value is not None:
        _require_nonempty(value, field_name)


def _require_int(value: int, field_name: str, *, minimum: int = 0) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ValueError(f"{field_name} must be an integer >= {minimum}")


def _require_tuple(value: object, field_name: str) -> tuple:
    if isinstance(value, (str, bytes)) or not isinstance(value, (tuple, list)):
        raise TypeError(f"{field_name} must be a tuple or list")
    return tuple(value)


def _require_exact_enum(value: object, enum_type: type[Enum], field_name: str) -> None:
    if type(value) is not enum_type:
        raise TypeError(f"{field_name} must be {enum_type.__name__}")


class RecipeSpecial(str, Enum):
    PC = "PC"
    SP = "SP"
    PSW = "PSW"


class RecipeRole(str, Enum):
    CFA = "cfa"
    CALLER_PC = "caller_pc"
    CALLER_SP = "caller_sp"
    CALLER_FRAME_BASE = "caller_frame_base"
    REGISTER = "register"
    LOCATION = "location"


class RecipeResultKind(str, Enum):
    ADDRESS = "address"
    UNSIGNED_SCALAR = "unsigned_scalar"
    SIGNED_SCALAR = "signed_scalar"
    REGISTER = "register"


class RecipeRuleKind(str, Enum):
    EXPRESSION = "expression"
    SAME = "same"
    UNDEFINED = "undefined"
    UNAVAILABLE = "unavailable"
    OPTIMIZED_OUT = "optimized_out"


class LocationKind(str, Enum):
    ADDRESS = "address"
    VALUE = "value"
    PIECES = "pieces"
    OPTIMIZED_OUT = "optimized_out"
    UNAVAILABLE = "unavailable"


class FrameBinding(str, Enum):
    SELECTED_FRAME = "selected_frame"


class UnwindBoundary(str, Enum):
    ORDINARY = "ordinary"
    ENTRY = "entry"
    EPILOGUE = "epilogue"
    TERMINAL = "terminal"
    UNSUPPORTED = "unsupported"


class RecipeEvaluationStatus(str, Enum):
    COMPLETE = "complete"
    UNAVAILABLE = "unavailable"
    UNSUPPORTED = "unsupported"
    CORRUPT = "corrupt"
    STALE = "stale"
    ARTIFACT_MISMATCH = "artifact_mismatch"


_register_contract_enums(
    RecipeSpecial,
    RecipeRole,
    RecipeResultKind,
    RecipeRuleKind,
    LocationKind,
    FrameBinding,
    UnwindBoundary,
    RecipeEvaluationStatus,
)


@dataclass(frozen=True, slots=True)
class RegValueOp:
    opcode: str
    register_id: str

    def __post_init__(self) -> None:
        if self.opcode != "reg_value":
            raise ValueError("opcode must be 'reg_value'")
        _require_nonempty(self.register_id, "register_id")


@dataclass(frozen=True, slots=True)
class SpecialValueOp:
    opcode: str
    special: RecipeSpecial

    def __post_init__(self) -> None:
        if self.opcode != "special_value":
            raise ValueError("opcode must be 'special_value'")
        _require_exact_enum(self.special, RecipeSpecial, "special")


@dataclass(frozen=True, slots=True)
class ConstUOp:
    opcode: str
    value: int
    bit_width: int

    def __post_init__(self) -> None:
        if self.opcode != "const_u":
            raise ValueError("opcode must be 'const_u'")
        _require_int(self.value, "value")
        _require_int(self.bit_width, "bit_width", minimum=1)


@dataclass(frozen=True, slots=True)
class ConstSOp:
    opcode: str
    value: int
    bit_width: int

    def __post_init__(self) -> None:
        if self.opcode != "const_s":
            raise ValueError("opcode must be 'const_s'")
        if isinstance(self.value, bool) or not isinstance(self.value, int):
            raise TypeError("value must be an integer")
        _require_int(self.bit_width, "bit_width", minimum=1)


@dataclass(frozen=True, slots=True)
class StaticAddressOp:
    opcode: str
    address: HsxAddress

    def __post_init__(self) -> None:
        if self.opcode != "static_address":
            raise ValueError("opcode must be 'static_address'")
        if not isinstance(self.address, HsxAddress):
            raise TypeError("address must be HsxAddress")


@dataclass(frozen=True, slots=True)
class ToAddressOp:
    opcode: str
    space: AddressSpaceId

    def __post_init__(self) -> None:
        if self.opcode != "to_address":
            raise ValueError("opcode must be 'to_address'")
        if not isinstance(self.space, AddressSpaceId):
            raise TypeError("space must be AddressSpaceId")


@dataclass(frozen=True, slots=True)
class CfaOp:
    opcode: str

    def __post_init__(self) -> None:
        if self.opcode != "cfa":
            raise ValueError("opcode must be 'cfa'")


@dataclass(frozen=True, slots=True)
class FrameBaseOp:
    opcode: str

    def __post_init__(self) -> None:
        if self.opcode != "frame_base":
            raise ValueError("opcode must be 'frame_base'")


@dataclass(frozen=True, slots=True)
class AddSConstCheckedOp:
    opcode: str
    signed_delta: int

    def __post_init__(self) -> None:
        if self.opcode != "add_sconst_checked":
            raise ValueError("opcode must be 'add_sconst_checked'")
        if isinstance(self.signed_delta, bool) or not isinstance(self.signed_delta, int):
            raise TypeError("signed_delta must be an integer")


@dataclass(frozen=True, slots=True)
class DerefUOp:
    opcode: str
    byte_length: int
    byte_order: ByteOrder

    def __post_init__(self) -> None:
        if self.opcode != "deref_u":
            raise ValueError("opcode must be 'deref_u'")
        if self.byte_length not in {1, 2, 4, 8, 16}:
            raise ValueError("byte_length must be one of 1, 2, 4, 8, 16")
        if not isinstance(self.byte_order, ByteOrder):
            raise TypeError("byte_order must be ByteOrder")


@dataclass(frozen=True, slots=True)
class BitSliceOp:
    opcode: str
    source_bit_offset: int
    bit_size: int

    def __post_init__(self) -> None:
        if self.opcode != "bit_slice":
            raise ValueError("opcode must be 'bit_slice'")
        _require_int(self.source_bit_offset, "source_bit_offset")
        _require_int(self.bit_size, "bit_size", minimum=1)


RecipeOpcode: TypeAlias = (
    RegValueOp
    | SpecialValueOp
    | ConstUOp
    | ConstSOp
    | StaticAddressOp
    | ToAddressOp
    | CfaOp
    | FrameBaseOp
    | AddSConstCheckedOp
    | DerefUOp
    | BitSliceOp
)


@dataclass(frozen=True, slots=True)
class RecipeExpression:
    role: RecipeRole
    opcodes: tuple[RecipeOpcode, ...]
    required_result: RecipeResultKind
    required_bit_width: int | None

    def __post_init__(self) -> None:
        _require_exact_enum(self.role, RecipeRole, "role")
        opcodes = _require_tuple(self.opcodes, "opcodes")
        if not all(isinstance(opcode, _RECIPE_OPCODE_TYPES) for opcode in opcodes):
            raise TypeError("opcodes must contain frozen RecipeOpcode values")
        _require_exact_enum(self.required_result, RecipeResultKind, "required_result")
        if self.required_result is RecipeResultKind.ADDRESS:
            if self.required_bit_width is not None:
                raise ValueError("ADDRESS requires required_bit_width=None")
        else:
            if self.required_bit_width is None:
                raise ValueError("non-address results require required_bit_width")
            _require_int(self.required_bit_width, "required_bit_width", minimum=1)
        object.__setattr__(self, "opcodes", opcodes)


@dataclass(frozen=True, slots=True)
class RecipeRule:
    kind: RecipeRuleKind
    expression: RecipeExpression | None
    reason: str | None

    def __post_init__(self) -> None:
        _require_exact_enum(self.kind, RecipeRuleKind, "kind")
        _require_optional_nonempty(self.reason, "reason")
        if self.kind is RecipeRuleKind.EXPRESSION:
            if not isinstance(self.expression, RecipeExpression) or self.reason is not None:
                raise ValueError("EXPRESSION alone has an expression and no reason")
        elif self.kind in {RecipeRuleKind.UNAVAILABLE, RecipeRuleKind.OPTIMIZED_OUT}:
            if self.expression is not None or self.reason is None:
                raise ValueError("terminal unavailable rules require only a reason")
        elif self.expression is not None or self.reason is not None:
            raise ValueError("SAME/UNDEFINED have neither expression nor reason")


@dataclass(frozen=True, slots=True)
class LocationPieceRule:
    destination_bit_offset: int
    bit_size: int
    expression: RecipeExpression
    source_bit_offset: int

    def __post_init__(self) -> None:
        _require_int(self.destination_bit_offset, "destination_bit_offset")
        _require_int(self.bit_size, "bit_size", minimum=1)
        if not isinstance(self.expression, RecipeExpression):
            raise TypeError("expression must be RecipeExpression")
        _require_int(self.source_bit_offset, "source_bit_offset")


@dataclass(frozen=True, slots=True)
class LocationForm:
    kind: LocationKind
    expression: RecipeExpression | None
    pieces: tuple[LocationPieceRule, ...]
    reason: str | None

    def __post_init__(self) -> None:
        _require_exact_enum(self.kind, LocationKind, "kind")
        pieces = _require_tuple(self.pieces, "pieces")
        if not all(isinstance(piece, LocationPieceRule) for piece in pieces):
            raise TypeError("pieces must contain LocationPieceRule values")
        _require_optional_nonempty(self.reason, "reason")
        if self.kind in {LocationKind.ADDRESS, LocationKind.VALUE}:
            if not isinstance(self.expression, RecipeExpression) or pieces or self.reason is not None:
                raise ValueError("ADDRESS/VALUE require only one expression")
        elif self.kind is LocationKind.PIECES:
            if self.expression is not None or not pieces or self.reason is not None:
                raise ValueError("PIECES requires one or more pieces only")
        elif self.expression is not None or pieces or self.reason is None:
            raise ValueError("terminal location forms require only a reason")
        object.__setattr__(self, "pieces", pieces)


@dataclass(frozen=True, slots=True)
class RecipeScalar:
    signed: bool
    bit_width: int
    value: int

    def __post_init__(self) -> None:
        if not isinstance(self.signed, bool):
            raise TypeError("signed must be bool")
        _require_int(self.bit_width, "bit_width", minimum=1)
        if isinstance(self.value, bool) or not isinstance(self.value, int):
            raise TypeError("value must be an integer")
        lower = -(1 << (self.bit_width - 1)) if self.signed else 0
        upper = (1 << (self.bit_width - (1 if self.signed else 0))) - 1
        if not lower <= self.value <= upper:
            raise ValueError("value does not fit signedness/bit_width")


@dataclass(frozen=True, slots=True)
class RecipeAddress:
    address: HsxAddress

    def __post_init__(self) -> None:
        if not isinstance(self.address, HsxAddress):
            raise TypeError("address must be HsxAddress")


@dataclass(frozen=True, slots=True)
class RecipeRegister:
    register_id: str
    bit_width: int
    unsigned_value: int

    def __post_init__(self) -> None:
        _require_nonempty(self.register_id, "register_id")
        _require_int(self.bit_width, "bit_width", minimum=1)
        _require_int(self.unsigned_value, "unsigned_value")
        if self.unsigned_value >= 1 << self.bit_width:
            raise ValueError("unsigned_value does not fit bit_width")


RecipeValue: TypeAlias = RecipeScalar | RecipeAddress | RecipeRegister


@dataclass(frozen=True, slots=True)
class RecipeEvaluationContext:
    context: InspectionContext
    frame_index: int
    binding: ImageDebugBinding
    bundle_identity: ImageDebugBundleIdentityPayload
    architecture: ArchitectureDescriptor
    abi: AbiDescriptorRef
    pc: HsxAddress
    sp: HsxAddress
    psw: RecipeScalar | None
    recovered_registers: RegisterSet
    cfa: HsxAddress | None
    frame_base: HsxAddress | None

    def __post_init__(self) -> None:
        if not isinstance(self.context, InspectionContext):
            raise TypeError("context must be InspectionContext")
        _require_int(self.frame_index, "frame_index")
        if not isinstance(self.binding, ImageDebugBinding):
            raise TypeError("binding must be ImageDebugBinding")
        if not isinstance(self.bundle_identity, ImageDebugBundleIdentityPayload):
            raise TypeError("bundle_identity must be ImageDebugBundleIdentityPayload")
        if not isinstance(self.architecture, ArchitectureDescriptor):
            raise TypeError("architecture must be ArchitectureDescriptor")
        if not isinstance(self.abi, AbiDescriptorRef):
            raise TypeError("abi must be AbiDescriptorRef")
        if not isinstance(self.pc, HsxAddress) or not isinstance(self.sp, HsxAddress):
            raise TypeError("pc/sp must be HsxAddress")
        if self.psw is not None and not isinstance(self.psw, RecipeScalar):
            raise TypeError("psw must be RecipeScalar or None")
        if not isinstance(self.recovered_registers, RegisterSet):
            raise TypeError("recovered_registers must be RegisterSet")
        if self.cfa is not None and not isinstance(self.cfa, HsxAddress):
            raise TypeError("cfa must be HsxAddress or None")
        if self.frame_base is not None and not isinstance(self.frame_base, HsxAddress):
            raise TypeError("frame_base must be HsxAddress or None")


@dataclass(frozen=True, slots=True)
class RecipeBudget:
    opcodes_remaining: int
    dereferences_remaining: int
    bytes_remaining: int

    def __post_init__(self) -> None:
        _require_int(self.opcodes_remaining, "opcodes_remaining")
        _require_int(self.dereferences_remaining, "dereferences_remaining")
        _require_int(self.bytes_remaining, "bytes_remaining")


@dataclass(frozen=True, slots=True)
class RecipeEvaluationResult:
    status: RecipeEvaluationStatus
    context: InspectionContext
    value: RecipeValue | None
    budget_after: RecipeBudget
    diagnostics: tuple[Diagnostic, ...]

    def __post_init__(self) -> None:
        _require_exact_enum(self.status, RecipeEvaluationStatus, "status")
        if not isinstance(self.context, InspectionContext):
            raise TypeError("context must be InspectionContext")
        if self.value is not None and not isinstance(self.value, (RecipeScalar, RecipeAddress, RecipeRegister)):
            raise TypeError("value must be RecipeValue or None")
        if not isinstance(self.budget_after, RecipeBudget):
            raise TypeError("budget_after must be RecipeBudget")
        diagnostics = _require_tuple(self.diagnostics, "diagnostics")
        if not all(isinstance(item, Diagnostic) for item in diagnostics):
            raise TypeError("diagnostics must contain Diagnostic values")
        if self.status is RecipeEvaluationStatus.COMPLETE:
            if self.value is None:
                raise ValueError("COMPLETE requires one value")
        elif self.value is not None:
            raise ValueError("non-complete evaluation statuses require no value")
        object.__setattr__(self, "diagnostics", diagnostics)


@dataclass(frozen=True, slots=True)
class RecipeLimits:
    opcodes_per_expression: int = 32
    evaluator_stack: int = 8
    dereferences_per_expression: int = 4
    bytes_per_dereference: int = 16
    unwind_frames: int = 64
    unwind_total_opcodes: int = 4096
    unwind_total_dereferenced_bytes: int = 1024
    location_pieces: int = 16
    location_declared_result_bits: int = 4096
    location_total_dereferenced_bytes: int = 512

    def __post_init__(self) -> None:
        expected = (32, 8, 4, 16, 64, 4096, 1024, 16, 4096, 512)
        if tuple(getattr(self, name) for name in self.__dataclass_fields__) != expected:
            raise ValueError("RecipeLimits must equal the exact accepted profile")


@dataclass(frozen=True, slots=True)
class RecipeRequestLimits:
    max_frames: int
    max_pieces: int

    def __post_init__(self) -> None:
        _require_int(self.max_frames, "max_frames", minimum=1)
        _require_int(self.max_pieces, "max_pieces", minimum=1)


@dataclass(frozen=True, slots=True)
class UnwindRow:
    row_id: str
    binding: ImageDebugBinding
    pc_range: HsxAddressRange
    abi: AbiDescriptorRef
    schema: RecipeSchemaRef
    cfa_expression: RecipeExpression
    caller_pc_rule: RecipeRule
    caller_sp_rule: RecipeRule
    caller_frame_base_rule: RecipeRule | None
    register_rules: tuple[tuple[str, RecipeRule], ...]
    boundary: UnwindBoundary
    call_site_adjustment: int | None

    def __post_init__(self) -> None:
        _require_nonempty(self.row_id, "row_id")
        if not isinstance(self.binding, ImageDebugBinding):
            raise TypeError("binding must be ImageDebugBinding")
        if not isinstance(self.pc_range, HsxAddressRange) or self.pc_range.length_units < 1:
            raise ValueError("pc_range must be a non-empty HsxAddressRange")
        if not isinstance(self.abi, AbiDescriptorRef):
            raise TypeError("abi must be AbiDescriptorRef")
        if not isinstance(self.schema, RecipeSchemaRef) or self.schema.schema != "hsx.unwind-recipe/1":
            raise ValueError("schema must be hsx.unwind-recipe/1")
        if not isinstance(self.cfa_expression, RecipeExpression):
            raise TypeError("cfa_expression must be RecipeExpression")
        for rule in (self.caller_pc_rule, self.caller_sp_rule):
            if not isinstance(rule, RecipeRule):
                raise TypeError("caller rules must be RecipeRule")
        if self.caller_frame_base_rule is not None and not isinstance(self.caller_frame_base_rule, RecipeRule):
            raise TypeError("caller_frame_base_rule must be RecipeRule or None")
        register_rules = _require_tuple(self.register_rules, "register_rules")
        checked: list[tuple[str, RecipeRule]] = []
        for entry in register_rules:
            if not isinstance(entry, (tuple, list)) or len(entry) != 2:
                raise TypeError("register_rules entries must be pairs")
            register_id, rule = entry
            _require_nonempty(register_id, "register_id")
            if not isinstance(rule, RecipeRule):
                raise TypeError("register rule must be RecipeRule")
            checked.append((register_id, rule))
        if len({name for name, _ in checked}) != len(checked):
            raise ValueError("register rule IDs must be unique")
        _require_exact_enum(self.boundary, UnwindBoundary, "boundary")
        if self.call_site_adjustment is not None and (
            isinstance(self.call_site_adjustment, bool) or not isinstance(self.call_site_adjustment, int)
        ):
            raise TypeError("call_site_adjustment must be an integer or None")
        object.__setattr__(self, "register_rules", tuple(checked))


@dataclass(frozen=True, slots=True)
class LocationRow:
    row_id: str
    binding: ImageDebugBinding
    symbol_id: str
    lexical_scope_id: str | None
    function_id: str | None
    pc_range: HsxAddressRange
    declared_type_id: str | None
    declared_bit_size: int
    abi: AbiDescriptorRef
    value_byte_order: ByteOrder
    frame_binding: FrameBinding
    schema: RecipeSchemaRef
    location_form: LocationForm

    def __post_init__(self) -> None:
        _require_nonempty(self.row_id, "row_id")
        if not isinstance(self.binding, ImageDebugBinding):
            raise TypeError("binding must be ImageDebugBinding")
        _require_nonempty(self.symbol_id, "symbol_id")
        _require_optional_nonempty(self.lexical_scope_id, "lexical_scope_id")
        _require_optional_nonempty(self.function_id, "function_id")
        if (self.function_id is None) != (self.lexical_scope_id is None):
            raise ValueError("function_id and lexical_scope_id must both be present or absent")
        if not isinstance(self.pc_range, HsxAddressRange) or self.pc_range.length_units < 1:
            raise ValueError("pc_range must be a non-empty HsxAddressRange")
        _require_optional_nonempty(self.declared_type_id, "declared_type_id")
        _require_int(self.declared_bit_size, "declared_bit_size", minimum=1)
        if not isinstance(self.abi, AbiDescriptorRef):
            raise TypeError("abi must be AbiDescriptorRef")
        if not isinstance(self.value_byte_order, ByteOrder):
            raise TypeError("value_byte_order must be ByteOrder")
        _require_exact_enum(self.frame_binding, FrameBinding, "frame_binding")
        if not isinstance(self.schema, RecipeSchemaRef) or self.schema.schema != "hsx.location-recipe/1":
            raise ValueError("schema must be hsx.location-recipe/1")
        if not isinstance(self.location_form, LocationForm):
            raise TypeError("location_form must be LocationForm")


@dataclass(frozen=True, slots=True)
class UnwindFrame:
    context: InspectionContext
    frame_index: int
    pc: HsxAddress
    sp: HsxAddress
    cfa: HsxAddress
    recovered_registers: RegisterSet
    recovered_psw: RegisterValue
    frame_base: HsxAddress | None
    resume_pc: HsxAddress | None
    call_site_pc: HsxAddress | None
    function: FunctionRecord | None
    source: SourceLocation | None
    terminal: bool
    diagnostics: tuple[Diagnostic, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.context, InspectionContext):
            raise TypeError("context must be InspectionContext")
        _require_int(self.frame_index, "frame_index")
        if not all(isinstance(value, HsxAddress) for value in (self.pc, self.sp, self.cfa)):
            raise TypeError("pc/sp/cfa must be HsxAddress")
        if not isinstance(self.recovered_registers, RegisterSet):
            raise TypeError("recovered_registers must be RegisterSet")
        if not isinstance(self.recovered_psw, RegisterValue):
            raise TypeError("recovered_psw must be RegisterValue")
        for name in ("frame_base", "resume_pc", "call_site_pc"):
            value = getattr(self, name)
            if value is not None and not isinstance(value, HsxAddress):
                raise TypeError(f"{name} must be HsxAddress or None")
        if self.function is not None and not isinstance(self.function, FunctionRecord):
            raise TypeError("function must be FunctionRecord or None")
        if self.source is not None and not isinstance(self.source, SourceLocation):
            raise TypeError("source must be SourceLocation or None")
        if not isinstance(self.terminal, bool):
            raise TypeError("terminal must be bool")
        diagnostics = _require_tuple(self.diagnostics, "diagnostics")
        if not all(isinstance(item, Diagnostic) for item in diagnostics):
            raise TypeError("diagnostics must contain Diagnostic values")
        object.__setattr__(self, "diagnostics", diagnostics)


_RECIPE_OPCODE_TYPES = (
    RegValueOp,
    SpecialValueOp,
    ConstUOp,
    ConstSOp,
    StaticAddressOp,
    ToAddressOp,
    CfaOp,
    FrameBaseOp,
    AddSConstCheckedOp,
    DerefUOp,
    BitSliceOp,
)


class RecipeParseError(ValueError):
    """Classified strict-parser failure for a recipe-bearing component."""

    def __init__(self, status: RecipeEvaluationStatus, diagnostic: Diagnostic) -> None:
        super().__init__(diagnostic.message)
        self.status = status
        self.diagnostic = diagnostic


def _parse_failure(status: RecipeEvaluationStatus, code: str, message: str) -> RecipeParseError:
    return RecipeParseError(status, Diagnostic(code, message, component="recipe"))


def _strict_fields(payload: object, required: frozenset[str], kind: str) -> Mapping[str, object]:
    if not isinstance(payload, Mapping):
        raise _parse_failure(
            RecipeEvaluationStatus.CORRUPT,
            "malformed_recipe_record",
            f"{kind} must be a mapping",
        )
    keys = frozenset(payload.keys())
    if not all(isinstance(key, str) for key in keys):
        raise _parse_failure(
            RecipeEvaluationStatus.UNSUPPORTED,
            "unsupported_field",
            f"{kind} contains a non-string field",
        )
    unknown = keys - required
    if unknown:
        raise _parse_failure(
            RecipeEvaluationStatus.UNSUPPORTED,
            "unsupported_field",
            f"{kind} contains unsupported fields {tuple(sorted(unknown))!r}",
        )
    missing = required - keys
    if missing:
        raise _parse_failure(
            RecipeEvaluationStatus.CORRUPT,
            "missing_recipe_field",
            f"{kind} is missing fields {tuple(sorted(missing))!r}",
        )
    return payload


def _parse_enum(value: object, enum_type: type[Enum], field_name: str) -> Enum:
    if not isinstance(value, str):
        raise _parse_failure(
            RecipeEvaluationStatus.CORRUPT,
            "malformed_recipe_field",
            f"{field_name} must be a string",
        )
    try:
        return enum_type(value)
    except ValueError as exc:
        raise _parse_failure(
            RecipeEvaluationStatus.UNSUPPORTED,
            "unsupported_field_value",
            f"{field_name} has unsupported value {value!r}",
        ) from exc


def _construct(factory, *args):
    try:
        return factory(*args)
    except RecipeParseError:
        raise
    except (TypeError, ValueError) as exc:
        raise _parse_failure(
            RecipeEvaluationStatus.CORRUPT,
            "malformed_recipe_field",
            str(exc),
        ) from exc


class RecipeParser:
    """Strict mapping-to-DTO parser; unknown extensions never fall through."""

    @staticmethod
    def parse_opcode(payload: object) -> RecipeOpcode:
        if not isinstance(payload, Mapping):
            raise _parse_failure(
                RecipeEvaluationStatus.CORRUPT,
                "malformed_recipe_opcode",
                "recipe opcode must be a mapping",
            )
        opcode = payload.get("opcode")
        if not isinstance(opcode, str):
            raise _parse_failure(
                RecipeEvaluationStatus.CORRUPT,
                "malformed_recipe_opcode",
                "opcode must be a string",
            )
        shapes = {
            "reg_value": (RegValueOp, ("opcode", "register_id")),
            "special_value": (SpecialValueOp, ("opcode", "special")),
            "const_u": (ConstUOp, ("opcode", "value", "bit_width")),
            "const_s": (ConstSOp, ("opcode", "value", "bit_width")),
            "static_address": (StaticAddressOp, ("opcode", "address")),
            "to_address": (ToAddressOp, ("opcode", "space")),
            "cfa": (CfaOp, ("opcode",)),
            "frame_base": (FrameBaseOp, ("opcode",)),
            "add_sconst_checked": (AddSConstCheckedOp, ("opcode", "signed_delta")),
            "deref_u": (DerefUOp, ("opcode", "byte_length", "byte_order")),
            "bit_slice": (BitSliceOp, ("opcode", "source_bit_offset", "bit_size")),
        }
        shape = shapes.get(opcode)
        if shape is None:
            raise _parse_failure(
                RecipeEvaluationStatus.UNSUPPORTED,
                "unsupported_opcode",
                f"unsupported recipe opcode {opcode!r}",
            )
        factory, fields = shape
        record = _strict_fields(payload, frozenset(fields), opcode)
        values = [record[field] for field in fields]
        if factory is SpecialValueOp:
            values[1] = _parse_enum(values[1], RecipeSpecial, "special")
        elif factory is DerefUOp:
            values[2] = _parse_enum(values[2], ByteOrder, "byte_order")
        return _construct(factory, *values)

    @staticmethod
    def parse_expression(payload: object) -> RecipeExpression:
        fields = frozenset({"role", "opcodes", "required_result", "required_bit_width"})
        record = _strict_fields(payload, fields, "recipe expression")
        raw_opcodes = record["opcodes"]
        try:
            opcodes = _require_tuple(raw_opcodes, "opcodes")
        except (TypeError, ValueError) as exc:
            raise _parse_failure(
                RecipeEvaluationStatus.CORRUPT, "malformed_recipe_field", str(exc)
            ) from exc
        parsed = tuple(
            opcode if isinstance(opcode, _RECIPE_OPCODE_TYPES) else RecipeParser.parse_opcode(opcode)
            for opcode in opcodes
        )
        return _construct(
            RecipeExpression,
            _parse_enum(record["role"], RecipeRole, "role"),
            parsed,
            _parse_enum(record["required_result"], RecipeResultKind, "required_result"),
            record["required_bit_width"],
        )

    @staticmethod
    def parse_rule(payload: object) -> RecipeRule:
        record = _strict_fields(
            payload, frozenset({"kind", "expression", "reason"}), "recipe rule"
        )
        expression = record["expression"]
        if expression is not None and not isinstance(expression, RecipeExpression):
            expression = RecipeParser.parse_expression(expression)
        return _construct(
            RecipeRule,
            _parse_enum(record["kind"], RecipeRuleKind, "kind"),
            expression,
            record["reason"],
        )

    @staticmethod
    def parse_piece(payload: object) -> LocationPieceRule:
        fields = frozenset(
            {"destination_bit_offset", "bit_size", "expression", "source_bit_offset"}
        )
        record = _strict_fields(payload, fields, "location piece")
        expression = record["expression"]
        if not isinstance(expression, RecipeExpression):
            expression = RecipeParser.parse_expression(expression)
        return _construct(
            LocationPieceRule,
            record["destination_bit_offset"],
            record["bit_size"],
            expression,
            record["source_bit_offset"],
        )

    @staticmethod
    def parse_location_form(payload: object) -> LocationForm:
        record = _strict_fields(
            payload, frozenset({"kind", "expression", "pieces", "reason"}), "location form"
        )
        expression = record["expression"]
        if expression is not None and not isinstance(expression, RecipeExpression):
            expression = RecipeParser.parse_expression(expression)
        try:
            raw_pieces = _require_tuple(record["pieces"], "pieces")
        except (TypeError, ValueError) as exc:
            raise _parse_failure(
                RecipeEvaluationStatus.CORRUPT, "malformed_recipe_field", str(exc)
            ) from exc
        pieces = tuple(
            piece if isinstance(piece, LocationPieceRule) else RecipeParser.parse_piece(piece)
            for piece in raw_pieces
        )
        return _construct(
            LocationForm,
            _parse_enum(record["kind"], LocationKind, "kind"),
            expression,
            pieces,
            record["reason"],
        )

    @staticmethod
    def parse_unwind_row(payload: object) -> UnwindRow:
        fields = frozenset(
            {
                "row_id",
                "binding",
                "pc_range",
                "abi",
                "schema",
                "cfa_expression",
                "caller_pc_rule",
                "caller_sp_rule",
                "caller_frame_base_rule",
                "register_rules",
                "boundary",
                "call_site_adjustment",
            }
        )
        record = _strict_fields(payload, fields, "unwind row")
        cfa = record["cfa_expression"]
        if not isinstance(cfa, RecipeExpression):
            cfa = RecipeParser.parse_expression(cfa)
        rules = []
        try:
            raw_rules = _require_tuple(record["register_rules"], "register_rules")
        except (TypeError, ValueError) as exc:
            raise _parse_failure(
                RecipeEvaluationStatus.CORRUPT, "malformed_recipe_field", str(exc)
            ) from exc
        for entry in raw_rules:
            if not isinstance(entry, (tuple, list)) or len(entry) != 2:
                raise _parse_failure(
                    RecipeEvaluationStatus.CORRUPT,
                    "malformed_recipe_field",
                    "register_rules entries must be pairs",
                )
            key, rule = entry
            if not isinstance(rule, RecipeRule):
                rule = RecipeParser.parse_rule(rule)
            rules.append((key, rule))

        def parsed_rule(value: object, *, optional: bool = False) -> RecipeRule | None:
            if value is None and optional:
                return None
            return value if isinstance(value, RecipeRule) else RecipeParser.parse_rule(value)

        return _construct(
            UnwindRow,
            record["row_id"],
            record["binding"],
            record["pc_range"],
            record["abi"],
            record["schema"],
            cfa,
            parsed_rule(record["caller_pc_rule"]),
            parsed_rule(record["caller_sp_rule"]),
            parsed_rule(record["caller_frame_base_rule"], optional=True),
            tuple(rules),
            _parse_enum(record["boundary"], UnwindBoundary, "boundary"),
            record["call_site_adjustment"],
        )

    @staticmethod
    def parse_location_row(payload: object) -> LocationRow:
        fields = frozenset(
            {
                "row_id",
                "binding",
                "symbol_id",
                "lexical_scope_id",
                "function_id",
                "pc_range",
                "declared_type_id",
                "declared_bit_size",
                "abi",
                "value_byte_order",
                "frame_binding",
                "schema",
                "location_form",
            }
        )
        record = _strict_fields(payload, fields, "location row")
        form = record["location_form"]
        if not isinstance(form, LocationForm):
            form = RecipeParser.parse_location_form(form)
        return _construct(
            LocationRow,
            record["row_id"],
            record["binding"],
            record["symbol_id"],
            record["lexical_scope_id"],
            record["function_id"],
            record["pc_range"],
            record["declared_type_id"],
            record["declared_bit_size"],
            record["abi"],
            _parse_enum(record["value_byte_order"], ByteOrder, "value_byte_order"),
            _parse_enum(record["frame_binding"], FrameBinding, "frame_binding"),
            record["schema"],
            form,
        )


def _recipe_diagnostic(
    code: str,
    message: str,
    *,
    row_id: str | None = None,
    frame_index: int | None = None,
    operation_index: int | None = None,
) -> Diagnostic:
    return Diagnostic(
        code,
        message,
        component="recipe",
        row_id=row_id,
        frame_index=frame_index,
        operation_index=operation_index,
    )


def _invalid_address_diagnostic(
    code: str,
    message: str,
    *,
    row_id: str | None = None,
    frame_index: int | None = None,
    operation_index: int | None = None,
) -> tuple[Diagnostic, ...]:
    return (
        _recipe_diagnostic(
            code,
            message,
            row_id=row_id,
            frame_index=frame_index,
            operation_index=operation_index,
        ),
    )


class RecipeComponentValidator:
    """Pure descriptor-aware row/frame checks shared with the later artifact/stack slices."""

    @staticmethod
    def validate_expression(
        expression: RecipeExpression,
        expected_role: RecipeRole,
        architecture: ArchitectureDescriptor,
        limits: RecipeLimits = RecipeLimits(),
        *,
        row_id: str | None = None,
    ) -> tuple[Diagnostic, ...]:
        if not isinstance(expression, RecipeExpression):
            raise TypeError("expression must be RecipeExpression")
        _require_exact_enum(expected_role, RecipeRole, "expected_role")
        if not isinstance(architecture, ArchitectureDescriptor):
            raise TypeError("architecture must be ArchitectureDescriptor")
        if not isinstance(limits, RecipeLimits):
            raise TypeError("limits must be RecipeLimits")
        if expression.role is not expected_role:
            return _invalid_address_diagnostic(
                "recipe_role_mismatch",
                f"expected role {expected_role.value!r}, got {expression.role.value!r}",
                row_id=row_id,
            )
        if len(expression.opcodes) > limits.opcodes_per_expression:
            return _invalid_address_diagnostic(
                "limit_exceeded",
                "expression exceeds opcodes_per_expression",
                row_id=row_id,
            )
        if expression.role is RecipeRole.CFA and any(
            isinstance(opcode, CfaOp) for opcode in expression.opcodes
        ):
            index = next(
                index for index, opcode in enumerate(expression.opcodes) if isinstance(opcode, CfaOp)
            )
            return _invalid_address_diagnostic(
                "cyclic_cfa",
                "a CFA expression cannot recursively consume CFA",
                row_id=row_id,
                operation_index=index,
            )
        for index, opcode in enumerate(expression.opcodes):
            if isinstance(opcode, RegValueOp) and opcode.register_id not in architecture.register_order:
                return _invalid_address_diagnostic(
                    "unknown_register",
                    "reg_value names an undeclared GPR",
                    row_id=row_id,
                    operation_index=index,
                )
            if isinstance(opcode, StaticAddressOp):
                validated = architecture.validate(opcode.address)
                if validated.status is not AddressStatus.VALID:
                    return _invalid_address_diagnostic(
                        "invalid_static_address",
                        validated.diagnostics[0].message,
                        row_id=row_id,
                        operation_index=index,
                    )
            if isinstance(opcode, ToAddressOp) and architecture.space_descriptor(opcode.space) is None:
                return _invalid_address_diagnostic(
                    "unknown_address_space",
                    "to_address names an undeclared address space",
                    row_id=row_id,
                    operation_index=index,
                )
            if isinstance(opcode, DerefUOp) and opcode.byte_length > limits.bytes_per_dereference:
                return _invalid_address_diagnostic(
                    "limit_exceeded",
                    "deref_u exceeds bytes_per_dereference",
                    row_id=row_id,
                    operation_index=index,
                )
        return ()

    @staticmethod
    def validate_unwind_row(
        row: UnwindRow,
        architecture: ArchitectureDescriptor,
        abi: AbiDescriptorRef,
        limits: RecipeLimits = RecipeLimits(),
    ) -> tuple[Diagnostic, ...]:
        if not isinstance(row, UnwindRow):
            raise TypeError("row must be UnwindRow")
        if not isinstance(architecture, ArchitectureDescriptor):
            raise TypeError("architecture must be ArchitectureDescriptor")
        if not isinstance(abi, AbiDescriptorRef):
            raise TypeError("abi must be AbiDescriptorRef")
        if row.abi != abi:
            return _invalid_address_diagnostic(
                "row_abi_mismatch", "unwind row ABI differs", row_id=row.row_id
            )
        if row.pc_range.start.space != architecture.pc_space:
            return _invalid_address_diagnostic(
                "row_pc_space_mismatch", "unwind row is not in pc_space", row_id=row.row_id
            )
        range_result = architecture.range(row.pc_range.start, row.pc_range.length_units)
        if range_result.status is not AddressStatus.VALID:
            return _invalid_address_diagnostic(
                "invalid_row_pc_range", range_result.diagnostics[0].message, row_id=row.row_id
            )
        checks: list[tuple[RecipeExpression, RecipeRole]] = [
            (row.cfa_expression, RecipeRole.CFA)
        ]
        for rule, role in (
            (row.caller_pc_rule, RecipeRole.CALLER_PC),
            (row.caller_sp_rule, RecipeRole.CALLER_SP),
            (row.caller_frame_base_rule, RecipeRole.CALLER_FRAME_BASE),
        ):
            if rule is not None and rule.kind is RecipeRuleKind.EXPRESSION:
                checks.append((rule.expression, role))
        if (
            row.cfa_expression.required_result is not RecipeResultKind.ADDRESS
            or row.cfa_expression.required_bit_width is not None
        ):
            return _invalid_address_diagnostic(
                "invalid_cfa_result", "CFA expression must require ADDRESS", row_id=row.row_id
            )
        for expression, role in checks:
            diagnostics = RecipeComponentValidator.validate_expression(
                expression, role, architecture, limits, row_id=row.row_id
            )
            if diagnostics:
                return diagnostics
            if role in {
                RecipeRole.CALLER_PC,
                RecipeRole.CALLER_SP,
                RecipeRole.CALLER_FRAME_BASE,
            } and expression.required_result is not RecipeResultKind.ADDRESS:
                return _invalid_address_diagnostic(
                    "invalid_caller_rule_result",
                    f"{role.value} expression must require ADDRESS",
                    row_id=row.row_id,
                )
        if row.call_site_adjustment is not None and (
            abi.ref != "hsx.abi.llc-r7-word32/1" or row.call_site_adjustment != -4
        ):
            return _invalid_address_diagnostic(
                "invalid_call_site_adjustment",
                "the selected current ABI admits only checked -4",
                row_id=row.row_id,
            )
        for register_id, rule in row.register_rules:
            if register_id in {"PC", "SP"}:
                return _invalid_address_diagnostic(
                    "special_register_rule_forbidden",
                    "PC/SP are owned by caller_pc_rule/caller_sp_rule",
                    row_id=row.row_id,
                )
            if register_id == "PSW":
                return _invalid_address_diagnostic(
                    "psw_rule_unsupported",
                    "the selected HSX profile has no PSW caller-rule seam",
                    row_id=row.row_id,
                )
            if register_id not in architecture.register_order:
                return _invalid_address_diagnostic(
                    "unknown_register", "register rule names an undeclared GPR", row_id=row.row_id
                )
            if rule.kind not in {RecipeRuleKind.EXPRESSION, RecipeRuleKind.SAME}:
                return _invalid_address_diagnostic(
                    "unsupported_register_rule",
                    "the selected HSX profile admits GPR EXPRESSION/SAME only",
                    row_id=row.row_id,
                )
            if rule.kind is RecipeRuleKind.EXPRESSION:
                expression = rule.expression
                diagnostics = RecipeComponentValidator.validate_expression(
                    expression, RecipeRole.REGISTER, architecture, limits, row_id=row.row_id
                )
                if diagnostics:
                    return diagnostics
                if (
                    expression.required_result is not RecipeResultKind.REGISTER
                    or expression.required_bit_width != architecture.register_width_bits
                ):
                    return _invalid_address_diagnostic(
                        "invalid_register_rule_result",
                        "GPR expressions require exact-width REGISTER results",
                        row_id=row.row_id,
                    )
        return ()

    @staticmethod
    def validate_location_row(
        row: LocationRow,
        variable: SymbolRecord,
        architecture: ArchitectureDescriptor,
        abi: AbiDescriptorRef,
        limits: RecipeLimits = RecipeLimits(),
    ) -> tuple[Diagnostic, ...]:
        if not isinstance(row, LocationRow):
            raise TypeError("row must be LocationRow")
        if not isinstance(variable, SymbolRecord):
            raise TypeError("variable must be SymbolRecord")
        if not isinstance(architecture, ArchitectureDescriptor):
            raise TypeError("architecture must be ArchitectureDescriptor")
        if not isinstance(abi, AbiDescriptorRef):
            raise TypeError("abi must be AbiDescriptorRef")
        if row.abi != abi:
            return _invalid_address_diagnostic(
                "row_abi_mismatch", "location row ABI differs", row_id=row.row_id
            )
        if variable.kind not in {SymbolKind.LOCAL, SymbolKind.GLOBAL, SymbolKind.CONSTANT}:
            return _invalid_address_diagnostic(
                "invalid_location_symbol_kind",
                "only LOCAL/GLOBAL/CONSTANT symbols have LocationRows",
                row_id=row.row_id,
            )
        if (
            row.symbol_id != variable.symbol_id
            or row.function_id != variable.function_id
            or row.lexical_scope_id != variable.lexical_scope_id
        ):
            return _invalid_address_diagnostic(
                "location_symbol_mismatch",
                "LocationRow identity/scope differs from SymbolRecord",
                row_id=row.row_id,
            )
        if row.declared_type_id != variable.type_id:
            return _invalid_address_diagnostic(
                "location_type_mismatch",
                "LocationRow declared type differs from SymbolRecord",
                row_id=row.row_id,
            )
        if row.declared_bit_size > limits.location_declared_result_bits:
            return _invalid_address_diagnostic(
                "limit_exceeded",
                "declared result exceeds location_declared_result_bits",
                row_id=row.row_id,
            )
        if row.pc_range.start.space != architecture.pc_space:
            return _invalid_address_diagnostic(
                "row_pc_space_mismatch", "location row is not in pc_space", row_id=row.row_id
            )
        range_result = architecture.range(row.pc_range.start, row.pc_range.length_units)
        if range_result.status is not AddressStatus.VALID:
            return _invalid_address_diagnostic(
                "invalid_row_pc_range", range_result.diagnostics[0].message, row_id=row.row_id
            )
        form = row.location_form
        expressions: list[RecipeExpression] = []
        if form.expression is not None:
            expressions.append(form.expression)
        expressions.extend(piece.expression for piece in form.pieces)
        for expression in expressions:
            diagnostics = RecipeComponentValidator.validate_expression(
                expression, RecipeRole.LOCATION, architecture, limits, row_id=row.row_id
            )
            if diagnostics:
                return diagnostics
        if form.kind is LocationKind.ADDRESS:
            if form.expression.required_result is not RecipeResultKind.ADDRESS:
                return _invalid_address_diagnostic(
                    "invalid_location_result",
                    "ADDRESS location requires an address result",
                    row_id=row.row_id,
                )
        elif form.kind is LocationKind.VALUE:
            expression = form.expression
            if (
                expression.required_result
                not in {
                    RecipeResultKind.UNSIGNED_SCALAR,
                    RecipeResultKind.SIGNED_SCALAR,
                    RecipeResultKind.REGISTER,
                }
                or expression.required_bit_width != row.declared_bit_size
            ):
                return _invalid_address_diagnostic(
                    "invalid_location_result",
                    "VALUE location must match the declared scalar/register width",
                    row_id=row.row_id,
                )
        elif form.kind is LocationKind.PIECES:
            ordered = tuple(sorted(form.pieces, key=lambda piece: piece.destination_bit_offset))
            if ordered != form.pieces:
                return _invalid_address_diagnostic(
                    "malformed_piece_coverage",
                    "pieces must be ordered by destination_bit_offset",
                    row_id=row.row_id,
                )
            previous_end = 0
            for piece in form.pieces:
                if piece.destination_bit_offset < previous_end:
                    return _invalid_address_diagnostic(
                        "malformed_piece_coverage",
                        "piece destination ranges overlap",
                        row_id=row.row_id,
                    )
                end = piece.destination_bit_offset + piece.bit_size
                if end > row.declared_bit_size:
                    return _invalid_address_diagnostic(
                        "malformed_piece_coverage",
                        "piece destination range exceeds the declared value",
                        row_id=row.row_id,
                    )
                expression = piece.expression
                if (
                    expression.required_result
                    not in {
                        RecipeResultKind.UNSIGNED_SCALAR,
                        RecipeResultKind.SIGNED_SCALAR,
                        RecipeResultKind.REGISTER,
                    }
                    or expression.required_bit_width is None
                    or piece.source_bit_offset + piece.bit_size
                    > expression.required_bit_width
                ):
                    return _invalid_address_diagnostic(
                        "malformed_piece_source",
                        "piece source range exceeds its scalar/register result",
                        row_id=row.row_id,
                    )
                previous_end = end
        return ()

    @staticmethod
    def validate_unwind_frame(
        frame: UnwindFrame, architecture: ArchitectureDescriptor
    ) -> tuple[Diagnostic, ...]:
        if not isinstance(frame, UnwindFrame):
            raise TypeError("frame must be UnwindFrame")
        if not isinstance(architecture, ArchitectureDescriptor):
            raise TypeError("architecture must be ArchitectureDescriptor")
        registers = frame.recovered_registers.registers
        ids = tuple(register.register_id for register in registers)
        if ids != architecture.register_order:
            return _invalid_address_diagnostic(
                "invalid_recovered_register_order",
                "recovered GPRs must exactly equal architecture.register_order",
                frame_index=frame.frame_index,
            )
        if any(register.bit_width != architecture.register_width_bits for register in registers):
            return _invalid_address_diagnostic(
                "invalid_recovered_register_width",
                "every recovered GPR must have the descriptor width",
                frame_index=frame.frame_index,
            )
        psw = frame.recovered_psw
        if psw.register_id != "PSW" or psw.bit_width != architecture.psw_width_bits:
            return _invalid_address_diagnostic(
                "invalid_recovered_psw",
                "recovered_psw must be exact descriptor PSW evidence",
                frame_index=frame.frame_index,
            )
        if frame.frame_index > 0 and psw.available:
            return _invalid_address_diagnostic(
                "psw_rule_unsupported",
                "non-top PSW must be unavailable without an admitted caller-rule seam",
                frame_index=frame.frame_index,
            )
        address_checks = (
            (frame.pc, architecture.pc_space, Permission.EXECUTE, "pc"),
            (frame.sp, architecture.sp_space, None, "sp"),
            (frame.cfa, architecture.sp_space, None, "cfa"),
        )
        for address, space, permission, name in address_checks:
            if address.space != space:
                return _invalid_address_diagnostic(
                    "invalid_frame_address",
                    f"frame {name} uses the wrong address space",
                    frame_index=frame.frame_index,
                )
            result = architecture.validate(address, permission)
            if result.status is not AddressStatus.VALID:
                return _invalid_address_diagnostic(
                    "invalid_frame_address",
                    f"frame {name}: {result.diagnostics[0].message}",
                    frame_index=frame.frame_index,
                )
        for name in ("frame_base", "resume_pc", "call_site_pc"):
            address = getattr(frame, name)
            if address is None:
                continue
            expected_space = architecture.sp_space if name == "frame_base" else architecture.pc_space
            permission = None if name == "frame_base" else Permission.EXECUTE
            if address.space != expected_space or architecture.validate(address, permission).status is not AddressStatus.VALID:
                return _invalid_address_diagnostic(
                    "invalid_frame_address",
                    f"frame {name} is invalid for the descriptor",
                    frame_index=frame.frame_index,
                )
        return ()


class RecipeEvaluator:
    @staticmethod
    def _result(
        evaluation: RecipeEvaluationContext,
        status: RecipeEvaluationStatus,
        budget: RecipeBudget,
        code: str | None = None,
        message: str = "",
        *,
        value: RecipeValue | None = None,
        operation_index: int | None = None,
        diagnostics: tuple[Diagnostic, ...] | None = None,
    ) -> RecipeEvaluationResult:
        if diagnostics is None:
            diagnostics = (
                ()
                if code is None
                else (
                    _recipe_diagnostic(
                        code,
                        message,
                        frame_index=evaluation.frame_index,
                        operation_index=operation_index,
                    ),
                )
            )
        return RecipeEvaluationResult(
            status=status,
            context=evaluation.context,
            value=value,
            budget_after=budget,
            diagnostics=diagnostics,
        )

    @staticmethod
    def _validate_context(
        evaluation: RecipeEvaluationContext,
    ) -> tuple[Diagnostic, ...]:
        architecture = evaluation.architecture
        registers = evaluation.recovered_registers.registers
        if tuple(register.register_id for register in registers) != architecture.register_order:
            return _invalid_address_diagnostic(
                "invalid_recovered_register_order",
                "evaluation recovered GPRs must exactly equal architecture.register_order",
                frame_index=evaluation.frame_index,
            )
        if any(register.bit_width != architecture.register_width_bits for register in registers):
            return _invalid_address_diagnostic(
                "invalid_recovered_register_width",
                "evaluation recovered GPRs have the wrong width",
                frame_index=evaluation.frame_index,
            )
        if evaluation.psw is not None and (
            evaluation.psw.signed
            or evaluation.psw.bit_width != architecture.psw_width_bits
            or evaluation.frame_index > 0
        ):
            return _invalid_address_diagnostic(
                "invalid_recovered_psw",
                "PSW must be an exact-width unsigned top-frame value",
                frame_index=evaluation.frame_index,
            )
        for address, space, permission, name in (
            (evaluation.pc, architecture.pc_space, Permission.EXECUTE, "pc"),
            (evaluation.sp, architecture.sp_space, None, "sp"),
        ):
            if address.space != space:
                return _invalid_address_diagnostic(
                    "invalid_evaluation_address",
                    f"evaluation {name} uses the wrong space",
                    frame_index=evaluation.frame_index,
                )
            result = architecture.validate(address, permission)
            if result.status is not AddressStatus.VALID:
                return _invalid_address_diagnostic(
                    "invalid_evaluation_address",
                    f"evaluation {name}: {result.diagnostics[0].message}",
                    frame_index=evaluation.frame_index,
                )
        for name in ("cfa", "frame_base"):
            address = getattr(evaluation, name)
            if address is not None and (
                address.space != architecture.sp_space
                or architecture.validate(address).status is not AddressStatus.VALID
            ):
                return _invalid_address_diagnostic(
                    "invalid_evaluation_address",
                    f"evaluation {name} is invalid for sp_space",
                    frame_index=evaluation.frame_index,
                )
        return ()

    @staticmethod
    def evaluate(
        evaluation: RecipeEvaluationContext,
        expression: RecipeExpression,
        read_port: SnapshotReadPort,
        limits: RecipeLimits,
        budget: RecipeBudget,
    ) -> RecipeEvaluationResult:
        if not isinstance(evaluation, RecipeEvaluationContext):
            raise TypeError("evaluation must be RecipeEvaluationContext")
        if not isinstance(expression, RecipeExpression):
            raise TypeError("expression must be RecipeExpression")
        if not isinstance(limits, RecipeLimits):
            raise TypeError("limits must be RecipeLimits")
        if not isinstance(budget, RecipeBudget):
            raise TypeError("budget must be RecipeBudget")

        # The portable binding is always fenced before expression, budget, opcode, or read work.
        binding_result = DebugBindingValidator.validate(
            evaluation.binding,
            evaluation.bundle_identity,
            evaluation.architecture,
            evaluation.abi,
        )
        if binding_result.status is not ResolutionStatus.RESOLVED:
            return RecipeEvaluator._result(
                evaluation,
                RecipeEvaluationStatus.ARTIFACT_MISMATCH,
                budget,
                diagnostics=binding_result.diagnostics,
            )
        if evaluation.binding.payload.loaded_image_ref != evaluation.context.image:
            return RecipeEvaluator._result(
                evaluation,
                RecipeEvaluationStatus.ARTIFACT_MISMATCH,
                budget,
                "binding_loaded_image_mismatch",
                "evaluation context image differs from the debug binding",
            )

        context_diagnostics = RecipeEvaluator._validate_context(evaluation)
        if context_diagnostics:
            return RecipeEvaluator._result(
                evaluation,
                RecipeEvaluationStatus.CORRUPT,
                budget,
                diagnostics=context_diagnostics,
            )
        if len(expression.opcodes) > limits.opcodes_per_expression:
            return RecipeEvaluator._result(
                evaluation,
                RecipeEvaluationStatus.UNSUPPORTED,
                budget,
                "limit_exceeded",
                "expression exceeds opcodes_per_expression",
            )
        if expression.role is RecipeRole.CFA and any(
            isinstance(opcode, CfaOp) for opcode in expression.opcodes
        ):
            index = next(
                index for index, opcode in enumerate(expression.opcodes) if isinstance(opcode, CfaOp)
            )
            return RecipeEvaluator._result(
                evaluation,
                RecipeEvaluationStatus.CORRUPT,
                budget,
                "cyclic_cfa",
                "a CFA expression cannot recursively consume CFA",
                operation_index=index,
            )

        current_budget = budget
        stack: list[RecipeValue] = []
        dereferences_used = 0
        registers = {
            register.register_id: register
            for register in evaluation.recovered_registers.registers
        }

        def failure(
            status: RecipeEvaluationStatus,
            code: str,
            message: str,
            operation_index: int,
            *,
            diagnostics: tuple[Diagnostic, ...] | None = None,
        ) -> RecipeEvaluationResult:
            return RecipeEvaluator._result(
                evaluation,
                status,
                current_budget,
                code,
                message,
                operation_index=operation_index,
                diagnostics=diagnostics,
            )

        def push(value: RecipeValue, operation_index: int) -> RecipeEvaluationResult | None:
            if len(stack) >= limits.evaluator_stack:
                return failure(
                    RecipeEvaluationStatus.CORRUPT,
                    "recipe_stack_overflow",
                    "recipe evaluator stack depth exceeded",
                    operation_index,
                )
            stack.append(value)
            return None

        for operation_index, opcode in enumerate(expression.opcodes):
            if current_budget.opcodes_remaining < 1:
                return failure(
                    RecipeEvaluationStatus.UNSUPPORTED,
                    "limit_exceeded",
                    "opcode budget exhausted before operation",
                    operation_index,
                )
            current_budget = RecipeBudget(
                current_budget.opcodes_remaining - 1,
                current_budget.dereferences_remaining,
                current_budget.bytes_remaining,
            )

            output: RecipeValue
            if isinstance(opcode, RegValueOp):
                register = registers.get(opcode.register_id)
                if register is None:
                    return failure(
                        RecipeEvaluationStatus.CORRUPT,
                        "unknown_register",
                        "reg_value names an undeclared recovered GPR",
                        operation_index,
                    )
                if not register.available:
                    return failure(
                        RecipeEvaluationStatus.UNAVAILABLE,
                        "register_unavailable",
                        "selected-frame recovered register is unavailable",
                        operation_index,
                    )
                output = RecipeRegister(
                    register.register_id,
                    register.bit_width,
                    register.unsigned_value,
                )
            elif isinstance(opcode, SpecialValueOp):
                if opcode.special is RecipeSpecial.PC:
                    output = RecipeAddress(evaluation.pc)
                elif opcode.special is RecipeSpecial.SP:
                    output = RecipeAddress(evaluation.sp)
                else:
                    if evaluation.psw is None:
                        return failure(
                            RecipeEvaluationStatus.UNAVAILABLE,
                            "psw_unavailable",
                            "selected-frame PSW is unavailable",
                            operation_index,
                        )
                    output = evaluation.psw
            elif isinstance(opcode, ConstUOp):
                try:
                    output = RecipeScalar(False, opcode.bit_width, opcode.value)
                except (TypeError, ValueError):
                    return failure(
                        RecipeEvaluationStatus.CORRUPT,
                        "invalid_scalar",
                        "const_u does not fit its declared width",
                        operation_index,
                    )
            elif isinstance(opcode, ConstSOp):
                try:
                    output = RecipeScalar(True, opcode.bit_width, opcode.value)
                except (TypeError, ValueError):
                    return failure(
                        RecipeEvaluationStatus.CORRUPT,
                        "invalid_scalar",
                        "const_s does not fit its declared width",
                        operation_index,
                    )
            elif isinstance(opcode, StaticAddressOp):
                result = evaluation.architecture.validate(opcode.address)
                if result.status is not AddressStatus.VALID:
                    return failure(
                        RecipeEvaluationStatus.CORRUPT,
                        "invalid_static_address",
                        result.diagnostics[0].message,
                        operation_index,
                    )
                output = RecipeAddress(opcode.address)
            elif isinstance(opcode, ToAddressOp):
                if not stack:
                    return failure(
                        RecipeEvaluationStatus.CORRUPT,
                        "recipe_stack_underflow",
                        "to_address requires one scalar",
                        operation_index,
                    )
                source = stack.pop()
                if not isinstance(source, RecipeScalar):
                    return failure(
                        RecipeEvaluationStatus.CORRUPT,
                        "recipe_type_mismatch",
                        "to_address requires RecipeScalar",
                        operation_index,
                    )
                if source.value < 0:
                    return failure(
                        RecipeEvaluationStatus.CORRUPT,
                        "negative_address",
                        "to_address requires a non-negative scalar",
                        operation_index,
                    )
                candidate = HsxAddress(opcode.space, source.value)
                result = evaluation.architecture.validate(candidate)
                if result.status is not AddressStatus.VALID:
                    return failure(
                        RecipeEvaluationStatus.CORRUPT,
                        "invalid_address_conversion",
                        result.diagnostics[0].message,
                        operation_index,
                    )
                output = RecipeAddress(candidate)
            elif isinstance(opcode, CfaOp):
                if expression.role is RecipeRole.CFA:
                    return failure(
                        RecipeEvaluationStatus.CORRUPT,
                        "cyclic_cfa",
                        "CFA expression recursively consumes CFA",
                        operation_index,
                    )
                if evaluation.cfa is None:
                    return failure(
                        RecipeEvaluationStatus.CORRUPT,
                        "cfa_not_computed",
                        "dependent expression requires an already-computed CFA",
                        operation_index,
                    )
                output = RecipeAddress(evaluation.cfa)
            elif isinstance(opcode, FrameBaseOp):
                if evaluation.frame_base is None:
                    return failure(
                        RecipeEvaluationStatus.UNAVAILABLE,
                        "frame_base_unavailable",
                        "selected-frame frame base is unavailable",
                        operation_index,
                    )
                output = RecipeAddress(evaluation.frame_base)
            elif isinstance(opcode, AddSConstCheckedOp):
                if not stack:
                    return failure(
                        RecipeEvaluationStatus.CORRUPT,
                        "recipe_stack_underflow",
                        "add_sconst_checked requires one value",
                        operation_index,
                    )
                source = stack.pop()
                if isinstance(source, RecipeAddress):
                    delta = opcode.signed_delta
                    if delta < 0:
                        result = evaluation.architecture.subtract(
                            source.address, -delta, AddressArithmeticMode.CHECKED
                        )
                    else:
                        result = evaluation.architecture.add(
                            source.address, delta, AddressArithmeticMode.CHECKED
                        )
                    if result.status is not AddressStatus.VALID:
                        return failure(
                            RecipeEvaluationStatus.CORRUPT,
                            "checked_add_failed",
                            result.diagnostics[0].message,
                            operation_index,
                        )
                    output = RecipeAddress(result.value)
                elif isinstance(source, RecipeScalar):
                    candidate = source.value + opcode.signed_delta
                    try:
                        output = RecipeScalar(source.signed, source.bit_width, candidate)
                    except (TypeError, ValueError):
                        return failure(
                            RecipeEvaluationStatus.CORRUPT,
                            "checked_add_failed",
                            "scalar addition exceeds its declared width",
                            operation_index,
                        )
                else:
                    return failure(
                        RecipeEvaluationStatus.CORRUPT,
                        "recipe_type_mismatch",
                        "add_sconst_checked accepts only address or scalar",
                        operation_index,
                    )
            elif isinstance(opcode, DerefUOp):
                if not stack:
                    return failure(
                        RecipeEvaluationStatus.CORRUPT,
                        "recipe_stack_underflow",
                        "deref_u requires one address",
                        operation_index,
                    )
                source = stack.pop()
                if not isinstance(source, RecipeAddress):
                    return failure(
                        RecipeEvaluationStatus.CORRUPT,
                        "recipe_type_mismatch",
                        "deref_u requires RecipeAddress",
                        operation_index,
                    )
                if (
                    dereferences_used >= limits.dereferences_per_expression
                    or current_budget.dereferences_remaining < 1
                    or opcode.byte_length > limits.bytes_per_dereference
                    or current_budget.bytes_remaining < opcode.byte_length
                ):
                    return failure(
                        RecipeEvaluationStatus.UNSUPPORTED,
                        "limit_exceeded",
                        "dereference or byte budget exhausted before operation",
                        operation_index,
                    )
                current_budget = RecipeBudget(
                    current_budget.opcodes_remaining,
                    current_budget.dereferences_remaining - 1,
                    current_budget.bytes_remaining - opcode.byte_length,
                )
                dereferences_used += 1
                units = evaluation.architecture.units_for_bytes(
                    source.address.space, opcode.byte_length
                )
                if units.status is AddressStatus.UNIT_CONVERSION_UNSUPPORTED:
                    return failure(
                        RecipeEvaluationStatus.UNSUPPORTED,
                        "unit_conversion_unsupported",
                        units.diagnostics[0].message,
                        operation_index,
                    )
                if units.status is not AddressStatus.VALID:
                    return failure(
                        RecipeEvaluationStatus.CORRUPT,
                        "invalid_dereference_length",
                        units.diagnostics[0].message,
                        operation_index,
                    )
                requested_range = evaluation.architecture.range(
                    source.address, units.value, Permission.READ
                )
                if requested_range.status is not AddressStatus.VALID:
                    return failure(
                        RecipeEvaluationStatus.CORRUPT,
                        "invalid_dereference_address",
                        requested_range.diagnostics[0].message,
                        operation_index,
                    )
                read_set = require_snapshot_read_set(evaluation.context, "memory")
                if read_set.status is not InspectionStatus.COMPLETE:
                    return failure(
                        RecipeEvaluationStatus.UNAVAILABLE,
                        "snapshot_memory_unavailable",
                        read_set.diagnostics[0].message,
                        operation_index,
                    )
                try:
                    read_result = read_port.read_memory(
                        evaluation.context, source.address, opcode.byte_length
                    )
                except Exception as exc:  # A port exception is a contract failure, not fallback authority.
                    return failure(
                        RecipeEvaluationStatus.CORRUPT,
                        "snapshot_read_contract",
                        f"snapshot memory port raised {type(exc).__name__}",
                        operation_index,
                    )
                if not isinstance(read_result, InspectionResult):
                    return failure(
                        RecipeEvaluationStatus.CORRUPT,
                        "snapshot_read_contract",
                        "snapshot memory port returned a non-InspectionResult",
                        operation_index,
                    )
                read_result = fence_snapshot_result(evaluation.context, read_result)
                status_map = {
                    InspectionStatus.STALE: RecipeEvaluationStatus.STALE,
                    InspectionStatus.ARTIFACT_MISMATCH: RecipeEvaluationStatus.ARTIFACT_MISMATCH,
                    InspectionStatus.UNSUPPORTED: RecipeEvaluationStatus.UNSUPPORTED,
                    InspectionStatus.CORRUPT: RecipeEvaluationStatus.CORRUPT,
                    InspectionStatus.UNAVAILABLE: RecipeEvaluationStatus.UNAVAILABLE,
                    InspectionStatus.PARTIAL: RecipeEvaluationStatus.UNAVAILABLE,
                }
                if read_result.status is not InspectionStatus.COMPLETE:
                    mapped = status_map.get(read_result.status, RecipeEvaluationStatus.CORRUPT)
                    diagnostics = read_result.diagnostics or (
                        _recipe_diagnostic(
                            "snapshot_read_failed",
                            "snapshot memory read did not complete",
                            frame_index=evaluation.frame_index,
                            operation_index=operation_index,
                        ),
                    )
                    return failure(
                        mapped,
                        "snapshot_read_failed",
                        "snapshot memory read did not complete",
                        operation_index,
                        diagnostics=diagnostics,
                    )
                block = read_result.value
                if (
                    not isinstance(block, MemoryBlock)
                    or block.start != source.address
                    or block.requested_length != opcode.byte_length
                    or any(
                        segment.status is not MemorySegmentStatus.COMPLETE
                        for segment in block.segments
                    )
                ):
                    return failure(
                        RecipeEvaluationStatus.CORRUPT,
                        "snapshot_read_contract",
                        "complete memory result does not match the exact request",
                        operation_index,
                    )
                raw = b"".join(segment.data for segment in block.segments)
                if len(raw) != opcode.byte_length:
                    return failure(
                        RecipeEvaluationStatus.CORRUPT,
                        "snapshot_read_contract",
                        "complete memory result has the wrong byte length",
                        operation_index,
                    )
                output = RecipeScalar(
                    False,
                    opcode.byte_length * 8,
                    int.from_bytes(raw, byteorder=opcode.byte_order.value, signed=False),
                )
            elif isinstance(opcode, BitSliceOp):
                if not stack:
                    return failure(
                        RecipeEvaluationStatus.CORRUPT,
                        "recipe_stack_underflow",
                        "bit_slice requires one scalar/register",
                        operation_index,
                    )
                source = stack.pop()
                if isinstance(source, RecipeScalar):
                    width = source.bit_width
                    unsigned = source.value % (1 << width)
                elif isinstance(source, RecipeRegister):
                    width = source.bit_width
                    unsigned = source.unsigned_value
                else:
                    return failure(
                        RecipeEvaluationStatus.CORRUPT,
                        "recipe_type_mismatch",
                        "bit_slice accepts only scalar/register",
                        operation_index,
                    )
                if opcode.source_bit_offset + opcode.bit_size > width:
                    return failure(
                        RecipeEvaluationStatus.CORRUPT,
                        "invalid_bit_slice",
                        "bit_slice exceeds its input width",
                        operation_index,
                    )
                mask = (1 << opcode.bit_size) - 1
                output = RecipeScalar(
                    False,
                    opcode.bit_size,
                    (unsigned >> opcode.source_bit_offset) & mask,
                )
            else:  # pragma: no cover - construction fences the closed union.
                return failure(
                    RecipeEvaluationStatus.UNSUPPORTED,
                    "unsupported_opcode",
                    "unsupported recipe opcode",
                    operation_index,
                )

            overflow = push(output, operation_index)
            if overflow is not None:
                return overflow

        if len(stack) != 1:
            return RecipeEvaluator._result(
                evaluation,
                RecipeEvaluationStatus.CORRUPT,
                current_budget,
                "invalid_final_stack",
                "recipe must finish with exactly one value",
            )
        value = stack[0]
        matches = False
        if expression.required_result is RecipeResultKind.ADDRESS:
            matches = isinstance(value, RecipeAddress) and expression.required_bit_width is None
        elif expression.required_result is RecipeResultKind.REGISTER:
            matches = (
                isinstance(value, RecipeRegister)
                and value.bit_width == expression.required_bit_width
            )
        elif expression.required_result is RecipeResultKind.UNSIGNED_SCALAR:
            matches = (
                isinstance(value, RecipeScalar)
                and not value.signed
                and value.bit_width == expression.required_bit_width
            )
        elif expression.required_result is RecipeResultKind.SIGNED_SCALAR:
            matches = (
                isinstance(value, RecipeScalar)
                and value.signed
                and value.bit_width == expression.required_bit_width
            )
        if not matches:
            return RecipeEvaluator._result(
                evaluation,
                RecipeEvaluationStatus.CORRUPT,
                current_budget,
                "recipe_result_mismatch",
                "final recipe value does not match required_result/width",
            )
        return RecipeEvaluator._result(
            evaluation,
            RecipeEvaluationStatus.COMPLETE,
            current_budget,
            value=value,
        )


class LocationEvaluator:
    @staticmethod
    def _inspection_failure(
        context: InspectionContext,
        status: InspectionStatus,
        code: str,
        message: str,
        *,
        row_id: str | None = None,
        frame_index: int | None = None,
        diagnostics: tuple[Diagnostic, ...] | None = None,
    ) -> InspectionResult[EvaluatedValue]:
        if diagnostics is None:
            diagnostics = (
                _recipe_diagnostic(
                    code,
                    message,
                    row_id=row_id,
                    frame_index=frame_index,
                ),
            )
        return InspectionResult(status, context, None, diagnostics)

    @staticmethod
    def _terminal_value(
        variable: SymbolRecord,
        row: LocationRow,
        availability: ValueAvailability,
        display: str,
    ) -> EvaluatedValue:
        return EvaluatedValue(
            symbol_id=variable.symbol_id,
            name=variable.name,
            declared_type_id=row.declared_type_id,
            display_value=display,
            raw_bytes=None,
            bit_size=row.declared_bit_size,
            location_status=availability,
            pieces=(),
        )

    @staticmethod
    def _map_recipe_failure(
        context: InspectionContext,
        variable: SymbolRecord,
        row: LocationRow,
        result: RecipeEvaluationResult,
    ) -> InspectionResult[EvaluatedValue]:
        if result.status is RecipeEvaluationStatus.UNAVAILABLE:
            reason = result.diagnostics[0].code if result.diagnostics else "unavailable"
            value = LocationEvaluator._terminal_value(
                variable,
                row,
                ValueAvailability.UNAVAILABLE,
                f"<{reason}>",
            )
            return InspectionResult(InspectionStatus.COMPLETE, context, value, result.diagnostics)
        status = {
            RecipeEvaluationStatus.UNSUPPORTED: InspectionStatus.UNSUPPORTED,
            RecipeEvaluationStatus.CORRUPT: InspectionStatus.CORRUPT,
            RecipeEvaluationStatus.STALE: InspectionStatus.STALE,
            RecipeEvaluationStatus.ARTIFACT_MISMATCH: InspectionStatus.ARTIFACT_MISMATCH,
        }.get(result.status, InspectionStatus.CORRUPT)
        return LocationEvaluator._inspection_failure(
            context,
            status,
            "recipe_evaluation_failed",
            "location recipe evaluation failed",
            row_id=row.row_id,
            diagnostics=result.diagnostics,
        )

    @staticmethod
    def _read_exact_memory(
        context: InspectionContext,
        frame: UnwindFrame,
        row: LocationRow,
        address: HsxAddress,
        byte_length: int,
        read_port: SnapshotReadPort,
        architecture: ArchitectureDescriptor,
    ) -> tuple[InspectionStatus, bytes | None, tuple[Diagnostic, ...]]:
        units = architecture.units_for_bytes(address.space, byte_length)
        if units.status is AddressStatus.UNIT_CONVERSION_UNSUPPORTED:
            return (
                InspectionStatus.UNSUPPORTED,
                None,
                (
                    _recipe_diagnostic(
                        "unit_conversion_unsupported",
                        units.diagnostics[0].message,
                        row_id=row.row_id,
                        frame_index=frame.frame_index,
                    ),
                ),
            )
        if units.status is not AddressStatus.VALID:
            return (
                InspectionStatus.CORRUPT,
                None,
                (
                    _recipe_diagnostic(
                        "invalid_location_read_length",
                        units.diagnostics[0].message,
                        row_id=row.row_id,
                        frame_index=frame.frame_index,
                    ),
                ),
            )
        checked = architecture.range(address, units.value, Permission.READ)
        if checked.status is not AddressStatus.VALID:
            return (
                InspectionStatus.CORRUPT,
                None,
                (
                    _recipe_diagnostic(
                        "invalid_location_read_address",
                        checked.diagnostics[0].message,
                        row_id=row.row_id,
                        frame_index=frame.frame_index,
                    ),
                ),
            )
        read_set = require_snapshot_read_set(context, "memory")
        if read_set.status is not InspectionStatus.COMPLETE:
            return InspectionStatus.UNAVAILABLE, None, read_set.diagnostics
        try:
            result = read_port.read_memory(context, address, byte_length)
        except Exception as exc:  # No alternate read path or live fallback is permitted.
            return (
                InspectionStatus.CORRUPT,
                None,
                (
                    _recipe_diagnostic(
                        "snapshot_read_contract",
                        f"snapshot memory port raised {type(exc).__name__}",
                        row_id=row.row_id,
                        frame_index=frame.frame_index,
                    ),
                ),
            )
        if not isinstance(result, InspectionResult):
            return (
                InspectionStatus.CORRUPT,
                None,
                (
                    _recipe_diagnostic(
                        "snapshot_read_contract",
                        "snapshot memory port returned a non-InspectionResult",
                        row_id=row.row_id,
                        frame_index=frame.frame_index,
                    ),
                ),
            )
        result = fence_snapshot_result(context, result)
        if result.status is not InspectionStatus.COMPLETE:
            mapped = (
                InspectionStatus.UNAVAILABLE
                if result.status is InspectionStatus.PARTIAL
                else result.status
            )
            if mapped not in {
                InspectionStatus.UNAVAILABLE,
                InspectionStatus.STALE,
                InspectionStatus.ARTIFACT_MISMATCH,
                InspectionStatus.UNSUPPORTED,
                InspectionStatus.CORRUPT,
            }:
                mapped = InspectionStatus.CORRUPT
            diagnostics = result.diagnostics or (
                _recipe_diagnostic(
                    "snapshot_read_failed",
                    "snapshot memory read did not complete",
                    row_id=row.row_id,
                    frame_index=frame.frame_index,
                ),
            )
            return mapped, None, diagnostics
        block = result.value
        if (
            not isinstance(block, MemoryBlock)
            or block.start != address
            or block.requested_length != byte_length
            or any(
                segment.status is not MemorySegmentStatus.COMPLETE
                for segment in block.segments
            )
        ):
            return (
                InspectionStatus.CORRUPT,
                None,
                (
                    _recipe_diagnostic(
                        "snapshot_read_contract",
                        "complete memory result does not match the exact request",
                        row_id=row.row_id,
                        frame_index=frame.frame_index,
                    ),
                ),
            )
        raw = b"".join(segment.data for segment in block.segments)
        if len(raw) != byte_length:
            return (
                InspectionStatus.CORRUPT,
                None,
                (
                    _recipe_diagnostic(
                        "snapshot_read_contract",
                        "complete memory result has the wrong byte length",
                        row_id=row.row_id,
                        frame_index=frame.frame_index,
                    ),
                ),
            )
        return InspectionStatus.COMPLETE, raw, ()

    @staticmethod
    def evaluate(
        context: InspectionContext,
        frame: UnwindFrame,
        index: object,
        variable: SymbolRecord,
        row: LocationRow,
        read_port: SnapshotReadPort,
        architecture: ArchitectureDescriptor,
        abi: AbiDescriptorRef,
        profile_limits: RecipeLimits,
        request_limits: RecipeRequestLimits,
    ) -> InspectionResult[EvaluatedValue]:
        if not isinstance(context, InspectionContext):
            raise TypeError("context must be InspectionContext")
        if not isinstance(frame, UnwindFrame):
            raise TypeError("frame must be UnwindFrame")
        if not isinstance(variable, SymbolRecord):
            raise TypeError("variable must be SymbolRecord")
        if not isinstance(row, LocationRow):
            raise TypeError("row must be LocationRow")
        if not isinstance(architecture, ArchitectureDescriptor):
            raise TypeError("architecture must be ArchitectureDescriptor")
        if not isinstance(abi, AbiDescriptorRef):
            raise TypeError("abi must be AbiDescriptorRef")
        if not isinstance(profile_limits, RecipeLimits):
            raise TypeError("profile_limits must be RecipeLimits")
        if not isinstance(request_limits, RecipeRequestLimits):
            raise TypeError("request_limits must be RecipeRequestLimits")

        if frame.context != context:
            return LocationEvaluator._inspection_failure(
                context,
                InspectionStatus.STALE,
                "frame_context_stale",
                "selected frame context differs from the requested inspection context",
                row_id=row.row_id,
                frame_index=frame.frame_index,
            )

        try:
            index_binding = index.binding()
            bundle_identity = index.bundle_identity()
        except Exception as exc:
            return LocationEvaluator._inspection_failure(
                context,
                InspectionStatus.ARTIFACT_MISMATCH,
                "artifact_index_contract",
                f"artifact index binding access failed with {type(exc).__name__}",
                row_id=row.row_id,
                frame_index=frame.frame_index,
            )
        if not isinstance(index_binding, ImageDebugBinding) or not isinstance(
            bundle_identity, ImageDebugBundleIdentityPayload
        ):
            return LocationEvaluator._inspection_failure(
                context,
                InspectionStatus.ARTIFACT_MISMATCH,
                "artifact_index_contract",
                "artifact index returned invalid binding evidence",
                row_id=row.row_id,
                frame_index=frame.frame_index,
            )
        if row.binding != index_binding:
            return LocationEvaluator._inspection_failure(
                context,
                InspectionStatus.ARTIFACT_MISMATCH,
                "row_binding_mismatch",
                "LocationRow binding differs from DebugArtifactIndex",
                row_id=row.row_id,
                frame_index=frame.frame_index,
            )
        binding_result = DebugBindingValidator.validate(
            index_binding, bundle_identity, architecture, abi
        )
        if binding_result.status is not ResolutionStatus.RESOLVED:
            return LocationEvaluator._inspection_failure(
                context,
                InspectionStatus.ARTIFACT_MISMATCH,
                "debug_binding_mismatch",
                "debug binding validation failed",
                row_id=row.row_id,
                frame_index=frame.frame_index,
                diagnostics=binding_result.diagnostics,
            )
        if index_binding.payload.loaded_image_ref != context.image:
            return LocationEvaluator._inspection_failure(
                context,
                InspectionStatus.ARTIFACT_MISMATCH,
                "binding_loaded_image_mismatch",
                "inspection context image differs from the debug binding",
                row_id=row.row_id,
                frame_index=frame.frame_index,
            )
        if row.abi != abi:
            return LocationEvaluator._inspection_failure(
                context,
                InspectionStatus.ARTIFACT_MISMATCH,
                "row_abi_mismatch",
                "LocationRow ABI differs from the validated ABI",
                row_id=row.row_id,
                frame_index=frame.frame_index,
            )

        if (
            request_limits.max_frames > profile_limits.unwind_frames
            or request_limits.max_pieces > profile_limits.location_pieces
        ):
            return LocationEvaluator._inspection_failure(
                context,
                InspectionStatus.UNSUPPORTED,
                "limit_exceeded",
                "request limits exceed the accepted recipe profile",
                row_id=row.row_id,
                frame_index=frame.frame_index,
            )
        frame_diagnostics = RecipeComponentValidator.validate_unwind_frame(frame, architecture)
        if frame_diagnostics:
            return LocationEvaluator._inspection_failure(
                context,
                InspectionStatus.CORRUPT,
                "invalid_unwind_frame",
                "selected UnwindFrame is invalid",
                row_id=row.row_id,
                frame_index=frame.frame_index,
                diagnostics=frame_diagnostics,
            )
        row_diagnostics = RecipeComponentValidator.validate_location_row(
            row, variable, architecture, abi, profile_limits
        )
        if row_diagnostics:
            status = (
                InspectionStatus.UNSUPPORTED
                if row_diagnostics[0].code == "limit_exceeded"
                else InspectionStatus.CORRUPT
            )
            return LocationEvaluator._inspection_failure(
                context,
                status,
                "invalid_location_row",
                "LocationRow validation failed",
                row_id=row.row_id,
                frame_index=frame.frame_index,
                diagnostics=row_diagnostics,
            )
        if not row.pc_range.contains(frame.pc):
            return LocationEvaluator._inspection_failure(
                context,
                InspectionStatus.CORRUPT,
                "location_row_not_applicable",
                "LocationRow does not contain the selected frame PC",
                row_id=row.row_id,
                frame_index=frame.frame_index,
            )
        if row.function_id is not None and (
            frame.function is None or frame.function.function_id != row.function_id
        ):
            return LocationEvaluator._inspection_failure(
                context,
                InspectionStatus.CORRUPT,
                "location_function_mismatch",
                "LocationRow function differs from the selected frame",
                row_id=row.row_id,
                frame_index=frame.frame_index,
            )

        if row.declared_type_id is not None:
            try:
                type_result = index.type_by_id(row.declared_type_id)
            except Exception as exc:
                return LocationEvaluator._inspection_failure(
                    context,
                    InspectionStatus.CORRUPT,
                    "type_index_contract",
                    f"type lookup failed with {type(exc).__name__}",
                    row_id=row.row_id,
                    frame_index=frame.frame_index,
                )
            if (
                not isinstance(type_result, ResolutionResult)
                or type_result.status is not ResolutionStatus.RESOLVED
                or len(type_result.values) != 1
                or not isinstance(type_result.values[0], TypeRecord)
            ):
                return LocationEvaluator._inspection_failure(
                    context,
                    InspectionStatus.CORRUPT,
                    "location_type_unresolved",
                    "declared LocationRow type does not resolve exactly once",
                    row_id=row.row_id,
                    frame_index=frame.frame_index,
                )
            type_record = type_result.values[0]
            if (
                type_record.bit_size != row.declared_bit_size
                or type_record.byte_order is not row.value_byte_order
            ):
                return LocationEvaluator._inspection_failure(
                    context,
                    InspectionStatus.CORRUPT,
                    "location_type_mismatch",
                    "resolved type width/byte order differs from LocationRow",
                    row_id=row.row_id,
                    frame_index=frame.frame_index,
                )

        psw = frame.recovered_psw
        evaluation = RecipeEvaluationContext(
            context=context,
            frame_index=frame.frame_index,
            binding=index_binding,
            bundle_identity=bundle_identity,
            architecture=architecture,
            abi=abi,
            pc=frame.pc,
            sp=frame.sp,
            psw=(
                RecipeScalar(False, psw.bit_width, psw.unsigned_value)
                if psw.available
                else None
            ),
            recovered_registers=frame.recovered_registers,
            cfa=frame.cfa,
            frame_base=frame.frame_base,
        )

        form = row.location_form
        if form.kind is LocationKind.OPTIMIZED_OUT:
            value = LocationEvaluator._terminal_value(
                variable,
                row,
                ValueAvailability.OPTIMIZED_OUT,
                f"<optimized out: {form.reason}>",
            )
            return InspectionResult(InspectionStatus.COMPLETE, context, value, ())
        if form.kind is LocationKind.UNAVAILABLE:
            value = LocationEvaluator._terminal_value(
                variable,
                row,
                ValueAvailability.UNAVAILABLE,
                f"<unavailable: {form.reason}>",
            )
            return InspectionResult(InspectionStatus.COMPLETE, context, value, ())

        if form.kind in {LocationKind.ADDRESS, LocationKind.VALUE}:
            budget = RecipeBudget(
                profile_limits.opcodes_per_expression,
                profile_limits.dereferences_per_expression,
                profile_limits.location_total_dereferenced_bytes,
            )
            result = RecipeEvaluator.evaluate(
                evaluation, form.expression, read_port, profile_limits, budget
            )
            if result.status is not RecipeEvaluationStatus.COMPLETE:
                return LocationEvaluator._map_recipe_failure(context, variable, row, result)
            if form.kind is LocationKind.VALUE:
                if isinstance(result.value, RecipeScalar):
                    raw = ScalarBytes.encode(
                        result.value.value,
                        result.value.signed,
                        result.value.bit_width,
                        row.value_byte_order,
                    )
                    display = str(result.value.value)
                elif isinstance(result.value, RecipeRegister):
                    raw = ScalarBytes.encode(
                        result.value.unsigned_value,
                        False,
                        result.value.bit_width,
                        row.value_byte_order,
                    )
                    display = str(result.value.unsigned_value)
                else:
                    return LocationEvaluator._inspection_failure(
                        context,
                        InspectionStatus.CORRUPT,
                        "invalid_location_result",
                        "VALUE expression returned a non-scalar/register",
                        row_id=row.row_id,
                        frame_index=frame.frame_index,
                    )
            else:
                if not isinstance(result.value, RecipeAddress):
                    return LocationEvaluator._inspection_failure(
                        context,
                        InspectionStatus.CORRUPT,
                        "invalid_location_result",
                        "ADDRESS expression returned a non-address",
                        row_id=row.row_id,
                        frame_index=frame.frame_index,
                    )
                byte_length = (row.declared_bit_size + 7) // 8
                if result.budget_after.bytes_remaining < byte_length:
                    return LocationEvaluator._inspection_failure(
                        context,
                        InspectionStatus.UNSUPPORTED,
                        "limit_exceeded",
                        "location byte budget exhausted before address read",
                        row_id=row.row_id,
                        frame_index=frame.frame_index,
                    )
                read_status, raw, diagnostics = LocationEvaluator._read_exact_memory(
                    context,
                    frame,
                    row,
                    result.value.address,
                    byte_length,
                    read_port,
                    architecture,
                )
                if read_status is InspectionStatus.UNAVAILABLE:
                    value = LocationEvaluator._terminal_value(
                        variable,
                        row,
                        ValueAvailability.UNAVAILABLE,
                        "<memory unavailable>",
                    )
                    return InspectionResult(InspectionStatus.COMPLETE, context, value, diagnostics)
                if read_status is not InspectionStatus.COMPLETE:
                    return LocationEvaluator._inspection_failure(
                        context,
                        read_status,
                        "location_memory_read_failed",
                        "location memory read failed",
                        row_id=row.row_id,
                        frame_index=frame.frame_index,
                        diagnostics=diagnostics,
                    )
                display = str(
                    int.from_bytes(raw, byteorder=row.value_byte_order.value, signed=False)
                )
            value = EvaluatedValue(
                symbol_id=variable.symbol_id,
                name=variable.name,
                declared_type_id=row.declared_type_id,
                display_value=display,
                raw_bytes=raw,
                bit_size=row.declared_bit_size,
                location_status=ValueAvailability.AVAILABLE,
                pieces=(),
            )
            return InspectionResult(InspectionStatus.COMPLETE, context, value, ())

        # PIECES: opcode/deref limits reset per expression; only location bytes are shared.
        if (
            len(form.pieces) > profile_limits.location_pieces
            or len(form.pieces) > request_limits.max_pieces
        ):
            return LocationEvaluator._inspection_failure(
                context,
                InspectionStatus.UNSUPPORTED,
                "limit_exceeded",
                "location piece count exceeds the active bound",
                row_id=row.row_id,
                frame_index=frame.frame_index,
            )
        bytes_remaining = profile_limits.location_total_dereferenced_bytes
        output_pieces: list[ValuePiece] = []
        missing_diagnostics: list[Diagnostic] = []
        aggregate = 0
        complete_coverage = True
        cursor = 0
        for piece_index, piece in enumerate(form.pieces):
            if piece.destination_bit_offset > cursor:
                gap_size = piece.destination_bit_offset - cursor
                output_pieces.append(
                    ValuePiece(
                        cursor,
                        gap_size,
                        0,
                        None,
                        ValuePieceStatus.UNAVAILABLE,
                        "piece_not_described",
                    )
                )
                missing_diagnostics.append(
                    _recipe_diagnostic(
                        "piece_not_described",
                        "location pieces leave an explicit destination gap",
                        row_id=row.row_id,
                        frame_index=frame.frame_index,
                        operation_index=piece_index,
                    )
                )
                complete_coverage = False
            budget = RecipeBudget(
                profile_limits.opcodes_per_expression,
                profile_limits.dereferences_per_expression,
                bytes_remaining,
            )
            result = RecipeEvaluator.evaluate(
                evaluation, piece.expression, read_port, profile_limits, budget
            )
            bytes_remaining = result.budget_after.bytes_remaining
            if result.status is RecipeEvaluationStatus.UNAVAILABLE:
                reason = result.diagnostics[0].code if result.diagnostics else "unavailable"
                output_pieces.append(
                    ValuePiece(
                        piece.destination_bit_offset,
                        piece.bit_size,
                        piece.source_bit_offset,
                        None,
                        ValuePieceStatus.UNAVAILABLE,
                        reason,
                    )
                )
                missing_diagnostics.append(
                    _recipe_diagnostic(
                        reason,
                        "location piece source is unavailable",
                        row_id=row.row_id,
                        frame_index=frame.frame_index,
                        operation_index=piece_index,
                    )
                )
                complete_coverage = False
            elif result.status is not RecipeEvaluationStatus.COMPLETE:
                return LocationEvaluator._map_recipe_failure(context, variable, row, result)
            else:
                if isinstance(result.value, RecipeScalar):
                    width = result.value.bit_width
                    unsigned = result.value.value % (1 << width)
                elif isinstance(result.value, RecipeRegister):
                    width = result.value.bit_width
                    unsigned = result.value.unsigned_value
                else:
                    return LocationEvaluator._inspection_failure(
                        context,
                        InspectionStatus.CORRUPT,
                        "malformed_piece_source",
                        "location piece returned a non-scalar/register",
                        row_id=row.row_id,
                        frame_index=frame.frame_index,
                    )
                mask = (1 << piece.bit_size) - 1
                piece_value = (unsigned >> piece.source_bit_offset) & mask
                aggregate |= piece_value << piece.destination_bit_offset
                output_pieces.append(
                    ValuePiece(
                        piece.destination_bit_offset,
                        piece.bit_size,
                        piece.source_bit_offset,
                        ScalarBytes.encode(
                            piece_value, False, piece.bit_size, row.value_byte_order
                        ),
                        ValuePieceStatus.AVAILABLE,
                        None,
                    )
                )
            cursor = piece.destination_bit_offset + piece.bit_size
        if cursor < row.declared_bit_size:
            output_pieces.append(
                ValuePiece(
                    cursor,
                    row.declared_bit_size - cursor,
                    0,
                    None,
                    ValuePieceStatus.UNAVAILABLE,
                    "piece_not_described",
                )
            )
            missing_diagnostics.append(
                _recipe_diagnostic(
                    "piece_not_described",
                    "location pieces leave an explicit trailing destination gap",
                    row_id=row.row_id,
                    frame_index=frame.frame_index,
                )
            )
            complete_coverage = False
        if complete_coverage:
            raw = ScalarBytes.encode(
                aggregate, False, row.declared_bit_size, row.value_byte_order
            )
            value = EvaluatedValue(
                variable.symbol_id,
                variable.name,
                row.declared_type_id,
                str(aggregate),
                raw,
                row.declared_bit_size,
                ValueAvailability.AVAILABLE,
                (),
            )
            return InspectionResult(InspectionStatus.COMPLETE, context, value, ())
        value = EvaluatedValue(
            variable.symbol_id,
            variable.name,
            row.declared_type_id,
            "<partial>",
            None,
            row.declared_bit_size,
            ValueAvailability.PARTIAL,
            tuple(output_pieces),
        )
        return InspectionResult(
            InspectionStatus.PARTIAL,
            context,
            value,
            tuple(missing_diagnostics),
        )


__all__ = [
    "AddSConstCheckedOp",
    "BitSliceOp",
    "CfaOp",
    "ConstSOp",
    "ConstUOp",
    "DerefUOp",
    "FrameBaseOp",
    "FrameBinding",
    "LocationEvaluator",
    "LocationForm",
    "LocationKind",
    "LocationPieceRule",
    "LocationRow",
    "RecipeAddress",
    "RecipeBudget",
    "RecipeComponentValidator",
    "RecipeEvaluationContext",
    "RecipeEvaluationResult",
    "RecipeEvaluationStatus",
    "RecipeEvaluator",
    "RecipeExpression",
    "RecipeLimits",
    "RecipeOpcode",
    "RecipeParseError",
    "RecipeParser",
    "RecipeRegister",
    "RecipeRequestLimits",
    "RecipeResultKind",
    "RecipeRole",
    "RecipeRule",
    "RecipeRuleKind",
    "RecipeScalar",
    "RecipeSpecial",
    "RecipeValue",
    "RegValueOp",
    "SpecialValueOp",
    "StaticAddressOp",
    "ToAddressOp",
    "UnwindBoundary",
    "UnwindFrame",
    "UnwindRow",
]
