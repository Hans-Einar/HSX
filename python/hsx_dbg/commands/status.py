"""Session status command."""

from __future__ import annotations

from typing import List

from .base import Command
from ..context import DebuggerContext


class StatusCommand(Command):
    def __init__(self) -> None:
        super().__init__("status", "Show connection status", aliases=("info",))

    def run(self, ctx: DebuggerContext, argv: List[str]) -> int:
        session = ctx.session
        if not session:
            print(f"Not connected (target {ctx.host}:{ctx.port})")
            return 0
        state = "disabled" if session.session_disabled else "active"
        session_id = session.session_id or "-"
        print(f"Session: {session_id} ({state}) host={ctx.host} port={ctx.port}")
        caps = session.state.capabilities or {}
        if caps:
            features = caps.get("features")
            if features:
                joined = ", ".join(features)
                print(f"  features: {joined}")
            max_events = caps.get("max_events")
            if max_events:
                print(f"  max_events: {max_events}")
        return 0
