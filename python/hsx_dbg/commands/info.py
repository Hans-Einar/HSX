"""Info command."""

from __future__ import annotations

import argparse
from typing import Any, Dict, List, Optional

from .base import Command
from ..context import DebuggerContext
from ..output import emit_error, emit_result


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
            self._render_tasks(info, current_pid=current)
        else:
            task = info.get("task")
            if isinstance(task, dict):
                self._render_task_detail(task)
            registers = info.get("registers")
            if isinstance(registers, dict):
                regs = registers.get("regs") or registers.get("registers")
                if isinstance(regs, list):
                    print("  registers:")
                    for idx, value in enumerate(regs):
                        print(f"    R{idx:02}: 0x{int(value) & 0xFFFFFFFF:08X}")

    def _render_tasks(self, info: Dict[str, Any], *, current_pid: Optional[int]) -> None:
        tasks_block = info.get("tasks")
        task_list: List[Dict[str, Any]] = []
        if isinstance(tasks_block, dict):
            entries = tasks_block.get("tasks")
            if isinstance(entries, list):
                task_list = [entry for entry in entries if isinstance(entry, dict)]
        elif isinstance(tasks_block, list):
            task_list = [entry for entry in tasks_block if isinstance(entry, dict)]
        if not task_list:
            return
        header = "      PID   State         Prio  Quantum  Steps     Sleep  Program"
        print("  tasks:")
        print(header)
        print("      " + "-" * (len(header) - 6))
        for task in task_list:
            pid = task.get("pid", "-")
            state = task.get("state", "-")
            prio = task.get("priority", "-")
            quantum = task.get("quantum", "-")
            steps_val = task.get("accounted_steps", task.get("accounted_cycles", "-"))
            sleep = task.get("sleep_pending", False)
            program = task.get("program", "")
            marker = "*" if current_pid is not None and pid == current_pid else " "
            print(
                f"    {marker} {pid:4}  {str(state):<12}  {prio:>4}  {quantum:>7}  {steps_val:>8}  {str(sleep):<5}  {program}"
            )

    def _render_task_detail(self, task: Dict[str, Any]) -> None:
        pid = task.get("pid")
        state = task.get("state")
        print(f"  task pid={pid} state={state}")
        for key in ("priority", "accounted_steps", "accounted_cycles", "sleep_pending", "exit_status"):
            if key in task:
                print(f"    {key:<16}: {task.get(key)}")
