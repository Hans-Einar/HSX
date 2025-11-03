import errno
import struct
import time
from typing import Any, Dict, List, Optional

from platforms.python.host_vm import VMController, MiniVM, context_to_dict
from python.mailbox import MailboxManager
from python import hsx_mailbox_constants as mbx_const


def _make_controller() -> VMController:
    controller = VMController()
    # ensure consistent mailbox manager instance for the MiniVM we spin up
    controller.mailboxes = MailboxManager()
    return controller


RECV_INFO_STRUCT = struct.Struct("<iiIII")


def _make_controller_with_tasks(*pids: int) -> VMController:
    controller = _make_controller()
    for pid in pids:
        controller.mailboxes.register_task(pid)
        controller.mailboxes.ensure_stdio_handles(pid)
    return controller


def _attach_vm(controller: VMController, pid: int) -> MiniVM:
    vm = MiniVM(b"", entry=0x0100, mailboxes=controller.mailboxes)
    vm.pid = pid
    vm.context.pid = pid
    vm.context.pc = 0x2000 + pid
    controller.vm = vm
    controller.current_pid = pid
    state = {
        "context": context_to_dict(vm.context),
        "mem": vm.mem,
        "running": vm.running,
    }
    controller.task_states[pid] = state
    controller.tasks[pid] = {"pid": pid, "state": "running", "vm_state": state}
    return vm


def _write_c_string(vm: MiniVM, addr: int, text: str) -> None:
    data = text.encode("ascii") + b"\x00"
    vm.mem[addr : addr + len(data)] = data


def _drain_events(vm: MiniVM, event_type: Optional[str] = None) -> List[Dict[str, Any]]:
    events = vm.consume_events()
    if event_type is None:
        return events
    return [evt for evt in events if evt.get("type") == event_type]


def test_mailbox_recv_wakes_consumer_via_svc():
    controller = _make_controller()

    # Register two tasks so manager allocates stdio/control descriptors.
    controller.mailboxes.register_task(1)
    controller.mailboxes.register_task(2)
    controller.mailboxes.ensure_stdio_handles(1)
    controller.mailboxes.ensure_stdio_handles(2)

    # Create a shared application mailbox via the manager (descriptor reuse).
    target = "app:svc_test"
    consumer_handle = controller.mailboxes.open(pid=1, target=target)
    producer_handle = controller.mailboxes.open(pid=2, target=target)

    # Sanity check: handles should refer to the same descriptor.
    consumer_desc = controller.mailboxes.descriptor_for_handle(1, consumer_handle)
    producer_desc = controller.mailboxes.descriptor_for_handle(2, producer_handle)
    assert consumer_desc.descriptor_id == producer_desc.descriptor_id

    # Minimal VM wiring: single task (PID 1) with deterministic PC.
    mini_vm = MiniVM(b"", entry=0x0100, mailboxes=controller.mailboxes)
    mini_vm.pid = 1
    mini_vm.context.pid = 1
    mini_vm.context.pc = 0x1234
    controller.vm = mini_vm
    controller.current_pid = 1

    # Prepare buffer and recv-info locations inside VM memory.
    buffer_ptr = 0x0200
    info_ptr = 0x0240
    mini_vm.mem[buffer_ptr : buffer_ptr + 32] = b"\x00" * 32
    mini_vm.mem[info_ptr : info_ptr + 20] = b"\xFF" * 20

    # Issue MAILBOX_RECV with infinite timeout and info pointer.
    mini_vm.regs[1] = consumer_handle & 0xFFFF
    mini_vm.regs[2] = buffer_ptr & 0xFFFF
    mini_vm.regs[3] = 32
    mini_vm.regs[4] = mbx_const.HSX_MBX_TIMEOUT_INFINITE
    mini_vm.regs[5] = info_ptr & 0xFFFF

    controller._svc_mailbox_controller(mini_vm, mbx_const.HSX_MBX_FN_RECV)

    # Task should now be waiting on the descriptor.
    assert mini_vm.running is False
    assert 1 in controller.waiting_tasks
    wait_info = controller.waiting_tasks[1]
    assert wait_info["descriptor_id"] == consumer_desc.descriptor_id

    # Producer sends data; deliver to waiting consumer via runtime helper.
    ok, descriptor_id = controller.mailboxes.send(
        pid=2,
        handle=producer_handle,
        payload=b"hello",
        flags=0,
        channel=0,
    )
    assert ok is True
    controller._deliver_mailbox_messages(descriptor_id)

    # Consumer should be resumed with registers/memory populated.
    assert mini_vm.running is True
    assert controller.waiting_tasks == {}
    assert mini_vm.regs[0] == mbx_const.HSX_MBX_STATUS_OK
    assert mini_vm.regs[1] == 5
    assert mini_vm.regs[2] == 0
    assert mini_vm.regs[3] == 0
    assert mini_vm.regs[4] == 2
    assert mini_vm.mem[buffer_ptr : buffer_ptr + 5] == b"hello"
    info_status = RECV_INFO_STRUCT.unpack(mini_vm.mem[info_ptr : info_ptr + RECV_INFO_STRUCT.size])
    assert info_status == (
        mbx_const.HSX_MBX_STATUS_OK,
        5,
        0,
        0,
        2,
    )

    # PC should remain unchanged across wait/resume (no corruption).
    assert mini_vm.context.pc == 0x1234


