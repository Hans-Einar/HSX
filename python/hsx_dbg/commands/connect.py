"""Connect command implementation."""

from __future__ import annotations

import argparse
from typing import List

from .base import Command
from ..context import DebuggerContext
from ..output import emit_error, emit_result


class ConnectCommand(Command):
    def __init__(self) -> None:
        super().__init__("connect", "Connect to the executive", aliases=("open",))
        self._parser = argparse.ArgumentParser(prog="connect", add_help=False)
        self._parser.add_argument("--host", type=str, help="Executive host")
        self._parser.add_argument("--port", type=int, help="Executive port")
        self._parser.add_argument("--no-events", action="store_true", help="Disable automatic event streaming")

    def run(self, ctx: DebuggerContext, argv: List[str]) -> int:
        try:
            args = self._parser.parse_args(argv)
        except SystemExit:
            return 1
        if args.host:
            ctx.host = args.host
        if args.port:
            ctx.port = args.port
        try:
            ctx.ensure_session(auto_events=not args.no_events)
        except Exception as exc:
            emit_error(ctx, message=f"connect failed: {exc}")
            return 2
        session = ctx.session
        session_id = session.session_id if session else None
        data = {"result": "connected", "session": session_id, "host": ctx.host, "port": ctx.port}
        emit_result(
            ctx,
            message=f"Connected to {ctx.host}:{ctx.port} session={session_id or '-'}",
            data=data,
        )
        return 0
