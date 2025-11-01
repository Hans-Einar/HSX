import json
from pathlib import Path

import pytest

from python.execd import ExecutiveState, SessionError


class DummyVM:
    def attach(self):
        return {}

    def detach(self):
        return {}

    def info(self, pid=None):
        return {}

    def ps(self):
        return {}

    def restart(self, targets):
        return {}


def make_state():
    return ExecutiveState(DummyVM(), step_batch=1)


def test_session_open_records_pid_lock_and_warnings():
    state = make_state()
    session = state.session_open(
        client="hsxdbg",
        capabilities={"features": ["events", "watch"], "max_events": 512},
        pid_lock=3,
    )
    session_id = session["id"]
    assert session["client"] == "hsxdbg"
    assert session["pid_lock"] == 3
    # unsupported feature should be rejected with a warning
    assert "unsupported_feature:watch" in session.get("warnings", [])
    # requested max_events honoured within limits
    assert session["max_events"] == 512
    assert state.pid_locks[3] == session_id


def test_session_open_clamps_max_events_and_heartbeat():
    state = make_state()
    session = state.session_open(
        client="hsxdbg",
        capabilities={"max_events": 4096},
        pid_lock=None,
        heartbeat_s=1,
    )
    assert session["pid_lock"] is None
    warnings = session.get("warnings", [])
    assert any(w.startswith("max_events_clamped") for w in warnings)
    assert any(w.startswith("heartbeat_clamped") for w in warnings)
    assert session["heartbeat_s"] >= state.session_heartbeat_min
    assert session["max_events"] == state.session_events_max


def test_session_open_conflicting_pid_lock_raises():
    state = make_state()
    state.session_open(pid_lock=7)
    with pytest.raises(SessionError) as excinfo:
        state.session_open(pid_lock=7)
    assert "pid_locked:7" in str(excinfo.value)


def test_session_keepalive_updates_last_seen():
    state = make_state()
    payload = state.session_open(pid_lock=None)
    session_id = payload["id"]
    record = state.sessions[session_id]
    record.last_seen -= 10
    before = record.last_seen
    state.session_keepalive(session_id)
    after = state.sessions[session_id].last_seen
    assert after > before


def test_session_keepalive_unknown_session_errors():
    state = make_state()
    with pytest.raises(SessionError):
        state.session_keepalive("missing")


def test_session_timeout_releases_lock():
    state = make_state()
    payload = state.session_open(pid_lock=5, heartbeat_s=1)
    session_id = payload["id"]
    record = state.sessions[session_id]
    record.last_seen -= (record.heartbeat_s + 1)
    state._last_session_prune = 0
    state.prune_sessions()
    assert session_id not in state.sessions
    assert 5 not in state.pid_locks


def test_session_close_releases_locks_and_blocks_further_calls():
    state = make_state()
    payload = state.session_open(pid_lock=9)
    session_id = payload["id"]
    state.session_close(session_id)
    assert session_id not in state.sessions
    assert 9 not in state.pid_locks
    with pytest.raises(SessionError):
        state.session_close(session_id)


def test_ensure_pid_access_respects_owner():
    state = make_state()
    owner = state.session_open(pid_lock=11)["id"]
    observer = state.session_open(pid_lock=None)["id"]
    # owner access succeeds
    state.ensure_pid_access(11, owner)
    # observer and sessionless callers are blocked
    with pytest.raises(SessionError):
        state.ensure_pid_access(11, observer)
    with pytest.raises(SessionError):
        state.ensure_pid_access(11, None)
    # unrelated pid remains accessible
    state.ensure_pid_access(42, observer)


def test_events_subscribe_receives_emitted_events():
    state = make_state()
    session_id = state.session_open(capabilities={"features": ["events"]})["id"]
    subscription = state.events_subscribe(session_id)
    state.emit_event("debug_break", pid=3, data={"pc": 0x100})
    event = state.events_next(subscription, timeout=0.1)
    assert event is not None
    assert event["type"] == "debug_break"
    assert event["pid"] == 3
    assert event["data"]["pc"] == 0x100


def test_events_ack_clears_queue():
    state = make_state()
    session_id = state.session_open(capabilities={"features": ["events"]})["id"]
    subscription = state.events_subscribe(session_id)
    emitted = state.emit_event("scheduler", pid=None, data={"state": "READY", "next_pid": 1})
    assert state.events_next(subscription, timeout=0.1) is not None
    # requeue another event
    state.emit_event("scheduler", pid=None, data={"state": "RUNNING", "next_pid": 1})
    state.events_ack(session_id, emitted["seq"])
    with subscription.condition:
        assert all(item["seq"] > emitted["seq"] for item in subscription.queue)


def test_events_queue_drop_emits_warning():
    state = make_state()
    session_id = state.session_open(capabilities={"features": ["events"], "max_events": 2})["id"]
    subscription = state.events_subscribe(session_id)
    first = state.emit_event("trace_step", pid=1, data={"pc": 0x10})
    second = state.emit_event("trace_step", pid=1, data={"pc": 0x14})
    third = state.emit_event("trace_step", pid=1, data={"pc": 0x18})
    # drain events to inspect warning presence
    collected = []
    for _ in range(3):
        evt = state.events_next(subscription, timeout=0.1)
        if evt is not None:
            collected.append(evt)
    types = {evt["type"] for evt in collected if evt}
    assert "warning" in types
    assert any(evt["type"] == "trace_step" and evt["data"]["pc"] == 0x18 for evt in collected)


