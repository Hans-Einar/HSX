#!/usr/bin/env python3
"""Shared helpers for talking to the HSX executive RPC service.

Provides a thin session-aware wrapper that automatically negotiates
``session.open`` (when supported), keeps the heartbeat alive, and exposes a
utility for subscribing to the asynchronous event stream.
"""

from __future__ import annotations

from dataclasses import dataclass
import copy
import json
import logging
import socket
import threading
import time
from collections import deque
try:
    from . import trace_format
except ImportError:
    import trace_format
from typing import Any, Callable, Deque, Dict, Iterable, List, Optional, Tuple


LOGGER = logging.getLogger("hsx.executive_session")

JsonDict = Dict[str, Any]
EventCallback = Callable[[JsonDict], None]

_UNSET = object()


def _json_dumps(payload: JsonDict) -> str:
    return json.dumps(payload, separators=(",", ":"))


class ExecutiveSessionError(RuntimeError):
    """Raised when an expected session negotiation step fails."""


class ConnectionLostError(ExecutiveSessionError):
    """Raised when the transport drops unexpectedly."""


class ProtocolVersionError(ExecutiveSessionError):
    """Raised when the executive reports a protocol version mismatch."""


@dataclass
class _EventStream:
    sock: socket.socket
    rfile: Any
    stop_event: threading.Event
    thread: threading.Thread
    token: str


