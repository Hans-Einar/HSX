#!/usr/bin/env python3
import sys, re, struct, zlib, argparse
from pathlib import Path

MAGIC = 0x48535845  # 'HSXE'
VERSION = 0x0001

OPC = {
    "LDI":   0x01, "LD": 0x02, "ST": 0x03, "MOV": 0x04, "LDB": 0x06, "LDH": 0x07, "STB": 0x08, "STH": 0x09,
    "ADD": 0x10, "SUB": 0x11, "MUL": 0x12, "DIV": 0x13,
    "AND": 0x14, "OR": 0x15, "XOR": 0x16, "NOT": 0x17,
    "CMP": 0x20, "JMP": 0x21, "JZ": 0x22, "JNZ": 0x23, "CALL": 0x24, "RET": 0x25,
    "SVC": 0x30, "PUSH": 0x40, "POP": 0x41,
    "FADD": 0x50, "FSUB": 0x51, "FMUL": 0x52, "FDIV": 0x53, "I2F": 0x54, "F2I": 0x55,
    "LDI32": 0x60
}

REGISTER_RE = re.compile(r'R([0-9]|1[0-5])\b', re.IGNORECASE)
def regnum(tok):
    m = REGISTER_RE.fullmatch(tok)
    if not m: raise ValueError(f"Bad register '{tok}'")
    n = int(m.group(1))
    if n<0 or n>15: raise ValueError("Register out of range 0..15")
    return n

def parse_int(token):
    token = token.strip()
    if token.lower().startswith('0x'): return int(token, 16)
    if token.lower().startswith('0b'): return int(token, 2)
    if token.startswith("'") and token.endswith("'") and len(token)==3:
        return ord(token[1])
    return int(token, 10)

def sign12(val):
    if val < -2048 or val > 2047:
        raise ValueError(f"Immediate out of 12-bit signed range: {val}")
    return val & 0x0FFF

def emit_word(op, rd=0, rs1=0, rs2=0, imm=0):
    return ((op & 0xFF)<<24) | ((rd & 0x0F)<<20) | ((rs1 & 0x0F)<<16) | ((rs2 & 0x0F)<<12) | (imm & 0x0FFF)

