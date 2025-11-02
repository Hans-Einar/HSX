from __future__ import annotations
"""Mailbox manager for the HSX Python executive."""


import collections
from dataclasses import dataclass, field
from typing import Any, Callable, Deque, Dict, Iterable, Iterator, List, Optional, Tuple

from python import hsx_mailbox_constants as mbx_const  # namespace package import

HSX_MBX_DEFAULT_RING_CAPACITY = mbx_const.HSX_MBX_DEFAULT_RING_CAPACITY
HSX_MBX_FLAG_OOB = mbx_const.HSX_MBX_FLAG_OOB
HSX_MBX_FLAG_STDERR = mbx_const.HSX_MBX_FLAG_STDERR
HSX_MBX_FLAG_STDOUT = mbx_const.HSX_MBX_FLAG_STDOUT
HSX_MBX_FLAG_OVERRUN = mbx_const.HSX_MBX_FLAG_OVERRUN
HSX_MBX_MAX_NAME_BYTES = mbx_const.HSX_MBX_MAX_NAME_BYTES
HSX_MBX_MODE_RDONLY = mbx_const.HSX_MBX_MODE_RDONLY
HSX_MBX_MODE_RDWR = mbx_const.HSX_MBX_MODE_RDWR
HSX_MBX_MODE_TAP = mbx_const.HSX_MBX_MODE_TAP
HSX_MBX_MODE_FANOUT = mbx_const.HSX_MBX_MODE_FANOUT
HSX_MBX_MODE_FANOUT_DROP = mbx_const.HSX_MBX_MODE_FANOUT_DROP
HSX_MBX_MODE_FANOUT_BLOCK = mbx_const.HSX_MBX_MODE_FANOUT_BLOCK
HSX_MBX_NAMESPACE_APP = mbx_const.HSX_MBX_NAMESPACE_APP
HSX_MBX_NAMESPACE_PID = mbx_const.HSX_MBX_NAMESPACE_PID
HSX_MBX_NAMESPACE_SHARED = mbx_const.HSX_MBX_NAMESPACE_SHARED
HSX_MBX_NAMESPACE_SVC = mbx_const.HSX_MBX_NAMESPACE_SVC
HSX_MBX_PREFIX_APP = mbx_const.HSX_MBX_PREFIX_APP
HSX_MBX_PREFIX_PID = mbx_const.HSX_MBX_PREFIX_PID
HSX_MBX_PREFIX_SHARED = mbx_const.HSX_MBX_PREFIX_SHARED
HSX_MBX_PREFIX_SVC = mbx_const.HSX_MBX_PREFIX_SVC
HSX_MBX_STDIO_IN = mbx_const.HSX_MBX_STDIO_IN
HSX_MBX_STDIO_OUT = mbx_const.HSX_MBX_STDIO_OUT
HSX_MBX_STDIO_ERR = mbx_const.HSX_MBX_STDIO_ERR
HSX_MBX_TIMEOUT_INFINITE = mbx_const.HSX_MBX_TIMEOUT_INFINITE
HSX_MBX_TIMEOUT_POLL = mbx_const.HSX_MBX_TIMEOUT_POLL



class MailboxError(Exception):
    """Raised for mailbox failures."""

    def __init__(self, message: str, *, code: Optional[int] = None) -> None:
        super().__init__(message)
        self.code = code


@dataclass
class MailboxMessage:
    length: int
    flags: int
    src_pid: int
    channel: int
    payload: bytes
    seq_no: int


@dataclass
class HandleState:
    descriptor_id: int
    last_seq: int = -1
    pending_overrun: bool = False
    is_sender: bool = False


@dataclass
class MailboxDescriptor:
    descriptor_id: int
    namespace: int
    name: str
    owner_pid: Optional[int]
    capacity: int = HSX_MBX_DEFAULT_RING_CAPACITY
    mode_mask: int = 0
    queue: Deque[MailboxMessage] = field(default_factory=collections.deque)
    bytes_used: int = 0
    waiters: List[int] = field(default_factory=list)
    taps: List[int] = field(default_factory=list)
    head_seq: int = 0
    next_seq: int = 0

    def space_remaining(self) -> int:
        return max(self.capacity - self.bytes_used, 0)


