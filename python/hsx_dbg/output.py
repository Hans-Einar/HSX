"""Output helpers for hsx-dbg."""

from __future__ import annotations

import json
from typing import Any, Mapping, Optional

from .context import DebuggerContext


def _json_dump(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, indent=2, sort_keys=True)


def emit_result(ctx: DebuggerContext, *, message: str, data: Optional[Mapping[str, Any]] = None) -> None:
    """Emit a successful command result."""
    if ctx.json_output and data is not None:
        print(_json_dump(data))
    else:
        print(message)


def emit_error(ctx: DebuggerContext, *, message: str, data: Optional[Mapping[str, Any]] = None) -> None:
    """Emit an error message respecting JSON mode."""
    payload = {"error": message}
    if data:
        payload.update(data)
    if ctx.json_output:
        print(_json_dump(payload))
    else:
        print(f"error: {message}")
