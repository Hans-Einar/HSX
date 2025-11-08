"""Event bus utilities and typed event helpers for hsxdbg."""

from __future__ import annotations

import queue
import threading
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional


EventHandler = Callable[["BaseEvent"], None]


def _to_int(value: Any) -> Optional[int]:
    try:
        if value is None:
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _to_float(value: Any) -> float:
    try:
        if value is None:
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _ensure_str_list(value: Any) -> List[str]:
    if isinstance(value, (list, tuple)):
        return [str(item) for item in value]
    return []


def _ensure_int_list(value: Any) -> Optional[List[int]]:
    if isinstance(value, (list, tuple)):
        ints: List[int] = []
        for item in value:
            maybe = _to_int(item)
            if maybe is None:
                return None
            ints.append(maybe & 0xFFFFFFFF)
        return ints
    return None


def parse_event(event: Dict[str, Any]) -> BaseEvent:
    """Convert a raw executive event dictionary into a typed dataclass."""

    event_type = str(event.get("type") or "")
    seq = int(event.get("seq") or 0)
    pid = event.get("pid")
    if isinstance(pid, str) and pid.isdigit():
        pid = int(pid)
    ts = _to_float(event.get("ts"))
    data = event.get("data") or {}

    if event_type == "trace_step":
        return TraceStepEvent(
            seq=seq,
            ts=ts,
            type=event_type,
            pid=pid,
            data=data,
            pc=_to_int(data.get("pc")),
            next_pc=_to_int(data.get("next_pc")),
            opcode=_to_int(data.get("opcode")),
            flags=_to_int(data.get("flags")),
            regs=_ensure_int_list(data.get("regs")),
            changed_regs=_ensure_str_list(data.get("changed_regs")),
            mem_access=data.get("mem_access") if isinstance(data.get("mem_access"), dict) else None,
        )
    if event_type == "debug_break":
        return DebugBreakEvent(
            seq=seq,
            ts=ts,
            type=event_type,
            pid=pid,
            data=data,
            pc=_to_int(data.get("pc")),
            reason=data.get("reason"),
            symbol=data.get("symbol"),
        )
    if event_type == "scheduler":
        return SchedulerEvent(
            seq=seq,
            ts=ts,
            type=event_type,
            pid=pid,
            data=data,
            prev_pid=_to_int(data.get("prev_pid")),
            next_pid=_to_int(data.get("next_pid")),
            reason=data.get("reason"),
            state=data.get("state") or data.get("post_state"),
        )
    if event_type == "task_state":
        return TaskStateEvent(
            seq=seq,
            ts=ts,
            type=event_type,
            pid=pid,
            data=data,
            prev_state=data.get("prev_state"),
            new_state=data.get("new_state"),
            reason=data.get("reason"),
        )
    if event_type.startswith("mailbox_"):
        return MailboxEvent(
            seq=seq,
            ts=ts,
            type=event_type,
            pid=pid,
            data=data,
            descriptor=data.get("descriptor"),
            handle=_to_int(data.get("handle")),
            length=_to_int(data.get("length")),
            channel=_to_int(data.get("channel")),
            flags=_to_int(data.get("flags")),
        )
    if event_type == "watch_update":
        return WatchUpdateEvent(
            seq=seq,
            ts=ts,
            type=event_type,
            pid=pid,
            data=data,
            watch_id=_to_int(data.get("watch_id")),
            expr=data.get("expr"),
            length=_to_int(data.get("length")),
            old_value=data.get("old"),
            new_value=data.get("new"),
            address=_to_int(data.get("address")),
        )
    if event_type in {"stdout", "stderr"}:
        return StdStreamEvent(
            seq=seq,
            ts=ts,
            type=event_type,
            pid=pid,
            data=data,
            stream=event_type,
            text=str(data.get("text") or ""),
        )
    if event_type == "warning":
        reason = data.get("reason")
        return WarningEvent(
            seq=seq,
            ts=ts,
            type=event_type,
            pid=pid,
            data=data,
            reason=reason,
            details={k: v for k, v in data.items() if k != "reason"},
        )
    return BaseEvent(seq=seq, ts=ts, type=event_type, pid=pid, data=data)
