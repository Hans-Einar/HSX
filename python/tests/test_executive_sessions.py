import json
import time
from pathlib import Path
from typing import Dict, List, Optional

import pytest

from python.execd import ExecutiveState, SessionError
from python import trace_format
from python.valcmd import float_to_f16
from python import hsx_value_constants as val_const
from python import hsx_command_constants as cmd_const


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

    def val_stats(self):
        return getattr(self, "_val_stats", {"values": {}, "strings": {}})

    def cmd_stats(self):
        return getattr(self, "_cmd_stats", {"commands": {}, "strings": {}})


def make_state():
    return ExecutiveState(DummyVM(), step_batch=1)


class TaskStateVM:
    def __init__(self) -> None:
        self.alive = True
        self.state = "running"
        self.sleep_pending = False
        self.exit_status: Optional[int] = None
        self.paused = False
        self.pc = 0
        self.fp = 0
        self.sp = 0x2000

    def attach(self) -> dict:
        return {}

    def detach(self) -> dict:
        return {}

    def info(self, pid: Optional[int] = None) -> dict:
        if not self.alive:
            return {"tasks": {"tasks": [], "current_pid": None}}
        task = {
            "pid": 1,
            "state": self.state,
            "stack_base": 0,
            "stack_limit": 0,
            "sleep_pending": self.sleep_pending,
        }
        if self.exit_status is not None:
            task["exit_status"] = self.exit_status
        return {"tasks": {"tasks": [task], "current_pid": 1}}

    def ps(self) -> dict:
        if not self.alive:
            return {"tasks": {"tasks": [], "current_pid": None}}
        task = {
            "pid": 1,
            "state": self.state,
            "program": "app.hxe",
            "sleep_pending": self.sleep_pending,
        }
        if self.exit_status is not None:
            task["exit_status"] = self.exit_status
        return {"tasks": {"tasks": [task], "current_pid": 1}}

    def restart(self, targets):
        return {}

    def pause(self, pid: Optional[int] = None) -> None:
        self.paused = True
        self.state = "paused"

    def resume(self, pid: Optional[int] = None) -> None:
        self.paused = False
        self.state = "running"
        self.exit_status = None

    def kill(self, pid: int) -> dict:
        self.paused = False
        self.state = "terminated"
        self.alive = False
        self.exit_status = None
        return {"status": "ok"}

    def read_regs(self, pid: Optional[int] = None) -> dict:
        regs = [0] * 16
        regs[7] = self.fp & 0xFFFFFFFF
        return {
            "pc": self.pc,
            "regs": regs,
            "sp": self.sp,
            "fp": self.fp,
            "stack_base": 0,
            "stack_size": 0,
            "stack_limit": 0,
            "context": {"state": self.state},
        }


def make_task_state_env() -> tuple[ExecutiveState, TaskStateVM]:
    vm = TaskStateVM()
    state = ExecutiveState(vm, step_batch=1)
    state.enforce_context_isolation = False
    return state, vm


def test_value_events_update_registry():
    state = make_state()
    state.value_registry.clear()

    register_event = {
        "type": "value_registered",
        "pid": 10,
        "oid": 0x0102,
        "group_id": 1,
        "value_id": 2,
        "flags": 0x05,
        "auth_level": 2,
        "caller_pid": 10,
        "owner_pid": 10,
    }
    state._process_vm_events([register_event])
    entry = state.value_registry[10][(1, 2)]
    assert entry["oid"] == 0x0102
    assert entry["flags"] == 0x05
    assert entry["auth_level"] == 2
    assert entry["registered_ts"] <= time.time()

    change_event = {
        "type": "value_changed",
        "pid": 10,
        "oid": 0x0102,
        "group_id": 1,
        "value_id": 2,
        "old_f16": float_to_f16(1.0),
        "new_f16": float_to_f16(2.5),
    }
    state._process_vm_events([change_event])
    entry = state.value_registry[10][(1, 2)]
    assert entry["last_f16"] == float_to_f16(2.5)
    assert entry["last_value"] == pytest.approx(2.5)
    assert entry["prev_value"] == pytest.approx(1.0)
    assert entry["change_count"] == 1


def test_command_events_update_registry():
    state = make_state()
    state.command_registry.clear()

    invoked_event = {
        "type": "cmd_invoked",
        "pid": 20,
        "oid": 0x0203,
        "group_id": 2,
        "cmd_id": 3,
        "flags": 0x01,
        "auth_level": 1,
        "caller_pid": 20,
        "owner_pid": 21,
    }
    state._process_vm_events([invoked_event])
    entry = state.command_registry[20][(2, 3)]
    assert entry["oid"] == 0x0203
    assert entry["flags"] == 0x01
    assert entry["owner_pid"] == 21
    assert entry["last_invoked_ts"] <= time.time()

    completed_event = {
        "type": "cmd_completed",
        "pid": 20,
        "oid": 0x0203,
        "group_id": 2,
        "cmd_id": 3,
        "status": 0,
        "result": "ok",
    }
    state._process_vm_events([completed_event])
    entry = state.command_registry[20][(2, 3)]
    assert entry["last_status"] == 0
    assert entry["last_result"] == "ok"
    assert entry["last_completed_ts"] <= time.time()


