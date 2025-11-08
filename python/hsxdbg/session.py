"""Session manager built on top of HSX transport."""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .events import EventBus
from .transport import HSXTransport, TransportConfig, TransportError


logger = logging.getLogger(__name__)


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
        self.transport.set_event_handler(self._handle_transport_event)

        self._event_subscription_token: Optional[str] = None
        self._event_filters: Optional[Dict] = None
        self._event_lock = threading.Lock()
        self._last_event_seq: Optional[int] = None
        self._last_ack_seq: Optional[int] = None
        self._ack_thread: Optional[threading.Thread] = None
        self._ack_stop = threading.Event()
        self._ack_interval = 0.5

    def attach_event_bus(self, event_bus: Optional[EventBus]) -> None:
        """Route transport events into the provided EventBus (or detach)."""

        self.event_bus = event_bus

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
        self.unsubscribe_events()
        payload = {"cmd": "session.close", "session": self.state.session_id}
        try:
            self.transport.send_request(payload)
        finally:
            self.state = SessionState()

    # ------------------------------------------------------------------
    # Event streaming helpers
    # ------------------------------------------------------------------

    def subscribe_events(
        self,
        filters: Optional[Dict] = None,
        *,
        auto_ack: bool = True,
        ack_interval: float = 0.5,
    ) -> Dict:
        """Subscribe to executive events and enable automatic ACKs."""

        if not self.state.session_id:
            self.open()
        if self._event_subscription_token:
            self.unsubscribe_events()
        payload = {
            "cmd": "events.subscribe",
            "session": self.state.session_id,
            "filters": filters or {},
        }
        response = self.transport.send_request(payload)
        if response.get("status") != "ok":
            raise RuntimeError(f"events.subscribe failed: {response}")
        events_info = response.get("events") or {}
        token = events_info.get("token")
        if not token:
            raise RuntimeError("events.subscribe response missing token")
        self._event_subscription_token = token
        self._event_filters = filters or {}
        self._ack_interval = ack_interval
        cursor = events_info.get("cursor")
        with self._event_lock:
            self._last_event_seq = cursor
        self._last_ack_seq = cursor
        if auto_ack:
            self._start_ack_thread()
        return events_info

    def unsubscribe_events(self) -> None:
        token = self._event_subscription_token
        if not token:
            return
        self._stop_ack_thread()
        self._event_subscription_token = None
        with self._event_lock:
            self._last_event_seq = None
        if not self.state.session_id:
            return
        payload = {"cmd": "events.unsubscribe", "session": self.state.session_id}
        try:
            self.transport.send_request(payload)
        except Exception as exc:  # best-effort
            logger.debug("events.unsubscribe failed: %s", exc)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _handle_transport_event(self, event: Dict) -> None:
        seq = event.get("seq")
        if isinstance(seq, int):
            with self._event_lock:
                if self._last_event_seq is None or seq > self._last_event_seq:
                    self._last_event_seq = seq
        if self.event_bus is not None:
            try:
                self.event_bus.publish(event)
            except Exception:
                logger.exception("event bus publish failed")

    def _start_ack_thread(self) -> None:
        if self._ack_thread and self._ack_thread.is_alive():
            return
        self._ack_stop.clear()
        self._ack_thread = threading.Thread(target=self._ack_loop, daemon=True)
        self._ack_thread.start()

    def _stop_ack_thread(self) -> None:
        self._ack_stop.set()
        thread = self._ack_thread
        if thread and thread.is_alive():
            thread.join(timeout=0.5)
        self._ack_thread = None

    def _ack_loop(self) -> None:
        while not self._ack_stop.wait(self._ack_interval):
            self._send_pending_ack()
        self._send_pending_ack()

    def _send_pending_ack(self) -> None:
        if not self.state.session_id:
            return
        with self._event_lock:
            target = self._last_event_seq
        if target is None or target == self._last_ack_seq:
            return
        payload = {"cmd": "events.ack", "session": self.state.session_id, "seq": target}
        try:
            response = self.transport.send_request(payload)
        except TransportError as exc:
            logger.debug("events.ack transport error: %s", exc)
            return
        if response.get("status") == "ok":
            self._last_ack_seq = target
        else:
            logger.debug("events.ack failed: %s", response)
