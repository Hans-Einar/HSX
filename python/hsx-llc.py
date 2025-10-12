#!/usr/bin/env python3
"""
hsx-llc.py — LLVM IR (text) -> HSX .mvasm (MVP)
- Supports a tiny subset: i32 arithmetic, return, branches, basic calls stub.
- Goal: bootstrap pipeline for testing; extend incrementally.

Usage:
  python3 hsx-llc.py input.ll -o output.mvasm --trace
"""
import argparse, re, sys
import struct
from collections import defaultdict
from typing import List, Dict, Optional, Tuple

R_RET = "R0"
ATTR_TOKENS = {"nsw", "nuw", "noundef", "dso_local", "local_unnamed_addr", "volatile"}

MOV_RE = re.compile(r"MOV\s+(R\d{1,2}),\s*(R\d{1,2})$", re.IGNORECASE)
IMM_TOKEN = r"(?:-?\d+|0x[0-9A-Fa-f]+)"
LDI_RE = re.compile(rf"LDI\s+(R\d{{1,2}}),\s*({IMM_TOKEN})$", re.IGNORECASE)
LDI32_RE = re.compile(rf"LDI32\s+(R\d{{1,2}}),\s*({IMM_TOKEN})$", re.IGNORECASE)

ARG_REGS = ["R1","R2","R3"]  # more via stack later

class ISelError(Exception):
    pass

def parse_llvm_string_literal(body: str) -> bytes:
    out = bytearray()
    i = 0
    while i < len(body):
        ch = body[i]
        if ch != '\\':
            out.append(ord(ch))
            i += 1
            continue
        if i + 2 >= len(body):
            raise ISelError(f"Bad string escape in c\"{body}\"")
        hx = body[i + 1:i + 3]
        out.append(int(hx, 16))
        i += 3
    return bytes(out)


def parse_global_definition(line: str):
    line = line.strip()
    string_match = re.match(r'@([A-Za-z0-9_.]+)\s*=\s*(?:[\w.]+\s+)*constant\s+\[(\d+)\s+x\s+i8\]\s+c"(.*)"(?:,\s*align\s*(\d+))?', line)
    if string_match:
        name, _, body, align = string_match.groups()
        data = parse_llvm_string_literal(body)
        return {"name": name, "kind": "bytes", "data": data, "align": int(align) if align else None}
    zero_array_match = re.match(
        r'@([A-Za-z0-9_.]+)\s*=\s*(?:[\w.]+\s+)*global\s+\[(\d+)\s+x\s+i(8|16|32)\]\s+zeroinitializer(?:,\s*align\s*(\d+))?',
        line,
    )
    if zero_array_match:
        name, count, bits, align = zero_array_match.groups()
        count = int(count)
        elem_size = int(bits) // 8
        data = bytes([0] * (count * elem_size))
        return {"name": name, "kind": "bytes", "data": data, "align": int(align) if align else None}
    int_match = re.match(r'@([A-Za-z0-9_.]+)\s*=\s*(?:[\w.]+\s+)*global\s+i(8|16|32)\s+([^,]+)(?:,\s*align\s*(\d+))?', line)
    if int_match:
        name, bits, value_str, align = int_match.groups()
        value_str = value_str.strip()
        value = 0 if value_str == 'zeroinitializer' else int(value_str)
        return {"name": name, "kind": "int", "bits": int(bits), "value": value, "align": int(align) if align else None}
    float_match = re.match(r'@([A-Za-z0-9_.]+)\s*=\s*(?:[\w.]+\s+)*global\s+float\s+([^,]+)(?:,\s*align\s*(\d+))?', line)
    if float_match:
        name, value_str, align = float_match.groups()
        value_str = value_str.strip()
        if value_str == 'zeroinitializer':
            bits = 0
        elif value_str.lower().startswith('0x'):
            bits = int(value_str, 16) & 0xFFFFFFFF
        else:
            bits = struct.unpack('<I', struct.pack('<f', float(value_str)))[0]
        return {"name": name, "kind": "float", "bits": 32, "value": bits, "align": int(align) if align else None}
    return None


def render_globals(globals_list):
    if not globals_list:
        return []
    lines = ['.data']
    for entry in globals_list:
        align = entry.get('align') or 0
        if align > 1:
            lines.append(f"    .align {align}")
        lines.append(f"{entry['name']}:")
        if entry['kind'] == 'bytes':
            data = entry['data']
            if data:
                for idx in range(0, len(data), 8):
                    chunk = data[idx:idx + 8]
                    lines.append('    .byte ' + ', '.join(f"0x{b:02X}" for b in chunk))
            else:
                lines.append('    .byte 0')
        elif entry['kind'] == 'int':
            bits = entry['bits']
            value = entry['value']
            if bits == 8:
                lines.append(f"    .byte {value}")
            elif bits == 16:
                lines.append(f"    .half {value}")
            else:
                lines.append(f"    .word {value}")
        elif entry['kind'] == 'float':
            value = entry['value'] & 0xFFFFFFFF
            lines.append(f"    .word 0x{value:08X}")
    return lines

def parse_ir(lines: List[str]) -> Dict:
    ir = {"functions": [], "globals": []}
    cur = None
    bb = None
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith(";"):
            continue
        if cur is None and line.startswith('@'):
            glob = parse_global_definition(line)
            if glob:
                ir["globals"].append(glob)
            continue
        if line.startswith("define "):
            m = re.match(r'define\s+(?:[\w.]+\s+)*(void|half|i\d+)\s+@([A-Za-z0-9_]+)\s*\(([^)]*)\)\s*(?:[^{}]*)\{', line)
            if not m:
                raise ISelError("Unsupported function signature: " + line)
            rettype, name, args = m.groups()
            if rettype.startswith('i'):
                retbits = int(rettype[1:])
            elif rettype == 'half':
                retbits = 16
            elif rettype == 'void':
                retbits = 0
            else:
                raise ISelError("Unsupported return type: " + rettype)
            cur = {"name": name, "rettype": rettype, "retbits": retbits, "args": args.split(",") if args.strip() else [], "blocks": []}
            ir["functions"].append(cur)
            bb = None
            continue
        if cur is None:
            continue
        label_match = re.match(r'([A-Za-z0-9_.]+):', line)
        if label_match and not line.startswith(";"):
            tail = line[label_match.end():].strip()
            if not tail or tail.startswith(';'):
                label = label_match.group(1)
                bb = {"label": label, "ins": []}
                cur["blocks"].append(bb)
                continue
        if line.endswith(":") and not line.startswith(";"):
            label = line[:-1]
            bb = {"label": label, "ins": []}
            cur["blocks"].append(bb)
            continue
        if line == "}":
            cur = None
            bb = None
            continue
        if bb is None:
            bb = {"label": "entry", "ins": []}
            cur["blocks"].append(bb)
        bb["ins"].append(line)
    return ir