def test_mailbox_svc_app_bind_open_reuse_and_backpressure():
    controller = _make_controller_with_tasks(1, 2)

    target = "app:svc_phase2"
    target_addr = 0x0300

    vm1 = _attach_vm(controller, 1)
    _write_c_string(vm1, target_addr, target)
    vm1.regs[1] = target_addr
    vm1.regs[2] = 16
    vm1.regs[3] = mbx_const.HSX_MBX_MODE_RDWR
    controller._svc_mailbox_controller(vm1, mbx_const.HSX_MBX_FN_BIND)
    assert vm1.regs[0] == mbx_const.HSX_MBX_STATUS_OK
    descriptor_id = vm1.regs[1]
    desc = controller.mailboxes.descriptor_by_id(descriptor_id)
    assert desc.namespace == mbx_const.HSX_MBX_NAMESPACE_APP
    assert desc.capacity == 16

    vm1.regs[1] = target_addr
    vm1.regs[2] = 0
    controller._svc_mailbox_controller(vm1, mbx_const.HSX_MBX_FN_OPEN)
    handle_pid1 = vm1.regs[1]

    vm2 = _attach_vm(controller, 2)
    _write_c_string(vm2, target_addr, target)
    vm2.regs[1] = target_addr
    vm2.regs[2] = 0
    controller._svc_mailbox_controller(vm2, mbx_const.HSX_MBX_FN_OPEN)
    handle_pid2 = vm2.regs[1]

    desc1 = controller.mailboxes.descriptor_for_handle(1, handle_pid1)
    desc2 = controller.mailboxes.descriptor_for_handle(2, handle_pid2)
    assert desc1.descriptor_id == descriptor_id == desc2.descriptor_id

    payload = b"12345678"
    send_ptr = 0x0400
    controller.vm = vm1
    controller.current_pid = 1
    vm1.mem[send_ptr : send_ptr + len(payload)] = payload
    vm1.regs[1] = handle_pid1
    vm1.regs[2] = send_ptr
    vm1.regs[3] = len(payload)
    vm1.regs[4] = 0
    vm1.regs[5] = 0
    controller._svc_mailbox_controller(vm1, mbx_const.HSX_MBX_FN_SEND)
    assert vm1.regs[0] == mbx_const.HSX_MBX_STATUS_OK

    vm1.regs[1] = handle_pid1
    vm1.regs[2] = send_ptr
    vm1.regs[3] = len(payload)
    vm1.regs[4] = 0
    vm1.regs[5] = 0
    controller._svc_mailbox_controller(vm1, mbx_const.HSX_MBX_FN_SEND)
    assert vm1.regs[0] == mbx_const.HSX_MBX_STATUS_WOULDBLOCK

    recv_ptr = 0x0500
    controller.vm = vm2
    controller.current_pid = 2
    vm2.mem[recv_ptr : recv_ptr + 16] = b"\x00" * 16
    vm2.regs[1] = handle_pid2
    vm2.regs[2] = recv_ptr
    vm2.regs[3] = 16
    vm2.regs[4] = mbx_const.HSX_MBX_TIMEOUT_POLL
    vm2.regs[5] = 0
    controller._svc_mailbox_controller(vm2, mbx_const.HSX_MBX_FN_RECV)
    assert vm2.regs[0] == mbx_const.HSX_MBX_STATUS_OK
    assert vm2.mem[recv_ptr : recv_ptr + len(payload)] == payload


