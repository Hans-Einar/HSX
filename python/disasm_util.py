#!/usr/bin/env python3

from typing import Dict

OPCODES: Dict[str, int] = {
    "LDI": 0x01, "LD": 0x02, "ST": 0x03, "MOV": 0x04, "LDB": 0x06, "LDH": 0x07, "STB": 0x08, "STH": 0x09,
    "ADD": 0x10, "SUB": 0x11, "MUL": 0x12, "DIV": 0x13,
    "AND": 0x14, "OR": 0x15, "XOR": 0x16, "NOT": 0x17,
    "CMP": 0x20, "JMP": 0x21, "JZ": 0x22, "JNZ": 0x23, "CALL": 0x24, "RET": 0x25,
    "SVC": 0x30, "PUSH": 0x40, "POP": 0x41,
    "FADD": 0x50, "FSUB": 0x51, "FMUL": 0x52, "FDIV": 0x53, "I2F": 0x54, "F2I": 0x55,
    "LDI32": 0x60, "BRK": 0x7F
}

OPCODE_NAMES: Dict[int, str] = {code: name for name, code in OPCODES.items()}


def instruction_size(mnemonic: str) -> int:
    return 8 if mnemonic.upper() == "LDI32" else 4
