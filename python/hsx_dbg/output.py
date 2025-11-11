"""Output helpers for hsx-dbg."""

from __future__ import annotations

import json
from typing import Any, Dict, Iterable, Mapping, Optional, Sequence

from .context import DebuggerContext


def _json_dump(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, indent=2, sort_keys=True)


def emit_result(ctx: DebuggerContext, *, message: str, data: Optional[Mapping[str, Any]] = None) -> None:
    """Emit a successful command result."""
    if ctx.json_output:
        payload: Dict[str, Any] = {"status": "ok"}
        if data is not None:
            payload["result"] = data
        else:
            payload["message"] = message
        print(_json_dump(payload))
    else:
        print(message)


def emit_error(ctx: DebuggerContext, *, message: str, data: Optional[Mapping[str, Any]] = None) -> None:
    """Emit an error message respecting JSON mode."""
    payload: Dict[str, Any] = {"status": "error", "error": message}
    if data:
        payload["details"] = dict(data)
    if ctx.json_output:
        print(_json_dump(payload))
    else:
        print(f"error: {message}")


def normalise_task_list(tasks_block: Any) -> list[Dict[str, Any]]:
    """Extract task entries from the various shapes used by the executive."""
    tasks: list[Dict[str, Any]] = []
    if isinstance(tasks_block, dict):
        entries = tasks_block.get("tasks")
        if isinstance(entries, list):
            tasks = [entry for entry in entries if isinstance(entry, dict)]
    elif isinstance(tasks_block, list):
        tasks = [entry for entry in tasks_block if isinstance(entry, dict)]
    return tasks


def render_task_table(
    task_list: Sequence[Mapping[str, Any]],
    *,
    current_pid: Optional[int] = None,
    show_metadata: bool = True,
) -> None:
    """Print a task table."""
    if not task_list:
        print("  tasks: (none)")
        return
    header = "      PID   State         Prio  Quantum  Steps     Sleep  Trace  App"
    if show_metadata:
        header += "        Metadata"
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
        trace = "on" if task.get("trace") else "off"
        app = task.get("app_name") or task.get("program", "")
        marker = "*" if current_pid is not None and pid == current_pid else " "
        row = f"    {marker} {pid!s:4}  {str(state):<12}  {prio!s:>4}  {quantum!s:>7}  {steps_val!s:>8}  {str(sleep):<5}  {trace:>5}  {app}"
        if show_metadata:
            metadata = _format_metadata(task.get("metadata"))
            row += f"  {metadata}"
        print(row)


def render_task_detail(task: Mapping[str, Any]) -> None:
    """Render detailed task info."""
    pid = task.get("pid")
    state = task.get("state")
    app = task.get("app_name") or task.get("program")
    print(f"  task pid={pid} state={state} app={app}")
    for key in ("priority", "accounted_steps", "accounted_cycles", "sleep_pending", "exit_status"):
        if key in task:
            print(f"    {key:<16}: {task.get(key)}")
    metadata_text = _format_metadata(task.get("metadata"))
    if metadata_text:
        print(f"    metadata         : {metadata_text}")


def _format_metadata(metadata: Any) -> str:
    if not isinstance(metadata, Mapping):
        return ""
    parts: list[str] = []
    for key in ("values", "commands", "mailboxes"):
        value = metadata.get(key)
        if value:
            abbrev = {"values": "V", "commands": "C", "mailboxes": "M"}[key]
            parts.append(f"{abbrev}:{value}")
    return ", ".join(parts)


def render_register_block(registers: Any, *, label: str = "registers") -> None:
    """Render a register list if present."""
    if not isinstance(registers, Mapping):
        return
    regs = registers.get("regs") or registers.get("registers")
    if not isinstance(regs, Sequence):
        return
    print(f"  {label}:")
    for idx, value in enumerate(regs):
        try:
            number = int(value)
        except (TypeError, ValueError):
            number = 0
        print(f"    R{idx:02}: 0x{number & 0xFFFFFFFF:08X}")


__all__ = [
    "emit_result",
    "emit_error",
    "normalise_task_list",
    "render_task_table",
    "render_task_detail",
    "render_register_block",
]
