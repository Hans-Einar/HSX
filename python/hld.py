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
from typing import Any, Dict, List, Optional, Tuple

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
VALUE_ENTRY_STRUCT = struct.Struct(">BBBBHHHHHHHH")
CMD_ENTRY_STRUCT = struct.Struct(">BBBBIHHI")
_F16_STRUCT = struct.Struct("<e")


def _float_to_f16(value: float) -> int:
    try:
        packed = _F16_STRUCT.pack(float(value))
    except OverflowError:
        return 0x7C00 if value > 0 else 0xFC00
    return int.from_bytes(packed, "little")


def _normalise_uint8(name: str, value: Any) -> int:
    try:
        num = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if not (0 <= num <= 0xFF):
        raise ValueError(f"{name} must be within 0..255")
    return num


def _normalise_uint16(name: str, value: Any) -> int:
    try:
        num = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if not (0 <= num <= 0xFFFF):
        raise ValueError(f"{name} must be within 0..65535")
    return num


def _normalise_uint32(name: str, value: Any) -> int:
    try:
        num = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if not (0 <= num <= 0xFFFFFFFF):
        raise ValueError(f"{name} must be within 0..4294967295")
    return num & 0xFFFFFFFF


def _intern_string(strings: Dict[str, int], table: bytearray, base_offset: int, text: Optional[str]) -> int:
    if text is None:
        return 0
    if not isinstance(text, str):
        text = str(text)
    if text == "":
        # Preserve empty string explicitly by allocating a null terminator.
        key = ""
    else:
        key = text
    cached = strings.get(key)
    if cached is not None:
        return cached
    offset = base_offset + len(table)
    table.extend(text.encode("utf-8"))
    table.append(0)
    strings[key] = offset
    return offset


def _encode_value_metadata(entries: List[Dict[str, Any]]) -> tuple[bytes, int]:
    if not entries:
        return b"", 0
    normalised: List[Dict[str, Any]] = []
    seen: set[tuple[int, int]] = set()
    for raw in entries:
        group_id = _normalise_uint8("value metadata group_id", raw.get("group", raw.get("group_id")))
        value_id = _normalise_uint8("value metadata value_id", raw.get("value", raw.get("value_id")))
        key = (group_id, value_id)
        if key in seen:
            raise ValueError(f"duplicate value metadata entry for ({group_id},{value_id})")
        seen.add(key)
        flags = _normalise_uint8("value metadata flags", raw.get("flags", 0))
        auth_level = _normalise_uint8("value metadata auth_level", raw.get("auth", raw.get("auth_level", 0)))
        init_raw = raw.get("init_raw")
        if init_raw is None:
            init_value = raw.get("init", raw.get("init_value", 0.0))
            init_raw = _float_to_f16(init_value)
        epsilon_raw = raw.get("epsilon_raw")
        if epsilon_raw is None:
            epsilon_value = raw.get("epsilon", 0.0)
            epsilon_raw = _float_to_f16(epsilon_value)
        min_raw = raw.get("min_raw")
        if min_raw is None:
            min_value = raw.get("min", 0.0)
            min_raw = _float_to_f16(min_value)
        max_raw = raw.get("max_raw")
        if max_raw is None:
            max_value = raw.get("max", 0.0)
            max_raw = _float_to_f16(max_value)
        persist_key = _normalise_uint16("value metadata persist_key", raw.get("persist_key", 0))
        reserved = _normalise_uint16("value metadata reserved", raw.get("reserved", 0))
        group_name = raw.get("group_name", raw.get("groupName"))
        normalised.append(
            {
                "group_id": group_id,
                "value_id": value_id,
                "flags": flags,
                "auth_level": auth_level,
                "init_raw": init_raw & 0xFFFF,
                "group_name": group_name,
                "name": raw.get("name"),
                "unit": raw.get("unit"),
                "epsilon_raw": epsilon_raw & 0xFFFF,
                "min_raw": min_raw & 0xFFFF,
                "max_raw": max_raw & 0xFFFF,
                "persist_key": persist_key,
                "reserved": reserved,
            }
        )
    normalised.sort(key=lambda item: (item["group_id"], item["value_id"]))
    entry_size = VALUE_ENTRY_STRUCT.size
    entries_blob = bytearray(len(normalised) * entry_size)
    string_table = bytearray()
    string_offsets: Dict[str, int] = {}
    for index, entry in enumerate(normalised):
        base_offset = len(normalised) * entry_size
        name_offset = _intern_string(string_offsets, string_table, base_offset, entry.get("name"))
        unit_offset = _intern_string(string_offsets, string_table, base_offset, entry.get("unit"))
        group_name_offset = _intern_string(string_offsets, string_table, base_offset, entry.get("group_name"))
        VALUE_ENTRY_STRUCT.pack_into(
            entries_blob,
            index * entry_size,
            entry["group_id"],
            entry["value_id"],
            entry["flags"],
            entry["auth_level"],
            entry["init_raw"],
            name_offset,
            unit_offset,
            entry["epsilon_raw"],
            entry["min_raw"],
            entry["max_raw"],
            entry["persist_key"],
            group_name_offset,
        )
    return bytes(entries_blob + string_table), len(normalised)