@dataclass
class BaseEvent:
    seq: int
    ts: float
    type: str
    pid: Optional[int]
    data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TraceStepEvent(BaseEvent):
    pc: Optional[int] = None
    next_pc: Optional[int] = None
    opcode: Optional[int] = None
    flags: Optional[int] = None
    regs: Optional[List[int]] = None
    changed_regs: List[str] = field(default_factory=list)
    mem_access: Optional[Dict[str, Any]] = None


@dataclass
class DebugBreakEvent(BaseEvent):
    pc: Optional[int] = None
    reason: Optional[str] = None
    symbol: Optional[str] = None


@dataclass
class SchedulerEvent(BaseEvent):
    prev_pid: Optional[int] = None
    next_pid: Optional[int] = None
    reason: Optional[str] = None
    state: Optional[str] = None


@dataclass
class TaskStateEvent(BaseEvent):
    prev_state: Optional[str] = None
    new_state: Optional[str] = None
    reason: Optional[str] = None


@dataclass
class MailboxEvent(BaseEvent):
    descriptor: Optional[str] = None
    handle: Optional[int] = None
    length: Optional[int] = None
    channel: Optional[int] = None
    flags: Optional[int] = None


@dataclass
class WatchUpdateEvent(BaseEvent):
    watch_id: Optional[int] = None
    expr: Optional[str] = None
    length: Optional[int] = None
    old_value: Optional[str] = None
    new_value: Optional[str] = None
    address: Optional[int] = None


@dataclass
class StdStreamEvent(BaseEvent):
    stream: str = "stdout"
    text: str = ""


@dataclass
class WarningEvent(BaseEvent):
    reason: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class EventSubscription:
    categories: Optional[List[str]] = None
    pid: Optional[int] = None
    queue_size: int = 256
    handler: EventHandler = lambda event: None
    _queue: queue.Queue = field(init=False)

    def __post_init__(self) -> None:
        self._queue = queue.Queue(maxsize=self.queue_size)

    def push(self, event: BaseEvent) -> None:
        try:
            self._queue.put_nowait(event)
        except queue.Full:
            # Drop oldest event to keep bus responsive
            try:
                self._queue.get_nowait()
            except queue.Empty:
                pass
            self._queue.put_nowait(event)

    def dispatch(self) -> None:
        while True:
            try:
                event = self._queue.get_nowait()
            except queue.Empty:
                break
            self.handler(event)


class EventBus:
    """Fan-out filtered events to subscribers."""

    def __init__(self) -> None:
        self._subs: Dict[int, EventSubscription] = {}
        self._lock = threading.Lock()
        self._next_token = 1
        self._worker: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._interval = 0.01

    def subscribe(self, sub: EventSubscription) -> int:
        with self._lock:
            token = self._next_token
            self._next_token += 1
            self._subs[token] = sub
            return token

    def unsubscribe(self, token: int) -> None:
        with self._lock:
            self._subs.pop(token, None)

    def publish(self, event: Dict[str, Any]) -> None:
        parsed = parse_event(event)
        with self._lock:
            subscriptions = list(self._subs.values())
        for sub in subscriptions:
            cat_ok = not sub.categories or parsed.type in sub.categories
            pid_ok = sub.pid is None or parsed.pid == sub.pid
            if cat_ok and pid_ok:
                sub.push(parsed)

    def pump(self) -> None:
        """Dispatch queued events on all subscriptions."""
        with self._lock:
            tokens = list(self._subs.keys())
        for token in tokens:
            sub = self._subs.get(token)
            if sub:
                sub.dispatch()

    def start(self, interval: float = 0.01) -> None:
        """Start background dispatcher that periodically pumps the bus."""

        self._interval = interval
        if self._worker and self._worker.is_alive():
            return
        self._stop_event.clear()
        self._worker = threading.Thread(target=self._run, daemon=True)
        self._worker.start()

    def stop(self) -> None:
        self._stop_event.set()
        worker = self._worker
        if worker and worker.is_alive():
            worker.join(timeout=0.5)
        self._worker = None

    def _run(self) -> None:
        while not self._stop_event.wait(self._interval):
            self.pump()
        self.pump()
