"""Attach command."""

from __future__ import annotations

from typing import List

from .base import Command
from ..context import DebuggerContext
from ..output import emit_error, emit_result


class AttachCommand(Command):
    def __init__(self) -> None:
        super().__init__("attach", "Attach to the executive (global)")

    def run(self, ctx: DebuggerContext, argv: List[str]) -> int:
        if ctx.observer_mode:
            emit_error(ctx, message="Observer mode enabled; attach disabled")
            return 1
        session = ctx.ensure_session()
        try:
            response = session.request({"cmd": "attach"})
        except Exception as exc:
            emit_error(ctx, message=f"attach failed: {exc}")
            return 2
        if response.get("status") != "ok":
            emit_error(ctx, message=response.get("error", "attach failed"), data=response)
            return 1
        info = response.get("info") or {}
        message = "Attached to executive"
        tasks = _summarise_tasks(info)
        if tasks and not ctx.json_output:
            message += f" (tasks={tasks})"
        emit_result(ctx, message=message, data={"result": "attached", "info": info})
        return 0


def _summarise_tasks(info) -> str:
    tasks_block = info.get("tasks")
    if isinstance(tasks_block, dict):
        entries = tasks_block.get("tasks")
        if isinstance(entries, list):
            return str(len(entries))
    return ""
