#!/usr/bin/env python3
"""Utilities for normalising HSX trace records.

Trace records are exchanged as JSON dictionaries using the ``hsx.trace/1``
format. This helper ensures the required fields are present, coerces integers,
and sanitises optional payloads such as register snapshots and memory access
metadata.  It is deliberately opinionated so downstream tools can rely on a
stable schema regardless of whether the trace originated inside the executive
or was imported from an offline capture.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Mapping

TRACE_FORMAT_VERSION = "hsx.trace/1"

_REQUIRED_FIELDS = ("seq", "pid", "pc", "opcode")
_OPTIONAL_INT_FIELDS = ("next_pc", "steps", "flags")
_VALID_MEM_OPS = {"read", "write"}


def _coerce_int(value: Any, field: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{field} must be an integer, got boolean")
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        value = value.strip()
        base = 16 if value.lower().startswith("0x") else 10
        return int(value, base)
    raise ValueError(f"{field} must be integer-compatible (got {value!r})")


def _coerce_float(value: Any, field: str) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        return float(value.strip())
    raise ValueError(f"{field} must be numeric-compatible (got {value!r})")


def _coerce_reg_list(values: Any) -> List[int]:
    if values is None:
        return []
    if not isinstance(values, (list, tuple)):
        raise ValueError("regs must be a sequence")
    coerced: List[int] = []
    for idx, entry in enumerate(values):
        coerced.append(_coerce_int(entry, f"regs[{idx}]") & 0xFFFFFFFF)
    return coerced


def _coerce_changed_regs(values: Any) -> List[str]:
    if values is None:
        return []
    if not isinstance(values, (list, tuple)):
        raise ValueError("changed_regs must be a sequence")
    result: List[str] = []
    for entry in values:
        if entry is None:
            continue
        text = str(entry).strip()
        if not text:
            continue
        result.append(text.upper())
    return result


def _coerce_mem_access(value: Any) -> Dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise ValueError("mem_access must be an object")
    op_raw = value.get("op")
    if op_raw is None:
        raise ValueError("mem_access.op missing")
    op = str(op_raw).strip().lower()
    if op not in _VALID_MEM_OPS:
        raise ValueError(f"mem_access.op must be one of {sorted(_VALID_MEM_OPS)}")
    address = _coerce_int(value.get("address"), "mem_access.address") & 0xFFFFFFFF
    width_value = value.get("width")
    width = _coerce_int(width_value, "mem_access.width") if width_value is not None else None
    result: Dict[str, Any] = {"op": op, "address": address}
    if width is not None:
        result["width"] = max(0, width)
    if "value" in value and value["value"] is not None:
        result["value"] = _coerce_int(value["value"], "mem_access.value") & 0xFFFFFFFF
    if "mask" in value and value["mask"] is not None:
        result["mask"] = _coerce_int(value["mask"], "mem_access.mask") & 0xFFFFFFFF
    return result


def normalise_trace_record(record: Mapping[str, Any]) -> Dict[str, Any]:
    """Return a JSON-friendly copy of ``record`` with the canonical schema.

    Required integer fields are coerced, register snapshots are promoted to
    lists, and optional payloads (`changed_regs`, `mem_access`) are sanitised.
    Unknown fields are preserved so callers can attach additional metadata,
    provided the core schema remains intact.
    """

    normalized: Dict[str, Any] = {}
    for field in _REQUIRED_FIELDS:
        if field not in record:
            raise ValueError(f"trace record missing required field '{field}'")
        normalized[field] = _coerce_int(record[field], field)

    for field in _OPTIONAL_INT_FIELDS:
        if field in record and record[field] is not None:
            normalized[field] = _coerce_int(record[field], field)
    if "ts" in record and record["ts"] is not None:
        normalized["ts"] = _coerce_float(record["ts"], "ts")

    regs = _coerce_reg_list(record.get("regs"))
    if regs:
        normalized["regs"] = regs

    changed = _coerce_changed_regs(record.get("changed_regs"))
    if changed:
        normalized["changed_regs"] = changed

    mem_access = _coerce_mem_access(record.get("mem_access"))
    if mem_access:
        normalized["mem_access"] = mem_access

    # Carry across any additional fields (without coercion) so callers can
    # attach metadata such as ``source`` or ``notes``.
    for key, value in record.items():
        if key in normalized or key in _REQUIRED_FIELDS or key in _OPTIONAL_INT_FIELDS:
            continue
        if key in {"regs", "changed_regs", "mem_access"}:
            continue
        normalized[key] = value

    return normalized


def encode_trace_records(records: Iterable[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    """Return a list of normalised trace records suitable for JSON encoding."""

    return [normalise_trace_record(record) for record in records]


def decode_trace_records(
    records: Iterable[Mapping[str, Any]], *, default_pid: int | None = None
) -> List[Dict[str, Any]]:
    """Parse trace records previously produced by :func:`encode_trace_records`.

    Values are coerced to the canonical representation; register snapshots and
    change lists are converted to tuples so the caller can store them without
    additional copies.
    """

    parsed: List[Dict[str, Any]] = []
    for record in records:
        if default_pid is not None and "pid" not in record:
            record = dict(record)
            record["pid"] = default_pid
        normalized = normalise_trace_record(record)
        internal = dict(normalized)
        if "regs" in internal:
            internal["regs"] = tuple(internal["regs"])
        if "changed_regs" in internal:
            internal["changed_regs"] = tuple(internal["changed_regs"])
        if "mem_access" in internal:
            internal["mem_access"] = dict(internal["mem_access"])
        parsed.append(internal)
    return parsed
