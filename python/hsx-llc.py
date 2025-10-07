#!/usr/bin/env python3
"""
hsx-llc.py — LLVM IR (text) -> HSX .mvasm (MVP)
- Supports a tiny subset: i32 arithmetic, return, branches, basic calls stub.
- Goal: bootstrap pipeline for testing; extend incrementally.

Usage:
  python3 hsx-llc.py input.ll -o output.mvasm --trace
"""
import argparse, re, sys
from collections import defaultdict
from typing import List, Dict, Optional

R_RET = "R0"
ATTR_TOKENS = {"nsw", "nuw", "noundef", "dso_local", "local_unnamed_addr", "volatile"}

MOV_RE = re.compile(r"MOV\s+(R\d{1,2}),\s*(R\d{1,2})$", re.IGNORECASE)
LDI_RE = re.compile(r"LDI\s+(R\d{1,2}),\s*([-]?\d+)$", re.IGNORECASE)

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
    string_match = re.match(r'@([A-Za-z0-9_]+)\s*=\s*(?:private\s+)?(?:unnamed_addr\s+)?(?:internal\s+)?constant\s+\[(\d+)\s+x\s+i8\]\s+c"(.*)"(?:,\s*align\s*(\d+))?', line)
    if string_match:
        name, _, body, align = string_match.groups()
        data = parse_llvm_string_literal(body)
        return {"name": name, "kind": "bytes", "data": data, "align": int(align) if align else None}
    int_match = re.match(r'@([A-Za-z0-9_]+)\s*=\s*(?:dso_local\s+)?global\s+i(8|16|32)\s+([^,]+)(?:,\s*align\s*(\d+))?', line)
    if int_match:
        name, bits, value_str, align = int_match.groups()
        value_str = value_str.strip()
        value = 0 if value_str == 'zeroinitializer' else int(value_str)
        return {"name": name, "kind": "int", "bits": int(bits), "value": value, "align": int(align) if align else None}
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
            ldi_match = LDI_RE.match(stripped)
            if ldi_match:
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
                                result.append(f"LDI {dst_reg}, {imm}")
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
    # Map arguments (if any) to R1..R3 (MVP ignores types)
    arg_names = []
    for i, a in enumerate(fn["args"]):
        a = a.strip()
        if not a: 
            continue
        m = re.search(r'%([A-Za-z0-9_]+)$', a)
        if not m: continue
        arg_names.append("%"+m.group(1))
    for i, an in enumerate(arg_names[:len(ARG_REGS)]):
        vmap[an] = ARG_REGS[i]

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

    def alloc_vreg(name: str) -> str:
        if name not in vmap:
            next_idx = 4 + (len(vmap) % 10)
            vmap[name] = f"R{next_idx}"
        return vmap[name]

    global_symbols_set = set(global_symbols or [])
    global_cache: Dict[str, str] = {}

    def materialize_global(symbol: str) -> str:
        if symbol not in global_symbols_set:
            raise ISelError(f"Unknown global @{symbol}")
        key = f"@{symbol}"
        reg = global_cache.get(key)
        if reg is not None:
            return reg
        reg = alloc_vreg(key)
        asm.append(f"LDI32 {reg}, {symbol}")
        global_cache[key] = reg
        return reg

    def materialize(value: str, tmp: str) -> str:
        value = value.strip()
        if value.startswith('%'):
            if value not in vmap:
                raise ISelError(f"Unknown value {value}")
            return vmap[value]
        try:
            imm = int(value)
        except ValueError as exc:
            raise ISelError(f"Unsupported immediate {value}") from exc
        load_const(tmp, imm)
        return tmp

    def load_const(reg: str, value: int) -> None:
        if -2048 <= value <= 2047:
            asm.append(f"LDI {reg}, {value}")
        else:
            asm.append(f"LDI32 {reg}, {value & 0xFFFFFFFF}")

    def materialize_ptr(value: str, tmp: str) -> str:
        value = value.strip()
        if value in vmap:
            return vmap[value]
        if value.startswith('@'):
            return materialize_global(value[1:])
        m = re.match(r'inttoptr\s*\(i\d+\s+([-]?\d+)\s+to\s+ptr\)', value)
        if m:
            imm = int(m.group(1))
            load_const(tmp, imm)
            return tmp
        raise ISelError(f"Unsupported pointer operand {value}")

    def resolve_operand(value: str, tmp: str = "R12") -> str:
        value = value.strip()
        if value in float_alias:
            return float_alias[value]
        hmatch = re.match(r'0xH([0-9A-Fa-f]+)', value)
        if hmatch:
            bits = int(hmatch.group(1), 16)
            load_const(tmp, bits)
            return tmp
        if value.startswith('%'):
            if value not in vmap:
                raise ISelError(f"Unknown value {value}")
            return vmap[value]
        if value.startswith('@'):
            return materialize_global(value[1:])
        if value.startswith('inttoptr'):
            return materialize_ptr(value, tmp)
        if value in ('true', 'false'):
            return materialize('1' if value == 'true' else '0', tmp)
        if value in ('null', 'undef'):
            return materialize('0', tmp)
        return materialize(value, tmp)

    phi_comments = defaultdict(list)
    phi_moves = defaultdict(list)
    float_alias: Dict[str, str] = {}

    def clear_alias(name: str) -> None:
        float_alias.pop(name, None)

    for block in fn["blocks"]:
        remaining_ins = []
        for raw in block["ins"]:
            norm = normalize_ir_line(raw)
            m = re.match(r'(%[A-Za-z0-9_]+)\s*=\s*phi\s+i32\s+(.+)', norm)
            if m:
                dest, tail = m.groups()
                incoming = []
                for val, pred in re.findall(r'\[\s*([^,]+),\s*%([A-Za-z0-9_]+)\s*\]', tail):
                    incoming.append((pred, val.strip()))
                    phi_moves[(pred, block["label"])].append((dest, val.strip()))
                phi_comments[block["label"]].append(raw)
                alloc_vreg(dest)
            else:
                remaining_ins.append(raw)
        block["ins"] = remaining_ins

    def apply_phi_moves(pred_label: str, succ_label: str) -> None:
        moves = phi_moves.get((pred_label, succ_label))
        if not moves:
            return
        for dest, value in moves:
            clear_alias(dest)
            dest_reg = alloc_vreg(dest)
            src_reg = resolve_operand(value, dest_reg)
            if dest_reg != src_reg:
                asm.append(f"MOV {dest_reg}, {src_reg}")

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
            m = re.match(r'(%[A-Za-z0-9_]+)\s*=\s*alloca\s+([A-Za-z0-9_]+)', line)
            if m:
                slot, _ = m.groups()
                stack_slots.add(slot)
                alloc_vreg(slot)
                continue

            if line.startswith("ret "):
                if " i32 " in line and "%" in line:
                    m = re.search(r'ret\s+i32\s+(%[A-Za-z0-9_]+)', line)
                    if not m: raise ISelError("Unsupported ret: "+orig_line)
                    v = m.group(1)
                    r = vmap.get(v, None)
                    if r is None: raise ISelError(f"Unknown value {v} in {orig_line}")
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
                rd = alloc_vreg(dst)
                opmap = {"add":"ADD","sub":"SUB","mul":"MUL"}
                asm.append(f"{opmap[op]} {rd}, {ra}, {rb}")
                continue

            m = re.match(r'(%[A-Za-z0-9_]+)\s*=\s*f(add|sub|mul|div)\s+half\s+([^,]+),\s*([^,]+)', line)
            if m:
                dst, op, lhs, rhs = m.groups()
                clear_alias(dst)
                ra = resolve_operand(lhs, "R12")
                rb = resolve_operand(rhs, "R13")
                rd = alloc_vreg(dst)
                opmap = {"add": "FADD", "sub": "FSUB", "mul": "FMUL", "div": "FDIV"}
                asm.append(f"{opmap[op]} {rd}, {ra}, {rb}")
                continue

            m = re.match(r'(%[A-Za-z0-9_]+)\s*=\s*f(add|sub|mul|div)\s+float\s+([^,]+),\s*([^,]+)', line)
            if m:
                dst, op, lhs, rhs = m.groups()
                if lhs not in float_alias or rhs not in float_alias:
                    raise ISelError(f"Float operation requires half alias operands: {orig_line}")
                clear_alias(dst)
                ra = resolve_operand(lhs, "R12")
                rb = resolve_operand(rhs, "R13")
                rd = alloc_vreg(dst)
                opmap = {"add": "FADD", "sub": "FSUB", "mul": "FMUL", "div": "FDIV"}
                asm.append(f"{opmap[op]} {rd}, {ra}, {rb}")
                float_alias[dst] = rd
                vmap[dst] = rd
                continue

            m = re.match(r'(%[A-Za-z0-9_]+)\s*=\s*fpext\s+half\s+(%[A-Za-z0-9_]+)\s+to\s+float', line)
            if m:
                dst, src = m.groups()
                clear_alias(dst)
                src_reg = resolve_operand(src, "R12")
                vmap[dst] = src_reg
                float_alias[dst] = src_reg
                continue

            m = re.match(r'(%[A-Za-z0-9_]+)\s*=\s*fptrunc\s+float\s+(%[A-Za-z0-9_]+)\s+to\s+half', line)
            if m:
                dst, src = m.groups()
                clear_alias(dst)
                if src not in float_alias:
                    raise ISelError(f"fptrunc expects known float source: {orig_line}")
                rs = resolve_operand(src, "R12")
                rd = alloc_vreg(dst)
                if rd != rs:
                    asm.append(f"MOV {rd}, {rs}")
                continue

            m = re.match(r'(%[A-Za-z0-9_]+)\s*=\s*fptosi\s+half\s+(%[A-Za-z0-9_]+)\s+to\s+i32', line)
            if m:
                dst, src = m.groups()
                clear_alias(dst)
                rs = resolve_operand(src, "R12")
                rd = alloc_vreg(dst)
                asm.append(f"F2I {rd}, {rs}")
                continue

            m = re.match(r'(%[A-Za-z0-9_]+)\s*=\s*fptosi\s+float\s+(%[A-Za-z0-9_]+)\s+to\s+i32', line)
            if m:
                dst, src = m.groups()
                if src not in float_alias:
                    raise ISelError(f"fptosi float source not supported: {orig_line}")
                clear_alias(dst)
                rs = resolve_operand(src, "R12")
                rd = alloc_vreg(dst)
                asm.append(f"F2I {rd}, {rs}")
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
                    rd = alloc_vreg(dst)
                    if rd != R_RET:
                        asm.append(f"MOV {rd}, {R_RET}")
                continue

            m = re.match(r'(%[A-Za-z0-9_]+)\s*=\s*icmp\s+(eq|ne|sgt|slt)\s+i32\s+([^,]+),\s*([^,]+)', line)
            if m:
                dst, pred, lhs, rhs = m.groups()
                clear_alias(dst)
                ra = resolve_operand(lhs, "R12")
                rb = resolve_operand(rhs, "R13")
                tmp_reg = alloc_vreg(new_label("icmp_tmp"))
                rd = alloc_vreg(dst)
                asm.append(f"SUB {tmp_reg}, {ra}, {rb}")
                asm.append(f"CMP {tmp_reg}, R0")
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
                    end_label = new_label("icmp_end")
                    asm.append(f"JZ {end_label}")
                    mask_reg = alloc_vreg(new_label("icmp_mask"))
                    load_const(mask_reg, 0x80000000)
                    asm.append(f"AND {mask_reg}, {tmp_reg}, {mask_reg}")
                    asm.append(f"CMP {mask_reg}, R0")
                    if pred == "sgt":
                        asm.append(f"JNZ {end_label}")
                        asm.append(f"LDI {rd}, 1")
                    else:
                        asm.append(f"JZ {end_label}")
                        asm.append(f"LDI {rd}, 1")
                    asm.append(f"{end_label}:")
                continue

            m = re.match(r'(%[A-Za-z0-9_]+)\s*=\s*select\s+i1\s+(%[A-Za-z0-9_]+),\s+i32\s+([^,]+),\s+i32\s+([^,]+)', line)
            if m:
                dst, cond, vtrue, vfalse = m.groups()
                clear_alias(dst)
                rd = alloc_vreg(dst)
                cond_reg = resolve_operand(cond, "R12")
                true_label = new_label("select_true")
                end_label = new_label("select_end")
                asm.append(f"CMP {cond_reg}, R0")
                asm.append(f"JNZ {true_label}")
                false_reg = resolve_operand(vfalse, rd)
                if false_reg != rd:
                    asm.append(f"MOV {rd}, {false_reg}")
                asm.append(f"JMP {end_label}")
                asm.append(f"{true_label}:")
                true_reg = resolve_operand(vtrue, rd)
                if true_reg != rd:
                    asm.append(f"MOV {rd}, {true_reg}")
                asm.append(f"{end_label}:")
                continue

            m = re.match(r'(%[A-Za-z0-9_]+)\s*=\s*sext\s+i(8|16|32)\s+(%[A-Za-z0-9_]+)\s+to\s+i(32|64)', line)
            if m:
                dst, src_bits, src, dst_bits = m.groups()
                src_bits = int(src_bits)
                dst_bits = int(dst_bits)
                clear_alias(dst)
                rs = resolve_operand(src, "R12")
                if src_bits == 8 and dst_bits >= 32:
                    rd = alloc_vreg(dst)
                    mask_reg = alloc_vreg(new_label("sext8_mask"))
                    load_const(mask_reg, 0x80)
                    bias_reg = alloc_vreg(new_label("sext8_bias"))
                    load_const(bias_reg, 0x100)
                    asm.append(f"MOV {rd}, {rs}")
                    asm.append(f"AND {mask_reg}, {rs}, {mask_reg}")
                    asm.append(f"CMP {mask_reg}, R0")
                    pos_label = new_label("sext8_pos")
                    asm.append(f"JZ {pos_label}")
                    asm.append(f"SUB {rd}, {rd}, {bias_reg}")
                    asm.append(f"{pos_label}:")
                    continue
                if src_bits == 32 and dst_bits == 64:
                    rd = alloc_vreg(dst)
                    if rd != rs:
                        asm.append(f"MOV {rd}, {rs}")
                    continue
                raise ISelError(f"Unsupported sext: {orig_line}")

            m = re.match(r'(%[A-Za-z0-9_]+)\s*=\s*zext\s+i1\s+(%[A-Za-z0-9_]+)\s+to\s+i32', line)
            if m:
                dst, src = m.groups()
                clear_alias(dst)
                rd = alloc_vreg(dst)
                rs = vmap.get(src)
                if rs is None:
                    raise ISelError(f"Unknown zext source {src} in {orig_line}")
                if rd != rs:
                    asm.append(f"MOV {rd}, {rs}")
                continue

            m = re.match(r'(%[A-Za-z0-9_]+)\s*=\s*zext\s+i(8|16|32)\s+([^,]+)\s+to\s+i(32|64)', line)
            if m:
                dst, src_bits, src, dst_bits = m.groups()
                src_bits = int(src_bits)
                dst_bits = int(dst_bits)
                clear_alias(dst)
                rd = alloc_vreg(dst)
                rs = resolve_operand(src, "R12")
                if rd != rs:
                    asm.append(f"MOV {rd}, {rs}")
                mask = (1 << src_bits) - 1
                mask_reg = alloc_vreg(new_label("zext_mask"))
                load_const(mask_reg, mask)
                asm.append(f"AND {rd}, {rd}, {mask_reg}")
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
                r = vmap.get(cond, None)
                if r is None:
                    raise ISelError("Conditional branch expects reg cond: "+orig_line)
                else_label = new_label("br_else")
                asm.append(f"CMP {r}, R0")
                asm.append(f"JZ {else_label}")
                apply_phi_moves(b["label"], tlabel)
                asm.append(f"JMP {label_map.get(tlabel, tlabel)}")
                asm.append(f"{else_label}:")
                apply_phi_moves(b["label"], flabel)
                asm.append(f"JMP {label_map.get(flabel, flabel)}")
                continue

            m = re.match(r'(%[A-Za-z0-9_]+)\s*=\s*getelementptr\s+inbounds\s+\[([0-9]+)\s+x\s+i8\],\s*ptr\s+@([A-Za-z0-9_]+),\s*i64\s+0,\s*i64\s+([^,]+)', line)
            if m:
                dst, _, global_name, index = m.groups()
                clear_alias(dst)
                rd = alloc_vreg(dst)
                base_reg = materialize_global(global_name)
                asm.append(f"MOV {rd}, {base_reg}")
                index = index.strip()
                if index not in ('0', '0LL', '0l'):
                    idx_reg = resolve_operand(index, "R12")
                    asm.append(f"ADD {rd}, {rd}, {idx_reg}")
                continue

            m = re.match(r'(%[A-Za-z0-9_]+)\s*=\s*getelementptr\s+inbounds\s+i8,\s*ptr\s+@([A-Za-z0-9_]+),\s*i64\s+([^,]+)', line)
            if m:
                dst, global_name, index = m.groups()
                clear_alias(dst)
                rd = alloc_vreg(dst)
                base_reg = materialize_global(global_name)
                asm.append(f"MOV {rd}, {base_reg}")
                index = index.strip()
                if index not in ('0', '0LL', '0l'):
                    idx_reg = resolve_operand(index, "R12")
                    asm.append(f"ADD {rd}, {rd}, {idx_reg}")
                continue

            m = re.match(r'(%[A-Za-z0-9_]+)\s*=\s*load(?:\s+volatile)?\s+(i8|i16|i32|ptr|half),\s*(?:i\d+\*|ptr)\s+([^,]+)(?:,\s*align\s+\d+)?', line)
            if m:
                dst, dtype, ptr = m.groups()
                clear_alias(dst)
                rd = alloc_vreg(dst)
                if ptr in stack_slots:
                    src_reg = alloc_vreg(ptr)
                    if rd != src_reg:
                        asm.append(f"MOV {rd}, {src_reg}")
                else:
                    rp = materialize_ptr(ptr, "R14")
                    op_map = {"i8": "LDB", "i16": "LDH", "half": "LDH"}
                    instr = op_map.get(dtype, "LD")
                    asm.append(f"{instr} {rd}, [{rp}+0]")
                continue

            m = re.match(r'store(?:\s+volatile)?\s+(i8|i16|i32|ptr|half)\s+([^,]+),\s*(?:i\d+\*|ptr)\s+([^,]+)(?:,\s*align\s+\d+)?', line)
            if m:
                dtype, src, ptr = m.groups()
                if ptr in stack_slots:
                    dst_reg = alloc_vreg(ptr)
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
    return asm

def compile_ll_to_mvasm(ir_text: str, trace=False, enable_opt=True) -> str:
    ir = parse_ir(ir_text.splitlines())
    entry_label = next((fn['name'] for fn in ir['functions'] if fn['name'] == 'main'), None)
    defined_names = {fn['name'] for fn in ir['functions']}
    globals_list = ir.get('globals', [])
    global_names = {g['name'] for g in globals_list}
    imports = set()
    out = []
    for fn in ir['functions']:
        out += lower_function(fn, trace=trace, imports=imports, defined=defined_names, global_symbols=global_names)
    if out or globals_list:
        header = []
        if entry_label:
            header.append(f".entry {entry_label}")
        else:
            header.append('.entry')
        exports = sorted(defined_names)
        for name in exports:
            header.append(f".extern {name}")
        if imports:
            for name in sorted(imports):
                header.append(f".import {name}")
        header += render_globals(globals_list)
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