def _encode_command_metadata(entries: List[Dict[str, Any]]) -> tuple[bytes, int]:
    if not entries:
        return b"", 0
    normalised: List[Dict[str, Any]] = []
    seen: set[tuple[int, int]] = set()
    for raw in entries:
        group_id = _normalise_uint8("command metadata group_id", raw.get("group", raw.get("group_id")))
        cmd_id = _normalise_uint8("command metadata cmd_id", raw.get("cmd", raw.get("cmd_id")))
        key = (group_id, cmd_id)
        if key in seen:
            raise ValueError(f"duplicate command metadata entry for ({group_id},{cmd_id})")
        seen.add(key)
        flags = _normalise_uint8("command metadata flags", raw.get("flags", 0))
        auth_level = _normalise_uint8("command metadata auth_level", raw.get("auth", raw.get("auth_level", 0)))
        handler_offset = _normalise_uint32("command metadata handler_offset", raw.get("handler", raw.get("handler_offset", 0)))
        reserved = _normalise_uint32("command metadata reserved", raw.get("reserved", 0))
        group_name = raw.get("group_name", raw.get("groupName"))
        normalised.append(
            {
                "group_id": group_id,
                "cmd_id": cmd_id,
                "flags": flags,
                "auth_level": auth_level,
                "handler_offset": handler_offset & 0xFFFFFFFF,
                "group_name": group_name,
                "name": raw.get("name"),
                "help": raw.get("help"),
                "reserved": reserved,
            }
        )
    normalised.sort(key=lambda item: (item["group_id"], item["cmd_id"]))
    entry_size = CMD_ENTRY_STRUCT.size
    entries_blob = bytearray(len(normalised) * entry_size)
    string_table = bytearray()
    string_offsets: Dict[str, int] = {}
    for index, entry in enumerate(normalised):
        base_offset = len(normalised) * entry_size
        name_offset = _intern_string(string_offsets, string_table, base_offset, entry.get("name"))
        help_offset = _intern_string(string_offsets, string_table, base_offset, entry.get("help"))
        group_name_offset = _intern_string(string_offsets, string_table, base_offset, entry.get("group_name"))
        combined_reserved = ((entry.get("reserved", 0) & 0xFFFF) << 16) | (group_name_offset & 0xFFFF)
        CMD_ENTRY_STRUCT.pack_into(
            entries_blob,
            index * entry_size,
            entry["group_id"],
            entry["cmd_id"],
            entry["flags"],
            entry["auth_level"],
            entry["handler_offset"],
            name_offset,
            help_offset,
            combined_reserved,
        )
    return bytes(entries_blob + string_table), len(normalised)


