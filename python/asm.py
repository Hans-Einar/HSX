#!/usr/bin/env python3
import sys, re, struct, zlib, argparse, json
from pathlib import Path
from typing import Any, Dict

MAGIC = 0x48535845  # 'HSXE'
VERSION = 0x0001
RODATA_BASE = 0x4000

OPC = {
    "LDI":   0x01, "LD": 0x02, "ST": 0x03, "MOV": 0x04, "LDB": 0x06, "LDH": 0x07, "STB": 0x08, "STH": 0x09,
    "ADD": 0x10, "SUB": 0x11, "MUL": 0x12, "DIV": 0x13,
    "AND": 0x14, "OR": 0x15, "XOR": 0x16, "NOT": 0x17,
    "CMP": 0x20, "JMP": 0x21, "JZ": 0x22, "JNZ": 0x23, "CALL": 0x24, "RET": 0x25,
    "SVC": 0x30, "PUSH": 0x40, "POP": 0x41,
    "FADD": 0x50, "FSUB": 0x51, "FMUL": 0x52, "FDIV": 0x53, "I2F": 0x54, "F2I": 0x55,
    "LDI32": 0x60
}

REGISTER_RE = re.compile(r"R([0-9]|1[0-5])\b", re.IGNORECASE)
SYMBOL_TOKEN_RE = re.compile(r"[A-Za-z_.][A-Za-z0-9_.$]*")
EXPR_TOKEN_RE = re.compile(r"(lo16|hi16|off16)\(([^)]+)\)")
SECTION_TEXT = "text"
SECTION_DATA = "data"


def regnum(tok):
    m = REGISTER_RE.fullmatch(tok)
    if not m:
        raise ValueError(f"Bad register '{tok}'")
    n = int(m.group(1))
    if n < 0 or n > 15:
        raise ValueError("Register out of range 0..15")
    return n


def parse_int(token):
    token = token.strip()
    if token.lower().startswith('0x'):
        return int(token, 16)
    if token.lower().startswith('0b'):
        return int(token, 2)
    if token.startswith("'") and token.endswith("'") and len(token) == 3:
        return ord(token[1])
    return int(token, 10)


def sign12(val):
    if val < -2048 or val > 2047:
        raise ValueError(f"Immediate out of 12-bit signed range: {val}")
    return val & 0x0FFF


def emit_word(op, rd=0, rs1=0, rs2=0, imm=0):
    return ((op & 0xFF) << 24) | ((rd & 0x0F) << 20) | ((rs1 & 0x0F) << 16) | ((rs2 & 0x0F) << 12) | (imm & 0x0FFF)


def set_imm12(word, imm):
    mask = 0x0FFF
    return (word & ~mask) | (sign12(imm) & mask)


def split_args(arg_str):
    if not arg_str:
        return []
    args = []
    current = []
    quote = None
    escape = False
    for ch in arg_str:
        if quote:
            current.append(ch)
            if escape:
                escape = False
            elif ch == '\\':
                escape = True
            elif ch == quote:
                quote = None
        else:
            if ch in (chr(34), chr(39)):
                quote = ch
                current.append(ch)
            elif ch == ',':
                args.append(''.join(current).strip())
                current = []
            else:
                current.append(ch)
    if quote:
        raise ValueError('Unterminated string literal')
    if current:
        args.append(''.join(current).strip())
    return [a for a in args if a]

def parse_string_literal(token):
    token = token.strip()
    if len(token) < 2 or token[0] != token[-1] or token[0] not in ('"', "'"):
        raise ValueError(f"Invalid string literal: {token}")
    body = token[1:-1]
    out = bytearray()
    i = 0
    while i < len(body):
        ch = body[i]
        if ch != '\\':
            out.append(ord(ch))
            i += 1
            continue
        i += 1
        if i >= len(body):
            raise ValueError("Trailing escape")
        esc = body[i]
        if esc == 'n':
            out.append(0x0A)
        elif esc == 'r':
            out.append(0x0D)
        elif esc == 't':
            out.append(0x09)
        elif esc == '\\':
            out.append(ord('\\'))
        elif esc == '0':
            out.append(0)
        elif esc == 'x':
            if i + 2 >= len(body):
                raise ValueError('\\x expects two hex digits')
            hx = body[i + 1:i + 3]
            out.append(int(hx, 16))
            i += 2
        else:
            out.append(ord(esc))
    return bytes(out)


