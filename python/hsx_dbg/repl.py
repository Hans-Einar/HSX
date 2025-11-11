"""Interactive REPL for hsx-dbg."""

from __future__ import annotations

import logging
from typing import Optional

from .commands import CommandRegistry
from .commands.help import HelpCommand
from .context import DebuggerContext
from .parser import split_command

LOGGER = logging.getLogger("hsx_dbg.repl")

try:
    from prompt_toolkit import PromptSession
    from prompt_toolkit.history import FileHistory
    from prompt_toolkit.patch_stdout import patch_stdout
except ImportError:  # pragma: no cover - fallback path
    PromptSession = None  # type: ignore
    FileHistory = None
    patch_stdout = None


class DebuggerREPL:
    """Minimal prompt-toolkit REPL with fallback to input()."""

    def __init__(self, ctx: DebuggerContext, registry: CommandRegistry, *, history_path: Optional[str] = None) -> None:
        self.ctx = ctx
        self.registry = registry
        self.history_path = history_path
        help_command = self.registry.get("help")
        if isinstance(help_command, HelpCommand):
            help_command.bind(registry)

    def run(self) -> int:
        if PromptSession is None:
            return self._fallback_loop()
        history = FileHistory(self.history_path) if (self.history_path and FileHistory) else None
        session = PromptSession("> ", history=history)
        while True:
            try:
                with patch_stdout():
                    line = session.prompt()
            except (EOFError, KeyboardInterrupt):
                print()
                return 0
            self._dispatch(line)

    def _fallback_loop(self) -> int:
        while True:
            try:
                line = input("> ")
            except (EOFError, KeyboardInterrupt):
                print()
                return 0
            self._dispatch(line)

    def _dispatch(self, line: str) -> None:
        stripped = line.strip()
        if not stripped:
            return
        argv = split_command(stripped)
        if not argv:
            return
        cmd_name, *cmd_args = argv
        if cmd_name.startswith("#parse-error"):
            print(f"Parse error: {cmd_args[-1] if cmd_args else cmd_name}")
            return
        command = self.registry.get(cmd_name)
        if not command:
            print(f"Unknown command: {cmd_name}")
            return
        try:
            command.run(self.ctx, cmd_args)
        except SystemExit:
            raise
        except Exception as exc:  # pragma: no cover - defensive logging
            LOGGER.exception("command failed")
            print(f"Command '{cmd_name}' failed: {exc}")
