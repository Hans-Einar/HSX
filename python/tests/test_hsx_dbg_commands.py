"""Unit tests for hsx-dbg command helpers."""

from __future__ import annotations

import sys
from pathlib import Path
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(REPO_ROOT / "python"))

from hsx_dbg.commands.alias import AliasCommand
from hsx_dbg.commands.attach import AttachCommand
from hsx_dbg.commands.breakpoints import BreakpointCommand
from hsx_dbg.commands.control import ContinueCommand, PauseCommand, StepCommand
from hsx_dbg.commands.detach import DetachCommand
from hsx_dbg.commands.info import InfoCommand
from hsx_dbg.commands.ps import PsCommand
from hsx_dbg.commands.session import SessionCommand
from hsx_dbg.commands.stack import StackCommand
from hsx_dbg.commands.watch import WatchCommand
from hsx_dbg.context import DebuggerContext


@dataclass
class DummySession:
    responses: List[Dict[str, Any]] = field(default_factory=list)
    requests: List[Dict[str, Any]] = field(default_factory=list)

    def request(self, payload: Dict[str, Any], **_: Any) -> Dict[str, Any]:
        self.requests.append(payload)
        if self.responses:
            return self.responses.pop(0)
        return {"status": "ok"}


class StubContext(DebuggerContext):
    def __init__(
        self,
        responses: Optional[List[Dict[str, Any]]] = None,
        *,
        json_output: bool = False,
        symbol_path: Optional[str] = None,
    ):
        super().__init__(host="127.0.0.1", port=9998, json_output=json_output)
        self._dummy_session = DummySession(list(responses or []))
        self._session = self._dummy_session
        if symbol_path:
            self.set_symbol_file(symbol_path)

    def ensure_session(self, *, auto_events: bool = True):  # type: ignore[override]
        return self._dummy_session


def test_attach_command_requests_attach(capsys):
    ctx = StubContext([{"status": "ok", "info": {}}])
    cmd = AttachCommand()
    rc = cmd.run(ctx, [])
    assert rc == 0
    assert ctx.session.requests == [{"cmd": "attach"}]  # type: ignore[arg-type]
    out = capsys.readouterr().out
    assert "Attached" in out


def test_detach_command_requests_detach(capsys):
    ctx = StubContext([{"status": "ok", "info": {}}])
    cmd = DetachCommand()
    rc = cmd.run(ctx, [])
    assert rc == 0
    assert ctx.session.requests == [{"cmd": "detach"}]  # type: ignore[arg-type]
    out = capsys.readouterr().out
    assert "Detached" in out


def test_pause_and_continue_commands(capsys):
    ctx = StubContext([{"status": "ok"}, {"status": "ok"}])
    pause = PauseCommand()
    resume = ContinueCommand()
    assert pause.run(ctx, ["1"]) == 0
    assert resume.run(ctx, ["1"]) == 0
    assert ctx.session.requests == [  # type: ignore[arg-type]
        {"cmd": "pause", "pid": 1},
        {"cmd": "resume", "pid": 1},
    ]
    out = capsys.readouterr().out
    assert "Paused PID 1" in out
    assert "Resumed PID 1" in out


def test_step_command_sends_step_payload(capsys):
    response = {
        "status": "ok",
        "result": {"executed": 5},
        "clock": {"state": "running"},
    }
    ctx = StubContext([response])
    cmd = StepCommand()
    rc = cmd.run(ctx, ["7", "5"])
    assert rc == 0
    assert ctx.session.requests == [{"cmd": "step", "pid": 7, "steps": 5}]  # type: ignore[arg-type]
    out = capsys.readouterr().out
    assert "Stepped PID 7" in out


def test_ps_command_renders_metadata(capsys):
    tasks = {
        "current_pid": 1,
        "tasks": [
            {
                "pid": 1,
                "state": "paused",
                "priority": 5,
                "quantum": 1,
                "accounted_steps": 10,
                "sleep_pending": False,
                "trace": False,
                "app_name": "demo",
                "metadata": {"values": 2, "commands": 1},
            }
        ],
    }
    ctx = StubContext([{"status": "ok", "tasks": tasks}])
    cmd = PsCommand()
    rc = cmd.run(ctx, [])
    assert rc == 0
    out = capsys.readouterr().out
    assert "demo" in out and "V:2" in out


