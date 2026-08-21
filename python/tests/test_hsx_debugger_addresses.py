from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from pathlib import Path
import sys

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
PYTHON_SRC = REPO_ROOT / "python"
if str(PYTHON_SRC) not in sys.path:
    sys.path.insert(0, str(PYTHON_SRC))

from hsx_debugger.addresses import (
    AddressArithmeticMode,
    AddressSpaceDescriptor,
    AddressSpaceId,
    ArchitectureDescriptor,
    ByteOrder,
    HsxAddress,
    HsxAddressRange,
    Permission,
    WrapPolicy,
)
from hsx_debugger.identity import ArchitectureDescriptorRef, CanonicalUInt64
from hsx_debugger.results import (
    AddressStatus,
    ConstantExpression,
    PageRequest,
    RegisterSelection,
    RegisterSet,
    RegisterValue,
    ScalarBytes,
)


def descriptor() -> ArchitectureDescriptor:
    code = AddressSpaceId("code")
    data = AddressSpaceId("data")
    word = AddressSpaceId("word")
    bit = AddressSpaceId("bit")
    return ArchitectureDescriptor(
        ArchitectureDescriptorRef("arch-v1", "a" * 64),
        CanonicalUInt64(1),
        "hsx.fixed32/1",
        ByteOrder.BIG,
        ByteOrder.LITTLE,
        32,
        ByteOrder.BIG,
        3,
        (
            AddressSpaceDescriptor(
                code,
                "byte",
                8,
                16,
                (
                    HsxAddressRange(HsxAddress(code, 0), 0x100),
                    HsxAddressRange(HsxAddress(code, 0x200), 0xFE00),
                ),
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
                ByteOrder.BIG,
                2,
                WrapPolicy.EXPLICIT,
                frozenset({Permission.READ, Permission.WRITE}),
            ),
            AddressSpaceDescriptor(
                word,
                "word16",
                16,
                12,
                (HsxAddressRange(HsxAddress(word, 0), 1 << 12),),
                ByteOrder.LITTLE,
                1,
                WrapPolicy.FORBIDDEN,
                frozenset({Permission.READ}),
            ),
            AddressSpaceDescriptor(
                bit,
                "bit",
                1,
                10,
                (HsxAddressRange(HsxAddress(bit, 0), 1 << 10),),
                ByteOrder.LITTLE,
                1,
                WrapPolicy.FORBIDDEN,
                frozenset({Permission.READ}),
            ),
        ),
        ("R0", "R7", "R15"),
        code,
        data,
        12,
        4,
    )


def test_descriptor_is_complete_deeply_immutable_and_exposes_exact_register_layout() -> None:
    arch = descriptor()
    assert arch.descriptor_version == CanonicalUInt64(1)
    assert arch.instruction_encoding == "hsx.fixed32/1"
    assert arch.container_header_byte_order is ByteOrder.BIG
    assert arch.instruction_serialization_byte_order is ByteOrder.LITTLE
    assert arch.register_byte_order is ByteOrder.BIG
    assert arch.declared_register_order == ("R0", "R7", "R15", "PC", "SP", "PSW")
    assert tuple(arch.register_bit_width(item) for item in arch.declared_register_order) == (
        32,
        32,
        32,
        16,
        24,
        12,
    )
    assert arch.selected_register_order(RegisterSelection(True, ())) == arch.declared_register_order
    assert arch.selected_register_order(RegisterSelection(False, ("PSW", "R0"))) == ("PSW", "R0")
    with pytest.raises(ValueError, match="unknown"):
        arch.selected_register_order(RegisterSelection(False, ("UNKNOWN",)))
    with pytest.raises(FrozenInstanceError):
        arch.register_count = 4  # type: ignore[misc]


@pytest.mark.parametrize(
    "change, message",
    [
        ({"descriptor_version": CanonicalUInt64(0)}, "descriptor_version"),
        ({"instruction_encoding": ""}, "instruction_encoding"),
        ({"register_count": 2}, "cardinality"),
        ({"register_order": ("R0", "R0", "R15")}, "unique"),
        ({"pc_space": AddressSpaceId("missing")}, "pc_space"),
        ({"psw_width_bits": 0}, "psw_width_bits"),
    ],
)
def test_descriptor_rejects_missing_or_inconsistent_fields(change, message: str) -> None:
    with pytest.raises((TypeError, ValueError), match=message):
        replace(descriptor(), **change)


def test_validate_covers_width_alignment_holes_permissions_and_wrong_space() -> None:
    arch = descriptor()
    code = AddressSpaceId("code")
    assert arch.validate(HsxAddress(code, 0x20)).status is AddressStatus.VALID
    assert arch.validate(HsxAddress(AddressSpaceId("other"), 0)).status is AddressStatus.UNKNOWN_SPACE
    assert arch.validate(HsxAddress(code, 1)).status is AddressStatus.MISALIGNED
    assert arch.validate(HsxAddress(code, 0x100)).status is AddressStatus.OUT_OF_RANGE
    assert arch.validate(HsxAddress(code, 1 << 16)).status is AddressStatus.OVERFLOW
    assert arch.validate(HsxAddress(code, 0x20), Permission.WRITE).status is AddressStatus.PERMISSION_DENIED
    assert arch.validate(HsxAddress(code, 0x20), Permission.EXECUTE).status is AddressStatus.VALID