def _expand_includes(lines, base_dir: Path, seen: set[Path]) -> list[str]:
    output: list[str] = []
    base_dir = base_dir.resolve()
    for line in lines:
        stripped = line.strip()
        if not stripped:
            output.append(line)
            continue
        token = stripped.split(None, 1)[0].lower()
        if token != '.include':
            output.append(line)
            continue
        parts = stripped.split(None, 1)
        if len(parts) != 2:
            raise ValueError(".include expects a filename")
        arg = parts[1].split(';', 1)[0].strip()
        if not arg:
            raise ValueError(".include missing filename")
        if arg[0] in ('"', "'"):
            include_bytes = parse_string_literal(arg)
            include_name = include_bytes.decode('utf-8')
        else:
            include_name = arg.split()[0]
        include_path = (base_dir / include_name).resolve()
        if include_path in seen:
            raise ValueError(f"Recursive .include detected for {include_path}")
        if not include_path.exists():
            raise FileNotFoundError(f"Included file not found: {include_path}")
        with include_path.open('r', encoding='utf-8') as inc_file:
            sub_lines = inc_file.read().splitlines(True)
        output.extend(_expand_includes(sub_lines, include_path.parent, seen | {include_path}))
    return output


def parse_symbol_token(token):
    token = token.strip()
    m = EXPR_TOKEN_RE.fullmatch(token)
    if m:
        kind = m.group(1)
        name = m.group(2).strip()
        if not SYMBOL_TOKEN_RE.fullmatch(name):
            raise ValueError(f"Invalid symbol name in expression: {token}")
        return kind, name
    if SYMBOL_TOKEN_RE.fullmatch(token):
        return ("symbol", token)
    return None


def _build_symbol_table(labels: Dict[str, tuple[str, int]], externs: set[str], imports_decl: set[str]) -> Dict[str, Dict[str, Any]]:
    symtab: Dict[str, Dict[str, Any]] = {}
    for name, (section, offset) in labels.items():
        if section == SECTION_TEXT:
            abs_addr = offset
        elif section == SECTION_DATA:
            abs_addr = RODATA_BASE + offset
        else:
            continue
        symtab[name] = {
            "section": section,
            "offset": offset,
            "abs_addr": abs_addr,
            "unit_local": name not in externs and name not in imports_decl,
        }
    return symtab


def _compute_local_reloc_value(reloc: Dict[str, Any], sym_info: Dict[str, Any]) -> int:
    kind = reloc.get("kind")
    if kind in (None, "symbol"):
        return int(sym_info["abs_addr"])
    if kind == "lo16":
        return int(sym_info["abs_addr"]) & 0xFFFF
    if kind == "hi16":
        return (int(sym_info["abs_addr"]) >> 16) & 0xFFFF
    if kind == "off16":
        return int(sym_info["offset"]) & 0xFFFF
    raise ValueError(f"Unsupported relocation kind {kind}")


def _resolve_unit_local_relocs(code_words: list[int], rodata_buf: bytearray, relocs: list[Dict[str, Any]], symtab: Dict[str, Dict[str, Any]]) -> list[Dict[str, Any]]:
    remaining: list[Dict[str, Any]] = []
    for reloc in relocs:
        symbol = reloc.get("symbol")
        sym_info = symtab.get(symbol)
        if not sym_info or not sym_info.get("unit_local"):
            remaining.append(reloc)
            continue
        value = _compute_local_reloc_value(reloc, sym_info)
        section = reloc.get("section")
        rtype = reloc.get("type")
        if section == "code":
            idx = reloc["index"]
            if rtype in {"imm12", "jump", "mem"}:
                code_words[idx] = set_imm12(code_words[idx], value)
            elif rtype == "imm32":
                code_words[idx] = value & 0xFFFFFFFF
            else:
                raise ValueError(f"Unsupported code relocation type {rtype}")
        elif section == "rodata":
            offset = reloc["offset"]
            if rtype == "data_word":
                rodata_buf[offset:offset + 4] = (value & 0xFFFFFFFF).to_bytes(4, "little")
            elif rtype == "data_half":
                rodata_buf[offset:offset + 2] = (value & 0xFFFF).to_bytes(2, "little")
            elif rtype == "data_byte":
                rodata_buf[offset] = value & 0xFF
            else:
                raise ValueError(f"Unsupported rodata relocation type {rtype}")
        else:
            raise ValueError(f"Unknown relocation section {section}")
    return remaining