def test_val_stats_passthrough():
    state = make_state()
    state.vm._val_stats = {
        "values": {"count": 2, "capacity": 8, "usage_pct": 25.0},
        "strings": {"used_bytes": 32, "total_bytes": 256, "usage_pct": 12.5},
    }
    stats = state.val_stats()
    assert stats["values"]["count"] == 2
    assert stats["strings"]["used_bytes"] == 32


def test_cmd_stats_passthrough():
    state = make_state()
    state.vm._cmd_stats = {
        "commands": {"count": 1, "capacity": 4, "usage_pct": 25.0},
        "strings": {"used_bytes": 40, "total_bytes": 256, "usage_pct": 15.6},
    }
    stats = state.cmd_stats()
    assert stats["commands"]["count"] == 1
    assert stats["strings"]["usage_pct"] == pytest.approx(15.6)


class ValCmdClient:
    def __init__(self) -> None:
        self.list_calls: list[dict] = []

    def val_list(self, *, pid=None, group=None, oid=None, name=None):
        self.list_calls.append({"pid": pid, "group": group, "oid": oid, "name": name})
        return [
            {
                "oid": 0x0101,
                "group_id": 1,
                "value_id": 1,
                "owner_pid": pid or 1,
                "name": "rpm",
                "group_name": "telemetry",
                "last_value": 12.5,
                "last_f16": float_to_f16(12.5),
            }
        ]

    def val_get(self, oid, *, pid=None):
        return {
            "status": val_const.HSX_VAL_STATUS_OK,
            "value": 7.5,
            "f16": float_to_f16(7.5),
            "pid": pid or 1,
        }

    def val_set(self, oid, value, *, pid=None):
        return {
            "status": val_const.HSX_VAL_STATUS_OK,
            "value": float(value),
            "f16": float_to_f16(float(value)),
            "pid": pid or 1,
        }

    def cmd_list(self, *, pid=None, group=None, oid=None, name=None):
        return [
            {
                "oid": 0x0202,
                "group_id": 2,
                "cmd_id": 2,
                "owner_pid": pid or 1,
                "name": "reset",
                "help": "reset board",
            }
        ]

    def cmd_call(self, oid, *, pid=None, async_call=False):
        return {
            "status": cmd_const.HSX_CMD_STATUS_OK,
            "result": "ok",
            "pid": pid or 1,
        }


def test_executive_state_val_api_merges_cache():
    client = ValCmdClient()
    state = ExecutiveState(client, step_batch=1)
    values = state.val_list(pid=1)
    assert values[0]["name"] == "rpm"
    result = state.val_get(0x0101, pid=1)
    assert result["status"] == val_const.HSX_VAL_STATUS_OK
    set_result = state.val_set(0x0101, 3.14, pid=1)
    assert set_result["status"] == val_const.HSX_VAL_STATUS_OK
    registry_entry = state.value_registry[1][(1, 1)]
    assert registry_entry["last_value"] == pytest.approx(3.14)


def test_executive_state_cmd_api_merges_cache():
    client = ValCmdClient()
    state = ExecutiveState(client, step_batch=1)
    commands = state.cmd_list(pid=1)
    assert commands[0]["name"] == "reset"
    result = state.cmd_call(0x0202, pid=1)
    assert result["status"] == cmd_const.HSX_CMD_STATUS_OK
    entry = state.command_registry[1][(2, 2)]
    assert entry["last_result"] == "ok"


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
    # requested feature should be negotiated when supported
    assert "watch" in session.get("features", [])
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


def test_events_backpressure_warns_and_drops_slow_clients():
    state = make_state()
    state.event_ack_warn_floor = 3
    state.event_ack_drop_floor = 6
    state.event_ack_warn_factor = 1
    state.event_ack_drop_factor = 3
    state.event_backpressure_grace = 0.0
    state.event_slow_warning_interval = 0.0
    session_id = state.session_open(capabilities={"features": ["events"], "max_events": 2})["id"]
    subscription = state.events_subscribe(session_id)
    warnings: list[str] = []
    drop_seen = False
    for i in range(12):
        state.emit_event("trace_step", pid=1, data={"pc": i})
        while True:
            evt = state.events_next(subscription, timeout=0.01)
            if evt is None:
                break
            if evt["type"] == "warning":
                reason = evt["data"].get("reason")
                if reason:
                    warnings.append(reason)
                    if reason == "slow_consumer_drop":
                        drop_seen = True
                        break
        if drop_seen or not subscription.active:
            break
    assert "slow_consumer" in warnings
    assert "slow_consumer_drop" in warnings
    assert drop_seen
    assert not subscription.active


