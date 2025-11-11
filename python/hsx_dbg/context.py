"""Debugger context and session helpers."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

from python.executive_session import ExecutiveSession, ExecutiveSessionError

LOGGER = logging.getLogger("hsx_dbg.context")


@dataclass
class DebuggerContext:
    """Holds shared CLI debugger state."""

    host: str = "127.0.0.1"
    port: int = 9998
    json_output: bool = False
    _session: Optional[ExecutiveSession] = field(default=None, init=False, repr=False)

    def ensure_session(self, *, auto_events: bool = True) -> ExecutiveSession:
        """Create the ExecutiveSession if needed."""
        if self._session and not self._session.session_disabled:
            return self._session
        self._session = ExecutiveSession(
            self.host,
            self.port,
            client_name="hsx-dbg",
            features=["events", "stack", "symbols", "memory", "watch", "disasm"],
            max_events=512,
        )
        if auto_events:
            try:
                self._session.start_event_stream(filters={"categories": ["debug_break", "task_state", "scheduler"]})
            except ExecutiveSessionError as exc:
                LOGGER.debug("event stream start failed: %s", exc)
        return self._session

    @property
    def session(self) -> Optional[ExecutiveSession]:
        return self._session

    def disconnect(self) -> None:
        session = self._session
        if not session:
            return
        try:
            session.close()
        except Exception as exc:
            LOGGER.debug("session close failed: %s", exc)
        self._session = None