def assemble(lines, *, include_base: Path | None = None, for_object: bool = False):
    include_base = include_base or Path.cwd()
    lines = _expand_includes(list(lines), include_base, set())
    code = []
    rodata = bytearray()
    labels = {}
    fixups = []
    relocs = []
    entry_symbol = None
    externs = set()
    imports_decl = set()
    exports: Dict[str, Dict[str, int]] = {}
    explicit_exports = set()
    entry = 0
    section = SECTION_TEXT
    pc = 0
    data_pc = 0

    def add_code_word(word):
        nonlocal pc
        code.append(word & 0xFFFFFFFF)
        pc += 4

    def add_data_bytes(data):
        nonlocal data_pc
        rodata.extend(data)
        data_pc += len(data)

    def current_offset():
        return pc if section == SECTION_TEXT else data_pc

    def define_label(name):
        if name in labels:
            raise ValueError(f"Duplicate label: {name}")
        labels[name] = (section, current_offset())
        if name in explicit_exports:
            exports.setdefault(name, {'section': section, 'offset': current_offset()})

    def resolve_symbol(name):
        if name in labels:
            sec, offset = labels[name]
            if sec == SECTION_TEXT:
                return offset
            if sec == SECTION_DATA:
                return RODATA_BASE + offset
        if name in imports_decl or name in externs:
            return None
        raise ValueError(f"Unknown label {name}")

    def eval_symbol_ref(ref):
        kind, name = ref
        if kind == "symbol":
            return resolve_symbol(name)
        if kind in ("lo16", "hi16", "off16"):
            if kind == "off16":
                if name not in labels:
                    if name in imports_decl or name in externs:
                        return None
                    raise ValueError(f"Unknown label {name}")
                sec, offset = labels[name]
                if sec != SECTION_DATA:
                    raise ValueError(f"off16() expects .data symbol: {name}")
                return offset & 0xFFFF
            value = resolve_symbol(name)
            if value is None:
                return None
            if kind == "lo16":
                return value & 0xFFFF
            if kind == "hi16":
                return (value >> 16) & 0xFFFF
        raise ValueError(f"Unsupported symbol reference {ref}")

    for raw in lines:
        line = raw.split(';')[0].strip()
        if not line:
            continue
        if line.endswith(':'):
            define_label(line[:-1].strip())
            continue
        lower = line.lower()
        if lower.startswith('.text'):
            section = SECTION_TEXT
            continue
        if lower.startswith('.data'):
            section = SECTION_DATA
            continue
        if lower.startswith('.extern'):
            parts = line.split()
            if len(parts) != 2:
                raise ValueError(".extern expects symbol")
            externs.add(parts[1])
            continue
        if lower.startswith('.export'):
            parts = line.split()
            if len(parts) != 2:
                raise ValueError(".export expects symbol")
            explicit_exports.add(parts[1])
            continue
        if lower.startswith('.import'):
            parts = line.split()
            if len(parts) != 2:
                raise ValueError(".import expects symbol")
            imports_decl.add(parts[1])
            continue
        if lower.startswith('.entry'):
            if section != SECTION_TEXT:
                raise ValueError(".entry only valid in .text section")
            parts = line.split()
            if len(parts) == 2:
                try:
                    entry_value = parse_int(parts[1])
                    entry = entry_value
                    entry_symbol = None
                except Exception:
                    fixups.append({'type': 'entry', 'symbol': parts[1]})
                    entry_symbol = parts[1]
            else:
                entry = pc
                entry_symbol = None
            continue
        if lower.startswith('.org'):
            if section != SECTION_TEXT:
                raise ValueError(".org only supported in .text section")
            parts = line.split()
            if len(parts) != 2:
                raise ValueError(".org expects one argument")
            newpc = parse_int(parts[1])
            while pc < newpc:
                add_code_word(0)
            continue

        if section == SECTION_DATA:
            if lower.startswith('.byte'):
                arg_str = line.split(None, 1)[1] if ' ' in line else ''
                for tok in split_args(arg_str):
                    if tok.startswith(('"', "'")) and len(tok) > 1:
                        add_data_bytes(parse_string_literal(tok))
                        continue
                    try:
                        value = parse_int(tok)
                        add_data_bytes(bytes([(value) & 0xFF]))
                    except ValueError:
                        ref = parse_symbol_token(tok)
                        if not ref:
                            raise ValueError(f"Unsupported .byte argument: {tok}")
                        offset = data_pc
                        add_data_bytes(b"\x00")
                        fixups.append({'type': 'data_byte', 'offset': offset, 'ref': ref})
                continue
            if lower.startswith('.word'):
                arg_str = line.split(None, 1)[1] if ' ' in line else ''
                for tok in split_args(arg_str):
                    try:
                        value = parse_int(tok)
                        add_data_bytes((value & 0xFFFFFFFF).to_bytes(4, 'little'))
                    except ValueError:
                        ref = parse_symbol_token(tok)
                        if not ref:
                            raise ValueError(f"Unsupported .word argument: {tok}")
                        offset = data_pc
                        add_data_bytes(b"\x00" * 4)
                        fixups.append({'type': 'data_word', 'offset': offset, 'ref': ref})
                continue
            if lower.startswith('.half') or lower.startswith('.hword'):
                arg_str = line.split(None, 1)[1] if ' ' in line else ''
                for tok in split_args(arg_str):
                    try:
                        value = parse_int(tok)
                        add_data_bytes((value & 0xFFFF).to_bytes(2, 'little'))
                    except ValueError:
                        ref = parse_symbol_token(tok)
                        if not ref:
                            raise ValueError(f"Unsupported .half argument: {tok}")
                        offset = data_pc
                        add_data_bytes(b"\x00" * 2)
                        fixups.append({'type': 'data_half', 'offset': offset, 'ref': ref})
                continue
            if lower.startswith('.asciz') or lower.startswith('.string'):
                parts = line.split(None, 1)
                if len(parts) != 2:
                    raise ValueError(f"{parts[0]} expects a string literal")
                data = parse_string_literal(parts[1].strip()) + b"\x00"
                add_data_bytes(data)
                continue
            if lower.startswith('.ascii'):
                parts = line.split(None, 1)
                if len(parts) != 2:
                    raise ValueError(".ascii expects a string literal")
                add_data_bytes(parse_string_literal(parts[1].strip()))
                continue
            if lower.startswith('.align'):
                parts = line.split()
                if len(parts) != 2:
                    raise ValueError(".align expects a value")
                align = parse_int(parts[1])
                if align <= 0:
                    raise ValueError(".align value must be positive")
                while data_pc % align:
                    add_data_bytes(b"\x00")
                continue
            if lower.startswith('.zero'):
                parts = line.split()
                if len(parts) != 2:
                    raise ValueError(".zero expects size")
                count = parse_int(parts[1])
                if count < 0:
                    raise ValueError(".zero size must be non-negative")
                add_data_bytes(b"\x00" * count)
                continue
            raise ValueError(f"Unsupported directive in .data: {line}")

        tokens = re.split(r'[,\s]+', line.strip())
        mnem = tokens[0].upper()
        args = tokens[1:] if len(tokens) > 1 else []
        if mnem not in OPC:
            raise ValueError(f"Unknown mnemonic: {mnem}")
        op = OPC[mnem]

        if mnem == 'RET':
            add_code_word(emit_word(op))
        elif mnem == 'MOV':
            rd, rs1 = regnum(args[0]), regnum(args[1])
            add_code_word(emit_word(op, rd, rs1, 0, 0))
        elif mnem == 'PUSH':
            rs1 = regnum(args[0])
            add_code_word(emit_word(op, 0, rs1, 0, 0))
        elif mnem == 'POP':
            rd = regnum(args[0])
            add_code_word(emit_word(op, rd, 0, 0, 0))
        elif mnem in ('ADD', 'SUB', 'MUL', 'DIV', 'AND', 'OR', 'XOR', 'FADD', 'FSUB', 'FMUL', 'FDIV'):
            rd, rs1, rs2 = regnum(args[0]), regnum(args[1]), regnum(args[2])
            add_code_word(emit_word(op, rd, rs1, rs2, 0))
        elif mnem in ('NOT', 'I2F', 'F2I'):
            rd, rs1 = regnum(args[0]), regnum(args[1])
            add_code_word(emit_word(op, rd, rs1, 0, 0))
        elif mnem == 'LDI':
            rd = regnum(args[0])
            imm_tok = args[1]
            try:
                imm_val = parse_int(imm_tok)
                add_code_word(emit_word(op, rd, 0, 0, sign12(imm_val)))
            except ValueError:
                ref = parse_symbol_token(imm_tok)
                if not ref:
                    raise
                add_code_word(emit_word(op, rd, 0, 0, 0))
                fixups.append({'type': 'imm12', 'index': len(code) - 1, 'ref': ref})
        elif mnem == 'LDI32':
            rd = regnum(args[0])
            imm_tok = args[1]
            try:
                imm_val = parse_int(imm_tok)
                add_code_word(emit_word(op, rd, 0, 0, 0))
                add_code_word(imm_val & 0xFFFFFFFF)
            except ValueError:
                ref = parse_symbol_token(imm_tok)
                if not ref:
                    raise
                add_code_word(emit_word(op, rd, 0, 0, 0))
                add_code_word(0)
                fixups.append({'type': 'imm32', 'index': len(code) - 1, 'ref': ref})
        elif mnem in ('LD', 'LDB', 'LDH'):
            rd = regnum(args[0])
            m = re.match(r"\[(R[0-9]|R1[0-5])\s*\+\s*([^\]]+)\]", args[1], re.IGNORECASE)
            if not m:
                raise ValueError("LD expects [Rs+imm]")
            rs1 = regnum(m.group(1))
            offs_token = m.group(2).strip()
            try:
                imm_val = parse_int(offs_token)
            except ValueError:
                ref = parse_symbol_token(offs_token)
                if not ref:
                    raise ValueError(f"Unsupported offset expression: {offs_token}")
                imm_val = 0
                fixups.append({'type': 'mem', 'index': len(code), 'ref': ref})
            add_code_word(emit_word(op, rd, rs1, 0, sign12(imm_val)))
        elif mnem in ('ST', 'STB', 'STH'):
            m = re.match(r"\[(R[0-9]|R1[0-5])\s*\+\s*([^\]]+)\]", args[0], re.IGNORECASE)
            if not m:
                raise ValueError("ST expects [Rs+imm]")
            rs1 = regnum(m.group(1))
            offs_token = m.group(2).strip()
            rs2 = regnum(args[1])
            try:
                imm_val = parse_int(offs_token)
            except ValueError:
                ref = parse_symbol_token(offs_token)
                if not ref:
                    raise ValueError(f"Unsupported offset expression: {offs_token}")
                imm_val = 0
                fixups.append({'type': 'mem', 'index': len(code), 'ref': ref})
            add_code_word(emit_word(op, 0, rs1, rs2, sign12(imm_val)))
        elif mnem == 'CMP':
            rs1, rs2 = regnum(args[0]), regnum(args[1])
            add_code_word(emit_word(op, 0, rs1, rs2, 0))
        elif mnem in ('JMP', 'JZ', 'JNZ', 'CALL'):
            target = args[0]
            try:
                imm_val = parse_int(target)
                add_code_word(emit_word(op, 0, 0, 0, sign12(imm_val)))
            except ValueError:
                ref = parse_symbol_token(target)
                if not ref:
                    raise
                add_code_word(emit_word(op, 0, 0, 0, 0))
                fixups.append({'type': 'jump', 'index': len(code) - 1, 'ref': ref})
        elif mnem == 'SVC':
            if len(args) == 1:
                imm_val = parse_int(args[0])
                add_code_word(emit_word(op, 0, 0, 0, imm_val & 0x0FFF))
            else:
                kv = {}
                for a in args:
                    if '=' in a:
                        k, v = a.split('=', 1)
                        kv[k.strip().upper()] = parse_int(v.strip())
                mod = kv.get('MOD', 0) & 0x0F
                fn = kv.get('FN', 0) & 0xFF
                imm_val = ((mod << 8) | fn) & 0x0FFF
                add_code_word(emit_word(op, 0, 0, 0, imm_val))
        else:
            raise ValueError(f"Unhandled mnemonic: {mnem}")

    for fx in fixups:
        ftype = fx['type']
        if ftype == 'imm12':
            kind, name = fx['ref']
            value = eval_symbol_ref(fx['ref'])
            is_local = name in labels
            if value is None or (for_object and is_local):
                relocs.append({'type': 'imm12', 'index': fx['index'], 'symbol': name, 'kind': kind, 'section': 'code'})
                continue
            code[fx['index']] = set_imm12(code[fx['index']], value)
        elif ftype == 'imm32':
            kind, name = fx['ref']
            value = eval_symbol_ref(fx['ref'])
            is_local = name in labels
            needs_reloc = value is None or (for_object and is_local)
            if not needs_reloc and fx['ref'][0] == 'symbol':
                sym_name = fx['ref'][1]
                if sym_name in labels and labels[sym_name][0] == SECTION_DATA:
                    needs_reloc = True
            if value is None or (for_object and is_local):
                relocs.append({'type': 'imm32', 'index': fx['index'], 'symbol': name, 'kind': kind, 'section': 'code'})
                continue
            code[fx['index']] = value & 0xFFFFFFFF
            if needs_reloc:
                if name in labels:
                    sec, offset = labels[name]
                    exports.setdefault(name, {'section': sec, 'offset': offset})
                relocs.append({'type': 'imm32', 'index': fx['index'], 'symbol': name, 'kind': kind, 'section': 'code'})
        elif ftype == 'jump':
            kind, name = fx['ref']
            value = eval_symbol_ref(fx['ref'])
            is_local = name in labels
            if value is None or (for_object and is_local):
                relocs.append({'type': 'jump', 'index': fx['index'], 'symbol': name, 'kind': kind, 'section': 'code'})
                continue
            code[fx['index']] = set_imm12(code[fx['index']], value)
        elif ftype == 'entry':
            value = resolve_symbol(fx['symbol'])
            if value is None:
                raise ValueError(f"Undefined entry symbol {fx['symbol']}")
            entry = value
            entry_symbol = fx['symbol']
        elif ftype == 'mem':
            kind, name = fx['ref']
            value = eval_symbol_ref(fx['ref'])
            is_local = name in labels
            if value is None or (for_object and is_local):
                relocs.append({'type': 'mem', 'index': fx['index'], 'symbol': name, 'kind': kind, 'section': 'code'})
                continue
            code[fx['index']] = set_imm12(code[fx['index']], value)
        elif ftype == 'data_word':
            kind, name = fx['ref']
            value = eval_symbol_ref(fx['ref'])
            is_local = name in labels
            if value is None or (for_object and is_local):
                relocs.append({'type': 'data_word', 'offset': fx['offset'], 'symbol': name, 'kind': kind, 'section': 'rodata'})
                continue
            rodata[fx['offset']:fx['offset'] + 4] = (value & 0xFFFFFFFF).to_bytes(4, 'little')
        elif ftype == 'data_half':
            kind, name = fx['ref']
            value = eval_symbol_ref(fx['ref'])
            is_local = name in labels
            if value is None or (for_object and is_local):
                relocs.append({'type': 'data_half', 'offset': fx['offset'], 'symbol': name, 'kind': kind, 'section': 'rodata'})
                continue
            rodata[fx['offset']:fx['offset'] + 2] = (value & 0xFFFF).to_bytes(2, 'little')
        elif ftype == 'data_byte':
            kind, name = fx['ref']
            value = eval_symbol_ref(fx['ref'])
            is_local = name in labels
            if value is None or (for_object and is_local):
                relocs.append({'type': 'data_byte', 'offset': fx['offset'], 'symbol': name, 'kind': kind, 'section': 'rodata'})
                continue
            rodata[fx['offset']] = value & 0xFF
        else:
            raise ValueError(f"Unknown fixup type {ftype}")

    symtab = _build_symbol_table(labels, externs, imports_decl)
    if not for_object:
        relocs = _resolve_unit_local_relocs(code, rodata, relocs, symtab)
    local_symbols = {
        name: {
            'section': info['section'],
            'offset': info['offset'],
            'abs_addr': info['abs_addr'],
        }
        for name, info in symtab.items()
    }

    for sym in externs:
        if sym in labels:
            sec, offset = labels[sym]
            exports[sym] = {'section': sec, 'offset': offset}
    if entry_symbol and entry_symbol in labels:
        sec, offset = labels[entry_symbol]
        exports.setdefault(entry_symbol, {'section': sec, 'offset': offset})
    return code, entry, sorted(externs), sorted(imports_decl), bytes(rodata), relocs, exports, entry_symbol, local_symbols


