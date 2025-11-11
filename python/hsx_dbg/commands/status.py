"""Session status command."""

from __future__ import annotations

from typing import List

from .base import Command
from ..context import DebuggerContext
from ..output import emit_result


class StatusCommand(Command):
    def __init__(self) -> None:
        super().__init__("status", "Show connection status", aliases=("info",))

    def run(self, ctx: DebuggerContext, argv: List[str]) -> int:
        session = ctx.session
        if not session:
            emit_result(ctx, message=f"Not connected (target {ctx.host}:{ctx.port})", data={"status": "disconnected"})
            return 0
        state = "disabled" if session.session_disabled else "active"
        session_id = session.session_id or "-"
        caps = session.state.capabilities or {}
        features = caps.get("features") if isinstance(caps, dict) else None
        max_events = caps.get("max_events") if isinstance(caps, dict) else None
        data = {
            "status": state,
            "session": session_id,
            "host": ctx.host,
            "port": ctx.port,
            "features": list(features) if isinstance(features, list) else features,
            "max_events": max_events,
        }
        emit_result(ctx, message=f"Session: {session_id} ({state}) host={ctx.host} port={ctx.port}", data=data)
        if not ctx.json_output and isinstance(features, list) and features:
            joined = ", ".join(features)
            print(f"  features: {joined}")
        if not ctx.json_output and max_events:
            print(f"  max_events: {max_events}")
        return 0
