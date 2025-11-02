#!/usr/bin/env python3
"""
hld.py -- HSX linker/packer
- Links one or more HSX object files (.hxo) into a final executable (.hxe)
- Falls back to pass-through when given a single .hxe input
Usage:
  python3 hld.py -o app.hxe input1.hxo [input2.hxo ...]
"""
import argparse
import json
import shutil
import struct
import sys
import zlib
from pathlib import Path
from typing import Any, Dict, List

try:
    from asm import RODATA_BASE, set_imm12
except ImportError:  # pragma: no cover - allow module import when run as package
    from .asm import RODATA_BASE, set_imm12

HSX_MAGIC = 0x48535845  # 'HSXE'
HSX_VERSION_V2 = 0x0002
FLAG_ALLOW_MULTIPLE = 0x0002
HEADER_V2 = struct.Struct(">IHHIIIIII32sII24s")
META_ENTRY_STRUCT = struct.Struct(">IIII")
METADATA_SECTION_VALUE = 1
METADATA_SECTION_COMMAND = 2
METADATA_SECTION_MAILBOX = 3
CRC_FIELD_OFFSET = 0x1C


def load_hxo(path: Path) -> Dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    module = {
        "path": path,
        "code": [int(word) & 0xFFFFFFFF for word in data.get("code", [])],
        "rodata": bytearray.fromhex(data.get("rodata", "")),
        "entry": data.get("entry", 0),
        "entry_symbol": data.get("entry_symbol"),
        "externs": data.get("externs", []),
        "imports": data.get("imports", []),
        "symbols": data.get("symbols", {}),
        "relocs": data.get("relocs", []),
        "local_symbols": data.get("local_symbols", {}),
        "metadata": data.get("metadata", {}),
    }
    return module


def compute_reloc_value(kind: str, symbol_entry: Dict) -> int:
    addr = symbol_entry["address"]
    if kind == "symbol" or kind is None:
        return addr
    if kind == "lo16":
        return addr & 0xFFFF
    if kind == "hi16":
        return (addr >> 16) & 0xFFFF
    if kind == "off16":
        return symbol_entry["offset"] & 0xFFFF
    raise ValueError(f"Unsupported relocation kind {kind}")


def _encode_app_name(candidate: str | None) -> bytes:
    if not candidate:
        return b"\x00" * 32
    clean = candidate.strip()
    if len(clean) > 31:
        clean = clean[:31]
    raw = clean.encode("ascii", errors="ignore")
    raw = raw[:31]
    return raw + b"\x00" * (32 - len(raw))


def write_hxe_v2(
    output: Path,
    *,
    code_words: List[int],
    entry: int,
    rodata: bytes,
    metadata: Dict[str, Any] | None = None,
    app_name: str | None = None,
    allow_multiple: bool = True,
    flags: int = 0,
    req_caps: int = 0,
) -> None:
    metadata = metadata or {}
    code_bytes = b"".join((word & 0xFFFFFFFF).to_bytes(4, "big") for word in code_words)
    rodata_bytes = bytes(rodata or b"")

    metadata_sections: List[tuple[int, bytes, int]] = []

    mailboxes = metadata.get("mailboxes") or []
    if mailboxes:
        payload = json.dumps({"version": 1, "mailboxes": mailboxes}, separators=(",", ":"), sort_keys=True).encode("utf-8")
        metadata_sections.append((METADATA_SECTION_MAILBOX, payload, len(mailboxes)))

    meta_count = len(metadata_sections)
    header_size = HEADER_V2.size
    table_size = meta_count * META_ENTRY_STRUCT.size

    code_offset = header_size
    ro_offset = code_offset + len(code_bytes)
    table_offset = ro_offset + len(rodata_bytes) if meta_count else 0
    sections_offset = table_offset + table_size if meta_count else ro_offset + len(rodata_bytes)
    payload_size = sum(len(section[1]) for section in metadata_sections)
    total_size = sections_offset + payload_size if meta_count else ro_offset + len(rodata_bytes)

    image = bytearray(total_size)
    cursor = header_size
    image[cursor:cursor + len(code_bytes)] = code_bytes
    cursor += len(code_bytes)
    image[cursor:cursor + len(rodata_bytes)] = rodata_bytes

    if meta_count:
        table_pos = table_offset
        section_cursor = sections_offset
        for section_type, payload_bytes, entry_count in metadata_sections:
            image[table_pos:table_pos + META_ENTRY_STRUCT.size] = META_ENTRY_STRUCT.pack(
                section_type,
                section_cursor,
                len(payload_bytes),
                entry_count,
            )
            table_pos += META_ENTRY_STRUCT.size
            image[section_cursor:section_cursor + len(payload_bytes)] = payload_bytes
            section_cursor += len(payload_bytes)

    flags_value = flags
    if allow_multiple:
        flags_value |= FLAG_ALLOW_MULTIPLE

    header = HEADER_V2.pack(
        HSX_MAGIC,
        HSX_VERSION_V2,
        flags_value,
        entry & 0xFFFFFFFF,
        len(code_bytes),
        len(rodata_bytes),
        0,  # bss size (not yet supported)
        req_caps & 0xFFFF,
        0,  # CRC placeholder
        _encode_app_name(app_name),
        table_offset if meta_count else 0,
        meta_count,
        b"\x00" * 24,
    )
    image[:header_size] = header

    crc_input = bytes(image[:CRC_FIELD_OFFSET]) + bytes(image[header_size:])
    crc = zlib.crc32(crc_input) & 0xFFFFFFFF
    struct.pack_into(">I", image, CRC_FIELD_OFFSET, crc)

    output.write_bytes(image)


