"""Tests for the ValCmd Registry Manager."""

import logging
from typing import Any, Callable, Tuple

import pytest
from python.valcmd import (
    ValCmdRegistry,
    ValueEntry,
    CommandEntry,
    GroupDescriptor,
    NameDescriptor,
    UnitDescriptor,
    RangeDescriptor,
    PersistDescriptor,
    CommandNameDescriptor,
    StringTable,
    float_to_f16,
    f16_to_float,
)
from python.hsx_value_constants import (
    HSX_VAL_STATUS_OK,
    HSX_VAL_STATUS_ENOENT,
    HSX_VAL_STATUS_EPERM,
    HSX_VAL_STATUS_ENOSPC,
    HSX_VAL_STATUS_EEXIST,
    HSX_VAL_STATUS_EBUSY,
    HSX_VAL_FLAG_RO,
    HSX_VAL_FLAG_PERSIST,
    HSX_VAL_AUTH_PUBLIC,
    HSX_VAL_AUTH_USER,
    HSX_VAL_DESC_INVALID,
    HSX_VAL_DESC_NAME,
)
from python.hsx_command_constants import (
    HSX_CMD_STATUS_OK,
    HSX_CMD_STATUS_ENOENT,
    HSX_CMD_STATUS_ENOSPC,
    HSX_CMD_STATUS_EEXIST,
    HSX_CMD_STATUS_EPERM,
    HSX_CMD_FLAG_ASYNC,
    HSX_CMD_FLAG_PIN,
    HSX_CMD_DESC_INVALID,
    HSX_CMD_DESC_NAME,
)


class TestStringTable:
    """Test string table deduplication."""
    
    def test_string_table_insert(self):
        """Test inserting strings into the table."""
        table = StringTable(capacity=100)
        
        offset1 = table.insert("hello")
        assert offset1 == 0
        
        offset2 = table.insert("world")
        assert offset2 == len("hello") + 1
        
        # Deduplication - same string returns same offset
        offset3 = table.insert("hello")
        assert offset3 == 0
    
    def test_string_table_get(self):
        """Test retrieving strings by offset."""
        table = StringTable(capacity=100)
        
        offset = table.insert("test")
        assert table.get(offset) == "test"
        assert table.get(999) is None
    
    def test_string_table_overflow(self):
        """Test string table capacity limits."""
        table = StringTable(capacity=10)
        
        # Small string should fit
        offset1 = table.insert("abc")
        assert offset1 is not None
        
        # Large string should fail
        offset2 = table.insert("x" * 100)
        assert offset2 is None
        
        # First string still accessible
        assert table.get(offset1) == "abc"
    
    def test_string_table_usage(self):
        """Test usage tracking."""
        table = StringTable(capacity=100)
        
        used, total = table.usage
        assert used == 0
        assert total == 100
        
        table.insert("hello")
        used, total = table.usage
        assert used > 0
        assert total == 100


class TestDescriptors:
    """Test descriptor chain building."""
    
    def test_group_descriptor(self):
        """Test group descriptor creation."""
        desc = GroupDescriptor(group_id=1, group_name="System")
        assert desc.group_id == 1
        assert desc.group_name == "System"
        assert desc.next is None
    
    def test_name_descriptor(self):
        """Test name descriptor creation."""
        desc = NameDescriptor(value_name="Temperature")
        assert desc.value_name == "Temperature"
    
    def test_unit_descriptor(self):
        """Test unit descriptor creation."""
        desc = UnitDescriptor(unit="degC", epsilon=0.1, rate_ms=100)
        assert desc.unit == "degC"
        assert desc.epsilon == 0.1
        assert desc.rate_ms == 100
    
    def test_range_descriptor(self):
        """Test range descriptor creation."""
        desc = RangeDescriptor(min_value=-40.0, max_value=125.0, default_value=20.0)
        assert desc.min_value == -40.0
        assert desc.max_value == 125.0
        assert desc.default_value == 20.0
    
    def test_descriptor_chain(self):
        """Test chaining multiple descriptors."""
        name = NameDescriptor(value_name="Temperature")
        unit = UnitDescriptor(unit="degC", epsilon=0.1)
        range_desc = RangeDescriptor(min_value=-40.0, max_value=125.0)
        
        name.next = unit
        unit.next = range_desc
        
        # Traverse chain
        assert name.next == unit
        assert unit.next == range_desc
        assert range_desc.next is None


