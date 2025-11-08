"""Typed command helpers built on top of SessionManager."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional

from .session import SessionManager


@dataclass
class CommandClient:
    session: SessionManager
    defaults: Dict[str, Optional[int]] = field(default_factory=dict)

    def _request(self, payload: Dict) -> Dict:
        if not self.session.state.session_id:
            self.session.open()
        payload.setdefault("session", self.session.state.session_id)
        return self.session.transport.send_request(payload)

    def pause(self, pid: Optional[int] = None) -> Dict:
        return self._request({"cmd": "exec.pause", "pid": pid or self.session.state.pid})

    def resume(self, pid: Optional[int] = None) -> Dict:
        return self._request({"cmd": "exec.continue", "pid": pid or self.session.state.pid})

    def step(self, pid: Optional[int] = None, *, source_only: bool = False) -> Dict:
        payload = {
            "cmd": "exec.step",
            "pid": pid or self.session.state.pid,
        }
        if source_only:
            payload["source_only"] = True
        return self._request(payload)

    def set_breakpoint(self, address: int, pid: Optional[int] = None) -> Dict:
        payload = {"cmd": "bp.add", "pid": pid or self.session.state.pid, "address": address}
        return self._request(payload)

    def clear_breakpoint(self, address: int, pid: Optional[int] = None) -> Dict:
        payload = {"cmd": "bp.remove", "pid": pid or self.session.state.pid, "address": address}
        return self._request(payload)

    def list_breakpoints(self, pid: Optional[int] = None) -> Dict:
        payload = {"cmd": "bp.list", "pid": pid or self.session.state.pid}
        return self._request(payload)