def write_hxe(code_words, entry, out_path, rodata=b"", bss_size=0, req_caps=0, flags=0):
    code_bytes = b"".join((w & 0xFFFFFFFF).to_bytes(4, "big") for w in code_words)
    crc_input = struct.pack(">IHHIIIII",
        MAGIC, VERSION, flags, entry, len(code_bytes),
        len(rodata), bss_size, req_caps)
    full_without_crc = crc_input + code_bytes + rodata
    crc = zlib.crc32(full_without_crc) & 0xFFFFFFFF
    header = struct.pack(">IHHIIIIII",
        MAGIC, VERSION, flags, entry, len(code_bytes),
        len(rodata), bss_size, req_caps, crc)
    with open(out_path, "wb") as f:
        f.write(header)
        f.write(code_bytes)
        f.write(rodata)


def write_hxo_object(out_path, *, code_words, rodata, entry, entry_symbol, externs, imports_decl, relocs, exports, local_symbols):
    obj = {
        "version": 1,
        "entry": entry,
        "entry_symbol": entry_symbol,
        "code": [int(w) & 0xFFFFFFFF for w in code_words],
        "rodata": (rodata or b"").hex(),
        "externs": list(externs),
        "imports": list(imports_decl),
        "relocs": relocs,
        "symbols": exports,
        "local_symbols": local_symbols,
    }
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2)
        f.write("\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input")
    ap.add_argument("-o", "--output", required=True)
    ap.add_argument("-v", "--verbose", action="store_true", help="print assembly statistics")
    ap.add_argument("--dump-bytes", action="store_true", help="emit code words as hex for debugging")
    ap.add_argument("--emit-hxo", action="store_true", help="emit HSX object (.hxo) instead of final .hxe")
    args = ap.parse_args()
    input_path = Path(args.input).resolve()
    with input_path.open("r", encoding="utf-8") as f:
        lines = f.readlines()
    code, entry, externs, imports_decl, rodata, relocs, exports, entry_symbol, local_symbols = assemble(
        lines,
        include_base=input_path.parent,
        for_object=args.emit_hxo,
    )
    if args.emit_hxo:
        write_hxo_object(
            args.output,
            code_words=code,
            rodata=rodata,
            entry=entry or 0,
            entry_symbol=entry_symbol,
            externs=externs,
            imports_decl=imports_decl,
            relocs=relocs,
            exports=exports,
            local_symbols=local_symbols,
        )
    else:
        write_hxe(code, entry or 0, args.output, rodata=rodata)
    if args.verbose:
        print(f"entry=0x{(entry or 0):08X} words={len(code)} bytes={len(code)*4} rodata={len(rodata)}")
        if imports_decl:
            print("imports: " + ", ".join(imports_decl))
        if externs:
            print("externs: " + ", ".join(externs))
    if args.dump_bytes:
        for idx, word in enumerate(code):
            print(f"{idx:04}: {word:08X}")
    print(f"Wrote {args.output} ({len(code)} words)")
if __name__ == "__main__":
    main()
