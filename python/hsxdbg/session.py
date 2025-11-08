"""Session manager built on top of HSX transport."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional

from .transport import HSXTransport, TransportConfig


@dataclass
class SessionConfig:
    client_name: str = "hsxdbg"
    features: Optional[list[str]] = None
    pid_lock: Optional[int] = None


@dataclass
class SessionState:
    session_id: Optional[str] = None
    pid: Optional[int] = None
    capabilities: Dict = field(default_factory=dict)
    locked: bool = False


class SessionManager:
    """High-level session lifecycle helper."""

    def __init__(
        self,
        transport: Optional[HSXTransport] = None,
        *,
        transport_config: Optional[TransportConfig] = None,
        session_config: Optional[SessionConfig] = None,
    ) -> None:
        self.transport = transport or HSXTransport(transport_config or TransportConfig())
        self.session_config = session_config or SessionConfig()
        self.state = SessionState()

    def open(self) -> SessionState:
        payload = {
            "cmd": "session.open",
            "client": self.session_config.client_name,
            "capabilities": {
                "features": self.session_config.features or ["events", "stack", "watch"],
            },
            "pid_lock": self.session_config.pid_lock,
        }
        response = self.transport.send_request(payload)
        if response.get("status") != "ok":
            raise RuntimeError(f"session.open failed: {response}")
        self.state.session_id = response.get("session_id")
        self.state.capabilities = response.get("capabilities", {})
        self.state.locked = self.session_config.pid_lock is not None
        self.state.pid = self.session_config.pid_lock
        return self.state

    def keepalive(self) -> None:
        if not self.state.session_id:
            raise RuntimeError("session not open")
        payload = {"cmd": "session.keepalive", "session": self.state.session_id}
        response = self.transport.send_request(payload)
        if response.get("status") != "ok":
            raise RuntimeError(f"session.keepalive failed: {response}")

    def close(self) -> None:
        if not self.state.session_id:
            return
        payload = {"cmd": "session.close", "session": self.state.session_id}
        try:
            self.transport.send_request(payload)
        finally:
            self.state = SessionState()
