"""Descriptor-governed typed HSX addresses and checked arithmetic."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .identity import ArchitectureDescriptorRef, CanonicalUInt64
from .results import (
    AddressRangeResult,
    AddressResult,
    AddressStatus,
    ByteLengthResult,
    Diagnostic,
    RegisterSelection,
    UnitCountResult,
    _register_contract_enums,
)


def _require_nonempty(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field_name} must be a non-empty string")


def _require_int(value: int, field_name: str, *, minimum: int = 0) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ValueError(f"{field_name} must be an integer >= {minimum}")


def _tuple(value: object, field_name: str) -> tuple:
    if isinstance(value, (str, bytes)) or not isinstance(value, (list, tuple)):
        raise TypeError(f"{field_name} must be a tuple or list")
    return tuple(value)


class ByteOrder(str, Enum):
    LITTLE = "little"
    BIG = "big"


class WrapPolicy(str, Enum):
    FORBIDDEN = "forbidden"
    EXPLICIT = "explicit"


class AddressArithmeticMode(str, Enum):
    CHECKED = "checked"
    WRAP = "wrap"


# The short frozen spelling is useful at service call sites.
ArithmeticMode = AddressArithmeticMode


class Permission(str, Enum):
    READ = "read"
    WRITE = "write"
    EXECUTE = "execute"


_register_contract_enums(ByteOrder, WrapPolicy, AddressArithmeticMode, Permission)


@dataclass(frozen=True, slots=True, order=True)
class AddressSpaceId:
    value: str

    def __post_init__(self) -> None:
        _require_nonempty(self.value, "value")


@dataclass(frozen=True, slots=True)
class HsxAddress:
    space: AddressSpaceId
    unsigned_value: int

    def __post_init__(self) -> None:
        if not isinstance(self.space, AddressSpaceId):
            raise TypeError("space must be AddressSpaceId")
        _require_int(self.unsigned_value, "unsigned_value")


@dataclass(frozen=True, slots=True)
class HsxAddressRange:
    start: HsxAddress
    length_units: int

    def __post_init__(self) -> None:
        if not isinstance(self.start, HsxAddress):
            raise TypeError("start must be HsxAddress")
        _require_int(self.length_units, "length_units")

    @property
    def end_unsigned_value(self) -> int:
        return self.start.unsigned_value + self.length_units

    def contains(self, address: HsxAddress) -> bool:
        if not isinstance(address, HsxAddress) or address.space != self.start.space:
            return False
        return self.start.unsigned_value <= address.unsigned_value < self.end_unsigned_value

    def contains_range(self, candidate: HsxAddressRange) -> bool:
        if not isinstance(candidate, HsxAddressRange) or candidate.start.space != self.start.space:
            return False
        return (
            self.start.unsigned_value <= candidate.start.unsigned_value
            and candidate.end_unsigned_value <= self.end_unsigned_value
        )


@dataclass(frozen=True, slots=True)
class AddressSpaceDescriptor:
    space: AddressSpaceId
    unit: str
    bits_per_unit: int
    width_bits: int
    legal_ranges: tuple[HsxAddressRange, ...]
    byte_order: ByteOrder
    alignment: int
    wrap_policy: WrapPolicy
    permissions: frozenset[Permission]

    def __post_init__(self) -> None:
        if not isinstance(self.space, AddressSpaceId):
            raise TypeError("space must be AddressSpaceId")
        _require_nonempty(self.unit, "unit")
        _require_int(self.bits_per_unit, "bits_per_unit", minimum=1)
        _require_int(self.width_bits, "width_bits", minimum=1)
        if self.unit == "byte" and self.bits_per_unit != 8:
            raise ValueError("unit='byte' requires bits_per_unit=8")
        if not isinstance(self.byte_order, ByteOrder):
            raise TypeError("byte_order must be ByteOrder")
        _require_int(self.alignment, "alignment", minimum=1)
        if not isinstance(self.wrap_policy, WrapPolicy):
            raise TypeError("wrap_policy must be WrapPolicy")
        if isinstance(self.permissions, str) or not isinstance(
            self.permissions, (set, frozenset, tuple, list)
        ):
            raise TypeError("permissions must be a collection")
        permissions = frozenset(self.permissions)
        if not all(isinstance(item, Permission) for item in permissions):
            raise TypeError("permissions must contain Permission values")
        ranges = _tuple(self.legal_ranges, "legal_ranges")
        if not ranges or not all(isinstance(item, HsxAddressRange) for item in ranges):
            raise ValueError("legal_ranges must contain at least one HsxAddressRange")
        capacity = 1 << self.width_bits
        previous_end = -1
        for legal_range in ranges:
            if legal_range.start.space != self.space:
                raise ValueError("every legal range must use the descriptor space")
            if legal_range.length_units < 1:
                raise ValueError("legal ranges must be non-empty")
            if legal_range.start.unsigned_value >= capacity or legal_range.end_unsigned_value > capacity:
                raise ValueError("legal range exceeds address width")
            if (
                legal_range.start.unsigned_value // self.alignment
            ) * self.alignment != legal_range.start.unsigned_value:
                raise ValueError("legal range start violates space alignment")
            if legal_range.start.unsigned_value < previous_end:
                raise ValueError("legal ranges must be ordered and non-overlapping")
            previous_end = legal_range.end_unsigned_value
        object.__setattr__(self, "legal_ranges", ranges)
        object.__setattr__(self, "permissions", permissions)


def _failure(status: AddressStatus, code: str, message: str):
    return status, (Diagnostic(code, message, component="address"),)


@dataclass(frozen=True, slots=True)
class ArchitectureDescriptor:
    ref: ArchitectureDescriptorRef
    descriptor_version: CanonicalUInt64
    instruction_encoding: str
    container_header_byte_order: ByteOrder
    instruction_serialization_byte_order: ByteOrder
    register_width_bits: int
    register_byte_order: ByteOrder
    register_count: int
    spaces: tuple[AddressSpaceDescriptor, ...]
    register_order: tuple[str, ...]
    pc_space: AddressSpaceId
    sp_space: AddressSpaceId
    psw_width_bits: int
    instruction_alignment: int

    def __post_init__(self) -> None:
        if not isinstance(self.ref, ArchitectureDescriptorRef):
            raise TypeError("ref must be ArchitectureDescriptorRef")
        if not isinstance(self.descriptor_version, CanonicalUInt64):
            raise TypeError("descriptor_version must be CanonicalUInt64")
        if self.descriptor_version.value < 1:
            raise ValueError("descriptor_version must be >= 1")
        _require_nonempty(self.instruction_encoding, "instruction_encoding")
        if not isinstance(self.container_header_byte_order, ByteOrder):
            raise TypeError("container_header_byte_order must be ByteOrder")
        if not isinstance(self.instruction_serialization_byte_order, ByteOrder):
            raise TypeError("instruction_serialization_byte_order must be ByteOrder")
        _require_int(self.register_width_bits, "register_width_bits", minimum=1)
        if not isinstance(self.register_byte_order, ByteOrder):
            raise TypeError("register_byte_order must be ByteOrder")
        _require_int(self.register_count, "register_count", minimum=1)
        spaces = _tuple(self.spaces, "spaces")
        if not spaces or not all(isinstance(item, AddressSpaceDescriptor) for item in spaces):
            raise ValueError("spaces must contain AddressSpaceDescriptor values")
        space_ids = tuple(item.space for item in spaces)
        if len(set(space_ids)) != len(space_ids):
            raise ValueError("address-space IDs must be unique")
        register_order = _tuple(self.register_order, "register_order")
        if len(register_order) != self.register_count:
            raise ValueError("register_order cardinality must equal register_count")
        for register_id in register_order:
            _require_nonempty(register_id, "register_id")
            if register_id in {"PC", "SP", "PSW"}:
                raise ValueError("special register IDs cannot be GPR IDs")
        if len(set(register_order)) != len(register_order):
            raise ValueError("register_order must contain unique GPR IDs")
        if not isinstance(self.pc_space, AddressSpaceId) or self.pc_space not in space_ids:
            raise ValueError("pc_space must name one declared address space")
        if not isinstance(self.sp_space, AddressSpaceId) or self.sp_space not in space_ids:
            raise ValueError("sp_space must name one declared address space")
        _require_int(self.psw_width_bits, "psw_width_bits", minimum=1)
        _require_int(self.instruction_alignment, "instruction_alignment", minimum=1)
        object.__setattr__(self, "spaces", spaces)
        object.__setattr__(self, "register_order", register_order)

    @property
    def declared_register_order(self) -> tuple[str, ...]:
        return self.register_order + ("PC", "SP", "PSW")

    def space_descriptor(self, space: AddressSpaceId) -> AddressSpaceDescriptor | None:
        if not isinstance(space, AddressSpaceId):
            raise TypeError("space must be AddressSpaceId")
        return next((item for item in self.spaces if item.space == space), None)

    def register_bit_width(self, register_id: str) -> int:
        _require_nonempty(register_id, "register_id")
        if register_id in self.register_order:
            return self.register_width_bits
        if register_id == "PC":
            return self._known_space(self.pc_space).width_bits
        if register_id == "SP":
            return self._known_space(self.sp_space).width_bits
        if register_id == "PSW":
            return self.psw_width_bits
        raise KeyError(register_id)

    def selected_register_order(self, selection: RegisterSelection) -> tuple[str, ...]:
        if not isinstance(selection, RegisterSelection):
            raise TypeError("selection must be RegisterSelection")
        if selection.all_declared:
            return self.declared_register_order
        unknown = tuple(item for item in selection.register_ids if item not in self.declared_register_order)
        if unknown:
            raise ValueError(f"unknown register IDs: {unknown!r}")
        return selection.register_ids

    def _known_space(self, space: AddressSpaceId) -> AddressSpaceDescriptor:
        descriptor = self.space_descriptor(space)
        if descriptor is None:
            raise KeyError(space.value)
        return descriptor

    def validate(
        self,
        address: HsxAddress,
        required_permission: Permission | None = None,
    ) -> AddressResult:
        if not isinstance(address, HsxAddress):
            raise TypeError("address must be HsxAddress")
        if required_permission is not None and not isinstance(required_permission, Permission):
            raise TypeError("required_permission must be Permission or None")
        space = self.space_descriptor(address.space)
        if space is None:
            status, diagnostics = _failure(
                AddressStatus.UNKNOWN_SPACE, "unknown_address_space", "address space is not declared"
            )
            return AddressResult(status, None, diagnostics)
        if address.unsigned_value >= 1 << space.width_bits:
            status, diagnostics = _failure(
                AddressStatus.OVERFLOW, "address_overflow", "address exceeds declared width"
            )
            return AddressResult(status, None, diagnostics)
        if (address.unsigned_value // space.alignment) * space.alignment != address.unsigned_value:
            status, diagnostics = _failure(
                AddressStatus.MISALIGNED, "address_misaligned", "address violates space alignment"
            )
            return AddressResult(status, None, diagnostics)
        if not any(item.contains(address) for item in space.legal_ranges):
            status, diagnostics = _failure(
                AddressStatus.OUT_OF_RANGE, "address_out_of_range", "address falls outside legal ranges"
            )
            return AddressResult(status, None, diagnostics)
        if required_permission is not None and required_permission not in space.permissions:
            status, diagnostics = _failure(
                AddressStatus.PERMISSION_DENIED,
                "address_permission_denied",
                "address space does not grant the required permission",
            )
            return AddressResult(status, None, diagnostics)
        return AddressResult(AddressStatus.VALID, address, ())

    def add(
        self,
        address: HsxAddress,
        delta_units: int,
        mode: AddressArithmeticMode,
    ) -> AddressResult:
        return self._arithmetic(address, delta_units, mode, subtract=False)

    def subtract(
        self,
        address: HsxAddress,
        delta_units: int,
        mode: AddressArithmeticMode,
    ) -> AddressResult:
        return self._arithmetic(address, delta_units, mode, subtract=True)

    def _arithmetic(
        self,
        address: HsxAddress,
        delta_units: int,
        mode: AddressArithmeticMode,
        *,
        subtract: bool,
    ) -> AddressResult:
        if not isinstance(address, HsxAddress):
            raise TypeError("address must be HsxAddress")
        _require_int(delta_units, "delta_units")
        if not isinstance(mode, AddressArithmeticMode):
            raise TypeError("mode must be AddressArithmeticMode")
        initial = self.validate(address)
        if initial.status is not AddressStatus.VALID:
            return initial
        space = self._known_space(address.space)
        if mode is AddressArithmeticMode.WRAP and space.wrap_policy is not WrapPolicy.EXPLICIT:
            status, diagnostics = _failure(
                AddressStatus.WRAP_FORBIDDEN,
                "address_wrap_forbidden",
                "space does not permit explicit wrapping",
            )
            return AddressResult(status, None, diagnostics)
        capacity = 1 << space.width_bits
        candidate = address.unsigned_value - delta_units if subtract else address.unsigned_value + delta_units
        if mode is AddressArithmeticMode.CHECKED:
            if candidate < 0:
                status, diagnostics = _failure(
                    AddressStatus.UNDERFLOW, "address_underflow", "subtraction underflows address width"
                )
                return AddressResult(status, None, diagnostics)
            if candidate >= capacity:
                status, diagnostics = _failure(
                    AddressStatus.OVERFLOW, "address_overflow", "addition overflows address width"
                )
                return AddressResult(status, None, diagnostics)
        else:
            # Modulo is permitted only in this explicitly selected WRAP branch.
            candidate %= capacity
        return self.validate(HsxAddress(address.space, candidate))

    def range(
        self,
        start: HsxAddress,
        length_units: int,
        required_permission: Permission | None = None,
    ) -> AddressRangeResult:
        if not isinstance(start, HsxAddress):
            raise TypeError("start must be HsxAddress")
        _require_int(length_units, "length_units")
        validated = self.validate(start, required_permission)
        if validated.status is not AddressStatus.VALID:
            return AddressRangeResult(validated.status, None, validated.diagnostics)
        space = self._known_space(start.space)
        end = start.unsigned_value + length_units
        if end > 1 << space.width_bits:
            status, diagnostics = _failure(
                AddressStatus.OVERFLOW, "address_range_overflow", "range exceeds address width"
            )
            return AddressRangeResult(status, None, diagnostics)
        candidate = HsxAddressRange(start, length_units)
        if length_units and not any(item.contains_range(candidate) for item in space.legal_ranges):
            status, diagnostics = _failure(
                AddressStatus.OUT_OF_RANGE,
                "address_range_out_of_range",
                "range crosses a legal-range boundary or hole",
            )
            return AddressRangeResult(status, None, diagnostics)
        return AddressRangeResult(AddressStatus.VALID, candidate, ())

    def units_for_bytes(self, space: AddressSpaceId, byte_length: int) -> UnitCountResult:
        if not isinstance(space, AddressSpaceId):
            raise TypeError("space must be AddressSpaceId")
        _require_int(byte_length, "byte_length")
        descriptor = self.space_descriptor(space)
        if descriptor is None:
            status, diagnostics = _failure(
                AddressStatus.UNKNOWN_SPACE, "unknown_address_space", "address space is not declared"
            )
            return UnitCountResult(status, None, diagnostics)
        if (descriptor.bits_per_unit // 8) * 8 != descriptor.bits_per_unit:
            status, diagnostics = _failure(
                AddressStatus.UNIT_CONVERSION_UNSUPPORTED,
                "unit_conversion_unsupported",
                "address units are not whole bytes",
            )
            return UnitCountResult(status, None, diagnostics)
        bytes_per_unit = descriptor.bits_per_unit // 8
        if (byte_length // bytes_per_unit) * bytes_per_unit != byte_length:
            status, diagnostics = _failure(
                AddressStatus.MISALIGNED,
                "byte_length_not_whole_units",
                "byte length is not an exact whole-unit multiple",
            )
            return UnitCountResult(status, None, diagnostics)
        return UnitCountResult(AddressStatus.VALID, byte_length // bytes_per_unit, ())

    def bytes_for_units(self, space: AddressSpaceId, length_units: int) -> ByteLengthResult:
        if not isinstance(space, AddressSpaceId):
            raise TypeError("space must be AddressSpaceId")
        _require_int(length_units, "length_units")
        descriptor = self.space_descriptor(space)
        if descriptor is None:
            status, diagnostics = _failure(
                AddressStatus.UNKNOWN_SPACE, "unknown_address_space", "address space is not declared"
            )
            return ByteLengthResult(status, None, diagnostics)
        if (descriptor.bits_per_unit // 8) * 8 != descriptor.bits_per_unit:
            status, diagnostics = _failure(
                AddressStatus.UNIT_CONVERSION_UNSUPPORTED,
                "unit_conversion_unsupported",
                "address units are not whole bytes",
            )
            return ByteLengthResult(status, None, diagnostics)
        bytes_per_unit = descriptor.bits_per_unit // 8
        byte_length = length_units * bytes_per_unit
        if byte_length > (1 << 64) - 1:
            status, diagnostics = _failure(
                AddressStatus.OVERFLOW,
                "byte_length_overflow",
                "converted byte length exceeds uint64",
            )
            return ByteLengthResult(status, None, diagnostics)
        return ByteLengthResult(AddressStatus.VALID, byte_length, ())

    def format(self, address: HsxAddress) -> str:
        result = self.validate(address)
        if result.status is not AddressStatus.VALID:
            raise ValueError(result.diagnostics[0].code)
        width = self._known_space(address.space).width_bits
        digits = (width + 3) // 4
        return f"{address.space.value}:0x{address.unsigned_value:0{digits}x}"


__all__ = [
    "AddressArithmeticMode",
    "AddressSpaceDescriptor",
    "AddressSpaceId",
    "ArchitectureDescriptor",
    "ArithmeticMode",
    "ByteOrder",
    "HsxAddress",
    "HsxAddressRange",
    "Permission",
    "WrapPolicy",
]