class TestRegistryStats:
    """Tests for registry resource statistics and warnings."""

    def test_stats_high_water_tracking(self):
        registry = ValCmdRegistry(max_values=4, max_commands=3, string_capacity=128)

        for value_id in range(3):
            status, _ = registry.value_register(
                group_id=0,
                value_id=value_id,
                flags=0,
                auth_level=HSX_VAL_AUTH_PUBLIC,
                owner_pid=42,
                descriptors=[{"type": "name", "name": f"val_{value_id}"}],
            )
            assert status == HSX_VAL_STATUS_OK

        status, _ = registry.command_register(
            group_id=0,
            cmd_id=1,
            flags=0,
            auth_level=0,
            owner_pid=42,
            descriptors=[{"type": "name", "name": "cmd_1", "help": "noop"}],
        )
        assert status == HSX_CMD_STATUS_OK

        stats = registry.get_stats()
        assert stats["values"]["count"] == 3
        assert stats["values"]["high_water"] == 3
        assert pytest.approx(stats["values"]["usage_pct"], rel=1e-6) == 75.0
        assert pytest.approx(stats["values"]["high_water_pct"], rel=1e-6) == 75.0
        assert stats["commands"]["count"] == 1
        assert stats["commands"]["high_water"] == 1
        assert stats["strings"]["used_bytes"] > 0
        assert stats["strings"]["total_bytes"] == 128

    def test_value_warning_threshold_and_reset(self, caplog: pytest.LogCaptureFixture):
        caplog.set_level(logging.WARNING, logger="hsx.valcmd")
        registry = ValCmdRegistry(max_values=5, max_commands=2, string_capacity=128)

        for value_id in range(4):  # 4/5 -> 80% occupancy
            status, _ = registry.value_register(
                group_id=1,
                value_id=value_id,
                flags=0,
                auth_level=HSX_VAL_AUTH_PUBLIC,
                owner_pid=7,
                descriptors=[{"type": "name", "name": f"warn_val_{value_id}"}],
            )
            assert status == HSX_VAL_STATUS_OK

        assert any("value registry occupancy high" in rec.message for rec in caplog.records)

        registry.cleanup_pid(7)
        caplog.clear()

        for value_id in range(4):
            status, _ = registry.value_register(
                group_id=1,
                value_id=value_id,
                flags=0,
                auth_level=HSX_VAL_AUTH_PUBLIC,
                owner_pid=7,
                descriptors=[{"type": "name", "name": f"warn_val_{value_id}"}],
            )
            assert status == HSX_VAL_STATUS_OK

        assert any("value registry occupancy high" in rec.message for rec in caplog.records)

    def test_string_warning_threshold(self, caplog: pytest.LogCaptureFixture):
        caplog.set_level(logging.WARNING, logger="hsx.valcmd")
        registry = ValCmdRegistry(max_values=2, max_commands=1, string_capacity=20)

        status, _ = registry.value_register(
            group_id=0,
            value_id=0,
            flags=0,
            auth_level=HSX_VAL_AUTH_PUBLIC,
            owner_pid=1,
            descriptors=[{"type": "name", "name": "abcdefghijklmnop"}],
        )
        assert status == HSX_VAL_STATUS_OK

        assert any("string table usage high" in rec.message for rec in caplog.records)


class TestValueEntry:
    """Test value entry structure."""
    
    def test_value_entry_oid(self):
        """Test OID calculation."""
        entry = ValueEntry(
            group_id=0x12,
            value_id=0x34,
            flags=0,
            auth_level=HSX_VAL_AUTH_PUBLIC,
            owner_pid=100,
            last_f16_raw=float_to_f16(0.0),
        )
        assert entry.oid == 0x1234
    
    def test_value_entry_flags(self):
        """Test flag properties."""
        entry = ValueEntry(
            group_id=1,
            value_id=1,
            flags=HSX_VAL_FLAG_RO | HSX_VAL_FLAG_PERSIST,
            auth_level=HSX_VAL_AUTH_PUBLIC,
            owner_pid=100,
            last_f16_raw=float_to_f16(0.0),
        )
        assert entry.is_readonly is True
        assert entry.is_persistent is True
        assert entry.requires_pin is False


