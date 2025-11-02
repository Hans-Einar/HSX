import time

import pytest

import python.execd as execd
from python.execd import ExecutiveState, TaskState


class StubVM:
    def __init__(self, tasks):
        self.tasks = tasks
        self.current_pid = tasks[0]["pid"] if tasks else None

    def set_tasks(self, tasks, current_pid=None):
        self.tasks = tasks
        if current_pid is not None:
            self.current_pid = current_pid
        elif tasks:
            self.current_pid = tasks[0]["pid"]
        else:
            self.current_pid = None

    def ps(self):
        return {"tasks": {"tasks": self.tasks, "current_pid": self.current_pid}}


def make_task(pid, state, **extra):
    reg_base = extra.pop("reg_base", 0x1000 + (pid * 0x40))
    stack_size = extra.pop("stack_size", 0x100)
    stack_base = extra.pop("stack_base", 0x8000 + (pid * 0x100))
    default_limit = stack_base - stack_size if stack_size is not None else stack_base - 0x100
    stack_limit = extra.pop("stack_limit", default_limit)
    payload = {
        "pid": pid,
        "state": state,
        "reg_base": reg_base,
        "stack_base": stack_base,
        "stack_limit": stack_limit,
        "stack_size": stack_size,
    }
    payload.update(extra)
    return payload


def scheduler_events(state):
    return [event for event in state.event_history if event.get("type") == "scheduler"]


def test_task_state_transitions_recorded():
    vm = StubVM([make_task(1, "running")])
    state = ExecutiveState(vm, step_batch=1)
    state._refresh_tasks()
    entry = state.task_states[1]
    assert entry["state_enum"] == TaskState.RUNNING

    vm.set_tasks([make_task(1, "waiting_mbx")])
    state._refresh_tasks()
    entry = state.task_states[1]
    assert entry["state_enum"] == TaskState.WAIT_MBX
    history = state.last_state_transition[1]
    assert history["from"] == TaskState.RUNNING.value
    assert history["to"] == TaskState.WAIT_MBX.value


def test_invalid_transition_raises():
    vm = StubVM([make_task(2, "terminated")])
    state = ExecutiveState(vm, step_batch=1)
    state._refresh_tasks()
    vm.set_tasks([make_task(2, "running")])
    with pytest.raises(ValueError):
        state._refresh_tasks()


def test_sleep_tracking_and_wake(monkeypatch):
    now = time.monotonic()
    vm = StubVM(
        [
            make_task(
                3,
                "sleeping",
                sleep_deadline=now + 0.05,
                sleep_pending_ms=50,
                sleep_pending=True,
            )
        ]
    )
    state = ExecutiveState(vm, step_batch=1)
    state._refresh_tasks()
    assert 3 in state.sleeping_deadlines

    monkeypatch.setattr(execd.time, "monotonic", lambda: now + 0.1)
    state._advance_sleeping_tasks()

    assert 3 not in state.sleeping_deadlines
    assert state.tasks[3]["state"] == "ready"
    assert state.task_state_pending[3]["reason"] == "sleep_wake"


def test_context_isolation_violation_raises():
    vm = StubVM([make_task(10, "running", reg_base=0)])
    state = ExecutiveState(vm, step_batch=1)
    with pytest.raises(AssertionError):
        state._refresh_tasks()


def test_context_isolation_can_be_disabled():
    vm = StubVM([make_task(11, "running", reg_base=0)])
    state = ExecutiveState(vm, step_batch=1)
    state.enforce_context_isolation = False
    state._refresh_tasks()
    assert state.tasks[11]["reg_base"] == 0


def test_scheduler_event_quantum_expired():
    vm = StubVM(
        [
            make_task(1, "running", quantum=4, accounted_steps=1),
            make_task(2, "ready", quantum=4, accounted_steps=0),
        ]
    )
    state = ExecutiveState(vm, step_batch=1)
    state._refresh_tasks()
    vm.set_tasks(
        [
            make_task(2, "running", quantum=4, accounted_steps=0),
            make_task(1, "ready", quantum=4, accounted_steps=2),
        ],
        current_pid=2,
    )
    state._refresh_tasks()

    events = scheduler_events(state)
    assert events, "expected scheduler event to be emitted"
    event = events[-1]
    assert event["pid"] == 2
    data = event["data"]
    assert data["prev_pid"] == 1
    assert data["next_pid"] == 2
    assert data["reason"] == "quantum_expired"
    assert data.get("quantum_remaining") == 3
    assert data.get("post_state") == "ready"


def test_scheduler_event_sleep_reason():
    vm = StubVM(
        [
            make_task(1, "running"),
            make_task(2, "ready"),
        ]
    )
    state = ExecutiveState(vm, step_batch=1)
    state._refresh_tasks()
    vm.set_tasks(
        [
            make_task(2, "running"),
            make_task(1, "sleeping", sleep_pending=True, sleep_deadline=time.monotonic() + 0.05),
        ],
        current_pid=2,
    )
    state._refresh_tasks()

    events = scheduler_events(state)
    assert events, "expected scheduler event for sleep transition"
    event = events[-1]
    data = event["data"]
    assert data["reason"] == "sleep"
    assert data["prev_pid"] == 1
    assert data["next_pid"] == 2
    assert data.get("post_state") == "sleeping"


def test_scheduler_event_killed_reason():
    vm = StubVM(
        [
            make_task(1, "running"),
            make_task(2, "ready"),
        ]
    )
    state = ExecutiveState(vm, step_batch=1)
    state._refresh_tasks()
    vm.set_tasks(
        [
            make_task(2, "running"),
        ],
        current_pid=2,
    )
    state._refresh_tasks()

    events = scheduler_events(state)
    assert events, "expected scheduler event when previous task exits"
    event = events[-1]
    data = event["data"]
    assert data["reason"] == "killed"
    assert data["prev_pid"] == 1
    assert data["next_pid"] == 2
    assert data.get("post_state") == "terminated" or data.get("post_state") is None