class ExecutiveSession:
    """Session-aware RPC helper for the HSX executive."""

    def __init__(
        self,
        host: str,
        port: int,
        *,
        client_name: str,
        features: Optional[Iterable[str]] = None,
        max_events: int = 256,
        timeout: float = 5.0,
        event_buffer: int = 256,
    ) -> None:
        self.host = host
        self.port = port
        self.client_name = client_name
        self.features_requested = list(features or [])
        self.max_events_requested = max_events
        self.timeout = timeout
        self.session_id: Optional[str] = None
        self.session_heartbeat: int = 30
        self.session_disabled = False
        self.negotiated_features: List[str] = []
        self._pid_lock_specified = False
        self._pid_lock_value: Optional[Any] = None
        self._heartbeat_override: Optional[int] = None

        self._keepalive_thread: Optional[threading.Thread] = None
        self._keepalive_stop = threading.Event()
        self._session_lock = threading.Lock()

        self._event_stream: Optional[_EventStream] = None
        self._event_buffer: Deque[JsonDict] = deque(maxlen=max(1, event_buffer))
        self._event_buffer_lock = threading.Lock()
        self._event_callback: Optional[EventCallback] = None
        self._keepalive_enabled = True
        self._stack_supported: Optional[bool] = None
        self._stack_cache: Dict[int, Tuple[float, JsonDict]] = {}
        self._stack_cache_lock = threading.Lock()
        self._disasm_supported: Optional[bool] = None
        self._symbols_supported: Optional[bool] = None
        self._memory_supported: Optional[bool] = None
        self._watch_supported: Optional[bool] = None
        self._last_connection_error: Optional[str] = None
        self._transport_retry_limit = 3

    # ------------------------------------------------------------------ Basics

    def close(self) -> None:
        """Terminate the active session and stop background helpers."""
        with self._session_lock:
            self._stop_event_stream_locked()
            self._stop_keepalive_locked()
            if self.session_id and not self.session_disabled:
                try:
                    self._send_raw({"cmd": "session.close", "session": self.session_id})
                except Exception:
                    pass
            self.session_id = None
        with self._stack_cache_lock:
            self._stack_cache.clear()
        self._stack_supported = None
        self._disasm_supported = None
        self._symbols_supported = None
        self._memory_supported = None
        self._watch_supported = None

    # Public API --------------------------------------------------------------

    def request(
        self,
        payload: JsonDict,
        *,
        use_session: bool = True,
        retry: bool = True,
    ) -> JsonDict:
        """Send a single RPC request.

        Automatically appends the negotiated session id (when available) and
        retries once if the server reports ``session_required`` and the session
        can be re-established.
        """
        attempts = max(2 if retry else 1, self._transport_retry_limit if retry else 1)
        last_error: Optional[Exception] = None
        for attempt in range(attempts):
            payload = dict(payload)
            payload.setdefault("version", 1)
            if use_session and not self.session_disabled:
                self._ensure_session(force=attempt > 0)
                if self.session_id:
                    payload.setdefault("session", self.session_id)
            try:
                response = self._send_raw(payload)
            except ConnectionLostError as exc:
                last_error = exc
                self._handle_connection_loss(exc, attempt)
                continue
            except ExecutiveSessionError as exc:
                last_error = exc
                if attempt + 1 >= attempts:
                    break
                continue
            if (
                use_session
                and not self.session_disabled
                and response.get("status") == "error"
                and isinstance(response.get("error"), str)
                and response["error"].startswith("session_required")
                and attempt + 1 < attempts
            ):
                continue
            return response
        if last_error:
            raise last_error
        return {"status": "error", "error": "session_failed"}

    def start_event_stream(
        self,
        *,
        filters: Optional[JsonDict] = None,
        callback: Optional[EventCallback] = None,
        ack_interval: int = 1,
    ) -> bool:
        """Begin streaming events in the background.

        Returns ``True`` when the stream is active and ``False`` when the
        executive does not support event streaming.
        """
        with self._session_lock:
            if self._event_stream is not None:
                return True
            session_disabled = self.session_disabled
        if session_disabled:
            return False
        self._ensure_session()
        with self._session_lock:
            if self._event_stream is not None:
                return True
            if self.session_disabled:
                return False
            if "events" not in self.negotiated_features:
                return False
            stream = self._open_event_stream(filters or {}, ack_interval)
            if stream is None:
                return False
            self._event_callback = callback
            self._event_stream = stream
            stream.thread.start()
            return True

    def stop_event_stream(self) -> None:
        with self._session_lock:
            self._stop_event_stream_locked()

    def get_recent_events(self, limit: int = 20) -> List[JsonDict]:
        """Return up to ``limit`` most recent streamed events (newest last)."""
        with self._event_buffer_lock:
            if limit <= 0:
                return list(self._event_buffer)
            return list(self._event_buffer)[-limit:]

    def supports_stack(self) -> bool:
        """Return ``True`` when the executive advertises stack debugging."""
        if self.session_disabled:
            return False
        if "stack" in self.negotiated_features:
            return True
        return bool(self._stack_supported)

    def invalidate_stack_cache(self, pid: Optional[int] = None) -> None:
        """Clear cached stack traces."""
        with self._stack_cache_lock:
            if pid is None:
                self._stack_cache.clear()
            else:
                self._stack_cache.pop(pid, None)

    def stack_info(
        self,
        pid: int,
        *,
        max_frames: Optional[int] = None,
        refresh: bool = True,
    ) -> Optional[JsonDict]:
        """Fetch stack metadata for *pid*.

        When ``refresh`` is ``False`` the most recent cached stack is returned
        (or ``None`` if no cache exists).
        """
        pid_int = int(pid)
        if not refresh:
            with self._stack_cache_lock:
                cached = self._stack_cache.get(pid_int)
                if cached:
                    return copy.deepcopy(cached[1])
            if self._stack_supported is False:
                return None
        payload: JsonDict = {"cmd": "stack", "pid": pid_int}
        if max_frames is not None:
            payload["max"] = int(max_frames)
        try:
            response = self.request(payload)
        except Exception as exc:  # pragma: no cover - network failures
            raise ExecutiveSessionError(f"stack request failed: {exc}") from exc
        status = response.get("status")
        if status != "ok":
            error = str(response.get("error", "stack error"))
            lowered = error.lower()
            if any(tag in lowered for tag in ("unknown_cmd", "unsupported", "stack_disabled")):
                self._stack_supported = False
                with self._stack_cache_lock:
                    self._stack_cache.pop(pid_int, None)
                return None
            raise ExecutiveSessionError(f"stack error: {error}")
        stack_block = response.get("stack")
        if not isinstance(stack_block, dict):
            return None
        stack_copy = copy.deepcopy(stack_block)
        timestamp = time.time()
        with self._stack_cache_lock:
            self._stack_cache[pid_int] = (timestamp, stack_copy)
        self._stack_supported = True
        return copy.deepcopy(stack_copy)

    def stack_frames(
        self,
        pid: int,
        *,
        max_frames: Optional[int] = None,
        refresh: bool = True,
    ) -> List[JsonDict]:
        """Convenience wrapper returning the frame list."""
        info = self.stack_info(pid, max_frames=max_frames, refresh=refresh)
        if not info:
            return []
        frames = info.get("frames")
        if isinstance(frames, list):
            return copy.deepcopy(frames)
        return []

    def supports_disasm(self) -> bool:
        if self.session_disabled:
            return False
        if "disasm" in self.negotiated_features:
            return True
        return bool(self._disasm_supported)

    def supports_memory(self) -> bool:
        if self.session_disabled:
            return False
        if "memory" in self.negotiated_features:
            return True
        return bool(self._memory_supported)

    def supports_watch(self) -> bool:
        if self.session_disabled:
            return False
        if "watch" in self.negotiated_features:
            return True
        return bool(self._watch_supported)

    def supports_symbols(self) -> bool:
        if self.session_disabled:
            return False
        if "symbols" in self.negotiated_features:
            return True
        return bool(self._symbols_supported)

    def symbols_list(
        self,
        pid: int,
        *,
        kind: Optional[str] = None,
        offset: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> Optional[JsonDict]:
        payload: JsonDict = {"cmd": "symbols", "pid": int(pid)}
        if kind is not None:
            payload["type"] = str(kind)
        if offset is not None:
            payload["offset"] = int(offset)
        if limit is not None:
            payload["limit"] = int(limit)
        try:
            response = self.request(payload)
        except Exception as exc:  # pragma: no cover - transport error
            raise ExecutiveSessionError(f"symbols request failed: {exc}") from exc
        if response.get("status") != "ok":
            error = str(response.get("error", "symbols error"))
            if "unknown_cmd" in error or "unsupported" in error:
                self._symbols_supported = False
                return None
            raise ExecutiveSessionError(error)
        block = response.get("symbols")
        if not isinstance(block, dict):
            return None
        self._symbols_supported = True
        return copy.deepcopy(block)

    def memory_regions(self, pid: int) -> Optional[JsonDict]:
        payload: JsonDict = {"cmd": "memory", "op": "regions", "pid": int(pid)}
        try:
            response = self.request(payload)
        except Exception as exc:  # pragma: no cover - transport error
            raise ExecutiveSessionError(f"memory request failed: {exc}") from exc
        if response.get("status") != "ok":
            error = str(response.get("error", "memory error"))
            if "unknown_cmd" in error or "unsupported" in error:
                self._memory_supported = False
                return None
            raise ExecutiveSessionError(error)
        block = response.get("memory")
        if not isinstance(block, dict):
            return None
        self._memory_supported = True
        return copy.deepcopy(block)

    def watch_add(
        self,
        pid: int,
        expr: str,
        *,
        watch_type: Optional[str] = None,
        length: Optional[int] = None,
    ) -> Optional[JsonDict]:
        payload: JsonDict = {"cmd": "watch", "op": "add", "pid": int(pid), "expr": str(expr)}
        if watch_type is not None:
            payload["type"] = str(watch_type)
        if length is not None:
            payload["length"] = int(length)
        try:
            response = self.request(payload)
        except Exception as exc:  # pragma: no cover - transport error
            raise ExecutiveSessionError(f"watch add failed: {exc}") from exc
        if response.get("status") != "ok":
            error = str(response.get("error", "watch error"))
            if "unknown_cmd" in error or "unsupported" in error:
                self._watch_supported = False
                return None
            raise ExecutiveSessionError(error)
        block = response.get("watch")
        if not isinstance(block, dict):
            return None
        self._watch_supported = True
        return copy.deepcopy(block)

    def watch_remove(self, pid: int, watch_id: int) -> Optional[JsonDict]:
        payload: JsonDict = {"cmd": "watch", "op": "remove", "pid": int(pid), "id": int(watch_id)}
        try:
            response = self.request(payload)
        except Exception as exc:  # pragma: no cover - transport error
            raise ExecutiveSessionError(f"watch remove failed: {exc}") from exc
        if response.get("status") != "ok":
            error = str(response.get("error", "watch error"))
            if "unknown_cmd" in error or "unsupported" in error:
                self._watch_supported = False
                return None
            raise ExecutiveSessionError(error)
        block = response.get("watch")
        if not isinstance(block, dict):
            return None
        self._watch_supported = True
        return copy.deepcopy(block)

    def watch_list(self, pid: int) -> Optional[JsonDict]:
        payload: JsonDict = {"cmd": "watch", "op": "list", "pid": int(pid)}
        try:
            response = self.request(payload)
        except Exception as exc:  # pragma: no cover - transport error
            raise ExecutiveSessionError(f"watch list failed: {exc}") from exc
        if response.get("status") != "ok":
            error = str(response.get("error", "watch error"))
            if "unknown_cmd" in error or "unsupported" in error:
                self._watch_supported = False
                return None
            raise ExecutiveSessionError(error)
        block = response.get("watch")
        if not isinstance(block, dict):
            return None
        self._watch_supported = True
        return copy.deepcopy(block)

    def trace(self, pid: int, mode: Optional[bool] = None) -> Optional[JsonDict]:
        payload: JsonDict = {"cmd": "trace", "pid": int(pid)}
        if mode is not None:
            payload["mode"] = bool(mode)
        response = self.request(payload)
        if response.get("status") != "ok":
            error = str(response.get("error", "trace error"))
            if "unknown_cmd" in error or "unsupported" in error:
                return None
            raise ExecutiveSessionError(error)
        block = response.get("trace")
        if not isinstance(block, dict):
            return None
        return copy.deepcopy(block)

    def trace_records(
        self,
        pid: int,
        *,
        limit: Optional[int] = None,
        export: bool = False,
    ) -> Optional[JsonDict]:
        payload: JsonDict = {
            "cmd": "trace",
            "pid": int(pid),
            "op": "export" if export else "records",
        }
        if limit is not None:
            payload["limit"] = int(limit)
        response = self.request(payload)
        if response.get("status") != "ok":
            error = str(response.get("error", "trace records error"))
            if "unknown_cmd" in error or "unsupported" in error:
                return None
            raise ExecutiveSessionError(error)
        block = response.get("trace")
        if not isinstance(block, dict):
            return None
        return copy.deepcopy(block)

    def trace_import(
        self,
        pid: int,
        records: Iterable[Dict[str, Any]],
        *,
        replace: bool = True,
    ) -> Optional[JsonDict]:
        encoded = trace_format.encode_trace_records(records)
        payload: JsonDict = {
            "cmd": "trace",
            "pid": int(pid),
            "op": "import",
            "records": encoded,
            "replace": bool(replace),
        }
        response = self.request(payload)
        if response.get("status") != "ok":
            error = str(response.get("error", "trace import error"))
            if "unknown_cmd" in error or "unsupported" in error:
                return None
            raise ExecutiveSessionError(error)
        block = response.get("trace")
        if not isinstance(block, dict):
            return None
        return copy.deepcopy(block)

    def disasm_read(
        self,
        pid: int,
        *,
        address: Optional[int] = None,
        count: Optional[int] = None,
        mode: Optional[str] = None,
        view: Optional[str] = None,
    ) -> Optional[JsonDict]:
        payload_base: JsonDict = {"pid": int(pid)}
        if address is not None:
            try:
                payload_base["addr"] = int(str(address), 0)
            except (TypeError, ValueError) as exc:
                raise ExecutiveSessionError("address must be integer-compatible") from exc
        if count is not None:
            try:
                payload_base["count"] = int(count)
            except (TypeError, ValueError) as exc:
                raise ExecutiveSessionError("count must be integer-compatible") from exc

        if mode is not None:
            payload_base["mode"] = str(mode)
            mode_lower = str(mode).strip().lower()
            if mode_lower in {"on-demand", "cached"}:
                payload_base["cache"] = mode_lower

        if view is not None:
            payload_base["view"] = str(view)

        commands = ["disasm.read", "disasm"]
        last_error: Optional[str] = None
        for command in commands:
            payload = dict(payload_base)
            payload["cmd"] = command
            if command == "disasm":
                payload.pop("view", None)
                payload.pop("cache", None)
            if mode is not None:
                payload.setdefault("mode", str(mode))
            try:
                response = self.request(payload)
            except Exception as exc:  # pragma: no cover - transport errors
                last_error = str(exc)
                continue
            if response.get("status") != "ok":
                error = str(response.get("error", "disasm error"))
                if "unknown_cmd" in error and command != commands[-1]:
                    last_error = error
                    continue
                if "unknown_cmd" in error or "unsupported" in error:
                    self._disasm_supported = False
                    return None
                raise ExecutiveSessionError(error)
            block = response.get("disasm")
            if not isinstance(block, dict):
                return None
            self._disasm_supported = True
            return copy.deepcopy(block)
        if last_error:
            raise ExecutiveSessionError(f"disasm request failed: {last_error}")
        self._disasm_supported = False
        return None

    # ---------------------------------------------------------------- Private

    def _handle_connection_loss(self, exc: ConnectionLostError, attempt: int) -> None:
        self._last_connection_error = str(exc)
        LOGGER.warning("connection lost (%s); retrying (attempt %s)", exc, attempt + 1)
        with self._session_lock:
            self._stop_event_stream_locked()
            self._stop_keepalive_locked()
            self.session_id = None
        delay = min(2.0, 0.5 * (attempt + 1))
        time.sleep(delay)

    @staticmethod
    def _is_protocol_mismatch(error: str, details: Optional[Any]) -> bool:
        lowered = error.lower()
        if "protocol" in lowered and "version" in lowered:
            return True
        if isinstance(details, dict) and details.get("protocol_version") is not None:
            return True
        return False

    def _send_raw(self, payload: JsonDict) -> JsonDict:
        data = _json_dumps(payload)
        try:
            with socket.create_connection((self.host, self.port), timeout=self.timeout) as sock:
                sock.settimeout(self.timeout)
                with sock.makefile("w", encoding="utf-8", newline="\n") as wfile, sock.makefile(
                    "r", encoding="utf-8", newline="\n"
                ) as rfile:
                    wfile.write(data + "\n")
                    wfile.flush()
                    line = rfile.readline()
                    if not line:
                        raise ConnectionLostError("executive closed connection")
                    return json.loads(line)
        except socket.timeout as exc:
            raise ConnectionLostError("transport timeout") from exc
        except OSError as exc:
            raise ConnectionLostError(f"transport error: {exc}") from exc

    def _ensure_session(self, *, force: bool = False) -> None:
        if self.session_disabled:
            return
        with self._session_lock:
            if self.session_disabled:
                return
            if self.session_id and not force:
                return
            if force and self.session_id:
                self._stop_event_stream_locked()
                self._stop_keepalive_locked()
            payload: JsonDict = {
                "cmd": "session.open",
                "client": self.client_name,
            }
            if self._pid_lock_specified:
                payload["pid_lock"] = self._pid_lock_value
            capabilities: JsonDict = {}
            if self.features_requested:
                capabilities["features"] = list(self.features_requested)
            if self.max_events_requested:
                capabilities["max_events"] = self.max_events_requested
            if capabilities:
                payload["capabilities"] = capabilities
            if self._heartbeat_override is not None:
                payload["heartbeat_s"] = self._heartbeat_override
            response = self._send_raw(payload)
            if response.get("status") != "ok":
                error = str(response.get("error", "exec error"))
                if self._is_protocol_mismatch(error, response.get("details")):
                    raise ProtocolVersionError(error)
                if "unknown_cmd" in error or "unsupported" in error:
                    self.session_disabled = True
                    self._stop_keepalive_locked()
                    self._stop_event_stream_locked()
                    return
                raise ExecutiveSessionError(f"session.open failed: {error}")
            session_block = response.get("session")
            if not isinstance(session_block, dict):
                raise ExecutiveSessionError("session.open missing session payload")
            self.session_id = session_block.get("id")
            if not isinstance(self.session_id, str) or not self.session_id:
                raise ExecutiveSessionError("session.open returned invalid session id")
            heartbeat = session_block.get("heartbeat_s", self.session_heartbeat)
            try:
                self.session_heartbeat = max(5, int(heartbeat))
            except (TypeError, ValueError):
                self.session_heartbeat = 30
            negotiated_features = session_block.get("features", [])
            if isinstance(negotiated_features, list):
                self.negotiated_features = [str(item) for item in negotiated_features]
            else:
                self.negotiated_features = []
            max_events = session_block.get("max_events")
            if isinstance(max_events, int) and max_events > 0:
                self.max_events_requested = max_events
            if self._keepalive_enabled:
                self._start_keepalive_locked()
            else:
                self._stop_keepalive_locked()

    # Keepalive management ----------------------------------------------------

    def _start_keepalive_locked(self) -> None:
        if self._keepalive_thread and self._keepalive_thread.is_alive():
            return
        self._keepalive_stop.clear()
        thread = threading.Thread(target=self._keepalive_worker, daemon=True)
        self._keepalive_thread = thread
        thread.start()

    def _stop_keepalive_locked(self) -> None:
        self._keepalive_stop.set()
        thread = self._keepalive_thread
        if thread and thread.is_alive():
            thread.join(timeout=1.0)
        self._keepalive_thread = None

    def _keepalive_worker(self) -> None:
        interval = max(5, int(self.session_heartbeat * 0.5))
        while not self._keepalive_stop.wait(timeout=interval):
            if self.session_disabled or not self.session_id:
                continue
            try:
                self.request({"cmd": "session.keepalive"}, use_session=True, retry=False)
            except Exception:
                # Allow retry on next loop; if the call raised because the
                # session expired the next regular RPC will attempt a reopen.
                continue

    def configure_keepalive(self, *, enabled: bool, interval: Optional[int] = None) -> None:
        """Enable/disable keepalive thread and optionally override interval."""

        with self._session_lock:
            self._keepalive_enabled = enabled
            if interval is not None:
                try:
                    self.session_heartbeat = max(5, int(interval))
                except (TypeError, ValueError):
                    pass
            if not self._keepalive_enabled:
                self._stop_keepalive_locked()
            elif self.session_id:
                self._stop_keepalive_locked()
                self._start_keepalive_locked()

    def configure_session(
        self,
        *,
        pid_lock: Any = _UNSET,
        heartbeat_s: Any = _UNSET,
    ) -> None:
        """Update session parameters such as pid locks or heartbeat interval."""

        changed = False
        with self._session_lock:
            if pid_lock is not _UNSET:
                self._pid_lock_specified = True
                self._pid_lock_value = self._normalise_pid_lock(pid_lock)
                changed = True
            if heartbeat_s is not _UNSET:
                if heartbeat_s is None:
                    self._heartbeat_override = None
                else:
                    try:
                        self._heartbeat_override = max(1, int(heartbeat_s))
                    except (TypeError, ValueError) as exc:
                        raise ExecutiveSessionError("heartbeat_s must be integer-compatible") from exc
                changed = True
        if changed and not self.session_disabled and self.session_id:
            self._ensure_session(force=True)

    # Event streaming ---------------------------------------------------------

    def _open_event_stream(
        self,
        filters: JsonDict,
        ack_interval: int,
    ) -> Optional[_EventStream]:
        if self.session_id is None:
            return None
        try:
            sock = socket.create_connection((self.host, self.port), timeout=self.timeout)
        except OSError:
            return None
        rfile = sock.makefile("r", encoding="utf-8", newline="\n")
        wfile = sock.makefile("w", encoding="utf-8", newline="\n")
        request_payload: JsonDict = {
            "cmd": "events.subscribe",
            "version": 1,
            "session": self.session_id,
        }
        if filters:
            request_payload["filters"] = filters
        wfile.write(_json_dumps(request_payload) + "\n")
        wfile.flush()
        ack_line = rfile.readline()
        if not ack_line:
            sock.close()
            return None
        ack_payload = json.loads(ack_line)
        if ack_payload.get("status") != "ok":
            sock.close()
            return None
        events_block = ack_payload.get("events", {})
        token = ""
        if isinstance(events_block, dict):
            token = str(events_block.get("token") or "")
        # The handshake uses a short timeout; switch the socket back to blocking mode for streaming.
        try:
            sock.settimeout(None)
        except Exception:
            pass
        stop_event = threading.Event()
        thread = threading.Thread(
            target=self._event_stream_worker,
            name="exec-events",
            daemon=True,
            args=(sock, rfile, stop_event, token, ack_interval),
        )
        return _EventStream(sock=sock, rfile=rfile, stop_event=stop_event, thread=thread, token=token)

    def _event_stream_worker(
        self,
        sock: socket.socket,
        rfile: Any,
        stop_event: threading.Event,
        token: str,
        ack_interval: int,
    ) -> None:
        pending_ack = 0
        last_seq_ack = 0
        try:
            while not stop_event.is_set():
                try:
                    line = rfile.readline()
                except TimeoutError:
                    continue
                except OSError as exc:
                    if getattr(exc, "errno", None) == socket.timeout:
                        continue
                    raise
                if not line:
                    break
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                seq_value = event.get("seq")
                if isinstance(seq_value, int) and seq_value > 0:
                    pending_ack += 1
                    last_seq_ack = max(last_seq_ack, seq_value)
                with self._event_buffer_lock:
                    self._event_buffer.append(event)
                callback = self._event_callback
                if callback:
                    try:
                        callback(event)
                    except Exception:
                        # Keep streaming even if the callback bombs out.
                        pass
                if pending_ack >= max(1, ack_interval) and last_seq_ack > 0 and self.session_id:
                    try:
                        self.request({"cmd": "events.ack", "seq": last_seq_ack}, use_session=True, retry=False)
                    except Exception:
                        pass
                    finally:
                        pending_ack = 0
        finally:
            stop_event.set()
            try:
                sock.close()
            except Exception:
                pass
            with self._session_lock:
                if self._event_stream and self._event_stream.token == token:
                    self._event_stream = None

    def _stop_event_stream_locked(self) -> None:
        stream = self._event_stream
        if stream is None:
            return
        stream.stop_event.set()
        try:
            stream.sock.shutdown(socket.SHUT_RDWR)  # type: ignore[attr-defined]
        except Exception:
            pass
        try:
            stream.sock.close()
        except Exception:
            pass
        if stream.thread.is_alive():
            stream.thread.join(timeout=1.0)
        self._event_stream = None
        self._event_callback = None

    def _normalise_pid_lock(self, value: Any) -> Optional[Any]:
        if value is None:
            return None
        if isinstance(value, (list, tuple, set)):
            result = [self._coerce_pid(item) for item in value]
            return result
        return self._coerce_pid(value)

    def _coerce_pid(self, value: Any) -> int:
        try:
            pid = int(value)
        except (TypeError, ValueError) as exc:
            raise ExecutiveSessionError("pid_lock must be integer-compatible") from exc
        if pid < 0:
            raise ExecutiveSessionError("pid_lock values must be non-negative")
        return pid


__all__ = ["ExecutiveSession", "ExecutiveSessionError"]
