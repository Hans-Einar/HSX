"""Tests for ValCmd SVC integration with VMController."""

import pytest
import sys
from pathlib import Path
import struct
from typing import Tuple

# Add repo root to path
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from platforms.python.host_vm import VMController, MiniVM
from python.hsx_value_constants import (
    HSX_VAL_STATUS_OK,
    HSX_VAL_STATUS_ENOENT,
    HSX_VAL_FN_REGISTER,
    HSX_VAL_FN_LOOKUP,
    HSX_VAL_FN_GET,
    HSX_VAL_FN_SET,
    HSX_VAL_FN_LIST,
    HSX_VAL_FN_SUB,
    HSX_VAL_DESC_NAME,
    HSX_VAL_DESC_INVALID,
    HSX_VAL_AUTH_PUBLIC,
)
from python.hsx_command_constants import (
    HSX_CMD_STATUS_OK,
    HSX_CMD_STATUS_ENOENT,
    HSX_CMD_FN_REGISTER,
    HSX_CMD_FN_LOOKUP,
    HSX_CMD_FN_CALL,
    HSX_CMD_FN_CALL_ASYNC,
    HSX_CMD_FN_HELP,
    HSX_CMD_DESC_NAME,
    HSX_CMD_DESC_INVALID,
)


class TestValCmdSVCIntegration:
    """Test ValCmd SVC handlers in VMController."""

    def _make_controller(self) -> Tuple[VMController, MiniVM]:
        controller = VMController()
        vm = MiniVM(b"")
        controller.vm = vm
        controller.current_pid = 1
        vm.set_value_handler(lambda fn, vm=vm: controller._svc_value_controller(vm, fn))
        vm.set_command_handler(lambda fn, vm=vm: controller._svc_command_controller(vm, fn))
        return controller, vm
    
    def test_controller_has_valcmd_registry(self):
        """Test that VMController has valcmd registry."""
        controller = VMController()
        assert controller.valcmd is not None
        assert hasattr(controller.valcmd, 'value_register')
        assert hasattr(controller.valcmd, 'command_register')
    
    def test_valcmd_event_hook(self):
        """Test that ValCmd events are emitted."""
        controller = VMController()
        events = []
        
        # Create a mock VM with event collection
        class MockVM:
            def emit_event(self, event):
                events.append(event)
        
        controller.vm = MockVM()
        
        # Register a value through the registry
        status, oid = controller.valcmd.value_register(
            group_id=1, value_id=1, flags=0, auth_level=0, owner_pid=100
        )
        
        assert status == HSX_VAL_STATUS_OK
        assert len(events) > 0
        assert events[0]['type'] == 'value_registered'
    
    def test_value_register_through_registry(self):
        """Test value registration directly through registry."""
        controller = VMController()
        
        status, oid = controller.valcmd.value_register(
            group_id=0x12,
            value_id=0x34,
            flags=0,
            auth_level=0,
            owner_pid=100
        )
        
        assert status == HSX_VAL_STATUS_OK
        assert oid == 0x1234
        
        # Verify lookup works
        status, found_oid = controller.valcmd.value_lookup(0x12, 0x34)
        assert status == HSX_VAL_STATUS_OK
        assert found_oid == 0x1234
    
    def test_value_get_set_through_registry(self):
        """Test value get/set through registry."""
        controller = VMController()
        
        # Register value
        status, oid = controller.valcmd.value_register(
            group_id=1, value_id=1, flags=0, auth_level=0, owner_pid=100
        )
        assert status == HSX_VAL_STATUS_OK
        
        # Set value
        status = controller.valcmd.value_set(oid, 42.5, caller_pid=100)
        assert status == HSX_VAL_STATUS_OK
        
        # Get value
        status, value = controller.valcmd.value_get(oid, caller_pid=100)
        assert status == HSX_VAL_STATUS_OK
        assert value == 42.5
    
    def test_command_register_through_registry(self):
        """Test command registration directly through registry."""
        controller = VMController()
        
        status, oid = controller.valcmd.command_register(
            group_id=0x12,
            cmd_id=0x34,
            flags=0,
            auth_level=0,
            owner_pid=100
        )
        
        assert status == HSX_CMD_STATUS_OK
        assert oid == 0x1234
        
        # Verify lookup works
        status, found_oid = controller.valcmd.command_lookup(0x12, 0x34)
        assert status == HSX_CMD_STATUS_OK
        assert found_oid == 0x1234
    
    def test_command_call_through_registry(self):
        """Test command invocation through registry."""
        controller = VMController()
        
        # Register command with handler
        call_count = [0]
        def handler():
            call_count[0] += 1
            return 42
        
        status, oid = controller.valcmd.command_register(
            group_id=1,
            cmd_id=1,
            flags=0,
            auth_level=0,
            owner_pid=100,
            handler_ref=handler
        )
        assert status == HSX_CMD_STATUS_OK
        
        # Call command
        status, result = controller.valcmd.command_call(oid, caller_pid=100)
        assert status == HSX_CMD_STATUS_OK
        assert result == 42
        assert call_count[0] == 1

    def test_value_register_via_svc_with_descriptor(self):
        controller, vm = self._make_controller()
        name_ptr = 0x0200
        vm.mem[name_ptr:name_ptr + 6] = b"Temp\x00"
        desc_ptr = 0x0100
        vm.mem[desc_ptr] = HSX_VAL_DESC_NAME
        vm.mem[desc_ptr + 1] = 0
        vm.mem[desc_ptr + 2:desc_ptr + 4] = HSX_VAL_DESC_INVALID.to_bytes(2, 'little')
        vm.mem[desc_ptr + 4:desc_ptr + 6] = name_ptr.to_bytes(2, 'little')

        vm.regs[1] = 0x01
        vm.regs[2] = 0x02
        vm.regs[3] = 0x00
        vm.regs[4] = desc_ptr

        controller._svc_value_controller(vm, HSX_VAL_FN_REGISTER)
        assert vm.regs[0] == HSX_VAL_STATUS_OK
        status, oid = controller.valcmd.value_lookup(0x01, 0x02)
        assert status == HSX_VAL_STATUS_OK
        assert oid == 0x0102

    def test_value_get_set_via_svc(self):
        controller, vm = self._make_controller()
        controller.valcmd.value_register(0x01, 0x01, 0, HSX_VAL_AUTH_PUBLIC, owner_pid=1)

        vm.regs[1] = 0x0101
        vm.regs[2] = 0x3C00  # f16 = 1.0
        controller._svc_value_controller(vm, HSX_VAL_FN_SET)
        assert vm.regs[0] == HSX_VAL_STATUS_OK

        vm.regs[1] = 0x0101
        controller._svc_value_controller(vm, HSX_VAL_FN_GET)
        raw = vm.regs[0] & 0xFFFF
        assert raw == 0x3C00

    def test_value_list_via_svc_writes_buffer(self):
        controller, vm = self._make_controller()
        controller.valcmd.value_register(0x01, 0x01, 0, HSX_VAL_AUTH_PUBLIC, 1)
        controller.valcmd.value_register(0x01, 0x02, 0, HSX_VAL_AUTH_PUBLIC, 1)

        buffer_ptr = 0x0300
        vm.regs[1] = 0x01
        vm.regs[2] = buffer_ptr
        vm.regs[3] = 4

        controller._svc_value_controller(vm, HSX_VAL_FN_LIST)
        assert vm.regs[0] == HSX_VAL_STATUS_OK
        assert vm.regs[1] == 2
        oids = [int.from_bytes(vm.mem[buffer_ptr + i*2:buffer_ptr + i*2 + 2], 'little') for i in range(2)]
        assert oids == [0x0101, 0x0102]

    def test_value_subscribe_via_svc(self):
        controller, vm = self._make_controller()
        controller.mailboxes.bind_target(pid=1, target="app:notify")
        controller.valcmd.value_register(0x01, 0x01, 0, HSX_VAL_AUTH_PUBLIC, 1)
        target_ptr = 0x0400
        vm.mem[target_ptr:target_ptr + 12] = b"app:notify\x00"

        vm.regs[1] = 0x0101
        vm.regs[2] = target_ptr
        controller._svc_value_controller(vm, HSX_VAL_FN_SUB)
        assert vm.regs[0] == HSX_VAL_STATUS_OK
        handle = vm.regs[1]
        assert handle > 0

    def test_value_set_notifies_subscriber(self):
        controller, vm = self._make_controller()
        controller.mailboxes.bind_target(pid=1, target="app:notify")
        controller.valcmd.value_register(0x01, 0x01, 0, HSX_VAL_AUTH_PUBLIC, 1)
        target_ptr = 0x0420
        vm.mem[target_ptr:target_ptr + 12] = b"app:notify\x00"
        vm.regs[1] = 0x0101
        vm.regs[2] = target_ptr
        controller._svc_value_controller(vm, HSX_VAL_FN_SUB)
        handle = vm.regs[1]

        vm.regs[1] = 0x0101
        vm.regs[2] = 0x3C00  # f16 = 1.0
        controller._svc_value_controller(vm, HSX_VAL_FN_SET)

        msg = controller.mailboxes.recv(pid=1, handle=handle, record_waiter=False)
        assert msg is not None
        oid, raw = struct.unpack_from("<HH", msg.payload)
        assert oid == 0x0101
        assert raw == 0x3C00

    def test_command_register_and_help_via_svc(self):
        controller, vm = self._make_controller()
        controller.mailboxes.bind_target(pid=1, target="app:cmd")
        name_ptr = 0x0500
        help_ptr = 0x0520
        vm.mem[name_ptr:name_ptr + 6] = b"Reset\x00"
        vm.mem[help_ptr:help_ptr + 12] = b"Reset motor\x00"
        desc_ptr = 0x0480
        vm.mem[desc_ptr] = HSX_CMD_DESC_NAME
        vm.mem[desc_ptr + 1] = 0
        vm.mem[desc_ptr + 2:desc_ptr + 4] = HSX_CMD_DESC_INVALID.to_bytes(2, 'little')
        vm.mem[desc_ptr + 4:desc_ptr + 6] = name_ptr.to_bytes(2, 'little')
        vm.mem[desc_ptr + 6:desc_ptr + 8] = help_ptr.to_bytes(2, 'little')

        vm.regs[1] = 0x01
        vm.regs[2] = 0x01
        vm.regs[3] = 0x00
        vm.regs[4] = desc_ptr
        controller._svc_command_controller(vm, HSX_CMD_FN_REGISTER)
        assert vm.regs[0] == HSX_CMD_STATUS_OK
        oid = vm.regs[1]

        out_ptr = 0x0600
        vm.regs[1] = oid
        vm.regs[2] = out_ptr
        vm.regs[3] = 16
        controller._svc_command_controller(vm, HSX_CMD_FN_HELP)
        assert vm.regs[0] == HSX_CMD_STATUS_OK
        assert vm.regs[1] == len("Reset motor")
        text = vm.mem[out_ptr:out_ptr + vm.regs[1]].decode('utf-8')
        assert text == "Reset motor"

    def test_command_call_async_posts_mailbox(self):
        controller, vm = self._make_controller()
        controller.mailboxes.bind_target(pid=1, target="app:cmd")

        def handler():
            return 7

        controller.valcmd.command_register(0x01, 0x01, 0, HSX_VAL_AUTH_PUBLIC, 1, handler_ref=handler)

        target_ptr = 0x0640
        vm.mem[target_ptr:target_ptr + 8] = b"app:cmd\x00"
        vm.regs[1] = 0x0101
        vm.regs[3] = target_ptr
        controller._svc_command_controller(vm, HSX_CMD_FN_CALL_ASYNC)
        assert vm.regs[0] == HSX_CMD_STATUS_OK
        handle = vm.regs[1]
        msg = controller.mailboxes.recv(pid=1, handle=handle, record_waiter=False)
        assert msg is not None
        data = msg.payload
        oid, status = struct.unpack_from("<HH", data)
        assert oid == 0x0101
        assert status == HSX_CMD_STATUS_OK
    
    def test_valcmd_cleanup_on_pid_termination(self):
        """Test that valcmd cleans up on PID termination."""
        controller = VMController()
        
        # Register resources for PID 100
        controller.valcmd.value_register(1, 1, 0, 0, 100)
        controller.valcmd.value_register(1, 2, 0, 0, 100)
        controller.valcmd.command_register(1, 1, 0, 0, 100)
        
        # Register resources for PID 200
        controller.valcmd.value_register(2, 1, 0, 0, 200)
        
        # Verify initial state
        assert len(controller.valcmd.value_list()) == 3
        assert len(controller.valcmd.command_list()) == 1
        
        # Clean up PID 100
        controller.valcmd.cleanup_pid(100)
        
        # Verify PID 100 resources removed
        assert len(controller.valcmd.value_list()) == 1
        assert len(controller.valcmd.command_list()) == 0
        
        # Verify PID 200 resources remain
        status, _ = controller.valcmd.value_lookup(2, 1)
        assert status == HSX_VAL_STATUS_OK
    
    def test_valcmd_stats(self):
        """Test valcmd statistics reporting."""
        controller = VMController()
        
        # Register some resources
        controller.valcmd.value_register(1, 1, 0, 0, 100)
        controller.valcmd.value_register(1, 2, 0, 0, 100)
        controller.valcmd.command_register(1, 1, 0, 0, 100)
        
        stats = controller.valcmd.get_stats()
        
        assert stats['values']['count'] == 2
        assert stats['commands']['count'] == 1
        assert stats['values']['usage_pct'] > 0
        assert stats['commands']['usage_pct'] > 0
