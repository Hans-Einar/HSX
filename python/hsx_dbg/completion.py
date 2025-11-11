"""prompt_toolkit completer for hsx-dbg."""

from __future__ import annotations

import shlex
from typing import Iterable, List, Sequence

from .context import DebuggerContext
from .commands import CommandRegistry

try:
    from prompt_toolkit.completion import Completer, Completion, PathCompleter
    from prompt_toolkit.document import Document
except ImportError:  # pragma: no cover - prompt_toolkit not installed
    Completer = object  # type: ignore[assignment]
    Completion = object  # type: ignore[assignment]
    PathCompleter = None
    Document = object  # type: ignore[assignment]

REGISTERS: Sequence[str] = tuple(
    [f"R{idx:02}" for idx in range(32)] + ["PC", "SP", "FP", "LR", "IP"]
)

_BREAK_SPEC_SUBCMDS = {"add", "clear", "disable", "enable"}
PATH_COMMANDS = {"symbols"}


def _normalise_tokens(text: str) -> List[str]:
    if not text:
        return []
    try:
        tokens = shlex.split(text, posix=True)
        trailing = text[-1].isspace()
    except ValueError:
        tokens = text.strip().split()
        trailing = text.endswith((" ", "\t"))
    if trailing:
        tokens.append("")
    return tokens


if PathCompleter is not None:

    class DebuggerCompleter(Completer):  # type: ignore[misc]
        """Context-aware CLI completer."""

        def __init__(self, ctx: DebuggerContext, registry: CommandRegistry) -> None:
            self.ctx = ctx
            self.registry = registry
            self._path = PathCompleter(expanduser=True)

        def get_completions(self, document: Document, complete_event) -> Iterable[Completion]:
            text = document.text_before_cursor
            tokens = _normalise_tokens(text)
            if not tokens:
                yield from self._command_completions("", document)
                return
            prefix = tokens[-1]
            if len(tokens) == 1:
                yield from self._command_completions(prefix, document)
                return
            command_name = tokens[0]
            resolved = self.ctx.resolve_alias(command_name)
            subcmd = tokens[1] if len(tokens) > 1 else ""
            if self._should_complete_path(resolved, subcmd, len(tokens)):
                yield from self._path.get_completions(document, complete_event)
                return
            candidates: List[str] = []
            if self._should_complete_symbol(resolved, subcmd, len(tokens)):
                candidates.extend(self._symbol_candidates(prefix))
            if self._should_complete_register(prefix):
                candidates.extend(self._register_candidates(prefix))
            if candidates:
                for entry in self._format_candidates(candidates):
                    yield Completion(entry, start_position=-len(prefix))
                return
            if self._looks_like_path(prefix):
                yield from self._path.get_completions(document, complete_event)

        def _command_completions(self, prefix: str, document: Document) -> Iterable[Completion]:
            for entry in self._format_candidates(self._command_names(), prefix):
                yield Completion(entry, start_position=-len(prefix))

        def _command_names(self) -> List[str]:
            names: List[str] = []
            for command in self.registry.list_commands():
                names.append(command.name)
                names.extend(command.aliases)
            return sorted(set(names))

        def _symbol_candidates(self, prefix: str) -> List[str]:
            results = self.ctx.symbol_completions(prefix)
            return results[:64]  # avoid flooding the prompt

        def _register_candidates(self, prefix: str) -> List[str]:
            needle = prefix.lower()
            return [reg for reg in REGISTERS if reg.lower().startswith(needle)]

        @staticmethod
        def _format_candidates(candidates: Iterable[str], prefix: str = "") -> List[str]:
            if not prefix:
                return sorted(dict.fromkeys(candidates))
            needle = prefix.lower()
            ordered = [c for c in candidates if c.lower().startswith(needle)]
            return sorted(dict.fromkeys(ordered))

        @staticmethod
        def _should_complete_symbol(command: str, subcmd: str, token_count: int) -> bool:
            if command in {"disasm"}:
                return token_count >= 3
            if command in {"break", "bp"} and subcmd in _BREAK_SPEC_SUBCMDS:
                return token_count >= 4
            return False

        @staticmethod
        def _should_complete_register(prefix: str) -> bool:
            return bool(prefix) and prefix[0].lower() in {"r", "p", "s", "f", "l"}

        def _should_complete_path(self, command: str, subcmd: str, token_count: int) -> bool:
            if command in PATH_COMMANDS and token_count >= 2:
                return True
            return False

        @staticmethod
        def _looks_like_path(prefix: str) -> bool:
            return prefix.startswith((".", "/", "~"))

else:  # pragma: no cover - prompt_toolkit unavailable

    class DebuggerCompleter:  # type: ignore[override]
        def __init__(self, *args, **kwargs) -> None:
            raise RuntimeError("prompt_toolkit is required for completion support")