def assemble(lines):
    code = []
    labels = {}
    fixups = []
    entry = 0
    pc = 0
    def add_word(w):
        nonlocal pc
        code.append(w & 0xFFFFFFFF)
        pc += 4

    for raw in lines:
        line = raw.split(';')[0].strip()
        if not line: continue
        if line.endswith(':'):
            lab = line[:-1].strip()
            if lab in labels: raise ValueError(f"Duplicate label: {lab}")
            labels[lab] = pc
            continue
        if line.lower().startswith('.entry'):
            parts = line.split()
            if len(parts)==2:
                try: entry = parse_int(parts[1])
                except: fixups.append(('entry', parts[1]))
            else:
                entry = pc
            continue
        if line.lower().startswith('.org'):
            parts = line.split()
            if len(parts)!=2: raise ValueError(".org expects one argument")
            newpc = parse_int(parts[1])
            while pc < newpc: add_word(0)
            continue

        tokens = re.split(r'[,\s]+', line.strip())
        mnem = tokens[0].upper()
        args = tokens[1:] if len(tokens)>1 else []
        if mnem not in OPC: raise ValueError(f"Unknown mnemonic: {mnem}")
        op = OPC[mnem]

        if mnem == 'RET':
            add_word(emit_word(op))
        elif mnem == 'MOV':
            rd, rs1 = regnum(args[0]), regnum(args[1]); add_word(emit_word(op, rd, rs1, 0, 0))
        elif mnem == 'PUSH':
            rs1 = regnum(args[0]); add_word(emit_word(op, 0, rs1, 0, 0))
        elif mnem == 'POP':
            rd = regnum(args[0]); add_word(emit_word(op, rd, 0, 0, 0))
        elif mnem in ('ADD','SUB','MUL','DIV','AND','OR','XOR','FADD','FSUB','FMUL','FDIV'):
            rd, rs1, rs2 = regnum(args[0]), regnum(args[1]), regnum(args[2])
            add_word(emit_word(op, rd, rs1, rs2, 0))
        elif mnem in ('NOT','I2F','F2I'):
            rd, rs1 = regnum(args[0]), regnum(args[1])
            add_word(emit_word(op, rd, rs1, 0, 0))
        elif mnem == 'LDI':
            rd = regnum(args[0])
            imm_tok = args[1]
            try:
                imm = parse_int(imm_tok); add_word(emit_word(op, rd, 0, 0, sign12(imm)))
            except ValueError:
                fixups.append(('imm12', len(code), rd, imm_tok)); add_word(0)
        elif mnem == 'LDI32':
            rd = regnum(args[0]); imm = parse_int(args[1])
            add_word(emit_word(op, rd, 0, 0, 0)); add_word(imm & 0xFFFFFFFF)
        elif mnem in ('LD','LDB','LDH'):
            rd = regnum(args[0])
            m = re.match(r'\[(R[0-9]|R1[0-5])\s*\+\s*([^\]]+)\]', args[1], re.IGNORECASE)
            if not m: raise ValueError("LD expects [Rs+imm]")
            rs1 = regnum(m.group(1)); imm = parse_int(m.group(2))
            add_word(emit_word(op, rd, rs1, 0, sign12(imm)))
        elif mnem in ('ST','STB','STH'):
            m = re.match(r'\[(R[0-9]|R1[0-5])\s*\+\s*([^\]]+)\]', args[0], re.IGNORECASE)
            if not m: raise ValueError("ST expects [Rs+imm]")
            rs1 = regnum(m.group(1)); imm = parse_int(m.group(2)); rs2 = regnum(args[1])
            add_word(emit_word(op, 0, rs1, rs2, sign12(imm)))
        elif mnem == 'CMP':
            rs1, rs2 = regnum(args[0]), regnum(args[1]); add_word(emit_word(op, 0, rs1, rs2, 0))
        elif mnem in ('JMP','JZ','JNZ','JLT','JGT','CALL'):
            target = args[0]
            try:
                imm = parse_int(target); add_word(emit_word(op, 0, 0, 0, sign12(imm)))
            except ValueError:
                add_word(emit_word(op, 0, 0, 0, 0))
                fixups.append(('jump', len(code)-1, mnem, target))
        elif mnem == 'SVC':
            if len(args)==1:
                imm = parse_int(args[0]); add_word(emit_word(op, 0, 0, 0, imm & 0x0FFF))
            else:
                kv = {}
                for a in args:
                    if '=' in a:
                        k,v = a.split('=',1)
                        kv[k.strip().upper()] = parse_int(v.strip())
                mod = kv.get('MOD',0) & 0x0F; fn = kv.get('FN',0) & 0xFF
                imm = ((mod<<8)|fn) & 0x0FFF
                add_word(emit_word(op, 0, 0, 0, imm))
        else:
            raise ValueError(f"Unhandled mnemonic: {mnem}")

    for fx in fixups:
        if fx[0]=='imm12':
            _, idx, rd, label = fx
            if label not in labels: raise ValueError(f"Unknown label {label}")
            code[idx] = emit_word(OPC['LDI'], rd, 0, 0, sign12(labels[label]))
        elif fx[0]=='jump':
            _, idx, mnem, label = fx
            if label not in labels: raise ValueError(f"Unknown label {label}")
            code[idx] = emit_word(OPC[mnem], 0, 0, 0, sign12(labels[label]))
        elif fx[0]=='entry':
            _, label = fx
            if label not in labels:
                raise ValueError(f"Unknown label {label}")
            entry = labels[label]

    return code, entry

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
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input")
    ap.add_argument("-o","--output", required=True)
    ap.add_argument("-v","--verbose", action="store_true", help="print assembly statistics")
    ap.add_argument("--dump-bytes", action="store_true", help="emit code words as hex for debugging")
    args = ap.parse_args()
    with open(args.input,"r",encoding="utf-8") as f:
        lines = f.readlines()
    code, entry = assemble(lines)
    write_hxe(code, entry or 0, args.output)
    if args.verbose:
        print(f"entry=0x{(entry or 0):08X} words={len(code)} bytes={len(code)*4}")
    if args.dump_bytes:
        for idx, word in enumerate(code):
            print(f"{idx:04}: {word:08X}")
    print(f"Wrote {args.output} ({len(code)} words)")

if __name__ == "__main__":
    main()
