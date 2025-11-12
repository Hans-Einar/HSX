#!/usr/bin/env python3
"""
hsx-llc.py — LLVM IR (text) -> HSX .mvasm (MVP)
- Supports a tiny subset: i32 arithmetic, return, branches, basic calls stub.
- Goal: bootstrap pipeline for testing; extend incrementally.

Usage:
  python3 hsx-llc.py input.ll -o output.mvasm --trace
"""
import argparse, json, re, sys
import math
import struct
from collections import defaultdict, deque
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

try:
    import hsx_mailbox_constants as mbx_const
    import hsx_value_constants as val_const
    import hsx_command_constants as cmd_const
except ImportError:  # pragma: no cover - allow running as package
    from python import hsx_mailbox_constants as mbx_const
    from python import hsx_value_constants as val_const
    from python import hsx_command_constants as cmd_const

R_RET = "R0"
ATTR_TOKENS = {"nsw", "nuw", "noundef", "dso_local", "local_unnamed_addr", "volatile"}

SPLIT_DISTANCE_THRESHOLD = 12
ENABLE_COALESCE = True
ENABLE_PROACTIVE_SPLIT = True


def _set_allocator_features(*, coalesce: Optional[bool] = None, split: Optional[bool] = None) -> Tuple[bool, bool]:
    global ENABLE_COALESCE, ENABLE_PROACTIVE_SPLIT
    prev = (ENABLE_COALESCE, ENABLE_PROACTIVE_SPLIT)
    if coalesce is not None:
        ENABLE_COALESCE = bool(coalesce)
    if split is not None:
        ENABLE_PROACTIVE_SPLIT = bool(split)
    return prev

MOV_RE = re.compile(r"MOV\s+(R\d{1,2}),\s*(R\d{1,2})$", re.IGNORECASE)
IMM_TOKEN = r"(?:-?\d+|0x[0-9A-Fa-f]+)"
LDI_RE = re.compile(rf"LDI\s+(R\d{{1,2}}),\s*({IMM_TOKEN})$", re.IGNORECASE)
LDI32_RE = re.compile(rf"LDI32\s+(R\d{{1,2}}),\s*({IMM_TOKEN})$", re.IGNORECASE)

ARG_REGS = ["R1","R2","R3"]  # more via stack later

MODE_ALIASES = {
    "RDONLY": mbx_const.HSX_MBX_MODE_RDONLY,
    "RO": mbx_const.HSX_MBX_MODE_RDONLY,
    "WRONLY": mbx_const.HSX_MBX_MODE_WRONLY,
    "WO": mbx_const.HSX_MBX_MODE_WRONLY,
    "RDWR": mbx_const.HSX_MBX_MODE_RDWR,
    "RW": mbx_const.HSX_MBX_MODE_RDWR,
    "TAP": mbx_const.HSX_MBX_MODE_TAP,
    "FANOUT": mbx_const.HSX_MBX_MODE_FANOUT,
    "FANOUT_DROP": mbx_const.HSX_MBX_MODE_FANOUT_DROP,
    "FANOUT_BLOCK": mbx_const.HSX_MBX_MODE_FANOUT_BLOCK,
}

VALUE_FLAG_ALIASES = {
    "RO": val_const.HSX_VAL_FLAG_RO,
    "READONLY": val_const.HSX_VAL_FLAG_RO,
    "READ_ONLY": val_const.HSX_VAL_FLAG_RO,
    "PERSIST": val_const.HSX_VAL_FLAG_PERSIST,
    "STICKY": val_const.HSX_VAL_FLAG_STICKY,
    "PIN": val_const.HSX_VAL_FLAG_PIN,
    "BOOL": val_const.HSX_VAL_FLAG_BOOL,
}

VALUE_AUTH_ALIASES = {
    "PUBLIC": val_const.HSX_VAL_AUTH_PUBLIC,
    "USER": val_const.HSX_VAL_AUTH_USER,
    "ADMIN": val_const.HSX_VAL_AUTH_ADMIN,
    "FACTORY": val_const.HSX_VAL_AUTH_FACTORY,
}

COMMAND_FLAG_ALIASES = {
    "PIN": cmd_const.HSX_CMD_FLAG_PIN,
    "ASYNC": cmd_const.HSX_CMD_FLAG_ASYNC,
}

COMMAND_AUTH_ALIASES = {
    "PUBLIC": cmd_const.HSX_CMD_AUTH_PUBLIC,
    "USER": cmd_const.HSX_CMD_AUTH_USER,
    "ADMIN": cmd_const.HSX_CMD_AUTH_ADMIN,
    "FACTORY": cmd_const.HSX_CMD_AUTH_FACTORY,
}

LAST_DEBUG_INFO: Optional[Dict[str, Any]] = None

def _write_debug_file(path: str, payload: Optional[Dict[str, Any]]) -> None:
    if not payload:
        raise ValueError("No debug metadata captured; rerun with -g input or ensure --emit-debug after lowering.")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2)
        fh.write("\n")


# ---------------------------------------------------------------------------
# Global symbol sanitization helpers

_GLOBAL_NAME_CACHE: Dict[str, str] = {}
_GLOBAL_RESERVED_NAMES: Set[str] = set()
_GLOBAL_NAME_COUNTER = 0
# Windows COFF IR places duplicate COMDAT names in lines that begin with
# `$"..." = comdat any`. Those names use the same quoting syntax as globals,
# but we must leave them intact so the surrounding syntax stays valid.  Use a
# negative look-behind to ensure we only touch real globals that are written as
# `@"..."` and ignore the `$"..."` COMDAT aliases.
_QUOTED_GLOBAL_RE = re.compile(r'(?<!\$)@"([^"\\]*(?:\\.[^"\\]*)*)"')
_BARE_GLOBAL_RE = re.compile(r'@([A-Za-z0-9_.]+)')


def _reset_global_name_cache() -> None:
    global _GLOBAL_NAME_CACHE, _GLOBAL_NAME_COUNTER, _GLOBAL_RESERVED_NAMES
    _GLOBAL_NAME_CACHE = {}
    _GLOBAL_NAME_COUNTER = 0
    _GLOBAL_RESERVED_NAMES = set()


def _reserve_global_name(name: str) -> None:
    _GLOBAL_RESERVED_NAMES.add(name)


def _sanitize_global_name(raw: str) -> str:
    """Return a backend-safe symbol name for an arbitrary LLVM global."""

    global _GLOBAL_NAME_COUNTER
    cached = _GLOBAL_NAME_CACHE.get(raw)
    if cached:
        return cached

    if re.fullmatch(r"[A-Za-z0-9_.]+", raw):
        name = raw
    else:
        while True:
            _GLOBAL_NAME_COUNTER += 1
            candidate = f"__hsx_quoted_global_{_GLOBAL_NAME_COUNTER}"
            if candidate not in _GLOBAL_RESERVED_NAMES:
                name = candidate
                break
    _reserve_global_name(name)
    _GLOBAL_NAME_CACHE[raw] = name
    return name


def _preprocess_ir_text(ir_text: str) -> str:
    """Replace quoted global references with sanitized backend names."""

    for match in _BARE_GLOBAL_RE.finditer(ir_text):
        _reserve_global_name(match.group(1))

    def repl(match: re.Match) -> str:
        raw = match.group(1)
        # Unescape simple sequences like \01 that Clang may emit for globals.
        raw_unescaped = bytes(raw, "utf-8").decode("unicode_escape")
        name = _sanitize_global_name(raw_unescaped)
        return f"@{name}"

    processed_lines = []
    for line in ir_text.splitlines():
        if line.lstrip().startswith('$"'):
            processed_lines.append(line)
            continue
        processed_lines.append(_QUOTED_GLOBAL_RE.sub(repl, line))
    suffix = "\n" if ir_text.endswith("\n") else ""
    return "\n".join(processed_lines) + suffix

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

    def parse_align_from_tail(tail: str) -> Optional[int]:
        if not tail:
            return None
        match = re.search(r'align\s+(\d+)', tail)
        if match:
            return int(match.group(1))
        return None

    def split_value_and_attrs(text: str) -> Tuple[str, str]:
        depth = 0
        in_string = False
        escape = False
        for idx, ch in enumerate(text):
            if in_string:
                if escape:
                    escape = False
                    continue
                if ch == '\\':
                    escape = True
                    continue
                if ch == '"':
                    in_string = False
                continue
            if ch == '"':
                in_string = True
                continue
            if ch == '(':
                depth += 1
                continue
            if ch == ')':
                depth = max(depth - 1, 0)
                continue
            if ch == ',' and depth == 0:
                return text[:idx].strip(), text[idx + 1 :].strip()
        return text.strip(), ''

    string_match = re.match(
        r'@([A-Za-z0-9_.]+)\s*=\s*(?:[\w.]+\s+)*constant\s+\[(\d+)\s+x\s+i8\]\s+c"((?:[^"\\]|\\.)*)"(.*)',
        line,
    )
    if string_match:
        name, _, body, tail = string_match.groups()
        data = parse_llvm_string_literal(body)
        align = parse_align_from_tail(tail)
        return {"name": name, "kind": "bytes", "data": data, "align": align}

    zero_array_match = re.match(
        r'@([A-Za-z0-9_.]+)\s*=\s*(?:[\w.]+\s+)*global\s+\[(\d+)\s+x\s+i(8|16|32)\]\s+zeroinitializer(.*)',
        line,
    )
    if zero_array_match:
        name, count, bits, tail = zero_array_match.groups()
        count = int(count)
        elem_size = int(bits) // 8
        data = bytes([0] * (count * elem_size))
        align = parse_align_from_tail(tail)
        return {"name": name, "kind": "bytes", "data": data, "align": align}

    int_match = re.match(
        r'@([A-Za-z0-9_.]+)\s*=\s*(?:[\w.]+\s+)*global\s+i(8|16|32)\s+(.+)',
        line,
    )
    if int_match:
        name, bits, rest = int_match.groups()
        value_str, tail = split_value_and_attrs(rest)
        align = parse_align_from_tail(tail)
        value_str = value_str.strip()
        value = 0 if value_str == 'zeroinitializer' else int(value_str, 0)
        return {"name": name, "kind": "int", "bits": int(bits), "value": value, "align": align}

    float_match = re.match(
        r'@([A-Za-z0-9_.]+)\s*=\s*(?:[\w.]+\s+)*global\s+float\s+(.+)',
        line,
    )
    if float_match:
        name, rest = float_match.groups()
        value_str, tail = split_value_and_attrs(rest)
        align = parse_align_from_tail(tail)
        value_str = value_str.strip()
        if value_str == 'zeroinitializer':
            bits = 0
        elif value_str.lower().startswith('0x'):
            bits = int(value_str, 16) & 0xFFFFFFFF
        else:
            bits = struct.unpack('<I', struct.pack('<f', float(value_str)))[0]
        return {"name": name, "kind": "float", "bits": 32, "value": bits, "align": align}
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


def _coerce_pragma_value(value: str) -> object:
    text = value.strip()
    if not text:
        return ""
    if text[0] in {'"', "'"} and text[-1] == text[0]:
        body = text[1:-1]
        return bytes(body, "utf-8").decode("unicode_escape")
    if text[0] in {'{', '['} and text[-1] in {'}', ']'}:
        return json.loads(text)
    if text.lower() in {"true", "false"}:
        return text.lower() == "true"
    try:
        return int(text, 0)
    except ValueError:
        return text


def _pop_any(values: Dict[str, object], *keys: str) -> Optional[object]:
    for key in keys:
        if key in values:
            return values.pop(key)
    return None


def _parse_flag_tokens(raw: object, alias_map: Dict[str, int], field: str) -> int:
    if raw is None or raw == "":
        return 0
    if isinstance(raw, bool):
        return int(raw)
    if isinstance(raw, (int, float)):
        return int(raw)
    if isinstance(raw, str):
        mask = 0
        tokens = [token.strip().upper() for token in re.split(r"[|]", raw) if token.strip()]
        if not tokens:
            return 0
        for token in tokens:
            value = alias_map.get(token)
            if value is None:
                raise ISelError(f"{field} uses unknown flag '{token}'")
            mask |= int(value)
        return mask
    raise ISelError(f"{field} expects integer or flag string, got {raw!r}")


def _parse_auth_token(raw: object, alias_map: Dict[str, int], field: str) -> int:
    if raw is None or raw == "":
        return 0
    if isinstance(raw, bool):
        return int(raw)
    if isinstance(raw, (int, float)):
        return int(raw)
    if isinstance(raw, str):
        token = raw.strip().upper()
        if not token:
            return 0
        value = alias_map.get(token)
        if value is None:
            raise ISelError(f"{field} uses unknown token '{raw}'")
        return int(value)
    raise ISelError(f"{field} expects integer or auth token, got {raw!r}")


