"""Lightweight harness tests for hsx-dap."""

from __future__ import annotations

from pathlib import Path
import json
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
from hsx_dbg.symbols import SymbolIndex
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

        def list_tasks(self) -> Dict[str, Any]:
            return {"tasks": [{"pid": 2}], "current_pid": 2}

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


def test_disassembly_formatting_accepts_operand_strings() -> None:
    adapter = hsx_dap.HSXDebugAdapter(StubProtocol())
    block = {
        "instructions": [
            {"pc": 0x10, "mnemonic": "LDI", "operands": "R1 <- 0x5", "bytes": "01020304"},
            {"pc": 0x14, "mnemonic": "ADD", "operands": ["R0", "R1"], "bytes": "10200000"},
        ]
    }
    lines = adapter._format_disassembly(block, resolve_symbols=False)
    assert lines[0]["instruction"] == "LDI R1 <- 0x5"
    assert lines[1]["instruction"] == "ADD R0, R1"


def test_instruction_breakpoints_round_trip() -> None:
    class InstructionBackend:
        def __init__(self) -> None:
            self.set_calls: List[int] = []
            self.clear_calls: List[int] = []

        def configure(self, **_: Any) -> None:
            pass

        def attach(self, *args: Any, **kwargs: Any) -> None:
            pass

        def start_event_stream(self, **_: Any) -> bool:
            return True

        def set_breakpoint(self, pid: int, address: int) -> None:
            self.set_calls.append(address)

        def clear_breakpoint(self, pid: int, address: int) -> None:
            self.clear_calls.append(address)

        def list_breakpoints(self, pid: int) -> List[int]:
            return []

        def list_tasks(self) -> Dict[str, Any]:
            return {"tasks": [{"pid": 1}], "current_pid": 1}

    backend = InstructionBackend()
    adapter = hsx_dap.HSXDebugAdapter(StubProtocol())
    adapter.client = backend
    adapter.current_pid = 1

    resp = adapter._handle_setInstructionBreakpoints({"breakpoints": [{"instructionReference": "0x100"}]})
    assert resp["breakpoints"][0]["verified"] is True
    assert backend.set_calls == [0x100]
    assert backend.clear_calls == []

    resp = adapter._handle_setInstructionBreakpoints(
        {"breakpoints": [{"instructionReference": "0x104"}, {"instructionReference": "0x108"}]}
    )
    assert len(resp["breakpoints"]) == 2
    assert backend.set_calls == [0x100, 0x104, 0x108]
    assert backend.clear_calls == [0x100]


def test_pid_exists_queries_task_list() -> None:
    class TaskBackend:
        def __init__(self) -> None:
            pass

        def list_tasks(self) -> Dict[str, Any]:
            return {"tasks": [{"pid": 2}, {"pid": 3}], "current_pid": 2}

    adapter = hsx_dap.HSXDebugAdapter(StubProtocol())
    adapter.client = TaskBackend()
    assert adapter._pid_exists(3) is True
    assert adapter._pid_exists(7) is False


def test_function_breakpoints_use_symbol_mapper() -> None:
    class FunctionBackend:
        def __init__(self) -> None:
            self.set_calls: List[int] = []

        def set_breakpoint(self, pid: int, address: int) -> None:
            self.set_calls.append(address)

    class SymbolStub:
        def lookup_symbol(self, name: str) -> List[int]:
            if name == "main":
                return [0x4000, 0x4002]
            return []

    adapter = hsx_dap.HSXDebugAdapter(StubProtocol())
    adapter.client = FunctionBackend()
    adapter.current_pid = 1
    adapter._symbol_mapper = SymbolStub()

    response = adapter._handle_setFunctionBreakpoints({"breakpoints": [{"name": "main"}]})
    assert response["breakpoints"][0]["verified"] is True
    assert adapter.client.set_calls == [0x4000, 0x4002]


def test_breakpoints_match_golden_fixture(tmp_path: Path) -> None:
    fixtures = Path(__file__).resolve().parent / "fixtures"
    sym_path = fixtures / "sample_debug.sym"
    golden_path = fixtures / "breakpoints_golden.json"
    golden = json.loads(golden_path.read_text(encoding="utf-8"))

    class GoldenBackend:
        def __init__(self) -> None:
            self.addresses: List[int] = []

        def configure(self, **_: Any) -> None:
            pass

        def attach(self, *args: Any, **kwargs: Any) -> None:
            pass

        def start_event_stream(self, **_: Any) -> bool:
            return True

        def set_breakpoint(self, pid: int, address: int) -> None:
            self.addresses.append(address)

        def clear_breakpoint(self, pid: int, address: int) -> None:
            pass

        def list_breakpoints(self, pid: int) -> List[int]:
            return []

    backend = GoldenBackend()
    adapter = hsx_dap.HSXDebugAdapter(StubProtocol())
    adapter.client = backend
    adapter.current_pid = 5
    adapter._sym_hint = sym_path
    adapter._symbol_mapper = SymbolIndex(sym_path)

    source_request = {
        "source": {"path": "sample.c"},
        "breakpoints": [{"line": 10}, {"line": 15}],
    }
    response = adapter._handle_setBreakpoints(source_request)
    seen = [
        {"line": entry.get("line"), "address": f"0x{entry.get('address', 0):04X}"}
        for entry in response["breakpoints"]
        if entry.get("verified")
    ]
    assert seen == golden["source"]

    func_response = adapter._handle_setFunctionBreakpoints({"breakpoints": [{"name": "main"}]})
    func_seen = [
        {"name": entry.get("name"), "address": f"0x{entry.get('address', 0):04X}"}
        for entry in func_response["breakpoints"]
        if entry.get("verified")
    ]
    assert func_seen == golden["functions"]
