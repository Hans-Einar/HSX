"""Stub backend implementations for DAP integration tests."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from hsx_dbg import RegisterState, StackFrame, WatchValue


@dataclass
class RecordedEvent:
    type: str
    payload: Dict[str, Any]


class CapturingBackend:
    """Minimal backend used by subprocess DAP tests."""

    def __init__(self, *, host: str, port: int, features: List[str]) -> None:
        self.host = host
        self.port = port
        self.features = list(features)
        self.pid: Optional[int] = None
        self.breakpoints: List[int] = []
        self.events: List[RecordedEvent] = []
        self.sym_path: Optional[str] = None

    # Session controls --------------------------------------------------
    def configure(self, **_: Any) -> None:  # pragma: no cover - trivial
        pass

    def attach(self, pid: Optional[int], *, observer: bool = False, heartbeat_s: Optional[int] = None) -> None:
        self.pid = pid
        self.events.append(RecordedEvent("attach", {"pid": pid, "observer": observer, "heartbeat": heartbeat_s}))

    def start_event_stream(self, **_: Any) -> bool:
        self.events.append(RecordedEvent("start_event_stream", {}))
        return True

    def stop_event_stream(self) -> None:  # pragma: no cover - not used
        self.events.append(RecordedEvent("stop_event_stream", {}))

    def disconnect(self) -> None:  # pragma: no cover - not used
        self.events.append(RecordedEvent("disconnect", {}))

    # Breakpoints -------------------------------------------------------
    def set_breakpoint(self, pid: int, address: int) -> None:
        self.breakpoints.append(address & 0xFFFF)

    def clear_breakpoint(self, pid: int, address: int) -> None:  # pragma: no cover - not used
        self.breakpoints = [value for value in self.breakpoints if value != (address & 0xFFFF)]

    def list_breakpoints(self, pid: int) -> List[int]:
        return list(self.breakpoints)

    # Symbols -----------------------------------------------------------
    def symbol_info(self, pid: int) -> Dict[str, Any]:
        return {"loaded": bool(self.sym_path), "path": self.sym_path}

    def load_symbols(self, pid: int, path: Optional[str] = None) -> Dict[str, Any]:
        self.sym_path = path
        return {"loaded": True, "path": path}

    def symbol_lookup_name(self, pid: int, name: str) -> Optional[Dict[str, Any]]:
        if name == "main":
            return {"address": 0x4000}
        return None

    # Stack / registers / memory ---------------------------------------
    def get_register_state(self, pid: int) -> RegisterState:
        registers = {f"R{i}": i for i in range(16)}
        return RegisterState(registers, pc=0x4000, sp=0x2000, psw=0x1)

    def get_call_stack(self, pid: int, *, max_frames: Optional[int] = None) -> List[StackFrame]:
        return [
            StackFrame(index=0, pc=0x4000, sp=0x2000, fp=0x2100, func_name="main", file="sample.c", line=10),
        ]

    def read_memory(self, addr: int, length: int, *, pid: int) -> Optional[bytes]:
        return bytes((addr + i) % 256 for i in range(length))

    def write_memory(self, addr: int, data: bytes, *, pid: int) -> None:  # pragma: no cover - not used
        pass

    # Watches -----------------------------------------------------------
    def list_watches(self, pid: int) -> List[WatchValue]:
        return []

    def add_watch(self, expr: str, *, pid: int) -> WatchValue:
        return WatchValue(watch_id=1, expr=expr, length=4, value="0x0")

    def remove_watch(self, watch_id: int, *, pid: int) -> None:  # pragma: no cover - not used
        pass


def create_backend(**kwargs: Any) -> CapturingBackend:
    backend = CapturingBackend(**kwargs)
    backend.sym_path = kwargs.get("sym_path")
    return backend
