import pytest

from python.execd import ExecutiveState, TaskState


class StubVM:
    def __init__(self, tasks):
        self.tasks = tasks
        self.current_pid = tasks[0]["pid"] if tasks else None

    def set_tasks(self, tasks):
        self.tasks = tasks
        if tasks:
            self.current_pid = tasks[0]["pid"]

    def ps(self):
        return {"tasks": {"tasks": self.tasks, "current_pid": self.current_pid}}


def make_task(pid, state, **extra):
    payload = {"pid": pid, "state": state}
    payload.update(extra)
    return payload


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
