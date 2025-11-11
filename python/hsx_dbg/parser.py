"""Lightweight command parsing helpers for hsx-dbg."""

from __future__ import annotations

import shlex
from typing import List


def split_command(line: str) -> List[str]:
    """Split a command line into argv tokens using shlex rules."""
    if not line:
        return []
    try:
        return shlex.split(line, comments=False, posix=True)
    except ValueError as exc:
        # Return the raw line as a single token so callers can raise a friendlier error.
        return [line.strip(), f"#parse-error:{exc}"]
