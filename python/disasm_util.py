#!/usr/bin/env python3

from typing import Dict, Optional, Sequence

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


def format_operands(
    mnemonic: str,
    rd: int,
    rs1: int,
    rs2: int,
    *,
    imm: Optional[int] = None,
    imm_raw: Optional[int] = None,
    reg_values: Optional[Sequence[int]] = None,
    flags: Optional[int] = None,
    next_word: Optional[int] = None,
    pc: Optional[int] = None,
) -> str:
    """Render a human readable operand string for trace/disassembly output."""

    mnemonic = (mnemonic or "").upper()
    imm = int(imm) if imm is not None else None
    imm_raw = int(imm_raw) if imm_raw is not None else None

    def _fmt_with_hex(value: Optional[int], raw: Optional[int], *, default_width: int = 3) -> str:
        if value is None and raw is None:
            return ""
        if raw is None:
            return str(value if value is not None else 0)
        width = max(default_width, ((raw.bit_length() + 3) // 4) or 1)
        val = value if value is not None else raw
        return f"{val} (0x{raw:0{width}X})"

    def _reg_src(idx: int) -> str:
        if reg_values is not None and 0 <= idx < len(reg_values):
            return f"R{idx}=0x{reg_values[idx] & 0xFFFFFFFF:08X}"
        return f"R{idx}"

    def _reg_dst(idx: int) -> str:
        return f"R{idx}"

    def _ea(base_idx: int, offset: int) -> str:
        base_txt = _reg_src(base_idx)
        off_txt = _fmt_with_hex(offset, imm_raw)
        if reg_values is not None and 0 <= base_idx < len(reg_values):
            base_val = reg_values[base_idx] & 0xFFFFFFFF
            addr = (base_val + offset) & 0xFFFFFFFF
            return f"{base_txt} + {off_txt} (addr=0x{addr:08X})"
        return f"{base_txt} + {off_txt}"

    def _alu(
        op_symbol: str,
        compute,
    ) -> str:
        left = _reg_src(rs1)
        right = _reg_src(rs2)
        if reg_values is not None and 0 <= rs1 < len(reg_values) and 0 <= rs2 < len(reg_values):
            try:
                result = compute(reg_values[rs1] & 0xFFFFFFFF, reg_values[rs2] & 0xFFFFFFFF)
            except ZeroDivisionError:
                result = None
        else:
            result = None
        if result is not None:
            return f"{_reg_dst(rd)} <- {left} {op_symbol} {right} -> 0x{result & 0xFFFFFFFF:08X}"
        return f"{_reg_dst(rd)} <- {left} {op_symbol} {right}"

    if mnemonic == "LDI":
        return f"{_reg_dst(rd)} <- {_fmt_with_hex(imm, imm_raw)}"
    if mnemonic == "LDI32":
        if next_word is None:
            return f"{_reg_dst(rd)} <- <invalid 32-bit immediate>"
        return f"{_reg_dst(rd)} <- 0x{next_word & 0xFFFFFFFF:08X}"
    if mnemonic == "LD":
        offset = imm or 0
        return f"{_reg_dst(rd)} <- MEM[{_ea(rs1, offset)}]"
    if mnemonic == "LDB":
        offset = imm or 0
        return f"{_reg_dst(rd)} <- MEM8[{_ea(rs1, offset)}]"
    if mnemonic == "LDH":
        offset = imm or 0
        return f"{_reg_dst(rd)} <- MEM16[{_ea(rs1, offset)}]"
    if mnemonic == "ST":
        offset = imm or 0
        return f"MEM[{_ea(rs1, offset)}] <- {_reg_src(rs2)}"
    if mnemonic == "STB":
        offset = imm or 0
        return f"MEM8[{_ea(rs1, offset)}] <- {_reg_src(rs2)}"
    if mnemonic == "STH":
        offset = imm or 0
        return f"MEM16[{_ea(rs1, offset)}] <- {_reg_src(rs2)}"
    if mnemonic == "MOV":
        return f"{_reg_dst(rd)} <- {_reg_src(rs1)}"
    if mnemonic == "ADD":
        return _alu("+", lambda a, b: (a + b) & 0xFFFFFFFF)
    if mnemonic == "SUB":
        return _alu("-", lambda a, b: (a - b) & 0xFFFFFFFF)
    if mnemonic == "MUL":
        return _alu("*", lambda a, b: (a * b) & 0xFFFFFFFF)
    if mnemonic == "DIV":
        def _div(a: int, b: int) -> int:
            if b == 0:
                raise ZeroDivisionError()
            return (a // b) & 0xFFFFFFFF

        return _alu("/", _div)
    if mnemonic == "AND":
        return _alu("&", lambda a, b: a & b)
    if mnemonic == "OR":
        return _alu("|", lambda a, b: a | b)
    if mnemonic == "XOR":
        return _alu("^", lambda a, b: a ^ b)
    if mnemonic == "NOT":
        src = _reg_src(rs1)
        if reg_values is not None and 0 <= rs1 < len(reg_values):
            result = (~(reg_values[rs1] & 0xFFFFFFFF)) & 0xFFFFFFFF
            return f"{_reg_dst(rd)} <- ~{src} -> 0x{result:08X}"
        return f"{_reg_dst(rd)} <- ~{src}"
    if mnemonic == "CMP":
        left = _reg_src(rs1)
        right = _reg_src(rs2)
        return f"{left} ? {right}"
    if mnemonic in {"JMP", "JZ", "JNZ"}:
        target = (imm or 0) & 0xFFFFFFFF
        target_txt = f"0x{target:08X}"
        imm_txt = _fmt_with_hex(imm, imm_raw)
        parts = [target_txt, f"imm={imm_txt}"]
        if mnemonic in {"JZ", "JNZ"} and flags is not None:
            cond = "Z=1" if (flags & 0x1) else "Z=0"
            parts.append(cond)
        return " ".join(parts)
    if mnemonic == "CALL":
        offset = (imm or 0)
        offset_txt = _fmt_with_hex(offset, imm_raw)
        if reg_values is not None and ((rs1 == 0 and pc is not None) or 0 <= rs1 < len(reg_values)):
            base_val = pc if rs1 == 0 else reg_values[rs1]
            base_fmt = f"PC=0x{(pc or 0) & 0xFFFF:04X}" if rs1 == 0 else _reg_src(rs1)
            target = (int(base_val) + (offset << 2)) & 0xFFFF
            return f"{base_fmt} + ({offset_txt} << 2) -> 0x{target:04X}"
        base_fmt = "PC" if rs1 == 0 else _reg_src(rs1)
        return f"{base_fmt} + ({offset_txt} << 2)"
    if mnemonic == "RET":
        return ""
    if mnemonic == "PUSH":
        return f"{_reg_src(rs1)}"
    if mnemonic == "POP":
        return f"{_reg_dst(rd)}"
    if mnemonic == "SVC":
        mod = ((imm or 0) >> 8) & 0x0F
        fn = (imm or 0) & 0xFF
        return f"mod=0x{mod:X} fn=0x{fn:X}"
    if mnemonic == "BRK":
        return f"code=0x{(imm or 0) & 0xFF:02X}"

    return f"rd={rd} rs1={rs1} rs2={rs2} imm={imm if imm is not None else 0}"
