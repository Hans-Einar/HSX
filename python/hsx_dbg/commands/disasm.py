"""Disassembly command."""

from __future__ import annotations

import argparse
from typing import List, Optional

from .base import Command
from ..context import DebuggerContext
from ..output import emit_error, emit_result


class DisasmCommand(Command):
    def __init__(self) -> None:
        super().__init__("disasm", "Disassemble instructions")
        parser = argparse.ArgumentParser(prog="disasm", add_help=False)
        parser.add_argument("pid", type=int)
        parser.add_argument("spec", nargs="?", help="Address or symbol")
        parser.add_argument("--count", type=int, default=16)
        parser.add_argument("--source", action="store_true", help="Show source lines")
        self._parser = parser

    def run(self, ctx: DebuggerContext, argv: List[str]) -> int:
        try:
            args = self._parser.parse_args(argv)
        except SystemExit:
            return 1
        session = ctx.ensure_session()
        payload = {"cmd": "disasm", "pid": args.pid, "op": "read", "count": max(1, args.count)}
        if args.spec:
            payload["spec"] = args.spec
        if args.source:
            payload["source"] = True
        try:
            response = session.request(payload)
        except Exception as exc:
            emit_error(ctx, message=f"disasm failed: {exc}")
            return 2
        if response.get("status") != "ok":
            emit_error(ctx, message=response.get("error", "disasm failed"), data=response)
            return 1
        emit_result(ctx, message="disasm", data=response)
        if not ctx.json_output:
            self._render_disasm(response)
        return 0

    def _render_disasm(self, response: dict) -> None:
        instructions = response.get("instructions") or []
        if not isinstance(instructions, list):
            print("<no instructions>")
            return
        current_pc = self._coerce_int(response.get("current_pc"))
        for entry in instructions:
            if not isinstance(entry, dict):
                print(entry)
                continue
            pc = self._coerce_int(entry.get("pc"))
            if pc is None:
                print(entry)
                continue
            marker = "=>" if self._is_current(entry, current_pc) else "  "
            text = self._format_instruction(entry)
            annotation = self._format_annotation(entry)
            source = self._format_source(entry)
            line = f"{marker} 0x{pc & 0xFFFFFFFF:08X}: {text}{annotation}"
            if source:
                line += f"    # {source}"
            print(line)

    @staticmethod
    def _coerce_int(value: object) -> Optional[int]:
        if isinstance(value, int):
            return value
        if isinstance(value, str):
            try:
                return int(value, 0)
            except ValueError:
                return None
        return None

    def _is_current(self, entry: dict, current_pc: Optional[int]) -> bool:
        if entry.get("current") or entry.get("is_current") or entry.get("is_pc"):
            return True
        marker = entry.get("marker")
        if isinstance(marker, str) and marker.strip() in {"=>", "*", "pc"}:
            return True
        pc = self._coerce_int(entry.get("pc"))
        if pc is None or current_pc is None:
            return False
        return pc == current_pc

    @staticmethod
    def _format_instruction(entry: dict) -> str:
        text = entry.get("text")
        if isinstance(text, str) and text.strip():
            return text
        mnemonic = entry.get("mnemonic")
        operands = entry.get("operands")
        if isinstance(mnemonic, str):
            if operands:
                return f"{mnemonic} {operands}"
            return mnemonic
        word = entry.get("word")
        if isinstance(word, int):
            return f"0x{word & 0xFFFFFFFF:08X}"
        return "<unknown>"

    def _format_annotation(self, entry: dict) -> str:
        symbol = entry.get("symbol")
        symbol_name = None
        symbol_offset: Optional[int] = None
        if isinstance(symbol, dict):
            symbol_name = symbol.get("name") or symbol.get("symbol")
            symbol_offset = self._coerce_int(symbol.get("offset"))
        elif isinstance(symbol, str):
            symbol_name = symbol
        if symbol_name is None:
            symbol_name = entry.get("function") or entry.get("label")
        if symbol_name:
            if symbol_offset is None:
                offset_value = self._coerce_int(entry.get("symbol_offset") or entry.get("offset"))
            else:
                offset_value = symbol_offset
            if offset_value:
                return f"  <{symbol_name}+0x{offset_value:X}>"
            return f"  <{symbol_name}>"
        return ""

    def _format_source(self, entry: dict) -> Optional[str]:
        source = entry.get("source")
        file = line = None
        if isinstance(source, dict):
            file = source.get("file")
            line = source.get("line")
        elif isinstance(source, str):
            return source
        if file is None:
            file = entry.get("file")
            line = entry.get("line")
        if file is None:
            return None
        if line is None:
            return str(file)
        return f"{file}:{line}"
