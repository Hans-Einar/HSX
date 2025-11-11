"""Execution control commands (pause/continue/step)."""

from __future__ import annotations

import argparse
from typing import List

from .base import Command
from ..context import DebuggerContext
from ..output import emit_error, emit_result


class PauseCommand(Command):
    def __init__(self) -> None:
        super().__init__("pause", "Pause execution for a PID")
        self._parser = argparse.ArgumentParser(prog="pause", add_help=False)
        self._parser.add_argument("pid", type=int, help="PID to pause")

    def run(self, ctx: DebuggerContext, argv: List[str]) -> int:
        try:
            args = self._parser.parse_args(argv)
        except SystemExit:
            return 1
        session = ctx.ensure_session()
        try:
            response = session.request({"cmd": "pause", "pid": args.pid})
        except Exception as exc:
            emit_error(ctx, message=f"pause failed: {exc}")
            return 2
        if response.get("status") != "ok":
            emit_error(ctx, message=response.get("error", "pause failed"), data=response)
            return 1
        emit_result(ctx, message=f"Paused PID {args.pid}", data={"result": "paused", "pid": args.pid})
        return 0


class ContinueCommand(Command):
    def __init__(self) -> None:
        super().__init__("continue", "Resume execution for a PID", aliases=("cont", "resume"))
        self._parser = argparse.ArgumentParser(prog="continue", add_help=False)
        self._parser.add_argument("pid", type=int, help="PID to resume")

    def run(self, ctx: DebuggerContext, argv: List[str]) -> int:
        try:
            args = self._parser.parse_args(argv)
        except SystemExit:
            return 1
        session = ctx.ensure_session()
        try:
            response = session.request({"cmd": "resume", "pid": args.pid})
        except Exception as exc:
            emit_error(ctx, message=f"continue failed: {exc}")
            return 2
        if response.get("status") != "ok":
            emit_error(ctx, message=response.get("error", "continue failed"), data=response)
            return 1
        emit_result(ctx, message=f"Resumed PID {args.pid}", data={"result": "resumed", "pid": args.pid})
        return 0


class StepCommand(Command):
    def __init__(self) -> None:
        super().__init__("step", "Single-step a PID", aliases=("next",))
        self._parser = argparse.ArgumentParser(prog="step", add_help=False)
        self._parser.add_argument("pid", type=int, help="PID to step")
        self._parser.add_argument("count", nargs="?", type=int, default=1, help="Instruction count (default 1)")

    def run(self, ctx: DebuggerContext, argv: List[str]) -> int:
        try:
            args = self._parser.parse_args(argv)
        except SystemExit:
            return 1
        session = ctx.ensure_session()
        payload = {"cmd": "step", "pid": args.pid, "steps": max(1, args.count)}
        try:
            response = session.request(payload)
        except Exception as exc:
            emit_error(ctx, message=f"step failed: {exc}")
            return 2
        if response.get("status") != "ok":
            emit_error(ctx, message=response.get("error", "step failed"), data=response)
            return 1
        result = response.get("result") or {}
        message = f"Stepped PID {args.pid} ({payload['steps']} instruction(s))"
        emit_result(ctx, message=message, data={"result": "stepped", "pid": args.pid, "response": response})
        return 0