def test_mailbox_svc_shared_fanout_writes_recv_info():
    controller = _make_controller_with_tasks(1, 2, 3)

    target = "shared:svc_bus"
    mode_mask = (
        mbx_const.HSX_MBX_MODE_RDWR
        | mbx_const.HSX_MBX_MODE_FANOUT
        | mbx_const.HSX_MBX_MODE_FANOUT_DROP
    )
    target_addr = 0x0300

    vm1 = _attach_vm(controller, 1)
    _write_c_string(vm1, target_addr, target)
    vm1.regs[1] = target_addr
    vm1.regs[2] = 64
    vm1.regs[3] = mode_mask
    controller._svc_mailbox_controller(vm1, mbx_const.HSX_MBX_FN_BIND)
    assert vm1.regs[0] == mbx_const.HSX_MBX_STATUS_OK
    descriptor_id = vm1.regs[1]
    shared_desc = controller.mailboxes.descriptor_by_id(descriptor_id)
    assert shared_desc.mode_mask & mbx_const.HSX_MBX_MODE_FANOUT

    vm1.regs[1] = target_addr
    vm1.regs[2] = 0
    controller._svc_mailbox_controller(vm1, mbx_const.HSX_MBX_FN_OPEN)
    handle_pid1 = vm1.regs[1]

    vm2 = _attach_vm(controller, 2)
    _write_c_string(vm2, target_addr, target)
    vm2.regs[1] = target_addr
    vm2.regs[2] = 0
    controller._svc_mailbox_controller(vm2, mbx_const.HSX_MBX_FN_OPEN)
    handle_pid2 = vm2.regs[1]

    vm3 = _attach_vm(controller, 3)
    _write_c_string(vm3, target_addr, target)
    vm3.regs[1] = target_addr
    vm3.regs[2] = 0
    controller._svc_mailbox_controller(vm3, mbx_const.HSX_MBX_FN_OPEN)
    sender_handle = vm3.regs[1]

    recv_state = {}
    for pid, handle in ((1, handle_pid1), (2, handle_pid2)):
        vm = vm1 if pid == 1 else vm2
        controller.vm = vm
        controller.current_pid = pid
        buffer_ptr = 0x0500
        info_ptr = 0x0600
        vm.mem[buffer_ptr : buffer_ptr + 32] = b"\x00" * 32
        vm.mem[info_ptr : info_ptr + RECV_INFO_STRUCT.size] = b"\xAA" * RECV_INFO_STRUCT.size
        vm.regs[1] = handle
        vm.regs[2] = buffer_ptr
        vm.regs[3] = 32
        vm.regs[4] = mbx_const.HSX_MBX_TIMEOUT_INFINITE
        vm.regs[5] = info_ptr
        controller._svc_mailbox_controller(vm, mbx_const.HSX_MBX_FN_RECV)
        assert vm.running is False
        recv_state[pid] = {"vm": vm, "buffer": buffer_ptr, "info": info_ptr}

    payload = b"fanout!"
    send_ptr = 0x0700
    controller.vm = vm3
    controller.current_pid = 3
    vm3.mem[send_ptr : send_ptr + len(payload)] = payload
    vm3.regs[1] = sender_handle
    vm3.regs[2] = send_ptr
    vm3.regs[3] = len(payload)
    vm3.regs[4] = 0
    vm3.regs[5] = 0
    controller._svc_mailbox_controller(vm3, mbx_const.HSX_MBX_FN_SEND)
    assert vm3.regs[0] == mbx_const.HSX_MBX_STATUS_OK
    assert controller.waiting_tasks == {}

    for pid in (1, 2):
        state = controller.task_states[pid]
        regs = state["context"]["regs"]
        assert regs[0] == mbx_const.HSX_MBX_STATUS_OK
        assert regs[1] == len(payload)
        assert regs[2] == 0
        assert regs[3] == 0
        assert regs[4] == 3
        vm = recv_state[pid]["vm"]
        buffer_ptr = recv_state[pid]["buffer"]
        info_ptr = recv_state[pid]["info"]
        assert vm.mem[buffer_ptr : buffer_ptr + len(payload)] == payload
        info_values = RECV_INFO_STRUCT.unpack(
            vm.mem[info_ptr : info_ptr + RECV_INFO_STRUCT.size]
        )
        assert info_values == (
            mbx_const.HSX_MBX_STATUS_OK,
            len(payload),
            0,
            0,
            3,
        )


