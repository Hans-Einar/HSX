"""Breakpoint management command."""

from __future__ import annotations

import argparse
from typing import List

from .base import Command
from ..context import DebuggerContext
from ..output import emit_error, emit_result


class BreakpointCommand(Command):
    def __init__(self) -> None:
        super().__init__("break", "Manage breakpoints", aliases=("bp",))
        parser = argparse.ArgumentParser(prog="break", add_help=False)
        sub = parser.add_subparsers(dest="subcmd")
        sub.required = True

        add = sub.add_parser("add")
        add.add_argument("pid", type=int)
        add.add_argument("spec")

        clear = sub.add_parser("clear")
        clear.add_argument("pid", type=int)
        clear.add_argument("spec")

        delete = sub.add_parser("delete")
        delete.add_argument("pid", type=int)
        delete.add_argument("bp_id")

        clear_all = sub.add_parser("clearall")
        clear_all.add_argument("pid", type=int)

        lst = sub.add_parser("list")
        lst.add_argument("pid", type=int)

        disable = sub.add_parser("disable")
        disable.add_argument("pid", type=int)
        disable.add_argument("spec")

        enable = sub.add_parser("enable")
        enable.add_argument("pid", type=int)
        enable.add_argument("spec")

        self._parser = parser

    def run(self, ctx: DebuggerContext, argv: List[str]) -> int:
        try:
            args = self._parser.parse_args(argv)
        except SystemExit:
            return 1
        action = args.subcmd
        if action == "add":
            return self._handle_add(ctx, args.pid, args.spec)
        if action == "clear":
            return self._handle_clear(ctx, args.pid, args.spec)
        if action == "delete":
            return self._handle_delete(ctx, args.pid, args.bp_id)
        if action == "clearall":
            return self._handle_clear_all(ctx, args.pid)
        if action == "list":
            return self._handle_list(ctx, args.pid)
        if action == "disable":
            return self._handle_disable(ctx, args.pid, args.spec)
        if action == "enable":
            return self._handle_enable(ctx, args.pid, args.spec)
        return 1

    def _resolve_addresses(self, ctx: DebuggerContext, spec: str) -> List[int]:
        try:
            return [int(spec, 0) & 0xFFFF]
        except ValueError:
            pass
        if ":" in spec:
            path, line_text = spec.rsplit(":", 1)
            try:
                line = int(line_text)
            except ValueError:
                return ctx.lookup_symbol(spec)
            return ctx.lookup_line(path, line)
        return ctx.lookup_symbol(spec)

    def _resolve_spec_or_id(self, ctx: DebuggerContext, pid: int, spec: str) -> List[int]:
        bp_id = ctx.breakpoint_id_for(pid, spec)
        if bp_id is not None:
            addr = ctx.breakpoint_address_for_id(pid, bp_id)
            return [addr] if addr is not None else []
        return self._resolve_addresses(ctx, spec)

    def _handle_add(self, ctx: DebuggerContext, pid: int, spec: str) -> int:
        addresses = self._resolve_addresses(ctx, spec)
        if not addresses:
            emit_error(ctx, message=f"Unable to resolve breakpoint '{spec}'")
            return 1
        session = ctx.ensure_session()
        added: List[int] = []
        ids: List[int] = []
        for addr in addresses:
            try:
                response = session.request({"cmd": "bp", "op": "set", "pid": pid, "addr": addr})
            except Exception as exc:
                emit_error(ctx, message=f"break add failed: {exc}")
                return 2
            if response.get("status") != "ok":
                emit_error(ctx, message=response.get("error", "break add failed"), data=response)
                return 1
            added.append(addr)
            ids.append(ctx.register_breakpoint(pid, addr))
        emit_result(ctx, message=f"Breakpoints set at {added}", data={"pid": pid, "addresses": added, "ids": ids})
        return 0

    def _handle_clear(self, ctx: DebuggerContext, pid: int, spec: str) -> int:
        addresses = self._resolve_spec_or_id(ctx, pid, spec)
        if not addresses:
            emit_error(ctx, message=f"Unable to resolve breakpoint '{spec}'")
            return 1
        session = ctx.ensure_session()
        for addr in addresses:
            try:
                response = session.request({"cmd": "bp", "op": "clear", "pid": pid, "addr": addr})
            except Exception as exc:
                emit_error(ctx, message=f"break clear failed: {exc}")
                return 2
            if response.get("status") != "ok":
                emit_error(ctx, message=response.get("error", "break clear failed"), data=response)
                return 1
            ctx.forget_breakpoint(pid, addr)
        emit_result(ctx, message=f"Breakpoints cleared: {addresses}", data={"pid": pid, "addresses": addresses})
        return 0

    def _handle_delete(self, ctx: DebuggerContext, pid: int, bp_id: str) -> int:
        bp_int = ctx.breakpoint_id_for(pid, f"#{bp_id}")
        if bp_int is None:
            emit_error(ctx, message=f"Unknown breakpoint id {bp_id}")
            return 1
        address = ctx.breakpoint_address_for_id(pid, bp_int)
        if address is None:
            emit_error(ctx, message=f"No address for breakpoint id {bp_id}")
            return 1
        return self._handle_clear(ctx, pid, f"0x{address:04X}")

    def _handle_clear_all(self, ctx: DebuggerContext, pid: int) -> int:
        session = ctx.ensure_session()
        try:
            response = session.request({"cmd": "bp", "op": "clear_all", "pid": pid})
        except Exception as exc:
            emit_error(ctx, message=f"break clearall failed: {exc}")
            return 2
        if response.get("status") != "ok":
            emit_error(ctx, message=response.get("error", "break clearall failed"), data=response)
            return 1
        ctx._breakpoint_ids.pop(pid, None)
        ctx._breakpoint_lookup.pop(pid, None)
        emit_result(ctx, message="All breakpoints cleared", data={"pid": pid})
        return 0

    def _handle_list(self, ctx: DebuggerContext, pid: int) -> int:
        session = ctx.ensure_session()
        try:
            response = session.request({"cmd": "bp", "op": "list", "pid": pid})
        except Exception as exc:
            emit_error(ctx, message=f"break list failed: {exc}")
            return 2
        if response.get("status") != "ok":
            emit_error(ctx, message=response.get("error", "break list failed"), data=response)
            return 1
        breakpoints = response.get("breakpoints", [])
        rows = []
        for addr in breakpoints:
            bp_id = ctx.register_breakpoint(pid, int(addr))
            rows.append({"id": bp_id, "address": int(addr)})
        emit_result(ctx, message="breakpoints", data={"pid": pid, "breakpoints": rows})
        if not ctx.json_output:
            print(f"breakpoints for pid {pid}:")
            if not rows:
                print("  (none)")
            else:
                disabled = ctx.disabled_breakpoints.get(pid, set())
                for row in rows:
                    addr = row["address"]
                    bp_id = row["id"]
                    marker = "" if addr not in disabled else " (disabled)"
                    print(f"  #{bp_id:<3} 0x{addr:04X}{marker}")
            disabled_only = sorted(ctx.disabled_breakpoints.get(pid, set()) - {row["address"] for row in rows})
            if disabled_only:
                print("  disabled (not set on executive):")
                for addr in disabled_only:
                    print(f"    0x{addr:04X}")
        return 0

    def _handle_disable(self, ctx: DebuggerContext, pid: int, spec: str) -> int:
        addresses = self._resolve_spec_or_id(ctx, pid, spec)
        if not addresses:
            emit_error(ctx, message=f"Unable to resolve breakpoint '{spec}'")
            return 1
        session = ctx.ensure_session()
        for addr in addresses:
            try:
                response = session.request({"cmd": "bp", "op": "clear", "pid": pid, "addr": addr})
            except Exception as exc:
                emit_error(ctx, message=f"break disable failed: {exc}")
                return 2
            if response.get("status") != "ok":
                emit_error(ctx, message=response.get("error", "break disable failed"), data=response)
                return 1
            ctx.disabled_breakpoints.setdefault(pid, set()).add(addr)
        emit_result(ctx, message=f"Breakpoints disabled: {addresses}", data={"pid": pid, "addresses": addresses})
        return 0

    def _handle_enable(self, ctx: DebuggerContext, pid: int, spec: str) -> int:
        addresses = self._resolve_spec_or_id(ctx, pid, spec)
        if not addresses:
            emit_error(ctx, message=f"Unable to resolve breakpoint '{spec}'")
            return 1
        disabled = ctx.disabled_breakpoints.get(pid, set())
        session = ctx.ensure_session()
        for addr in addresses:
            try:
                response = session.request({"cmd": "bp", "op": "set", "pid": pid, "addr": addr})
            except Exception as exc:
                emit_error(ctx, message=f"break enable failed: {exc}")
                return 2
            if response.get("status") != "ok":
                emit_error(ctx, message=response.get("error", "break enable failed"), data=response)
                return 1
            disabled.discard(addr)
            ctx.register_breakpoint(pid, addr)
        emit_result(ctx, message=f"Breakpoints enabled: {addresses}", data={"pid": pid, "addresses": addresses})
        return 0
