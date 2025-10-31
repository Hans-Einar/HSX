import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from python import asm as hsx_asm
from platforms.python.host_vm import MiniVM, VMController

from python.execd import ExecutiveState
import unittest


def _assemble(lines):
    code_words, entry, externs, imports_decl, rodata, relocs, exports, entry_symbol, _local_symbols = hsx_asm.assemble(lines)
    assert not relocs
    code_bytes = b"".join((word & 0xFFFFFFFF).to_bytes(4, "big") for word in code_words)
    return code_bytes, entry, rodata


def test_vmcontroller_step_respects_pause():
    lines = [
        ".entry",
        "loop:",
        "LDI R1, 1",
        "ADD R2, R2, R1",
        "JMP loop",
    ]
    code, entry, rodata = _assemble(lines)
    controller = VMController()
    vm = MiniVM(code, entry=entry, rodata=rodata)
    controller.vm = vm
    state = vm.snapshot_state()
    state["context"]["pid"] = 1
    controller.task_states[1] = state
    controller.tasks[1] = {
        "pid": 1,
        "program": "<inline>",
        "state": "running",
        "priority": state["context"].get("priority", 10),
        "quantum": state["context"].get("time_slice_steps", 1),
        "pc": state["context"].get("pc", entry),
        "sleep_pending": False,
        "vm_state": state,
    }
    controller.current_pid = 1

    first = controller.step(5)
    assert first["executed"] > 0
    steps_before = controller.vm.steps

    controller.paused = True
    second = controller.step(10)
    assert second["executed"] == 0
    assert second["paused"] is True
    assert controller.vm.steps == steps_before


class _StubVM:
    def __init__(self):
        self.paused = False
        self.pause_calls = 0
        self.resume_calls = 0
        self.reset_calls = 0
        self.kill_calls = 0
        self.step_calls = 0
        self.steps = 0
        self.tasks = {1: {"pid": 1, "state": "running", "pc": 0}}
        self.current_pid = 1

    def pause(self, pid: int | None = None):
        self.pause_calls += 1
        self.paused = True
        if pid is not None and pid in self.tasks:
            self.tasks[pid]["state"] = "paused"
        return {"status": "ok"}

    def resume(self, pid: int | None = None):
        self.resume_calls += 1
        self.paused = False
        if pid is not None and pid in self.tasks:
            self.tasks[pid]["state"] = "running"
            self.current_pid = pid
        return {"status": "ok"}

    def reset(self):
        self.reset_calls += 1
        self.paused = False
        self.tasks.clear()
        return {"status": "ok"}

    def kill(self, pid: int):
        self.kill_calls += 1
        self.tasks.pop(pid, None)
        return {"status": "ok"}

    def step(self, steps, pid: int | None = None):
        self.step_calls += 1
        if self.paused:
            return {
                "executed": 0,
                "running": True,
                "pc": 0x0010,
                "steps": self.steps,
                "cycles": self.steps,
                "sleep_pending": False,
                "paused": True,
                "current_pid": self.current_pid,
            }
        self.steps += steps
        return {
            "executed": steps,
            "running": True,
            "pc": 0x0020,
            "steps": self.steps,
            "cycles": self.steps,
            "sleep_pending": False,
            "paused": False,
            "current_pid": self.current_pid,
        }

    def read_mem(self, addr, length, pid: int | None = None):
        return bytes(length)

    def write_mem(self, addr, data, pid: int | None = None):
        return None

    def read_regs(self, pid: int | None = None):
        return {
            "pc": 0x0020,
            "regs": [0] * 16,
            "sp": 0x8000,
            "flags": 0,
            "running": True,
            "steps": self.steps,
            "cycles": self.steps,
            "context": {
                "pc": 0x0020,
                "regs": [0] * 16,
                "sp": 0x8000,
                "psw": 0,
                "reg_base": 0,
                "stack_base": 0,
                "stack_limit": 0,
                "time_slice_steps": 1,
                "time_slice_cycles": 1,
                "accounted_steps": self.steps,
                "accounted_cycles": self.steps,
                "state": "running",
                "priority": 10,
                "pid": pid,
            },
        }

    def info(self):
        return {"paused": self.paused}

    def attach(self):
        return {}

    def detach(self):
        return {}

    def load(self, path, verbose=False):
        return {"entry": 0, "pid": 1}

    def ps(self):
        return {"tasks": list(self.tasks.values()), "current_pid": self.current_pid}

    def sched(self, pid: int, priority=None, quantum=None):
        task = self.tasks.get(pid, {"pid": pid})
        if priority is not None:
            task["priority"] = int(priority)
        if quantum is not None:
            task["quantum"] = int(quantum)
        self.tasks[pid] = task
        return task


def test_executive_pause_resume_kill():
    vm = _StubVM()
    state = ExecutiveState(vm)
    state._refresh_tasks()
    state.tasks = {1: {"pid": 1, "state": "running", "pc": 0, "sleep_pending": False}}

    paused_task = state.pause_task(1)
    assert paused_task["state"] == "paused"
    assert vm.pause_calls == 1

    step_result = state.step(4)
    assert step_result.get("paused") is True

    resumed_task = state.resume_task(1)
    assert resumed_task["state"] == "running"
    assert vm.resume_calls == 1

    running_result = state.step(3)
    assert running_result.get("paused") is False

    killed_task = state.kill_task(1)
    assert killed_task["state"] == "terminated"
    assert vm.kill_calls == 1


def test_round_robin_single_instruction():
    lines = [
        ".text",
        ".entry start",
        "start:",
        "LDI R1, 1",
        "ADD R0, R0, R1",
        "JMP start",
    ]
    code, entry, rodata = _assemble(lines)
    controller = VMController()

    def _add_task(pid: int) -> None:
        vm = MiniVM(code, entry=entry, rodata=rodata)
        state = vm.snapshot_state()
        ctx = state["context"]
        ctx["pid"] = pid
        ctx["regs"][1] = 1
        controller.task_states[pid] = state
        controller.tasks[pid] = {
            "pid": pid,
            "program": f"<loop-{pid}>",
            "state": "running",
            "priority": ctx.get("priority", 10),
            "quantum": ctx.get("time_slice_steps", 1),
            "pc": ctx.get("pc", entry),
            "sleep_pending": False,
            "vm_state": state,
            "trace": False,
        }

    _add_task(1)
    _add_task(2)
    controller.current_pid = 1
    controller._activate_task(1)

    controller.step(4)

    for pid in (1, 2):
        ctx = controller.task_states[pid]["context"]
        assert ctx.get("accounted_steps") == 2


class TestRegisterWindowIsolation(unittest.TestCase):
    def test_register_windows_isolated_between_tasks(self):
        repo_root = Path(__file__).resolve().parents[2]
        controller = VMController()
        consumer = controller.load_from_path(str(repo_root / "examples/demos/build/mailbox/consumer.hxe"))
        producer = controller.load_from_path(str(repo_root / "examples/demos/build/mailbox/producer.hxe"))

        controller._activate_task(consumer["pid"])
        controller.vm.regs[1] = 0xAAAAAAAA
        controller._store_active_state()

        controller._activate_task(producer["pid"])
        controller.vm.regs[1] = 0xBBBBBBBB
        controller._store_active_state()

        consumer_ctx = controller.task_states[consumer["pid"]]["context"]
        producer_ctx = controller.task_states[producer["pid"]]["context"]

        self.assertEqual(consumer_ctx["regs"][1], 0xAAAAAAAA & 0xFFFFFFFF)
        self.assertEqual(producer_ctx["regs"][1], 0xBBBBBBBB & 0xFFFFFFFF)
