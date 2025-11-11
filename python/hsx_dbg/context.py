"""Debugger context and session helpers."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict, Optional

from python.executive_session import ExecutiveSession, ExecutiveSessionError

LOGGER = logging.getLogger("hsx_dbg.context")


@dataclass
class DebuggerContext:
    """Holds shared CLI debugger state."""

    host: str = "127.0.0.1"
    port: int = 9998
    json_output: bool = False
    _session: Optional[ExecutiveSession] = field(default=None, init=False, repr=False)
    aliases: Dict[str, str] = field(default_factory=dict)
    keepalive_enabled: bool = True
    keepalive_interval: Optional[int] = None
    observer_mode: bool = False

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
        try:
            self._session.configure_keepalive(
                enabled=self.keepalive_enabled,
                interval=self.keepalive_interval,
            )
        except Exception as exc:  # pragma: no cover
            LOGGER.debug("keepalive configure failed: %s", exc)
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

    def resolve_alias(self, name: str) -> str:
        return self.aliases.get(name, name)

    def set_alias(self, alias: str, command: str) -> None:
        if alias == command:
            self.aliases.pop(alias, None)
            return
        self.aliases[alias] = command

    def list_aliases(self) -> Dict[str, str]:
        return dict(self.aliases)