def _coerce_float_arg(name: str, value: object) -> float:
    if value is None or value == "":
        return 0.0
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError as exc:
            raise ISelError(f"{name} expects numeric value, got '{value}'") from exc
    raise ISelError(f"{name} expects numeric value, got {value!r}")


def _coerce_int_arg(name: str, value: object) -> int:
    if value is None or value == "":
        raise ISelError(f"{name} requires a value")
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str):
        try:
            return int(value, 0)
        except ValueError as exc:
            raise ISelError(f"{name} expects integer literal, got '{value}'") from exc
    raise ISelError(f"{name} expects integer literal, got {value!r}")


def _parse_mailbox_mode_tokens(spec: str) -> int:
    tokens = [tok.strip().upper() for tok in re.split(r"[|]", spec) if tok.strip()]
    if not tokens:
        raise ISelError("hsx_mailbox pragma mode string cannot be empty")
    mask = 0
    for tok in tokens:
        value = MODE_ALIASES.get(tok)
        if value is None:
            raise ISelError(f"hsx_mailbox pragma uses unknown mode token '{tok}'")
        mask |= int(value)
    return mask


def _parse_mailbox_pragma(arg_text: str) -> Dict[str, object]:
    params = _split_top_level(arg_text, ',')
    parsed: Dict[str, object] = {}
    for piece in params:
        if not piece.strip():
            continue
        if '=' not in piece:
            raise ISelError(f"hsx_mailbox pragma expected key=value entries, got '{piece}'")
        key, value = piece.split('=', 1)
        key = key.strip()
        if not key:
            raise ISelError("hsx_mailbox pragma contains empty key")
        parsed[key] = _coerce_pragma_value(value)
    target_val = parsed.pop("target", None)
    if target_val is None:
        raise ISelError("hsx_mailbox pragma requires target=\"namespace:name\"")
    target = str(target_val).strip()
    if not target:
        raise ISelError("hsx_mailbox pragma target cannot be empty")
    entry: Dict[str, object] = {"target": target}
    if "capacity" in parsed:
        entry["capacity"] = int(parsed.pop("capacity"))
    if "queue_depth" in parsed:
        entry["queue_depth"] = int(parsed.pop("queue_depth"))
    if "mode_mask" in parsed:
        entry["mode_mask"] = int(parsed.pop("mode_mask"))
    elif "mode" in parsed:
        entry["mode_mask"] = _parse_mailbox_mode_tokens(str(parsed.pop("mode")))
    if "owner_pid" in parsed:
        entry["owner_pid"] = int(parsed.pop("owner_pid"))
    if "bindings" in parsed:
        entry["bindings"] = parsed.pop("bindings")
    for key, value in parsed.items():
        entry[key] = value
    return entry


def _parse_value_pragma(arg_text: str) -> Dict[str, object]:
    params = _split_top_level(arg_text, ',')
    positional: List[object] = []
    parsed: Dict[str, object] = {}
    for piece in params:
        token = piece.strip()
        if not token:
            continue
        if '=' in token:
            key, value = token.split('=', 1)
            key = key.strip()
            if not key:
                raise ISelError("hsx_value pragma contains empty key")
            parsed[key] = _coerce_pragma_value(value)
        else:
            positional.append(_coerce_pragma_value(token))
    entry: Dict[str, object] = {}
    if positional:
        name_token = str(positional[0]).strip()
        if name_token:
            entry["name"] = name_token
    group_raw = _pop_any(parsed, "group", "group_id", "groupId")
    if group_raw is None:
        raise ISelError("hsx_value pragma requires group=<id>")
    group_id = _coerce_int_arg("hsx_value group", group_raw)
    if not (0 <= group_id <= 0xFF):
        raise ISelError("hsx_value group must be within 0..255")
    entry["group"] = group_id
    value_raw = _pop_any(parsed, "id", "value", "value_id", "valueId")
    if value_raw is None:
        raise ISelError("hsx_value pragma requires id=<value_id>")
    value_id = _coerce_int_arg("hsx_value id", value_raw)
    if not (0 <= value_id <= 0xFF):
        raise ISelError("hsx_value id must be within 0..255")
    entry["value"] = value_id
    group_name = _pop_any(parsed, "group_name", "groupName")
    if group_name is not None:
        entry["group_name"] = str(group_name)
    flags_raw = _pop_any(parsed, "flags")
    if flags_raw is not None:
        entry["flags"] = _parse_flag_tokens(flags_raw, VALUE_FLAG_ALIASES, "hsx_value flags")
    auth_raw = _pop_any(parsed, "auth", "auth_level", "authLevel")
    if auth_raw is not None:
        entry["auth"] = _parse_auth_token(auth_raw, VALUE_AUTH_ALIASES, "hsx_value auth")
    init_raw = _pop_any(parsed, "init", "init_value")
    if init_raw is not None:
        entry["init"] = _coerce_float_arg("hsx_value init", init_raw)
    init_raw_raw = _pop_any(parsed, "init_raw")
    if init_raw_raw is not None:
        entry["init_raw"] = _coerce_int_arg("hsx_value init_raw", init_raw_raw) & 0xFFFF
    epsilon_raw = _pop_any(parsed, "epsilon")
    if epsilon_raw is not None:
        entry["epsilon"] = _coerce_float_arg("hsx_value epsilon", epsilon_raw)
    epsilon_raw_raw = _pop_any(parsed, "epsilon_raw")
    if epsilon_raw_raw is not None:
        entry["epsilon_raw"] = _coerce_int_arg("hsx_value epsilon_raw", epsilon_raw_raw) & 0xFFFF
    min_raw = _pop_any(parsed, "min")
    if min_raw is not None:
        entry["min"] = _coerce_float_arg("hsx_value min", min_raw)
    min_raw_raw = _pop_any(parsed, "min_raw")
    if min_raw_raw is not None:
        entry["min_raw"] = _coerce_int_arg("hsx_value min_raw", min_raw_raw) & 0xFFFF
    max_raw = _pop_any(parsed, "max")
    if max_raw is not None:
        entry["max"] = _coerce_float_arg("hsx_value max", max_raw)
    max_raw_raw = _pop_any(parsed, "max_raw")
    if max_raw_raw is not None:
        entry["max_raw"] = _coerce_int_arg("hsx_value max_raw", max_raw_raw) & 0xFFFF
    persist_key = _pop_any(parsed, "persist_key", "persist")
    if persist_key is not None:
        key_value = _coerce_int_arg("hsx_value persist_key", persist_key)
        if not (0 <= key_value <= 0xFFFF):
            raise ISelError("hsx_value persist_key must be within 0..65535")
        entry["persist_key"] = key_value
    unit_value = _pop_any(parsed, "unit", "unit_name", "unitName")
    if unit_value is not None:
        entry["unit"] = str(unit_value)
    rate_ms = _pop_any(parsed, "rate_ms", "rateMs")
    if rate_ms is not None:
        entry["rate_ms"] = _coerce_int_arg("hsx_value rate_ms", rate_ms)
    # Preserve any additional keys for forwards compatibility.
    for key, value in parsed.items():
        entry[key] = value
    return entry


def _parse_command_pragma(arg_text: str) -> Dict[str, object]:
    params = _split_top_level(arg_text, ',')
    positional: List[object] = []
    parsed: Dict[str, object] = {}
    for piece in params:
        token = piece.strip()
        if not token:
            continue
        if '=' in token:
            key, value = token.split('=', 1)
            key = key.strip()
            if not key:
                raise ISelError("hsx_command pragma contains empty key")
            parsed[key] = _coerce_pragma_value(value)
        else:
            positional.append(_coerce_pragma_value(token))
    entry: Dict[str, object] = {}
    if positional:
        name_token = str(positional[0]).strip()
        if name_token:
            entry["name"] = name_token
    group_raw = _pop_any(parsed, "group", "group_id", "groupId")
    if group_raw is None:
        raise ISelError("hsx_command pragma requires group=<id>")
    group_id = _coerce_int_arg("hsx_command group", group_raw)
    if not (0 <= group_id <= 0xFF):
        raise ISelError("hsx_command group must be within 0..255")
    entry["group"] = group_id
    cmd_raw = _pop_any(parsed, "id", "cmd", "cmd_id", "command_id", "commandId")
    if cmd_raw is None:
        raise ISelError("hsx_command pragma requires id=<cmd_id>")
    cmd_id = _coerce_int_arg("hsx_command id", cmd_raw)
    if not (0 <= cmd_id <= 0xFF):
        raise ISelError("hsx_command id must be within 0..255")
    entry["cmd"] = cmd_id
    group_name = _pop_any(parsed, "group_name", "groupName")
    if group_name is not None:
        entry["group_name"] = str(group_name)
    flags_raw = _pop_any(parsed, "flags")
    if flags_raw is not None:
        entry["flags"] = _parse_flag_tokens(flags_raw, COMMAND_FLAG_ALIASES, "hsx_command flags")
    auth_raw = _pop_any(parsed, "auth", "auth_level", "authLevel")
    if auth_raw is not None:
        entry["auth"] = _parse_auth_token(auth_raw, COMMAND_AUTH_ALIASES, "hsx_command auth")
    handler_offset_raw = _pop_any(parsed, "handler_offset")
    if handler_offset_raw is not None:
        entry["handler_offset"] = _coerce_int_arg("hsx_command handler_offset", handler_offset_raw)
    else:
        handler_raw = _pop_any(parsed, "handler")
        if handler_raw is not None:
            if isinstance(handler_raw, str):
                handler_name = handler_raw.strip()
                if not handler_name:
                    raise ISelError("hsx_command handler cannot be empty")
                entry["handler"] = handler_name
            else:
                entry["handler_offset"] = _coerce_int_arg("hsx_command handler", handler_raw)
    help_value = _pop_any(parsed, "help")
    if help_value is not None:
        entry["help"] = str(help_value)
    reserved_value = _pop_any(parsed, "reserved")
    if reserved_value is not None:
        entry["reserved"] = _coerce_int_arg("hsx_command reserved", reserved_value)
    for key, value in parsed.items():
        entry[key] = value
    return entry