class TestCommandEntry:
    """Test command entry structure."""
    
    def test_command_entry_oid(self):
        """Test OID calculation."""
        entry = CommandEntry(
            group_id=0x12,
            cmd_id=0x34,
            flags=0,
            auth_level=HSX_VAL_AUTH_PUBLIC,
            owner_pid=100
        )
        assert entry.oid == 0x1234
    
    def test_command_entry_flags(self):
        """Test flag properties."""
        entry = CommandEntry(
            group_id=1,
            cmd_id=1,
            flags=HSX_CMD_FLAG_ASYNC,
            auth_level=HSX_VAL_AUTH_PUBLIC,
            owner_pid=100
        )
        assert entry.allows_async is True
        assert entry.requires_pin is False


class TestValCmdRegistry:
    """Test the main registry manager."""
    
    def test_registry_init(self):
        """Test registry initialization."""
        registry = ValCmdRegistry(max_values=256, max_commands=256)
        assert registry.max_values == 256
        assert registry.max_commands == 256
        
        stats = registry.get_stats()
        assert stats['values']['count'] == 0
        assert stats['commands']['count'] == 0

    def test_parse_value_descriptors_from_memory(self):
        registry = ValCmdRegistry()
        mem = bytearray(128)
        ptr = 0x10
        mem[ptr] = HSX_VAL_DESC_NAME
        mem[ptr + 1] = 0
        mem[ptr + 2:ptr + 4] = HSX_VAL_DESC_INVALID.to_bytes(2, 'little')
        mem[ptr + 4:ptr + 6] = (0x40).to_bytes(2, 'little')
        mem[0x40:0x45] = b'Temp\x00'

        ok, specs = registry.parse_value_descriptors_from_memory(mem, ptr)
        assert ok is True
        assert specs == [{'type': 'name', 'name': 'Temp'}]

    def test_parse_command_descriptors_from_memory(self):
        registry = ValCmdRegistry()
        mem = bytearray(160)
        ptr = 0x20
        mem[ptr] = HSX_CMD_DESC_NAME
        mem[ptr + 1] = 0
        mem[ptr + 2:ptr + 4] = HSX_CMD_DESC_INVALID.to_bytes(2, 'little')
        mem[ptr + 4:ptr + 6] = (0x60).to_bytes(2, 'little')
        mem[ptr + 6:ptr + 8] = (0x80).to_bytes(2, 'little')
        mem[0x60:0x65] = b'Reset\x00'
        mem[0x80:0x8c] = b'Reset motor\x00'

        ok, specs = registry.parse_command_descriptors_from_memory(mem, ptr)
        assert ok is True
        assert specs == [{'type': 'name', 'name': 'Reset', 'help': 'Reset motor'}]
    
    def test_value_register(self):
        """Test value registration."""
        registry = ValCmdRegistry()
        
        status, oid = registry.value_register(
            group_id=1,
            value_id=1,
            flags=0,
            auth_level=HSX_VAL_AUTH_PUBLIC,
            owner_pid=100
        )
        
        assert status == HSX_VAL_STATUS_OK
        assert oid == 0x0101
        
        # Duplicate registration should fail
        status, oid2 = registry.value_register(
            group_id=1,
            value_id=1,
            flags=0,
            auth_level=HSX_VAL_AUTH_PUBLIC,
            owner_pid=100
        )
        assert status == HSX_VAL_STATUS_EEXIST
    
    def test_value_lookup(self):
        """Test value lookup."""
        registry = ValCmdRegistry()
        
        # Lookup non-existent value
        status, oid = registry.value_lookup(1, 1)
        assert status == HSX_VAL_STATUS_ENOENT
        
        # Register and lookup
        registry.value_register(1, 1, 0, HSX_VAL_AUTH_PUBLIC, 100)
        status, oid = registry.value_lookup(1, 1)
        assert status == HSX_VAL_STATUS_OK
        assert oid == 0x0101
    
    def test_value_get_set(self):
        """Test getting and setting values."""
        registry = ValCmdRegistry()
        
        status, oid = registry.value_register(1, 1, 0, HSX_VAL_AUTH_PUBLIC, 100)
        assert status == HSX_VAL_STATUS_OK
        
        # Get initial value
        status, value = registry.value_get(oid, caller_pid=100)
        assert status == HSX_VAL_STATUS_OK
        assert value == 0.0
        
        # Set value
        status = registry.value_set(oid, 42.5, caller_pid=100)
        assert status == HSX_VAL_STATUS_OK
        
        # Get updated value
        status, value = registry.value_get(oid, caller_pid=100)
        assert status == HSX_VAL_STATUS_OK
        assert value == 42.5
    
    def test_value_permissions(self):
        """Test value permission checks."""
        registry = ValCmdRegistry()
        
        # Register value with user-level auth
        status, oid = registry.value_register(
            1, 1, 0, HSX_VAL_AUTH_USER, owner_pid=100
        )
        assert status == HSX_VAL_STATUS_OK
        
        # Owner can access
        status, value = registry.value_get(oid, caller_pid=100)
        assert status == HSX_VAL_STATUS_OK
        
        # Other PID with insufficient auth cannot access
        status, value = registry.value_get(oid, caller_pid=200, caller_auth=HSX_VAL_AUTH_PUBLIC)
        assert status == HSX_VAL_STATUS_EPERM
        
        # Other PID with sufficient auth can access
        status, value = registry.value_get(oid, caller_pid=200, caller_auth=HSX_VAL_AUTH_USER)
        assert status == HSX_VAL_STATUS_OK
    
    def test_value_readonly(self):
        """Test read-only value enforcement."""
        registry = ValCmdRegistry()
        
        status, oid = registry.value_register(
            1, 1, HSX_VAL_FLAG_RO, HSX_VAL_AUTH_PUBLIC, owner_pid=100
        )
        assert status == HSX_VAL_STATUS_OK
        
        # Setting read-only value should fail
        status = registry.value_set(oid, 42.0, caller_pid=100)
        assert status == HSX_VAL_STATUS_EPERM
    
    def test_value_list(self):
        """Test value enumeration."""
        registry = ValCmdRegistry()
        
        # Register values in different groups
        registry.value_register(1, 1, 0, HSX_VAL_AUTH_PUBLIC, 100)
        registry.value_register(1, 2, 0, HSX_VAL_AUTH_PUBLIC, 100)
        registry.value_register(2, 1, 0, HSX_VAL_AUTH_PUBLIC, 200)
        
        # List all values
        oids = registry.value_list(group_filter=0xFF)
        assert len(oids) == 3
        
        # List group 1 values
        oids = registry.value_list(group_filter=1)
        assert len(oids) == 2
        assert all(oid >> 8 == 1 for oid in oids)
        
        # List values owned by PID 100
        oids = registry.value_list(group_filter=0xFF, caller_pid=100)
        assert len(oids) == 2
    
    def test_value_capacity(self):
        """Test value registry capacity limits."""
        registry = ValCmdRegistry(max_values=2)
        
        # Fill registry
        status, _ = registry.value_register(1, 1, 0, HSX_VAL_AUTH_PUBLIC, 100)
        assert status == HSX_VAL_STATUS_OK
        
        status, _ = registry.value_register(1, 2, 0, HSX_VAL_AUTH_PUBLIC, 100)
        assert status == HSX_VAL_STATUS_OK
        
        # Registry full
        status, _ = registry.value_register(1, 3, 0, HSX_VAL_AUTH_PUBLIC, 100)
        assert status == HSX_VAL_STATUS_ENOSPC
    
    def test_command_register(self):
        """Test command registration."""
        registry = ValCmdRegistry()
        
        status, oid = registry.command_register(
            group_id=1,
            cmd_id=1,
            flags=0,
            auth_level=HSX_VAL_AUTH_PUBLIC,
            owner_pid=100
        )
        
        assert status == HSX_CMD_STATUS_OK
        assert oid == 0x0101
        
        # Duplicate registration should fail
        status, oid2 = registry.command_register(
            group_id=1,
            cmd_id=1,
            flags=0,
            auth_level=HSX_VAL_AUTH_PUBLIC,
            owner_pid=100
        )
        assert status == HSX_CMD_STATUS_EEXIST
    
    def test_command_lookup(self):
        """Test command lookup."""
        registry = ValCmdRegistry()
        
        # Lookup non-existent command
        status, oid = registry.command_lookup(1, 1)
        assert status == HSX_CMD_STATUS_ENOENT
        
        # Register and lookup
        registry.command_register(1, 1, 0, HSX_VAL_AUTH_PUBLIC, 100)
        status, oid = registry.command_lookup(1, 1)
        assert status == HSX_CMD_STATUS_OK
        assert oid == 0x0101
    
    def test_command_call(self):
        """Test command invocation."""
        registry = ValCmdRegistry()

        # Register command with handler
        call_count = [0]
        
        def handler():
            call_count[0] += 1
            return "success"
        
        status, oid = registry.command_register(
            1, 1, 0, HSX_VAL_AUTH_PUBLIC, 100, handler_ref=handler
        )
        assert status == HSX_CMD_STATUS_OK
        
        # Call command
        status, result = registry.command_call(oid, caller_pid=100)
        assert status == HSX_CMD_STATUS_OK
        assert result == "success"
        assert call_count[0] == 1

    def test_command_call_requires_owner(self):
        registry = ValCmdRegistry()
        status, oid = registry.command_register(1, 2, 0, HSX_VAL_AUTH_PUBLIC, 50)
        assert status == HSX_CMD_STATUS_OK
        status, _ = registry.command_call(oid, caller_pid=99)
        assert status == HSX_CMD_STATUS_EPERM

    def test_command_call_requires_pin_token(self):
        registry = ValCmdRegistry()
        registry.set_token_validator(lambda entry, token, pid: token == b"1234")
        call_count = [0]

        def handler():
            call_count[0] += 1
            return "ok"

        status, oid = registry.command_register(
            2,
            3,
            HSX_CMD_FLAG_PIN,
            HSX_VAL_AUTH_PUBLIC,
            owner_pid=7,
            handler_ref=handler,
        )
        assert status == HSX_CMD_STATUS_OK

        status, _ = registry.command_call(oid, caller_pid=7)
        assert status == HSX_CMD_STATUS_EPERM
        status, _ = registry.command_call(oid, caller_pid=7, token=b"bad")
        assert status == HSX_CMD_STATUS_EPERM
        status, result = registry.command_call(oid, caller_pid=7, token=b"1234")
        assert status == HSX_CMD_STATUS_OK
        assert result == "ok"
        assert call_count[0] == 1

    def test_command_call_async_uses_executor(self):
        registry = ValCmdRegistry()
        captured: list[Callable[[], None]] = []
        registry.set_async_executor(lambda fn: captured.append(fn))
        events: list[str] = []
        registry.set_event_hook(lambda event_type, **_: events.append(event_type))

        status, oid = registry.command_register(
            4,
            1,
            HSX_CMD_FLAG_ASYNC,
            HSX_VAL_AUTH_PUBLIC,
            owner_pid=88,
            handler_ref=lambda: 42,
        )
        assert status == HSX_CMD_STATUS_OK

        results: list[Tuple[int, Any]] = []
        status, _ = registry.command_call_async(
            oid,
            caller_pid=88,
            on_complete=lambda s, r: results.append((s, r)),
        )
        assert status == HSX_CMD_STATUS_OK
        assert len(captured) == 1
        captured[0]()
        assert results == [(HSX_CMD_STATUS_OK, 42)]
        assert events.count("cmd_invoked") == 1
        assert events.count("cmd_completed") == 1
    
    def test_command_list(self):
        """Test command enumeration."""
        registry = ValCmdRegistry()
        
        # Register commands in different groups
        registry.command_register(1, 1, 0, HSX_VAL_AUTH_PUBLIC, 100)
        registry.command_register(1, 2, 0, HSX_VAL_AUTH_PUBLIC, 100)
        registry.command_register(2, 1, 0, HSX_VAL_AUTH_PUBLIC, 200)
        
        # List all commands
        oids = registry.command_list(group_filter=0xFF)
        assert len(oids) == 3
        
        # List group 1 commands
        oids = registry.command_list(group_filter=1)
        assert len(oids) == 2
    
    def test_command_capacity(self):
        """Test command registry capacity limits."""
        registry = ValCmdRegistry(max_commands=2)
        
        # Fill registry
        status, _ = registry.command_register(1, 1, 0, HSX_VAL_AUTH_PUBLIC, 100)
        assert status == HSX_CMD_STATUS_OK
        
        status, _ = registry.command_register(1, 2, 0, HSX_VAL_AUTH_PUBLIC, 100)
        assert status == HSX_CMD_STATUS_OK
        
        # Registry full
        status, _ = registry.command_register(1, 3, 0, HSX_VAL_AUTH_PUBLIC, 100)
        assert status == HSX_CMD_STATUS_ENOSPC
    
    def test_event_emission(self):
        """Test event hook integration."""
        registry = ValCmdRegistry()
        events = []
        
        def event_hook(event_type, **kwargs):
            events.append((event_type, kwargs))
        
        registry.set_event_hook(event_hook)
        
        # Register value should emit event
        registry.value_register(1, 1, 0, HSX_VAL_AUTH_PUBLIC, 100)
        assert len(events) == 1
        event_type, payload = events[0]
        assert event_type == 'value_registered'
        assert payload['pid'] == 100
        assert payload['caller_pid'] == 100
        assert payload['group_id'] == 1
        assert payload['value_id'] == 1
        assert payload['oid'] == 0x0101

        # Set value should emit event
        oid = 0x0101
        registry.value_set(oid, 42.0, caller_pid=100)
        assert len(events) == 2
        event_type, payload = events[1]
        assert event_type == 'value_changed'
        assert payload['pid'] == 100
        assert payload['caller_pid'] == 100
        assert payload['group_id'] == 1
        assert payload['value_id'] == 1
        assert payload['new_f16'] == float_to_f16(42.0)
        assert payload['new_value'] == pytest.approx(42.0)
        assert payload['old_value'] == pytest.approx(0.0)

    def test_describe_value_and_command(self):
        registry = ValCmdRegistry()

        value_specs = [
            {"type": "group", "name": "telemetry"},
            {"type": "name", "name": "rpm"},
            {"type": "unit", "unit": "rpm", "epsilon": 0.1, "rate_ms": 50},
            {"type": "range", "min": 0.0, "max": 5000.0},
        ]
        status, oid = registry.value_register(1, 1, 0, HSX_VAL_AUTH_PUBLIC, 10, descriptors=value_specs)
        assert status == HSX_VAL_STATUS_OK
        registry.value_set(oid, 1234.5, caller_pid=10)
        value_info = registry.describe_value(oid)
        assert value_info is not None
        assert value_info["oid"] == oid
        assert value_info["name"] == "rpm"
        assert value_info["group_name"] == "telemetry"
        assert value_info["unit"] == "rpm"
        expected_value = f16_to_float(value_info["last_f16"])
        assert value_info["last_value"] == pytest.approx(expected_value)

        command_specs = [{"type": "name", "name": "reset", "help": "reset motor"}]
        status, cmd_oid = registry.command_register(2, 3, 0, HSX_VAL_AUTH_PUBLIC, 10, descriptors=command_specs)
        assert status == HSX_CMD_STATUS_OK
        command_info = registry.describe_command(cmd_oid)
        assert command_info is not None
        assert command_info["name"] == "reset"
        assert command_info["help"] == "reset motor"
    
    def test_cleanup_pid(self):
        """Test PID cleanup on task termination."""
        registry = ValCmdRegistry()
        
        # Register resources for PID 100
        registry.value_register(1, 1, 0, HSX_VAL_AUTH_PUBLIC, 100)
        registry.value_register(1, 2, 0, HSX_VAL_AUTH_PUBLIC, 100)
        registry.command_register(1, 1, 0, HSX_VAL_AUTH_PUBLIC, 100)
        
        # Register resources for PID 200
        registry.value_register(2, 1, 0, HSX_VAL_AUTH_PUBLIC, 200)
        
        # Verify initial state
        assert len(registry.value_list()) == 3
        assert len(registry.command_list()) == 1
        
        # Clean up PID 100
        registry.cleanup_pid(100)
        
        # Verify PID 100 resources removed
        assert len(registry.value_list()) == 1
        assert len(registry.command_list()) == 0
        
        # Verify PID 200 resources remain
        status, _ = registry.value_lookup(2, 1)
        assert status == HSX_VAL_STATUS_OK
    
    def test_get_stats(self):
        """Test registry statistics."""
        registry = ValCmdRegistry(max_values=10, max_commands=10)
        
        # Register some resources
        registry.value_register(1, 1, 0, HSX_VAL_AUTH_PUBLIC, 100)
        registry.value_register(1, 2, 0, HSX_VAL_AUTH_PUBLIC, 100)
        registry.command_register(1, 1, 0, HSX_VAL_AUTH_PUBLIC, 100)
        
        stats = registry.get_stats()
        
        assert stats['values']['count'] == 2
        assert stats['values']['capacity'] == 10
        assert stats['values']['usage_pct'] == 20.0
        
        assert stats['commands']['count'] == 1
        assert stats['commands']['capacity'] == 10
        assert stats['commands']['usage_pct'] == 10.0
