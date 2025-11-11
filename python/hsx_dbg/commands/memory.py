"""Memory inspection command."""

from __future__ import annotations

import argparse
from collections.abc import Iterable
from typing import List, Optional

from .base import Command
from ..context import DebuggerContext
from ..output import emit_error, emit_result


class MemoryCommand(Command):
    def __init__(self) -> None:
        super().__init__("mem", "Inspect memory", aliases=("memory", "x"))
        parser = argparse.ArgumentParser(prog="mem", add_help=False)
        sub = parser.add_subparsers(dest="subcmd")
        sub.required = True

        regions = sub.add_parser("regions")
        regions.add_argument("pid", type=int)

        read = sub.add_parser("read")
        read.add_argument("pid", type=int)
        read.add_argument("address", type=str)
        read.add_argument("--count", type=int, default=16)
        read.add_argument("--format", choices=["x", "d", "i", "s"], default="x")
        read.add_argument("--width", type=int, default=4)

        dump = sub.add_parser("dump")
        dump.add_argument("pid", type=int)
        dump.add_argument("start", type=str)
        dump.add_argument("end", type=str)

        self._parser = parser

    def run(self, ctx: DebuggerContext, argv: List[str]) -> int:
        try:
            args = self._parser.parse_args(argv)
        except SystemExit:
            return 1
        action = args.subcmd
        if action == "regions":
            return self._handle_regions(ctx, args.pid)
        if action == "read":
            return self._handle_read(ctx, args.pid, args.address, args.count, args.format, args.width)
        if action == "dump":
            return self._handle_dump(ctx, args.pid, args.start, args.end)
        return 1

    def _handle_regions(self, ctx: DebuggerContext, pid: int) -> int:
        session = ctx.ensure_session()
        try:
            response = session.request({"cmd": "memory", "op": "regions", "pid": pid})
        except Exception as exc:
            emit_error(ctx, message=f"memory regions failed: {exc}")
            return 2
        if response.get("status") != "ok":
            emit_error(ctx, message=response.get("error", "memory regions failed"), data=response)
            return 1
        emit_result(ctx, message="memory regions", data=response)
        if not ctx.json_output:
            regions = response.get("regions") or []
            print("regions:")
            for region in regions:
                start = region.get("start")
                end = region.get("end")
                kind = region.get("kind")
                print(f"  0x{int(start):08X}-0x{int(end):08X} {kind}")
        return 0

    def _handle_read(
        self,
        ctx: DebuggerContext,
        pid: int,
        address: str,
        count: int,
        fmt: str,
        width: int = 4,
    ) -> int:
        session = ctx.ensure_session()
        payload = {
            "cmd": "memory",
            "op": "read",
            "pid": pid,
            "address": address,
            "count": max(1, int(count)),
            "format": fmt,
            "width": max(1, int(width)),
        }
        try:
            response = session.request(payload)
        except Exception as exc:
            emit_error(ctx, message=f"memory read failed: {exc}")
            return 2
        if response.get("status") != "ok":
            emit_error(ctx, message=response.get("error", "memory read failed"), data=response)
            return 1
        emit_result(ctx, message="memory", data=response)
        if not ctx.json_output:
            data = response.get("data") or []
            if fmt == "s":
                print(data)
            elif fmt == "i":
                for entry in data:
                    print(entry)
            else:
                for entry in data:
                    addr = self._coerce_int(entry.get("address"))
                    value = entry.get("value")
                    addr_text = f"0x{addr:08X}" if addr is not None else str(entry.get("address"))
                    print(f"{addr_text}: {value}")
        return 0

    def _handle_dump(self, ctx: DebuggerContext, pid: int, start: str, end: str) -> int:
        session = ctx.ensure_session()
        start_int = self._coerce_int(start)
        end_int = self._coerce_int(end)
        if start_int is not None and end_int is not None and end_int <= start_int:
            emit_error(ctx, message="end must be greater than start for dump")
            return 1
        payload = {
            "cmd": "memory",
            "op": "dump",
            "pid": pid,
            "start": start,
            "end": end,
        }
        try:
            response = session.request(payload)
        except Exception as exc:
            emit_error(ctx, message=f"memory dump failed: {exc}")
            return 2
        if response.get("status") != "ok":
            emit_error(ctx, message=response.get("error", "memory dump failed"), data=response)
            return 1
        emit_result(ctx, message="memory dump", data=response)
        if not ctx.json_output:
            block = response.get("dump")
            if not isinstance(block, dict):
                block = response
            self._render_dump(block, start_int)
        return 0

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

    def _render_dump(self, block: dict, fallback_start: Optional[int]) -> None:
        data = self._decode_bytes(block)
        if data is not None and data:
            width = self._coerce_int(block.get("width")) or 16
            start_addr = self._coerce_int(block.get("start")) or fallback_start or 0
            for offset in range(0, len(data), width):
                chunk = data[offset : offset + width]
                hex_text = " ".join(f"{byte:02X}" for byte in chunk)
                padding = width - len(chunk)
                if padding > 0:
                    hex_text += "   " * padding
                ascii_text = "".join(chr(byte) if 32 <= byte < 127 else "." for byte in chunk)
                address = (start_addr + offset) & 0xFFFFFFFF
                print(f"0x{address:08X}: {hex_text}  {ascii_text}")
            return
        lines = block.get("lines")
        if isinstance(lines, Iterable) and not isinstance(lines, (str, bytes)):
            for entry in lines:
                if not isinstance(entry, dict):
                    print(entry)
                    continue
                addr = self._coerce_int(entry.get("address"))
                text = entry.get("text") or entry.get("hex") or entry.get("data") or ""
                ascii_text = entry.get("ascii")
                addr_text = f"0x{addr:08X}" if addr is not None else str(entry.get("address"))
                suffix = f"  {ascii_text}" if ascii_text else ""
                print(f"{addr_text}: {text}{suffix}")
            return
        hex_text = block.get("hex") or block.get("data")
        if isinstance(hex_text, str):
            print(hex_text)
        else:
            print("<no data>")

    def _decode_bytes(self, block: dict) -> Optional[bytes]:
        data_list = block.get("bytes")
        if isinstance(data_list, Iterable) and not isinstance(data_list, (str, bytes)):
            try:
                return bytes(int(value) & 0xFF for value in data_list)  # type: ignore[arg-type]
            except (TypeError, ValueError):
                return None
        hex_blob = block.get("data") or block.get("hex")
        if isinstance(hex_blob, str):
            cleaned = "".join(hex_blob.split())
            if not cleaned:
                return b""
            try:
                return bytes.fromhex(cleaned)
            except ValueError:
                return None
        lines = block.get("lines")
        if isinstance(lines, Iterable) and not isinstance(lines, (str, bytes)):
            chunks: bytearray = bytearray()
            for entry in lines:
                if not isinstance(entry, dict):
                    continue
                bytes_field = entry.get("bytes")
                if isinstance(bytes_field, Iterable) and not isinstance(bytes_field, (str, bytes)):
                    try:
                        chunks.extend(int(value) & 0xFF for value in bytes_field)
                        continue
                    except (TypeError, ValueError):
                        continue
                text = entry.get("data") or entry.get("hex") or entry.get("text")
                if isinstance(text, str):
                    cleaned = "".join(text.split())
                    try:
                        chunks.extend(bytes.fromhex(cleaned))
                    except ValueError:
                        continue
            return bytes(chunks) if chunks else None
        return None
