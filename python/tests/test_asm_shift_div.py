from __future__ import annotations

import pytest

from python import asm as hsx_asm


def _assemble(mnemonic: str, dst: str, src1: str, src2: str) -> int:
    code, *_ = hsx_asm.assemble(
        [
            ".text\n",
            ".entry main\n",
            "main:\n",
            f"    {mnemonic} {dst}, {src1}, {src2}\n",
        ],
        for_object=True,
    )
    assert len(code) == 1
    return code[0]


@pytest.mark.parametrize(
    ("mnemonic", "rd", "rs1", "rs2"),
    [
        ("LSL", "R2", "R3", "R4"),
        ("LSR", "R7", "R8", "R9"),
        ("ASR", "R10", "R11", "R12"),
    ],
)
def test_shift_opcode_encodings(mnemonic: str, rd: str, rs1: str, rs2: str) -> None:
    encoded = _assemble(mnemonic, rd, rs1, rs2)
    expected = hsx_asm.emit_word(
        hsx_asm.OPC[mnemonic],
        hsx_asm.regnum(rd),
        hsx_asm.regnum(rs1),
        hsx_asm.regnum(rs2),
        0,
    )
    assert encoded == expected


def test_div_opcode_encoding() -> None:
    encoded = _assemble("DIV", "R5", "R6", "R7")
    expected = hsx_asm.emit_word(
        hsx_asm.OPC["DIV"],
        hsx_asm.regnum("R5"),
        hsx_asm.regnum("R6"),
        hsx_asm.regnum("R7"),
        0,
    )
    assert encoded == expected


@pytest.mark.parametrize(
    "line",
    [
        "    LSL R16, R1, R2",
        "    LSL R0, R16, R2",
        "    LSL R0, R1, R16",
        "    DIV R17, R1, R2",
    ],
)
def test_invalid_register_rejected(line: str) -> None:
    with pytest.raises(ValueError):
        hsx_asm.assemble(
            [
                ".text\n",
                ".entry main\n",
                "main:\n",
                f"{line}\n",
            ],
            for_object=True,
        )
