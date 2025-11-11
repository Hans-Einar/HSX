"""Detach command."""

from __future__ import annotations

from typing import List

from .base import Command
from ..context import DebuggerContext
from ..output import emit_error, emit_result


class DetachCommand(Command):
    def __init__(self) -> None:
        super().__init__("detach", "Detach from the executive")

    def run(self, ctx: DebuggerContext, argv: List[str]) -> int:
        if ctx.observer_mode:
            emit_result(ctx, message="Observer mode does not acquire locks", data={"result": "observer"})
            return 0
        session = ctx.session or ctx.ensure_session()
        try:
            response = session.request({"cmd": "detach"})
        except Exception as exc:
            emit_error(ctx, message=f"detach failed: {exc}")
            return 2
        if response.get("status") != "ok":
            emit_error(ctx, message=response.get("error", "detach failed"), data=response)
            return 1
        info = response.get("info") or {}
        emit_result(ctx, message="Detached from executive", data={"result": "detached", "info": info})
        return 0
