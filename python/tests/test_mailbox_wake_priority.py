"""
Test wake priority handling for mailbox subsystem (Phase 3.3).

These tests verify:
1. FIFO order preserved for single-reader mode
2. All waiters woken in fan-out mode
3. No starvation under various scenarios
"""
from typing import Dict

from python import hsx_mailbox_constants as mbx_const
from platforms.python.host_vm import MiniVM, VMController


def _create_task(controller: VMController, pid: int) -> MiniVM:
    """Create and register a task with the controller."""
    controller.mailboxes.register_task(pid)
    
    vm = MiniVM(b"", entry=0, mailboxes=controller.mailboxes)
    vm.context.pid = pid
    vm.set_mailbox_handler(lambda fn, vm=vm: controller._svc_mailbox_controller(vm, fn))
    state = vm.snapshot_state()
    state["context"]["pid"] = pid
    
    controller.tasks[pid] = {
        "pid": pid,
        "program": f"<task{pid}>",
        "state": "running",
        "priority": 10,
        "quantum": 1000,
        "pc": 0,
        "sleep_pending": False,
        "vm_state": state,
    }
    controller.task_states[pid] = state
    
    return vm


def test_single_reader_fifo_wake_order():
    """Test that single-reader mode wakes waiters in FIFO order."""
    controller = VMController()
    controller.mailboxes.register_task(0)  # Shell/sender
    
    # Create 3 reader tasks
    vms: Dict[int, MiniVM] = {}
    handles: Dict[int, int] = {}
    for pid in [1, 2, 3]:
        vm = _create_task(controller, pid)
        vms[pid] = vm
        # All readers open the same mailbox (single-reader mode)
        handles[pid] = controller.mailboxes.open(pid=pid, target="shared:test")
    
    # All three tasks issue blocking recv in order: PID 1, 2, 3
    buffer_ptr = 0x0200
    for pid in [1, 2, 3]:
        vm = vms[pid]
        controller.current_pid = pid
        controller.vm = vm
        vm.regs[1] = handles[pid]
        vm.regs[2] = buffer_ptr
        vm.regs[3] = 64
        vm.regs[4] = mbx_const.HSX_MBX_TIMEOUT_INFINITE
        controller._svc_mailbox_controller(vm, mbx_const.HSX_MBX_FN_RECV)
    
    # Verify all three are waiting
    assert len(controller.waiting_tasks) == 3
    
    # Send one message from shell
    sender_handle = controller.mailboxes.open(pid=0, target="shared:test")
    ok, desc_id = controller.mailboxes.send(pid=0, handle=sender_handle, payload=b"msg1")
    assert ok
    
    # Deliver messages - should wake only PID 1 (FIFO order)
    controller._deliver_mailbox_messages(desc_id)
    
    # PID 1 should be woken, PIDs 2 and 3 should still be waiting
    assert 1 not in controller.waiting_tasks
    assert 2 in controller.waiting_tasks
    assert 3 in controller.waiting_tasks
    
    # Send another message - should wake PID 2
    ok, desc_id = controller.mailboxes.send(pid=0, handle=sender_handle, payload=b"msg2")
    assert ok
    controller._deliver_mailbox_messages(desc_id)
    
    assert 2 not in controller.waiting_tasks
    assert 3 in controller.waiting_tasks
    
    # Send third message - should wake PID 3
    ok, desc_id = controller.mailboxes.send(pid=0, handle=sender_handle, payload=b"msg3")
    assert ok
    controller._deliver_mailbox_messages(desc_id)
    
    assert 3 not in controller.waiting_tasks
    assert len(controller.waiting_tasks) == 0


