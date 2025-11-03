"""Value and Command Registry Manager for HSX.

This module aligns the Python reference implementation with the packed layouts
defined in 04.04--ValCmd.md. All runtime state tracks the raw half-precision
values, descriptor offsets, and string table addresses that the forthcoming C
port will rely upon.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import struct
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple, Union

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
    HSX_VAL_FLAG_PIN,
    HSX_VAL_AUTH_PUBLIC,
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
    HSX_VAL_DESC_INVALID,
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
    HSX_CMD_DESC_NAME,
    HSX_CMD_DESC_INVALID,
)

# ---------------------------------------------------------------------------
# Utility conversions

_F16_STRUCT = struct.Struct("<e")


def float_to_f16(value: float) -> int:
    """Convert Python float to IEEE-754 half-precision bits."""
    try:
        packed = _F16_STRUCT.pack(float(value))
    except OverflowError:
        # Saturate to +/-inf
        return 0x7C00 if value > 0 else 0xFC00
    return int.from_bytes(packed, "little")


def f16_to_float(raw: int) -> float:
    """Convert IEEE-754 half-precision bits to Python float."""
    return _F16_STRUCT.unpack(int(raw & 0xFFFF).to_bytes(2, "little"))[0]


def encode_unit_code(unit: str) -> int:
    """Encode up to 4 ASCII characters into a 32-bit little-endian code."""
    raw = unit.encode("ascii", "ignore")[:4]
    padded = raw.ljust(4, b"\x00")
    return int.from_bytes(padded, "little")


def decode_unit_code(code: int) -> str:
    """Decode a 32-bit packed unit code back into a string."""
    return code.to_bytes(4, "little").rstrip(b"\x00").decode("ascii", "ignore")


def _memory_view(buffer: Union[bytes, bytearray, memoryview]) -> memoryview:
    return buffer if isinstance(buffer, memoryview) else memoryview(buffer)


def _read_uint16(memory: memoryview, offset: int) -> Optional[int]:
    if offset < 0 or offset + 1 >= len(memory):
        return None
    return int.from_bytes(memory[offset : offset + 2], "little")


def _read_c_string(memory: memoryview, offset: int) -> Optional[str]:
    if offset < 0 or offset >= len(memory):
        return None
    end = offset
    limit = len(memory)
    while end < limit and memory[end] != 0:
        end += 1
    if end == limit:
        return None
    return memory[offset:end].tobytes().decode("utf-8", "ignore")


# ---------------------------------------------------------------------------
# Legacy descriptor compatibility (used by existing tests)


class LegacyDescriptor:
    """Compatibility wrapper representing descriptor chains from earlier revisions."""

    desc_type: int
    next: Optional["LegacyDescriptor"]

    def __init__(self, next: Optional["LegacyDescriptor"] = None):
        self.next = next

    def _to_spec(self) -> Dict[str, Any]:
        raise NotImplementedError

    def to_spec_list(self) -> List[Dict[str, Any]]:
        specs: List[Dict[str, Any]] = []
        current: Optional["LegacyDescriptor"] = self
        while current:
            specs.append(current._to_spec())
            current = current.next
        return specs


class GroupDescriptor(LegacyDescriptor):
    def __init__(self, group_id: int = 0, group_name: str = "", next: Optional["LegacyDescriptor"] = None):
        super().__init__(next=next)
        self.group_id = group_id
        self.group_name = group_name

    def _to_spec(self) -> Dict[str, Any]:
        return {"type": "group", "name": self.group_name}


class NameDescriptor(LegacyDescriptor):
    def __init__(self, value_name: str = "", next: Optional["LegacyDescriptor"] = None):
        super().__init__(next=next)
        self.value_name = value_name

    def _to_spec(self) -> Dict[str, Any]:
        return {"type": "name", "name": self.value_name}


class UnitDescriptor(LegacyDescriptor):
    def __init__(self, unit: str = "", epsilon: float = 0.0, rate_ms: int = 0, next: Optional["LegacyDescriptor"] = None):
        super().__init__(next=next)
        self.unit = unit
        self.epsilon = epsilon
        self.rate_ms = rate_ms

    def _to_spec(self) -> Dict[str, Any]:
        return {"type": "unit", "unit": self.unit, "epsilon": self.epsilon, "rate_ms": self.rate_ms}


class RangeDescriptor(LegacyDescriptor):
    def __init__(
        self,
        min_value: float = 0.0,
        max_value: float = 0.0,
        default_value: Optional[float] = None,
        next: Optional["LegacyDescriptor"] = None,
    ):
        super().__init__(next=next)
        self.min_value = min_value
        self.max_value = max_value
        self.default_value = default_value

    def _to_spec(self) -> Dict[str, Any]:
        spec: Dict[str, Any] = {"type": "range", "min": self.min_value, "max": self.max_value}
        if self.default_value is not None:
            spec["default"] = self.default_value
        return spec


class PersistDescriptor(LegacyDescriptor):
    def __init__(self, persist_key: int = 0, debounce_ms: int = 0, next: Optional["LegacyDescriptor"] = None):
        super().__init__(next=next)
        self.persist_key = persist_key
        self.debounce_ms = debounce_ms

    def _to_spec(self) -> Dict[str, Any]:
        return {"type": "persist", "key": self.persist_key, "debounce_ms": self.debounce_ms}


class CommandNameDescriptor(LegacyDescriptor):
    def __init__(self, name: str = "", help_text: str = "", next: Optional["LegacyDescriptor"] = None):
        super().__init__(next=next)
        self.name = name
        self.help_text = help_text

    def _to_spec(self) -> Dict[str, Any]:
        return {"type": "name", "name": self.name, "help": self.help_text}


# ---------------------------------------------------------------------------
# String table support


class StringTable:
    """Deduplicated null-terminated string pool."""

    def __init__(self, capacity: int = HSX_VAL_STRING_TABLE_SIZE):
        self.capacity = capacity
        self._data = bytearray()
        self._offsets: Dict[str, int] = {}

    def insert(self, text: str) -> Optional[int]:
        """Insert string, returning byte offset or None if table full."""
        if text in self._offsets:
            return self._offsets[text]
        encoded = text.encode("utf-8")
        needed = len(encoded) + 1
        if len(self._data) + needed > self.capacity:
            return None
        offset = len(self._data)
        self._data.extend(encoded)
        self._data.append(0)
        self._offsets[text] = offset
        return offset

    def get(self, offset: int) -> Optional[str]:
        """Retrieve string by offset."""
        if offset < 0 or offset >= len(self._data):
            return None
        end = self._data.find(0, offset)
        if end == -1:
            end = len(self._data)
        return self._data[offset:end].decode("utf-8")

    @property
    def usage(self) -> Tuple[int, int]:
        return (len(self._data), self.capacity)


# ---------------------------------------------------------------------------
# Descriptor records and pool


@dataclass
class DescriptorRecord:
    desc_type: int
    next_offset: int


@dataclass
class GroupDescriptorRecord(DescriptorRecord):
    group_id: int
    name_offset: int


@dataclass
class NameDescriptorRecord(DescriptorRecord):
    name_offset: int


@dataclass
class UnitDescriptorRecord(DescriptorRecord):
    unit_code: int
    epsilon_raw: int
    rate_ms: int

    @property
    def epsilon(self) -> float:
        return f16_to_float(self.epsilon_raw)


@dataclass
class RangeDescriptorRecord(DescriptorRecord):
    min_raw: int
    max_raw: int

    @property
    def min_value(self) -> float:
        return f16_to_float(self.min_raw)

    @property
    def max_value(self) -> float:
        return f16_to_float(self.max_raw)


@dataclass
class PersistDescriptorRecord(DescriptorRecord):
    persist_key: int
    debounce_ms: int


@dataclass
class CommandNameDescriptorRecord(DescriptorRecord):
    name_offset: int
    help_offset: int


class DescriptorPool:
    """Manages descriptor storage and allocates 16-bit offsets."""

    _SIZES = {
        HSX_VAL_DESC_GROUP: 6,
        HSX_VAL_DESC_NAME: 6,
        HSX_VAL_DESC_UNIT: 12,
        HSX_VAL_DESC_RANGE: 8,
        HSX_VAL_DESC_PERSIST: 8,
        HSX_CMD_DESC_NAME: 8,
    }

    def __init__(self):
        self._records: Dict[int, DescriptorRecord] = {}
        self._next_offset = 0

    def allocate(self, record: DescriptorRecord) -> int:
        size = self._SIZES.get(record.desc_type)
        if size is None:
            raise ValueError(f"Unsupported descriptor type {record.desc_type:#04x}")
        offset = self._next_offset
        self._records[offset] = record
        self._next_offset += size
        return offset

    def get(self, offset: int) -> Optional[DescriptorRecord]:
        return self._records.get(offset)

    def iter_chain(self, offset: int) -> Iterable[DescriptorRecord]:
        current = offset
        while current not in (HSX_VAL_DESC_INVALID, HSX_CMD_DESC_INVALID):
            record = self._records.get(current)
            if record is None:
                break
            yield record
            current = record.next_offset


def _parse_value_descriptor_chain(memory: memoryview, ptr: int) -> Tuple[bool, List[Dict[str, Any]]]:
    if ptr in (0, HSX_VAL_DESC_INVALID):
        return True, []
    specs: List[Dict[str, Any]] = []
    visited: set[int] = set()
    current = ptr
    while current not in (HSX_VAL_DESC_INVALID, None):
        if current in visited or current + 1 >= len(memory):
            return False, []
        visited.add(current)
        desc_type = memory[current]
        if desc_type == HSX_VAL_DESC_GROUP:
            if current + 5 >= len(memory):
                return False, []
            group_id = memory[current + 1]
            next_ptr = _read_uint16(memory, current + 2)
            name_ptr = _read_uint16(memory, current + 4)
            if next_ptr is None or name_ptr is None:
                return False, []
            group_name = _read_c_string(memory, name_ptr) or ""
            specs.append({"type": "group", "group_id": group_id, "name": group_name})
        elif desc_type == HSX_VAL_DESC_NAME:
            if current + 5 >= len(memory):
                return False, []
            next_ptr = _read_uint16(memory, current + 2)
            name_ptr = _read_uint16(memory, current + 4)
            if next_ptr is None or name_ptr is None:
                return False, []
            value_name = _read_c_string(memory, name_ptr) or ""
            specs.append({"type": "name", "name": value_name})
        elif desc_type == HSX_VAL_DESC_UNIT:
            if current + 11 >= len(memory):
                return False, []
            next_ptr = _read_uint16(memory, current + 2)
            unit_code = int.from_bytes(memory[current + 4 : current + 8], "little")
            epsilon_raw = _read_uint16(memory, current + 8)
            rate_ms = _read_uint16(memory, current + 10)
            if next_ptr is None or epsilon_raw is None or rate_ms is None:
                return False, []
            specs.append(
                {
                    "type": "unit",
                    "unit": decode_unit_code(unit_code),
                    "epsilon": f16_to_float(epsilon_raw),
                    "rate_ms": rate_ms,
                }
            )
        elif desc_type == HSX_VAL_DESC_RANGE:
            if current + 7 >= len(memory):
                return False, []
            next_ptr = _read_uint16(memory, current + 2)
            min_raw = _read_uint16(memory, current + 4)
            max_raw = _read_uint16(memory, current + 6)
            if next_ptr is None or min_raw is None or max_raw is None:
                return False, []
            spec: Dict[str, Any] = {
                "type": "range",
                "min": f16_to_float(min_raw),
                "max": f16_to_float(max_raw),
            }
            specs.append(spec)
        elif desc_type == HSX_VAL_DESC_PERSIST:
            if current + 7 >= len(memory):
                return False, []
            next_ptr = _read_uint16(memory, current + 2)
            persist_key = _read_uint16(memory, current + 4)
            debounce_ms = _read_uint16(memory, current + 6)
            if next_ptr is None or persist_key is None or debounce_ms is None:
                return False, []
            specs.append({"type": "persist", "key": persist_key, "debounce_ms": debounce_ms})
        else:
            return False, []

        next_ptr = _read_uint16(memory, current + 2)
        if next_ptr is None or next_ptr == HSX_VAL_DESC_INVALID:
            break
        current = next_ptr
    return True, specs


def _parse_command_descriptor_chain(memory: memoryview, ptr: int) -> Tuple[bool, List[Dict[str, Any]]]:
    if ptr in (0, HSX_CMD_DESC_INVALID):
        return True, []
    specs: List[Dict[str, Any]] = []
    visited: set[int] = set()
    current = ptr
    while current not in (HSX_CMD_DESC_INVALID, None):
        if current in visited or current + 6 >= len(memory):
            return False, []
        visited.add(current)
        desc_type = memory[current]
        if desc_type != HSX_CMD_DESC_NAME:
            return False, []
        next_ptr = _read_uint16(memory, current + 2)
        name_ptr = _read_uint16(memory, current + 4)
        help_ptr = _read_uint16(memory, current + 6)
        if next_ptr is None or name_ptr is None or help_ptr is None:
            return False, []
        name = _read_c_string(memory, name_ptr) or ""
        help_text = _read_c_string(memory, help_ptr) or ""
        specs.append({"type": "name", "name": name, "help": help_text})
        if next_ptr == HSX_CMD_DESC_INVALID:
            break
        current = next_ptr
    return True, specs


# ---------------------------------------------------------------------------
# Registry entries


@dataclass
class ValueEntry:
    group_id: int
    value_id: int
    flags: int
    auth_level: int
    owner_pid: int
    last_f16_raw: int = 0
    desc_head: int = HSX_VAL_DESC_INVALID
    last_change_time: float = 0.0
    subscribers: List[Any] = field(default_factory=list)

    @property
    def oid(self) -> int:
        return (self.group_id << 8) | self.value_id

    @property
    def is_readonly(self) -> bool:
        return bool(self.flags & HSX_VAL_FLAG_RO)

    @property
    def is_persistent(self) -> bool:
        return bool(self.flags & HSX_VAL_FLAG_PERSIST)

    @property
    def requires_pin(self) -> bool:
        return bool(self.flags & HSX_VAL_FLAG_PIN)

    @property
    def last_value(self) -> float:
        return f16_to_float(self.last_f16_raw)

    def set_value(self, value: float) -> None:
        self.last_f16_raw = float_to_f16(value)


@dataclass
class CommandEntry:
    group_id: int
    cmd_id: int
    flags: int
    auth_level: int
    owner_pid: int
    handler_ref: int = 0
    desc_head: int = HSX_CMD_DESC_INVALID

    @property
    def oid(self) -> int:
        return (self.group_id << 8) | self.cmd_id

    @property
    def requires_pin(self) -> bool:
        return bool(self.flags & HSX_CMD_FLAG_PIN)

    @property
    def allows_async(self) -> bool:
        return bool(self.flags & HSX_CMD_FLAG_ASYNC)


# ---------------------------------------------------------------------------
# Registry implementation


class ValCmdRegistry:
    """Executive-side value and command registry."""

    def __init__(
        self,
        max_values: int = HSX_VAL_MAX_VALUES,
        max_commands: int = HSX_CMD_MAX_COMMANDS,
        string_capacity: int = HSX_VAL_STRING_TABLE_SIZE,
    ):
        self.max_values = max_values
        self.max_commands = max_commands
        self._values: Dict[int, ValueEntry] = {}
        self._commands: Dict[int, CommandEntry] = {}
        self._string_table = StringTable(string_capacity)
        self._descriptors = DescriptorPool()
        self._event_hook: Optional[Callable[..., None]] = None
        self._command_handlers: Dict[int, Callable[[], Any]] = {}
        self._next_handler_ref: int = 1

    # ------------------------------------------------------------------ utils

    def set_event_hook(self, hook: Callable[..., None]) -> None:
        self._event_hook = hook

    def _emit_event(self, event_type: str, **payload: Any) -> None:
        if self._event_hook:
            self._event_hook(event_type, **payload)

    def parse_value_descriptors_from_memory(
        self, memory: Union[bytes, bytearray, memoryview], head_ptr: int
    ) -> Tuple[bool, List[Dict[str, Any]]]:
        return _parse_value_descriptor_chain(_memory_view(memory), head_ptr)

    def parse_command_descriptors_from_memory(
        self, memory: Union[bytes, bytearray, memoryview], head_ptr: int
    ) -> Tuple[bool, List[Dict[str, Any]]]:
        return _parse_command_descriptor_chain(_memory_view(memory), head_ptr)

    # ---------------------------------------------------------- descriptor io

    def _allocate_value_descriptors(
        self, group_id: int, specs: Optional[Iterable[Dict[str, Any]]]
    ) -> Tuple[bool, int]:
        if not specs:
            return (True, HSX_VAL_DESC_INVALID)

        next_offset = HSX_VAL_DESC_INVALID
        for spec in reversed(list(specs)):
            dtype = spec.get("type")
            if dtype == "group":
                name_offset = self._string_table.insert(spec.get("name", ""))
                if name_offset is None:
                    return (False, HSX_VAL_DESC_INVALID)
                record = GroupDescriptorRecord(
                    desc_type=HSX_VAL_DESC_GROUP,
                    next_offset=next_offset,
                    group_id=group_id,
                    name_offset=name_offset,
                )
            elif dtype == "name":
                name_offset = self._string_table.insert(spec.get("name", ""))
                if name_offset is None:
                    return (False, HSX_VAL_DESC_INVALID)
                record = NameDescriptorRecord(
                    desc_type=HSX_VAL_DESC_NAME,
                    next_offset=next_offset,
                    name_offset=name_offset,
                )
            elif dtype == "unit":
                unit_code = encode_unit_code(spec.get("unit", ""))
                epsilon_raw = float_to_f16(spec.get("epsilon", 0.0))
                record = UnitDescriptorRecord(
                    desc_type=HSX_VAL_DESC_UNIT,
                    next_offset=next_offset,
                    unit_code=unit_code,
                    epsilon_raw=epsilon_raw,
                    rate_ms=int(spec.get("rate_ms", 0)),
                )
            elif dtype == "range":
                record = RangeDescriptorRecord(
                    desc_type=HSX_VAL_DESC_RANGE,
                    next_offset=next_offset,
                    min_raw=float_to_f16(spec.get("min", 0.0)),
                    max_raw=float_to_f16(spec.get("max", 0.0)),
                )
            elif dtype == "persist":
                record = PersistDescriptorRecord(
                    desc_type=HSX_VAL_DESC_PERSIST,
                    next_offset=next_offset,
                    persist_key=int(spec.get("key", 0)),
                    debounce_ms=int(spec.get("debounce_ms", 0)),
                )
            else:
                raise ValueError(f"unsupported value descriptor spec: {spec}")
            next_offset = self._descriptors.allocate(record)
        return (True, next_offset)

    def _allocate_command_descriptors(
        self, specs: Optional[Iterable[Dict[str, Any]]]
    ) -> Tuple[bool, int]:
        if not specs:
            return (True, HSX_CMD_DESC_INVALID)

        next_offset = HSX_CMD_DESC_INVALID
        for spec in reversed(list(specs)):
            dtype = spec.get("type")
            if dtype == "name":
                name_offset = self._string_table.insert(spec.get("name", ""))
                help_offset = self._string_table.insert(spec.get("help", ""))
                if name_offset is None or help_offset is None:
                    return (False, HSX_CMD_DESC_INVALID)
                record = CommandNameDescriptorRecord(
                    desc_type=HSX_CMD_DESC_NAME,
                    next_offset=next_offset,
                    name_offset=name_offset,
                    help_offset=help_offset,
                )
            else:
                raise ValueError(f"unsupported command descriptor spec: {spec}")
            next_offset = self._descriptors.allocate(record)
        return (True, next_offset)

    def _iter_value_descriptors(self, entry: ValueEntry) -> Iterable[DescriptorRecord]:
        return self._descriptors.iter_chain(entry.desc_head)

    def _iter_command_descriptors(self, entry: CommandEntry) -> Iterable[DescriptorRecord]:
        return self._descriptors.iter_chain(entry.desc_head)

    # ------------------------------------------------------------ value APIs

    def value_register(
        self,
        group_id: int,
        value_id: int,
        flags: int,
        auth_level: int,
        owner_pid: int,
        descriptors: Optional[Iterable[Dict[str, Any]]] = None,
    ) -> Tuple[int, int]:
        oid = (group_id << 8) | value_id
        if oid in self._values:
            return (HSX_VAL_STATUS_EEXIST, 0)
        if len(self._values) >= self.max_values:
            return (HSX_VAL_STATUS_ENOSPC, 0)

        specs: Optional[Iterable[Dict[str, Any]]]
        if isinstance(descriptors, LegacyDescriptor):
            specs = descriptors.to_spec_list()
        else:
            specs = descriptors

        ok, desc_head = self._allocate_value_descriptors(group_id, specs)
        if not ok:
            return (HSX_VAL_STATUS_ENOSPC, 0)
        entry = ValueEntry(
            group_id=group_id,
            value_id=value_id,
            flags=flags,
            auth_level=auth_level,
            owner_pid=owner_pid,
            desc_head=desc_head,
        )
        self._values[oid] = entry
        self._emit_event(
            "value_registered",
            oid=oid,
            group_id=group_id,
            value_id=value_id,
            owner_pid=owner_pid,
        )
        return (HSX_VAL_STATUS_OK, oid)

    def value_lookup(self, group_id: int, value_id: int) -> Tuple[int, int]:
        oid = (group_id << 8) | value_id
        if oid in self._values:
            return (HSX_VAL_STATUS_OK, oid)
        return (HSX_VAL_STATUS_ENOENT, 0)

    def value_get(self, oid: int, caller_pid: int, caller_auth: int = HSX_VAL_AUTH_PUBLIC) -> Tuple[int, float]:
        entry = self._values.get(oid)
        if entry is None:
            return (HSX_VAL_STATUS_ENOENT, 0.0)
        if entry.owner_pid != caller_pid and caller_auth < entry.auth_level:
            return (HSX_VAL_STATUS_EPERM, 0.0)
        return (HSX_VAL_STATUS_OK, entry.last_value)

    def value_set(
        self,
        oid: int,
        new_value: float,
        caller_pid: int,
        caller_auth: int = HSX_VAL_AUTH_PUBLIC,
        current_time: float = 0.0,
    ) -> int:
        entry = self._values.get(oid)
        if entry is None:
            return HSX_VAL_STATUS_ENOENT
        if entry.owner_pid != caller_pid and caller_auth < entry.auth_level:
            return HSX_VAL_STATUS_EPERM
        if entry.is_readonly:
            return HSX_VAL_STATUS_EPERM

        epsilon = 0.0
        rate_ms = 0
        for record in self._iter_value_descriptors(entry):
            if isinstance(record, UnitDescriptorRecord):
                epsilon = record.epsilon
                rate_ms = record.rate_ms
                break

        if current_time and rate_ms:
            elapsed_ms = (current_time - entry.last_change_time) * 1000
            if entry.last_change_time != 0.0 and elapsed_ms < rate_ms:
                return HSX_VAL_STATUS_EBUSY

        old_value = entry.last_value
        if epsilon and abs(new_value - old_value) < epsilon:
            return HSX_VAL_STATUS_OK

        entry.set_value(new_value)
        entry.last_change_time = current_time
        self._emit_event(
            "value_changed",
            oid=oid,
            old_f16=float_to_f16(old_value),
            new_f16=float_to_f16(new_value),
            owner_pid=entry.owner_pid,
        )
        return HSX_VAL_STATUS_OK

    def value_list(self, group_filter: int = 0xFF, caller_pid: Optional[int] = None) -> List[int]:
        oids: List[int] = []
        for oid, entry in self._values.items():
            if group_filter != 0xFF and entry.group_id != group_filter:
                continue
            if caller_pid is not None and entry.owner_pid != caller_pid:
                continue
            oids.append(oid)
        return oids

    def value_subscribe(self, oid: int, mailbox_handle: Any) -> int:
        entry = self._values.get(oid)
        if entry is None:
            return HSX_VAL_STATUS_ENOENT
        if mailbox_handle not in entry.subscribers:
            entry.subscribers.append(mailbox_handle)
        return HSX_VAL_STATUS_OK

    def get_value_subscribers(self, oid: int) -> List[Any]:
        entry = self._values.get(oid)
        if entry is None:
            return []
        return list(entry.subscribers)

    def get_value_entry(self, oid: int) -> Optional[ValueEntry]:
        return self._values.get(oid)

    def value_persist(self, oid: int, mode: int, caller_pid: int) -> int:
        entry = self._values.get(oid)
        if entry is None:
            return HSX_VAL_STATUS_ENOENT
        if entry.owner_pid != caller_pid:
            return HSX_VAL_STATUS_EPERM

        if mode == HSX_VAL_PERSIST_VOLATILE:
            entry.flags &= ~HSX_VAL_FLAG_PERSIST
            return HSX_VAL_STATUS_OK
        if mode not in (HSX_VAL_PERSIST_LOAD, HSX_VAL_PERSIST_SAVE):
            return HSX_VAL_STATUS_EINVAL

        entry.flags |= HSX_VAL_FLAG_PERSIST
        has_persist = any(isinstance(rec, PersistDescriptorRecord) for rec in self._iter_value_descriptors(entry))
        if not has_persist:
            record = PersistDescriptorRecord(
                desc_type=HSX_VAL_DESC_PERSIST,
                next_offset=entry.desc_head,
                persist_key=0,
                debounce_ms=0,
            )
            entry.desc_head = self._descriptors.allocate(record)
        return HSX_VAL_STATUS_OK

    # ----------------------------------------------------------- command APIs

    def command_register(
        self,
        group_id: int,
        cmd_id: int,
        flags: int,
        auth_level: int,
        owner_pid: int,
        handler_ref: Optional[Callable[[], Any]] = None,
        descriptors: Optional[Iterable[Dict[str, Any]]] = None,
    ) -> Tuple[int, int]:
        oid = (group_id << 8) | cmd_id
        if oid in self._commands:
            return (HSX_CMD_STATUS_EEXIST, 0)
        if len(self._commands) >= self.max_commands:
            return (HSX_CMD_STATUS_ENOSPC, 0)

        specs: Optional[Iterable[Dict[str, Any]]]
        if isinstance(descriptors, LegacyDescriptor):
            specs = descriptors.to_spec_list()
        else:
            specs = descriptors

        ok, desc_head = self._allocate_command_descriptors(specs)
        if not ok:
            return (HSX_CMD_STATUS_ENOSPC, 0)
        handler_index = 0
        if callable(handler_ref):
            handler_index = self._next_handler_ref
            self._command_handlers[handler_index] = handler_ref
            self._next_handler_ref += 1
        elif isinstance(handler_ref, int):
            handler_index = handler_ref

        entry = CommandEntry(
            group_id=group_id,
            cmd_id=cmd_id,
            flags=flags,
            auth_level=auth_level,
            owner_pid=owner_pid,
            handler_ref=handler_index,
            desc_head=desc_head,
        )
        self._commands[oid] = entry
        self._emit_event(
            "command_registered",
            oid=oid,
            group_id=group_id,
            cmd_id=cmd_id,
            owner_pid=owner_pid,
        )
        return (HSX_CMD_STATUS_OK, oid)

    def command_lookup(self, group_id: int, cmd_id: int) -> Tuple[int, int]:
        oid = (group_id << 8) | cmd_id
        if oid in self._commands:
            return (HSX_CMD_STATUS_OK, oid)
        return (HSX_CMD_STATUS_ENOENT, 0)

    def command_call(self, oid: int, caller_pid: int, caller_auth: int = HSX_VAL_AUTH_PUBLIC) -> Tuple[int, Any]:
        entry = self._commands.get(oid)
        if entry is None:
            return (HSX_CMD_STATUS_ENOENT, None)
        if caller_auth < entry.auth_level:
            return (HSX_CMD_STATUS_EPERM, None)

        self._emit_event("cmd_invoked", oid=oid, caller_pid=caller_pid)

        result: Any = None
        status = HSX_CMD_STATUS_OK
        handler = self._command_handlers.get(entry.handler_ref)
        if handler:
            try:
                result = handler()
            except Exception as exc:  # pylint: disable=broad-except
                status = HSX_CMD_STATUS_EFAIL
                result = str(exc)

        self._emit_event("cmd_completed", oid=oid, status=status, result=result)
        return (status, result)

    def command_call_async(self, oid: int, caller_pid: int, caller_auth: int = HSX_VAL_AUTH_PUBLIC) -> Tuple[int, Any]:
        entry = self._commands.get(oid)
        if entry is None:
            return (HSX_CMD_STATUS_ENOENT, None)
        if not entry.allows_async:
            return (HSX_CMD_STATUS_ENOASYNC, None)
        return self.command_call(oid, caller_pid, caller_auth)

    def command_list(self, group_filter: int = 0xFF, caller_pid: Optional[int] = None) -> List[int]:
        oids: List[int] = []
        for oid, entry in self._commands.items():
            if group_filter != 0xFF and entry.group_id != group_filter:
                continue
            if caller_pid is not None and entry.owner_pid != caller_pid:
                continue
            oids.append(oid)
        return oids

    def command_help_text(self, oid: int) -> Optional[str]:
        entry = self._commands.get(oid)
        if entry is None:
            return None
        for record in self._iter_command_descriptors(entry):
            if isinstance(record, CommandNameDescriptorRecord):
                return self._string_table.get(record.help_offset) or ""
        return None

    # --------------------------------------------------------- housekeeping

    def get_stats(self) -> Dict[str, Any]:
        used_bytes, total_bytes = self._string_table.usage
        return {
            "values": {
                "count": len(self._values),
                "capacity": self.max_values,
                "usage_pct": (len(self._values) / self.max_values * 100) if self.max_values else 0.0,
            },
            "commands": {
                "count": len(self._commands),
                "capacity": self.max_commands,
                "usage_pct": (len(self._commands) / self.max_commands * 100) if self.max_commands else 0.0,
            },
            "strings": {
                "used_bytes": used_bytes,
                "total_bytes": total_bytes,
                "usage_pct": (used_bytes / total_bytes * 100) if total_bytes else 0.0,
            },
        }

    def cleanup_pid(self, pid: int) -> None:
        value_oids = [oid for oid, entry in self._values.items() if entry.owner_pid == pid]
        for oid in value_oids:
            del self._values[oid]
        command_oids = [oid for oid, entry in self._commands.items() if entry.owner_pid == pid]
        for oid in command_oids:
            entry = self._commands.pop(oid)
            if entry.handler_ref in self._command_handlers:
                self._command_handlers.pop(entry.handler_ref, None)
