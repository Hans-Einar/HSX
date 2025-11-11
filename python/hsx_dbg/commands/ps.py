"""ps command (task listing)."""

from __future__ import annotations

import argparse
from typing import Any, Dict, List, Optional

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


class PsCommand(Command):
    def __init__(self) -> None:
        super().__init__("ps", "List tasks or show PID details")
        self._parser = argparse.ArgumentParser(prog="ps", add_help=False)
        self._parser.add_argument("pid", nargs="?", type=int, help="Optional PID to inspect")

    def run(self, ctx: DebuggerContext, argv: List[str]) -> int:
        try:
            args = self._parser.parse_args(argv)
        except SystemExit:
            return 1
        if args.pid is None:
            return self._run_list(ctx)
        return self._run_detail(ctx, args.pid)

    def _run_list(self, ctx: DebuggerContext) -> int:
        session = ctx.ensure_session()
        try:
            response = session.request({"cmd": "ps"})
        except Exception as exc:
            emit_error(ctx, message=f"ps failed: {exc}")
            return 2
        if response.get("status") != "ok":
            emit_error(ctx, message=response.get("error", "ps failed"), data=response)
            return 1
        tasks_block = response.get("tasks") or {}
        if ctx.json_output:
            emit_result(ctx, message="ps", data={"tasks": tasks_block})
            return 0
        current_pid = None
        if isinstance(tasks_block, dict):
            current_pid = tasks_block.get("current_pid")
        task_list = normalise_task_list(tasks_block)
        render_task_table(task_list, current_pid=current_pid, show_metadata=True)
        return 0

    def _run_detail(self, ctx: DebuggerContext, pid: int) -> int:
        session = ctx.ensure_session()
        try:
            response = session.request({"cmd": "info", "pid": pid})
        except Exception as exc:
            emit_error(ctx, message=f"ps {pid} failed: {exc}")
            return 2
        if response.get("status") != "ok":
            emit_error(ctx, message=response.get("error", "ps failed"), data=response)
            return 1
        info = response.get("info") or {}
        if ctx.json_output:
            emit_result(ctx, message="ps", data={"info": info})
            return 0
        task = _extract_task(info, pid)
        if task is None:
            print(f"task {pid} not found")
            return 1
        render_task_detail(task)
        registers = info.get("selected_registers") or info.get("registers")
        render_register_block(registers)
        return 0


def _extract_task(info: Dict[str, Any], pid: int) -> Optional[Dict[str, Any]]:
    task = info.get("task")
    if isinstance(task, dict):
        return task
    task_list = normalise_task_list(info.get("tasks"))
    for entry in task_list:
        if entry.get("pid") == pid:
            return entry
    return None