def test_events_metrics_track_pending_and_reset_after_ack():
    state = make_state()
    session_id = state.session_open(capabilities={"features": ["events"], "max_events": 4})["id"]
    subscription = state.events_subscribe(session_id)
    emitted = state.emit_event("debug_break", pid=7, data={"pc": 0x200})
    # drain event but do not ack yet
    assert state.events_next(subscription, timeout=0.05) is not None
    metrics = state.events_metrics(session_id)
    assert metrics["pending"] >= 1
    assert metrics["delivered_seq"] >= emitted["seq"]
    state.events_ack(session_id, metrics["delivered_seq"])
    metrics_after = state.events_metrics(session_id)
    assert metrics_after["pending"] == 0


def test_trace_step_changed_regs_tracks_diffs():
    state = make_state()
    state.event_history.clear()
    state.trace_last_regs.clear()
    state._process_vm_events(
        [
            {
                "type": "trace_step",
                "pid": 1,
                "pc": 0x100,
                "regs": [0] * 16,
                "flags": 0,
                "opcode": 0,
            }
        ]
    )
    trace_events = [evt for evt in state.event_history if evt.get("type") == "trace_step"]
    assert trace_events, "expected trace_step event"
    first_changed = set(trace_events[-1]["data"].get("changed_regs", []))
    assert "R0" in first_changed
    assert "PC" not in first_changed

    state.event_history.clear()
    state._process_vm_events(
        [
            {
                "type": "trace_step",
                "pid": 1,
                "pc": 0x104,
                "regs": [0] * 16,
                "flags": 0,
                "opcode": 0,
            }
        ]
    )
    followup = [evt for evt in state.event_history if evt.get("type") == "trace_step"]
    assert followup[-1]["data"].get("changed_regs") is None


def test_trace_step_changed_regs_toggle_respected():
    state = make_state()
    state.set_trace_changed_regs(False)
    state.event_history.clear()
    state._process_vm_events(
        [
            {
                "type": "trace_step",
                "pid": 1,
                "pc": 0x200,
                "regs": [0] * 16,
                "flags": 0,
                "opcode": 0,
            }
        ]
    )
    trace_events = [evt for evt in state.event_history if evt.get("type") == "trace_step"]
    assert trace_events and "changed_regs" not in trace_events[-1]["data"]

    state.set_trace_changed_regs(True)
    state.event_history.clear()
    regs = [0] * 16
    regs[3] = 0x1234
    state._process_vm_events(
        [
            {
                "type": "trace_step",
                "pid": 1,
                "pc": 0x204,
                "regs": regs,
                "flags": 0,
                "opcode": 0,
            }
        ]
    )
    changed = [evt for evt in state.event_history if evt.get("type") == "trace_step"][-1]["data"].get("changed_regs", [])
    assert "R3" in changed
    assert "PC" not in changed


def test_trace_buffer_captures_records():
    state = make_state()
    state.set_trace_buffer_size(4)
    state._process_vm_events(
        [
            {
                "type": "trace_step",
                "pid": 1,
                "pc": 0x140,
                "regs": list(range(16)),
                "flags": 0x5,
                "mem_access": {"op": "read", "address": 0x1234, "width": 4, "value": 0xDEADBEEF},
                "opcode": 0xDEADBEEF,
            }
        ]
    )
    info = state.trace_records(1)
    assert info["count"] == 1
    record = info["records"][0]
    assert record["pc"] == 0x140
    assert record["opcode"] == 0xDEADBEEF
    assert "changed_regs" in record


def test_trace_buffer_capacity_trim():
    state = make_state()
    state.set_trace_buffer_size(2)
    for offset in range(3):
        pc = 0x100 + offset * 2
        state._process_vm_events(
            [
                {
                    "type": "trace_step",
                    "pid": 1,
                    "pc": pc,
                    "regs": [pc] * 16,
                    "flags": 0,
                    "opcode": pc,
                }
            ]
        )
    info = state.trace_records(1)
    assert info["count"] == 2
    pcs = [rec["pc"] for rec in info["records"]]
    assert pcs == [0x102, 0x104]


def test_trace_buffer_disable_clears_records():
    state = make_state()
    state._process_vm_events(
        [
            {
                "type": "trace_step",
                "pid": 1,
                "pc": 0x200,
                "regs": [0] * 16,
                "flags": 0,
                "opcode": 0x1,
            }
        ]
    )
    assert state.trace_records(1)["count"] == 1
    state.set_trace_buffer_size(0)
    info = state.trace_records(1)
    assert info["capacity"] == 0
    assert info["count"] == 0


