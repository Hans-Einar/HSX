"""Watch management command."""

from __future__ import annotations

import argparse
from typing import List

from .base import Command
from ..context import DebuggerContext
from ..output import emit_error, emit_result


class WatchCommand(Command):
    def __init__(self) -> None:
        super().__init__("watch", "Manage watch expressions")
        parser = argparse.ArgumentParser(prog="watch", add_help=False)
        sub = parser.add_subparsers(dest="subcmd")
        sub.required = True

        add = sub.add_parser("add")
        add.add_argument("pid", type=int)
        add.add_argument("expr")

        remove = sub.add_parser("remove")
        remove.add_argument("pid", type=int)
        remove.add_argument("watch_id", type=int)

        lst = sub.add_parser("list")
        lst.add_argument("pid", type=int)

        self._parser = parser

    def run(self, ctx: DebuggerContext, argv: List[str]) -> int:
        try:
            args = self._parser.parse_args(argv)
        except SystemExit:
            return 1
        if args.subcmd == "add":
            return self._handle_add(ctx, args.pid, args.expr)
        if args.subcmd == "remove":
            return self._handle_remove(ctx, args.pid, args.watch_id)
        return self._handle_list(ctx, args.pid)

    def _handle_add(self, ctx: DebuggerContext, pid: int, expr: str) -> int:
        session = ctx.ensure_session()
        try:
            response = session.request({"cmd": "watch", "op": "add", "pid": pid, "expr": expr})
        except Exception as exc:
            emit_error(ctx, message=f"watch add failed: {exc}")
            return 2
        if response.get("status") != "ok":
            emit_error(ctx, message=response.get("error", "watch add failed"), data=response)
            return 1
        watch = response.get("watch") or {}
        emit_result(ctx, message=f"Watch added: {watch}", data={"watch": watch})
        if not ctx.json_output:
            print(f"watch {watch.get('watch_id')}: {expr} -> {watch.get('value')}")
        return 0

    def _handle_remove(self, ctx: DebuggerContext, pid: int, watch_id: int) -> int:
        session = ctx.ensure_session()
        try:
            response = session.request({"cmd": "watch", "op": "remove", "pid": pid, "watch_id": watch_id})
        except Exception as exc:
            emit_error(ctx, message=f"watch remove failed: {exc}")
            return 2
        if response.get("status") != "ok":
            emit_error(ctx, message=response.get("error", "watch remove failed"), data=response)
            return 1
        emit_result(ctx, message=f"Watch {watch_id} removed", data={"watch_id": watch_id})
        if not ctx.json_output:
            print(f"watch {watch_id} removed")
        return 0

    def _handle_list(self, ctx: DebuggerContext, pid: int) -> int:
        session = ctx.ensure_session()
        try:
            response = session.request({"cmd": "watch", "op": "list", "pid": pid})
        except Exception as exc:
            emit_error(ctx, message=f"watch list failed: {exc}")
            return 2
        if response.get("status") != "ok":
            emit_error(ctx, message=response.get("error", "watch list failed"), data=response)
            return 1
        watches = response.get("watches", [])
        emit_result(ctx, message="watches", data={"watches": watches})
        if not ctx.json_output:
            print("watches:")
            if not watches:
                print("  (none)")
            else:
                for entry in watches:
                    wid = entry.get("watch_id")
                    expr = entry.get("expr")
                    value = entry.get("value")
                    print(f"  {wid}: {expr} -> {value}")
        return 0
