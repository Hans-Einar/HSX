"""Session introspection command."""

from __future__ import annotations

import argparse
from typing import Any, Dict, List

from .base import Command
from ..context import DebuggerContext
from ..output import emit_error, emit_result


class SessionCommand(Command):
    def __init__(self) -> None:
        super().__init__("session", "Show session info/list")
        parser = argparse.ArgumentParser(prog="session", add_help=False)
        subparsers = parser.add_subparsers(dest="subcmd")
        subparsers.required = False
        subparsers.add_parser("info")
        subparsers.add_parser("list")
        self._parser = parser

    def run(self, ctx: DebuggerContext, argv: List[str]) -> int:
        try:
            args = self._parser.parse_args(argv)
        except SystemExit:
            return 1
        subcmd = args.subcmd or "info"
        if subcmd == "list":
            return self._run_list(ctx)
        return self._run_info(ctx)

    def _run_info(self, ctx: DebuggerContext) -> int:
        session = ctx.ensure_session()
        payload = {"cmd": "session.current"}
        try:
            response = session.request(payload)
        except Exception as exc:
            emit_error(ctx, message=f"session info failed: {exc}")
            return 2
        if response.get("status") != "ok":
            emit_error(ctx, message=response.get("error", "session info failed"), data=response)
            return 1
        info = response.get("session") or {}
        if ctx.json_output:
            emit_result(ctx, message="session info", data={"session": info})
            return 0
        print("session info:")
        print(f"  id        : {info.get('id')}")
        print(f"  client    : {info.get('client')}")
        features = info.get("features") or []
        if features:
            print(f"  features  : {', '.join(str(f) for f in features)}")
        pid_locks = info.get("pid_locks") or []
        if pid_locks:
            print(f"  pid_locks : {pid_locks}")
        heartbeat = info.get("heartbeat_s")
        if heartbeat:
            print(f"  heartbeat : {heartbeat}s")
        max_events = info.get("max_events")
        if max_events:
            print(f"  max_events: {max_events}")
        return 0

    def _run_list(self, ctx: DebuggerContext) -> int:
        session = ctx.ensure_session()
        try:
            response = session.request({"cmd": "session.list"}, use_session=False)
        except Exception as exc:
            emit_error(ctx, message=f"session list failed: {exc}")
            return 2
        if response.get("status") != "ok":
            emit_error(ctx, message=response.get("error", "session list failed"), data=response)
            return 1
        sessions = response.get("sessions") or []
        if ctx.json_output:
            emit_result(ctx, message="session list", data={"sessions": sessions})
            return 0
        if not sessions:
            print("No active sessions")
            return 0
        print("sessions:")
        for entry in sessions:
            sid = entry.get("id")
            client = entry.get("client")
            pid_locks = entry.get("pid_locks") or entry.get("pid_lock")
            features = entry.get("features") or []
            print(f"  {sid}: client={client} locks={pid_locks} features={features}")
        return 0
