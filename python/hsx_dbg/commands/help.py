"""Help command."""

from __future__ import annotations

from typing import TYPE_CHECKING, List

from .base import Command
from ..context import DebuggerContext

if TYPE_CHECKING:  # pragma: no cover
    from . import CommandRegistry


class HelpCommand(Command):
    def __init__(self) -> None:
        super().__init__("help", "Show available commands", aliases=("?",))
        self._registry: CommandRegistry | None = None

    def bind(self, registry: "CommandRegistry") -> None:
        self._registry = registry

    def run(self, ctx: DebuggerContext, argv: List[str]) -> int:
        registry = self._registry
        if not registry:
            return 1
        for command in registry.list_commands():
            print(command.format_help())
        return 0