def test_mailbox_svc_recv_timeout_populates_info_struct():
    controller = _make_controller_with_tasks(1)
    target = "shared:timeout_demo"
    target_addr = 0x0400

    vm = _attach_vm(controller, 1)
    _write_c_string(vm, target_addr, target)
    vm.regs[1] = target_addr
    vm.regs[2] = 0
    controller._svc_mailbox_controller(vm, mbx_const.HSX_MBX_FN_OPEN)
    handle = vm.regs[1]

    buffer_ptr = 0x0800
    info_ptr = 0x0840
    vm.mem[buffer_ptr : buffer_ptr + 16] = b"\x00" * 16
    vm.mem[info_ptr : info_ptr + RECV_INFO_STRUCT.size] = b"\xDD" * RECV_INFO_STRUCT.size

    vm.regs[1] = handle
    vm.regs[2] = buffer_ptr
    vm.regs[3] = 16
    vm.regs[4] = 5
    vm.regs[5] = info_ptr

    controller._svc_mailbox_controller(vm, mbx_const.HSX_MBX_FN_RECV)
    assert vm.running is False
    assert 1 in controller.waiting_tasks
    controller.waiting_tasks[1]["deadline"] = time.monotonic() - 0.1

    controller._check_mailbox_timeouts()
    assert 1 not in controller.waiting_tasks

    state = controller.task_states[1]
    regs = state["context"]["regs"]
    assert regs[0] == mbx_const.HSX_MBX_STATUS_TIMEOUT
    assert regs[1] == 0
    assert regs[2] == 0
    assert regs[3] == 0
    assert regs[4] == 0
    info_values = RECV_INFO_STRUCT.unpack(
        vm.mem[info_ptr : info_ptr + RECV_INFO_STRUCT.size]
    )
    assert info_values == (
        mbx_const.HSX_MBX_STATUS_TIMEOUT,
        0,
        0,
        0,
        0,
    )
    assert vm.mem[buffer_ptr : buffer_ptr + 16] == b"\x00" * 16


def test_mailbox_bind_returns_no_descriptor_when_pool_full():
    controller = VMController()
    controller.mailboxes = MailboxManager(max_descriptors=8)
    controller.mailboxes.register_task(1)
    controller.mailboxes.ensure_stdio_handles(1)

    fill_idx = 0
    while controller.mailboxes.descriptor_count < controller.mailboxes.max_descriptors:
        controller.mailboxes.bind_target(pid=1, target=f"app:fill_{fill_idx}")
        fill_idx += 1

    vm = _attach_vm(controller, 1)
    target_addr = 0x0900
    overflow_target = "app:overflow_limit"
    _write_c_string(vm, target_addr, overflow_target)
    vm.regs[1] = target_addr
    vm.regs[2] = 0
    vm.regs[3] = mbx_const.HSX_MBX_MODE_RDWR

    controller._svc_mailbox_controller(vm, mbx_const.HSX_MBX_FN_BIND)
    assert vm.regs[0] == mbx_const.HSX_MBX_STATUS_NO_DESCRIPTOR


def test_mailbox_open_returns_enospc_when_handle_quota_exhausted():
    controller = VMController(mailbox_profile={"handle_limit_per_pid": 4})
    controller.mailboxes.register_task(1)
    controller.mailboxes.ensure_stdio_handles(1)
    prefill_handle = controller.mailboxes.open(pid=1, target="app:pre_fill")

    vm = _attach_vm(controller, 1)
    overflow_target = "app:quota_hit"
    target_addr = 0x0A00
    _write_c_string(vm, target_addr, overflow_target)
    vm.regs[1] = target_addr
    vm.regs[2] = 0

    controller._svc_mailbox_controller(vm, mbx_const.HSX_MBX_FN_OPEN)
    assert vm.regs[0] == mbx_const.HSX_MBX_STATUS_NO_DESCRIPTOR
    events = _drain_events(vm)
    assert any(event.get("type") == "mailbox_exhausted" and event.get("reason") == "handle_limit" for event in events)

    controller.mailboxes.close(pid=1, handle=prefill_handle)
    vm.regs[0] = vm.regs[2] = 0
    vm.regs[1] = target_addr
    controller._svc_mailbox_controller(vm, mbx_const.HSX_MBX_FN_OPEN)
    assert vm.regs[0] == mbx_const.HSX_MBX_STATUS_OK


def test_vmcontroller_supports_named_mailbox_profile():
    controller = VMController(mailbox_profile="embedded")
    stats = controller.mailboxes.resource_stats()
    assert stats["max_descriptors"] == 16
    assert stats["handle_limit_per_pid"] == 8


