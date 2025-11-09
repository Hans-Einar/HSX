"""Runtime cache helpers for hsxdbg."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Sequence

from .events import (
    BaseEvent,
    DebugBreakEvent,
    EventBus,
    EventSubscription,
    TraceStepEvent,
    WatchUpdateEvent,
)


def _to_int(value: Any) -> Optional[int]:
    try:
        if value is None:
            return None
        return int(value) & 0xFFFFFFFF
    except (TypeError, ValueError):
        return None


def _now() -> float:
    return time.time()


@dataclass
class RegisterState:
    """Register snapshot (R0-R15 plus PC/SP/PSW)."""

    registers: Dict[str, int]
    pc: Optional[int]
    sp: Optional[int]
    psw: Optional[int]
    timestamp: float = field(default_factory=_now)

    def as_list(self) -> List[int]:
        return [self.registers.get(f"R{i}", 0) for i in range(16)]


@dataclass
class MemoryBlock:
    """Cached block of task memory."""

    base: int
    data: bytes
    readonly: bool = True
    timestamp: float = field(default_factory=_now)

    @property
    def end(self) -> int:
        return self.base + len(self.data)


@dataclass
class StackFrame:
    index: int
    pc: Optional[int]
    sp: Optional[int]
    fp: Optional[int]
    symbol: Optional[str] = None
    func_name: Optional[str] = None
    func_addr: Optional[int] = None
    func_offset: Optional[int] = None
    line: Optional[int] = None
    file: Optional[str] = None


@dataclass
class WatchValue:
    watch_id: int
    expr: str
    length: int
    value: str
    old_value: Optional[str] = None
    address: Optional[int] = None
    location: Optional[str] = None
    timestamp: float = field(default_factory=_now)


@dataclass
class MailboxDescriptor:
    name: str
    owner: Optional[int]
    capacity: Optional[int]
    mode: Optional[int]
    flags: Optional[int]
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RuntimeCache:
    """Aggregates debugger state that can be served without RPCs."""

    registers: Dict[int, RegisterState] = field(default_factory=dict)
    memory: Dict[int, Dict[int, MemoryBlock]] = field(default_factory=dict)
    callstacks: Dict[int, List[StackFrame]] = field(default_factory=dict)
    watches: Dict[int, Dict[int, WatchValue]] = field(default_factory=dict)
    mailboxes: Dict[int, Dict[str, MailboxDescriptor]] = field(default_factory=dict)
    symbols: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    instructions: Dict[int, Dict[str, Any]] = field(default_factory=dict)

    # ------------------------------------------------------------------
    # Register snapshots
    # ------------------------------------------------------------------
    def update_registers(
        self,
        pid: int,
        regs: Mapping[str, Any] | Sequence[Any],
        *,
        pc: Optional[int] = None,
        sp: Optional[int] = None,
        psw: Optional[int] = None,
    ) -> RegisterState:
        """Store a register snapshot. Accepts dicts or R0..R15 sequences."""

        reg_map: Dict[str, int] = {}
        if isinstance(regs, Mapping):
        for idx in range(16):
            raw_value = self._lookup_reg_value(regs, idx)
            reg_map[f"R{idx}"] = _to_int(raw_value) or 0
        pc = _to_int(pc if pc is not None else (regs.get("PC") or regs.get("pc")))
            sp = _to_int(sp if sp is not None else (regs.get("SP") or regs.get("sp")))
            psw = _to_int(psw if psw is not None else (regs.get("PSW") or regs.get("psw")))
        else:
            seq = list(regs)
            for idx in range(16):
                value = seq[idx] if idx < len(seq) else 0
                reg_map[f"R{idx}"] = _to_int(value) or 0
            pc = _to_int(pc)
            sp = _to_int(sp)
            psw = _to_int(psw)
        state = RegisterState(registers=reg_map, pc=pc, sp=sp, psw=psw)
        self.registers[pid] = state
        return state

    def get_registers(self, pid: int) -> Optional[RegisterState]:
        return self.registers.get(pid)

    def query_registers(self, pid: int, register: str) -> Optional[int]:
        state = self.get_registers(pid)
        if not state:
            return None
        name = register.upper()
        if name in {"PC", "SP", "PSW"}:
            return getattr(state, name.lower())
        if name.startswith("R"):
            try:
                idx = int(name[1:])
                key = f"R{idx}"
                return state.registers.get(key)
            except ValueError:
                return None
        return state.registers.get(name)

    @staticmethod
    def _lookup_reg_value(regs: Mapping[str, Any], idx: int) -> Any:
        candidates = [
            f"R{idx}",
            f"r{idx}",
            f"R{idx:02d}",
            f"r{idx:02d}",
        ]
        for key in candidates:
            if key in regs:
                value = regs.get(key)
                if value is not None:
                    return value
        return None

    # ------------------------------------------------------------------
    # Memory caching
    # ------------------------------------------------------------------
    def cache_memory(self, pid: int, base: int, data: bytes, *, readonly: bool = True) -> MemoryBlock:
        block = MemoryBlock(base=base & 0xFFFFFFFF, data=bytes(data), readonly=readonly)
        self.memory.setdefault(pid, {})[block.base] = block
        return block

    def read_memory(self, pid: int, addr: int, length: int) -> Optional[bytes]:
        pid_blocks = self.memory.get(pid)
        if not pid_blocks:
            return None
        for block in pid_blocks.values():
            if block.base <= addr and (addr + length) <= block.end:
                offset = addr - block.base
                return block.data[offset : offset + length]
        return None

    def query_memory(self, pid: int, addr: int, length: int, *, fallback: Optional[Callable[[int, int], Optional[bytes]]] = None) -> Optional[bytes]:
        data = self.read_memory(pid, addr, length)
        if data is not None:
            return data
        if fallback:
            data = fallback(addr, length)
            if data is not None:
                self.cache_memory(pid, addr, data)
        return data

    # ------------------------------------------------------------------
    # Stack frames
    # ------------------------------------------------------------------
    def update_call_stack(self, pid: int, frames: Iterable[Mapping[str, Any]]) -> List[StackFrame]:
        normalized: List[StackFrame] = []
        for idx, frame in enumerate(frames):
            normalized.append(
                StackFrame(
                    index=idx,
                    pc=_to_int(frame.get("pc")),
                    sp=_to_int(frame.get("sp")),
                    fp=_to_int(frame.get("fp")),
                    symbol=frame.get("symbol") or frame.get("func_name"),
                    func_name=frame.get("func_name"),
                    func_addr=_to_int(frame.get("func_addr")),
                    func_offset=_to_int(frame.get("func_offset")),
                    line=_to_int(frame.get("line")) or frame.get("line_num"),
                    file=frame.get("file"),
                )
            )
        self.callstacks[pid] = normalized
        return normalized

    def get_call_stack(self, pid: int) -> List[StackFrame]:
        return list(self.callstacks.get(pid, []))

    def query_call_stack(self, pid: int, *, fallback: Optional[Callable[[], Optional[List[Mapping[str, Any]]]]] = None) -> List[StackFrame]:
        stack = self.get_call_stack(pid)
        if stack:
            return stack
        if fallback:
            frames = fallback() or []
            return self.update_call_stack(pid, frames)
        return []

    # ------------------------------------------------------------------
    # Watch values
    # ------------------------------------------------------------------
    def update_watch(self, pid: int, watch: Mapping[str, Any]) -> WatchValue:
        watch_id = int(watch.get("id") or watch.get("watch_id"))
        value = str(watch.get("value") or watch.get("new") or "")
        old = watch.get("old") or watch.get("previous")
        entry = WatchValue(
            watch_id=watch_id,
            expr=str(watch.get("expr") or ""),
            length=int(watch.get("length") or len(value) // 2 or 0),
            value=value,
            old_value=old,
            address=_to_int(watch.get("address")),
            location=watch.get("location"),
        )
        self.watches.setdefault(pid, {})[watch_id] = entry
        return entry

    def get_watch(self, pid: int, watch_id: int) -> Optional[WatchValue]:
        return self.watches.get(pid, {}).get(watch_id)

    def iter_watches(self, pid: int) -> List[WatchValue]:
        return list(self.watches.get(pid, {}).values())

    def query_watches(self, pid: int, *, fallback: Optional[Callable[[], Optional[Iterable[Mapping[str, Any]]]]] = None) -> List[WatchValue]:
        cached = self.iter_watches(pid)
        if cached:
            return cached
        if fallback:
            data = fallback() or []
            for record in data:
                self.update_watch(pid, record)
            return self.iter_watches(pid)
        return []

    # ------------------------------------------------------------------
    # Mailbox descriptors
    # ------------------------------------------------------------------
    def update_mailboxes(self, pid: int, descriptors: Iterable[Mapping[str, Any]]) -> Dict[str, MailboxDescriptor]:
        entries: Dict[str, MailboxDescriptor] = {}
        for desc in descriptors:
            name = str(desc.get("name") or desc.get("target") or "")
            if not name:
                continue
            entries[name] = MailboxDescriptor(
                name=name,
                owner=_to_int(desc.get("owner")),
                capacity=_to_int(desc.get("capacity")),
                mode=_to_int(desc.get("mode")),
                flags=_to_int(desc.get("flags")),
                metadata={k: v for k, v in desc.items() if k not in {"name", "target", "owner", "capacity", "mode", "flags"}},
            )
        self.mailboxes[pid] = entries
        return entries

    def list_mailboxes(self, pid: int) -> List[MailboxDescriptor]:
        return list(self.mailboxes.get(pid, {}).values())

    # ------------------------------------------------------------------
    # Symbols / instructions helpers
    # ------------------------------------------------------------------
    def store_instruction(self, pc: int, meta: Mapping[str, Any]) -> None:
        self.instructions[int(pc) & 0xFFFFFFFF] = dict(meta)

    def lookup_instruction(self, pc: int) -> Optional[Dict[str, Any]]:
        return self.instructions.get(int(pc) & 0xFFFFFFFF)

    def seed_symbols(self, symbols: Mapping[str, Dict[str, Any]]) -> None:
        self.symbols = dict(symbols)

    # ------------------------------------------------------------------
    # Bulk helpers
    # ------------------------------------------------------------------
    def apply_event(self, event: BaseEvent) -> None:
        pid = event.pid
        if pid is None:
            return
        if isinstance(event, TraceStepEvent):
            regs = event.regs or []
            self.update_registers(pid, regs, pc=event.pc, psw=event.flags)
        elif isinstance(event, WatchUpdateEvent):
            payload = {
                "id": event.watch_id or event.data.get("watch_id"),
                "expr": event.expr or event.data.get("expr") or "",
                "length": event.length or event.data.get("length") or 0,
                "value": event.new_value or event.data.get("new") or "",
                "old": event.old_value or event.data.get("old"),
                "address": event.address or event.data.get("address"),
                "location": event.data.get("location"),
            }
            self.update_watch(pid, payload)
        elif isinstance(event, DebugBreakEvent):
            # force stack refresh after breakpoint
            self.callstacks.pop(pid, None)

    def seed_snapshot(
        self,
        pid: int,
        *,
        registers: Optional[Mapping[str, Any]] = None,
        stack: Optional[Iterable[Mapping[str, Any]]] = None,
        watches: Optional[Iterable[Mapping[str, Any]]] = None,
        mailboxes: Optional[Iterable[Mapping[str, Any]]] = None,
    ) -> None:
        if registers:
            self.update_registers(pid, registers)
        if stack:
            self.update_call_stack(pid, stack)
        if watches:
            for watch in watches:
                self.update_watch(pid, watch)
        if mailboxes:
            self.update_mailboxes(pid, mailboxes)

    def clear_pid(self, pid: int) -> None:
        self.registers.pop(pid, None)
        self.memory.pop(pid, None)
        self.callstacks.pop(pid, None)
        self.watches.pop(pid, None)
        self.mailboxes.pop(pid, None)

    def invalidate_registers(self, pid: int) -> None:
        self.registers.pop(pid, None)

    def invalidate_memory(self, pid: int) -> None:
        self.memory.pop(pid, None)

    def invalidate_stack(self, pid: int) -> None:
        self.callstacks.pop(pid, None)

    def invalidate_watches(self, pid: int) -> None:
        self.watches.pop(pid, None)


class CacheController:
    """Optional helper that wires RuntimeCache to an EventBus."""

    def __init__(
        self,
        cache: RuntimeCache,
        bus: EventBus,
        *,
        pid: Optional[int] = None,
        categories: Optional[List[str]] = None,
    ) -> None:
        self.cache = cache
        self.bus = bus
        self.token: Optional[int] = None
        self.handler: Callable[[BaseEvent], None] = self.cache.apply_event
        cats = categories or ["trace_step", "watch_update", "debug_break"]
        self.token = bus.subscribe(EventSubscription(categories=cats, pid=pid, handler=self.handler))

    def detach(self) -> None:
        if self.token is not None:
            self.bus.unsubscribe(self.token)
            self.token = None
