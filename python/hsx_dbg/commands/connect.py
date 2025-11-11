"""Connect command implementation."""

from __future__ import annotations

import argparse
from typing import List

from .base import Command
from ..context import DebuggerContext


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
            session = ctx.session
            if session and session.session_id:
                print(f"Connected to {ctx.host}:{ctx.port} session={session.session_id}")
            else:
                print(f"Connected to {ctx.host}:{ctx.port}")
            return 0
        except Exception as exc:
            print(f"connect failed: {exc}")
            return 2