def test_vmcontroller_env_mailbox_profile(monkeypatch):
    monkeypatch.setenv("HSX_MAILBOX_PROFILE", "embedded")
    controller = VMController()
    stats = controller.mailboxes.resource_stats()
    assert stats["max_descriptors"] == 16
    assert stats["handle_limit_per_pid"] == 8
    assert controller.mailbox_profile_name == "embedded"


def test_descriptor_pool_exhaustion_emits_event_and_existing_handles_work():
    controller = VMController(mailbox_profile={"max_descriptors": 4})
    controller.mailboxes.register_task(1)
    controller.mailboxes.ensure_stdio_handles(1)
    vm = _attach_vm(controller, 1)
    _drain_events(vm)

    target_addr = 0x0800
    overflow_target = "app:out_of_descriptors"
    _write_c_string(vm, target_addr, overflow_target)
    vm.regs[1] = target_addr
    vm.regs[2] = 0
    vm.regs[3] = mbx_const.HSX_MBX_MODE_RDWR

    controller._svc_mailbox_controller(vm, mbx_const.HSX_MBX_FN_BIND)
    assert vm.regs[0] == mbx_const.HSX_MBX_STATUS_NO_DESCRIPTOR
    events = _drain_events(vm)
    assert any(event.get("type") == "mailbox_exhausted" and event.get("reason") == "descriptor_pool_full" for event in events)

    handles = controller.mailboxes.ensure_stdio_handles(1)
    stdout_handle = handles["stdout"]
    ok, _ = controller.mailboxes.send(pid=1, handle=stdout_handle, payload=b"ping")
    assert ok is True
    msg = controller.mailboxes.recv(pid=1, handle=stdout_handle)
    assert msg is not None and msg.payload == b"ping"


def test_mailbox_send_event_payload():
    controller = _make_controller_with_tasks(1)
    vm = _attach_vm(controller, 1)
    controller.current_pid = 1

    target = "app:event_send"
    desc = controller.mailboxes.bind_target(pid=1, target=target, mode_mask=mbx_const.HSX_MBX_MODE_RDWR)
    handle = controller.mailboxes.open(pid=1, target=target)
    _drain_events(vm)

    payload = b"ping"
    buffer_ptr = 0x0200
    vm.mem[buffer_ptr : buffer_ptr + len(payload)] = payload
    vm.regs[1] = handle
    vm.regs[2] = buffer_ptr
    vm.regs[3] = len(payload)
    vm.regs[4] = 0
    vm.regs[5] = 0

    controller._svc_mailbox_controller(vm, mbx_const.HSX_MBX_FN_SEND)

    events = _drain_events(vm, "mailbox_send")
    assert events, "expected mailbox_send event"
    event = events[-1]
    assert event["descriptor"] == desc.descriptor_id
    assert event["handle"] == handle
    assert event["length"] == len(payload)
    assert event["src_pid"] == 1


def test_mailbox_recv_event_payload():
    controller = _make_controller_with_tasks(1)
    vm = _attach_vm(controller, 1)
    controller.current_pid = 1

    target = "app:event_recv"
    desc = controller.mailboxes.bind_target(pid=1, target=target, mode_mask=mbx_const.HSX_MBX_MODE_RDWR)
    handle = controller.mailboxes.open(pid=1, target=target)

    controller.mailboxes.send(pid=1, handle=handle, payload=b"hello", flags=0)
    _drain_events(vm)

    buffer_ptr = 0x0300
    vm.mem[buffer_ptr : buffer_ptr + 16] = b"\x00" * 16
    vm.regs[1] = handle
    vm.regs[2] = buffer_ptr
    vm.regs[3] = 16
    vm.regs[4] = mbx_const.HSX_MBX_TIMEOUT_POLL
    vm.regs[5] = 0

    controller._svc_mailbox_controller(vm, mbx_const.HSX_MBX_FN_RECV)

    events = _drain_events(vm, "mailbox_recv")
    assert events, "expected mailbox_recv event"
    event = events[-1]
    assert event["descriptor"] == desc.descriptor_id
    assert event["handle"] == handle
    assert event["length"] == 5
    assert event["src_pid"] == 1


