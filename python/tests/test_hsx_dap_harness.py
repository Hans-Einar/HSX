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


def test_initialize_advertises_instruction_breakpoints() -> None:
    adapter = hsx_dap.HSXDebugAdapter(StubProtocol())
    response = adapter._handle_initialize({})
    capabilities = response["capabilities"]
    assert capabilities["supportsInstructionBreakpoints"] is True


def test_terminate_request_pauses_and_shuts_down() -> None:
    protocol = StubProtocol()

    class TermBackend:
        def __init__(self) -> None:
            self.paused_pid: Optional[int] = None
            self.disconnected = False
            self.stream_stopped = False

        def pause(self, pid: int) -> None:
            self.paused_pid = pid

        def stop_event_stream(self) -> None:
            self.stream_stopped = True

        def disconnect(self) -> None:
            self.disconnected = True

    backend = TermBackend()
    adapter = hsx_dap.HSXDebugAdapter(protocol)
    adapter.client = backend
    adapter.backend = backend
    adapter.current_pid = 9

    result = adapter._handle_terminate({"restart": False})
    assert result == {}
    assert backend.paused_pid == 9
    assert backend.disconnected is True
    assert backend.stream_stopped is True
    terminated_events = [event for event in protocol.events if event["event"] == "terminated"]
    assert terminated_events and terminated_events[-1]["body"] == {"restart": False}
    assert adapter.client is None and adapter.backend is None


def test_launch_uses_backend_attach(monkeypatch: pytest.MonkeyPatch) -> None:
    created: List["StubBackend"] = []

    class StubBackend:
        def __init__(self, **kwargs: Any) -> None:
            self.init_kwargs = kwargs
            self.configure_intervals: List[Optional[int]] = []
            self.attach_calls: List[Dict[str, Any]] = []
            self.event_stream_calls: List[Dict[str, Any]] = []
            self.last_pid: Optional[int] = None
            created.append(self)

        def configure(self, *, keepalive_interval: Optional[int] = None, **_: Any) -> None:
            self.configure_intervals.append(keepalive_interval)

        def attach(self, pid: Optional[int], *, observer: bool = False, heartbeat_s: Optional[int] = None) -> None:
            self.last_pid = pid
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

        def list_tasks(self) -> Dict[str, Any]:
            pid = self.last_pid or 0
            return {"tasks": [{"pid": pid, "state": "running"}], "current_pid": pid}

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
            self.last_pid: Optional[int] = None
            created.append(self)

        def configure(self, *, keepalive_interval: Optional[int] = None, **_: Any) -> None:
            pass

        def attach(self, pid: Optional[int], *, observer: bool = False, heartbeat_s: Optional[int] = None) -> None:
            self.last_pid = pid
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
            pid = self.last_pid or 2
            return {"tasks": [{"pid": pid, "state": "running"}], "current_pid": pid}

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


def test_set_breakpoints_ignores_disassembly_sources(monkeypatch: pytest.MonkeyPatch) -> None:
    adapter = hsx_dap.HSXDebugAdapter(StubProtocol())
    adapter.client = object()
    adapter.current_pid = 1
    monkeypatch.setattr(adapter, "_ensure_symbol_mapper", lambda *args, **kwargs: None)

    response = adapter._handle_setBreakpoints(
        {
            "source": {"path": "hsx-disassembly:/pid-1/0x0000003C"},
            "breakpoints": [{"line": 1}, {"line": 2}],
        }
    )
    assert len(response["breakpoints"]) == 2
    assert all(entry.get("verified") for entry in response["breakpoints"])


def test_remote_breakpoint_sync_emits_telemetry() -> None:
    class RemoteBackend:
        def __init__(self) -> None:
            self.entries: List[int] = []

        def list_breakpoints(self, pid: int) -> List[int]:
            assert pid == 1
            return list(self.entries)

    backend = RemoteBackend()
    protocol = StubProtocol()
    adapter = hsx_dap.HSXDebugAdapter(protocol)
    adapter.client = backend
    adapter.current_pid = 1

    backend.entries = [0x12345678, 0xABCDEF01]
    adapter._sync_remote_breakpoints()

    telemetry_events = [
        event for event in protocol.events if event["event"] == "telemetry" and event["body"].get("subsystem") == "hsx-breakpoints"
    ]
    assert telemetry_events, "expected telemetry when external breakpoints are registered"
    first = telemetry_events[-1]["body"]
    assert first["addedCount"] == 2
    assert first["removedCount"] == 0
    initial_count = len(telemetry_events)

    # Re-run sync with the same high addresses to ensure no phantom add/remove events occur.
    adapter._sync_remote_breakpoints()
    telemetry_events = [
        event for event in protocol.events if event["event"] == "telemetry" and event["body"].get("subsystem") == "hsx-breakpoints"
    ]
    assert len(telemetry_events) == initial_count

    backend.entries = []
    adapter._sync_remote_breakpoints()
    telemetry_events = [
        event for event in protocol.events if event["event"] == "telemetry" and event["body"].get("subsystem") == "hsx-breakpoints"
    ]
    assert len(telemetry_events) == initial_count + 1
    latest = telemetry_events[-1]["body"]
    assert latest["addedCount"] == 0
    assert latest["removedCount"] == 2


