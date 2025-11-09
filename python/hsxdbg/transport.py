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
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional


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
    max_retries: int = 5
    request_retries: int = 2


@dataclass
class HSXTransport:
    """Thin synchronous transport wrapper (JSON-over-TCP RPC)."""

    config: TransportConfig = field(default_factory=TransportConfig)

    _sock: Optional[socket.socket] = field(init=False, default=None)
    _lock: threading.Lock = field(init=False, default_factory=threading.Lock)
    _connect_lock: threading.Lock = field(init=False, default_factory=threading.Lock)
    _state_lock: threading.Lock = field(init=False, default_factory=threading.Lock)
    _state: str = field(init=False, default="disconnected")
    _shutdown: bool = field(init=False, default=False)
    _next_id: int = field(init=False, default=1)
    _reader_thread: Optional[threading.Thread] = field(init=False, default=None)
    _responses: Dict[int, Dict[str, Any]] = field(init=False, default_factory=dict)
    _pending: OrderedDict[int, None] = field(init=False, default_factory=OrderedDict)
    _resp_cv: threading.Condition = field(init=False, default_factory=lambda: threading.Condition(threading.Lock()))
    _closed: bool = field(init=False, default=True)
    _event_handler: Optional[Callable[[Dict[str, Any]], None]] = field(init=False, default=None)
    _on_connect: list[Callable[[str], None]] = field(init=False, default_factory=list)
    _on_disconnect: list[Callable[[str], None]] = field(init=False, default_factory=list)

    #
    # Connection lifecycle helpers
    #
    @property
    def state(self) -> str:
        with self._state_lock:
            return self._state

    def register_on_connect(self, callback: Callable[[str], None]) -> None:
        self._on_connect.append(callback)

    def register_on_disconnect(self, callback: Callable[[str], None]) -> None:
        self._on_disconnect.append(callback)

    def set_event_handler(self, handler: Optional[Callable[[Dict[str, Any]], None]]) -> None:
        self._event_handler = handler

    def connect(self, *, retry: bool = True) -> None:
        """Open TCP connection to the executive."""
        with self._connect_lock:
            if self._sock:
                return
            if self._shutdown:
                raise TransportError("transport closed")
            self._set_state("connecting")
            try:
                sock = self._connect_with_backoff(retry=retry)
            except TransportError:
                self._set_state("disconnected")
                raise
            self._sock = sock
            self._closed = False
            self._reader_thread = threading.Thread(target=self._reader_loop, daemon=True)
            self._reader_thread.start()
            self._set_state("connected")

    def close(self) -> None:
        self._shutdown = True
        self._handle_disconnect()
        if self._reader_thread and self._reader_thread.is_alive():
            self._reader_thread.join(timeout=0.5)
        with self._resp_cv:
            self._resp_cv.notify_all()

    def _next_seq(self) -> int:
        with self._lock:
            seq = self._next_id
            self._next_id += 1
            return seq

    def _reader_loop(self) -> None:
        buffer = b""
        while not self._shutdown:
            sock = self._sock
            if not sock:
                break
            try:
                chunk = sock.recv(4096)
            except OSError as exc:
                self._handle_disconnect(exc)
                break
            if not chunk:
                self._handle_disconnect()
                break
            buffer += chunk
            while b"\n" in buffer:
                line, buffer = buffer.split(b"\n", 1)
                if not line:
                    continue
                try:
                    message = json.loads(line.decode("utf-8"))
                except json.JSONDecodeError:
                    continue
                if self._is_event(message):
                    self._dispatch_event(message)
                    continue
                self._handle_response(message)
        self._handle_disconnect()

    def send_request(self, payload: Dict[str, Any], timeout: Optional[float] = None) -> Dict[str, Any]:
        """Send a JSON request and wait for reply."""
        request_payload = dict(payload)
        attempts = max(1, self.config.request_retries)
        last_error: Optional[Exception] = None
        for attempt in range(attempts):
            try:
                return self._send_single_request(request_payload, timeout=timeout)
            except TransportError as exc:
                last_error = exc
                if attempt + 1 >= attempts:
                    break
                time.sleep(self.config.reconnect_backoff)
        raise TransportError(f"rpc failed: {last_error}") from last_error

    def ping(self) -> float:
        """Round-trip latency measurement (best-effort)."""
        start = time.perf_counter()
        response = self.send_request({"cmd": "ping"})
        if response.get("status") not in ("ok", None):
            raise TransportError(f"ping failed: {response}")
        return time.perf_counter() - start

    #
    # Internal helpers
    #
    def _ensure_connected(self) -> None:
        if self._sock:
            return
        self.connect()

    def _connect_with_backoff(self, *, retry: bool) -> socket.socket:
        attempt = 0
        backoff = self.config.reconnect_backoff
        last_error: Optional[OSError] = None
        while not self._shutdown:
            attempt += 1
            try:
                sock = socket.create_connection(
                    (self.config.host, self.config.port),
                    timeout=self.config.connect_timeout,
                )
                sock.settimeout(self.config.read_timeout)
                return sock
            except OSError as exc:
                last_error = exc
                if not retry:
                    break
                if self.config.max_retries > 0 and attempt >= self.config.max_retries:
                    break
                time.sleep(backoff)
                backoff = min(backoff * 2, self.config.max_backoff)
        if last_error is None:
            raise TransportError("connect failed: transport closed")
        raise TransportError(f"connect failed: {last_error}") from last_error

    def _send_single_request(self, payload: Dict[str, Any], timeout: Optional[float]) -> Dict[str, Any]:
        if self._shutdown:
            raise TransportError("transport closed")
        self._ensure_connected()
        request_id = self._next_seq()
        data = json.dumps(payload).encode("utf-8") + b"\n"
        with self._resp_cv:
            self._pending[request_id] = None
        try:
            assert self._sock is not None  # mypy guard
            self._sock.sendall(data)
        except OSError as exc:
            with self._resp_cv:
                self._pending.pop(request_id, None)
            self._handle_disconnect(exc)
            raise TransportError(f"rpc send failed: {exc}") from exc
        return self._wait_for_response(request_id, timeout=timeout)

    def _wait_for_response(self, request_id: int, timeout: Optional[float]) -> Dict[str, Any]:
        deadline = time.perf_counter() + (timeout or self.config.read_timeout)
        with self._resp_cv:
            while request_id not in self._responses:
                remaining = deadline - time.perf_counter()
                if remaining <= 0:
                    self._pending.pop(request_id, None)
                    raise TransportError("rpc timeout")
                if self._shutdown or (self._closed and not self._sock):
                    self._pending.pop(request_id, None)
                    raise TransportError("connection closed")
                self._resp_cv.wait(timeout=remaining)
            response = self._responses.pop(request_id)
            return response

    def _handle_disconnect(self, exc: Optional[BaseException] = None) -> None:
        sock = self._sock
        if sock:
            try:
                sock.close()
            except OSError:
                pass
        self._sock = None
        self._closed = True
        with self._resp_cv:
            self._resp_cv.notify_all()
        self._set_state("disconnected")

    def _set_state(self, new_state: str) -> None:
        with self._state_lock:
            if self._state == new_state:
                return
            self._state = new_state
        callbacks: list[Callable[[str], None]]
        if new_state == "connected":
            callbacks = list(self._on_connect)
        elif new_state == "disconnected":
            callbacks = list(self._on_disconnect)
        else:
            callbacks = []
        for callback in callbacks:
            try:
                callback(new_state)
            except Exception:
                pass

    def _handle_response(self, message: Dict[str, Any]) -> None:
        with self._resp_cv:
            req_id: Optional[int] = None
            seq_value = message.get("seq")
            if isinstance(seq_value, int) and seq_value in self._pending:
                req_id = seq_value
                self._pending.pop(seq_value, None)
            elif self._pending:
                req_id, _ = self._pending.popitem(last=False)
            if req_id is None:
                return
            self._responses[req_id] = message
            self._resp_cv.notify_all()

    def _dispatch_event(self, message: Dict[str, Any]) -> None:
        handler = self._event_handler
        if not handler:
            return
        try:
            handler(message)
        except Exception:
            # Event handlers should not disrupt transport.
            pass

    def _is_event(self, message: Dict[str, Any]) -> bool:
        """Best-effort detection of async events from executive."""
        if "type" in message and "status" not in message:
            return True
        return False
