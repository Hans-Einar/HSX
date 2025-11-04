from __future__ import annotations

from python import asm as hsx_asm
from python.disassemble import disassemble


def _words_to_bytes(words: list[int]) -> bytes:
    return b"".join((word & 0xFFFFFFFF).to_bytes(4, "big") for word in words)


def test_disassemble_reports_operands_for_new_opcodes() -> None:
    words = [
        hsx_asm.emit_word(hsx_asm.OPC["LSL"], hsx_asm.regnum("R2"), hsx_asm.regnum("R3"), hsx_asm.regnum("R4"), 0),
        hsx_asm.emit_word(hsx_asm.OPC["LSR"], hsx_asm.regnum("R7"), hsx_asm.regnum("R8"), hsx_asm.regnum("R9"), 0),
        hsx_asm.emit_word(hsx_asm.OPC["ASR"], hsx_asm.regnum("R10"), hsx_asm.regnum("R11"), hsx_asm.regnum("R12"), 0),
        hsx_asm.emit_word(hsx_asm.OPC["ADC"], hsx_asm.regnum("R1"), hsx_asm.regnum("R2"), hsx_asm.regnum("R3"), 0),
        hsx_asm.emit_word(hsx_asm.OPC["SBC"], hsx_asm.regnum("R4"), hsx_asm.regnum("R5"), hsx_asm.regnum("R6"), 0),
        hsx_asm.emit_word(hsx_asm.OPC["DIV"], hsx_asm.regnum("R5"), hsx_asm.regnum("R6"), hsx_asm.regnum("R7"), 0),
    ]
    listing = disassemble(_words_to_bytes(words))
    mnemonics = [entry["mnemonic"] for entry in listing]
    assert mnemonics == ["LSL", "LSR", "ASR", "ADC", "SBC", "DIV"]
    assert listing[0]["operands"] == "R2 <- R3 << R4"
    assert listing[1]["operands"] == "R7 <- R8 >> R9"
    assert listing[2]["operands"] == "R10 <- R11 >>> R12"
    assert listing[3]["operands"] == "R1 <- R2 + R3 + C"
    assert listing[4]["operands"] == "R4 <- R5 - R6 - (1 - C)"
    assert listing[5]["operands"] == "R5 <- R6 / R7"


def test_assemble_then_disassemble_round_trip_words() -> None:
    asm_lines = [
        ".entry main",
        ".text",
        "main:",
        "    LDI R1, 5",
        "    LDI R2, 3",
        "    LSL R3, R1, R2",
        "    ADC R4, R3, R1",
        "    SBC R5, R4, R2",
        "    DIV R6, R4, R1",
        "    BRK 0",
    ]
    words, entry, *_ = hsx_asm.assemble(asm_lines, for_object=True)
    assert entry == 0
    bytecode = _words_to_bytes(words)
    listing = disassemble(bytecode)
    decoded_words = [entry["word"] for entry in listing]
    assert decoded_words == [word & 0xFFFFFFFF for word in words]