def test_write_memory_failure_propagates_error() -> None:
    class WriteBackend:
        def write_memory(self, addr: int, data: bytes, *, pid: int) -> None:
            raise DebuggerBackendError("denied")

    adapter = hsx_dap.HSXDebugAdapter(StubProtocol())
    adapter.client = WriteBackend()
    adapter.current_pid = 1

    with pytest.raises(DebuggerBackendError):
        adapter._handle_writeMemory({"memoryReference": "0x1000", "data": "AQI="})


def test_step_instruction_request(monkeypatch: pytest.MonkeyPatch) -> None:
    class StepBackend:
        def __init__(self) -> None:
            self.calls: List[Dict[str, Any]] = []
            self.cleared: List[int] = []
            self.restored: List[int] = []
            self.modes: List[Dict[str, Any]] = []

        def step(self, pid: int, *, source_only: bool = False) -> None:
            self.calls.append({"pid": pid, "source_only": source_only})

        def set_debug_state(self, pid: int, enable: bool) -> None:
            self.modes.append({"pid": pid, "enable": enable})

        def clear_breakpoint(self, pid: int, address: int) -> None:
            self.cleared.append(address)

        def set_breakpoint(self, pid: int, address: int) -> None:
            self.restored.append(address)

        def list_breakpoints(self, pid: int) -> List[int]:
            return [0x4000]

    protocol = StubProtocol()
    adapter = hsx_dap.HSXDebugAdapter(protocol)
    backend = StepBackend()
    adapter.client = backend
    adapter.current_pid = 3
    key = adapter._instruction_breakpoint_key()
    adapter._breakpoints[key] = [{"addresses": [0x4000]}]

    monkeypatch.setattr(adapter, "_read_current_pc", lambda: 0x4000)

    captured: List[Dict[str, Any]] = []

    def fake_emit(**kwargs: Any) -> None:
        captured.append(kwargs)

    monkeypatch.setattr(adapter, "_emit_stopped_event", fake_emit)
    monkeypatch.setattr(adapter, "_synchronize_execution_state", lambda *args, **kwargs: None)

    adapter._handle_stepInstruction({})
    assert backend.calls == [{"pid": 3, "source_only": False}]
    assert backend.modes == [{"pid": 3, "enable": True}]
    assert backend.cleared == []
    assert backend.restored == []
    assert not captured
    adapter._cancel_step_fallback()
    adapter._step_fallback_check()
    assert captured and captured[-1]["reason"] == "step"


def test_step_instruction_fallback_without_debug_state(monkeypatch: pytest.MonkeyPatch) -> None:
    class LegacyBackend:
        def __init__(self) -> None:
            self.calls: List[Dict[str, Any]] = []
            self.cleared: List[int] = []
            self.restored: List[int] = []

        def step(self, pid: int, *, source_only: bool = False) -> None:
            self.calls.append({"pid": pid, "source_only": source_only})

        def clear_breakpoint(self, pid: int, address: int) -> None:
            self.cleared.append(address)

        def set_breakpoint(self, pid: int, address: int) -> None:
            self.restored.append(address)

        def list_breakpoints(self, pid: int) -> List[int]:
            return [0x5000]

    adapter = hsx_dap.HSXDebugAdapter(StubProtocol())
    backend = LegacyBackend()
    adapter.client = backend
    adapter.current_pid = 9
    key = adapter._instruction_breakpoint_key()
    adapter._breakpoints[key] = [{"addresses": [0x5000]}]
    monkeypatch.setattr(adapter, "_read_current_pc", lambda: 0x5000)
    monkeypatch.setattr(adapter, "_synchronize_execution_state", lambda *args, **kwargs: None)

    adapter._handle_stepInstruction({})
    assert backend.calls == [{"pid": 9, "source_only": False}]
    assert backend.cleared == [0x5000]
    assert backend.restored == [0x5000]