class MailboxManager:
    """Tracks HSX mailboxes and per-task handle tables."""

    def __init__(self, *, max_descriptors: int = 256, event_hook: Optional[Callable[[Dict[str, Any]], None]] = None) -> None:
        self._max_descriptors = max(1, int(max_descriptors))
        self._next_descriptor_id = 1
        self._descriptors: Dict[int, MailboxDescriptor] = {}
        self._lookup: Dict[Tuple[int, str, Optional[int]], int] = {}
        self._handles: Dict[int, Dict[int, HandleState]] = {}  # pid -> handle -> state
        self._next_handle: Dict[int, int] = {}
        self._default_stdio_modes: Dict[str, int] = {
            HSX_MBX_STDIO_IN: HSX_MBX_MODE_RDWR,
            HSX_MBX_STDIO_OUT: HSX_MBX_MODE_RDWR,
            HSX_MBX_STDIO_ERR: HSX_MBX_MODE_RDWR,
        }
        self._stdio_handles: Dict[int, Dict[str, int]] = {}
        self._event_hook: Optional[Callable[[Dict[str, Any]], None]] = event_hook

    # ------------------------------------------------------------------
    # Lifecycle helpers

    @property
    def max_descriptors(self) -> int:
        return self._max_descriptors

    @property
    def descriptor_count(self) -> int:
        return len(self._descriptors)

    def set_event_hook(self, hook: Optional[Callable[[Dict[str, Any]], None]]) -> None:
        """Assign or clear the event hook used for instrumentation callbacks."""
        self._event_hook = hook

    def _emit_event(self, event_type: str, **fields: Any) -> None:
        if self._event_hook is None:
            return
        event = {"type": event_type, **fields}
        try:
            self._event_hook(event)
        except Exception:
            # Instrumentation must never disrupt mailbox operation.
            pass

    def register_task(self, pid: int) -> None:
        """Ensure the per-task mailboxes exist (stdio + control)."""
        for target in (HSX_MBX_STDIO_IN, HSX_MBX_STDIO_OUT, HSX_MBX_STDIO_ERR):
            mode = self._default_stdio_modes.get(target, HSX_MBX_MODE_RDWR)
            self.bind_target(pid=pid, target=target, mode_mask=mode)
        control_target = f"{HSX_MBX_PREFIX_PID}{pid}"
        self.bind_target(pid=pid, target=control_target, mode_mask=HSX_MBX_MODE_RDWR)
        self.ensure_stdio_handles(pid)

    def ensure_stdio_handles(self, pid: int) -> Dict[str, int]:
        """Ensure the default stdio handles exist for *pid* and return them."""
        streams = (
            ("stdin", HSX_MBX_STDIO_IN),
            ("stdout", HSX_MBX_STDIO_OUT),
            ("stderr", HSX_MBX_STDIO_ERR),
        )
        table = self._stdio_handles.setdefault(pid, {})
        handle_table = self._handles.setdefault(pid, {})
        result: Dict[str, int] = {}
        for stream, target in streams:
            handle = table.get(stream)
            if handle is None or handle not in handle_table:
                handle = self.open(pid=pid, target=target)
                table[stream] = handle
                handle_table = self._handles.setdefault(pid, {})
            result[stream] = handle
        return dict(result)

    # ------------------------------------------------------------------
    # Public API

    def bind(
        self,
        *,
        namespace: int,
        name: str,
        owner_pid: Optional[int] = None,
        capacity: Optional[int] = None,
        mode_mask: int = 0,
    ) -> MailboxDescriptor:
        key = (namespace, name, owner_pid)
        descriptor_id = self._lookup.get(key)
        if descriptor_id is None:
            if len(self._descriptors) >= self._max_descriptors:
                raise MailboxError(
                    "descriptor pool exhausted",
                    code=mbx_const.HSX_MBX_STATUS_NO_DESCRIPTOR,
                )
            descriptor_id = self._next_descriptor_id
            self._next_descriptor_id += 1
            desc = MailboxDescriptor(
                descriptor_id=descriptor_id,
                namespace=namespace,
                name=name,
                owner_pid=owner_pid,
                capacity=capacity or HSX_MBX_DEFAULT_RING_CAPACITY,
                mode_mask=mode_mask,
            )
            self._descriptors[descriptor_id] = desc
            self._lookup[key] = descriptor_id
            self._update_head_seq(desc)
            if mode_mask:
                self._apply_descriptor_mode(desc, mode_mask)
            return desc

        desc = self._descriptors[descriptor_id]
        if capacity is not None and capacity > 0 and capacity != desc.capacity:
            desc.capacity = capacity
            self._enforce_capacity(desc)
        if mode_mask:
            self._apply_descriptor_mode(desc, mode_mask)
        return desc

    def bind_target(
        self,
        *,
        pid: int,
        target: str,
        capacity: Optional[int] = None,
        mode_mask: int = 0,
    ) -> MailboxDescriptor:
        namespace, name, owner = self._parse_target(pid, target)
        return self.bind(
            namespace=namespace,
            name=name,
            owner_pid=owner,
            capacity=capacity,
            mode_mask=mode_mask,
        )

    def set_default_stdio_mode(self, stream: str, mode_mask: int, *, update_existing: bool = False) -> List[int]:
        key = self._stdio_target_for_stream(stream)
        self._default_stdio_modes[key] = mode_mask
        if not update_existing:
            return []
        stream_name = key.split(":", 1)[1] if ":" in key else key
        updated: List[int] = []
        for desc in self._descriptors.values():
            if desc.namespace == HSX_MBX_NAMESPACE_SVC and desc.name == stream_name:
                self._apply_descriptor_mode(desc, mode_mask)
                updated.append(desc.descriptor_id)
        return updated

    def open(self, *, pid: int, target: str, flags: int = 0) -> int:
        namespace, name, owner_pid = self._parse_target(pid, target)
        desc = self.bind(namespace=namespace, name=name, owner_pid=owner_pid)
        handle = self._allocate_handle(pid)
        state = HandleState(descriptor_id=desc.descriptor_id)
        self._initialize_handle_state(desc, state)
        self._handles.setdefault(pid, {})[handle] = state
        return handle

    def close(self, *, pid: int, handle: int) -> None:
        table = self._handles.get(pid)
        if not table or handle not in table:
            raise MailboxError(
                f"invalid handle {handle} for pid {pid}",
                code=mbx_const.HSX_MBX_STATUS_INVALID_HANDLE,
            )
        state = table.pop(handle)
        desc = self._descriptors.get(state.descriptor_id)
        if desc is not None:
            self._reclaim_acked(desc)

    def descriptor_for_handle(self, pid: int, handle: int) -> MailboxDescriptor:
        state = self._handle_state(pid, handle)
        desc = self._descriptors.get(state.descriptor_id)
        if desc is None:
            raise MailboxError(f"descriptor {state.descriptor_id} missing")
        return desc

    def descriptor_by_id(self, descriptor_id: int) -> MailboxDescriptor:
        desc = self._descriptors.get(descriptor_id)
        if desc is None:
            raise MailboxError(f"descriptor {descriptor_id} missing")
        return desc

    def send(
        self,
        *,
        pid: int,
        handle: int,
        payload: bytes,
        flags: int = 0,
        channel: int = 0,
    ) -> Tuple[bool, Optional[int]]:
        try:
            with open("/tmp/hsx_mailbox_trace.log", "a", encoding="utf-8") as trace_fp:
                trace_fp.write(f"[MailboxManager] send pid={pid} handle={handle} len={len(payload)} flags=0x{flags:04X} channel={channel}\n")
        except OSError:
            pass
        state = self._handle_state(pid, handle)
        desc = self.descriptor_by_id(state.descriptor_id)
        state.is_sender = True
        if not payload:
            return True, desc.descriptor_id
        message = MailboxMessage(
            length=len(payload),
            flags=flags,
            src_pid=pid,
            channel=channel,
            payload=payload,
            seq_no=desc.next_seq,
        )
        ok = self._enqueue_message(desc, message)
        try:
            with open("/tmp/hsx_mailbox_trace.log", "a", encoding="utf-8") as trace_fp:
                trace_fp.write(f"[MailboxManager] send result ok={ok} descriptor={desc.descriptor_id} ns={desc.namespace} depth={len(desc.queue)}\n")
        except OSError:
            pass
        return ok, desc.descriptor_id

    def recv(self, *, pid: int, handle: int, record_waiter: bool = True) -> Optional[MailboxMessage]:
        state = self._handle_state(pid, handle)
        desc = self.descriptor_by_id(state.descriptor_id)
        fanout_enabled = bool(desc.mode_mask & HSX_MBX_MODE_FANOUT)
        try:
            with open("/tmp/hsx_mailbox_trace.log", "a", encoding="utf-8") as trace_fp:
                trace_fp.write(f"[MailboxManager] recv pid={pid} handle={handle} descriptor={desc.descriptor_id} depth={len(desc.queue)}\n")
        except OSError:
            pass
        if fanout_enabled:
            self._reclaim_acked(desc)
            next_msg = self._next_message_for_handle(desc, state)
            if next_msg is None:
                if record_waiter and pid not in desc.waiters:
                    desc.waiters.append(pid)
                return None
            state.is_sender = False
            state.last_seq = next_msg.seq_no
            overrun = state.pending_overrun
            state.pending_overrun = False
            if pid in desc.waiters:
                desc.waiters = [p for p in desc.waiters if p != pid]
            result = MailboxMessage(
                length=next_msg.length,
                flags=next_msg.flags | (HSX_MBX_FLAG_OVERRUN if overrun else 0),
                src_pid=next_msg.src_pid,
                channel=next_msg.channel,
                payload=next_msg.payload,
                seq_no=next_msg.seq_no,
            )
            self._reclaim_acked(desc)
            return result

        msg = self._pop_head(desc)
        try:
            with open("/tmp/hsx_mailbox_trace.log", "a", encoding="utf-8") as trace_fp:
                trace_fp.write(f"[MailboxManager] recv pop pid={pid} handle={handle} msg={'none' if msg is None else msg.length} depth={len(desc.queue)}\n")
        except OSError:
            pass
        if msg is None:
            if record_waiter and pid not in desc.waiters:
                desc.waiters.append(pid)
            return None
        if pid in desc.waiters:
            desc.waiters = [p for p in desc.waiters if p != pid]
        return msg

    def peek(self, *, pid: int, handle: int) -> Dict[str, int]:
        state = self._handle_state(pid, handle)
        desc = self.descriptor_by_id(state.descriptor_id)
        fanout_enabled = bool(desc.mode_mask & HSX_MBX_MODE_FANOUT)
        if fanout_enabled:
            next_msg = self._next_message_for_handle(desc, state)
        else:
            next_msg = desc.queue[0] if desc.queue else None
        next_len = next_msg.length if next_msg is not None else 0
        next_seq = next_msg.seq_no if next_msg is not None else desc.next_seq
        return {
            "depth": len(desc.queue),
            "bytes_used": desc.bytes_used,
            "capacity": desc.capacity,
            "next_len": next_len,
            "head_seq": desc.head_seq,
            "next_seq": next_seq,
            "mode_mask": desc.mode_mask,
        }

    def tap(self, *, pid: int, handle: int, enable: bool) -> None:
        desc = self.descriptor_for_handle(pid, handle)
        taps = desc.taps
        if enable:
            if pid not in taps:
                taps.append(pid)
        else:
            if pid in taps:
                taps.remove(pid)

    def iter_waiters(self, descriptor_id: int) -> Iterable[int]:
        desc = self._descriptors.get(descriptor_id)
        if desc:
            yield from desc.waiters

    def remove_waiter(self, descriptor_id: int, pid: int) -> None:
        desc = self._descriptors.get(descriptor_id)
        if not desc:
            return
        if pid in desc.waiters:
            desc.waiters = [p for p in desc.waiters if p != pid]

    # ------------------------------------------------------------------
    # Helpers

    def _parse_target(self, pid: int, target: str) -> Tuple[int, str, Optional[int]]:
        if not target:
            raise MailboxError("empty mailbox target")
        trimmed = target[:HSX_MBX_MAX_NAME_BYTES]
        if trimmed.startswith(HSX_MBX_PREFIX_PID):
            suffix = trimmed[len(HSX_MBX_PREFIX_PID) :]
            owner = int(suffix) if suffix else pid
            name = f"pid:{owner}"
            return HSX_MBX_NAMESPACE_PID, name, owner
        if trimmed.startswith(HSX_MBX_PREFIX_SVC):
            suffix = trimmed[len(HSX_MBX_PREFIX_SVC) :]
            base, owner = self._split_owner_suffix(pid, suffix)
            return HSX_MBX_NAMESPACE_SVC, base, owner
        if trimmed.startswith(HSX_MBX_PREFIX_APP):
            suffix = trimmed[len(HSX_MBX_PREFIX_APP) :]
            base, owner = self._split_owner_suffix(None, suffix)
            return HSX_MBX_NAMESPACE_APP, base, owner
        if trimmed.startswith(HSX_MBX_PREFIX_SHARED):
            suffix = trimmed[len(HSX_MBX_PREFIX_SHARED) :]
            base, _ = self._split_owner_suffix(None, suffix)
            return HSX_MBX_NAMESPACE_SHARED, base, None
        # default to svc namespace for bare names
        base, owner = self._split_owner_suffix(pid, trimmed)
        return HSX_MBX_NAMESPACE_SVC, base, owner

    @staticmethod
    def _split_owner_suffix(default_owner: Optional[int], suffix: str) -> Tuple[str, Optional[int]]:
        if "@" in suffix:
            base, _, owner_str = suffix.partition("@")
            owner = default_owner
            if owner_str:
                owner = int(owner_str)
        else:
            base = suffix
            owner = default_owner
        return base, owner

    def _allocate_handle(self, pid: int) -> int:
        counter = self._next_handle.get(pid, 1)
        handle = counter
        self._next_handle[pid] = counter + 1
        return handle

    # ------------------------------------------------------------------
    # Introspection helpers

    def descriptor_snapshot(self) -> List[Dict[str, object]]:
        out: List[Dict[str, object]] = []
        for desc in self._descriptors.values():
            out.append(
                {
                    "descriptor_id": desc.descriptor_id,
                    "namespace": desc.namespace,
                    "name": desc.name,
                    "owner_pid": desc.owner_pid,
                    "capacity": desc.capacity,
                    "bytes_used": desc.bytes_used,
                    "queue_depth": len(desc.queue),
                    "head_seq": desc.head_seq,
                    "next_seq": desc.next_seq,
                    "mode_mask": desc.mode_mask,
                    "subscriber_count": sum(1 for _ in self._iter_handle_states(desc.descriptor_id)),
                    "waiters": list(desc.waiters),
                    "taps": list(desc.taps),
                }
            )
        return sorted(out, key=lambda item: item["descriptor_id"])

    # ------------------------------------------------------------------
    # Internal helpers

    def _stdio_target_for_stream(self, stream: str) -> str:
        normalized = stream.lower()
        if normalized in {"in", "stdin"}:
            return HSX_MBX_STDIO_IN
        if normalized in {"out", "stdout"}:
            return HSX_MBX_STDIO_OUT
        if normalized in {"err", "stderr"}:
            return HSX_MBX_STDIO_ERR
        raise MailboxError(f"unknown stdio stream '{stream}'")

    def default_stdio_modes(self) -> Dict[str, int]:
        result: Dict[str, int] = {}
        for stream, target in (("in", HSX_MBX_STDIO_IN), ("out", HSX_MBX_STDIO_OUT), ("err", HSX_MBX_STDIO_ERR)):
            result[stream] = self._default_stdio_modes.get(target, HSX_MBX_MODE_RDWR)
        return result

    def stdio_modes_for_pid(self, pid: int) -> Dict[str, int]:
        result: Dict[str, int] = {}
        for stream, target in (("in", HSX_MBX_STDIO_IN), ("out", HSX_MBX_STDIO_OUT), ("err", HSX_MBX_STDIO_ERR)):
            result[stream] = self._stdio_mode_for_target(pid, target)
        return result

    def _stdio_mode_for_target(self, pid: Optional[int], target: str) -> int:
        if ":" in target:
            _, _, name = target.partition(":")
        else:
            name = target
        owner = pid
        key = (HSX_MBX_NAMESPACE_SVC, name, owner)
        desc_id = self._lookup.get(key)
        if desc_id is not None:
            desc = self._descriptors.get(desc_id)
            if desc is not None:
                return desc.mode_mask
        if pid is None:
            return self._default_stdio_modes.get(target, HSX_MBX_MODE_RDWR)
        return self._default_stdio_modes.get(target, HSX_MBX_MODE_RDWR)

    def _handle_state(self, pid: int, handle: int) -> HandleState:
        table = self._handles.get(pid)
        if not table or handle not in table:
            raise MailboxError(
                f"invalid handle {handle} for pid {pid}",
                code=mbx_const.HSX_MBX_STATUS_INVALID_HANDLE,
            )
        return table[handle]

    def _iter_handle_states(self, descriptor_id: int) -> Iterator[HandleState]:
        for table in self._handles.values():
            for state in table.values():
                if state.descriptor_id == descriptor_id:
                    yield state

    def _initialize_handle_state(self, desc: MailboxDescriptor, state: HandleState) -> None:
        if desc.mode_mask & HSX_MBX_MODE_FANOUT:
            state.last_seq = desc.next_seq - 1
        else:
            state.last_seq = -1
        state.pending_overrun = False
        state.is_sender = False

    def _next_message_for_handle(self, desc: MailboxDescriptor, state: HandleState) -> Optional[MailboxMessage]:
        for message in desc.queue:
            if message.seq_no > state.last_seq:
                return message
        return None

    def _enqueue_message(self, desc: MailboxDescriptor, message: MailboxMessage) -> bool:
        cost = _message_cost(message)
        if cost > desc.capacity:
            raise MailboxError(
                "message too large for mailbox capacity",
                code=mbx_const.HSX_MBX_STATUS_MSG_TOO_LARGE,
            )

        fanout_enabled = bool(desc.mode_mask & HSX_MBX_MODE_FANOUT)
        if not fanout_enabled:
            if cost > desc.space_remaining():
                return False
            self._append_message(desc, message, cost)
            return True

        self._reclaim_acked(desc)
        if desc.mode_mask & HSX_MBX_MODE_FANOUT_BLOCK:
            if cost > desc.space_remaining():
                return False
        else:
            while cost > desc.space_remaining() and desc.queue:
                dropped = self._pop_head(desc)
                if dropped is not None:
                    self._emit_event(
                        "mailbox_overrun",
                        pid=dropped.src_pid,
                        descriptor=desc.descriptor_id,
                        dropped_seq=dropped.seq_no,
                        dropped_length=dropped.length,
                        dropped_flags=dropped.flags,
                        channel=dropped.channel,
                        reason="fanout_drop",
                        queue_depth=len(desc.queue),
                    )
                    self._mark_overrun(desc.descriptor_id, dropped.seq_no)
        if cost > desc.space_remaining():
            return False
        self._append_message(desc, message, cost)
        return True

    def _append_message(self, desc: MailboxDescriptor, message: MailboxMessage, cost: int) -> None:
        was_empty = not desc.queue
        desc.queue.append(message)
        desc.bytes_used += cost
        desc.next_seq = message.seq_no + 1
        if was_empty:
            desc.head_seq = message.seq_no

    def _pop_head(self, desc: MailboxDescriptor) -> Optional[MailboxMessage]:
        if not desc.queue:
            return None
        message = desc.queue.popleft()
        desc.bytes_used = max(desc.bytes_used - _message_cost(message), 0)
        self._update_head_seq(desc)
        return message

    def _reclaim_acked(self, desc: MailboxDescriptor) -> None:
        if not (desc.mode_mask & HSX_MBX_MODE_FANOUT):
            return
        while desc.queue:
            head = desc.queue[0]
            readers = [state for state in self._iter_handle_states(desc.descriptor_id) if not state.is_sender]
            if not readers:
                break
            if all(state.last_seq >= head.seq_no for state in readers):
                self._pop_head(desc)
                continue
            break

    def _mark_overrun(self, descriptor_id: int, seq_no: int) -> None:
        for state in self._iter_handle_states(descriptor_id):
            if not state.is_sender and state.last_seq < seq_no:
                state.pending_overrun = True

    def _update_head_seq(self, desc: MailboxDescriptor) -> None:
        if desc.queue:
            desc.head_seq = desc.queue[0].seq_no
        else:
            desc.head_seq = desc.next_seq

    def _enforce_capacity(self, desc: MailboxDescriptor) -> None:
        while desc.bytes_used > desc.capacity and desc.queue:
            dropped = self._pop_head(desc)
            if dropped is not None:
                self._mark_overrun(desc.descriptor_id, dropped.seq_no)

    def _apply_descriptor_mode(self, desc: MailboxDescriptor, mode_mask: int) -> None:
        desc.mode_mask = mode_mask
        for state in self._iter_handle_states(desc.descriptor_id):
            self._initialize_handle_state(desc, state)
        self._reclaim_acked(desc)
        self._update_head_seq(desc)
        self._enforce_capacity(desc)


def _message_cost(message: MailboxMessage) -> int:
    return message.length + 8