def test_trace_polling_uses_trace_last_when_no_events():
    state, vm = make_debug_state()
    vm.step_delta = 4
    before = state.trace_records(1)
    assert before["count"] == 0
    result = state.step(steps=1, pid=1)
    assert "trace_last" not in result
    after = state.trace_records(1)
    assert after["count"] >= 1


def test_trace_export_returns_format():
    state = make_state()
    state.set_trace_buffer_size(4)
    state._process_vm_events(
        [
            {
                "type": "trace_step",
                "pid": 1,
                "pc": 0x310,
                "regs": [0] * 16,
                "flags": 0,
                "opcode": 0xAAA,
            }
        ]
    )
    export = state.trace_export(1)
    assert export["format"] == trace_format.TRACE_FORMAT_VERSION
    assert export["records"]


def test_trace_import_replace_overwrites_buffer():
    state = make_state()
    state.set_trace_buffer_size(4)
    imported = state.trace_import(
        1,
        [
            {"seq": 10, "pid": 1, "pc": 0x400, "opcode": 0xAAA},
            {"seq": 11, "pid": 1, "pc": 0x404, "opcode": 0xAAB},
        ],
        replace=True,
    )
    assert imported["count"] == 2
    assert imported["records"][0]["seq"] == 10
    assert state.trace_records(1)["count"] == 2


def test_trace_import_append_extends_buffer():
    state = make_state()
    state.set_trace_buffer_size(4)
    state.trace_import(1, [{"seq": 20, "pid": 1, "pc": 0x500, "opcode": 0xABC}], replace=True)
    appended = state.trace_import(
        1,
        [{"seq": 21, "pid": 1, "pc": 0x504, "opcode": 0xABD}],
        replace=False,
    )
    assert appended["count"] == 2
    assert appended["records"][-1]["seq"] == 21


def _task_state_events(state: ExecutiveState) -> List[dict]:
    return [evt for evt in state.event_history if evt.get("type") == "task_state"]


def test_task_state_loaded_event():
    state, vm = make_task_state_env()
    state.event_history.clear()
    state._refresh_tasks()
    events = _task_state_events(state)
    assert events, "expected initial task_state event"
    data = events[-1]["data"]
    assert data["reason"] == "loaded"
    assert data["new_state"] == "running"


def test_task_state_mailbox_wait_and_wake_events():
    state, vm = make_task_state_env()
    state._refresh_tasks()
    state.event_history.clear()

    wait_event = {"descriptor": 7, "handle": 2, "timeout": 50, "deadline": 123.456}
    state._mark_task_wait_mailbox(1, wait_event)
    task_before = state.tasks[1]
    assert task_before["wait_mailbox"] == 7
    assert task_before["wait_handle"] == 2
    assert task_before["wait_timeout"] == 50
    assert task_before["wait_deadline"] == pytest.approx(123.456)
    vm.state = "waiting_mbx"
    state._refresh_tasks()
    task_after = state.tasks[1]
    assert task_after["state"] == "waiting_mbx"
    assert task_after["wait_mailbox"] == 7
    assert task_after["wait_handle"] == 2
    assert task_after["wait_timeout"] == 50
    assert task_after["wait_deadline"] == pytest.approx(123.456)
    events = _task_state_events(state)
    assert events, "expected mailbox wait event"
    data = events[-1]["data"]
    assert data["reason"] == "mailbox_wait"
    assert data["new_state"] == "waiting_mbx"
    assert data.get("details", {}).get("descriptor") == 7

    state.event_history.clear()
    vm.state = "ready"
    state._mark_task_ready(1, {"descriptor": 7}, reason="mailbox_wake")
    state._refresh_tasks()
    task_ready = state.tasks[1]
    assert "wait_mailbox" not in task_ready
    assert "wait_handle" not in task_ready
    assert "wait_timeout" not in task_ready
    wake_events = _task_state_events(state)
    assert wake_events, "expected mailbox wake event"
    wake_data = wake_events[-1]["data"]
    assert wake_data["reason"] == "mailbox_wake"
    assert wake_data["new_state"] == "ready"


def test_wait_mailbox_deadline_tracking():
    state, vm = make_task_state_env()
    state.wait_mbx_deadlines.clear()
    state.wait_mbx_heap.clear()
    state.auto_event.clear()

    deadline = time.monotonic() + 1.0
    wait_event = {"descriptor": 9, "handle": 1, "timeout": 100, "deadline": deadline}
    state._mark_task_wait_mailbox(1, wait_event)

    assert 1 in state.wait_mbx_deadlines
    assert state.wait_mbx_deadlines[1] == pytest.approx(deadline)
    next_deadline = state._next_wait_mailbox_deadline()
    assert next_deadline == pytest.approx(deadline)
    assert state.auto_event.is_set()

    state.auto_event.clear()
    state._mark_task_ready(1, {"descriptor": 9}, reason="mailbox_wake")
    assert 1 not in state.wait_mbx_deadlines
    assert state._next_wait_mailbox_deadline() is None


