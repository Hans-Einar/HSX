"""Command base classes for hsx-dbg."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Sequence

from ..context import DebuggerContext
from ..parser import split_command


@dataclass
class Command:
    """Abstract command description."""

    name: str
    description: str
    aliases: Sequence[str] = field(default_factory=tuple)

    def run(self, ctx: DebuggerContext, argv: List[str]) -> int:
        raise NotImplementedError("Command must implement run()")

    def format_help(self) -> str:
        return f"{self.name:<12} {self.description}"

    def parse(self, line: str) -> List[str]:
        return split_command(line)