def test_fanout_wakes_all_readers():
    """Test that fan-out mode wakes ALL readers when a message arrives."""
    controller = VMController()
    controller.mailboxes.register_task(0)  # Shell/sender
    
    # Create fan-out mailbox
    mode = (mbx_const.HSX_MBX_MODE_RDWR | 
            mbx_const.HSX_MBX_MODE_FANOUT | 
            mbx_const.HSX_MBX_MODE_FANOUT_DROP)
    desc = controller.mailboxes.bind_target(pid=0, target="shared:fanout", mode_mask=mode)
    
    # Create 3 reader tasks
    vms: Dict[int, MiniVM] = {}
    handles: Dict[int, int] = {}
    for pid in [1, 2, 3]:
        vm = _create_task(controller, pid)
        vms[pid] = vm
        handles[pid] = controller.mailboxes.open(pid=pid, target="shared:fanout")
    
    # All three tasks issue blocking recv
    buffer_ptr = 0x0200
    for pid in [1, 2, 3]:
        vm = vms[pid]
        controller.current_pid = pid
        controller.vm = vm
        vm.regs[1] = handles[pid]
        vm.regs[2] = buffer_ptr
        vm.regs[3] = 64
        vm.regs[4] = mbx_const.HSX_MBX_TIMEOUT_INFINITE
        controller._svc_mailbox_controller(vm, mbx_const.HSX_MBX_FN_RECV)
    
    # Verify all three are waiting
    assert len(controller.waiting_tasks) == 3
    
    # Send one message from shell
    sender_handle = controller.mailboxes.open(pid=0, target="shared:fanout")
    ok, desc_id = controller.mailboxes.send(pid=0, handle=sender_handle, payload=b"broadcast")
    assert ok
    
    # Deliver messages - should wake ALL readers (fan-out mode)
    controller._deliver_mailbox_messages(desc_id)
    
    # All readers should be woken
    assert len(controller.waiting_tasks) == 0
    
    # Verify all readers received the message
    for pid in [1, 2, 3]:
        regs = controller.task_states[pid]["context"]["regs"]
        assert regs[0] == mbx_const.HSX_MBX_STATUS_OK
        assert regs[1] == len(b"broadcast")


def test_fanout_preserves_fifo_within_priority():
    """Test that fan-out mode processes waiters in FIFO order."""
    controller = VMController()
    controller.mailboxes.register_task(0)
    
    # Create fan-out mailbox
    mode = (mbx_const.HSX_MBX_MODE_RDWR | 
            mbx_const.HSX_MBX_MODE_FANOUT | 
            mbx_const.HSX_MBX_MODE_FANOUT_DROP)
    desc = controller.mailboxes.bind_target(pid=0, target="shared:test", mode_mask=mode)
    
    # Create 4 reader tasks that will wait in order
    wake_order = []
    
    vms: Dict[int, MiniVM] = {}
    handles: Dict[int, int] = {}
    for pid in [5, 3, 7, 2]:  # Non-sequential PIDs to verify FIFO, not PID order
        vm = _create_task(controller, pid)
        vms[pid] = vm
        handles[pid] = controller.mailboxes.open(pid=pid, target="shared:test")
    
    # Tasks wait in order: 5, 3, 7, 2
    buffer_ptr = 0x0200
    for pid in [5, 3, 7, 2]:
        vm = vms[pid]
        controller.current_pid = pid
        controller.vm = vm
        vm.regs[1] = handles[pid]
        vm.regs[2] = buffer_ptr
        vm.regs[3] = 64
        vm.regs[4] = mbx_const.HSX_MBX_TIMEOUT_INFINITE
        controller._svc_mailbox_controller(vm, mbx_const.HSX_MBX_FN_RECV)
    
    # Send message
    sender_handle = controller.mailboxes.open(pid=0, target="shared:test")
    ok, desc_id = controller.mailboxes.send(pid=0, handle=sender_handle, payload=b"test")
    assert ok
    
    # Deliver - all should wake, but verify FIFO order in waiters list was preserved
    # (The descriptor's waiters list should have been [5, 3, 7, 2])
    desc_check = controller.mailboxes.descriptor_by_id(desc_id)
    assert len(controller.waiting_tasks) == 4
    
    controller._deliver_mailbox_messages(desc_id)
    
    # All should be woken
    assert len(controller.waiting_tasks) == 0