def _align_to(value: int, alignment: int) -> int:
    if alignment <= 0:
        alignment = 1
    return ((value + alignment - 1) // alignment) * alignment


def _split_top_level(expr: str, sep: str = ',') -> List[str]:
    parts: List[str] = []
    depth = 0
    token: List[str] = []
    idx = 0
    while idx < len(expr):
        ch = expr[idx]
        if ch in '{[(':
            depth += 1
        elif ch in '}])':
            depth = max(depth - 1, 0)
        if ch == sep and depth == 0:
            piece = ''.join(token).strip()
            if piece:
                parts.append(piece)
            token = []
        else:
            token.append(ch)
        idx += 1
    tail = ''.join(token).strip()
    if tail:
        parts.append(tail)
    return parts


def _strip_quotes(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    text = value.strip()
    if len(text) >= 2 and text[0] == '"' and text[-1] == '"':
        body = text[1:-1]
        try:
            return bytes(body, "utf-8").decode("unicode_escape")
        except Exception:
            return body
    return text or None


def _parse_metadata_fields(body: str) -> Dict[str, str]:
    fields: Dict[str, str] = {}
    for piece in _split_top_level(body):
        if ':' not in piece:
            continue
        key, value = piece.split(':', 1)
        fields[key.strip()] = value.strip()
    return fields


def _extract_metadata_args(text: str, marker: str) -> Optional[str]:
    idx = text.find(marker)
    if idx == -1:
        return None
    start = text.find('(', idx)
    if start == -1:
        return None
    start += 1
    depth = 1
    pos = start
    end = len(text)
    while pos < len(text) and depth > 0:
        ch = text[pos]
        if ch == '(':
            depth += 1
        elif ch == ')':
            depth -= 1
            if depth == 0:
                end = pos
                break
        pos += 1
    if depth != 0:
        return None
    return text[start:end]


def _parse_int_field(value: Optional[str]) -> Optional[int]:
    if value is None:
        return None
    text = value.strip()
    if not text or text.lower() == "null":
        return None
    try:
        return int(text, 0)
    except ValueError:
        return None


def _parse_difile(meta_id: str, text: str) -> Optional[Dict[str, Any]]:
    body = _extract_metadata_args(text, "!DIFile")
    if body is None:
        return None
    fields = _parse_metadata_fields(body)
    filename = _strip_quotes(fields.get("filename")) or ""
    directory = _strip_quotes(fields.get("directory")) or ""
    return {
        "id": meta_id,
        "filename": filename,
        "directory": directory,
    }


def _parse_disubprogram(meta_id: str, text: str) -> Optional[Dict[str, Any]]:
    body = _extract_metadata_args(text, "!DISubprogram")
    if body is None:
        return None
    fields = _parse_metadata_fields(body)
    name = _strip_quotes(fields.get("name"))
    linkage_name = _strip_quotes(fields.get("linkageName"))
    file_ref = fields.get("file")
    line = _parse_int_field(fields.get("line")) or 0
    scope_line = _parse_int_field(fields.get("scopeLine"))
    return {
        "id": meta_id,
        "name": name,
        "linkage_name": linkage_name,
        "file": file_ref,
        "line": line,
        "scope_line": scope_line or 0,
        "scope": fields.get("scope"),
        "raw": text,
    }


def _parse_dilocation(meta_id: str, text: str) -> Optional[Dict[str, Any]]:
    body = _extract_metadata_args(text, "!DILocation")
    if body is None:
        return None
    fields = _parse_metadata_fields(body)
    result: Dict[str, Any] = {
        "id": meta_id,
        "line": _parse_int_field(fields.get("line")),
        "column": _parse_int_field(fields.get("column")),
    }
    scope = fields.get("scope")
    if scope:
        result["scope"] = scope
    inlined = fields.get("inlinedAt")
    if inlined:
        result["inlined_at"] = inlined
    file_ref = fields.get("file")
    if file_ref:
        result["file"] = file_ref
    return result


def _parse_dilexicalblock(meta_id: str, text: str) -> Optional[Dict[str, Any]]:
    body = _extract_metadata_args(text, "!DILexicalBlock")
    if body is None:
        return None
    fields = _parse_metadata_fields(body)
    result: Dict[str, Any] = {
        "id": meta_id,
        "line": _parse_int_field(fields.get("line")),
        "column": _parse_int_field(fields.get("column")),
    }
    scope = fields.get("scope")
    if scope:
        result["scope"] = scope
    file_ref = fields.get("file")
    if file_ref:
        result["file"] = file_ref
    return result


def _parse_dilocalvariable(meta_id: str, text: str) -> Optional[Dict[str, Any]]:
    body = _extract_metadata_args(text, "!DILocalVariable")
    if body is None:
        return None
    fields = _parse_metadata_fields(body)
    return {
        "id": meta_id,
        "name": _strip_quotes(fields.get("name")) or "",
        "arg": _parse_int_field(fields.get("arg")) or 0,
        "scope": fields.get("scope"),
        "file": fields.get("file"),
        "line": _parse_int_field(fields.get("line")),
        "type": fields.get("type"),
        "flags": fields.get("flags"),
        "align": _parse_int_field(fields.get("align")),
    }


def _parse_diexpression(meta_id: str, text: str) -> Optional[Dict[str, Any]]:
    body = _extract_metadata_args(text, "!DIExpression")
    if body is None:
        return None
    ops: List[Any] = []
    for token in _split_top_level(body):
        piece = token.strip()
        if not piece:
            continue
        if piece.startswith("DW_OP"):
            ops.append(piece)
            continue
        try:
            ops.append(int(piece, 0))
        except ValueError:
            ops.append(piece)
    return {
        "id": meta_id,
        "ops": ops,
    }


def parse_ir(lines: List[str]) -> Dict:
    ir = {
        "functions": [],
        "globals": [],
        "types": {},
        "mailboxes": [],
        "values": [],
        "commands": [],
    }
    cur = None
    bb = None
    debug_files: Dict[str, Dict[str, Any]] = {}
    debug_subprograms: Dict[str, Dict[str, Any]] = {}
    debug_locations: Dict[str, Dict[str, Any]] = {}
    debug_lexical_blocks: Dict[str, Dict[str, Any]] = {}
    debug_locals: Dict[str, Dict[str, Any]] = {}
    debug_expressions: Dict[str, Dict[str, Any]] = {}
    total = len(lines)
    idx = 0
    while idx < total:
        raw = lines[idx]
        idx += 1
        line = raw.strip()
        if not line:
            continue
        if line.startswith(";"):
            mailbox_match = re.match(r';\s*#pragma\s+hsx_mailbox\s*\((.*)\)\s*$', line, re.IGNORECASE)
            if mailbox_match:
                entry = _parse_mailbox_pragma(mailbox_match.group(1))
                ir["mailboxes"].append(entry)
                continue
            value_match = re.match(r';\s*#pragma\s+hsx_value\s*\((.*)\)\s*$', line, re.IGNORECASE)
            if value_match:
                entry = _parse_value_pragma(value_match.group(1))
                ir["values"].append(entry)
                continue
            command_match = re.match(r';\s*#pragma\s+hsx_command\s*\((.*)\)\s*$', line, re.IGNORECASE)
            if command_match:
                entry = _parse_command_pragma(command_match.group(1))
                ir["commands"].append(entry)
                continue
            continue
        if line.startswith("!"):
            meta_match = re.match(r'(!\d+)\s*=\s*(.*)', line)
            if meta_match:
                meta_id = meta_match.group(1)
                rhs = meta_match.group(2).strip()
                target_tokens = (
                    "!DISubprogram",
                    "!DIFile",
                    "!DILocation",
                    "!DILexicalBlock",
                    "!DILocalVariable",
                    "!DIExpression",
                )
                merged = rhs
                if any(token in rhs for token in target_tokens):
                    parts = [rhs]
                    balance = rhs.count("(") - rhs.count(")")
                    while balance > 0 and idx < total:
                        next_line = lines[idx].strip()
                        parts.append(next_line)
                        balance += next_line.count("(") - next_line.count(")")
                        idx += 1
                    merged = " ".join(part for part in parts)
                if "!DISubprogram" in merged:
                    parsed = _parse_disubprogram(meta_id, merged)
                    if parsed:
                        debug_subprograms[meta_id] = parsed
                elif "!DIFile" in merged:
                    parsed = _parse_difile(meta_id, merged)
                    if parsed:
                        debug_files[meta_id] = parsed
                elif "!DILocation" in merged:
                    parsed = _parse_dilocation(meta_id, merged)
                    if parsed:
                        debug_locations[meta_id] = parsed
                elif "!DILexicalBlock" in merged:
                    parsed = _parse_dilexicalblock(meta_id, merged)
                    if parsed:
                        debug_lexical_blocks[meta_id] = parsed
                elif "!DILocalVariable" in merged:
                    parsed = _parse_dilocalvariable(meta_id, merged)
                    if parsed:
                        debug_locals[meta_id] = parsed
                elif "!DIExpression" in merged:
                    parsed = _parse_diexpression(meta_id, merged)
                    if parsed:
                        debug_expressions[meta_id] = parsed
            continue
        if cur is None:
            type_match = re.match(r'(%[A-Za-z0-9_.]+)\s*=\s*type\s+(.+)', line)
            if type_match:
                type_name, type_body = type_match.groups()
                ir["types"][type_name] = type_body.strip()
                continue
        if cur is None and line.startswith('@'):
            glob = parse_global_definition(line)
            if glob:
                ir["globals"].append(glob)
            continue
        if line.startswith("define "):
            m = re.match(
                r'define\s+(?:[\w.]+\s+)*(void|half|i\d+)\s+@([A-Za-z0-9_]+)\s*\(([^)]*)\)\s*(?:[^{}]*)\{',
                line,
            )
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
            dbg_match = re.search(r'!dbg\s+(!\d+)', line)
            dbg_id = dbg_match.group(1) if dbg_match else None
            cur = {
                "name": name,
                "rettype": rettype,
                "retbits": retbits,
                "args": args.split(",") if args.strip() else [],
                "blocks": [],
            }
            if dbg_id:
                cur["dbg"] = dbg_id
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
                bb = {"label": label, "ins": [], "dbg_refs": []}
                cur["blocks"].append(bb)
                continue
        if line.endswith(":") and not line.startswith(";"):
            label = line[:-1]
            bb = {"label": label, "ins": [], "dbg_refs": []}
            cur["blocks"].append(bb)
            continue
        if line == "}":
            cur = None
            bb = None
            continue
        if bb is None:
            bb = {"label": "entry", "ins": [], "dbg_refs": []}
            cur["blocks"].append(bb)
        dbg_match = re.search(r'!dbg\s+(!\d+)', line)
        dbg_id = dbg_match.group(1) if dbg_match else None
        bb["ins"].append(line)
        bb.setdefault("dbg_refs", []).append(dbg_id)

    debug_functions: List[Dict[str, Any]] = []
    for fn in ir["functions"]:
        dbg_id = fn.get("dbg")
        if not dbg_id:
            continue
        sub = debug_subprograms.get(dbg_id)
        if not sub:
            continue
        file_info = debug_files.get(sub.get("file"))
        debug_entry = {
            "function": fn["name"],
            "subprogram": dbg_id,
            "name": sub.get("name") or fn["name"],
            "linkage_name": sub.get("linkage_name"),
            "file": file_info,
            "line": sub.get("line"),
        }
        debug_functions.append(debug_entry)

    ir["debug"] = {
        "files": debug_files,
        "subprograms": debug_subprograms,
        "locations": debug_locations,
        "lexical_blocks": debug_lexical_blocks,
        "locals": debug_locals,
        "expressions": debug_expressions,
        "functions": debug_functions,
    }
    return ir


def compute_type_layout(
    type_expr: str,
    type_defs: Dict[str, str],
    cache: Optional[Dict[str, Tuple[int, int]]] = None,
) -> Tuple[int, int]:
    key = type_expr.strip()
    if cache is None:
        cache = {}
    cached = cache.get(key)
    if cached:
        return cached

    # Named type indirection
    if key.startswith('%'):
        body = type_defs.get(key)
        if body is None:
            result = (1, 1)
        else:
            result = compute_type_layout(body, type_defs, cache)
        cache[key] = result
        return result

    # Handle "type { ... }" bodies that may still include the keyword
    if key.startswith('type '):
        result = compute_type_layout(key[5:], type_defs, cache)
        cache[key] = result
        return result

    # Struct/union-like aggregates
    if key.startswith('{') and key.endswith('}'):
        inner = key[1:-1].strip()
        if not inner:
            result = (0, 1)
        else:
            fields = _split_top_level(inner)
            offset = 0
            max_align = 1
            for field in fields:
                field_size, field_align = compute_type_layout(field, type_defs, cache)
                offset = _align_to(offset, field_align)
                offset += field_size
                max_align = max(max_align, field_align)
            size = _align_to(offset, max_align)
            result = (size, max_align)
        cache[key] = result
        return result

    # Arrays
    if key.startswith('[') and key.endswith(']'):
        m = re.match(r'\[(\d+)\s+x\s+(.+)\]', key)
        if m:
            count = int(m.group(1))
            elem_expr = m.group(2).strip()
            elem_size, elem_align = compute_type_layout(elem_expr, type_defs, cache)
            stride = _align_to(elem_size, elem_align)
            size = stride * count
            result = (size, elem_align)
            cache[key] = result
            return result

    # Vectors (treat like packed arrays)
    if key.startswith('<') and key.endswith('>'):
        m = re.match(r'<(\d+)\s+x\s+(.+)>', key)
        if m:
            count = int(m.group(1))
            elem_expr = m.group(2).strip()
            elem_size, elem_align = compute_type_layout(elem_expr, type_defs, cache)
            size = elem_size * count
            result = (size, elem_align)
            cache[key] = result
            return result

    # Pointer types
    if key == 'ptr' or key.startswith('ptr ') or key.endswith('*') or 'addrspace' in key and '*' in key:
        result = (4, 4)
        cache[key] = result
        return result

    scalar_map = {
        'void': (0, 1),
        'i1': (1, 1),
        'i8': (1, 1),
        'i16': (2, 2),
        'i32': (4, 4),
        'i64': (8, 8),
        'half': (2, 2),
        'float': (4, 4),
        'double': (8, 8),
    }
    if key in scalar_map:
        result = scalar_map[key]
        cache[key] = result
        return result

    if key.startswith('i') and key[1:].isdigit():
        bits = int(key[1:])
        size = max(1, (bits + 7) // 8)
        if bits <= 8:
            align = 1
        elif bits <= 16:
            align = 2
        elif bits <= 32:
            align = 4
        else:
            align = 8
        result = (size, align)
        cache[key] = result
        return result

    # Fallback: treat as word-sized
    result = (4, 4)
    cache[key] = result
    return result

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
    return _combine_ldi_movs_core(lines)[0]


def _combine_ldi_movs_core(
    lines: List[str],
    tags: Optional[List[Optional[Any]]] = None,
) -> Tuple[List[str], Optional[List[Optional[Any]]]]:
    work = list(lines)
    work_tags = list(tags) if tags is not None else None
    while True:
        result: List[str] = []
        result_tags: Optional[List[Optional[Any]]] = [] if work_tags is not None else None
        changed = False
        i = 0
        label_positions = build_label_positions(work)
        while i < len(work):
            line = work[i]
            stripped = line.strip()
            current_tag = work_tags[i] if work_tags is not None else None
            if not is_instruction_line(line):
                result.append(line)
                if result_tags is not None:
                    result_tags.append(current_tag)
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
                                if result_tags is not None:
                                    new_tag = work_tags[next_idx] if work_tags is not None else None
                                    if new_tag is None:
                                        new_tag = current_tag
                                    result_tags.append(new_tag)
                                for rel_idx, filler in enumerate(work[i + 1:next_idx], start=1):
                                    result.append(filler)
                                    if result_tags is not None and work_tags is not None:
                                        result_tags.append(work_tags[i + rel_idx])
                                i = next_idx + 1
                                changed = True
                                continue
            result.append(line)
            if result_tags is not None:
                result_tags.append(current_tag)
            i += 1
        if not changed:
            return result, result_tags
        work = result
        work_tags = result_tags


def find_last_instruction(lines: List[str]):
    for line in reversed(lines):
        if not is_instruction_line(line):
            continue
        match = MOV_RE.match(line.strip())
        if match:
            return ('MOV', match.group(1).upper(), match.group(2).upper())
            return ('OTHER', None, None)
    return None


def pop_last_instruction(lines: List[str], tags: Optional[List[Optional[Any]]] = None) -> None:
    for idx in range(len(lines) - 1, -1, -1):
        if is_instruction_line(lines[idx]):
            lines.pop(idx)
            if tags is not None:
                tags.pop(idx)
            return


def _eliminate_mov_chains_core(
    lines: List[str],
    tags: Optional[List[Optional[Any]]] = None,
) -> Tuple[List[str], Optional[List[Optional[Any]]]]:
    label_positions = build_label_positions(lines)
    result: List[str] = []
    result_tags: Optional[List[Optional[Any]]] = [] if tags is not None else None
    last_instr = None
    for idx, line in enumerate(lines):
        stripped = line.strip()
        current_tag = tags[idx] if tags is not None else None
        if not is_instruction_line(line):
            result.append(line)
            if result_tags is not None:
                result_tags.append(current_tag)
            continue
        mov_match = MOV_RE.match(stripped)
        if mov_match:
            dst = mov_match.group(1).upper()
            src = mov_match.group(2).upper()
            if dst == src and not is_return_mov(lines, idx):
                continue
            if dst == R_RET and is_return_mov(lines, idx):
                result.append(f"MOV {dst}, {src}")
                if result_tags is not None:
                    result_tags.append(current_tag)
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
                    pop_last_instruction(result, result_tags)
                    last_instr = find_last_instruction(result)
                    if last_instr and len(last_instr) == 3:
                        last_instr = last_instr + (None,)
                    src = prev_src
                    if dst == src:
                        continue
            result.append(f"MOV {dst}, {src}")
            if result_tags is not None:
                result_tags.append(current_tag)
            last_instr = ('MOV', dst, src, idx)
            continue
        result.append(line)
        if result_tags is not None:
            result_tags.append(current_tag)
        last_instr = ('OTHER', None, None, idx)
    return result, result_tags


def eliminate_mov_chains(lines: List[str]) -> List[str]:
    return _eliminate_mov_chains_core(lines)[0]


def optimize_movs(lines: List[str]) -> List[str]:
    return _optimize_movs(lines)[0]


def _optimize_movs(
    lines: List[str],
    tags: Optional[List[Optional[Any]]] = None,
) -> Tuple[List[str], Optional[List[Optional[Any]]]]:
    if not lines:
        empty_tags: Optional[List[Optional[Any]]] = [] if tags is not None else None
        return [], empty_tags
    if tags is not None and len(tags) != len(lines):
        raise ValueError("optimize_movs tag length mismatch")
    stage1_lines, stage1_tags = _combine_ldi_movs_core(list(lines), list(tags) if tags is not None else None)
    stage2_lines, stage2_tags = _eliminate_mov_chains_core(stage1_lines, stage1_tags)
    return stage2_lines, stage2_tags

def lower_function(
    fn: Dict,
    trace=False,
    imports=None,
    defined=None,
    global_symbols=None,
    type_info=None,
    debug_info=None,
) -> List[str]:
    asm: List[str] = []
    vmap: Dict[str, str] = {}
    if imports is None:
        imports = set()
    if defined is None:
        defined = set()

    type_defs = type_info or {}
    type_layout_cache: Dict[str, Tuple[int, int]] = {}
    debug_info = debug_info or {}
    debug_files: Dict[str, Dict[str, Any]] = debug_info.get("files", {})
    debug_subprograms: Dict[str, Dict[str, Any]] = debug_info.get("subprograms", {})
    debug_lexical_blocks: Dict[str, Dict[str, Any]] = debug_info.get("lexical_blocks", {})
    debug_locals: Dict[str, Dict[str, Any]] = debug_info.get("locals", {})
    debug_expressions: Dict[str, Dict[str, Any]] = debug_info.get("expressions", {})
    function_dbg_id: Optional[str] = fn.get("dbg")

    def scope_belongs_to_function(scope_id: Optional[str]) -> bool:
        if not function_dbg_id or not scope_id:
            return False
        current = scope_id
        visited: Set[str] = set()
        while current and current not in visited:
            if current == function_dbg_id:
                return True
            visited.add(current)
            block = debug_lexical_blocks.get(current)
            if block:
                current = block.get("scope")
                continue
            sub = debug_subprograms.get(current)
            if sub:
                current = sub.get("scope")
                continue
            current = None
        return False

    tracked_variables: Dict[str, Dict[str, Any]] = {}
    if function_dbg_id:
        for var_id, var_meta in debug_locals.items():
            if scope_belongs_to_function(var_meta.get("scope")):
                tracked_variables[var_id] = var_meta
    variable_states: Dict[str, Dict[str, Any]] = {}

    def _extract_metadata_payload(text: Optional[str]) -> str:
        if not text:
            return ""
        payload = text.strip()
        if payload.startswith("metadata"):
            payload = payload[len("metadata"):].strip()
        return payload

    def _resolve_expression_ops(expr_token: Optional[str]) -> List[Any]:
        payload = _extract_metadata_payload(expr_token)
        if not payload:
            return []
        if payload.startswith("!DIExpression"):
            parsed = _parse_diexpression(payload, payload)
            return parsed.get("ops", []) if parsed else []
        if payload.startswith("!"):
            parsed = debug_expressions.get(payload)
            if parsed:
                return parsed.get("ops", [])
        return []

    def _pointer_offset_from_ops(ops: List[Any]) -> Tuple[int, bool]:
        extra = 0
        deref = False
        idx = 0
        total = len(ops)
        while idx < total:
            op = ops[idx]
            if op == "DW_OP_deref":
                deref = True
                idx += 1
                continue
            if op == "DW_OP_plus_uconst":
                if idx + 1 < total:
                    val = ops[idx + 1]
                    if isinstance(val, int):
                        extra += val
                idx += 2
                continue
            break
        return extra, deref

    def _stack_location_from_pointer(ptr: str, extra: int = 0) -> Optional[Dict[str, Any]]:
        canonical = resolve_name(ptr)
        if canonical in frame_ptr_offsets:
            return {"kind": "stack", "offset": frame_ptr_offsets[canonical] + extra}
        if canonical in spill_slots:
            return {"kind": "stack", "offset": spill_slots[canonical] + extra}
        return None

    def _resolve_value_location(value_token: str, ops: List[Any]) -> Optional[Dict[str, Any]]:
        token = value_token.strip()
        extra, deref = _pointer_offset_from_ops(ops)
        if not token:
            return None
        if token.startswith('%'):
            canonical = resolve_name(token)
            if deref:
                loc = _stack_location_from_pointer(token, extra)
                if loc:
                    return loc
            reg = vmap.get(canonical)
            if reg:
                return {"kind": "register", "name": reg}
            spilled = spilled_values.get(canonical)
            if spilled:
                slot_offset, stored_type = spilled
                loc = {"kind": "stack", "offset": slot_offset + extra}
                size_val = type_size(stored_type)
                if size_val:
                    loc["size"] = size_val
                return loc
            if canonical in frame_ptr_offsets:
                return {"kind": "stack", "offset": frame_ptr_offsets[canonical] + extra}
            return None
        if token.startswith('@'):
            symbol_name = token[1:]
            return {"kind": "global", "symbol": symbol_name, "offset": extra}
        lowered = token.lower()
        if lowered in {"null", "undef"}:
            return {"kind": "const", "value": 0}
        if lowered == "true":
            return {"kind": "const", "value": 1}
        if lowered == "false":
            return {"kind": "const", "value": 0}
        try:
            return {"kind": "const", "value": int(token, 0)}
        except ValueError:
            return None

    def _current_line_hint() -> int:
        hint = len(asm) - 1
        if hint < 0:
            hint = 0
        return hint

    def _record_variable_event(var_id: str, location: Optional[Dict[str, Any]], reason: str) -> None:
        if not location or var_id not in tracked_variables:
            return
        loc_copy = dict(location)
        state = variable_states.setdefault(var_id, {"events": [], "last_location": None})
        if state.get("last_location") == loc_copy:
            return
        event = {
            "location": loc_copy,
            "line_index": _current_line_hint(),
            "reason": reason,
        }
        state["events"].append(event)
        state["last_location"] = loc_copy

    def _parse_value_operand(text: str) -> Dict[str, Optional[str]]:
        payload = _extract_metadata_payload(text)
        if not payload:
            return {"type": None, "token": None}
        parts = payload.split(None, 1)
        if len(parts) == 1:
            return {"type": None, "token": parts[0]}
        return {"type": parts[0], "token": parts[1]}

    def _parse_metadata_id(text: str) -> Optional[str]:
        payload = _extract_metadata_payload(text)
        if payload.startswith('!'):
            return payload
        return None

    def _pointer_token(text: str) -> Optional[str]:
        payload = _extract_metadata_payload(text)
        if not payload:
            return None
        parts = payload.split()
        if not parts:
            return None
        return parts[-1]

    def _split_dbg_args(line: str) -> List[str]:
        start = line.find('(')
        end = line.rfind(')')
        if start == -1 or end == -1 or end <= start:
            return []
        return _split_top_level(line[start + 1 : end])

    def _handle_dbg_declare(line: str) -> bool:
        args = _split_dbg_args(line)
        if len(args) < 2:
            return True
        var_id = _parse_metadata_id(args[1])
        if not var_id:
            return True
        ptr_token = _pointer_token(args[0])
        expr_ops = _resolve_expression_ops(args[2] if len(args) >= 3 else None)
        extra_offset, _ = _pointer_offset_from_ops(expr_ops)
        location: Optional[Dict[str, Any]] = None
        if ptr_token and ptr_token.startswith('%'):
            location = _stack_location_from_pointer(ptr_token, extra_offset)
        elif ptr_token and ptr_token.startswith('@'):
            location = {"kind": "global", "symbol": ptr_token[1:], "offset": extra_offset}
        if location:
            _record_variable_event(var_id, location, "declare")
        return True

    def _handle_dbg_value(line: str) -> bool:
        args = _split_dbg_args(line)
        if len(args) < 2:
            return True
        var_id = _parse_metadata_id(args[1])
        if not var_id:
            return True
        value_info = _parse_value_operand(args[0])
        token = value_info.get("token")
        expr_ops = _resolve_expression_ops(args[2] if len(args) >= 3 else None)
        if token:
            location = _resolve_value_location(token, expr_ops)
            _record_variable_event(var_id, location, "value")
        return True


    asm.append(f"; -- function {fn['name']} --")

    line_debug_entries: List[Tuple[int, Optional[str], str]] = []
    instruction_records: List[Dict[str, Any]] = []
    inst_counter = 0

    use_counts: Dict[str, int] = defaultdict(int)
    use_positions: Dict[str, List[int]] = defaultdict(list)
    instruction_index = 0
    for block in fn["blocks"]:
        for raw in block["ins"]:
            norm = normalize_ir_line(raw)
            if norm.startswith("call void @llvm.dbg."):
                continue
            phi_match = re.match(r'(%[A-Za-z0-9_]+)\s*=\s*phi', norm)
            if phi_match:
                incoming = re.findall(r'\[\s*([^,]+),\s*%([A-Za-z0-9_]+)\s*\]', norm)
                for val, _ in incoming:
                    val = val.strip()
                    if val.startswith('%'):
                        use_counts[val] += 1
                        use_positions[val].append(instruction_index)
                instruction_index += 1
                continue
            dest_match = re.match(r'(%[A-Za-z0-9_]+)\s*=', norm)
            dest = dest_match.group(1) if dest_match else None
            cleaned = re.sub(r'label\s+%[A-Za-z0-9_]+', '', norm)
            for tok in re.findall(r'%[A-Za-z0-9_]+', cleaned):
                if tok == dest:
                    continue
                use_counts[tok] += 1
                use_positions[tok].append(instruction_index)
            instruction_index += 1

    future_use_positions: Dict[str, deque[int]] = {
        name: deque(indices) for name, indices in use_positions.items()
    }
    AVAILABLE_REGS = ["R4", "R5", "R6", "R8", "R9", "R10", "R11"]
    free_regs: List[str] = AVAILABLE_REGS.copy()
    value_types: Dict[str, str] = {}
    overflow_pairs: Dict[str, Dict[str, str]] = {}
    spilled_values: Dict[str, Tuple[str, str]] = {}
    spill_slots: Dict[str, int] = {}
    spill_data_lines: List[str] = []
    frame_ptr_offsets: Dict[str, int] = {}
    frame_size = 0
    frame_committed = 0
    pinned_values = set()
    pinned_registers: Dict[str, str] = {}
    reg_lru: List[str] = []
    spilled_float_alias = set()
    allocation_stats: Dict[str, Any] = {
        "max_pressure": 0,
        "spill_count": 0,
        "reload_count": 0,
        "proactive_splits": 0,
    }
    used_registers: Set[str] = set()

    def record_pressure() -> None:
        active = len(AVAILABLE_REGS) - len(free_regs)
        if active > allocation_stats["max_pressure"]:
            allocation_stats["max_pressure"] = active

    def next_use_for(name: str) -> float:
        queue = future_use_positions.get(name)
        if not queue:
            return math.inf
        return float(queue[0])

    def mark_used(name: str) -> None:
        if name in reg_lru:
            reg_lru.remove(name)
        reg_lru.append(name)

    label_map = {}
    for block in fn["blocks"]:
        orig = block["label"]
        unique = f"{fn['name']}__{orig}"
        counter = 2
        while unique in label_map.values():
            unique = f"{fn['name']}__{orig}_{counter}"
            counter += 1
        label_map[orig] = unique

    is_first_block = True
    prologue_emitted = False
    temp_label_counter = 0

    def new_label(tag: str) -> str:
        nonlocal temp_label_counter
        temp_label_counter += 1
        return f"{fn['name']}__{tag}_{temp_label_counter}"

    def canonical_type(type_name: Optional[str]) -> str:
        if not type_name:
            return 'i32'
        return type_name

    def type_layout_info(type_name: Optional[str]) -> Tuple[int, int]:
        return compute_type_layout(canonical_type(type_name), type_defs, type_layout_cache)

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
        size, _ = type_layout_info(type_name)
        if size <= 1:
            return 'byte'
        if size == 2:
            return 'half'
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
        size, _ = type_layout_info(type_name)
        return size

    def type_alignment(type_name: Optional[str]) -> int:
        _, align = type_layout_info(type_name)
        return max(align, 1)

    # Map arguments (if any) to R1..R3 (MVP ignores types)
    arg_regs = {}
    initial_float_alias = {}
    stack_args: List[Tuple[str, int, str]] = []
    for i, a in enumerate(fn["args"]):
        arg = a.strip()
        if not arg:
            continue
        m = re.search(r'%([A-Za-z0-9_]+)$', arg)
        if not m:
            continue
        name = "%" + m.group(1)
        arg_type_token = arg.split()[0] if arg else ''
        val_type = deduce_value_type(arg_type_token)
        if i < len(ARG_REGS):
            reg = ARG_REGS[i]
            vmap[name] = reg
            arg_regs[name] = reg
            value_types[name] = val_type
            if val_type == 'float':
                initial_float_alias[name] = reg
            mark_used(name)
        else:
            value_types[name] = val_type
            stack_offset = 4 * (i - len(ARG_REGS) + 1)
            stack_args.append((name, stack_offset, val_type))

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
        best_name: Optional[str] = None
        best_next_use = -1.0
        best_lru_pos = len(reg_lru) + 1
        for idx, name in enumerate(reg_lru):
            if name in blocked or name in pinned_values:
                continue
            reg = vmap.get(name)
            if not reg or reg not in AVAILABLE_REGS:
                continue
            next_use_val = next_use_for(name)
            # Prefer values with no future use (next_use == inf), otherwise farthest use.
            if (
                next_use_val > best_next_use
                or (next_use_val == best_next_use and idx < best_lru_pos)
            ):
                best_name = name
                best_next_use = next_use_val
                best_lru_pos = idx
        return best_name

    def align_up(value: int, alignment: int) -> int:
        if alignment <= 0:
            alignment = 1
        return ((value + alignment - 1) // alignment) * alignment

    def format_stack_offset(offset: int) -> str:
        if offset < 0:
            return f"+-{abs(offset)}"
        return f"+{offset}"

    def ensure_frame_capacity(target_bytes: int) -> None:
        nonlocal frame_committed
        while frame_committed < target_bytes:
            asm.append("PUSH R12")
            frame_committed += 4

    def allocate_frame_slot_bytes(size: int, align: int) -> int:
        nonlocal frame_size
        eff_align = max(align, 4)
        size = align_up(size, 4)
        frame_size = align_up(frame_size, eff_align)
        frame_size += size
        frame_size = align_up(frame_size, eff_align)
        ensure_frame_capacity(frame_size)
        return -frame_size

    def record_frame_slot(name: str, val_type: str, align: int) -> int:
        if name in spill_slots:
            return spill_slots[name]
        slot_size = type_size(val_type)
        offset = allocate_frame_slot_bytes(slot_size, align)
        spill_slots[name] = offset
        return offset

    def spill_value(name: str, *, proactive: bool = False) -> None:
        reg = vmap.get(name)
        if not reg or reg not in AVAILABLE_REGS:
            return
        val_type = value_types.get(name, 'i32')
        slot_offset = record_frame_slot(name, val_type, 4)
        store_instr = type_to_store_instr(val_type)
        asm.append(f"{store_instr} [R7{format_stack_offset(slot_offset)}], {reg}")
        allocation_stats["spill_count"] += 1
        if proactive:
            allocation_stats["proactive_splits"] += 1
        vmap.pop(name, None)
        add_free_reg(reg)
        if name in reg_lru:
            reg_lru.remove(name)
        if name in float_alias:
            spilled_float_alias.add(name)
        float_alias.pop(name, None)
        spilled_values[name] = (slot_offset, val_type)

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
        canonical = resolve_name(name)
        val_type = canonical_type(val_type or value_types.get(canonical))
        value_types[canonical] = val_type
        if canonical in pinned_registers:
            reg = pinned_registers[canonical]
            if canonical not in vmap:
                vmap[canonical] = reg
            mark_used(canonical)
            used_registers.add(reg)
            return reg
        if canonical in vmap:
            mark_used(canonical)
            reg = vmap[canonical]
            used_registers.add(reg)
            return reg
        if canonical in spilled_values:
            ensure_register_available({canonical})
            reg = free_regs.pop(0)
            record_pressure()
            vmap[canonical] = reg
            mark_used(canonical)
            slot_offset, stored_type = spilled_values.pop(canonical)
            value_types[canonical] = stored_type
            load_instr = type_to_load_instr(stored_type)
            asm.append(f"{load_instr} {reg}, [R7{format_stack_offset(slot_offset)}]")
            if canonical in spilled_float_alias:
                float_alias[canonical] = reg
                spilled_float_alias.remove(canonical)
            allocation_stats["reload_count"] += 1
            used_registers.add(reg)
            return reg
        ensure_register_available({canonical})
        reg = free_regs.pop(0)
        record_pressure()
        vmap[canonical] = reg
        mark_used(canonical)
        if canonical in spilled_float_alias:
            float_alias[canonical] = reg
            spilled_float_alias.remove(canonical)
        used_registers.add(reg)
        return reg

    def ensure_value_in_reg(name: str) -> str:
        canonical = resolve_name(name)
        if canonical in vmap:
            mark_used(canonical)
            return vmap[canonical]
        if canonical in spilled_values:
            return alloc_vreg(canonical, value_types.get(canonical))
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

    def resolve_name(name: str) -> str:
        return name

    def materialize(value: str, tmp: str) -> str:
        value = value.strip()
        if value.startswith('%'):
            value = resolve_name(value)
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
        queue = future_use_positions.get(name)
        if queue:
            queue.popleft()
            if not queue:
                future_use_positions.pop(name, None)
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
        value = resolve_name(value)
        if value in vmap or value in spilled_values:
            reg = ensure_value_in_reg(value)
            consume_use(value)
            return reg
        if value in frame_ptr_offsets:
            offset = frame_ptr_offsets[value]
            reg = alloc_vreg(value, 'ptr')
            asm.append(f"MOV {reg}, R7")
            if offset != 0:
                load_const('R14', offset)
                asm.append(f"ADD {reg}, {reg}, R14")
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
        canonical = resolve_name(value) if value.startswith('%') else value
        if canonical in float_alias:
            reg = float_alias[canonical]
            if canonical not in vmap or vmap[canonical] != reg:
                reg = ensure_value_in_reg(canonical)
            consume_use(canonical)
            return reg
        hmatch = re.match(r'0xH([0-9A-Fa-f]+)', value)
        if hmatch:
            bits = int(hmatch.group(1), 16)
            load_const(tmp, bits)
            return tmp
        if value.startswith('%'):
            reg = ensure_value_in_reg(canonical)
            consume_use(canonical)
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
        frame_ptr_offsets.pop(name, None)

    def maybe_split_long_lived(current_index: int) -> None:
        if not ENABLE_PROACTIVE_SPLIT or SPLIT_DISTANCE_THRESHOLD <= 0:
            return
        for name in list(vmap.keys()):
            if name in pinned_values:
                continue
            if name not in future_use_positions:
                continue
            next_use_val = next_use_for(name)
            if math.isinf(next_use_val):
                continue
            if next_use_val - current_index >= SPLIT_DISTANCE_THRESHOLD:
                spill_value(name, proactive=True)

    def try_coalesce_value(dest: str, value: str, dest_type: str) -> bool:
        value = value.strip()
        if not ENABLE_COALESCE:
            return False
        if not value.startswith('%'):
            return False
        canonical = resolve_name(value)
        if canonical in pinned_values:
            return False
        reg = vmap.get(canonical)
        if not reg:
            return False
        if use_counts.get(canonical, 0) > 1:
            return False
        use_counts.pop(canonical, None)
        future_use_positions.pop(canonical, None)
        pinned_registers.pop(canonical, None)
        pinned_values.discard(canonical)
        if canonical in reg_lru:
            reg_lru.remove(canonical)
        vmap.pop(canonical, None)
        alias_reg = float_alias.pop(canonical, None)
        if alias_reg is not None:
            float_alias[dest] = alias_reg
        spilled_float_alias.discard(canonical)
        spill_entry = spilled_values.pop(canonical, None)
        if spill_entry is not None:
            spilled_values[dest] = spill_entry
        frame_slot = frame_ptr_offsets.pop(canonical, None)
        if frame_slot is not None:
            frame_ptr_offsets[dest] = frame_slot
        value_types[dest] = dest_type
        vmap[dest] = reg
        mark_used(dest)
        used_registers.add(reg)
        return True

    def emit_stack_teardown() -> None:
        if frame_committed > 0:
            words = frame_committed // 4
            for _ in range(words):
                asm.append("POP R12")
        asm.append("POP R7")

    for block in fn["blocks"]:
        remaining_ins: List[str] = []
        remaining_dbg: List[Optional[str]] = []
        dbg_refs = block.get("dbg_refs", [])
        for idx_ins, raw in enumerate(block["ins"]):
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
            else:
                remaining_ins.append(raw)
                dbg_id = dbg_refs[idx_ins] if idx_ins < len(dbg_refs) else None
                remaining_dbg.append(dbg_id)
        block["ins"] = remaining_ins
        block["dbg_refs"] = remaining_dbg

    def apply_phi_moves(pred_label: str, succ_label: str) -> None:
        moves = phi_moves.get((pred_label, succ_label))
        if not moves:
            return
        for dest, value in moves:
            clear_alias(dest)
            dest_type = phi_types.get(dest, value_types.get(dest, 'i32'))
            if not try_coalesce_value(dest, value, dest_type):
                dest_reg = alloc_vreg(dest, dest_type)
                src_reg = resolve_operand(value, dest_reg)
                if dest_reg != src_reg:
                    asm.append(f"MOV {dest_reg}, {src_reg}")
            maybe_release(dest)

    def _lower_ir_instruction(raw_line: str, block_label: str) -> str:
            orig_line = raw_line
            stripped_line = orig_line.strip()
            if not stripped_line:
                return None
            if stripped_line.startswith("#dbg_declare"):
                _handle_dbg_declare(stripped_line)
                return None
            if stripped_line.startswith("#dbg_value"):
                _handle_dbg_value(stripped_line)
                return None
            if stripped_line.startswith("#dbg"):
                return None
            if stripped_line.startswith("call void @llvm.dbg.declare"):
                _handle_dbg_declare(stripped_line)
                return None
            if stripped_line.startswith("call void @llvm.dbg.value"):
                _handle_dbg_value(stripped_line)
                return None
            line = normalize_ir_line(raw_line)
            if trace: asm.append(f"; IR: {orig_line}")
            m = re.match(r'(%[A-Za-z0-9_]+)\s*=\s*alloca\s+([^,]+)', line)
            if m:
                slot, elem_type = m.groups()
                elem_type = elem_type.strip()
                value_types[slot] = 'ptr'
                align_match = re.search(r'align\s+(\d+)', line)
                align_val = int(align_match.group(1)) if align_match else type_alignment(elem_type)
                slot_size = type_size(elem_type)
                if slot_size <= 0:
                    slot_size = max(align_val, 1)
                offset = allocate_frame_slot_bytes(slot_size, align_val)
                frame_ptr_offsets[slot] = offset
                rd = alloc_vreg(slot, 'ptr')
                asm.append(f"MOV {rd}, R7")
                if offset != 0:
                    load_const('R14', offset)
                    asm.append(f"ADD {rd}, {rd}, R14")
                maybe_release(slot)
                return line

            if line.startswith("ret "):
                if " i32 " in line and "%" in line:
                    m = re.search(r'ret\s+i32\s+(%[A-Za-z0-9_]+)', line)
                    if not m:
                        raise ISelError("Unsupported ret: " + orig_line)
                    v = m.group(1)
                    r = ensure_value_in_reg(v)
                    consume_use(v)
                    if r != R_RET:
                        asm.append(f"MOV {R_RET}, {r}")
                elif re.match(r'ret\s+i32\s+[-]?\d+', line):
                    imm = int(line.split()[-1])
                    asm.append(f"LDI {R_RET}, {imm}")
                elif line.startswith("ret half "):
                    value = line.split(" ", 2)[2]
                    src_reg = resolve_operand(value, R_RET)
                    if src_reg != R_RET:
                        asm.append(f"MOV {R_RET}, {src_reg}")
                elif re.match(r'ret\s+i1\s+(%[A-Za-z0-9_]+)', line):
                    m = re.search(r'ret\s+i1\s+(%[A-Za-z0-9_]+)', line)
                    if not m:
                        raise ISelError("Unsupported ret: " + orig_line)
                    v = m.group(1)
                    r = ensure_value_in_reg(v)
                    consume_use(v)
                    if r != R_RET:
                        asm.append(f"MOV {R_RET}, {r}")
                elif re.match(r'ret\s+i1\s+[-]?\d+', line):
                    imm = int(line.split()[-1]) & 0x1
                    asm.append(f"LDI {R_RET}, {imm}")
                elif re.match(r'ret\s+i16\s+(%[A-Za-z0-9_]+)', line):
                    value = line.split()[-1]
                    src_reg = resolve_operand(value, R_RET)
                    if src_reg != R_RET:
                        asm.append(f"MOV {R_RET}, {src_reg}")
                elif re.match(r'ret\s+void', line):
                    pass
                else:
                    raise ISelError("Unsupported ret form: " + orig_line)
                emit_stack_teardown()
                asm.append("RET")
                return line

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
                return line

            m = re.match(r'(%[A-Za-z0-9_]+)\s*=\s*shl\s+i32\s+([^,]+),\s*([^,]+)', line)
            if m:
                dst, lhs, rhs = m.groups()
                clear_alias(dst)
                value_types[dst] = 'i32'
                rd = alloc_vreg(dst, 'i32')
                ra = materialize(lhs, "R12")
                rb = materialize(rhs, "R13")
                asm.append(f"LSL {rd}, {ra}, {rb}")
                maybe_release(dst)
                return line

            m = re.match(r'(%[A-Za-z0-9_]+)\s*=\s*lshr\s+i32\s+([^,]+),\s*([^,]+)', line)
            if m:
                dst, lhs, rhs = m.groups()
                clear_alias(dst)
                value_types[dst] = 'i32'
                rd = alloc_vreg(dst, 'i32')
                ra = materialize(lhs, "R12")
                rb = materialize(rhs, "R13")
                asm.append(f"LSR {rd}, {ra}, {rb}")
                maybe_release(dst)
                return line

            m = re.match(r'(%[A-Za-z0-9_]+)\s*=\s*ashr\s+i32\s+([^,]+),\s*([^,]+)', line)
            if m:
                dst, lhs, rhs = m.groups()
                clear_alias(dst)
                value_types[dst] = 'i32'
                rd = alloc_vreg(dst, 'i32')
                ra = materialize(lhs, "R12")
                rb = materialize(rhs, "R13")
                asm.append(f"ASR {rd}, {ra}, {rb}")
                maybe_release(dst)
                return line

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
                return line

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
                return line

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
                return line

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
                return line

            m = re.match(r'(%[A-Za-z0-9_]+)\s*=\s*fptosi\s+half\s+(%[A-Za-z0-9_]+)\s+to\s+i32', line)
            if m:
                dst, src = m.groups()
                clear_alias(dst)
                rs = resolve_operand(src, "R12")
                rd = alloc_vreg(dst, 'i32')
                asm.append(f"F2I {rd}, {rs}")
                maybe_release(dst)
                return line

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
                return line

            m = re.match(r'(%[A-Za-z0-9_.]+)\s*=\s*call\s+\{\s*i32\s*,\s*i1\s*\}\s+@llvm\.uadd\.with\.overflow\.i32\(\s*i32\s+([^,]+),\s*i32\s+([^)]*)\)', line)
            if m:
                dst, lhs, rhs = m.groups()
                lhs = lhs.strip()
                rhs = rhs.strip()
                sum_name = f"{dst}__sum"
                carry_name = f"{dst}__carry"
                overflow_pairs[dst] = {"value": sum_name, "flag": carry_name, "kind": "uadd"}
                value_types[sum_name] = 'i32'
                value_types[carry_name] = 'i32'
                ra = materialize(lhs, "R12")
                rb = materialize(rhs, "R13")
                rd_sum = alloc_vreg(sum_name, 'i32')
                asm.append(f"ADD {rd_sum}, {ra}, {rb}")
                zero_name = f"{dst}__carry_seed"
                value_types[zero_name] = 'i32'
                rd_zero = alloc_vreg(zero_name, 'i32')
                asm.append(f"LDI {rd_zero}, 0")
                rd_carry = alloc_vreg(carry_name, 'i32')
                asm.append(f"ADC {rd_carry}, {rd_zero}, {rd_zero}")
                maybe_release(zero_name)
                return line

            m = re.match(r'(%[A-Za-z0-9_.]+)\s*=\s*call\s+\{\s*i32\s*,\s*i1\s*\}\s+@llvm\.usub\.with\.overflow\.i32\(\s*i32\s+([^,]+),\s*i32\s+([^)]*)\)', line)
            if m:
                dst, lhs, rhs = m.groups()
                lhs = lhs.strip()
                rhs = rhs.strip()
                diff_name = f"{dst}__diff"
                flag_name = f"{dst}__borrow"
                overflow_pairs[dst] = {"value": diff_name, "flag": flag_name, "kind": "usub"}
                value_types[diff_name] = 'i32'
                value_types[flag_name] = 'i32'
                ra = materialize(lhs, "R12")
                rb = materialize(rhs, "R13")
                rd_diff = alloc_vreg(diff_name, 'i32')
                asm.append(f"SUB {rd_diff}, {ra}, {rb}")
                zero_name = f"{dst}__borrow_seed"
                value_types[zero_name] = 'i32'
                rd_zero = alloc_vreg(zero_name, 'i32')
                asm.append(f"LDI {rd_zero}, 0")
                borrow_tmp = f"{dst}__borrow_tmp"
                value_types[borrow_tmp] = 'i32'
                rd_tmp = alloc_vreg(borrow_tmp, 'i32')
                asm.append(f"SBC {rd_tmp}, {rd_zero}, {rd_zero}")
                shift_name = f"{dst}__borrow_shift"
                value_types[shift_name] = 'i32'
                rd_shift = alloc_vreg(shift_name, 'i32')
                load_const(rd_shift, 31)
                rd_flag = alloc_vreg(flag_name, 'i32')
                asm.append(f"LSR {rd_flag}, {rd_tmp}, {rd_shift}")
                maybe_release(zero_name)
                maybe_release(borrow_tmp)
                maybe_release(shift_name)
                return line

            m = re.match(r'(%[A-Za-z0-9_.]+)\s*=\s*extractvalue\s+\{\s*i32\s*,\s*i1\s*\}\s+(%[A-Za-z0-9_.]+),\s*(\d+)', line)
            if m:
                dst, src, idx = m.groups()
                pair = overflow_pairs.get(src)
                if not pair:
                    raise ISelError(f"extractvalue from unsupported value {src}")
                if idx == '0':
                    alias = pair["value"]
                    value_types[dst] = value_types.get(alias, 'i32')
                    if not try_coalesce_value(dst, alias, value_types[dst]):
                        src_reg = ensure_value_in_reg(alias)
                        consume_use(alias)
                        rd = alloc_vreg(dst, value_types[alias])
                        if rd != src_reg:
                            asm.append(f"MOV {rd}, {src_reg}")
                elif idx == '1':
                    alias = pair["flag"]
                    value_types[dst] = 'i1'
                    if not try_coalesce_value(dst, alias, 'i1'):
                        src_reg = ensure_value_in_reg(alias)
                        consume_use(alias)
                        rd = alloc_vreg(dst, 'i1')
                        if rd != src_reg:
                            asm.append(f"MOV {rd}, {src_reg}")
                else:
                    raise ISelError(f"Unsupported extractvalue index {idx}")
                maybe_release(dst)
                return line

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
                return line

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
                return line

            m = re.match(r'(?:(%[A-Za-z0-9_]+)\s*=\s*)?call\s+([^@]+)@([A-Za-z0-9_]+)\s*\(([^)]*)\)', line)
            if m:
                dst, ret_type, func_name, args_str = m.groups()
                args = [arg.strip() for arg in args_str.split(',') if arg.strip()]
                stack_args = args[len(ARG_REGS):]
                stack_arg_count = len(stack_args)
                if stack_arg_count:
                    for arg in reversed(stack_args):
                        value_token = arg.split()[-1]
                        src_reg = resolve_operand(value_token, "R12")
                        asm.append(f"PUSH {src_reg}")
                reg_args = args[:len(ARG_REGS)]
                for idx, arg in enumerate(reg_args):
                    value_token = arg.split()[-1]
                    target_reg = ARG_REGS[idx]
                    src_reg = resolve_operand(value_token, target_reg)
                    if src_reg != target_reg:
                        asm.append(f"MOV {target_reg}, {src_reg}")
                if defined is not None and func_name not in defined:
                    imports.add(func_name)
                asm.append(f"CALL {func_name}")
                if stack_arg_count:
                    for _ in range(stack_arg_count):
                        asm.append("POP R12")
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
                return line

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
                return line

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
                return line

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
                    return line
                if src_bits == 32 and dst_bits == 64:
                    rd = alloc_vreg(dst, 'i32')
                    if rd != rs:
                        asm.append(f"MOV {rd}, {rs}")
                    maybe_release(dst)
                    return line
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
                return line

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
                return line

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
                return line

            m = re.match(r'br\s+label\s+%([A-Za-z0-9_]+)', line)
            if m:
                target_label = m.group(1)
                apply_phi_moves(block_label, target_label)
                asm.append(f"JMP {label_map.get(target_label, target_label)}")
                return line

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
                apply_phi_moves(block_label, tlabel)
                asm.append(f"JMP {label_map.get(tlabel, tlabel)}")
                asm.append(f"{else_label}:")
                apply_phi_moves(block_label, flabel)
                asm.append(f"JMP {label_map.get(flabel, flabel)}")
                return line

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
                index_clean = index.strip()
                if index_clean not in ('0', '0LL', '0l'):
                    stride = type_size(elem_type)
                    idx_reg = resolve_operand(index, "R12")
                    if idx_reg != 'R12':
                        asm.append(f"MOV R12, {idx_reg}")
                        idx_reg = 'R12'
                    if stride != 1:
                        load_const('R13', stride)
                        asm.append(f"MUL {idx_reg}, {idx_reg}, R13")
                    asm.append(f"ADD {rd}, {rd}, {idx_reg}")
                    if base_name in frame_ptr_offsets:
                        try:
                            idx_const = int(index_clean, 0)
                        except ValueError:
                            frame_ptr_offsets.pop(dst, None)
                        else:
                            stride_bytes = type_size(elem_type)
                            frame_ptr_offsets[dst] = frame_ptr_offsets[base_name] + idx_const * stride_bytes
                    else:
                        frame_ptr_offsets.pop(dst, None)
                else:
                    if base_name in frame_ptr_offsets:
                        frame_ptr_offsets[dst] = frame_ptr_offsets[base_name]
                maybe_release(dst)
                return line

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
                index_clean = index.strip()
                if index_clean not in ('0', '0LL', '0l'):
                    stride = type_size(elem_type)
                    idx_reg = resolve_operand(index, 'R12')
                    if idx_reg != 'R12':
                        asm.append(f"MOV R12, {idx_reg}")
                        idx_reg = 'R12'
                    if stride != 1:
                        load_const('R13', stride)
                        asm.append(f"MUL {idx_reg}, {idx_reg}, R13")
                    asm.append(f"ADD {rd}, {rd}, {idx_reg}")
                    if base_name in frame_ptr_offsets:
                        try:
                            idx_const = int(index_clean, 0)
                        except ValueError:
                            frame_ptr_offsets.pop(dst, None)
                        else:
                            stride_bytes = type_size(elem_type)
                            frame_ptr_offsets[dst] = frame_ptr_offsets[base_name] + idx_const * stride_bytes
                    else:
                        frame_ptr_offsets.pop(dst, None)
                else:
                    if base_name in frame_ptr_offsets:
                        frame_ptr_offsets[dst] = frame_ptr_offsets[base_name]
                maybe_release(dst)
                return line

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
                if base_name in frame_ptr_offsets:
                    frame_ptr_offsets[dst] = frame_ptr_offsets[base_name]
                maybe_release(dst)
                return line

            m = re.match(r'(%[A-Za-z0-9_]+)\s*=\s*load(?:\s+volatile)?\s+(i8|i16|i32|ptr|half|float),\s*(?:i\d+\*|ptr)\s+([^,]+)(?:,\s*align\s+\d+)?', line)
            if m:
                dst, dtype, ptr = m.groups()
                clear_alias(dst)
                dst_type = deduce_value_type(dtype)
                value_types[dst] = dst_type
                rd = alloc_vreg(dst, dst_type)
                if ptr in frame_ptr_offsets:
                    offset = frame_ptr_offsets[ptr]
                    op_map = {"i8": "LDB", "i16": "LDH", "half": "LDH"}
                    instr = op_map.get(dtype, "LD")
                    asm.append(f"{instr} {rd}, [R7{format_stack_offset(offset)}]")
                    consume_use(ptr)
                else:
                    rp = materialize_ptr(ptr, "R14")
                    op_map = {"i8": "LDB", "i16": "LDH", "half": "LDH"}
                    instr = op_map.get(dtype, "LD")
                    asm.append(f"{instr} {rd}, [{rp}+0]")
                if dst_type == 'float':
                    float_alias[dst] = rd
                maybe_release(dst)
                return line

            m = re.match(r'store(?:\s+volatile)?\s+(i8|i16|i32|ptr|half|float)\s+([^,]+),\s*(?:i\d+\*|ptr)\s+([^,]+)(?:,\s*align\s+\d+)?', line)
            if m:
                dtype, src, ptr = m.groups()
                if ptr in frame_ptr_offsets:
                    offset = frame_ptr_offsets[ptr]
                    if dtype == 'ptr':
                        rs = materialize_ptr(src, "R12")
                    else:
                        rs = resolve_operand(src, "R12")
                    op_map = {"i8": "STB", "i16": "STH", "half": "STH"}
                    instr = op_map.get(dtype, "ST")
                    asm.append(f"{instr} [R7{format_stack_offset(offset)}], {rs}")
                    consume_use(ptr)
                else:
                    rp = materialize_ptr(ptr, "R14")
                    if dtype == 'ptr':
                        rs = materialize_ptr(src, "R12")
                    else:
                        rs = resolve_operand(src, "R12")
                    op_map = {"i8": "STB", "i16": "STH", "half": "STH"}
                    instr = op_map.get(dtype, "ST")
                    asm.append(f"{instr} [{rp}+0], {rs}")
                return line

            raise ISelError("Unsupported IR line: "+orig_line)

    for b in fn["blocks"]:
        if is_first_block:
            asm.append(f"{fn['name']}:")
            is_first_block = False
        asm.append(label_map[b["label"]] + ":")
        if not prologue_emitted:
            asm.append("PUSH R7")
            asm.append("MOV R7, R15")
            prologue_emitted = True
        if trace and phi_comments.get(b["label"]):
            for phi_line in phi_comments[b["label"]]:
                asm.append(f"; PHI: {phi_line}")
        dbg_refs = b.get("dbg_refs", [])
        for instr_idx, raw in enumerate(b["ins"]):
            dbg_id = dbg_refs[instr_idx] if instr_idx < len(dbg_refs) else None
            inst_counter += 1
            inst_id = f"{fn['name']}@{inst_counter}"
            start_idx = len(asm)
            normalized_line = None
            emitted_indices: List[int] = []
            try:
                normalized_line = _lower_ir_instruction(raw, b["label"])
            finally:
                if sys.exc_info()[0] is None:
                    if normalized_line is None:
                        normalized_line = normalize_ir_line(raw)
                    end_idx = len(asm)
                    for asm_index in range(start_idx, end_idx):
                        if is_instruction_line(asm[asm_index]):
                            emitted_indices.append(asm_index)
                    if emitted_indices:
                        instruction_records.append(
                            {
                                "id": inst_id,
                                "function": fn["name"],
                                "ir": normalized_line,
                                "raw_ir": raw.strip(),
                                "dbg": dbg_id,
                            }
                        )
                        for asm_index in emitted_indices:
                            line_debug_entries.append((asm_index, dbg_id, inst_id))
            maybe_split_long_lived(inst_counter)
    allocation_stats["available_registers"] = len(AVAILABLE_REGS)
    allocation_stats["stack_slots"] = len(spill_slots)
    allocation_stats["stack_bytes"] = frame_size
    allocation_stats["used_registers"] = sorted(used_registers)
    allocation_stats["used_register_count"] = len(allocation_stats["used_registers"])
    variable_records: List[Dict[str, Any]] = []
    for var_id, state in variable_states.items():
        events = state.get("events") or []
        if not events:
            continue
        variable_records.append(
            {
                "id": var_id,
                "function": fn["name"],
                "events": events,
            }
        )
    line_tags: List[Optional[Dict[str, Any]]] = [None] * len(asm)
    for asm_index, dbg_id, inst_id in line_debug_entries:
        tag: Dict[str, Any] = {"inst": inst_id}
        if dbg_id:
            tag["dbg"] = dbg_id
        line_tags[asm_index] = tag
    return asm, spill_data_lines, line_tags, instruction_records, allocation_stats, variable_records


def compile_ll_to_mvasm(
    ir_text: str,
    trace=False,
    enable_opt=True,
    allocator_opts: Optional[Dict[str, bool]] = None,
) -> str:
    global LAST_DEBUG_INFO
    _reset_global_name_cache()
    ir_text = _preprocess_ir_text(ir_text)
    restore_features: Optional[Tuple[bool, bool]] = None
    if allocator_opts:
        restore_features = _set_allocator_features(
            coalesce=allocator_opts.get("coalesce"),
            split=allocator_opts.get("split"),
        )
    try:
        ir = parse_ir(ir_text.splitlines())
        entry_label = next((fn['name'] for fn in ir['functions'] if fn['name'] == 'main'), None)
        defined_names = {fn['name'] for fn in ir['functions']}
        globals_list = ir.get('globals', [])
        global_names = {g['name'] for g in globals_list}
        imports = set()
        out: List[str] = []
        line_tags: List[Optional[Dict[str, Any]]] = []
        spill_data_all: List[str] = []
        function_spans: List[Tuple[str, int, int]] = []
        instruction_records: Dict[str, Dict[str, Any]] = {}
        instruction_order: List[str] = []
        function_reg_stats: Dict[str, Dict[str, Any]] = {}
        variable_event_records: List[Dict[str, Any]] = []
        for fn in ir['functions']:
            start_line = len(out)
            (
                fn_asm,
                fn_spill_data,
                fn_tags,
                fn_instruction_records,
                fn_alloc_stats,
                fn_variable_records,
            ) = lower_function(
                fn,
                trace=trace,
                imports=imports,
                defined=defined_names,
                global_symbols=global_names,
                type_info=ir.get('types', {}),
                debug_info=ir.get('debug', {}),
            )
            out += fn_asm
            line_tags.extend(fn_tags)
            end_line = len(out)
            function_spans.append((fn["name"], start_line, end_line))
            if fn_spill_data:
                spill_data_all.extend(fn_spill_data)
            for record in fn_instruction_records:
                inst_id = record["id"]
                instruction_records[inst_id] = record
                instruction_order.append(inst_id)
            function_reg_stats[fn["name"]] = fn_alloc_stats
            for record in fn_variable_records:
                entry = dict(record)
                entry["line_base"] = start_line
                variable_event_records.append(entry)
        data_section = render_globals(globals_list)
        mailbox_entries = ir.get("mailboxes", [])
        value_entries = ir.get("values", [])
        command_entries = ir.get("commands", [])
        if spill_data_all:
            if data_section:
                data_section.extend(spill_data_all)
            else:
                data_section = ['.data'] + spill_data_all
        summary_total_funcs = len(function_reg_stats)
        total_spills = sum(stats["spill_count"] for stats in function_reg_stats.values())
        total_reloads = sum(stats["reload_count"] for stats in function_reg_stats.values())
        max_pressure_overall = max((stats["max_pressure"] for stats in function_reg_stats.values()), default=0)
        max_stack_bytes = max((stats["stack_bytes"] for stats in function_reg_stats.values()), default=0)
        functions_with_spills = sorted(
            name for name, stats in function_reg_stats.items() if stats["spill_count"] > 0
        )
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
            if value_entries:
                for entry in value_entries:
                    header.append(".value " + json.dumps(entry, separators=(",", ":"), sort_keys=True))
            if command_entries:
                for entry in command_entries:
                    header.append(".cmd " + json.dumps(entry, separators=(",", ":"), sort_keys=True))
            if mailbox_entries:
                for entry in mailbox_entries:
                    header.append(".mailbox " + json.dumps(entry, separators=(",", ":"), sort_keys=True))
            if data_section:
                header += data_section
            header.append('.text')
            out = header + out
            header_tags: List[Optional[Dict[str, Any]]] = [None] * len(header)
            line_tags = header_tags + line_tags
            header_len = len(header)
            function_spans = [(name, start + header_len, end + header_len) for (name, start, end) in function_spans]
            if enable_opt and not trace:
                out, line_tags = _optimize_movs(out, line_tags)
        else:
            header_len = 0

        instruction_ordinals: Dict[int, int] = {}
        ordinal_counter = 0
        for idx, asm_line in enumerate(out):
            if is_instruction_line(asm_line):
                tag = line_tags[idx]
                if not isinstance(tag, dict):
                    tag = {}
                    line_tags[idx] = tag
                tag["ordinal"] = ordinal_counter
                instruction_ordinals[idx + 1] = ordinal_counter
                ordinal_counter += 1

        line_to_ordinal = dict(instruction_ordinals)

        debug_info = ir.get("debug", {"files": {}, "subprograms": {}, "functions": []})
        files = debug_info.get("files", {})
        subprograms = debug_info.get("subprograms", {})
        locations = debug_info.get("locations", {})
        lexical_blocks = debug_info.get("lexical_blocks", {})
        local_variables = debug_info.get("locals", {})
        functions_meta = debug_info.get("functions", [])

        def _resolve_file_for_scope(scope_id: Optional[str]) -> Optional[Dict[str, Any]]:
            current = scope_id
            visited: Set[str] = set()
            while current and current not in visited:
                visited.add(current)
                block = lexical_blocks.get(current)
                if block:
                    file_ref = block.get("file")
                    if file_ref and file_ref in files:
                        return files[file_ref]
                    current = block.get("scope")
                    continue
                sub = subprograms.get(current)
                if sub:
                    file_ref = sub.get("file")
                    if file_ref and file_ref in files:
                        return files[file_ref]
                    current = sub.get("scope")
                    continue
                if current in files:
                    return files[current]
                break
            return None

        def _resolve_location_ref(meta_id: Optional[str]) -> Optional[Dict[str, Any]]:
            if not meta_id:
                return None
            loc = locations.get(meta_id)
            if not loc:
                return None
            result: Dict[str, Any] = {
                "id": meta_id,
                "line": loc.get("line"),
                "column": loc.get("column"),
                "scope": loc.get("scope"),
            }
            file_entry = None
            file_ref = loc.get("file")
            if file_ref:
                file_entry = files.get(file_ref)
            if not file_entry:
                file_entry = _resolve_file_for_scope(loc.get("scope"))
            if file_entry:
                result["file"] = {
                    "id": file_entry.get("id"),
                    "filename": file_entry.get("filename"),
                    "directory": file_entry.get("directory"),
                }
            return result

        files_list: List[Dict[str, Any]] = []
        for meta_id, info in files.items():
            files_list.append(
                {
                    "id": meta_id,
                    "filename": info.get("filename"),
                    "directory": info.get("directory"),
                }
            )
        total_proactive = sum(stats.get("proactive_splits", 0) for stats in function_reg_stats.values())
        allocation_summary = {
            "total_functions": summary_total_funcs,
            "functions_with_spills": functions_with_spills,
            "max_pressure": max_pressure_overall,
            "total_spills": total_spills,
            "total_reloads": total_reloads,
            "max_stack_bytes": max_stack_bytes,
            "total_proactive_splits": total_proactive,
        }

        functions_list: List[Dict[str, Any]] = []
        function_ordinals_map: Dict[str, Tuple[Optional[int], Optional[int]]] = {}
        span_map = {fname: (start, end) for fname, start, end in function_spans}
        for entry in functions_meta:
            name = entry.get("function")
            start_end = span_map.get(name)
            if start_end:
                start_line = start_end[0] + 1
                end_line = start_end[1] if start_end[1] > start_end[0] else start_line
            else:
                start_line = None
                end_line = None
            ordinals_in_range: List[int] = []
            if start_line is not None and end_line is not None:
                for line_num in range(start_line, end_line + 1):
                    ordinal_val = line_to_ordinal.get(line_num)
                    if ordinal_val is not None:
                        ordinals_in_range.append(ordinal_val)
            if ordinals_in_range:
                start_ord = min(ordinals_in_range)
                end_ord = max(ordinals_in_range)
            else:
                start_ord = None
                end_ord = None
            function_ordinals_map[name] = (start_ord, end_ord)
            func_entry: Dict[str, Any] = {
                "function": name,
                "name": entry.get("name"),
                "linkage_name": entry.get("linkage_name"),
                "file": entry.get("file"),
                "line": entry.get("line"),
                "mvasm_start_line": start_line,
                "mvasm_end_line": end_line,
                "mvasm_start_ordinal": start_ord,
                "mvasm_end_ordinal": end_ord,
            }
            stats_entry = function_reg_stats.get(name)
            if stats_entry:
                func_entry["register_allocation"] = stats_entry
            functions_list.append(func_entry)
        existing_names = {entry["function"] for entry in functions_list}
        for name, stats_entry in function_reg_stats.items():
            if name in existing_names:
                continue
            functions_list.append(
                {
                    "function": name,
                    "register_allocation": stats_entry,
                }
            )
            if name not in function_ordinals_map:
                function_ordinals_map[name] = (None, None)

        line_map_entries: List[Dict[str, Any]] = []
        instruction_line_map: Dict[str, List[int]] = defaultdict(list)
        source_mapped_ordinals: Set[int] = set()
        compiler_ordinals: Set[int] = set()
        for idx, tag in enumerate(line_tags):
            if not tag or not isinstance(tag, dict):
                continue
            inst_id = tag.get("inst")
            if inst_id:
                instruction_line_map.setdefault(inst_id, []).append(idx + 1)
            entry: Dict[str, Any] = {
                "mvasm_line": idx + 1,
            }
            ordinal_val = tag.get("ordinal")
            if ordinal_val is not None:
                entry["mvasm_ordinal"] = ordinal_val
            if inst_id:
                entry["instruction"] = inst_id
            dbg_id = tag.get("dbg")
            loc_info = _resolve_location_ref(dbg_id) if dbg_id else None
            if loc_info:
                entry["source_kind"] = "source"
                entry["source_line"] = loc_info["line"]
                if loc_info.get("column") is not None:
                    entry["source_column"] = loc_info["column"]
                file_entry = loc_info.get("file")
                if file_entry:
                    entry["source_file"] = file_entry.get("filename")
                    directory = file_entry.get("directory")
                    if directory:
                        entry["source_directory"] = directory
                    entry["source_file_id"] = file_entry.get("id")
                if ordinal_val is not None:
                    source_mapped_ordinals.add(ordinal_val)
            else:
                entry["source_kind"] = "compiler"
                if ordinal_val is not None:
                    compiler_ordinals.add(ordinal_val)
            line_map_entries.append(entry)
        line_map_entries.sort(key=lambda item: item["mvasm_line"])

        instruction_ordinal_map: Dict[str, List[int]] = {}
        for inst_id, line_numbers in instruction_line_map.items():
            ordinals: List[int] = []
            for line_number in line_numbers:
                ordinal_val = line_to_ordinal.get(line_number)
                if ordinal_val is not None:
                    ordinals.append(ordinal_val)
            if ordinals:
                instruction_ordinal_map[inst_id] = ordinals

        llvm_map_entries: List[Dict[str, Any]] = []
        for inst_id in instruction_order:
            lines_for_inst = instruction_line_map.get(inst_id)
            if not lines_for_inst:
                continue
            record = instruction_records.get(inst_id)
            if not record:
                continue
            entry: Dict[str, Any] = {
                "id": inst_id,
                "function": record.get("function"),
                "ir": record.get("ir"),
                "raw_ir": record.get("raw_ir"),
                "mvasm_lines": lines_for_inst,
            }
            dbg_ref = record.get("dbg")
            if dbg_ref:
                entry["dbg"] = dbg_ref
                loc_info = _resolve_location_ref(dbg_ref)
                if loc_info:
                    entry["source_line"] = loc_info.get("line")
                    if loc_info.get("column") is not None:
                        entry["source_column"] = loc_info.get("column")
                    file_entry = loc_info.get("file")
                    if file_entry:
                        entry["source_file"] = file_entry.get("filename")
                        if file_entry.get("directory"):
                            entry["source_directory"] = file_entry["directory"]
            ordinals_for_inst = instruction_ordinal_map.get(inst_id)
            if ordinals_for_inst:
                entry["mvasm_ordinals"] = ordinals_for_inst
            llvm_map_entries.append(entry)

        all_ordinals = set(line_to_ordinal.values())
        unmapped_ordinals = sorted(
            ord_val
            for ord_val in all_ordinals
            if ord_val not in source_mapped_ordinals and ord_val not in compiler_ordinals
        )
        line_coverage = {
            "total_instructions": len(all_ordinals),
            "source_mapped": len(source_mapped_ordinals),
            "compiler_tagged": len(compiler_ordinals),
            "unmapped": unmapped_ordinals,
        }
        if unmapped_ordinals:
            sys.stderr.write(
                f"[hsx-llc] warning: {len(unmapped_ordinals)} instruction(s) missing debug coverage\n"
            )

        def _ordinal_from_line_hint(global_index: int) -> Optional[int]:
            if global_index < 0:
                global_index = 0
            limit = len(line_tags)
            idx = min(global_index, limit - 1) if limit else 0
            while idx < limit:
                tag = line_tags[idx]
                if tag and isinstance(tag, dict):
                    ord_val = tag.get("ordinal")
                    if ord_val is not None:
                        return ord_val
                idx += 1
            return None

        variables_entries: List[Dict[str, Any]] = []
        for record in variable_event_records:
            var_id = record.get("id")
            fn_name = record.get("function")
            events = record.get("events") or []
            if not var_id or not fn_name or not events:
                continue
            var_meta = local_variables.get(var_id)
            if not var_meta:
                continue
            line_base = record.get("line_base", 0)
            resolved_events: List[Dict[str, Any]] = []
            for event in events:
                line_index = max(int(event.get("line_index", 0)), 0)
                ordinal = _ordinal_from_line_hint(line_base + line_index)
                if ordinal is None:
                    continue
                resolved_events.append(
                    {
                        "ordinal": ordinal,
                        "location": dict(event.get("location") or {}),
                    }
                )
            if not resolved_events:
                continue
            resolved_events.sort(key=lambda item: item["ordinal"])
            fn_ordinals = function_ordinals_map.get(fn_name, (None, None))
            ranges: List[Dict[str, Any]] = []
            for idx, evt in enumerate(resolved_events):
                start_ord = evt["ordinal"]
                next_ord = (
                    resolved_events[idx + 1]["ordinal"]
                    if idx + 1 < len(resolved_events)
                    else None
                )
                end_ord = next_ord if next_ord is not None else fn_ordinals[1]
                range_entry = {
                    "start_ordinal": start_ord,
                    "end_ordinal": end_ord,
                    "location": evt["location"],
                }
                ranges.append(range_entry)
            if not ranges:
                continue
            file_info = None
            file_ref = var_meta.get("file")
            if file_ref and file_ref in files:
                file_info = files[file_ref]
            if not file_info:
                file_info = _resolve_file_for_scope(var_meta.get("scope"))
            variables_entries.append(
                {
                    "id": var_id,
                    "name": var_meta.get("name"),
                    "function": fn_name,
                    "scope": var_meta.get("scope"),
                    "file": file_info,
                    "line": var_meta.get("line"),
                    "type": var_meta.get("type"),
                    "locations": ranges,
                }
            )
        LAST_DEBUG_INFO = {
            "version": 1,
            "files": files_list,
            "functions": functions_list,
            "line_map": line_map_entries,
            "llvm_to_mvasm": llvm_map_entries,
            "variables": variables_entries,
            "register_allocation_summary": allocation_summary,
            "line_coverage": line_coverage,
        }
        return "\n".join(out) + "\n"
    finally:
        if restore_features is not None:
            _set_allocator_features(coalesce=restore_features[0], split=restore_features[1])

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input")
    ap.add_argument("-o","--output", required=True)
    ap.add_argument("--trace", action="store_true")
    ap.add_argument("--no-opt", action="store_true", help="disable MOV optimization pass")
    ap.add_argument("--emit-debug", help="write debug metadata JSON to file")
    ap.add_argument("--dump-reg-stats", action="store_true", help="emit register allocation summary to stdout")
    ap.add_argument("--disable-coalesce", action="store_true", help="disable register coalescing heuristics")
    ap.add_argument("--disable-split", action="store_true", help="disable proactive live-range splitting")
    args = ap.parse_args()
    txt = open(args.input,"r",encoding="utf-8").read()
    allocator_opts = {}
    if args.disable_coalesce:
        allocator_opts["coalesce"] = False
    if args.disable_split:
        allocator_opts["split"] = False
    asm = compile_ll_to_mvasm(
        txt,
        trace=args.trace,
        enable_opt=not args.no_opt,
        allocator_opts=allocator_opts or None,
    )
    with open(args.output,"w",encoding="utf-8") as f:
        f.write(asm)
    if args.emit_debug:
        _write_debug_file(args.emit_debug, LAST_DEBUG_INFO)
    if args.dump_reg_stats:
        summary = (LAST_DEBUG_INFO or {}).get("register_allocation_summary", {})
        print(json.dumps(summary, indent=2, sort_keys=True))
    print(f"Wrote {args.output}")
if __name__ == "__main__":
    main()