def test_checked_arithmetic_never_masks_and_explicit_wrap_is_descriptor_gated() -> None:
    arch = descriptor()
    code = AddressSpaceId("code")
    data = AddressSpaceId("data")
    assert arch.add(HsxAddress(code, 0xFC), 4, AddressArithmeticMode.CHECKED).status is AddressStatus.OUT_OF_RANGE
    assert arch.add(HsxAddress(code, 0xFFFC), 4, AddressArithmeticMode.CHECKED).status is AddressStatus.OVERFLOW
    assert arch.subtract(HsxAddress(code, 0), 4, AddressArithmeticMode.CHECKED).status is AddressStatus.UNDERFLOW
    assert arch.add(HsxAddress(code, 0xFFFC), 4, AddressArithmeticMode.WRAP).status is AddressStatus.WRAP_FORBIDDEN
    wrapped = arch.add(HsxAddress(data, (1 << 24) - 2), 2, AddressArithmeticMode.WRAP)
    assert wrapped.status is AddressStatus.VALID
    assert wrapped.value == HsxAddress(data, 0)
    wrapped_subtract = arch.subtract(HsxAddress(data, 0), 2, AddressArithmeticMode.WRAP)
    assert wrapped_subtract.value == HsxAddress(data, (1 << 24) - 2)
    with pytest.raises(TypeError, match="mode"):
        arch.add(HsxAddress(code, 0), 1, "checked")  # type: ignore[arg-type]


def test_half_open_ranges_reject_hole_crossing_and_preserve_declared_units() -> None:
    arch = descriptor()
    code = AddressSpaceId("code")
    word = AddressSpaceId("word")
    valid = arch.range(HsxAddress(code, 0xF0), 0x10)
    assert valid.status is AddressStatus.VALID
    assert valid.value.end_unsigned_value == 0x100
    assert not valid.value.contains(HsxAddress(code, 0x100))
    assert arch.range(HsxAddress(code, 0xF0), 0x20).status is AddressStatus.OUT_OF_RANGE
    word_range = arch.range(HsxAddress(word, 2), 3)
    assert word_range.value.length_units == 3
    assert word_range.value.end_unsigned_value == 5
    assert HsxAddress(code, 4) != HsxAddress(word, 4)


def test_exact_whole_byte_unit_conversions_cover_multiple_unit_widths() -> None:
    arch = descriptor()
    code = AddressSpaceId("code")
    word = AddressSpaceId("word")
    bit = AddressSpaceId("bit")
    assert arch.units_for_bytes(code, 7).value == 7
    assert arch.bytes_for_units(code, 7).value == 7
    assert arch.units_for_bytes(word, 6).value == 3
    assert arch.bytes_for_units(word, 3).value == 6
    assert arch.units_for_bytes(word, 3).status is AddressStatus.MISALIGNED
    assert arch.units_for_bytes(bit, 1).status is AddressStatus.UNIT_CONVERSION_UNSUPPORTED
    assert arch.bytes_for_units(bit, 8).status is AddressStatus.UNIT_CONVERSION_UNSUPPORTED
    assert arch.units_for_bytes(AddressSpaceId("none"), 1).status is AddressStatus.UNKNOWN_SPACE


def test_format_uses_address_width_not_unit_width() -> None:
    arch = descriptor()
    assert arch.format(HsxAddress(AddressSpaceId("code"), 0x20)) == "code:0x0020"
    assert arch.format(HsxAddress(AddressSpaceId("word"), 0x20)) == "word:0x020"


def test_scalar_bytes_exact_fixed_width_twos_complement_endian_and_padding() -> None:
    assert ScalarBytes.encode(0x1234, False, 16, ByteOrder.BIG) == b"\x12\x34"
    assert ScalarBytes.encode(0x1234, False, 16, ByteOrder.LITTLE) == b"\x34\x12"
    assert ScalarBytes.encode(1, False, 9, ByteOrder.BIG) == b"\x00\x01"
    assert ScalarBytes.encode(-1, True, 9, ByteOrder.BIG) == b"\xff\xff"
    assert ScalarBytes.encode(-256, True, 9, ByteOrder.LITTLE) == b"\x00\xff"
    assert ScalarBytes.encode(255, False, 9, ByteOrder.BIG) == b"\x00\xff"
    for value, signed, bits in ((256, True, 9), (-257, True, 9), (512, False, 9), (-1, False, 8)):
        with pytest.raises(OverflowError):
            ScalarBytes.encode(value, signed, bits, ByteOrder.LITTLE)


def test_simple_register_page_and_expression_records_enforce_cardinality() -> None:
    with pytest.raises(ValueError):
        RegisterSelection(True, ("R0",))
    with pytest.raises(ValueError):
        RegisterSelection(False, ())
    with pytest.raises(ValueError):
        PageRequest(0, 257)
    available = RegisterValue("R0", 8, 255, True)
    unavailable = RegisterValue("PC", 16, None, False)
    assert RegisterSet([available, unavailable]).registers == (available, unavailable)
    with pytest.raises(ValueError, match="unique"):
        RegisterSet((available, available))
    constant = ConstantExpression(7, 3, ByteOrder.BIG)
    assert ScalarBytes.encode(
        constant.unsigned_value, False, constant.bit_width, constant.byte_order
    ) == b"\x07"