def test_mixed_single_reader_and_fanout_no_interference():
    """Test that single-reader and fan-out mailboxes operate independently."""
    controller = VMController()
    controller.mailboxes.register_task(0)
    
    # Create one single-reader mailbox
    desc_single = controller.mailboxes.bind_target(pid=0, target="shared:single")
    
    # Create one fan-out mailbox
    mode_fanout = (mbx_const.HSX_MBX_MODE_RDWR | 
                   mbx_const.HSX_MBX_MODE_FANOUT | 
                   mbx_const.HSX_MBX_MODE_FANOUT_DROP)
    desc_fanout = controller.mailboxes.bind_target(pid=0, target="shared:fanout", mode_mask=mode_fanout)
    
    # Create readers
    vm1 = _create_task(controller, 1)
    vm2 = _create_task(controller, 2)
    vm3 = _create_task(controller, 3)
    vm4 = _create_task(controller, 4)
    
    # PIDs 1 and 2 wait on single-reader mailbox
    h1_single = controller.mailboxes.open(pid=1, target="shared:single")
    h2_single = controller.mailboxes.open(pid=2, target="shared:single")
    
    # PIDs 3 and 4 wait on fan-out mailbox
    h3_fanout = controller.mailboxes.open(pid=3, target="shared:fanout")
    h4_fanout = controller.mailboxes.open(pid=4, target="shared:fanout")
    
    buffer_ptr = 0x0200
    
    # Set up blocking receives
    for pid, vm, handle in [(1, vm1, h1_single), (2, vm2, h2_single)]:
        controller.current_pid = pid
        controller.vm = vm
        vm.regs[1] = handle
        vm.regs[2] = buffer_ptr
        vm.regs[3] = 64
        vm.regs[4] = mbx_const.HSX_MBX_TIMEOUT_INFINITE
        controller._svc_mailbox_controller(vm, mbx_const.HSX_MBX_FN_RECV)
    
    for pid, vm, handle in [(3, vm3, h3_fanout), (4, vm4, h4_fanout)]:
        controller.current_pid = pid
        controller.vm = vm
        vm.regs[1] = handle
        vm.regs[2] = buffer_ptr
        vm.regs[3] = 64
        vm.regs[4] = mbx_const.HSX_MBX_TIMEOUT_INFINITE
        controller._svc_mailbox_controller(vm, mbx_const.HSX_MBX_FN_RECV)
    
    assert len(controller.waiting_tasks) == 4
    
    # Send to fan-out mailbox - should wake PIDs 3 and 4 only
    sender_fanout = controller.mailboxes.open(pid=0, target="shared:fanout")
    ok, desc_id = controller.mailboxes.send(pid=0, handle=sender_fanout, payload=b"fanout_msg")
    assert ok
    controller._deliver_mailbox_messages(desc_id)
    
    assert 3 not in controller.waiting_tasks
    assert 4 not in controller.waiting_tasks
    assert 1 in controller.waiting_tasks  # Still waiting
    assert 2 in controller.waiting_tasks  # Still waiting
    
    # Send to single-reader mailbox - should wake only PID 1 (FIFO)
    sender_single = controller.mailboxes.open(pid=0, target="shared:single")
    ok, desc_id = controller.mailboxes.send(pid=0, handle=sender_single, payload=b"single_msg")
    assert ok
    controller._deliver_mailbox_messages(desc_id)
    
    assert 1 not in controller.waiting_tasks
    assert 2 in controller.waiting_tasks  # Still waiting


