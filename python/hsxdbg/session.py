"""Session manager built on top of HSX transport."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .events import EventBus
from .transport import HSXTransport, TransportConfig


@dataclass
class SessionConfig:
    client_name: str = "hsxdbg"
    features: Optional[list[str]] = None
    pid_lock: Optional[int] = None
    max_events: Optional[int] = None
    heartbeat_s: Optional[int] = None


@dataclass
class SessionState:
    session_id: Optional[str] = None
    client: str = ""
    pid: Optional[int] = None
    pid_locks: List[int] = field(default_factory=list)
    capabilities: Dict = field(default_factory=dict)
    features: List[str] = field(default_factory=list)
    max_events: Optional[int] = None
    heartbeat_s: Optional[int] = None
    warnings: List[str] = field(default_factory=list)
    locked: bool = False


class SessionManager:
    """High-level session lifecycle helper."""

    def __init__(
        self,
        transport: Optional[HSXTransport] = None,
        *,
        transport_config: Optional[TransportConfig] = None,
        session_config: Optional[SessionConfig] = None,
        event_bus: Optional[EventBus] = None,
    ) -> None:
        self.transport = transport or HSXTransport(transport_config or TransportConfig())
        self.session_config = session_config or SessionConfig()
        self.event_bus = event_bus
        self.state = SessionState()
        if event_bus is not None:
            self.transport.set_event_handler(event_bus.publish)

    def attach_event_bus(self, event_bus: Optional[EventBus]) -> None:
        """Route transport events into the provided EventBus (or detach)."""

        self.event_bus = event_bus
        handler = event_bus.publish if event_bus is not None else None
        self.transport.set_event_handler(handler)

    def open(self) -> SessionState:
        capabilities: Dict[str, object] = {
            "features": self.session_config.features or ["events", "stack", "watch"],
        }
        if self.session_config.max_events is not None:
            capabilities["max_events"] = self.session_config.max_events
        payload = {
            "cmd": "session.open",
            "client": self.session_config.client_name,
            "capabilities": capabilities,
            "pid_lock": self.session_config.pid_lock,
        }
        if self.session_config.heartbeat_s is not None:
            payload["heartbeat_s"] = self.session_config.heartbeat_s
        response = self.transport.send_request(payload)
        if response.get("status") != "ok":
            raise RuntimeError(f"session.open failed: {response}")
        session_payload = response.get("session") or response
        session_id = session_payload.get("id") or response.get("session_id")
        if not session_id:
            raise RuntimeError("session.open response missing session id")
        pid_lock = session_payload.get("pid_lock")
        pid_locks: List[int]
        if pid_lock is None:
            pid_locks = []
        elif isinstance(pid_lock, list):
            pid_locks = [int(pid) for pid in pid_lock]
        else:
            pid_locks = [int(pid_lock)]
        capabilities = session_payload.get("capabilities") or response.get("capabilities", {})
        self.state = SessionState(
            session_id=session_id,
            client=session_payload.get("client", ""),
            capabilities=capabilities,
            features=list(session_payload.get("features", [])),
            pid=pid_locks[0] if len(pid_locks) == 1 else None,
            pid_locks=pid_locks,
            max_events=session_payload.get("max_events"),
            heartbeat_s=session_payload.get("heartbeat_s"),
            warnings=list(session_payload.get("warnings", [])),
            locked=bool(pid_locks),
        )
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