def test_wait_mailbox_poll_not_tracked():
    state, vm = make_task_state_env()
    state.wait_mbx_deadlines.clear()
    state.wait_mbx_heap.clear()

    wait_event = {"descriptor": 3, "handle": 1, "timeout": 0, "deadline": None}
    state._mark_task_wait_mailbox(1, wait_event)

    assert 1 not in state.wait_mbx_deadlines
    assert state._next_wait_mailbox_deadline() is None


def test_task_state_mailbox_timeout_reason():
    state, vm = make_task_state_env()
    state._refresh_tasks()
    state.event_history.clear()
    vm.state = "ready"
    timeout_event = {"descriptor": 3, "status": 0xFFFF}
    state._mark_task_ready(1, timeout_event, reason="timeout")
    state._refresh_tasks()
    events = _task_state_events(state)
    assert events, "expected timeout event"
    data = events[-1]["data"]
    assert data["reason"] == "timeout"
    assert data["new_state"] == "ready"
    assert data.get("details", {}).get("descriptor") == 3


def test_task_state_debug_break_reason():
    state, vm = make_task_state_env()
    state._refresh_tasks()
    state.event_history.clear()
    event = state._handle_breakpoint_hit(1, 0x200, phase="pre")
    assert event["type"] == "debug_break"
    debug_events = _task_state_events(state)
    assert debug_events, "expected task_state event after debug break"
    data = debug_events[-1]["data"]
    assert data["reason"] == "debug_break"
    assert data["new_state"] == "paused"


def test_task_state_sleep_reason():
    state, vm = make_task_state_env()
    state._refresh_tasks()
    state.event_history.clear()
    vm.sleep_pending = True
    state._refresh_tasks()
    events = _task_state_events(state)
    assert events, "expected sleep task_state event"
    data = events[-1]["data"]
    assert data["reason"] == "sleep"
    assert data["new_state"] == "running"
    assert data.get("details", {}).get("sleep_pending") is True


def test_task_state_returned_reason():
    state, vm = make_task_state_env()
    state._refresh_tasks()
    state.event_history.clear()
    vm.state = "returned"
    vm.exit_status = 0
    state._refresh_tasks()
    events = _task_state_events(state)
    assert events, "expected returned event"
    data = events[-1]["data"]
    assert data["reason"] == "returned"
    assert data["new_state"] == "returned"
    assert data.get("details", {}).get("exit_status") == 0


def test_task_state_killed_reason():
    state, vm = make_task_state_env()
    state._refresh_tasks()
    state.event_history.clear()
    state.kill_task(1)
    events = _task_state_events(state)
    assert events, "expected kill event"
    data = events[-1]["data"]
    assert data["reason"] == "killed"
    assert data["new_state"] == "terminated"

class DebugVM:
    def __init__(self) -> None:
        self.breakpoints: set[int] = set()
        self.requests: list[dict] = []
        self.attach_calls = 0
        self.pc = 0
        self.sp = 0x2000
        self.fp = 0
        self.step_delta = 0x10
        self.step_calls = 0
        self.paused = False
        self.regs_list: List[int] = [0] * 16
        self.regs_list[7] = self.fp
        self.memory: Dict[int, int] = {}

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
        return {"tasks": {"tasks": [{"pid": 1, "state": state, "program": ""}], "current_pid": 1}}

    def info(self, pid: int | None = None) -> dict:
        state = "paused" if self.paused else "running"
        return {"tasks": {"tasks": [{"pid": 1, "state": state, "stack_base": 0, "stack_limit": 0}], "current_pid": 1}}

    def read_regs(self, pid: int | None = None) -> dict:
        return {
            "pc": self.pc,
            "regs": list(self.regs_list),
            "sp": self.sp,
            "fp": self.fp,
            "stack_base": 0x8000,
            "stack_size": 0x1000,
            "stack_limit": 0x8000,
            "sp_effective": self.sp,
            "context": {"state": "paused" if self.paused else "running"},
        }

    def pause(self, pid: int | None = None) -> None:
        self.paused = True

    def resume(self, pid: int | None = None) -> None:
        self.paused = False

    def step(self, steps: int, pid: int | None = None) -> dict:
        self.step_calls += 1
        self.paused = False
        prev_pc = self.pc
        self.pc = (self.pc + self.step_delta) & 0xFFFF
        self.regs_list[7] = self.fp & 0xFFFFFFFF
        trace_last = {
            "pid": pid if pid is not None else 1,
            "pc": prev_pc & 0xFFFF,
            "next_pc": self.pc & 0xFFFF,
            "opcode": 0,
            "flags": 0,
            "regs": list(self.regs_list),
        }
        return {
            "executed": 1 if steps is not None else 0,
            "running": True,
            "current_pid": pid,
            "paused": False,
            "events": [],
            "trace_last": trace_last,
        }

    def read_mem(self, addr: int, length: int, pid: int | None = None) -> bytes:
        return bytes(self.memory.get((addr + i) & 0xFFFFFFFF, 0) for i in range(length))
    def kill(self, pid: int) -> dict:
        self.paused = False
        return {"status": "ok"}