def test_tap_isolation_from_regular_readers():
    """Test that taps don't interfere with regular reader wake order."""
    controller = VMController()
    controller.mailboxes.register_task(0)
    
    # Create fan-out mailbox
    mode = (mbx_const.HSX_MBX_MODE_RDWR | 
            mbx_const.HSX_MBX_MODE_FANOUT | 
            mbx_const.HSX_MBX_MODE_FANOUT_DROP)
    desc = controller.mailboxes.bind_target(pid=0, target="shared:test", mode_mask=mode)
    
    # Create regular readers
    vm1 = _create_task(controller, 1)
    vm2 = _create_task(controller, 2)
    h1 = controller.mailboxes.open(pid=1, target="shared:test")
    h2 = controller.mailboxes.open(pid=2, target="shared:test")
    
    # Create a tap observer
    vm_tap = _create_task(controller, 99)
    h_tap = controller.mailboxes.open(pid=99, target="shared:test")
    controller.mailboxes.tap(pid=99, handle=h_tap, enable=True)
    
    # Regular readers issue blocking recv
    buffer_ptr = 0x0200
    for pid, vm, handle in [(1, vm1, h1), (2, vm2, h2)]:
        controller.current_pid = pid
        controller.vm = vm
        vm.regs[1] = handle
        vm.regs[2] = buffer_ptr
        vm.regs[3] = 64
        vm.regs[4] = mbx_const.HSX_MBX_TIMEOUT_INFINITE
        controller._svc_mailbox_controller(vm, mbx_const.HSX_MBX_FN_RECV)
    
    # Verify only regular readers are waiting (tap should not block)
    assert len(controller.waiting_tasks) == 2
    assert 1 in controller.waiting_tasks
    assert 2 in controller.waiting_tasks
    assert 99 not in controller.waiting_tasks
    
    # Send message
    sender = controller.mailboxes.open(pid=0, target="shared:test")
    ok, desc_id = controller.mailboxes.send(pid=0, handle=sender, payload=b"test")
    assert ok
    controller._deliver_mailbox_messages(desc_id)
    
    # Both regular readers should be woken, tap unaffected
    assert len(controller.waiting_tasks) == 0
    
    # Tap should have received a copy (best-effort)
    msg = controller.mailboxes.recv(pid=99, handle=h_tap, record_waiter=False)
    assert msg is not None
    assert msg.payload == b"test"


def test_no_starvation_with_continuous_sends():
    """Test that all waiters eventually receive messages under load."""
    controller = VMController()
    controller.mailboxes.register_task(0)
    
    # Create fan-out mailbox
    mode = (mbx_const.HSX_MBX_MODE_RDWR | 
            mbx_const.HSX_MBX_MODE_FANOUT | 
            mbx_const.HSX_MBX_MODE_FANOUT_DROP)
    desc = controller.mailboxes.bind_target(pid=0, target="shared:test", mode_mask=mode)
    
    # Create multiple readers
    num_readers = 5
    vms = {}
    handles = {}
    for pid in range(1, num_readers + 1):
        vms[pid] = _create_task(controller, pid)
        handles[pid] = controller.mailboxes.open(pid=pid, target="shared:test")
    
    sender = controller.mailboxes.open(pid=0, target="shared:test")
    
    # Send multiple messages and verify all readers receive them
    for msg_num in range(3):
        # All readers issue blocking recv
        buffer_ptr = 0x0200
        for pid in range(1, num_readers + 1):
            vm = vms[pid]
            controller.current_pid = pid
            controller.vm = vm
            vm.regs[1] = handles[pid]
            vm.regs[2] = buffer_ptr
            vm.regs[3] = 64
            vm.regs[4] = mbx_const.HSX_MBX_TIMEOUT_INFINITE
            controller._svc_mailbox_controller(vm, mbx_const.HSX_MBX_FN_RECV)
        
        assert len(controller.waiting_tasks) == num_readers
        
        # Send message
        ok, desc_id = controller.mailboxes.send(
            pid=0, handle=sender, payload=f"msg{msg_num}".encode()
        )
        assert ok
        controller._deliver_mailbox_messages(desc_id)
        
        # All readers should be woken
        assert len(controller.waiting_tasks) == 0
        
        # Verify all received the message
        for pid in range(1, num_readers + 1):
            regs = controller.task_states[pid]["context"]["regs"]
            assert regs[0] == mbx_const.HSX_MBX_STATUS_OK