def _resolve_command_handler_offsets(
    commands: List[Dict[str, Any]],
    modules: List[Dict[str, Any]],
    symbol_table: Dict[str, Dict[str, Any]],
) -> None:
    for entry in commands:
        origin = entry.pop("_module", None)
        handler_offset_value = entry.get("handler_offset")
        handler_value = entry.pop("handler", None)
        if handler_offset_value is not None and handler_value is None:
            entry["handler_offset"] = int(handler_offset_value) & 0xFFFFFFFF
            continue
        if handler_value is None:
            if handler_offset_value is not None:
                entry["handler_offset"] = int(handler_offset_value) & 0xFFFFFFFF
            continue
        if isinstance(handler_value, (int, float, bool)):
            entry["handler_offset"] = int(handler_value) & 0xFFFFFFFF
            continue
        if not isinstance(handler_value, str):
            raise ValueError(f"command handler must be string or integer, got {handler_value!r}")
        handler_name = handler_value.strip()
        if not handler_name:
            raise ValueError("command handler name cannot be empty")
        sym_entry = symbol_table.get(handler_name)
        resolved_address: Optional[int] = None
        if sym_entry is not None:
            if sym_entry.get("section") != "text":
                raise ValueError(f"command handler '{handler_name}' must reference .text symbol")
            resolved_address = int(sym_entry["address"])
        elif origin is not None and origin in modules:
            local_info = origin.get("local_symbols", {}).get(handler_name)
            if local_info and local_info.get("section") == "text":
                resolved_address = origin["code_base"] + int(local_info.get("offset", 0))
        if resolved_address is None:
            raise ValueError(f"command handler symbol '{handler_name}' not found in linked objects")
        entry["handler_offset"] = resolved_address & 0xFFFFFFFF