def make_debug_state() -> tuple[ExecutiveState, DebugVM]:
    vm = DebugVM()
    state = ExecutiveState(vm)
    state.enforce_context_isolation = False
    state.tasks[1] = {
        'pid': 1,
        'state': 'running',
        'stack_base': 0x8000,
        'stack_size': 0x1000,
        'stack_limit': 0x8000,
    }
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


def _write_word(vm: DebugVM, addr: int, value: int) -> None:
    for i in range(4):
        vm.memory[(addr + i) & 0xFFFFFFFF] = (value >> (8 * i)) & 0xFF


def _write_bytes(vm: DebugVM, addr: int, data: bytes) -> None:
    for i, byte in enumerate(data):
        vm.memory[(addr + i) & 0xFFFFFFFF] = byte


def _seed_symbol_table(state: ExecutiveState, pid: int, entries: list[tuple[str, int, int] | dict]) -> None:
    symbols: list[dict] = []
    for entry in entries:
        if isinstance(entry, dict):
            symbol = dict(entry)
        else:
            name, addr, size = entry
            symbol = {"name": name, "address": addr, "size": size, "type": "function"}
        symbol.setdefault("size", 0)
        symbol.setdefault("type", "function")
        symbols.append(symbol)
    addresses = [
        {
            "name": item["name"],
            "address": item["address"],
            "size": item["size"],
            "type": item.get("type", "function"),
        }
        for item in symbols
    ]
    lines = [
        {"address": item["address"], "file": "prog.c", "line": 10 + idx * 5}
        for idx, item in enumerate(symbols)
    ]
    table = {
        "path": "test.sym",
        "symbols": symbols,
        "addresses": addresses,
        "by_name": {item["name"]: item for item in symbols},
        "lines": lines,
    }
    with state.symbol_cache_lock:
        state.symbol_tables[pid] = table


def _inject_locals(state: ExecutiveState, pid: int, locals_entries: list[dict]) -> None:
    with state.symbol_cache_lock:
        table = state.symbol_tables.get(pid)
        if not table:
            table = {
                "path": "test.sym",
                "symbols": [],
                "addresses": [],
                "by_name": {},
                "lines": [],
            }
        table["locals"] = list(locals_entries)
        mapping: Dict[str, List[dict]] = {}
        for entry in locals_entries:
            fn = entry.get("function")
            if not fn:
                continue
            mapping.setdefault(fn, []).append(entry)
        table["locals_by_function"] = mapping
        state.symbol_tables[pid] = table


def test_symbols_list_filters_and_paginate():
    state, _ = make_debug_state()
    _seed_symbol_table(
        state,
        1,
        [
            {"name": "alpha", "address": 0x100, "size": 12, "type": "function"},
            {"name": "beta", "address": 0x120, "size": 8, "type": "function"},
            {"name": "buffer", "address": 0x200, "size": 16, "type": "object"},
            {"name": "flag", "address": 0x210, "size": 2, "type": "variable"},
        ],
    )
    all_symbols = state.symbols_list(1)
    assert all_symbols["count"] == 4
    assert [entry["name"] for entry in all_symbols["symbols"]] == ["alpha", "beta", "buffer", "flag"]

    funcs = state.symbols_list(1, kind="functions")
    assert funcs["count"] == 2
    assert [entry["name"] for entry in funcs["symbols"]] == ["alpha", "beta"]

    vars_only = state.symbols_list(1, kind="variables")
    assert vars_only["count"] == 2
    assert [entry["name"] for entry in vars_only["symbols"]] == ["buffer", "flag"]

    paged = state.symbols_list(1, offset=1, limit=2)
    assert paged["offset"] == 1
    assert paged["limit"] == 2
    assert [entry["name"] for entry in paged["symbols"]] == ["beta", "buffer"]


def test_symbols_list_missing_table_returns_empty():
    state, _ = make_debug_state()
    result = state.symbols_list(1, offset=0, limit=5)
    assert result["count"] == 0
    assert result["offset"] == 0
    assert result["symbols"] == []


def test_symbols_list_invalid_kind_raises():
    state, _ = make_debug_state()
    with pytest.raises(ValueError):
        state.symbols_list(1, kind="registers")


