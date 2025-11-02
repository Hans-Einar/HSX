import time
from typing import Tuple

from python import hsx_mailbox_constants as mbx_const
from platforms.python.host_vm import MiniVM, VMController


def _setup_controller(pid: int = 1) -> Tuple[VMController, MiniVM, int]:
    controller = VMController()
    controller.mailboxes.register_task(pid)
    controller.mailboxes.register_task(0)

    vm = MiniVM(b"", entry=0, mailboxes=controller.mailboxes)
    vm.context.pid = pid
    vm.set_mailbox_handler(lambda fn, vm=vm: controller._svc_mailbox_controller(vm, fn))
    state = vm.snapshot_state()
    state["context"]["pid"] = pid

    controller.vm = vm
    controller.current_pid = pid
    controller.tasks[pid] = {
        "pid": pid,
        "program": "<inline>",
        "state": "running",
        "priority": 10,
        "quantum": 1000,
        "pc": 0,
        "sleep_pending": False,
        "vm_state": state,
    }
    controller.task_states[pid] = state

    recv_handle = controller.mailboxes.open(pid=pid, target=f"pid:{pid}")
    return controller, vm, recv_handle


def _open_shell_handle(controller: VMController, pid: int) -> int:
    return controller.mailboxes.open(pid=0, target=f"pid:{pid}")


def test_mailbox_recv_blocks_and_wakes_on_send():
    controller, vm, recv_handle = _setup_controller()
    buffer_ptr = 0x0200
    vm.regs[1] = recv_handle
    vm.regs[2] = buffer_ptr
    vm.regs[3] = 64
    vm.regs[4] = mbx_const.HSX_MBX_TIMEOUT_INFINITE

    # Invoke blocking receive
    controller._svc_mailbox_controller(vm, mbx_const.HSX_MBX_FN_RECV)

    assert controller.waiting_tasks
    wait_info = controller.waiting_tasks.get(1)
    assert wait_info is not None
    assert wait_info["handle"] == recv_handle
    assert controller.tasks[1]["state"] == "waiting_mbx"
    assert vm.running is False

    # Send data from shell handle and verify wake-up
    sender_handle = _open_shell_handle(controller, 1)
    controller.mailbox_send(0, sender_handle, data="hello")

    assert not controller.waiting_tasks
    assert controller.tasks[1]["state"] in {"ready", "running", "returned"}
    regs = controller.task_states[1]["context"]["regs"]
    assert regs[0] == mbx_const.HSX_MBX_STATUS_OK
    assert regs[1] == len("hello")
    assert vm.running is True
    assert bytes(vm.mem[buffer_ptr : buffer_ptr + 5]) == b"hello"


def test_mailbox_recv_timeout_marks_task_ready():
    controller, vm, recv_handle = _setup_controller()
    buffer_ptr = 0x0300
    vm.regs[1] = recv_handle
    vm.regs[2] = buffer_ptr
    vm.regs[3] = 32
    vm.regs[4] = 10  # 10 ms timeout

    controller._svc_mailbox_controller(vm, mbx_const.HSX_MBX_FN_RECV)
    wait_info = controller.waiting_tasks.get(1)
    assert wait_info is not None

    # Force timeout by moving deadline to the past
    wait_info["deadline"] = time.monotonic() - 0.1
    controller._check_mailbox_timeouts()

    assert not controller.waiting_tasks
    assert controller.tasks[1]["state"] in {"ready", "running", "returned"}
    regs = controller.task_states[1]["context"]["regs"]
    assert regs[0] == mbx_const.HSX_MBX_STATUS_TIMEOUT
    assert regs[1] == 0