def test_mailbox_wait_and_wake_event_payload():
    controller = _make_controller_with_tasks(1)
    vm = _attach_vm(controller, 1)
    controller.current_pid = 1

    target = "app:event_wait"
    desc = controller.mailboxes.bind_target(pid=1, target=target, mode_mask=mbx_const.HSX_MBX_MODE_RDWR)
    handle = controller.mailboxes.open(pid=1, target=target)

    buffer_ptr = 0x0400
    vm.mem[buffer_ptr : buffer_ptr + 16] = b"\x00" * 16
    vm.regs[1] = handle
    vm.regs[2] = buffer_ptr
    vm.regs[3] = 16
    vm.regs[4] = mbx_const.HSX_MBX_TIMEOUT_INFINITE
    vm.regs[5] = 0

    controller._svc_mailbox_controller(vm, mbx_const.HSX_MBX_FN_RECV)
    wait_events = _drain_events(vm, "mailbox_wait")
    assert wait_events, "expected mailbox_wait event"
    wait_event = wait_events[-1]
    assert wait_event["descriptor"] == desc.descriptor_id
    assert wait_event["handle"] == handle

    ok, descriptor_id = controller.mailboxes.send(pid=1, handle=handle, payload=b"wake", flags=0)
    assert ok is True
    controller._deliver_mailbox_messages(descriptor_id)

    wake_events = _drain_events(vm, "mailbox_wake")
    assert wake_events, "expected mailbox_wake event"
    wake_event = wake_events[-1]
    assert wake_event["descriptor"] == desc.descriptor_id
    assert wake_event["handle"] == handle
    assert wake_event["length"] == 4


def test_mailbox_timeout_event_payload():
    controller = _make_controller_with_tasks(1)
    vm = _attach_vm(controller, 1)
    controller.current_pid = 1

    target = "app:event_timeout"
    desc = controller.mailboxes.bind_target(pid=1, target=target, mode_mask=mbx_const.HSX_MBX_MODE_RDWR)
    handle = controller.mailboxes.open(pid=1, target=target)

    buffer_ptr = 0x0500
    vm.mem[buffer_ptr : buffer_ptr + 16] = b"\x00" * 16
    vm.regs[1] = handle
    vm.regs[2] = buffer_ptr
    vm.regs[3] = 16
    vm.regs[4] = 5
    vm.regs[5] = 0

    controller._svc_mailbox_controller(vm, mbx_const.HSX_MBX_FN_RECV)
    controller.waiting_tasks[1]["deadline"] = time.monotonic() - 0.1
    controller._check_mailbox_timeouts()

    timeout_events = _drain_events(vm, "mailbox_timeout")
    assert timeout_events, "expected mailbox_timeout event"
    event = timeout_events[-1]
    assert event["descriptor"] == desc.descriptor_id
    assert event["handle"] == handle
    assert event["status"] == mbx_const.HSX_MBX_STATUS_TIMEOUT


def test_mailbox_overrun_event_payload():
    controller = _make_controller_with_tasks(1)
    vm = _attach_vm(controller, 1)
    controller.current_pid = 1

    captured: List[Dict[str, Any]] = []

    def capture_event(event: Dict[str, Any]) -> None:
        captured.append(dict(event))
        controller._handle_mailbox_manager_event(event)

    controller.mailboxes.set_event_hook(capture_event)

    target = "shared:overrun"
    mode_mask = (
        mbx_const.HSX_MBX_MODE_RDWR
        | mbx_const.HSX_MBX_MODE_FANOUT
        | mbx_const.HSX_MBX_MODE_FANOUT_DROP
    )
    desc = controller.mailboxes.bind_target(pid=1, target=target, capacity=16, mode_mask=mode_mask)
    handle = controller.mailboxes.open(pid=1, target=target)

    buffer_ptr = 0x0600
    first_payload = b"abcdefgh"
    vm.mem[buffer_ptr : buffer_ptr + len(first_payload)] = first_payload
    vm.regs[1] = handle
    vm.regs[2] = buffer_ptr
    vm.regs[3] = len(first_payload)
    vm.regs[4] = 0
    vm.regs[5] = 0
    controller._svc_mailbox_controller(vm, mbx_const.HSX_MBX_FN_SEND)
    _drain_events(vm)

    second_payload = b"ijklmnop"
    vm.mem[buffer_ptr : buffer_ptr + len(second_payload)] = second_payload
    vm.regs[1] = handle
    vm.regs[2] = buffer_ptr
    vm.regs[3] = len(second_payload)
    vm.regs[4] = 0
    vm.regs[5] = 0
    controller._svc_mailbox_controller(vm, mbx_const.HSX_MBX_FN_SEND)

    overrun_events = [evt for evt in captured if evt.get("type") == "mailbox_overrun"]
    assert overrun_events, "expected mailbox_overrun event"
    event = overrun_events[-1]
    assert event["descriptor"] == desc.descriptor_id
    assert event["reason"] == "fanout_drop"
    assert event["dropped_length"] == len(first_payload)