def test_step_requests_enable_and_disable_debug_state(monkeypatch: pytest.MonkeyPatch) -> None:
    class ModeBackend:
        def __init__(self) -> None:
            self.step_calls: List[Dict[str, Any]] = []
            self.mode_calls: List[Dict[str, Any]] = []
            self.resume_calls: int = 0
            self.clock_calls: int = 0

        def step(self, pid: int, *, source_only: bool = False) -> None:
            self.step_calls.append({"pid": pid, "source_only": source_only})

        def set_debug_state(self, pid: int, enable: bool) -> None:
            self.mode_calls.append({"pid": pid, "enable": enable})

        def resume(self, pid: int) -> None:
            self.resume_calls += 1

        def clock_start(self) -> None:
            self.clock_calls += 1

    protocol = StubProtocol()
    adapter = hsx_dap.HSXDebugAdapter(protocol)
    backend = ModeBackend()
    adapter.client = backend
    adapter.current_pid = 4
    monkeypatch.setattr(adapter, "_synchronize_execution_state", lambda *args, **kwargs: None)

    adapter._handle_next({})
    adapter._handle_next({})
    assert backend.step_calls == [
        {"pid": 4, "source_only": True},
        {"pid": 4, "source_only": True},
    ]
    assert backend.mode_calls == [{"pid": 4, "enable": True}]

    adapter._handle_continue({})
    assert {"pid": 4, "enable": False} in backend.mode_calls
    assert backend.resume_calls == 1
    assert backend.clock_calls == 1


def test_disable_debug_state_failure_is_logged(monkeypatch: pytest.MonkeyPatch) -> None:
    adapter = hsx_dap.HSXDebugAdapter(StubProtocol())
    adapter.client = object()  # attribute check handled by monkeypatch below
    adapter._debug_state_pids.add(7)

    def failing_call_backend(*_args: Any, **_kwargs: Any) -> None:
        raise DebuggerBackendError("pid locked elsewhere")

    messages: List[str] = []
    monkeypatch.setattr(adapter, "_call_backend", failing_call_backend)
    monkeypatch.setattr(adapter, "_emit_console_message", lambda text: messages.append(text))
    # pretend client exposes set_debug_state so _disable_debug_state attempts RPC
    monkeypatch.setattr(adapter, "client", type("C", (), {"set_debug_state": lambda *_: None})())

    adapter._disable_debug_state(pid=7, reason="teardown")
    assert 7 not in adapter._debug_state_pids
    assert any("pid locked elsewhere" in entry for entry in messages)


def test_disassemble_requires_pid() -> None:
    adapter = hsx_dap.HSXDebugAdapter(StubProtocol())
    adapter.client = object()
    adapter.current_pid = None
    with pytest.raises(hsx_dap.AdapterCommandError):
        adapter._handle_disassemble({"instructionCount": 4})


def test_attempt_reconnect_uses_cached_config(monkeypatch: pytest.MonkeyPatch) -> None:
    adapter = hsx_dap.HSXDebugAdapter(StubProtocol())
    adapter.current_pid = 5
    adapter._connection_config = {
        "host": "127.0.0.1",
        "port": 9998,
        "pid": 5,
        "observer_mode": False,
        "keepalive_interval": None,
        "heartbeat_override": None,
    }
    called: Dict[str, Any] = {}

    def fake_connect(host: str, port: int, pid: int, **kwargs: Any) -> None:
        called["host"] = host
        called["port"] = port
        called["pid"] = pid
        called["kwargs"] = kwargs
        adapter.client = object()
        adapter.backend = adapter.client

    monkeypatch.setattr(adapter, "_connect", fake_connect)
    monkeypatch.setattr(adapter, "_pid_exists", lambda _pid: True)
    assert adapter._attempt_reconnect(DebuggerBackendError("transport error"))
    assert called["host"] == "127.0.0.1"
    assert called["pid"] == 5