def test_memory_regions_reports_layout_and_stack():
    state, _ = make_debug_state()
    state.tasks[1]["program"] = "app.hxe"
    state.memory_layouts[1] = {
        "entry": 0x10,
        "code_len": 0x80,
        "ro_len": 0x20,
        "bss": 0x10,
    }
    state.task_states[1] = {
        "context": {
            "reg_base": 0x1200,
            "stack_base": 0xF000,
            "stack_size": 0x200,
            "stack_limit": 0xF000,
            "sp": 0xF1F0,
        }
    }
    info = state.memory_regions(1)
    assert info["pid"] == 1
    assert info["program"] == "app.hxe"
    regions = {region["name"]: region for region in info["regions"]}
    assert regions["code"]["start"] == 0x0000 and regions["code"]["length"] == 0x80
    assert regions["code"]["permissions"] == "rx"
    assert regions["rodata"]["start"] == 0x4000 and regions["rodata"]["length"] == 0x20
    assert regions["bss"]["start"] == 0x4020 and regions["bss"]["length"] == 0x10
    assert regions["registers"]["start"] == 0x1200 and regions["registers"]["length"] == 64
    assert regions["stack"]["start"] == 0xF000 and regions["stack"]["length"] == 0x200
    assert regions["stack"]["details"]["sp"] == 0xF1F0


def test_memory_regions_handles_missing_context():
    state, _ = make_debug_state()
    state.memory_layouts[1] = {"code_len": 0x40}
    info = state.memory_regions(1)
    names = [region["name"] for region in info["regions"]]
    assert "code" in names
    assert "stack" not in names
    assert "registers" not in names


def test_watch_add_emits_event_on_change():
    state, vm = make_debug_state()
    addr = 0x0200
    vm.memory[addr] = 0x10
    vm.memory[addr + 1] = 0x20
    watch = state.watch_add(1, f"0x{addr:X}", watch_type="address", length=2)
    assert watch["address"] == addr
    assert watch["value"] == "1020"

    vm.memory[addr] = 0x11
    vm.memory[addr + 1] = 0x22
    result = state.step(steps=1, pid=1)
    events = result.get("events", [])
    updates = [evt for evt in events if evt.get("type") == "watch_update"]
    assert updates, "expected watch update event"
    data = updates[0]["data"]
    assert data["watch_id"] == watch["id"]
    assert data["old"] == "1020"
    assert data["new"] == "1122"


def test_watch_add_local_stack_tracks_frame_pointer():
    state, vm = make_debug_state()
    _seed_symbol_table(state, 1, [("main", 0x100, 32)])
    local_entry = {
        "name": "tmp",
        "function": "main",
        "locations": [
            {"start": 0x100, "end": 0x200, "location": {"kind": "stack", "offset": -4}},
        ],
    }
    _inject_locals(state, 1, [local_entry])
    vm.pc = 0x120
    vm.fp = 0x9000
    vm.regs_list[7] = vm.fp
    vm.memory[vm.fp - 4] = 0xAA
    vm.memory[vm.fp - 3] = 0xBB
    vm.memory[vm.fp - 2] = 0xCC
    vm.memory[vm.fp - 1] = 0xDD
    watch = state.watch_add(1, "local:tmp", watch_type="local")
    assert watch["type"] == "local"
    assert watch.get("mode") == "local"
    assert watch.get("location") == "fp-0x4"
    assert watch["value"] == "aabbccdd"


def test_watch_local_register_emits_updates():
    state, vm = make_debug_state()
    _seed_symbol_table(state, 1, [("main", 0x100, 64)])
    local_entry = {
        "name": "acc",
        "function": "main",
        "locations": [
            {"start": 0x100, "end": 0x200, "location": {"kind": "register", "name": "R5", "index": 5}},
        ],
    }
    _inject_locals(state, 1, [local_entry])
    vm.pc = 0x110
    vm.regs_list[5] = 0x11223344
    watch = state.watch_add(1, "local:acc", watch_type="local")
    assert watch["type"] == "local"
    assert watch.get("location") == "R5"
    vm.regs_list[5] = 0x55667788
    result = state.step(steps=1, pid=1)
    updates = [evt for evt in result.get("events", []) if evt.get("type") == "watch_update"]
    assert updates, "expected local watch update"
    data = updates[0]["data"]
    assert data["type"] == "local"
    assert data.get("location") == "R5"
    assert data["new"] == "88776655"


def test_watch_add_symbol_resolves_address():
    state, vm = make_debug_state()
    _seed_symbol_table(state, 1, [("main", 0x1000, 16)])
    vm.memory[0x1000] = 0xAA
    watch = state.watch_add(1, "main", watch_type="symbol", length=1)
    assert watch["symbol"] == "main"
    assert watch["address"] == 0x1000
    listing = state.watch_list(1)
    assert listing["count"] == 1
    assert listing["watches"][0]["symbol"] == "main"


def test_watch_remove_and_cleanup():
    state, _ = make_debug_state()
    watch = state.watch_add(1, "0x300", watch_type="address", length=1)
    removed = state.watch_remove(1, watch["id"])
    assert removed["id"] == watch["id"]
    listing = state.watch_list(1)
    assert listing["count"] == 0
    with pytest.raises(ValueError):
        state.watch_remove(1, watch["id"])


