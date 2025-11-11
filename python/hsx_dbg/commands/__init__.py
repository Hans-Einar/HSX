"""Command registry for hsx-dbg."""

from __future__ import annotations

from typing import Dict, Iterable, List, Optional

from .base import Command
from .connect import ConnectCommand
from .exit import ExitCommand
from .help import HelpCommand
from .status import StatusCommand


class CommandRegistry:
    """Stores the known commands and resolves aliases."""

    def __init__(self) -> None:
        self._commands: Dict[str, Command] = {}
        self._ordered: List[Command] = []

    def register(self, command: Command) -> None:
        self._ordered.append(command)
        self._commands[command.name] = command
        for alias in command.aliases:
            self._commands[alias] = command

    def get(self, name: str) -> Optional[Command]:
        return self._commands.get(name)

    def list_commands(self) -> Iterable[Command]:
        return self._ordered


def build_registry() -> CommandRegistry:
    registry = CommandRegistry()
    commands = [
        HelpCommand(),
        ConnectCommand(),
        StatusCommand(),
        ExitCommand(),
    ]
    for command in commands:
        registry.register(command)
        bind = getattr(command, "bind", None)
        if callable(bind):
            bind(registry)
    return registry


__all__ = ["CommandRegistry", "build_registry"]