def normalize_ir_line(line: str) -> str:
    line = re.sub(r',\s*!dbg\S*', '', line)
    line = re.sub(r',\s*!tbaa\s*!?\d*', '', line)
    line = re.sub(r'!\d+', '', line)
    for tok in ATTR_TOKENS:
        line = re.sub(rf'\b{tok}\b', '', line)
    line = re.sub(r'\s+', ' ', line).strip()
    return line


def is_instruction_line(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    if stripped.startswith(';'):
        return False
    if stripped.endswith(':'):
        return False
    if stripped.startswith('.'):  # directives such as .entry
        return False
    return True


def next_instruction_index(lines: List[str], start_idx: int) -> int:
    idx = start_idx
    while idx < len(lines):
        if is_instruction_line(lines[idx]):
            return idx
        idx += 1
    return -1


def build_label_positions(lines: List[str]) -> Dict[str, int]:
    positions: Dict[str, int] = {}
    for idx, line in enumerate(lines):
        stripped = line.strip()
        if not stripped or stripped.startswith(';'):
            continue
        if stripped.endswith(':') and not stripped.startswith('.'):
            positions[stripped[:-1]] = idx
    return positions


def register_used(
    lines: List[str],
    start_idx: int,
    reg: str,
    *,
    origin_idx: Optional[int] = None,
    labels: Optional[Dict[str, int]] = None,
) -> bool:
    pattern = re.compile(rf'\b{reg}\b', re.IGNORECASE)
    label_positions = labels if labels is not None else build_label_positions(lines)
    for idx in range(start_idx, len(lines)):
        stripped = lines[idx].strip()
        if not stripped or stripped.startswith(';'):
            continue
        if stripped.endswith(':') or stripped.startswith('.'):
            continue
        if origin_idx is not None:
            branch_match = re.match(r'(JMP|JZ|JNZ|JC|JNC|JA|JAE|JB|JBE)\s+([A-Za-z0-9_.$]+)', stripped, re.IGNORECASE)
            if branch_match:
                target = branch_match.group(2)
                target_idx = label_positions.get(target)
                if target_idx is None or target_idx <= origin_idx:
                    return True
                return True
        dest_match = re.match(r'[A-Z]+\s+(R\d{1,2})', stripped)
        if dest_match and dest_match.group(1).upper() == reg.upper():
            return False  # redefined before any use
        if pattern.search(stripped):
            return True
    return False


def is_return_mov(lines: List[str], mov_index: int) -> bool:
    stripped = lines[mov_index].strip()
    match = MOV_RE.match(stripped)
    if not match:
        return False
    dst = match.group(1).upper()
    if dst != R_RET:
        return False
    idx = mov_index + 1
    while idx < len(lines):
        nxt = lines[idx].strip()
        if not nxt or nxt.startswith(';'):
            idx += 1
            continue
        if nxt.endswith(':') or nxt.startswith('.'):
            idx += 1
            continue
        return nxt.upper().startswith('RET')
    return False


def combine_ldi_movs(lines: List[str]) -> List[str]:
    work = list(lines)
    while True:
        result: List[str] = []
        changed = False
        i = 0
        label_positions = build_label_positions(work)
        while i < len(work):
            line = work[i]
            stripped = line.strip()
            if not is_instruction_line(line):
                result.append(line)
                i += 1
                continue
            instr = None
            ldi_match = LDI_RE.match(stripped)
            if ldi_match:
                instr = "LDI"
            else:
                ldi_match = LDI32_RE.match(stripped)
                if ldi_match:
                    instr = "LDI32"
            if ldi_match and instr:
                src_reg = ldi_match.group(1).upper()
                imm = ldi_match.group(2)
                next_idx = next_instruction_index(work, i + 1)
                if next_idx != -1:
                    mov_match = MOV_RE.match(work[next_idx].strip())
                    if mov_match:
                        dst_reg = mov_match.group(1).upper()
                        mov_src = mov_match.group(2).upper()
                        if mov_src == src_reg and not is_return_mov(work, next_idx):
                            if not register_used(
                                work,
                                next_idx + 1,
                                src_reg,
                                origin_idx=i,
                                labels=label_positions,
                            ):
                                result.append(f"{instr} {dst_reg}, {imm}")
                                for filler in work[i + 1:next_idx]:
                                    result.append(filler)
                                i = next_idx + 1
                                changed = True
                                continue
            result.append(line)
            i += 1
        if not changed:
            return result
        work = result


def find_last_instruction(lines: List[str]):
    for line in reversed(lines):
        if not is_instruction_line(line):
            continue
        match = MOV_RE.match(line.strip())
        if match:
            return ('MOV', match.group(1).upper(), match.group(2).upper())
        return ('OTHER', None, None)
    return None


def pop_last_instruction(lines: List[str]) -> None:
    for idx in range(len(lines) - 1, -1, -1):
        if is_instruction_line(lines[idx]):
            lines.pop(idx)
            return


def eliminate_mov_chains(lines: List[str]) -> List[str]:
    label_positions = build_label_positions(lines)
    result: List[str] = []
    last_instr = None
    for idx, line in enumerate(lines):
        stripped = line.strip()
        if not is_instruction_line(line):
            result.append(line)
            continue
        mov_match = MOV_RE.match(stripped)
        if mov_match:
            dst = mov_match.group(1).upper()
            src = mov_match.group(2).upper()
            if dst == src and not is_return_mov(lines, idx):
                continue
            if dst == R_RET and is_return_mov(lines, idx):
                result.append(f"MOV {dst}, {src}")
                last_instr = ('MOV', dst, src, idx)
                continue
            if last_instr and last_instr[0] == 'MOV' and last_instr[1] == src:
                prev_src = last_instr[2]
                origin_idx = last_instr[3] if len(last_instr) > 3 and last_instr[3] is not None else idx
                if not register_used(
                    lines,
                    idx + 1,
                    src,
                    origin_idx=origin_idx,
                    labels=label_positions,
                ):
                    pop_last_instruction(result)
                    last_instr = find_last_instruction(result)
                    if last_instr and len(last_instr) == 3:
                        last_instr = last_instr + (None,)
                    src = prev_src
                    if dst == src:
                        continue
            result.append(f"MOV {dst}, {src}")
            last_instr = ('MOV', dst, src, idx)
            continue
        result.append(line)
        last_instr = ('OTHER', None, None, idx)
    return result


def optimize_movs(lines: List[str]) -> List[str]:
    if not lines:
        return lines
    stage1 = combine_ldi_movs(list(lines))
    stage2 = eliminate_mov_chains(stage1)
    return stage2

def lower_function(fn: Dict, trace=False, imports=None, defined=None, global_symbols=None) -> List[str]:
    asm: List[str] = []
    vmap: Dict[str,str] = {}
    if imports is None:
        imports = set()
    if defined is None:
        defined = set()


    asm.append(f"; -- function {fn['name']} --")

    use_counts: Dict[str, int] = defaultdict(int)
    for block in fn["blocks"]:
        for raw in block["ins"]:
            norm = normalize_ir_line(raw)
            phi_match = re.match(r'(%[A-Za-z0-9_]+)\s*=\s*phi', norm)
            if phi_match:
                incoming = re.findall(r'\[\s*([^,]+),\s*%([A-Za-z0-9_]+)\s*\]', norm)
                for val, _ in incoming:
                    val = val.strip()
                    if val.startswith('%'):
                        use_counts[val] += 1
                continue
            dest_match = re.match(r'(%[A-Za-z0-9_]+)\s*=', norm)
            dest = dest_match.group(1) if dest_match else None
            cleaned = re.sub(r'label\s+%[A-Za-z0-9_]+', '', norm)
            for tok in re.findall(r'%[A-Za-z0-9_]+', cleaned):
                if tok == dest:
                    continue
                use_counts[tok] += 1

    AVAILABLE_REGS = ["R4", "R5", "R6", "R8", "R9", "R10", "R11", "R15"]
    free_regs: List[str] = AVAILABLE_REGS.copy()
    value_types: Dict[str, str] = {}
    spilled_values: Dict[str, Tuple[str, str]] = {}
    spill_slots: Dict[str, str] = {}
    spill_data_lines: List[str] = []
    spill_slot_counter = 0
    pinned_values = set()
    pinned_registers: Dict[str, str] = {}
    first_stack_slot: Optional[str] = None
    reg_lru: List[str] = []
    spilled_float_alias = set()

    def mark_used(name: str) -> None:
        if name in reg_lru:
            reg_lru.remove(name)
        reg_lru.append(name)

    # Map arguments (if any) to R1..R3 (MVP ignores types)
    arg_regs = {}
    initial_float_alias = {}
    for i, a in enumerate(fn["args"]):
        arg = a.strip()
        if not arg:
            continue
        m = re.search(r'%([A-Za-z0-9_]+)$', arg)
        if not m:
            continue
        name = "%" + m.group(1)
        if i < len(ARG_REGS):
            reg = ARG_REGS[i]
            vmap[name] = reg
            arg_regs[name] = reg
            if arg.startswith('half '):
                value_types[name] = 'half'
            elif arg.startswith('float '):
                value_types[name] = 'float'
                initial_float_alias[name] = reg
            elif arg.startswith('i8 '):
                value_types[name] = 'i8'
            elif arg.startswith('i16 '):
                value_types[name] = 'i16'
            elif arg.startswith('ptr '):
                value_types[name] = 'ptr'
            else:
                value_types[name] = 'i32'
            mark_used(name)

    label_map = {}
    stack_slots = set()
    for block in fn["blocks"]:
        orig = block["label"]
        unique = f"{fn['name']}__{orig}"
        counter = 2
        while unique in label_map.values():
            unique = f"{fn['name']}__{orig}_{counter}"
            counter += 1
        label_map[orig] = unique

    is_first_block = True
    temp_label_counter = 0

    def new_label(tag: str) -> str:
        nonlocal temp_label_counter
        temp_label_counter += 1
        return f"{fn['name']}__{tag}_{temp_label_counter}"

    def canonical_type(type_name: Optional[str]) -> str:
        if not type_name:
            return 'i32'
        return type_name

    def deduce_value_type(token: Optional[str]) -> str:
        if not token:
            return 'i32'
        token = token.strip()
        if token.startswith('i1'):
            return 'i1'
        if token.startswith('i8'):
            return 'i8'
        if token.startswith('i16'):
            return 'i16'
        if token.startswith('half'):
            return 'half'
        if token.startswith('float'):
            return 'float'
        if token.startswith('ptr'):
            return 'ptr'
        return 'i32'

    def type_category(type_name: Optional[str]) -> str:
        tname = canonical_type(type_name)
        if tname in {'i1', 'i8'}:
            return 'byte'
        if tname in {'i16', 'half'}:
            return 'half'
        if tname in {'i32', 'float', 'ptr'}:
            return 'word'
        return 'word'

    def type_to_store_instr(type_name: Optional[str]) -> str:
        kind = type_category(type_name)
        return {'byte': 'STB', 'half': 'STH', 'word': 'ST'}[kind]

    def type_to_load_instr(type_name: Optional[str]) -> str:
        kind = type_category(type_name)
        return {'byte': 'LDB', 'half': 'LDH', 'word': 'LD'}[kind]

    def type_to_directive(type_name: Optional[str]) -> str:
        kind = type_category(type_name)
        return {'byte': '.byte', 'half': '.half', 'word': '.word'}[kind]

    def type_size(type_name: Optional[str]) -> int:
        tname = canonical_type(type_name)
        if tname in {'i1', 'i8'}:
            return 1
        if tname in {'i16', 'half'}:
            return 2
        if tname in {'i32', 'float', 'ptr'}:
            return 4
        if tname == 'i64':
            return 8
        return 1

    def add_free_reg(reg: str) -> None:
        if reg not in AVAILABLE_REGS or reg in free_regs:
            return
        idx = AVAILABLE_REGS.index(reg)
        for pos, existing in enumerate(free_regs):
            if AVAILABLE_REGS.index(existing) > idx:
                free_regs.insert(pos, reg)
                break
        else:
            free_regs.append(reg)

    def select_spill_candidate(exclude: Optional[set] = None) -> Optional[str]:
        blocked = set(exclude or ())
        for name in reg_lru:
            if name in blocked:
                continue
            if name in pinned_values:
                continue
            reg = vmap.get(name)
            if not reg or reg not in AVAILABLE_REGS:
                continue
            return name
        return None

    def allocate_spill_slot(name: str, val_type: str) -> str:
        nonlocal spill_slot_counter
        if name in spill_slots:
            return spill_slots[name]
        label = f"__spill_{fn['name']}_{spill_slot_counter}"
        spill_slot_counter += 1
        spill_slots[name] = label
        directive = type_to_directive(val_type)
        spill_data_lines.append(f"{label}:")
        spill_data_lines.append(f"    {directive} 0")
        return label

    def spill_value(name: str) -> None:
        reg = vmap.get(name)
        if not reg or reg not in AVAILABLE_REGS:
            return
        val_type = value_types.get(name, 'i32')
        slot_label = allocate_spill_slot(name, val_type)
        asm.append(f"LDI32 R14, {slot_label}")
        store_instr = type_to_store_instr(val_type)
        asm.append(f"{store_instr} [R14+0], {reg}")
        vmap.pop(name, None)
        add_free_reg(reg)
        if name in reg_lru:
            reg_lru.remove(name)
        if name in float_alias:
            spilled_float_alias.add(name)
        float_alias.pop(name, None)
        spilled_values[name] = (slot_label, val_type)

    def ensure_register_available(exclude: Optional[set] = None) -> None:
        blocked = set(exclude or ())
        while not free_regs:
            candidate = select_spill_candidate(blocked)
            if candidate is None:
                raise ISelError("register allocator exhausted; unable to spill further")
            if use_counts.get(candidate, 0) <= 0:
                release_reg(candidate)
                continue
            spill_value(candidate)

    def alloc_vreg(name: str, val_type: Optional[str] = None) -> str:
        val_type = canonical_type(val_type or value_types.get(name))
        value_types[name] = val_type
        if name in pinned_registers:
            reg = pinned_registers[name]
            if name not in vmap:
                vmap[name] = reg
            mark_used(name)
            return reg
        if name in vmap:
            mark_used(name)
            return vmap[name]
        if name in spilled_values:
            ensure_register_available({name})
            reg = free_regs.pop(0)
            vmap[name] = reg
            mark_used(name)
            slot_label, stored_type = spilled_values.pop(name)
            value_types[name] = stored_type
            asm.append(f"LDI32 R14, {slot_label}")
            load_instr = type_to_load_instr(stored_type)
            asm.append(f"{load_instr} {reg}, [R14+0]")
            if name in spilled_float_alias:
                float_alias[name] = reg
                spilled_float_alias.remove(name)
            return reg
        ensure_register_available({name})
        reg = free_regs.pop(0)
        vmap[name] = reg
        mark_used(name)
        if name in spilled_float_alias:
            float_alias[name] = reg
            spilled_float_alias.remove(name)
        return reg

    def ensure_value_in_reg(name: str) -> str:
        if name in vmap:
            mark_used(name)
            return vmap[name]
        if name in spilled_values:
            return alloc_vreg(name, value_types.get(name))
        raise ISelError(f"Unknown value {name}")

    global_symbols_set = set(global_symbols or [])
    def materialize_global(symbol: str, target: Optional[str] = None) -> str:
        if symbol not in global_symbols_set:
            raise ISelError(f"Unknown global @{symbol}")
        reg = target or "R12"
        asm.append(f"LDI32 {reg}, {symbol}")
        return reg

    def load_const(reg: str, value: int) -> None:
        if -2048 <= value <= 2047:
            asm.append(f"LDI {reg}, {value}")
        else:
            asm.append(f"LDI32 {reg}, {value & 0xFFFFFFFF}")

    def materialize(value: str, tmp: str) -> str:
        value = value.strip()
        if value.startswith('%'):
            reg = ensure_value_in_reg(value)
            consume_use(value)
            if reg != tmp:
                asm.append(f"MOV {tmp}, {reg}")
                return tmp
            return reg
        try:
            imm = int(value)
        except ValueError as exc:
            raise ISelError(f"Unsupported immediate {value}") from exc
        load_const(tmp, imm)
        return tmp

    def float_literal_to_half_bits(token: str) -> int:
        token = token.strip()
        if token.lower().startswith('0xh'):
            return int(token[3:], 16) & 0xFFFF
        if token.endswith('f') or token.endswith('F'):
            token = token[:-1]
        try:
            value = float(token)
        except ValueError as exc:
            raise ISelError(f"Unsupported float literal {token}") from exc
        try:
            packed = struct.pack('<e', value)
        except OverflowError as exc:
            raise ISelError(f"Float literal out of range for half: {token}") from exc
        return int.from_bytes(packed, 'little') & 0xFFFF


    def release_reg(name: str) -> None:
        reg = vmap.pop(name, None)
        if reg and reg in AVAILABLE_REGS:
            add_free_reg(reg)
        if name in reg_lru:
            reg_lru.remove(name)
        float_alias.pop(name, None)
        spilled_float_alias.discard(name)
        spilled_values.pop(name, None)

    def consume_use(name: str) -> None:
        if not name.startswith('%'):
            return
        if name not in use_counts:
            return
        remaining = use_counts[name] - 1
        if remaining <= 0:
            use_counts.pop(name, None)
            if name in pinned_values:
                return
            release_reg(name)
        else:
            use_counts[name] = remaining

    def maybe_release(name: str) -> None:
        if not name.startswith('%'):
            return
        if use_counts.get(name, 0) == 0 and name not in pinned_values:
            release_reg(name)


    def materialize_ptr(value: str, tmp: str) -> str:
        value = value.strip()
        if value in vmap or value in spilled_values:
            reg = ensure_value_in_reg(value)
            consume_use(value)
            return reg
        if value.startswith('@'):
            return materialize_global(value[1:], tmp)
        m = re.match(r'inttoptr\s*\(i\d+\s+([-]?\d+)\s+to\s+ptr\)', value)
        if m:
            imm = int(m.group(1))
            load_const(tmp, imm)
            return tmp
        raise ISelError(f"Unsupported pointer operand {value}")

    def resolve_operand(value: str, tmp: str = "R12") -> str:
        value = value.strip()
        if value in float_alias:
            reg = float_alias[value]
            if value not in vmap or vmap[value] != reg:
                reg = ensure_value_in_reg(value)
            consume_use(value)
            return reg
        hmatch = re.match(r'0xH([0-9A-Fa-f]+)', value)
        if hmatch:
            bits = int(hmatch.group(1), 16)
            load_const(tmp, bits)
            return tmp
        if value.startswith('%'):
            reg = ensure_value_in_reg(value)
            consume_use(value)
            return reg
        if value.startswith('@'):
            return materialize_global(value[1:], tmp)
        if value.startswith('inttoptr'):
            return materialize_ptr(value, tmp)
        if value in ('true', 'false'):
            return materialize('1' if value == 'true' else '0', tmp)
        if value in ('null', 'undef'):
            return materialize('0', tmp)
        return materialize(value, tmp)

    phi_comments = defaultdict(list)
    phi_moves = defaultdict(list)
    phi_types: Dict[str, str] = {}
    float_alias: Dict[str, str] = {}
    float_alias.update(initial_float_alias)

    def clear_alias(name: str) -> None:
        float_alias.pop(name, None)
        spilled_float_alias.discard(name)

    for block in fn["blocks"]:
        remaining_ins = []
        for raw in block["ins"]:
            norm = normalize_ir_line(raw)
            m = re.match(r'(%[A-Za-z0-9_]+)\s*=\s*phi\s+([A-Za-z0-9_]+)\s+(.+)', norm)
            if m:
                dest, phi_type, tail = m.groups()
                phi_type = phi_type.strip()
                incoming = []
                for val, pred in re.findall(r'\[\s*([^,]+),\s*%([A-Za-z0-9_]+)\s*\]', tail):
                    incoming.append((pred, val.strip()))
                    phi_moves[(pred, block["label"])].append((dest, val.strip()))
                phi_comments[block["label"]].append(raw)
                phi_types[dest] = phi_type
                value_types[dest] = phi_type
                alloc_vreg(dest, phi_type)
                maybe_release(dest)
            else:
                remaining_ins.append(raw)
        block["ins"] = remaining_ins

    def apply_phi_moves(pred_label: str, succ_label: str) -> None:
        moves = phi_moves.get((pred_label, succ_label))
        if not moves:
            return
        for dest, value in moves:
            clear_alias(dest)
            dest_type = phi_types.get(dest, value_types.get(dest, 'i32'))
            dest_reg = alloc_vreg(dest, dest_type)
            src_reg = resolve_operand(value, dest_reg)
            if dest_reg != src_reg:
                asm.append(f"MOV {dest_reg}, {src_reg}")
            maybe_release(dest)

    for b in fn["blocks"]:
        if is_first_block:
            asm.append(f"{fn['name']}:")
            is_first_block = False
        asm.append(label_map[b["label"]] + ":")
        if trace and phi_comments.get(b["label"]):
            for phi_line in phi_comments[b["label"]]:
                asm.append(f"; PHI: {phi_line}")
        for line in b["ins"]:
            orig_line = line
            line = normalize_ir_line(line)
            if trace: asm.append(f"; IR: {orig_line}")
            m = re.match(r'(%[A-Za-z0-9_]+)\s*=\s*alloca\b', line)
            if m:
                slot = m.group(1)
                stack_slots.add(slot)
                pinned_values.add(slot)
                value_types[slot] = 'ptr'
                if first_stack_slot is None:
                    first_stack_slot = slot
                    pinned_registers[slot] = 'R7'
                    if 'R7' in free_regs:
                        free_regs.remove('R7')
                    vmap[slot] = 'R7'
                    mark_used(slot)
                else:
                    alloc_vreg(slot, 'ptr')
                continue

            if line.startswith("ret "):
                if " i32 " in line and "%" in line:
                    m = re.search(r'ret\s+i32\s+(%[A-Za-z0-9_]+)', line)
                    if not m: raise ISelError("Unsupported ret: "+orig_line)
                    v = m.group(1)
                    r = ensure_value_in_reg(v)
                    consume_use(v)
                    if r != R_RET:
                        asm.append(f"MOV {R_RET}, {r}")
                    asm.append("RET")
                elif re.match(r'ret\s+i32\s+[-]?\d+', line):
                    imm = int(line.split()[-1])
                    asm.append(f"LDI {R_RET}, {imm}")
                    asm.append("RET")
                elif line.startswith("ret half "):
                    value = line.split(" ", 2)[2]
                    src_reg = resolve_operand(value, R_RET)
                    if src_reg != R_RET:
                        asm.append(f"MOV {R_RET}, {src_reg}")
                    asm.append("RET")
                elif re.match(r'ret\s+i16\s+(%[A-Za-z0-9_]+)', line):
                    value = line.split()[-1]
                    src_reg = resolve_operand(value, R_RET)
                    if src_reg != R_RET:
                        asm.append(f"MOV {R_RET}, {src_reg}")
                    asm.append("RET")
                elif re.match(r'ret\s+void', line):
                    asm.append("RET")
                else:
                    raise ISelError("Unsupported ret form: "+orig_line)
                continue

            m = re.match(r'(%[A-Za-z0-9_]+)\s*=\s*(add|sub|mul)(?:\s+[A-Za-z]+)*\s+i32\s+([^,]+),\s*([^,]+)', line)
            if m:
                dst, op, lhs, rhs = m.groups()
                clear_alias(dst)
                ra = materialize(lhs, "R12")
                rb = materialize(rhs, "R13")
                rd = alloc_vreg(dst, 'i32')
                opmap = {"add":"ADD","sub":"SUB","mul":"MUL"}
                asm.append(f"{opmap[op]} {rd}, {ra}, {rb}")
                maybe_release(dst)
                continue

            m = re.match(r'(%[A-Za-z0-9_]+)\s*=\s*f(add|sub|mul|div)\s+half\s+([^,]+),\s*([^,]+)', line)
            if m:
                dst, op, lhs, rhs = m.groups()
                clear_alias(dst)
                ra = resolve_operand(lhs, "R12")
                rb = resolve_operand(rhs, "R13")
                rd = alloc_vreg(dst, 'half')
                opmap = {"add": "FADD", "sub": "FSUB", "mul": "FMUL", "div": "FDIV"}
                asm.append(f"{opmap[op]} {rd}, {ra}, {rb}")
                float_alias[dst] = rd
                maybe_release(dst)
                continue

            m = re.match(r'(%[A-Za-z0-9_]+)\s*=\s*f(add|sub|mul|div)\s+float\s+([^,]+),\s*([^,]+)', line)
            if m:
                dst, op, lhs, rhs = m.groups()
                if lhs not in float_alias or rhs not in float_alias:
                    raise ISelError(f"Float operation requires half alias operands: {orig_line}")
                clear_alias(dst)
                ra = resolve_operand(lhs, "R12")
                rb = resolve_operand(rhs, "R13")
                rd = alloc_vreg(dst, 'float')
                opmap = {"add": "FADD", "sub": "FSUB", "mul": "FMUL", "div": "FDIV"}
                asm.append(f"{opmap[op]} {rd}, {ra}, {rb}")
                float_alias[dst] = rd
                maybe_release(dst)
                continue

            m = re.match(r'(%[A-Za-z0-9_]+)\s*=\s*fpext\s+half\s+(%[A-Za-z0-9_]+)\s+to\s+float', line)
            if m:
                dst, src = m.groups()
                clear_alias(dst)
                rd = alloc_vreg(dst, 'float')
                src_reg = resolve_operand(src, rd)
                if rd != src_reg:
                    asm.append(f"MOV {rd}, {src_reg}")
                float_alias[dst] = rd
                maybe_release(dst)
                continue

            m = re.match(r'(%[A-Za-z0-9_]+)\s*=\s*fptrunc\s+float\s+(%[A-Za-z0-9_]+)\s+to\s+half', line)
            if m:
                dst, src = m.groups()
                clear_alias(dst)
                if src not in float_alias:
                    raise ISelError(f"fptrunc expects known float source: {orig_line}")
                rs = resolve_operand(src, "R12")
                rd = alloc_vreg(dst, 'half')
                if rd != rs:
                    asm.append(f"MOV {rd}, {rs}")
                float_alias[dst] = rd
                maybe_release(dst)
                continue

            m = re.match(r'(%[A-Za-z0-9_]+)\s*=\s*fptosi\s+half\s+(%[A-Za-z0-9_]+)\s+to\s+i32', line)
            if m:
                dst, src = m.groups()
                clear_alias(dst)
                rs = resolve_operand(src, "R12")
                rd = alloc_vreg(dst, 'i32')
                asm.append(f"F2I {rd}, {rs}")
                maybe_release(dst)
                continue

            m = re.match(r'(%[A-Za-z0-9_]+)\s*=\s*fptosi\s+float\s+(%[A-Za-z0-9_]+)\s+to\s+i32', line)
            if m:
                dst, src = m.groups()
                if src not in float_alias:
                    raise ISelError(f"fptosi float source not supported: {orig_line}")
                clear_alias(dst)
                rs = resolve_operand(src, "R12")
                rd = alloc_vreg(dst, 'i32')
                asm.append(f"F2I {rd}, {rs}")
                maybe_release(dst)
                continue

            m = re.match(r'(%[A-Za-z0-9_]+)\s*=\s*call\s+([^@]*)@llvm\.convert\.to\.fp16\.f32\(([^)]*)\)', line)
            if m:
                dst, _, arg_str = m.groups()
                arg = arg_str.strip()
                parts = arg.split()
                if not parts or parts[0] != 'float':
                    raise ISelError(f"Unexpected operand for llvm.convert.to.fp16.f32: {orig_line}")
                value_token = parts[-1]
                clear_alias(dst)
                rd = alloc_vreg(dst, 'half')
                if value_token.startswith('%'):
                    if value_token not in float_alias:
                        raise ISelError(f"Float source for llvm.convert.to.fp16.f32 must be known: {orig_line}")
                    rs = resolve_operand(value_token, 'R12')
                    if rd != rs:
                        asm.append(f"MOV {rd}, {rs}")
                else:
                    bits = float_literal_to_half_bits(value_token)
                    load_const(rd, bits)
                maybe_release(dst)
                continue

            m = re.match(r'(%[A-Za-z0-9_]+)\s*=\s*call\s+([^@]*)@llvm\.convert\.from\.fp16\.f32\(([^)]*)\)', line)
            if m:
                dst, _, arg_str = m.groups()
                arg = arg_str.strip()
                parts = arg.split()
                if not parts or parts[0] not in {'i16', 'half'}:
                    raise ISelError(f"Unexpected operand for llvm.convert.from.fp16.f32: {orig_line}")
                value_token = parts[-1]
                clear_alias(dst)
                rs = resolve_operand(value_token, 'R12')
                rd = alloc_vreg(dst, 'float')
                if rd != rs:
                    asm.append(f"MOV {rd}, {rs}")
                float_alias[dst] = rd
                maybe_release(dst)
                continue

            m = re.match(r'(?:(%[A-Za-z0-9_]+)\s*=\s*)?call\s+([^@]+)@([A-Za-z0-9_]+)\s*\(([^)]*)\)', line)
            if m:
                dst, ret_type, func_name, args_str = m.groups()
                args = [arg.strip() for arg in args_str.split(',') if arg.strip()]
                if len(args) > len(ARG_REGS):
                    raise ISelError("Call with more than 3 args not supported: " + orig_line)
                for idx, arg in enumerate(args):
                    value_token = arg.split()[-1]
                    target_reg = ARG_REGS[idx]
                    src_reg = resolve_operand(value_token, target_reg)
                    if src_reg != target_reg:
                        asm.append(f"MOV {target_reg}, {src_reg}")
                if defined is not None and func_name not in defined:
                    imports.add(func_name)
                asm.append(f"CALL {func_name}")
                if dst:
                    clear_alias(dst)
                    ret_token = ret_type.strip().split()[0] if ret_type.strip() else ''
                    dst_type = deduce_value_type(ret_token)
                    value_types[dst] = dst_type
                    rd = alloc_vreg(dst, dst_type)
                    if rd != R_RET:
                        asm.append(f"MOV {rd}, {R_RET}")
                    if dst_type == 'float':
                        float_alias[dst] = rd
                    maybe_release(dst)
                continue

            m = re.match(r'(%[A-Za-z0-9_]+)\s*=\s*icmp\s+(eq|ne|sgt|slt|sge|sle)\s+i32\s+([^,]+),\s*([^,]+)', line)
            if m:
                dst, pred, lhs, rhs = m.groups()
                clear_alias(dst)
                ra = resolve_operand(lhs, "R12")
                rb = resolve_operand(rhs, "R13")
                tmp_name = new_label("icmp_tmp")
                tmp_reg = alloc_vreg(tmp_name, 'i32')
                rd = alloc_vreg(dst, 'i32')
                asm.append(f"SUB {tmp_reg}, {ra}, {rb}")
                zero_name = new_label("icmp_zero_const")
                zero_reg = alloc_vreg(zero_name, 'i32')
                load_const(zero_reg, 0)
                asm.append(f"CMP {tmp_reg}, {zero_reg}")
                asm.append(f"LDI {rd}, 0")
                if pred in ("eq", "ne"):
                    true_label = new_label(f"icmp_{pred}_true")
                    end_label = new_label("icmp_end")
                    branch = {"eq": "JZ", "ne": "JNZ"}[pred]
                    asm.append(f"{branch} {true_label}")
                    asm.append(f"JMP {end_label}")
                    asm.append(f"{true_label}:")
                    asm.append(f"LDI {rd}, 1")
                    asm.append(f"{end_label}:")
                else:
                    zero_label = new_label("icmp_zero")
                    end_label = new_label("icmp_end")
                    asm.append(f"JZ {zero_label}")
                    mask_name = new_label("icmp_mask")
                    mask_reg = alloc_vreg(mask_name, 'i32')
                    load_const(mask_reg, 0x80000000)
                    asm.append(f"AND {mask_reg}, {tmp_reg}, {mask_reg}")
                    asm.append(f"CMP {mask_reg}, {zero_reg}")
                    if pred in ("sgt", "sge"):
                        asm.append(f"JNZ {end_label}")
                        asm.append(f"LDI {rd}, 1")
                        asm.append(f"JMP {end_label}")
                    else:  # slt or sle
                        asm.append(f"JZ {end_label}")
                        asm.append(f"LDI {rd}, 1")
                        asm.append(f"JMP {end_label}")
                    asm.append(f"{zero_label}:")
                    if pred in ("sge", "sle"):
                        asm.append(f"LDI {rd}, 1")
                    asm.append(f"{end_label}:")
                    release_reg(mask_name)
                release_reg(zero_name)
                release_reg(tmp_name)
                maybe_release(dst)
                continue

            m = re.match(r'(%[A-Za-z0-9_]+)\s*=\s*select\s+i1\s+(%[A-Za-z0-9_]+),\s+i32\s+([^,]+),\s+i32\s+([^,]+)', line)
            if m:
                dst, cond, vtrue, vfalse = m.groups()
                clear_alias(dst)
                rd = alloc_vreg(dst, 'i32')
                cond_reg = resolve_operand(cond, "R12")
                true_label = new_label("select_true")
                end_label = new_label("select_end")
                zero_name = new_label("select_zero")
                zero_reg = alloc_vreg(zero_name, 'i32')
                load_const(zero_reg, 0)
                asm.append(f"CMP {cond_reg}, {zero_reg}")
                asm.append(f"JNZ {true_label}")
                release_reg(zero_name)
                false_reg = resolve_operand(vfalse, rd)
                if false_reg != rd:
                    asm.append(f"MOV {rd}, {false_reg}")
                asm.append(f"JMP {end_label}")
                asm.append(f"{true_label}:")
                true_reg = resolve_operand(vtrue, rd)
                if true_reg != rd:
                    asm.append(f"MOV {rd}, {true_reg}")
                asm.append(f"{end_label}:")
                maybe_release(dst)
                continue

            m = re.match(r'(%[A-Za-z0-9_]+)\s*=\s*sext\s+i(8|16|32)\s+([^,]+?)\s+to\s+i(32|64)', line)
            if m:
                dst, src_bits, src, dst_bits = m.groups()
                src_bits = int(src_bits)
                dst_bits = int(dst_bits)
                clear_alias(dst)
                rs = resolve_operand(src.strip(), "R12")
                if src_bits in (8, 16) and dst_bits >= 32:
                    rd = alloc_vreg(dst, 'i32')
                    if rd != rs:
                        asm.append(f"MOV {rd}, {rs}")
                    mask = (1 << src_bits) - 1
                    load_const('R13', mask)
                    asm.append(f"AND {rd}, {rd}, R13")
                    sign_bit = 1 << (src_bits - 1)
                    load_const('R13', sign_bit)
                    asm.append(f"AND R13, {rd}, R13")
                    nonneg_label = new_label("sext_nonneg")
                    load_const('R12', 0)
                    asm.append(f"CMP R13, R12")
                    asm.append(f"JZ {nonneg_label}")
                    extend = 1 << src_bits
                    load_const('R12', extend)
                    asm.append(f"SUB {rd}, {rd}, R12")
                    asm.append(f"{nonneg_label}:")
                    maybe_release(dst)
                    continue
                if src_bits == 32 and dst_bits == 64:
                    rd = alloc_vreg(dst, 'i32')
                    if rd != rs:
                        asm.append(f"MOV {rd}, {rs}")
                    maybe_release(dst)
                    continue
                raise ISelError(f"Unsupported sext: {orig_line}")

            m = re.match(r'(%[A-Za-z0-9_]+)\s*=\s*zext\s+i1\s+(%[A-Za-z0-9_]+)\s+to\s+i32', line)
            if m:
                dst, src = m.groups()
                clear_alias(dst)
                rd = alloc_vreg(dst, 'i32')
                rs = ensure_value_in_reg(src)
                consume_use(src)
                if rs is None:
                    raise ISelError(f"Unknown zext source {src} in {orig_line}")
                if rd != rs:
                    asm.append(f"MOV {rd}, {rs}")
                maybe_release(dst)
                continue

            m = re.match(r'(%[A-Za-z0-9_]+)\s*=\s*zext\s+i(8|16|32)\s+([^,]+)\s+to\s+i(32|64)', line)
            if m:
                dst, src_bits, src, dst_bits = m.groups()
                src_bits = int(src_bits)
                dst_bits = int(dst_bits)
                clear_alias(dst)
                rd = alloc_vreg(dst, 'i32')
                rs = resolve_operand(src, "R12")
                if rd != rs:
                    asm.append(f"MOV {rd}, {rs}")
                mask = (1 << src_bits) - 1
                mask_name = new_label("zext_mask")
                mask_reg = alloc_vreg(mask_name, 'i32')
                load_const(mask_reg, mask)
                asm.append(f"AND {rd}, {rd}, {mask_reg}")
                release_reg(mask_name)
                maybe_release(dst)
                continue

            m = re.match(r'(%[A-Za-z0-9_]+)\s*=\s*trunc\s+i(32|16)\s+([^,]+)\s+to\s+i(8|16)', line)
            if m:
                dst, src_bits, src, dst_bits = m.groups()
                src_bits = int(src_bits)
                dst_bits = int(dst_bits)
                if dst_bits >= src_bits:
                    raise ISelError(f"Unsupported trunc: {orig_line}")
                clear_alias(dst)
                rd = alloc_vreg(dst, f"i{dst_bits}")
                rs = resolve_operand(src, rd)
                if rd != rs:
                    asm.append(f"MOV {rd}, {rs}")
                mask = (1 << dst_bits) - 1
                load_const('R13', mask)
                asm.append(f"AND {rd}, {rd}, R13")
                maybe_release(dst)
                continue

            m = re.match(r'br\s+label\s+%([A-Za-z0-9_]+)', line)
            if m:
                target_label = m.group(1)
                apply_phi_moves(b["label"], target_label)
                asm.append(f"JMP {label_map.get(target_label, target_label)}")
                continue

            m = re.match(r'br\s+i1\s+(%[A-Za-z0-9_]+),\s*label\s+%([A-Za-z0-9_]+),\s*label\s+%([A-Za-z0-9_]+)', line)
            if m:
                cond, tlabel, flabel = m.groups()
                cond_reg = ensure_value_in_reg(cond)
                consume_use(cond)
                else_label = new_label("br_else")
                zero_name = new_label("br_zero")
                zero_reg = alloc_vreg(zero_name, 'i32')
                load_const(zero_reg, 0)
                asm.append(f"CMP {cond_reg}, {zero_reg}")
                asm.append(f"JZ {else_label}")
                release_reg(zero_name)
                apply_phi_moves(b["label"], tlabel)
                asm.append(f"JMP {label_map.get(tlabel, tlabel)}")
                asm.append(f"{else_label}:")
                apply_phi_moves(b["label"], flabel)
                asm.append(f"JMP {label_map.get(flabel, flabel)}")
                continue

            m = re.match(
                r'(%[A-Za-z0-9_]+)\s*=\s*getelementptr\s+inbounds\s+\[(\d+)\s+x\s+([A-Za-z0-9_.]+)\],\s*ptr\s+([@%][A-Za-z0-9_.]+),\s*i(?:32|64)\s+0,\s*i(?:32|64)\s+([^,]+)',
                line,
            )
            if m:
                dst, _, elem_type, base_name, index = m.groups()
                clear_alias(dst)
                rd = alloc_vreg(dst, 'ptr')
                if base_name.startswith('@'):
                    base_reg = materialize_global(base_name[1:], rd)
                else:
                    base_reg = materialize_ptr(base_name, rd)
                if rd != base_reg:
                    asm.append(f"MOV {rd}, {base_reg}")
                index = index.strip()
                if index not in ('0', '0LL', '0l'):
                    stride = type_size(elem_type)
                    idx_reg = resolve_operand(index, "R12")
                    if idx_reg != 'R12':
                        asm.append(f"MOV R12, {idx_reg}")
                        idx_reg = 'R12'
                    if stride != 1:
                        load_const('R13', stride)
                        asm.append(f"MUL {idx_reg}, {idx_reg}, R13")
                    asm.append(f"ADD {rd}, {rd}, {idx_reg}")
                maybe_release(dst)
                continue

            m = re.match(r'(%[A-Za-z0-9_]+)\s*=\s*getelementptr\s+inbounds\s+(i8|i16|i32|i64|half|float|ptr),\s*ptr\s+([@%][A-Za-z0-9_.]+),\s*i(?:32|64)\s+([^,]+)', line)
            if m:
                dst, elem_type, base_name, index = m.groups()
                clear_alias(dst)
                rd = alloc_vreg(dst, 'ptr')
                if base_name.startswith('@'):
                    base_reg = materialize_global(base_name[1:], rd)
                else:
                    base_reg = materialize_ptr(base_name, rd)
                if rd != base_reg:
                    asm.append(f"MOV {rd}, {base_reg}")
                index = index.strip()
                if index not in ('0', '0LL', '0l'):
                    stride = type_size(elem_type)
                    idx_reg = resolve_operand(index, 'R12')
                    if idx_reg != 'R12':
                        asm.append(f"MOV R12, {idx_reg}")
                        idx_reg = 'R12'
                    if stride != 1:
                        load_const('R13', stride)
                        asm.append(f"MUL {idx_reg}, {idx_reg}, R13")
                    asm.append(f"ADD {rd}, {rd}, {idx_reg}")
                maybe_release(dst)
                continue

            m = re.match(r'(%[A-Za-z0-9_]+)\s*=\s*getelementptr\s+inbounds\s+%[A-Za-z0-9_.]+,\s*ptr\s+([@%][A-Za-z0-9_.]+),\s*(.+)', line)
            if m:
                dst, base_name, _ = m.groups()
                clear_alias(dst)
                rd = alloc_vreg(dst, 'ptr')
                if base_name.startswith('@'):
                    base_reg = materialize_global(base_name[1:], rd)
                else:
                    base_reg = materialize_ptr(base_name, rd)
                if rd != base_reg:
                    asm.append(f"MOV {rd}, {base_reg}")
                maybe_release(dst)
                continue

            m = re.match(r'(%[A-Za-z0-9_]+)\s*=\s*load(?:\s+volatile)?\s+(i8|i16|i32|ptr|half|float),\s*(?:i\d+\*|ptr)\s+([^,]+)(?:,\s*align\s+\d+)?', line)
            if m:
                dst, dtype, ptr = m.groups()
                clear_alias(dst)
                dst_type = deduce_value_type(dtype)
                value_types[dst] = dst_type
                rd = alloc_vreg(dst, dst_type)
                if ptr in stack_slots:
                    src_reg = alloc_vreg(ptr, 'ptr')
                    consume_use(ptr)
                    if rd != src_reg:
                        asm.append(f"MOV {rd}, {src_reg}")
                else:
                    rp = materialize_ptr(ptr, "R14")
                    op_map = {"i8": "LDB", "i16": "LDH", "half": "LDH"}
                    instr = op_map.get(dtype, "LD")
                    asm.append(f"{instr} {rd}, [{rp}+0]")
                if dst_type == 'float':
                    float_alias[dst] = rd
                maybe_release(dst)
                continue

            m = re.match(r'store(?:\s+volatile)?\s+(i8|i16|i32|ptr|half|float)\s+([^,]+),\s*(?:i\d+\*|ptr)\s+([^,]+)(?:,\s*align\s+\d+)?', line)
            if m:
                dtype, src, ptr = m.groups()
                if ptr in stack_slots:
                    dst_reg = alloc_vreg(ptr, 'ptr')
                    consume_use(ptr)
                    if dtype == 'ptr':
                        rs = materialize_ptr(src, "R12")
                    else:
                        rs = resolve_operand(src, "R12")
                    if dst_reg != rs:
                        asm.append(f"MOV {dst_reg}, {rs}")
                else:
                    rp = materialize_ptr(ptr, "R14")
                    if dtype == 'ptr':
                        rs = materialize_ptr(src, "R12")
                    else:
                        rs = resolve_operand(src, "R12")
                    op_map = {"i8": "STB", "i16": "STH", "half": "STH"}
                    instr = op_map.get(dtype, "ST")
                    asm.append(f"{instr} [{rp}+0], {rs}")
                continue

            raise ISelError("Unsupported IR line: "+orig_line)
    return asm, spill_data_lines

def compile_ll_to_mvasm(ir_text: str, trace=False, enable_opt=True) -> str:
    ir = parse_ir(ir_text.splitlines())
    entry_label = next((fn['name'] for fn in ir['functions'] if fn['name'] == 'main'), None)
    defined_names = {fn['name'] for fn in ir['functions']}
    globals_list = ir.get('globals', [])
    global_names = {g['name'] for g in globals_list}
    imports = set()
    out: List[str] = []
    spill_data_all: List[str] = []
    for fn in ir['functions']:
        fn_asm, fn_spill_data = lower_function(fn, trace=trace, imports=imports, defined=defined_names, global_symbols=global_names)
        out += fn_asm
        if fn_spill_data:
            spill_data_all.extend(fn_spill_data)
    data_section = render_globals(globals_list)
    if spill_data_all:
        if data_section:
            data_section.extend(spill_data_all)
        else:
            data_section = ['.data'] + spill_data_all
    if out or data_section:
        header = []
        if entry_label:
            header.append(f".entry {entry_label}")
        else:
            header.append('.entry')
        exports = sorted(defined_names)
        for name in exports:
            header.append(f".export {name}")
        if imports:
            for name in sorted(imports):
                header.append(f".import {name}")
        if data_section:
            header += data_section
        header.append('.text')
        out = header + out
        if enable_opt and not trace:
            out = optimize_movs(out)
    return "\n".join(out) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input")
    ap.add_argument("-o","--output", required=True)
    ap.add_argument("--trace", action="store_true")
    ap.add_argument("--no-opt", action="store_true", help="disable MOV optimization pass")
    args = ap.parse_args()
    txt = open(args.input,"r",encoding="utf-8").read()
    asm = compile_ll_to_mvasm(txt, trace=args.trace, enable_opt=not args.no_opt)
    with open(args.output,"w",encoding="utf-8") as f:
        f.write(asm)
    print(f"Wrote {args.output}")
if __name__ == "__main__":
    main()
