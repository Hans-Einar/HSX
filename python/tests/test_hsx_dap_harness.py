"""Lightweight harness tests for hsx-dap."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

import sys

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
PYTHON_SRC = REPO_ROOT / "python"
if str(REPO_ROOT) not in sys.path:
    sys.path.append(str(REPO_ROOT))
if str(PYTHON_SRC) not in sys.path:
    sys.path.append(str(PYTHON_SRC))

from hsx_dbg import DebuggerBackendError, RegisterState, StackFrame, WatchValue
from python import hsx_dap


class StubProtocol:
    def __init__(self) -> None:
        self.events: List[Dict[str, Any]] = []

    def send_event(self, event: str, body: Optional[Dict[str, Any]] = None) -> None:
        self.events.append({"event": event, "body": body or {}})

    def send_response(self, *args: Any, **kwargs: Any) -> None:  # pragma: no cover - harness doesn't inspect responses
        pass


def test_launch_uses_backend_attach(monkeypatch: pytest.MonkeyPatch) -> None:
    created: List["StubBackend"] = []

    class StubBackend:
        def __init__(self, **kwargs: Any) -> None:
            self.init_kwargs = kwargs
            self.configure_intervals: List[Optional[int]] = []
            self.attach_calls: List[Dict[str, Any]] = []
            self.event_stream_calls: List[Dict[str, Any]] = []
            created.append(self)

        def configure(self, *, keepalive_interval: Optional[int] = None, **_: Any) -> None:
            self.configure_intervals.append(keepalive_interval)

        def attach(self, pid: Optional[int], *, observer: bool = False, heartbeat_s: Optional[int] = None) -> None:
            self.attach_calls.append({"pid": pid, "observer": observer, "heartbeat": heartbeat_s})

        def start_event_stream(self, *, filters: Dict[str, Any], callback, ack_interval: int) -> bool:
            self.event_stream_calls.append({"filters": filters, "ack_interval": ack_interval, "callback": callback})
            return True

        def list_breakpoints(self, pid: int) -> List[int]:
            return []

        def symbol_info(self, pid: int) -> Dict[str, Any]:
            return {"loaded": False}

        def load_symbols(self, pid: int, path: Optional[str] = None) -> Dict[str, Any]:
            return {}

        def disconnect(self) -> None:  # pragma: no cover - not used in this test
            pass

    monkeypatch.setattr(hsx_dap, "DebuggerBackend", StubBackend)
    adapter = hsx_dap.HSXDebugAdapter(StubProtocol())
    args = {
        "pid": 7,
        "host": "localhost",
        "port": 10000,
        "observerMode": True,
        "keepaliveInterval": 15,
        "sessionHeartbeat": 12,
    }
    adapter._handle_launch(args)

    assert len(created) == 1
    backend = created[0]
    # keepalive interval forwarded to backend.configure
    assert backend.configure_intervals == [15]
    # attach requested observer mode + heartbeat override
    assert backend.attach_calls == [{"pid": 7, "observer": True, "heartbeat": 12}]
    # event stream subscribed to pid filters
    assert backend.event_stream_calls
    filters = backend.event_stream_calls[0]["filters"]
    assert filters["pid"] == [7]


def test_reconnect_reapplies_breakpoints(monkeypatch: pytest.MonkeyPatch) -> None:
    created: List["ReconnectBackend"] = []

    class ReconnectBackend:
        def __init__(self, **_: Any) -> None:
            self.attach_calls: List[Dict[str, Any]] = []
            self.event_stream_calls: List[Dict[str, Any]] = []
            self.breakpoints: List[int] = []
            self._resume_failures = 1
            created.append(self)

        def configure(self, *, keepalive_interval: Optional[int] = None, **_: Any) -> None:
            pass

        def attach(self, pid: Optional[int], *, observer: bool = False, heartbeat_s: Optional[int] = None) -> None:
            self.attach_calls.append({"pid": pid, "observer": observer, "heartbeat": heartbeat_s})

        def start_event_stream(self, *, filters: Dict[str, Any], callback, ack_interval: int) -> bool:
            self.event_stream_calls.append({"filters": filters, "ack_interval": ack_interval, "callback": callback})
            return True

        def list_breakpoints(self, pid: int) -> List[int]:
            return []

        def symbol_info(self, pid: int) -> Dict[str, Any]:
            return {"loaded": False}

        def load_symbols(self, pid: int, path: Optional[str] = None) -> Dict[str, Any]:
            return {}

        def set_breakpoint(self, pid: int, address: int) -> None:
            self.breakpoints.append(address)

        def clear_breakpoint(self, pid: int, address: int) -> None:
            pass

        def resume(self, pid: int) -> None:
            if self._resume_failures > 0:
                self._resume_failures -= 1
                raise DebuggerBackendError("transport lost")

        def clock_start(self) -> None:
            pass

        def stop_event_stream(self) -> None:  # pragma: no cover - not used in test
            pass

        def disconnect(self) -> None:  # pragma: no cover - not used in test
            pass

    def backend_factory(**kwargs: Any) -> ReconnectBackend:
        backend = ReconnectBackend(**kwargs)
        # Only the first backend should fail resume; subsequent ones succeed.
        if len(created) > 1:
            backend._resume_failures = 0
        return backend

    monkeypatch.setattr(hsx_dap, "DebuggerBackend", backend_factory)
    adapter = hsx_dap.HSXDebugAdapter(StubProtocol())
    launch_args = {"pid": 2, "host": "localhost", "port": 10000}
    adapter._handle_launch(launch_args)

    # Seed a breakpoint so reconnection has something to reapply.
    bps = {"source": {"path": "main.c"}, "breakpoints": [{"instructionReference": "0x200"}]}
    adapter._handle_setBreakpoints(bps)
    assert created[0].breakpoints == [0x200]

    # Force resume; first backend raises, triggering reconnection.
    adapter._handle_continue({})
    assert len(created) >= 2
    # New backend should receive the breakpoint during reapply
    assert created[1].breakpoints == [0x200]


def test_stacktrace_and_scopes(monkeypatch: pytest.MonkeyPatch) -> None:
    class StackBackend:
        def __init__(self) -> None:
            path = (REPO_ROOT / "python/tests/test_hsx_dap_harness.py").resolve()
            self.frames = [
                StackFrame(index=0, pc=0x1000, sp=0x2000, fp=0x2100, func_name="main", file=str(path), line=10),
                StackFrame(index=1, pc=0x1100, sp=0x2010, fp=0x2110, func_name="helper", file=str(path), line=42),
            ]
            self.register_state = RegisterState({f"R{i}": i for i in range(16)}, pc=0x1000, sp=0x2000, psw=0x1)
            self.watch_values = [
                WatchValue(watch_id=1, expr="foo", length=4, value="0x1", address=0x3000),
            ]
            self.stack_calls: List[Dict[str, Any]] = []

        def get_call_stack(self, pid: int, *, max_frames: Optional[int] = None) -> List[StackFrame]:
            self.stack_calls.append({"pid": pid, "max_frames": max_frames})
            if max_frames is None:
                return self.frames
            return self.frames[:max_frames]

        def get_register_state(self, pid: int) -> RegisterState:
            return self.register_state

        def list_watches(self, pid: int) -> List[WatchValue]:
            return self.watch_values

    backend = StackBackend()
    adapter = hsx_dap.HSXDebugAdapter(StubProtocol())
    adapter.client = backend
    adapter.current_pid = 3

    stack_result = adapter._handle_stackTrace({"startFrame": 0, "levels": 2})
    assert stack_result["stackFrames"][0]["line"] == 10
    assert backend.stack_calls == [{"pid": 3, "max_frames": 2}]

    frame_id = stack_result["stackFrames"][0]["id"]
    scopes = adapter._handle_scopes({"frameId": frame_id})["scopes"]
    scope_names = [scope["name"] for scope in scopes]
    assert "Registers" in scope_names
    assert "Watches" in scope_names

    # Inspect registers scope contents via variables request.
    registers_scope = next(scope for scope in scopes if scope["name"] == "Registers")
    vars_payload = adapter._handle_variables({"variablesReference": registers_scope["variablesReference"]})
    reg_names = {entry["name"] for entry in vars_payload["variables"]}
    assert "R00" in reg_names and "PC" in reg_names

    watches_scope = next(scope for scope in scopes if scope["name"] == "Watches")
    watch_vars = adapter._handle_variables({"variablesReference": watches_scope["variablesReference"]})["variables"]
    assert watch_vars[0]["memoryReference"] == "0x00003000"
