"""Interactive REPL for hsx-dbg."""

from __future__ import annotations

import logging
from typing import Optional

from .commands import CommandRegistry
from .commands.help import HelpCommand
from .context import DebuggerContext
from .history import HistoryStore
from .parser import split_command

try:
    from .completion import DebuggerCompleter
except Exception:  # pragma: no cover - prompt_toolkit missing
    DebuggerCompleter = None  # type: ignore

LOGGER = logging.getLogger("hsx_dbg.repl")

try:
    from prompt_toolkit import PromptSession
    from prompt_toolkit.history import InMemoryHistory
    from prompt_toolkit.patch_stdout import patch_stdout
except ImportError:  # pragma: no cover - fallback path
    PromptSession = None  # type: ignore
    InMemoryHistory = None  # type: ignore
    patch_stdout = None

try:  # pragma: no cover - optional dependency
    import readline
except ImportError:  # pragma: no cover
    readline = None


class DebuggerREPL:
    """Minimal prompt-toolkit REPL with fallback to input()."""

    def __init__(
        self,
        ctx: DebuggerContext,
        registry: CommandRegistry,
        *,
        history_store: Optional[HistoryStore] = None,
    ) -> None:
        self.ctx = ctx
        self.registry = registry
        self.history_store = history_store
        help_command = self.registry.get("help")
        if isinstance(help_command, HelpCommand):
            help_command.bind(registry)
        self._readline_enabled = False

    def run(self) -> int:
        if PromptSession is None:
            return self._fallback_loop()
        history = None
        if InMemoryHistory is not None:
            history = InMemoryHistory()
            if self.history_store:
                for entry in self.history_store.snapshot():
                    history.append_string(entry)
        completer = None
        if DebuggerCompleter is not None:
            try:
                completer = DebuggerCompleter(self.ctx, self.registry)
            except RuntimeError:
                completer = None
        session = PromptSession("> ", history=history, completer=completer, complete_while_typing=True)
        buffer: list[str] = []
        while True:
            try:
                with patch_stdout():
                    line = session.prompt()
            except (EOFError, KeyboardInterrupt):
                print()
                return 0
            if self._handle_multiline(buffer, line):
                continue
            payload = " ".join(buffer) if buffer else line
            buffer.clear()
            self._record_history(payload)
            self._dispatch(payload)

    def _fallback_loop(self) -> int:
        buffer: list[str] = []
        use_readline = bool(readline and self.history_store)
        if use_readline:
            for entry in self.history_store.snapshot():
                try:
                    readline.add_history(entry)
                except Exception:
                    break
        self._readline_enabled = use_readline
        while True:
            try:
                line = input("> ")
            except (EOFError, KeyboardInterrupt):
                print()
                return 0
            if self._handle_multiline(buffer, line):
                continue
            payload = " ".join(buffer) if buffer else line
            buffer.clear()
            self._record_history(payload)
            self._dispatch(payload)

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
        cmd_name = self.ctx.resolve_alias(cmd_name)
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

    def _handle_multiline(self, buffer: list[str], line: str) -> bool:
        stripped = line.rstrip()
        if stripped.endswith("\\"):
            buffer.append(stripped[:-1])
            return True
        if buffer:
            buffer.append(stripped)
            return False
        return False

    def _record_history(self, entry: str) -> None:
        stripped = entry.strip()
        if not stripped:
            return
        if self.history_store:
            self.history_store.append(stripped)
        if self._readline_enabled and readline:
            try:
                readline.add_history(stripped)
                if self.history_store:
                    limit = self.history_store.limit
                    while readline.get_current_history_length() > limit:
                        readline.remove_history_item(0)
            except Exception:
                pass
