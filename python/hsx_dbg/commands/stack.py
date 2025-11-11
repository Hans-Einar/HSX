"""Stack inspection command."""

from __future__ import annotations

import argparse
from typing import Dict, List

from .base import Command
from ..context import DebuggerContext
from ..output import emit_error, emit_result


class StackCommand(Command):
    def __init__(self) -> None:
        super().__init__("stack", "Inspect call stack", aliases=("bt",))
        parser = argparse.ArgumentParser(prog="stack", add_help=False)
        sub = parser.add_subparsers(dest="subcmd")
        sub.required = False

        bt = sub.add_parser("bt")
        bt.add_argument("pid", type=int)
        bt.add_argument("--frames", type=int, default=32)

        frame = sub.add_parser("frame")
        frame.add_argument("pid", type=int)
        frame.add_argument("index", type=int)

        up = sub.add_parser("up")
        up.add_argument("pid", type=int)
        up.add_argument("--count", type=int, default=1)

        down = sub.add_parser("down")
        down.add_argument("pid", type=int)
        down.add_argument("--count", type=int, default=1)

        info = sub.add_parser("info")
        info.add_argument("pid", type=int)

        parser.set_defaults(subcmd="bt")
        self._parser = parser

    def run(self, ctx: DebuggerContext, argv: List[str]) -> int:
        try:
            args = self._parser.parse_args(argv)
        except SystemExit:
            return 1
        action = args.subcmd
        if action == "bt":
            return self._handle_bt(ctx, args.pid, args.frames)
        if action == "frame":
            return self._handle_frame(ctx, args.pid, args.index)
        if action == "up":
            return self._handle_step(ctx, args.pid, -abs(args.count))
        if action == "down":
            return self._handle_step(ctx, args.pid, abs(args.count))
        return self._handle_bt(ctx, args.pid, None)

    def _handle_bt(self, ctx: DebuggerContext, pid: int, frames: int | None) -> int:
        session = ctx.ensure_session()
        payload = {"cmd": "stack", "op": "info", "pid": pid}
        if frames is not None:
            payload["max"] = max(1, int(frames))
        try:
            response = session.request(payload)
        except Exception as exc:
            emit_error(ctx, message=f"stack bt failed: {exc}")
            return 2
        if response.get("status") != "ok":
            emit_error(ctx, message=response.get("error", "stack bt failed"), data=response)
            return 1
        stack = response.get("stack") or {}
        ctx.set_stack_cache(pid, stack)
        data = {"stack": stack}
        emit_result(ctx, message="stack", data=data)
        if not ctx.json_output:
            self._render_stack(stack, ctx.current_frames.get(pid, 0))
        return 0

    def _handle_frame(self, ctx: DebuggerContext, pid: int, index: int) -> int:
        if ctx.ensure_session():
            pass
        stack = ctx.get_stack_cache(pid)
        if stack is None:
            return self._handle_bt(ctx, pid, None)
        selected = ctx.select_frame(pid, index)
        self._print_frame(stack, selected)
        emit_result(ctx, message=f"frame {selected}", data={"frame": selected})
        return 0

    def _handle_step(self, ctx: DebuggerContext, pid: int, delta: int) -> int:
        stack = ctx.get_stack_cache(pid)
        if stack is None:
            return self._handle_bt(ctx, pid, None)
        current = ctx.current_frames.get(pid, 0)
        target = current + delta
        selected = ctx.select_frame(pid, target)
        self._print_frame(stack, selected)
        emit_result(ctx, message=f"frame {selected}", data={"frame": selected})
        return 0

    def _render_stack(self, stack: Dict[str, any], selected: int) -> None:
        frames = stack.get("frames") or []
        if not frames:
            print("stack: (no frames)")
            return
        print("stack:")
        for entry in frames:
            idx = entry.get("index")
            if idx is None:
                idx = frames.index(entry)
            marker = "->" if idx == selected else "  "
            pc = entry.get("pc") or 0
            file_value = entry.get("file")
            line = entry.get("line")
            symbol = entry.get("symbol") or {}
            name = symbol.get("name")
            loc = f"{file_value}:{line}" if file_value and line is not None else ""
            label = name or loc or "?"
            print(f"{marker} [{idx:02}] 0x{int(pc) & 0xFFFFFFFF:08X} {label}")

    def _print_frame(self, stack: Dict[str, any], index: int) -> None:
        frames = stack.get("frames") or []
        if not frames:
            print("No frames cached")
            return
        if index < 0 or index >= len(frames):
            print(f"Frame {index} out of range (0-{len(frames)-1})")
            return
        frame = frames[index]
        pc = frame.get("pc") or 0
        sp = frame.get("sp")
        fp = frame.get("fp")
        file_value = frame.get("file")
        line = frame.get("line")
        symbol = frame.get("symbol") or {}
        name = symbol.get("name")
        print(f"frame {index}:")
        print(f"  pc=0x{int(pc) & 0xFFFFFFFF:08X}")
        if sp is not None:
            print(f"  sp=0x{int(sp) & 0xFFFFFFFF:08X}")
        if fp is not None:
            print(f"  fp=0x{int(fp) & 0xFFFFFFFF:08X}")
        if name:
            print(f"  function: {name}")
        if file_value:
            print(f"  location: {file_value}:{line}")
