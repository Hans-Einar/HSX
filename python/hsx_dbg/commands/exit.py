"""Exit command."""

from __future__ import annotations

from typing import List

from .base import Command
from ..context import DebuggerContext


class ExitCommand(Command):
    def __init__(self) -> None:
        super().__init__("exit", "Exit the debugger", aliases=("quit", "q"))

    def run(self, ctx: DebuggerContext, argv: List[str]) -> int:
        ctx.disconnect()
        raise SystemExit(0)
