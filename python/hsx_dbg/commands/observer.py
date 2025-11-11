"""Observer mode command."""

from __future__ import annotations

import argparse
from typing import List

from .base import Command
from ..context import DebuggerContext
from ..output import emit_result


class ObserverCommand(Command):
    def __init__(self) -> None:
        super().__init__("observer", "Toggle observer (read-only) mode")
        parser = argparse.ArgumentParser(prog="observer", add_help=False)
        parser.add_argument("state", nargs="?", choices=["on", "off", "status"], default="status")
        self._parser = parser

    def run(self, ctx: DebuggerContext, argv: List[str]) -> int:
        try:
            args = self._parser.parse_args(argv)
        except SystemExit:
            return 1
        if args.state == "status":
            emit_result(
                ctx,
                message=f"observer mode: {'on' if ctx.observer_mode else 'off'}",
                data={"observer": ctx.observer_mode},
            )
            if not ctx.json_output:
                print(f"Observer mode is {'enabled' if ctx.observer_mode else 'disabled'}")
            return 0
        if args.state == "on":
            ctx.observer_mode = True
            ctx.disconnect()
            emit_result(ctx, message="Observer mode enabled", data={"observer": True})
            if not ctx.json_output:
                print("Observer mode enabled (detach skipped)")
            return 0
        ctx.observer_mode = False
        emit_result(ctx, message="Observer mode disabled", data={"observer": False})
        if not ctx.json_output:
            print("Observer mode disabled")
        return 0
