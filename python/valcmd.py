"""Value and Command Registry Manager for HSX.

This module implements the value and command subsystem as specified in:
- main/04--Design/04.04--ValCmd.md
- main/05--Implementation/01--GapAnalysis/04--ValCmd/02--ImplementationPlan.md

The registry manages:
- Value entries (group_id, value_id, flags, auth_level, owner_pid, last_f16)
- Command entries (group_id, cmd_id, flags, auth_level, owner_pid, handler_ref)
- Descriptor chains (Group, Name, Unit, Range, Persist)
- String table for deduplicated strings
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any, Callable
from enum import IntEnum

from python.hsx_value_constants import (
    HSX_VAL_STATUS_OK,
    HSX_VAL_STATUS_ENOENT,
    HSX_VAL_STATUS_EPERM,
    HSX_VAL_STATUS_ENOSPC,
    HSX_VAL_STATUS_EINVAL,
    HSX_VAL_STATUS_EEXIST,
    HSX_VAL_STATUS_EBUSY,
    HSX_VAL_FLAG_RO,
    HSX_VAL_FLAG_PERSIST,
    HSX_VAL_FLAG_STICKY,
    HSX_VAL_FLAG_PIN,
    HSX_VAL_FLAG_BOOL,
    HSX_VAL_AUTH_PUBLIC,
    HSX_VAL_AUTH_USER,
    HSX_VAL_AUTH_ADMIN,
    HSX_VAL_AUTH_FACTORY,
    HSX_VAL_PERSIST_VOLATILE,
    HSX_VAL_PERSIST_LOAD,
    HSX_VAL_PERSIST_SAVE,
    HSX_VAL_DESC_GROUP,
    HSX_VAL_DESC_NAME,
    HSX_VAL_DESC_UNIT,
    HSX_VAL_DESC_RANGE,
    HSX_VAL_DESC_PERSIST,
    HSX_VAL_MAX_VALUES,
    HSX_VAL_STRING_TABLE_SIZE,
)

from python.hsx_command_constants import (
    HSX_CMD_STATUS_OK,
    HSX_CMD_STATUS_ENOENT,
    HSX_CMD_STATUS_EPERM,
    HSX_CMD_STATUS_ENOSPC,
    HSX_CMD_STATUS_EINVAL,
    HSX_CMD_STATUS_EEXIST,
    HSX_CMD_STATUS_ENOASYNC,
    HSX_CMD_STATUS_EFAIL,
    HSX_CMD_FLAG_PIN,
    HSX_CMD_FLAG_ASYNC,
    HSX_CMD_MAX_COMMANDS,
)


class DescriptorType(IntEnum):
    """Descriptor type tags."""
    GROUP = HSX_VAL_DESC_GROUP
    NAME = HSX_VAL_DESC_NAME
    UNIT = HSX_VAL_DESC_UNIT
    RANGE = HSX_VAL_DESC_RANGE
    PERSIST = HSX_VAL_DESC_PERSIST


@dataclass
class Descriptor:
    """Base descriptor class."""
    desc_type: DescriptorType
    next: Optional[Descriptor] = None


@dataclass
class GroupDescriptor(Descriptor):
    """Group descriptor providing group metadata."""
    group_id: int = 0
    group_name: str = ""

    def __init__(self, group_id: int = 0, group_name: str = "", next: Optional[Descriptor] = None):
        super().__init__(desc_type=DescriptorType.GROUP, next=next)
        self.group_id = group_id
        self.group_name = group_name


@dataclass
class NameDescriptor(Descriptor):
    """Name descriptor providing human-readable name."""
    value_name: str = ""

    def __init__(self, value_name: str = "", next: Optional[Descriptor] = None):
        super().__init__(desc_type=DescriptorType.NAME, next=next)
        self.value_name = value_name


@dataclass
class UnitDescriptor(Descriptor):
    """Unit descriptor with formatting and rate limiting."""
    unit: str = ""  # 4-character unit code (e.g., 'degC', 'km/h')
    epsilon: float = 0.0  # Minimum change threshold
    rate_ms: int = 0  # Minimum milliseconds between notifications

    def __init__(self, unit: str = "", epsilon: float = 0.0, rate_ms: int = 0, next: Optional[Descriptor] = None):
        super().__init__(desc_type=DescriptorType.UNIT, next=next)
        self.unit = unit
        self.epsilon = epsilon
        self.rate_ms = rate_ms


@dataclass
class RangeDescriptor(Descriptor):
    """Range descriptor with min/max/default values."""
    min_value: float = 0.0
    max_value: float = 0.0
    default_value: float = 0.0

    def __init__(self, min_value: float = 0.0, max_value: float = 0.0, default_value: float = 0.0, next: Optional[Descriptor] = None):
        super().__init__(desc_type=DescriptorType.RANGE, next=next)
        self.min_value = min_value
        self.max_value = max_value
        self.default_value = default_value


@dataclass
class PersistDescriptor(Descriptor):
    """Persistence descriptor with debounce and storage info."""
    debounce_ms: int = 0
    persist_addr: int = 0

    def __init__(self, debounce_ms: int = 0, persist_addr: int = 0, next: Optional[Descriptor] = None):
        super().__init__(desc_type=DescriptorType.PERSIST, next=next)
        self.debounce_ms = debounce_ms
        self.persist_addr = persist_addr


@dataclass
class ValueEntry:
    """Compact 8-byte value entry (runtime storage).
    
    Corresponds to hsx_val_entry in C header.
    """
    group_id: int
    value_id: int
    flags: int
    auth_level: int
    owner_pid: int
    last_f16: float  # IEEE 754 half-precision (stored as Python float)
    desc_head: Optional[Descriptor] = None
    
    # Additional runtime state (not in compact C structure)
    last_change_time: float = 0.0  # For rate limiting
    subscribers: List[Any] = field(default_factory=list)  # Mailbox subscriptions
    
    @property
    def oid(self) -> int:
        """Calculate Object ID: (group_id << 8) | value_id."""
        return (self.group_id << 8) | self.value_id
    
    @property
    def is_readonly(self) -> bool:
        """Check if value is read-only."""
        return bool(self.flags & HSX_VAL_FLAG_RO)
    
    @property
    def is_persistent(self) -> bool:
        """Check if value has persistence flag."""
        return bool(self.flags & HSX_VAL_FLAG_PERSIST)
    
    @property
    def requires_pin(self) -> bool:
        """Check if value requires PIN authentication."""
        return bool(self.flags & HSX_VAL_FLAG_PIN)


@dataclass
class CommandEntry:
    """Compact command entry (runtime storage).
    
    Corresponds to hsx_cmd_entry in C header.
    """
    group_id: int
    cmd_id: int
    flags: int
    auth_level: int
    owner_pid: int
    handler_ref: Optional[Callable] = None  # Callback function
    desc_head: Optional[Descriptor] = None
    
    @property
    def oid(self) -> int:
        """Calculate Object ID: (group_id << 8) | cmd_id."""
        return (self.group_id << 8) | self.cmd_id
    
    @property
    def requires_pin(self) -> bool:
        """Check if command requires PIN authentication."""
        return bool(self.flags & HSX_CMD_FLAG_PIN)
    
    @property
    def allows_async(self) -> bool:
        """Check if command allows async invocation."""
        return bool(self.flags & HSX_CMD_FLAG_ASYNC)


class StringTable:
    """Deduplicated null-terminated string storage.
    
    Optimizes memory by storing strings once and referencing by offset.
    """
    
    def __init__(self, capacity: int = HSX_VAL_STRING_TABLE_SIZE):
        self.capacity = capacity
        self._storage: List[str] = []
        self._offsets: Dict[str, int] = {}  # string -> offset mapping
        self._total_bytes = 0
    
    def insert(self, s: str) -> Optional[int]:
        """Insert string and return offset, or None if table full."""
        if s in self._offsets:
            return self._offsets[s]
        
        # Check if we have space (string + null terminator)
        bytes_needed = len(s.encode('utf-8')) + 1
        if self._total_bytes + bytes_needed > self.capacity:
            return None
        
        offset = len(self._storage)
        self._storage.append(s)
        self._offsets[s] = offset
        self._total_bytes += bytes_needed
        return offset
    
    def get(self, offset: int) -> Optional[str]:
        """Retrieve string by offset."""
        if 0 <= offset < len(self._storage):
            return self._storage[offset]
        return None
    
    @property
    def usage(self) -> Tuple[int, int]:
        """Return (used_bytes, total_bytes)."""
        return (self._total_bytes, self.capacity)


class ValCmdRegistry:
    """Value and Command Registry Manager.
    
    Provides the executive-side storage and lookup for values and commands.
    All operations are O(1) using OID-based dictionary lookup.
    """
    
    def __init__(self, 
                 max_values: int = HSX_VAL_MAX_VALUES,
                 max_commands: int = HSX_CMD_MAX_COMMANDS,
                 string_capacity: int = HSX_VAL_STRING_TABLE_SIZE):
        self.max_values = max_values
        self.max_commands = max_commands
        
        # OID -> Entry mappings
        self._values: Dict[int, ValueEntry] = {}
        self._commands: Dict[int, CommandEntry] = {}
        
        # Group descriptor deduplication (group_id -> GroupDescriptor)
        self._groups: Dict[int, GroupDescriptor] = {}
        
        # String table for names, units, help text
        self.strings = StringTable(string_capacity)
        
        # Event emission hook (set by executive)
        self._event_hook: Optional[Callable] = None
    
    def set_event_hook(self, hook: Callable):
        """Set the event emission hook for notifications."""
        self._event_hook = hook
    
    def _emit_event(self, event_type: str, **kwargs):
        """Emit an event if hook is configured."""
        if self._event_hook:
            self._event_hook(event_type, **kwargs)
    
    # Value operations
    
    def value_register(self, group_id: int, value_id: int, flags: int, 
                       auth_level: int, owner_pid: int, 
                       descriptors: Optional[Descriptor] = None) -> Tuple[int, int]:
        """Register a new value.
        
        Returns: (status, oid)
        """
        oid = (group_id << 8) | value_id
        
        # Check if already exists
        if oid in self._values:
            return (HSX_VAL_STATUS_EEXIST, 0)
        
        # Check capacity
        if len(self._values) >= self.max_values:
            return (HSX_VAL_STATUS_ENOSPC, 0)
        
        # Create value entry
        entry = ValueEntry(
            group_id=group_id,
            value_id=value_id,
            flags=flags,
            auth_level=auth_level,
            owner_pid=owner_pid,
            last_f16=0.0,
            desc_head=descriptors
        )
        
        self._values[oid] = entry
        
        # Emit registration event
        self._emit_event('value_registered', 
                        oid=oid, 
                        group_id=group_id, 
                        value_id=value_id,
                        owner_pid=owner_pid)
        
        return (HSX_VAL_STATUS_OK, oid)
    
    def value_lookup(self, group_id: int, value_id: int) -> Tuple[int, int]:
        """Lookup a value without creating it.
        
        Returns: (status, oid)
        """
        oid = (group_id << 8) | value_id
        
        if oid in self._values:
            return (HSX_VAL_STATUS_OK, oid)
        else:
            return (HSX_VAL_STATUS_ENOENT, 0)
    
    def value_get(self, oid: int, caller_pid: int, caller_auth: int = HSX_VAL_AUTH_PUBLIC) -> Tuple[int, float]:
        """Get a value.
        
        Returns: (status, f16_value)
        """
        if oid not in self._values:
            return (HSX_VAL_STATUS_ENOENT, 0.0)
        
        entry = self._values[oid]
        
        # Check permissions
        if entry.owner_pid != caller_pid and caller_auth < entry.auth_level:
            return (HSX_VAL_STATUS_EPERM, 0.0)
        
        return (HSX_VAL_STATUS_OK, entry.last_f16)
    
    def value_set(self, oid: int, f16_value: float, caller_pid: int, 
                  caller_auth: int = HSX_VAL_AUTH_PUBLIC,
                  current_time: float = 0.0) -> int:
        """Set a value.
        
        Returns: status
        """
        if oid not in self._values:
            return HSX_VAL_STATUS_ENOENT
        
        entry = self._values[oid]
        
        # Check permissions
        if entry.owner_pid != caller_pid and caller_auth < entry.auth_level:
            return HSX_VAL_STATUS_EPERM
        
        # Check read-only flag
        if entry.is_readonly:
            return HSX_VAL_STATUS_EPERM
        
        # Check rate limiting
        if current_time > 0 and entry.last_change_time > 0:
            # Find rate limit from unit descriptor
            rate_ms = 0
            desc = entry.desc_head
            while desc:
                if isinstance(desc, UnitDescriptor):
                    rate_ms = desc.rate_ms
                    break
                desc = desc.next
            
            if rate_ms > 0:
                elapsed_ms = (current_time - entry.last_change_time) * 1000
                if elapsed_ms < rate_ms:
                    return HSX_VAL_STATUS_EBUSY
        
        # Check epsilon threshold
        epsilon = 0.0
        desc = entry.desc_head
        while desc:
            if isinstance(desc, UnitDescriptor):
                epsilon = desc.epsilon
                break
            desc = desc.next
        
        if epsilon > 0 and abs(f16_value - entry.last_f16) < epsilon:
            # Change below threshold, ignore
            return HSX_VAL_STATUS_OK
        
        # Update value
        old_value = entry.last_f16
        entry.last_f16 = f16_value
        entry.last_change_time = current_time
        
        # Emit change event
        self._emit_event('value_changed',
                        oid=oid,
                        old_f16=old_value,
                        new_f16=f16_value,
                        owner_pid=entry.owner_pid)
        
        # Notify subscribers (mailbox notifications handled elsewhere)
        
        return HSX_VAL_STATUS_OK
    
    def value_list(self, group_filter: int = 0xFF, caller_pid: Optional[int] = None) -> List[int]:
        """List value OIDs matching filter.
        
        Args:
            group_filter: Group ID to filter (0xFF for all groups)
            caller_pid: If provided, only show values owned by this PID
        
        Returns: List of OIDs
        """
        result = []
        for oid, entry in self._values.items():
            # Apply group filter
            if group_filter != 0xFF and entry.group_id != group_filter:
                continue
            
            # Apply PID filter
            if caller_pid is not None and entry.owner_pid != caller_pid:
                continue
            
            result.append(oid)
        
        return result
    
    def value_subscribe(self, oid: int, mailbox_handle: Any) -> int:
        """Subscribe to value changes via mailbox.
        
        Returns: status
        """
        if oid not in self._values:
            return HSX_VAL_STATUS_ENOENT
        
        entry = self._values[oid]
        
        # Add subscriber if not already present
        if mailbox_handle not in entry.subscribers:
            entry.subscribers.append(mailbox_handle)
        
        return HSX_VAL_STATUS_OK
    
    def value_persist(self, oid: int, mode: int, caller_pid: int) -> int:
        """Toggle persistence mode for a value.
        
        Returns: status
        """
        if oid not in self._values:
            return HSX_VAL_STATUS_ENOENT
        
        entry = self._values[oid]
        
        # Check ownership
        if entry.owner_pid != caller_pid:
            return HSX_VAL_STATUS_EPERM
        
        # Update persist flag based on mode
        if mode == HSX_VAL_PERSIST_VOLATILE:
            entry.flags &= ~HSX_VAL_FLAG_PERSIST
        elif mode in (HSX_VAL_PERSIST_LOAD, HSX_VAL_PERSIST_SAVE):
            entry.flags |= HSX_VAL_FLAG_PERSIST
        else:
            return HSX_VAL_STATUS_EINVAL
        
        return HSX_VAL_STATUS_OK
    
    # Command operations
    
    def command_register(self, group_id: int, cmd_id: int, flags: int,
                        auth_level: int, owner_pid: int,
                        handler_ref: Optional[Callable] = None,
                        descriptors: Optional[Descriptor] = None) -> Tuple[int, int]:
        """Register a new command.
        
        Returns: (status, oid)
        """
        oid = (group_id << 8) | cmd_id
        
        # Check if already exists
        if oid in self._commands:
            return (HSX_CMD_STATUS_EEXIST, 0)
        
        # Check capacity
        if len(self._commands) >= self.max_commands:
            return (HSX_CMD_STATUS_ENOSPC, 0)
        
        # Create command entry
        entry = CommandEntry(
            group_id=group_id,
            cmd_id=cmd_id,
            flags=flags,
            auth_level=auth_level,
            owner_pid=owner_pid,
            handler_ref=handler_ref,
            desc_head=descriptors
        )
        
        self._commands[oid] = entry
        
        # Emit registration event
        self._emit_event('command_registered',
                        oid=oid,
                        group_id=group_id,
                        cmd_id=cmd_id,
                        owner_pid=owner_pid)
        
        return (HSX_CMD_STATUS_OK, oid)
    
    def command_lookup(self, group_id: int, cmd_id: int) -> Tuple[int, int]:
        """Lookup a command without creating it.
        
        Returns: (status, oid)
        """
        oid = (group_id << 8) | cmd_id
        
        if oid in self._commands:
            return (HSX_CMD_STATUS_OK, oid)
        else:
            return (HSX_CMD_STATUS_ENOENT, 0)
    
    def command_call(self, oid: int, caller_pid: int,
                    caller_auth: int = HSX_VAL_AUTH_PUBLIC) -> Tuple[int, Any]:
        """Invoke a command synchronously.
        
        Returns: (status, result)
        """
        if oid not in self._commands:
            return (HSX_CMD_STATUS_ENOENT, None)
        
        entry = self._commands[oid]
        
        # Check permissions
        if caller_auth < entry.auth_level:
            return (HSX_CMD_STATUS_EPERM, None)
        
        # Emit invoked event
        self._emit_event('cmd_invoked',
                        oid=oid,
                        caller_pid=caller_pid)
        
        # Invoke handler if present
        result = None
        status = HSX_CMD_STATUS_OK
        
        if entry.handler_ref:
            try:
                result = entry.handler_ref()
            except Exception as e:
                status = HSX_CMD_STATUS_EFAIL
                result = str(e)
        
        # Emit completed event
        self._emit_event('cmd_completed',
                        oid=oid,
                        status=status,
                        result=result)
        
        return (status, result)
    
    def command_list(self, group_filter: int = 0xFF, caller_pid: Optional[int] = None) -> List[int]:
        """List command OIDs matching filter.
        
        Args:
            group_filter: Group ID to filter (0xFF for all groups)
            caller_pid: If provided, only show commands owned by this PID
        
        Returns: List of OIDs
        """
        result = []
        for oid, entry in self._commands.items():
            # Apply group filter
            if group_filter != 0xFF and entry.group_id != group_filter:
                continue
            
            # Apply PID filter
            if caller_pid is not None and entry.owner_pid != caller_pid:
                continue
            
            result.append(oid)
        
        return result
    
    # Resource monitoring
    
    def get_stats(self) -> Dict[str, Any]:
        """Get registry statistics."""
        str_used, str_total = self.strings.usage
        
        return {
            'values': {
                'count': len(self._values),
                'capacity': self.max_values,
                'usage_pct': len(self._values) / self.max_values * 100 if self.max_values > 0 else 0
            },
            'commands': {
                'count': len(self._commands),
                'capacity': self.max_commands,
                'usage_pct': len(self._commands) / self.max_commands * 100 if self.max_commands > 0 else 0
            },
            'strings': {
                'used_bytes': str_used,
                'total_bytes': str_total,
                'usage_pct': str_used / str_total * 100 if str_total > 0 else 0
            }
        }
    
    def cleanup_pid(self, pid: int):
        """Clean up all values and commands owned by a terminated PID."""
        # Remove values owned by this PID
        oids_to_remove = [oid for oid, entry in self._values.items() if entry.owner_pid == pid]
        for oid in oids_to_remove:
            del self._values[oid]
        
        # Remove commands owned by this PID
        oids_to_remove = [oid for oid, entry in self._commands.items() if entry.owner_pid == pid]
        for oid in oids_to_remove:
            del self._commands[oid]
