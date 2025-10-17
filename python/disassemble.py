#!/usr/bin/env python3
import argparse
import json
from pathlib import Path
import re
import struct
import sys
from typing import Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
MODULE_DIR = Path(__file__).resolve().parent
if str(MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(MODULE_DIR))

from disasm_util import OPCODE_NAMES, format_operands, instruction_size
from platforms.python.host_vm import HEADER, HEADER_FIELDS, HSX_MAGIC


def be32(data: bytes, offset: int) -> int:
    return struct.unpack_from('>I', data, offset)[0]


def load_hxe(path: Path):
    data = path.read_bytes()
    if len(data) < HEADER.size:
        raise ValueError('file too small')
    header_values = HEADER.unpack_from(data)
    header = dict(zip(HEADER_FIELDS, header_values))
    if header['magic'] != HSX_MAGIC:
        raise ValueError(f"bad magic 0x{header['magic']:08X}")
    code_start = HEADER.size
    code_end = code_start + header['code_len']
    ro_end = code_end + header['ro_len']
    return header, data[code_start:code_end], data[code_end:ro_end]


def decode_instruction(word: int) -> Dict[str, int]:
    op = (word >> 24) & 0xFF
    rd = (word >> 20) & 0x0F
    rs1 = (word >> 16) & 0x0F
    rs2 = (word >> 12) & 0x0F
    imm_raw = word & 0x0FFF
    imm = imm_raw
    if imm & 0x800:
        imm -= 0x1000
    return {'op': op, 'rd': rd, 'rs1': rs1, 'rs2': rs2, 'imm': imm, 'imm_raw': imm_raw}


def disassemble(code: bytes) -> List[Dict[str, object]]:
    listing = []
    offset = 0
    while offset < len(code):
        word = be32(code, offset)
        info = decode_instruction(word)
        opcode_name = OPCODE_NAMES.get(info['op'], f"0x{info['op']:02X}")
        next_word = None
        if opcode_name == 'LDI32' and offset + 8 <= len(code):
            next_word = be32(code, offset + 4)
        unsigned_ops = {0x21, 0x22, 0x23, 0x30, 0x7F}
        imm_effective = info['imm_raw'] if info['op'] in unsigned_ops else info['imm']
        inst = {
            'pc': offset,
            'word': word,
            'mnemonic': opcode_name,
            'rd': info['rd'],
            'rs1': info['rs1'],
            'rs2': info['rs2'],
            'imm': info['imm'],
            'imm_raw': info['imm_raw'],
            'imm_effective': imm_effective,
            'extended_imm': next_word,
        }
        inst['operands'] = format_operands(
            opcode_name,
            info['rd'],
            info['rs1'],
            info['rs2'],
            imm=imm_effective,
            imm_raw=info['imm_raw'],
            next_word=next_word,
            pc=offset,
        )
        listing.append(inst)
        offset += instruction_size(opcode_name)
    return listing


LABEL_RE = re.compile(r'([A-Za-z_][A-Za-z0-9_.$]*):')
INSTR_RE = re.compile(r'^([A-Za-z]+)')
DATA_RE = re.compile(r'^\.(byte|half|word)\s+(.*)$')


def parse_mvasm(path: Path) -> Dict[str, Dict[str, object]]:
    labels_text: Dict[int, List[str]] = {}
    labels_data: Dict[int, List[str]] = {}
    comments: Dict[int, str] = {}
    data_entries: List[Tuple[int, str, List[int]]] = []

    current_section = None
    pc = 0
    data_off = 0
    lines = path.read_text().splitlines()
    for raw in lines:
        line = raw.split(';', 1)[0].strip()
        if not line:
            continue
        if line.startswith('.text'):
            current_section = 'text'
            continue
        if line.startswith('.data'):
            current_section = 'data'
            continue
        label_match = LABEL_RE.match(line)
        if label_match:
            name = label_match.group(1)
            if current_section == 'text':
                labels_text.setdefault(pc, []).append(name)
            elif current_section == 'data':
                labels_data.setdefault(data_off, []).append(name)
            line = line[label_match.end():].strip()
            if not line:
                continue
        if current_section == 'text':
            instr_match = INSTR_RE.match(line)
            if not instr_match:
                continue
            mnemonic = instr_match.group(1).upper()
            pc += instruction_size(mnemonic)
        elif current_section == 'data':
            data_match = DATA_RE.match(line)
            if not data_match:
                continue
            directive, values_str = data_match.groups()
            values = [v.strip() for v in values_str.split(',') if v.strip()]
            ints: List[int] = []
            for v in values:
                base = 10
                if v.lower().startswith('0x'):
                    base = 16
                ints.append(int(v, base))
            data_entries.append((data_off, directive, ints))
            if directive == 'byte':
                data_off += len(ints)
            elif directive == 'half':
                data_off += 2 * len(ints)
            else:
                data_off += 4 * len(ints)
    return {
        'labels_text': labels_text,
        'labels_data': labels_data,
        'data_entries': data_entries,
    }


def annotate(listing, symbols):
    addr_to_label = {}
    for addr, names in symbols['labels_text'].items():
        for name in names:
            addr_to_label[addr] = name
    for inst in listing:
        imm = inst['imm']
        if imm >= 0 and imm in addr_to_label:
            inst['target'] = addr_to_label[imm]


def print_listing(header, listing, symbols, rodata):
    labels_text = symbols.get('labels_text', {})
    print(f"; entry=0x{header['entry']:08X} code_len={header['code_len']} ro_len={header['ro_len']}")
    for inst in listing:
        for name in labels_text.get(inst['pc'], []):
            print(f"{name}:")
        target = f" -> {inst['target']}" if 'target' in inst else ''
        operands = inst.get('operands') or ''
        spacing = f" {operands}" if operands else ''
        print(f"  0x{inst['pc']:04X}: 0x{inst['word']:08X} {inst['mnemonic']}{spacing}{target}")
    if rodata:
        print()
        print('; rodata')
        offset = 0
        labels_data = symbols.get('labels_data', {})
        for addr, name_list in labels_data.items():
            for name in name_list:
                print(f"{name}:")
        if symbols.get('data_entries'):
            for addr, directive, ints in symbols['data_entries']:
                line_values = ', '.join(f"0x{v:X}" for v in ints)
                print(f"  ; {directive} @0x{addr:04X}: {line_values}")
        else:
            print(rodata.hex())


def main() -> None:
    ap = argparse.ArgumentParser(description='HSX disassembler prototype')
    ap.add_argument('hxe', type=Path, help='.hxe file to disassemble')
    ap.add_argument('--mvasm', type=Path, help='optional .mvasm file for labels')
    ap.add_argument('-o', '--output', type=Path, help='write JSON output instead of text')
    args = ap.parse_args()

    header, code, rodata = load_hxe(args.hxe)
    listing = disassemble(code)
    symbols = {'labels_text': {}, 'labels_data': {}, 'data_entries': []}
    if args.mvasm and args.mvasm.exists():
        symbols = parse_mvasm(args.mvasm)
        annotate(listing, symbols)

    if args.output:
        args.output.write_text(json.dumps({'header': header, 'instructions': listing, 'symbols': symbols}, indent=2))
    else:
        print_listing(header, listing, symbols, rodata)


if __name__ == '__main__':
    main()
