#!/usr/bin/env python3
"""Shared opcode definitions for the HSX toolchain.

Keeping the canonical mapping in a single module prevents drift between the
assembler, disassembler, and documentation. Tests assert that all consumers
import these tables unchanged.
"""

from __future__ import annotations

from typing import Dict, Iterable, Tuple

# Ordered list so docs and tooling can iterate in a stable order.
OPCODE_LIST: Tuple[Tuple[str, int], ...] = (
    ("LDI", 0x01),
    ("LD", 0x02),
    ("ST", 0x03),
    ("MOV", 0x04),
    ("LDB", 0x06),
    ("LDH", 0x07),
    ("STB", 0x08),
    ("STH", 0x09),
    ("ADD", 0x10),
    ("SUB", 0x11),
    ("MUL", 0x12),
    ("DIV", 0x13),
    ("AND", 0x14),
    ("OR", 0x15),
    ("XOR", 0x16),
    ("NOT", 0x17),
    ("CMP", 0x20),
    ("JMP", 0x21),
    ("JZ", 0x22),
    ("JNZ", 0x23),
    ("CALL", 0x24),
    ("RET", 0x25),
    ("SVC", 0x30),
    ("LSL", 0x31),
    ("LSR", 0x32),
    ("ASR", 0x33),
    ("ADC", 0x34),
    ("SBC", 0x35),
    ("PUSH", 0x40),
    ("POP", 0x41),
    ("FADD", 0x50),
    ("FSUB", 0x51),
    ("FMUL", 0x52),
    ("FDIV", 0x53),
    ("I2F", 0x54),
    ("F2I", 0x55),
    ("LDI32", 0x60),
    ("BRK", 0x7F),
)

OPCODES: Dict[str, int] = {mnemonic: opcode for mnemonic, opcode in OPCODE_LIST}
OPCODE_NAMES: Dict[int, str] = {opcode: mnemonic for mnemonic, opcode in OPCODE_LIST}

__all__ = [
    "OPCODE_LIST",
    "OPCODES",
    "OPCODE_NAMES",
]


def opcode_values() -> Iterable[int]:
    """Return all VM opcode numeric values."""

    return OPCODE_NAMES.keys()

