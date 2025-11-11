"""Info command."""

from __future__ import annotations

import argparse
from typing import Dict, Optional

from .base import Command
from ..context import DebuggerContext
from ..output import (
    emit_error,
    emit_result,
    normalise_task_list,
    render_register_block,
    render_task_detail,
    render_task_table,
)


class InfoCommand(Command):
    def __init__(self) -> None:
        super().__init__("info", "Show executive/task info")
        self._parser = argparse.ArgumentParser(prog="info", add_help=False)
        self._parser.add_argument("pid", nargs="?", type=int, help="Optional PID to inspect")

    def run(self, ctx: DebuggerContext, argv: List[str]) -> int:
        try:
            args = self._parser.parse_args(argv)
        except SystemExit:
            return 1
        session = ctx.ensure_session()
        payload: Dict[str, Any] = {"cmd": "info"}
        if args.pid is not None:
            payload["pid"] = args.pid
        try:
            response = session.request(payload)
        except Exception as exc:
            emit_error(ctx, message=f"info failed: {exc}")
            return 2
        if response.get("status") != "ok":
            emit_error(ctx, message=response.get("error", "info failed"), data=response)
            return 1
        info = response.get("info") or {}
        if ctx.json_output:
            emit_result(ctx, message="info", data={"info": info})
            return 0
        self._render_info(info, pid=args.pid)
        return 0

    def _render_info(self, info: Dict[str, Any], *, pid: Optional[int]) -> None:
        print("info:")
        running = info.get("running")
        paused = info.get("paused")
        attached = info.get("attached")
        program = info.get("program")
        if program is not None:
            print(f"  program  : {program}")
        print(f"  running  : {running}  paused: {paused}  attached: {attached}")
        current = info.get("current_pid")
        if current is not None:
            print(f"  current_pid: {current}")
        if pid is None:
            task_list = normalise_task_list(info.get("tasks"))
            render_task_table(task_list, current_pid=current, show_metadata=True)
        else:
            task = info.get("task")
            if isinstance(task, dict):
                render_task_detail(task)
            registers = info.get("registers") or info.get("selected_registers")
            render_register_block(registers)
