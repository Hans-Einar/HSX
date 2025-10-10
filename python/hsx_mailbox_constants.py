from __future__ import annotations
"""Load shared HSX mailbox constants from the C header.

This keeps the Python executive aligned with the canonical C definitions.
"""


import re
from pathlib import Path
from typing import Dict, Union

_HEADER_BASENAME = "hsx_mailbox.h"
_HEADER_PATH = Path(__file__).resolve().parents[1] / "include" / _HEADER_BASENAME

_NUMBER_RE = re.compile(r"^0[xX][0-9a-fA-F]+$|^[0-9]+$")


def _parse_numeric(token: str) -> int:
    token = token.rstrip("uUlL")
    if not token:
        raise ValueError("empty numeric token")
    base = 16 if token.lower().startswith("0x") else 10
    return int(token, base)


def load_mailbox_constants() -> Dict[str, Union[int, str]]:
    """Parse `hsx_mailbox.h` and return a name->value mapping."""
    if not _HEADER_PATH.exists():
        raise FileNotFoundError(f"missing mailbox header: {_HEADER_PATH}")

    constants: Dict[str, Union[int, str]] = {}
    for raw_line in _HEADER_PATH.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or not line.startswith("#define HSX_MBX_"):
            continue
        parts = line.split(None, 2)
        if len(parts) < 3:
            continue
        name = parts[1]
        value_token = parts[2]
        # Strip trailing comments
        if "/*" in value_token:
            value_token = value_token.split("/*", 1)[0]
        if "//" in value_token:
            value_token = value_token.split("//", 1)[0]
        value_token = value_token.strip()
        if not value_token:
            continue
        if value_token.startswith("\"") and value_token.endswith("\""):
            constants[name] = value_token.strip("\"")
        elif _NUMBER_RE.match(value_token):
            constants[name] = _parse_numeric(value_token)
        else:
            raise ValueError(f"unsupported macro value for {name}: {value_token}")
    return constants


CONSTANTS = load_mailbox_constants()

globals().update(CONSTANTS)

__all__ = ["CONSTANTS"] + list(CONSTANTS.keys())


def header_path() -> Path:
    """Return the path to the authoritative header file."""
    return _HEADER_PATH