def _generate_symbol_payload(
    modules: List[Dict[str, Any]],
    symbol_table: Dict[str, Dict[str, Any]],
    final_code: List[int],
    final_rodata: bytearray,
    output_path: Path,
    crc: int,
) -> Dict[str, Any]:
    functions_section: List[Dict[str, Any]] = []
    instructions_section: List[Dict[str, Any]] = []
    variables_section: List[Dict[str, Any]] = []
    local_variables_section: List[Dict[str, Any]] = []

    labels_map: Dict[str, List[str]] = {}
    for name, info in symbol_table.items():
        addr = int(info.get("address", 0)) & 0xFFFFFFFF
        key = f"0x{addr:08X}"
        labels_map.setdefault(key, []).append(name)
        if info.get("section") == "data":
            size_val = info.get("size")
            if size_val is None:
                size_val = 0
            variables_section.append(
                {
                    "name": name,
                    "address": addr,
                    "size": int(size_val),
                    "scope": "global",
                    "type": info.get("type"),
                }
            )
    for names in labels_map.values():
        names.sort()
    variables_section.sort(key=lambda item: item["address"])

    for mod in modules:
        debug_payload = mod.get("debug")
        if not debug_payload:
            continue
        code_words: List[int] = mod["code"]
        base_address = int(mod["code_base"])
        functions_meta = debug_payload.get("functions", [])
        function_ranges: List[Tuple[int, int, Dict[str, Any]]] = []
        function_ord_map: Dict[str, Tuple[int, int]] = {}
        for fn_entry in functions_meta:
            start_ord = fn_entry.get("mvasm_start_ordinal")
            if start_ord is None:
                continue
            end_ord = fn_entry.get("mvasm_end_ordinal")
            if end_ord is None or end_ord < start_ord:
                end_ord = start_ord
            function_ranges.append((start_ord, end_ord, fn_entry))
            function_ord_map[fn_entry.get("function")] = (start_ord, end_ord)
            size_words = max(1, end_ord - start_ord + 1)
            file_info = fn_entry.get("file")
            file_name = None
            if isinstance(file_info, dict):
                file_name = file_info.get("filename")
            elif isinstance(file_info, str):
                file_name = file_info
            functions_section.append(
                {
                    "name": fn_entry.get("name") or fn_entry.get("function"),
                    "linkage_name": fn_entry.get("linkage_name"),
                    "address": base_address + start_ord * 4,
                    "size": size_words * 4,
                    "file": file_name,
                    "line": fn_entry.get("line"),
                }
            )
        function_ranges.sort(key=lambda item: item[0])

        def _function_for_ordinal(ordinal: int) -> Optional[Dict[str, Any]]:
            for start_ord, end_ord, fn_meta in function_ranges:
                if start_ord <= ordinal <= end_ord:
                    return fn_meta
            return None

        for line_entry in debug_payload.get("line_map", []):
            ordinal = line_entry.get("mvasm_ordinal")
            if ordinal is None or ordinal >= len(code_words):
                continue
            pc = base_address + ordinal * 4
            instruction_record: Dict[str, Any] = {
                "pc": pc,
                "word": int(code_words[ordinal]) & 0xFFFFFFFF,
                "mvasm_line": line_entry.get("mvasm_line"),
                "ordinal": ordinal,
            }
            fn_meta = _function_for_ordinal(ordinal)
            if fn_meta:
                instruction_record["function"] = fn_meta.get("name") or fn_meta.get("function")
            if "source_file" in line_entry:
                instruction_record["file"] = line_entry["source_file"]
            if "source_directory" in line_entry:
                instruction_record["directory"] = line_entry["source_directory"]
            if "source_file_id" in line_entry:
                instruction_record["file_id"] = line_entry["source_file_id"]
            if "source_line" in line_entry:
                instruction_record["line"] = line_entry["source_line"]
            if "source_column" in line_entry:
                instruction_record["column"] = line_entry["source_column"]
            if "source_kind" in line_entry:
                instruction_record["source_kind"] = line_entry["source_kind"]
            instructions_section.append(instruction_record)

        for var_entry in debug_payload.get("variables", []):
            fn_name = var_entry.get("function")
            if not fn_name:
                continue
            ord_range = function_ord_map.get(fn_name)
            if not ord_range:
                continue
            location_ranges: List[Dict[str, Any]] = []
            for loc in var_entry.get("locations", []):
                start_ord = loc.get("start_ordinal")
                if start_ord is None or start_ord >= len(code_words):
                    continue
                end_ord = loc.get("end_ordinal")
                if end_ord is None:
                    end_ord = ord_range[1]
                if end_ord is None:
                    end_ord = start_ord
                start_pc = base_address + start_ord * 4
                bounded_end = max(start_ord, min(end_ord, len(code_words)))
                end_pc = base_address + bounded_end * 4
                range_entry = {
                    "start": start_pc,
                    "end": end_pc,
                    "location": loc.get("location"),
                }
                location_ranges.append(range_entry)
            if not location_ranges:
                continue
            file_info = var_entry.get("file") or {}
            local_variables_section.append(
                {
                    "name": var_entry.get("name"),
                    "function": fn_name,
                    "file": file_info.get("filename"),
                    "directory": file_info.get("directory"),
                    "line": var_entry.get("line"),
                    "scope": var_entry.get("scope"),
                    "locations": location_ranges,
                }
            )

    functions_section.sort(key=lambda item: item["address"])
    instructions_section.sort(key=lambda item: item["pc"])

    memory_regions: List[Dict[str, Any]] = []
    if final_code:
        memory_regions.append(
            {
                "name": "code",
                "type": "text",
                "start": 0,
                "end": len(final_code) * 4 - 1,
            }
        )
    if final_rodata:
        memory_regions.append(
            {
                "name": "rodata",
                "type": "data",
                "start": RODATA_BASE,
                "end": RODATA_BASE + len(final_rodata) - 1,
            }
        )

    symbols_payload = {
        "functions": functions_section,
        "variables": variables_section,
        "locals": local_variables_section,
        "labels": {key: names for key, names in sorted(labels_map.items())},
    }

    return {
        "version": 1,
        "hxe_path": str(output_path),
        "hxe_crc": crc & 0xFFFFFFFF,
        "symbols": symbols_payload,
        "instructions": instructions_section,
        "memory_regions": memory_regions,
    }


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

    values_meta = metadata.get("values") or []
    if values_meta:
        payload, count = _encode_value_metadata(list(values_meta))
        metadata_sections.append((METADATA_SECTION_VALUE, payload, count))

    commands_meta = metadata.get("commands") or []
    if commands_meta:
        payload, count = _encode_command_metadata(list(commands_meta))
        metadata_sections.append((METADATA_SECTION_COMMAND, payload, count))

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
    return crc


