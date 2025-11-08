"""
Transport layer for hsxdbg.

Responsibilities (per 04.06--Toolkit §4.2.1):
    * Manage JSON-over-TCP connections to the executive debugger port.
    * Provide request/response helpers with message IDs.
    * Surface connection state changes to callers.

This initial implementation focuses on establishing the public API; the
internal behaviour will be fleshed out in follow-up commits.
"""

from __future__ import annotations

import json
import socket
import threading
import time
from dataclasses import dataclass, field
from typing import Dict, Optional


class TransportError(RuntimeError):
    """Raised when the transport cannot complete an operation."""


@dataclass
class TransportConfig:
    host: str = "127.0.0.1"
    port: int = 9998
    connect_timeout: float = 2.0
    read_timeout: float = 5.0
    reconnect_backoff: float = 0.5
    max_backoff: float = 5.0


@dataclass
class HSXTransport:
    """Thin synchronous transport wrapper (JSON-RPC over TCP)."""

    config: TransportConfig = field(default_factory=TransportConfig)

    _sock: Optional[socket.socket] = field(init=False, default=None)
    _lock: threading.Lock = field(init=False, default_factory=threading.Lock)
    _next_id: int = field(init=False, default=1)

    def connect(self) -> None:
        """Open TCP connection to the executive."""
        if self._sock:
            return
        try:
            sock = socket.create_connection(
                (self.config.host, self.config.port),
                timeout=self.config.connect_timeout,
            )
            sock.settimeout(self.config.read_timeout)
        except OSError as exc:
            raise TransportError(f"connect failed: {exc}") from exc
        self._sock = sock

    def close(self) -> None:
        if self._sock:
            try:
                self._sock.close()
            finally:
                self._sock = None

    def _next_seq(self) -> int:
        with self._lock:
            seq = self._next_id
            self._next_id += 1
            return seq

    def send_request(self, payload: Dict) -> Dict:
        """Send a JSON request and wait for reply."""
        if not self._sock:
            self.connect()
        request_id = payload.setdefault("seq", self._next_seq())
        data = json.dumps(payload).encode("utf-8")
        framed = data + b"\n"
        try:
            assert self._sock is not None  # mypy guard
            self._sock.sendall(framed)
            response = self._sock.recv(1024 * 1024)
        except OSError as exc:
            self.close()
            raise TransportError(f"rpc failed: {exc}") from exc
        if not response:
            self.close()
            raise TransportError("connection closed by peer")
        try:
            decoded = json.loads(response.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise TransportError(f"invalid JSON response: {exc}") from exc
        if decoded.get("seq") != request_id and "status" not in decoded:
            raise TransportError("unexpected response sequence")
        return decoded

    def ping(self) -> float:
        """Round-trip latency measurement (best-effort)."""
        start = time.perf_counter()
        response = self.send_request({"cmd": "session.keepalive"})
        if response.get("status") not in ("ok", None):
            raise TransportError(f"ping failed: {response}")
        return time.perf_counter() - start
