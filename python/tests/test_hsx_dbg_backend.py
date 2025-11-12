"""Tests for hsx-dbg DebuggerBackend."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

import sys
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
PYTHON_SRC = REPO_ROOT / "python"
for entry in (REPO_ROOT, PYTHON_SRC):
    if str(entry) not in sys.path:
        sys.path.append(str(entry))

from hsx_dbg.backend import DebuggerBackend, DebuggerBackendError, StackFrame


class StubSession:
    def __init__(self, host: str, port: int, *, responses: Optional[List[Dict[str, Any]]] = None, **_: Any) -> None:
        self.host = host
        self.port = port
        self.requests: List[Dict[str, Any]] = []
        self.responses = list(responses or [])
        self.session_disabled = False
        self.closed = False
        self.keepalive = None

    def configure_keepalive(self, *, enabled: bool, interval: Optional[int]) -> None:
        self.keepalive = (enabled, interval)

    def request(self, payload: Dict[str, Any], **_: Any) -> Dict[str, Any]:
        self.requests.append(payload)
        if self.responses:
            return self.responses.pop(0)
        return {"status": "ok"}

    def close(self) -> None:  # pragma: no cover - defensive
        self.closed = True


def test_backend_pause_sends_rpc():
    stub = StubSession("127.0.0.1", 9998)
    backend = DebuggerBackend(session_factory=lambda *args, **kwargs: stub)
    backend.pause(pid=7)
    assert stub.requests[0] == {"cmd": "pause", "pid": 7}


def test_backend_stack_parses_frames():
    response = {
        "status": "ok",
        "stack": {
            "frames": [
                {"index": 0, "pc": 0x10, "sp": 0x200, "fp": 0x210, "function": "main", "file": "demo.c", "line": 5}
            ]
        },
    }
    stub = StubSession("127.0.0.1", 9998, responses=[response])
    backend = DebuggerBackend(session_factory=lambda *args, **kwargs: stub)
    frames = backend.get_call_stack(pid=1)
    assert isinstance(frames[0], StackFrame)
    assert frames[0].func_name == "main"
    assert frames[0].line == 5


def test_backend_register_state_vectors():
    response = {"status": "ok", "registers": {"regs": list(range(16)), "PC": 0x1234, "SP": 0x2000, "PSW": 0x1}}
    stub = StubSession("127.0.0.1", 9998, responses=[response])
    backend = DebuggerBackend(session_factory=lambda *args, **kwargs: stub)
    regs = backend.get_register_state(pid=1)
    assert regs.registers["R0"] == 0
    assert regs.registers["R15"] == 15
    assert regs.pc == 0x1234 and regs.sp == 0x2000 and regs.psw == 0x1


def test_backend_read_memory_hex():
    response = {"status": "ok", "data": "00010203"}
    stub = StubSession("127.0.0.1", 9998, responses=[response])
    backend = DebuggerBackend(session_factory=lambda *args, **kwargs: stub)
    data = backend.read_memory(0x1000, 4, pid=1)
    assert data == bytes(range(4))
    assert stub.requests[0]["cmd"] == "peek"


def test_backend_errors_raise_exception():
    response = {"status": "error", "error": "fail"}
    stub = StubSession("127.0.0.1", 9998, responses=[response])
    backend = DebuggerBackend(session_factory=lambda *args, **kwargs: stub)
    with pytest.raises(DebuggerBackendError):
        backend.symbol_info(pid=1)