def test_clear_all_breakpoints_request(monkeypatch: pytest.MonkeyPatch) -> None:
    class ClearBackend:
        def __init__(self) -> None:
            self.cleared: List[int] = []

        def clear_breakpoint(self, pid: int, address: int) -> None:
            self.cleared.append(address)

        def list_breakpoints(self, pid: int) -> List[int]:
            return []

    adapter = hsx_dap.HSXDebugAdapter(StubProtocol())
    backend = ClearBackend()
    adapter.client = backend
    adapter.current_pid = 5
    instr_key = adapter._instruction_breakpoint_key()
    remote_key = adapter._remote_breakpoint_key()
    adapter._breakpoints[instr_key] = [{"addresses": [0x100, 0x104]}]
    adapter._breakpoints[remote_key] = [{"addresses": [0x200], "readonly": True}]

    result = adapter._handle_clearAllBreakpoints({})
    assert result["cleared"] == 3
    assert sorted(backend.cleared) == [0x100, 0x104, 0x200]
    assert adapter._breakpoints == {}


def test_task_state_debug_break_falls_back_to_stopped() -> None:
    protocol = StubProtocol()
    adapter = hsx_dap.HSXDebugAdapter(protocol)
    adapter.current_pid = 1
    adapter._thread_states[1] = {"name": "PID 1", "state": None}
    adapter._handle_task_state_event({"pid": 1, "data": {"new_state": "paused", "reason": "debug_break", "details": {"pc": "0x20"}}})
    stopped_events = [event for event in protocol.events if event["event"] == "stopped"]
    assert len(stopped_events) == 1
    last = stopped_events[-1]["body"]
    assert last["reason"] == "debug_break"
    assert last["instructionPointerReference"] == "0x20"

    # Duplicate event in quick succession should be suppressed.
    protocol.events.clear()
    adapter._handle_task_state_event({"pid": 1, "data": {"new_state": "paused", "reason": "debug_break", "details": {"pc": "0x20"}}})
    assert not [event for event in protocol.events if event["event"] == "stopped"]


def test_trace_requests(monkeypatch: pytest.MonkeyPatch) -> None:
    class TraceBackend:
        def __init__(self) -> None:
            self.mode_changes: List[Optional[bool]] = []

        def trace_records(self, pid: int, *, limit: Optional[int] = None, export: bool = False) -> Dict[str, Any]:
            assert pid == 1
            assert limit == 5
            return {
                "pid": pid,
                "records": [
                    {"seq": 1, "pc": 0x10, "opcode": 0x20},
                    {"seq": 2, "pc": 0x14, "opcode": 0x24},
                ],
            }

        def trace_control(self, pid: int, enable: Optional[bool]) -> Dict[str, Any]:
            assert pid == 1
            self.mode_changes.append(enable)
            return {"enabled": enable}

    backend = TraceBackend()
    adapter = hsx_dap.HSXDebugAdapter(StubProtocol())
    adapter.client = backend
    adapter.current_pid = 1

    records = adapter._handle_traceRecords({"limit": 5})
    assert isinstance(records["records"], list)
    assert records["records"][0]["pc"] == 0x10

    state = adapter._handle_traceControl({"enabled": True})
    assert state["enabled"] is True
    assert backend.mode_changes == [True]


def test_read_registers_custom_request(monkeypatch: pytest.MonkeyPatch) -> None:
    adapter = hsx_dap.HSXDebugAdapter(StubProtocol())
    adapter.client = object()
    adapter.current_pid = 1
    monkeypatch.setattr(adapter, "_format_registers", lambda: [{"name": "R00", "value": "0x0"}])
    response = adapter._handle_readRegisters({})
    assert response["registers"][0]["name"] == "R00"


def test_stopped_event_emits_disassembly_telemetry(monkeypatch: pytest.MonkeyPatch) -> None:
    protocol = StubProtocol()
    adapter = hsx_dap.HSXDebugAdapter(protocol)
    adapter.current_pid = 1

    monkeypatch.setattr(adapter, "_ensure_symbol_mapper", lambda *args, **kwargs: None)
    monkeypatch.setattr(adapter, "_map_pc_to_source", lambda pc: None)

    adapter._emit_stopped_event(pid=1, reason="breakpoint", description="hit", pc=0x1234)

    telemetry_events = [
        event for event in protocol.events if event["event"] == "telemetry" and event["body"].get("subsystem") == "hsx-disassembly"
    ]
    assert telemetry_events, "expected disassembly telemetry after stopped event"
    last = telemetry_events[-1]["body"]
    assert last.get("action") == "refresh"
    assert last.get("pc") == "0x1234"


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