def link_objects(
    object_paths: List[Path],
    output: Path,
    *,
    verbose: bool = False,
    debug_infos: Optional[List[Path]] = None,
    emit_sym: Optional[Path] = None,
    app_name: Optional[str] = None,
    allow_multiple: bool = True,
    req_caps: int = 0,
) -> Dict:
    modules = [load_hxo(Path(p)) for p in object_paths]
    if not modules:
        raise ValueError("No object files provided")

    debug_info_map: Dict[str, List[Tuple[Path, Dict[str, Any]]]] = {}
    if debug_infos:
        for item in debug_infos:
            dbg_path = Path(item)
            data = json.loads(dbg_path.read_text(encoding="utf-8"))
            debug_info_map.setdefault(dbg_path.stem, []).append((dbg_path, data))
    for mod in modules:
        stem = mod["path"].stem
        entries = debug_info_map.get(stem)
        if entries:
            dbg_path, dbg_data = entries.pop(0)
            mod["debug"] = dbg_data
            mod["debug_path"] = dbg_path
    if emit_sym:
        missing_debug = [mod["path"].name for mod in modules if "debug" not in mod]
        if missing_debug:
            raise ValueError(
                "Debug info required for --emit-sym, missing for: " + ", ".join(sorted(missing_debug))
            )
    unused_debug = [
        str(entry[0])
        for entries in debug_info_map.values()
        for entry in entries
        if entries
    ]
    if unused_debug:
        raise ValueError("Unmatched debug info files: " + ", ".join(sorted(unused_debug)))

    code_offset = 0
    ro_offset = 0
    for mod in modules:
        mod["code_base"] = code_offset
        mod["ro_base"] = ro_offset
        code_offset += len(mod["code"]) * 4
        ro_offset += len(mod["rodata"])

    aggregated_values: List[Dict[str, Any]] = []
    aggregated_commands: List[Dict[str, Any]] = []
    aggregated_mailboxes: List[Dict[str, Any]] = []
    seen_values: Dict[tuple[int, int], Path] = {}
    seen_commands: Dict[tuple[int, int], Path] = {}
    seen_mailboxes: Dict[str, Path] = {}
    for mod in modules:
        metadata = mod.get("metadata") or {}
        values_meta = metadata.get("values") or []
        if not isinstance(values_meta, list):
            raise ValueError(f"Value metadata for {mod['path']} must be a list")
        for entry in values_meta:
            if not isinstance(entry, dict):
                raise ValueError(f"Value metadata entries must be objects ({mod['path']})")
            group_id = _normalise_uint8("value metadata group_id", entry.get("group", entry.get("group_id")))
            value_id = _normalise_uint8("value metadata value_id", entry.get("value", entry.get("value_id")))
            key = (group_id, value_id)
            if key in seen_values:
                raise ValueError(
                    f"Duplicate value metadata ({group_id},{value_id}) defined in {mod['path']} and {seen_values[key]}"
                )
            seen_values[key] = mod["path"]
            aggregated_values.append(dict(entry))
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
        commands_meta = metadata.get("commands") or []
        if not isinstance(commands_meta, list):
            raise ValueError(f"Command metadata for {mod['path']} must be a list")
        for entry in commands_meta:
            if not isinstance(entry, dict):
                raise ValueError(f"Command metadata entries must be objects ({mod['path']})")
            group_id = _normalise_uint8("command metadata group_id", entry.get("group", entry.get("group_id")))
            cmd_id = _normalise_uint8("command metadata cmd_id", entry.get("cmd", entry.get("cmd_id")))
            key = (group_id, cmd_id)
            if key in seen_commands:
                raise ValueError(
                    f"Duplicate command metadata ({group_id},{cmd_id}) defined in {mod['path']} and {seen_commands[key]}"
                )
            seen_commands[key] = mod["path"]
            entry_copy = dict(entry)
            entry_copy["_module"] = mod
            aggregated_commands.append(entry_copy)

    if aggregated_mailboxes:
        aggregated_mailboxes.sort(key=lambda item: item["target"])
    if aggregated_values:
        aggregated_values.sort(
            key=lambda item: (
                _normalise_uint8("value metadata group_id", item.get("group", item.get("group_id"))),
                _normalise_uint8("value metadata value_id", item.get("value", item.get("value_id"))),
            )
        )
    if aggregated_commands:
        aggregated_commands.sort(
            key=lambda item: (
                _normalise_uint8("command metadata group_id", item.get("group", item.get("group_id"))),
                _normalise_uint8("command metadata cmd_id", item.get("cmd", item.get("cmd_id"))),
            )
        )
    metadata: Dict[str, Any] = {}
    if aggregated_values:
        metadata["values"] = aggregated_values
    if aggregated_commands:
        metadata["commands"] = aggregated_commands
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

    if metadata.get("commands"):
        _resolve_command_handler_offsets(metadata["commands"], modules, symbol_table)
    if metadata.get("values"):
        for entry in metadata["values"]:
            entry.pop("_module", None)

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

    crc = write_hxe_v2(
        Path(output),
        code_words=final_code,
        entry=entry_address or 0,
        rodata=bytes(final_rodata),
        metadata=metadata,
        app_name=app_name or Path(output).stem,
        allow_multiple=allow_multiple,
        req_caps=req_caps,
    )
    sym_payload: Optional[Dict[str, Any]] = None
    if emit_sym:
        sym_path = Path(emit_sym)
        sym_path.parent.mkdir(parents=True, exist_ok=True)
        sym_payload = _generate_symbol_payload(modules, symbol_table, final_code, final_rodata, Path(output), crc)
        sym_path.write_text(json.dumps(sym_payload, indent=2, sort_keys=True))
    if verbose:
        print(f"Linked {len(modules)} modules -> {output}")
        print(f"  entry=0x{entry_address or 0:08X} words={len(final_code)} rodata={len(final_rodata)}")
        print(f"  exports: {', '.join(sorted(symbol_table.keys()))}")
    result = {
        "entry": entry_address or 0,
        "words": len(final_code),
        "rodata": len(final_rodata),
        "crc": crc,
    }
    if sym_payload is not None:
        result["sym"] = sym_payload
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("inputs", nargs="+")
    ap.add_argument("-o", "--output", required=True)
    ap.add_argument("-v", "--verbose", action="store_true")
    ap.add_argument("--app-name")
    ap.add_argument("--emit-sym")
    ap.add_argument("--debug-info", nargs="+", action="append", default=[])
    ap.add_argument("--req-cap", dest="req_cap", type=int, default=0, help="Required capability mask")
    ap.add_argument(
        "--single-instance",
        dest="allow_multiple",
        action="store_false",
        help="Disallow multiple concurrent instances of the linked application",
    )
    ap.add_argument(
        "--allow-multiple-instances",
        dest="allow_multiple",
        action="store_true",
        help="Explicitly allow multiple concurrent instances (default)",
    )
    ap.set_defaults(allow_multiple=True)
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

    debug_info_paths: List[Path] = []
    for group in args.debug_info:
        debug_info_paths.extend(Path(item) for item in group)

    link_objects(
        hxo_inputs,
        Path(args.output),
        verbose=args.verbose,
        debug_infos=debug_info_paths or None,
        emit_sym=Path(args.emit_sym) if args.emit_sym else None,
        app_name=args.app_name,
        allow_multiple=args.allow_multiple,
        req_caps=args.req_cap,
    )
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
