"""Command registry for hsx-dbg."""

from __future__ import annotations

from typing import Dict, Iterable, List, Optional

from .base import Command
from .alias import AliasCommand
from .attach import AttachCommand
from .connect import ConnectCommand
from .control import ContinueCommand, PauseCommand, StepCommand
from .detach import DetachCommand
from .exit import ExitCommand
from .help import HelpCommand
from .info import InfoCommand
from .status import StatusCommand
from .session import SessionCommand
from .ps import PsCommand
from .observer import ObserverCommand


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
        SessionCommand(),
        AttachCommand(),
        DetachCommand(),
        PauseCommand(),
        ContinueCommand(),
        StepCommand(),
        PsCommand(),
        InfoCommand(),
        ObserverCommand(),
        AliasCommand(),
        ExitCommand(),
    ]
    for command in commands:
        registry.register(command)
        bind = getattr(command, "bind", None)
        if callable(bind):
            bind(registry)
    return registry


__all__ = ["CommandRegistry", "build_registry"]
