"""Tests for ValCmd SVC integration with VMController."""

import pytest
import sys
from pathlib import Path

# Add repo root to path
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from platforms.python.host_vm import VMController
from python.hsx_value_constants import (
    HSX_VAL_STATUS_OK,
    HSX_VAL_STATUS_ENOENT,
    HSX_VAL_FN_REGISTER,
    HSX_VAL_FN_LOOKUP,
    HSX_VAL_FN_GET,
    HSX_VAL_FN_SET,
)
from python.hsx_command_constants import (
    HSX_CMD_STATUS_OK,
    HSX_CMD_STATUS_ENOENT,
    HSX_CMD_FN_REGISTER,
    HSX_CMD_FN_LOOKUP,
    HSX_CMD_FN_CALL,
)


class TestValCmdSVCIntegration:
    """Test ValCmd SVC handlers in VMController."""
    
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