def link_objects(object_paths: List[Path], output: Path, *, verbose: bool = False) -> Dict:
    modules = [load_hxo(Path(p)) for p in object_paths]
    if not modules:
        raise ValueError("No object files provided")

    code_offset = 0
    ro_offset = 0
    for mod in modules:
        mod["code_base"] = code_offset
        mod["ro_base"] = ro_offset
        code_offset += len(mod["code"]) * 4
        ro_offset += len(mod["rodata"])

    aggregated_mailboxes: List[Dict[str, Any]] = []
    seen_mailboxes: Dict[str, Path] = {}
    for mod in modules:
        metadata = mod.get("metadata") or {}
        mailboxes = metadata.get("mailboxes") or []
        if not isinstance(mailboxes, list):
            raise ValueError(f"Mailbox metadata for {mod['path']} must be a list")
        for entry in mailboxes:
            if not isinstance(entry, dict):
                raise ValueError(f"Mailbox metadata entries must be objects ({mod['path']})")
            target = entry.get("target") or entry.get("name")
            if not isinstance(target, str) or not target.strip():
                raise ValueError(f"Mailbox metadata entry missing target in {mod['path']}")
            target_norm = target.strip()
            if target_norm in seen_mailboxes:
                raise ValueError(
                    f"Duplicate mailbox target '{target_norm}' defined in {mod['path']} and {seen_mailboxes[target_norm]}"
                )
            seen_mailboxes[target_norm] = mod["path"]
            normalized = dict(entry)
            normalized["target"] = target_norm
            aggregated_mailboxes.append(normalized)
        mod["metadata"] = metadata

    if aggregated_mailboxes:
        aggregated_mailboxes.sort(key=lambda item: item["target"])
    metadata: Dict[str, Any] = {}
    if aggregated_mailboxes:
        metadata["mailboxes"] = aggregated_mailboxes

    symbol_table: Dict[str, Dict] = {}
    for mod in modules:
        for name, info in mod["symbols"].items():
            section = info.get("section")
            offset = int(info.get("offset", 0))
            if section == "text":
                address = mod["code_base"] + offset
            elif section == "data":
                address = RODATA_BASE + mod["ro_base"] + offset
            else:
                raise ValueError(f"Unknown symbol section '{section}' for {name}")
            if name in symbol_table:
                raise ValueError(f"Duplicate symbol '{name}' exported by {mod['path']}")
            symbol_table[name] = {
                "address": address,
                "offset": offset,
                "section": section,
                "module": mod,
            }

    # Ensure imports are satisfied
    for mod in modules:
        missing = [sym for sym in mod["imports"] if sym not in symbol_table]
        if missing:
            raise ValueError(f"Unresolved imports in {mod['path']}: {', '.join(sorted(missing))}")

    # Apply relocations
    for mod in modules:
        for reloc in mod["relocs"]:
            symbol = reloc["symbol"]
            sym_entry = symbol_table.get(symbol)
            if sym_entry is None:
                local_info = mod.get("local_symbols", {}).get(symbol)
                if local_info is None:
                    raise ValueError(f"Relocation references unknown symbol '{symbol}' in {mod['path']}")
                section = local_info.get("section")
                offset = int(local_info.get("offset", 0))
                if section == "text":
                    address = mod["code_base"] + offset
                elif section == "data":
                    address = RODATA_BASE + mod["ro_base"] + offset
                else:
                    raise ValueError(f"Unsupported local symbol section '{section}' for {symbol}")
                sym_entry = {
                    "address": address,
                    "offset": offset,
                    "section": section,
                    "module": mod,
                }
            value = compute_reloc_value(reloc.get("kind"), sym_entry)
            if reloc.get("section") == "code":
                idx = reloc["index"]
                if reloc["type"] in {"imm12", "jump", "mem"}:
                    patch_value = value
                    if reloc.get("pc_relative"):
                        instr_pc = mod["code_base"] + idx * 4
                        delta = value - instr_pc
                        if delta % 4 != 0:
                            raise ValueError(
                                f"PC-relative relocation requires word alignment: value=0x{value:X} pc=0x{instr_pc:X}"
                            )
                        patch_value = delta // 4
                    mod["code"][idx] = set_imm12(mod["code"][idx], patch_value)
                elif reloc["type"] == "imm32":
                    mod["code"][idx] = value & 0xFFFFFFFF
                else:
                    raise ValueError(f"Unsupported code relocation type {reloc['type']}")
            elif reloc.get("section") == "rodata":
                offset = reloc["offset"]
                if reloc["type"] == "data_word":
                    mod["rodata"][offset:offset + 4] = (value & 0xFFFFFFFF).to_bytes(4, "little")
                elif reloc["type"] == "data_half":
                    mod["rodata"][offset:offset + 2] = (value & 0xFFFF).to_bytes(2, "little")
                elif reloc["type"] == "data_byte":
                    mod["rodata"][offset] = value & 0xFF
                else:
                    raise ValueError(f"Unsupported data relocation type {reloc['type']}")
            else:
                raise ValueError(f"Unknown relocation section {reloc.get('section')}")

    # Choose entry point
    entry_address = None
    if "_start" in symbol_table:
        entry_address = symbol_table["_start"]["address"]
    else:
        for mod in modules:
            sym = mod.get("entry_symbol")
            if sym and sym in symbol_table:
                entry_address = symbol_table[sym]["address"]
                break
        if entry_address is None:
            primary = modules[0]
            entry_address = primary["code_base"] + int(primary.get("entry", 0))

    final_code: List[int] = []
    final_rodata = bytearray()
    for mod in modules:
        final_code.extend(mod["code"])
        final_rodata.extend(mod["rodata"])

    write_hxe_v2(
        Path(output),
        code_words=final_code,
        entry=entry_address or 0,
        rodata=bytes(final_rodata),
        metadata=metadata,
        app_name=Path(output).stem,
    )
    if verbose:
        print(f"Linked {len(modules)} modules -> {output}")
        print(f"  entry=0x{entry_address or 0:08X} words={len(final_code)} rodata={len(final_rodata)}")
        print(f"  exports: {', '.join(sorted(symbol_table.keys()))}")
    return {
        "entry": entry_address or 0,
        "words": len(final_code),
        "rodata": len(final_rodata),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("inputs", nargs="+")
    ap.add_argument("-o", "--output", required=True)
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()

    input_paths = [Path(p) for p in args.inputs]
    hxe_inputs = [p for p in input_paths if p.suffix == ".hxe"]
    hxo_inputs = [p for p in input_paths if p.suffix == ".hxo"]

    if hxo_inputs and hxe_inputs:
        print("Cannot mix .hxe and .hxo inputs", file=sys.stderr)
        sys.exit(2)

    if not hxo_inputs:
        if len(input_paths) == 1 and input_paths[0].suffix == ".hxe":
            shutil.copyfile(input_paths[0], args.output)
            if args.verbose:
                print(f"Copied {input_paths[0]} -> {args.output}")
            else:
                print(f"Copied {args.output}")
            return
        print("Provide .hxo objects or a single .hxe", file=sys.stderr)
        sys.exit(2)

    link_objects(hxo_inputs, Path(args.output), verbose=args.verbose)
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