def test_watch_cleared_on_task_kill():
    state, _ = make_debug_state()
    watch = state.watch_add(1, "0x350", watch_type="address", length=1)
    state.kill_task(1)
    assert state.watchers.get(1) is None
    with pytest.raises(ValueError):
        state.watch_remove(1, watch["id"])


def test_stack_info_two_frames_with_symbols():
    state, vm = make_debug_state()
    vm.pc = 0x1000
    vm.sp = 0x8FE8
    vm.fp = 0x8FF0
    vm.regs_list[7] = vm.fp
    _write_word(vm, 0x8FF0, 0x8FE0)
    _write_word(vm, 0x8FF4, 0x1100)
    _write_word(vm, 0x8FE0, 0x0000)
    _write_word(vm, 0x8FE4, 0x0000)
    _seed_symbol_table(state, 1, [("func_main", 0x1000, 16), ("func_caller", 0x1100, 32)])

    stack = state.stack_info(1, max_frames=4)
    frames = stack["frames"]
    assert stack["truncated"] is False
    assert stack["errors"] == []
    assert stack["initial_sp"] == 0x8FE8
    assert stack["initial_fp"] == 0x8FF0
    assert len(frames) == 2

    frame0 = frames[0]
    assert frame0["pc"] == 0x1000
    assert frame0["sp"] == 0x8FE8
    assert frame0["fp"] == 0x8FF0
    assert frame0["return_pc"] == 0x1100
    assert frame0.get("func_name") == "func_main"
    assert frame0.get("func_addr") == 0x1000
    assert frame0.get("func_offset") == 0
    assert frame0.get("line_num") == 10

    frame1 = frames[1]
    assert frame1["pc"] == 0x1100
    assert frame1["fp"] == 0x8FE0
    assert frame1.get("func_name") == "func_caller"
    assert frame1.get("return_pc") == 0


def test_stack_info_detects_fp_cycle():
    state, vm = make_debug_state()
    vm.pc = 0x2000
    vm.sp = 0x8FD0
    vm.fp = 0x8FE0
    vm.regs_list[7] = vm.fp
    _write_word(vm, 0x8FE0, 0x8FE0)
    _write_word(vm, 0x8FE4, 0x2100)

    stack = state.stack_info(1, max_frames=4)
    assert stack["truncated"] is True
    assert any(err.startswith("fp_cycle") for err in stack["errors"])
    frames = stack["frames"]
    assert frames[0]["pc"] == 0x2000
    assert "return_pc" in frames[0]


def test_stack_info_reports_read_error():
    state, vm = make_debug_state()
    vm.pc = 0x3000
    vm.sp = 0x8FC0
    vm.fp = 0x8FD0
    vm.regs_list[7] = vm.fp
    _write_word(vm, 0x8FD0, 0x8FC0)
    _write_word(vm, 0x8FD4, 0x3100)

    original_read = vm.read_mem

    def failing_read(addr: int, length: int, pid: int | None = None) -> bytes:
        if addr == 0x8FC0:
            raise RuntimeError("boom")
        return original_read(addr, length, pid)

    vm.read_mem = failing_read  # type: ignore[assignment]

    stack = state.stack_info(1, max_frames=4)
    assert stack["truncated"] is True
    assert any(err.startswith("stack_read_failed") for err in stack["errors"])
    frames = stack["frames"]
    assert len(frames) == 2
    assert frames[0]["return_pc"] == 0x3100
    assert frames[1]["return_pc"] is None


def test_disasm_read_basic():
    state, vm = make_debug_state()
    base = 0x9000
    word_ldi = (0x01 << 24) | (1 << 20) | (0 << 16) | (0 << 12) | 0x123
    word_add = (0x10 << 24) | (2 << 20) | (1 << 16) | (1 << 12)
    word_brk = (0x7F << 24)
    _write_bytes(vm, base, word_ldi.to_bytes(4, "big"))
    _write_bytes(vm, base + 4, word_add.to_bytes(4, "big"))
    _write_bytes(vm, base + 8, word_brk.to_bytes(4, "big"))
    vm.pc = base
    _seed_symbol_table(state, 1, [("func_start", base, 12)])

    result = state.disasm_read(1, address=base, count=3, mode="on-demand")
    assert result["count"] == 3
    assert result["cached"] is False
    instructions = result["instructions"]
    assert instructions[0]["mnemonic"] == "LDI"
    assert instructions[0].get("label") == "func_start"
    assert instructions[1]["mnemonic"] == "ADD"
    assert instructions[2]["mnemonic"] == "BRK"

    cached_first = state.disasm_read(1, address=base, count=3, mode="cached")
    assert cached_first["mode"] == "cached"
    assert cached_first["cached"] is False
    cached_second = state.disasm_read(1, address=base, count=3, mode="cached")
    assert cached_second["cached"] is True