class DebugVM:
    def __init__(self) -> None:
        self.breakpoints: set[int] = set()
        self.requests: list[dict] = []
        self.attach_calls = 0
        self.pc = 0
        self.step_delta = 0x10
        self.step_calls = 0
        self.paused = False

    def request(self, payload: dict) -> dict:
        self.requests.append(payload)
        if payload.get('cmd') != 'dbg':
            raise AssertionError('unexpected cmd')
        op = payload.get('op')
        if op == 'attach':
            self.attach_calls += 1
            return {'status': 'ok', 'debug': {'breakpoints': sorted(self.breakpoints)}}
        if op == 'detach':
            if self.attach_calls > 0:
                self.attach_calls -= 1
            return {'status': 'ok', 'debug': {'breakpoints': sorted(self.breakpoints)}}
        if op == 'bp':
            action = (payload.get('action') or 'list').lower()
            if action in {'', 'list'}:
                return {'status': 'ok', 'debug': {'breakpoints': sorted(self.breakpoints)}}
            if action == 'add':
                addr_raw = payload.get('addr')
                addr_int = int(addr_raw, 0) if isinstance(addr_raw, str) else int(addr_raw)
                self.breakpoints.add(addr_int & 0xFFFF)
                return {'status': 'ok', 'debug': {'breakpoints': sorted(self.breakpoints)}}
            if action == 'remove':
                addr_raw = payload.get('addr')
                addr_int = int(addr_raw, 0) if isinstance(addr_raw, str) else int(addr_raw)
                self.breakpoints.discard(addr_int & 0xFFFF)
                return {'status': 'ok', 'debug': {'breakpoints': sorted(self.breakpoints)}}
            return {'status': 'error', 'error': 'unknown_action'}
        raise AssertionError(f'unhandled dbg op {op!r}')

    def ps(self) -> dict:
        state = "paused" if self.paused else "running"
        return {"tasks": [{"pid": 1, "state": state}], "current_pid": 1}

    def info(self, pid: int | None = None) -> dict:
        state = "paused" if self.paused else "running"
        return {"tasks": {"tasks": [{"pid": 1, "state": state}], "current_pid": 1}}

    def read_regs(self, pid: int | None = None) -> dict:
        return {"pc": self.pc}

    def pause(self, pid: int | None = None) -> None:
        self.paused = True

    def resume(self, pid: int | None = None) -> None:
        self.paused = False

    def step(self, steps: int, pid: int | None = None) -> dict:
        self.step_calls += 1
        self.paused = False
        self.pc = (self.pc + self.step_delta) & 0xFFFF
        return {"executed": 1 if steps is not None else 0, "running": True, "current_pid": pid, "paused": False}


def make_debug_state() -> tuple[ExecutiveState, DebugVM]:
    vm = DebugVM()
    state = ExecutiveState(vm)
    state.tasks[1] = {'pid': 1}
    return state, vm


def test_breakpoint_add_list_clear():
    state, vm = make_debug_state()
    info = state.breakpoint_add(1, 0x200)
    assert info['breakpoints'] == [0x200]
    assert vm.breakpoints == {0x200}
    info = state.breakpoint_list(1)
    assert info['breakpoints'] == [0x200]
    info = state.breakpoint_clear(1, 0x200)
    assert info['breakpoints'] == []
    assert vm.breakpoints == set()


def test_breakpoint_clear_all():
    state, vm = make_debug_state()
    state.breakpoint_add(1, 0x10)
    state.breakpoint_add(1, 0x20)
    info = state.breakpoint_clear_all(1)
    assert info['breakpoints'] == []
    assert vm.breakpoints == set()


def test_load_symbols_for_pid(tmp_path):
    state, vm = make_debug_state()
    program_path = tmp_path / "app.hxe"
    program_path.write_bytes(b"")
    sym_path = tmp_path / "app.sym"
    sym_data = {
        "version": 1,
        "symbols": [
            {"name": "main", "address": 0x100, "size": 12, "type": "function", "file": "main.c", "line": 10},
            {"name": "helper", "address": 0x120, "size": 8, "type": "function"},
        ],
        "lines": [
            {"address": 0x100, "file": "main.c", "line": 10},
            {"address": 0x104, "file": "main.c", "line": 11},
        ],
    }
    sym_path.write_text(json.dumps(sym_data), encoding='utf-8')
    state.tasks[1]['program'] = str(program_path)
    result = state.load_symbols_for_pid(1, program=str(program_path), override=str(sym_path))
    assert result['loaded'] is True
    info = state.symbol_info(1)
    assert info['loaded'] is True
    assert info['count'] == 2
    entry = state.symbol_lookup_name(1, 'main')
    assert entry and entry['address'] == 0x100
    lookup = state.symbol_lookup_addr(1, 0x102)
    assert lookup and lookup['name'] == 'main' and lookup['offset'] == 0x2
    line = state.symbol_lookup_line(1, 0x103)
    assert line and line['line'] == 10


def test_step_hits_breakpoint_pre_phase():
    state, vm = make_debug_state()
    vm.pc = 0x200
    state.breakpoint_add(1, 0x200)
    result = state.step(steps=1, pid=1)
    assert vm.step_calls == 0
    assert vm.paused is True
    assert result['paused'] is True
    assert result['running'] is False
    assert result['executed'] == 0
    events = result.get('events', [])
    assert events and events[0]['type'] == 'debug_break'
    assert events[0]['data'].get('phase') == 'pre'
    assert events[0]['data'].get('reason') == 'breakpoint'


def test_step_hits_breakpoint_post_phase():
    state, vm = make_debug_state()
    state.breakpoint_add(1, 0x200)
    vm.pc = 0x1F0
    vm.step_delta = 0x10
    result = state.step(steps=1, pid=1)
    assert vm.step_calls == 1
    assert vm.paused is True
    events = result.get('events', [])
    assert any(evt['data'].get('phase') == 'post' for evt in events)
    assert result['paused'] is True
    assert result['running'] is False

