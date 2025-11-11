"""Symbols command."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import List

from .base import Command
from ..context import DebuggerContext
from ..output import emit_error, emit_result


class SymbolsCommand(Command):
    def __init__(self) -> None:
        super().__init__("symbols", "Show or set symbol file path")
        parser = argparse.ArgumentParser(prog="symbols", add_help=False)
        parser.add_argument("path", nargs="?", help="Path to .sym file")
        self._parser = parser

    def run(self, ctx: DebuggerContext, argv: List[str]) -> int:
        try:
            args = self._parser.parse_args(argv)
        except SystemExit:
            return 1
        if not args.path:
            data = {"symbol_path": str(ctx.symbol_path) if ctx.symbol_path else None}
            emit_result(ctx, message=f"symbols: {data['symbol_path']}", data=data)
            if not ctx.json_output:
                print(f"Symbol file: {data['symbol_path'] or '(unset)'}")
            return 0
        try:
            ctx.set_symbol_file(args.path)
        except Exception as exc:
            emit_error(ctx, message=f"failed to load symbols: {exc}")
            return 1
        emit_result(ctx, message=f"Symbols set to {ctx.symbol_path}", data={"symbol_path": str(ctx.symbol_path)})
        if not ctx.json_output:
            print(f"Symbols loaded from {ctx.symbol_path}")
        return 0
