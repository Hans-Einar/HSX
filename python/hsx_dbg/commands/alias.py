"""Alias management command."""

from __future__ import annotations

import argparse
from typing import List

from .base import Command
from ..context import DebuggerContext
from ..output import emit_result


class AliasCommand(Command):
    def __init__(self) -> None:
        super().__init__("alias", "Manage command aliases")
        parser = argparse.ArgumentParser(prog="alias", add_help=False)
        parser.add_argument("name", nargs="?", help="Alias name")
        parser.add_argument("command", nargs="?", help="Target command")
        parser.add_argument("--clear", action="store_true", help="Clear all aliases")
        self._parser = parser

    def run(self, ctx: DebuggerContext, argv: List[str]) -> int:
        try:
            args = self._parser.parse_args(argv)
        except SystemExit:
            return 1
        if args.clear:
            ctx.aliases.clear()
            emit_result(ctx, message="Aliases cleared", data={"aliases": {}})
            return 0
        if args.name and args.command:
            ctx.set_alias(args.name, args.command)
            emit_result(ctx, message=f"{args.name} -> {args.command}", data={"aliases": ctx.list_aliases()})
            return 0
        aliases = ctx.list_aliases()
        if not ctx.json_output:
            if not aliases:
                print("No aliases defined")
            else:
                print("Aliases:")
                for alias, command in sorted(aliases.items()):
                    print(f"  {alias}={command}")
        emit_result(ctx, message="aliases", data={"aliases": aliases})
        return 0