def test_info_pid_outputs_registers(capsys):
    info_payload = {
        "status": "ok",
        "info": {
            "running": False,
            "paused": True,
            "attached": True,
            "task": {
                "pid": 3,
                "state": "paused",
                "app_name": "demo",
                "metadata": {"mailboxes": 4},
            },
            "selected_registers": {"regs": [0, 1, 2]},
        },
    }
    ctx = StubContext([info_payload])
    cmd = InfoCommand()
    rc = cmd.run(ctx, ["3"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "task pid=3" in out
    assert "R00" in out


def test_alias_command_sets_mapping(capsys):
    ctx = StubContext()
    cmd = AliasCommand()
    assert cmd.run(ctx, []) == 0  # list
    assert cmd.run(ctx, ["b", "break"]) == 0
    assert ctx.aliases["b"] == "break"
    out = capsys.readouterr().out
    assert "b -> break" in out


def test_session_list_command(capsys):
    sessions = [
        {"id": "abc", "client": "hsx-dbg", "pid_locks": [1], "features": ["events"]}
    ]
    ctx = StubContext([{"status": "ok", "session": {"id": "abc", "client": "hsx-dbg"}}, {"status": "ok", "sessions": sessions}])
    cmd = SessionCommand()
    assert cmd.run(ctx, []) == 0
    assert cmd.run(ctx, ["list"]) == 0
    out = capsys.readouterr().out
    assert "sessions:" in out


def test_json_output_schema_for_pause(capsys):
    ctx = StubContext([{"status": "ok"}], json_output=True)
    cmd = PauseCommand()
    assert cmd.run(ctx, ["1"]) == 0
    out = capsys.readouterr().out.strip()
    assert out.startswith("{") and '"status": "ok"' in out


def test_watch_add_and_list(capsys):
    ctx = StubContext([{"status": "ok", "watch": {"watch_id": 1, "expr": "counter", "value": 0}}, {"status": "ok", "watches": [{"watch_id": 1, "expr": "counter", "value": 0}]}])
    cmd = WatchCommand()
    assert cmd.run(ctx, ["add", "1", "counter"]) == 0
    assert cmd.run(ctx, ["list", "1"]) == 0
    out = capsys.readouterr().out
    assert "watch 1" in out


def test_stack_bt_and_frame(capsys):
    stack_info = {
        "frames": [
            {"index": 0, "pc": 0x10, "symbol": {"name": "main"}, "file": "main.c", "line": 3},
            {"index": 1, "pc": 0x20, "symbol": {"name": "loop"}, "file": "main.c", "line": 8},
        ]
    }
    ctx = StubContext([{"status": "ok", "stack": stack_info}])
    cmd = StackCommand()
    assert cmd.run(ctx, ["bt", "1"]) == 0
    ctx._dummy_session.responses = []  # frame command should use cache
    assert cmd.run(ctx, ["frame", "1", "1"]) == 0


def test_break_add_symbol_line(tmp_path):
    sym_path = "examples/demos/build/debug/longrun/main.sym"
    ctx = StubContext([{"status": "ok"}], symbol_path=sym_path)
    cmd = BreakpointCommand()
    # use a real line from the sym file
    addresses = ctx.lookup_line("examples/demos/longrun/main.c", 6)
    assert addresses, "symbol lookup should produce at least one address"
    responses = ["ok"] * len(addresses)
    ctx._dummy_session.responses = [{"status": "ok"} for _ in addresses]
    rc = cmd.run(ctx, ["add", "1", "examples/demos/longrun/main.c:6"])
    assert rc == 0
    reqs = ctx.session.requests  # type: ignore[arg-type]
    assert len(reqs) == len(addresses)
    for request in reqs:
        assert request["cmd"] == "bp"
        assert request["op"] == "set"
        assert request["pid"] == 1


def test_break_disable_enable_tracks_state():
    ctx = StubContext([{"status": "ok"}, {"status": "ok"}, {"status": "ok"}])
    cmd = BreakpointCommand()
    assert cmd.run(ctx, ["disable", "1", "0x12"]) == 0
    assert 0x12 in ctx.disabled_breakpoints.get(1, set())
    ctx._dummy_session.responses = [{"status": "ok"}]
    assert cmd.run(ctx, ["enable", "1", "0x12"]) == 0
    assert 0x12 not in ctx.disabled_breakpoints.get(1, set())
