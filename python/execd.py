#!/usr/bin/env python3
try:
    from .vmclient import VMClient
except ImportError:
    from vmclient import VMClient

try:
    from . import hsx_mailbox_constants as mbx_const
except ImportError:
    import hsx_mailbox_constants as mbx_const

try:
    from . import disasm_util
except ImportError:
    import disasm_util

try:
    from . import trace_format
except ImportError:
    import trace_format

"""HSX executive daemon.

Connects to the HSX VM RPC server, takes over scheduling (attach/pause/resume),
and exposes a TCP JSON interface for shell clients. This is an initial scaffold;
future work will add task tables, stdout routing, and richer scheduling.
"""
import argparse
import bisect
import heapq
import json
import os
import socketserver
import threading
import time
import sys
import uuid
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Optional, List, Iterable, Deque, Set, Tuple, Mapping


class SessionError(RuntimeError):
    """Raised when session validation or locking fails."""


class TaskState(Enum):
    READY = "ready"
    RUNNING = "running"
    WAIT_MBX = "waiting_mbx"
    SLEEPING = "sleeping"
    PAUSED = "paused"
    RETURNED = "returned"
    TERMINATED = "terminated"
    KILLED = "killed"

    @classmethod
    def from_any(cls, value: Any) -> "TaskState":
        if isinstance(value, TaskState):
            return value
        if value is None:
            raise ValueError("task_state_none")
        if isinstance(value, str):
            key = value.lower()
            alias = _TASK_STATE_ALIASES.get(key)
            if alias is not None:
                return alias
        raise ValueError(f"unknown_task_state:{value}")


_TASK_STATE_ALIASES = {
    state.value: state for state in TaskState
}
_TASK_STATE_ALIASES.update(
    {
        "wait_mbx": TaskState.WAIT_MBX,
        "waiting": TaskState.WAIT_MBX,
        "sleep": TaskState.SLEEPING,
        "sleeping": TaskState.SLEEPING,
        "returning": TaskState.RETURNED,
        "returned": TaskState.RETURNED,
        "exited": TaskState.RETURNED,
        "exit": TaskState.RETURNED,
        "stopped": TaskState.PAUSED,
        "dead": TaskState.TERMINATED,
    }
)

_ALLOWED_STATE_TRANSITIONS: Dict[Optional[TaskState], Set[TaskState]] = {
    None: {
        TaskState.READY,
        TaskState.RUNNING,
        TaskState.RETURNED,
        TaskState.TERMINATED,
        TaskState.PAUSED,
        TaskState.SLEEPING,
        TaskState.WAIT_MBX,
    },
    TaskState.READY: {
        TaskState.READY,
        TaskState.RUNNING,
        TaskState.WAIT_MBX,
        TaskState.SLEEPING,
        TaskState.PAUSED,
        TaskState.TERMINATED,
        TaskState.KILLED,
    },
    TaskState.RUNNING: {
        TaskState.RUNNING,
        TaskState.READY,
        TaskState.WAIT_MBX,
        TaskState.SLEEPING,
        TaskState.PAUSED,
        TaskState.RETURNED,
        TaskState.TERMINATED,
        TaskState.KILLED,
    },
    TaskState.WAIT_MBX: {
        TaskState.WAIT_MBX,
        TaskState.READY,
        TaskState.RUNNING,
        TaskState.PAUSED,
        TaskState.TERMINATED,
        TaskState.KILLED,
    },
    TaskState.SLEEPING: {
        TaskState.SLEEPING,
        TaskState.READY,
        TaskState.RUNNING,
        TaskState.PAUSED,
        TaskState.TERMINATED,
        TaskState.KILLED,
    },
    TaskState.PAUSED: {
        TaskState.PAUSED,
        TaskState.READY,
        TaskState.RUNNING,
        TaskState.TERMINATED,
        TaskState.KILLED,
    },
    TaskState.RETURNED: {
        TaskState.RETURNED,
        TaskState.TERMINATED,
        TaskState.KILLED,
    },
    TaskState.TERMINATED: {
        TaskState.TERMINATED,
    },
    TaskState.KILLED: {
        TaskState.KILLED,
    },
}


@dataclass
class SessionRecord:
    session_id: str
    client: str
    features: List[str]
    max_events: int
    pid_locks: List[int]
    heartbeat_s: int
    warnings: List[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    last_seen: float = field(default_factory=time.time)


@dataclass
class EventSubscription:
    token: str
    session_id: str
    pids: Optional[Set[int]]
    categories: Optional[Set[str]]
    queue: Deque[Dict[str, Any]]
    condition: threading.Condition
    max_events: int
    last_ack: int = 0
    delivered_seq: int = 0
    drop_count: int = 0
    slow_count: int = 0
    high_water: int = 0
    slow_warning_active: bool = False
    slow_since: float = 0.0
    last_warning_ts: float = 0.0
    last_delivery_ts: float = field(default_factory=time.time)
    created_at: float = field(default_factory=time.time)
    active: bool = True
    since_seq: Optional[int] = None

    def matches(self, event: Dict[str, Any]) -> bool:
        if self.pids is not None:
            pid = event.get("pid")
            if pid not in self.pids:
                return False
        if self.categories is not None:
            etype = event.get("type")
            if etype not in self.categories:
                return False
        return True

    def pending(self) -> int:
        return max(0, self.delivered_seq - self.last_ack)



RODATA_BASE = 0x4000
REGISTER_REGION_START = 0x1000
REGISTER_BANK_BYTES = 16 * 4
VM_ADDRESS_SPACE_SIZE = 0x10000


class ExecutiveState:
    def __init__(self, vm: VMClient, step_batch: int = 1) -> None:
        self.vm = vm
        self.step_batch = max(1, step_batch)
        self.auto_event = threading.Event()
        self.auto_thread: Optional[threading.Thread] = None
        self.lock = threading.Lock()
        self.tasks: Dict[int, Dict[str, Any]] = {}
        self.current_pid: Optional[int] = None
        self.restart_requested: bool = False
        self.restart_targets: Optional[List[str]] = None
        self.server: Optional["ExecutiveServer"] = None
        self.task_states: Dict[int, Dict[str, Any]] = {}
        self.log_buffer: deque[Dict[str, Any]] = deque(maxlen=512)
        self._next_log_seq = 1
        self.clock_rate_hz: float = 0.0
        self.total_steps: int = 0
        self.auto_step_count: int = 0
        self.auto_step_total: int = 0
        self.manual_step_count: int = 0
        self.manual_step_total: int = 0
        self._last_vm_running: bool = True
        self.clock_mode: str = "stopped"
        self._clock_last_wait: float = 0.0
        self._clock_throttle_reason: Optional[str] = None
        self.sessions: Dict[str, SessionRecord] = {}
        self.pid_locks: Dict[int, str] = {}
        self.session_lock = threading.RLock()
        self.session_heartbeat_default = 30
        self.session_heartbeat_min = 5
        self.session_heartbeat_max = 300
        self.session_events_default = 256
        self.session_events_max = 2048
        self._last_session_prune = 0.0
        self._session_prune_interval = 5.0
        self.session_supported_features = {"events", "stack", "disasm", "symbols", "memory", "watch"}
        self.debug_attached: Set[int] = set()
        self.breakpoints: Dict[int, Set[int]] = {}
        self.event_lock = threading.RLock()
        self.event_seq = 1
        self.event_history: Deque[Dict[str, Any]] = deque(maxlen=4096)
        self.event_subscriptions: Dict[str, EventSubscription] = {}
        self.session_event_map: Dict[str, str] = {}
        self.event_retention_ms = 5000
        self.event_ack_warn_factor = 2
        self.event_ack_drop_factor = 4
        self.event_ack_warn_floor = 64
        self.event_ack_drop_floor = 256
        self.event_backpressure_grace = 1.0
        self.event_slow_warning_interval = 0.5
        self.symbol_tables: Dict[int, Dict[str, Any]] = {}
        self.disasm_cache: Dict[int, Dict[Tuple[int, int], Dict[str, Any]]] = {}
        self.memory_layouts: Dict[int, Dict[str, int]] = {}
        self.image_metadata: Dict[int, Dict[str, Any]] = {}
        self.value_registry: Dict[int, Dict[Tuple[int, int], Dict[str, Any]]] = {}
        self.command_registry: Dict[int, Dict[Tuple[int, int], Dict[str, Any]]] = {}
        self.mailbox_registry: Dict[int, Dict[str, Dict[str, Any]]] = {}
        self.watchers: Dict[int, Dict[int, Dict[str, Any]]] = {}
        self._next_watch_id = 1
        self.task_state_pending: Dict[int, Dict[str, Any]] = {}
        self.trace_last_regs: Dict[int, Dict[str, Any]] = {}
        self.trace_track_changed_regs = True
        self.trace_lock = threading.RLock()
        self.trace_buffer_capacity = 256
        self.trace_buffer_max = 4096
        self.trace_buffers: Dict[int, Deque[Dict[str, Any]]] = {}
        self._trace_seq = 1
        self.symbol_cache_lock = threading.RLock()
        self.default_stack_frames = 16
        self.last_state_transition: Dict[int, Dict[str, Any]] = {}
        self.sleeping_heap: List[Tuple[float, int]] = []
        self.sleeping_deadlines: Dict[int, float] = {}
        self._pending_scheduler_context: Optional[Dict[str, Any]] = None
        self.enforce_context_isolation: bool = True

    def _register_metadata(self, pid: int, metadata: Dict[str, Any]) -> None:
        if not metadata:
            self.value_registry.pop(pid, None)
            self.command_registry.pop(pid, None)
            self.mailbox_registry.pop(pid, None)
            return
        if not isinstance(metadata, dict):
            raise ValueError("metadata_invalid")

        values_block = metadata.get("values") or []
        commands_block = metadata.get("commands") or []
        mailboxes_block = metadata.get("mailboxes") or []

        if not isinstance(values_block, list) or not isinstance(commands_block, list) or not isinstance(mailboxes_block, list):
            raise ValueError("metadata_structure_invalid")

        new_values: Dict[Tuple[int, int], Dict[str, Any]] = {}
        new_commands: Dict[Tuple[int, int], Dict[str, Any]] = {}
        new_mailboxes: Dict[str, Dict[str, Any]] = {}
        mailbox_bind_requests: List[Tuple[str, Optional[int], int, Dict[str, Any]]] = []

        for entry in values_block:
            if not isinstance(entry, dict):
                raise ValueError("metadata_value_invalid")
            try:
                group_id = int(entry.get("group_id"))
                value_id = int(entry.get("value_id"))
            except (TypeError, ValueError):
                raise ValueError("metadata_value_invalid")
            if not (0 <= group_id <= 0xFF) or not (0 <= value_id <= 0xFF):
                raise ValueError("metadata_value_range")
            key = (group_id, value_id)
            if key in new_values:
                raise ValueError(f"metadata_value_duplicate:{group_id}:{value_id}")
            record = {
                "group_id": group_id,
                "value_id": value_id,
                "flags": int(entry.get("flags", 0)) & 0xFF,
                "auth_level": int(entry.get("auth_level", 0)) & 0xFF,
                "init_raw": int(entry.get("init_raw", 0)) & 0xFFFF,
                "init_value": entry.get("init_value"),
                "name": entry.get("name"),
                "unit": entry.get("unit"),
                "epsilon_raw": int(entry.get("epsilon_raw", 0)) & 0xFFFF,
                "epsilon": entry.get("epsilon"),
                "min_raw": int(entry.get("min_raw", 0)) & 0xFFFF,
                "min": entry.get("min"),
                "max_raw": int(entry.get("max_raw", 0)) & 0xFFFF,
                "max": entry.get("max"),
                "persist_key": int(entry.get("persist_key", 0)) & 0xFFFF,
                "reserved": int(entry.get("reserved", 0)) & 0xFFFF,
            }
            new_values[key] = record

        for entry in commands_block:
            if not isinstance(entry, dict):
                raise ValueError("metadata_command_invalid")
            try:
                group_id = int(entry.get("group_id"))
                cmd_id = int(entry.get("cmd_id"))
            except (TypeError, ValueError):
                raise ValueError("metadata_command_invalid")
            if not (0 <= group_id <= 0xFF) or not (0 <= cmd_id <= 0xFF):
                raise ValueError("metadata_command_range")
            key = (group_id, cmd_id)
            if key in new_commands:
                raise ValueError(f"metadata_command_duplicate:{group_id}:{cmd_id}")
            record = {
                "group_id": group_id,
                "cmd_id": cmd_id,
                "flags": int(entry.get("flags", 0)) & 0xFF,
                "auth_level": int(entry.get("auth_level", 0)) & 0xFF,
                "handler_offset": int(entry.get("handler_offset", 0)) & 0xFFFFFFFF,
                "name": entry.get("name"),
                "help": entry.get("help"),
                "reserved": int(entry.get("reserved", 0)) & 0xFFFFFFFF,
            }
            new_commands[key] = record

        for entry in mailboxes_block:
            if not isinstance(entry, dict):
                raise ValueError("metadata_mailbox_invalid")
            name = entry.get("name")
            if not isinstance(name, str) or not name.strip():
                raise ValueError("metadata_mailbox_name")
            target = name.strip()
            if target in new_mailboxes:
                raise ValueError(f"metadata_mailbox_duplicate:{target}")
            queue_depth = entry.get("queue_depth")
            capacity: Optional[int]
            if queue_depth in (None, "", 0):
                capacity = None
            else:
                try:
                    capacity = int(queue_depth)
                except (TypeError, ValueError):
                    raise ValueError(f"metadata_mailbox_capacity:{target}")
                if capacity <= 0:
                    capacity = None
            mode_mask = int(entry.get("flags", 0)) & 0xFFFF
            if mode_mask == 0:
                mode_mask = mbx_const.HSX_MBX_MODE_RDWR
            record = {
                "name": target,
                "queue_depth": entry.get("queue_depth"),
                "flags": entry.get("flags"),
                "mode": mode_mask,
                "reserved": entry.get("reserved"),
            }
            mailbox_bind_requests.append((target, capacity, mode_mask, record))

        bound_mailboxes: List[Tuple[str, Dict[str, Any]]] = []
        for target, capacity, mode_mask, record in mailbox_bind_requests:
            response = self.vm.mailbox_bind(pid, target, capacity=capacity, mode=mode_mask)
            if response.get("status") != "ok":
                error_text = response.get("error", "mailbox_bind_failed")
                raise RuntimeError(f"metadata_mailbox_bind_failed:{target}:{error_text}")
            bound_record = dict(record)
            bound_record["descriptor"] = response.get("descriptor")
            bound_record["capacity"] = response.get("capacity", capacity)
            bound_record["mode"] = response.get("mode", mode_mask)
            bound_mailboxes.append((target, bound_record))

        if new_values:
            self.value_registry[pid] = new_values
        else:
            self.value_registry.pop(pid, None)
        if new_commands:
            self.command_registry[pid] = new_commands
        else:
            self.command_registry.pop(pid, None)
        if bound_mailboxes:
            self.mailbox_registry[pid] = {name: info for name, info in bound_mailboxes}
        else:
            self.mailbox_registry.pop(pid, None)

        self.log(
            "info",
            "metadata_registered",
            pid=pid,
            values=len(new_values),
            commands=len(new_commands),
            mailboxes=len(bound_mailboxes),
        )

    def _normalise_pid_list(self, pid_lock: Any) -> List[int]:
        if pid_lock is None:
            return []
        values: Iterable[Any]
        if isinstance(pid_lock, (list, tuple, set)):
            values = pid_lock
        else:
            values = (pid_lock,)
        pids: List[int] = []
        for value in values:
            if value is None:
                continue
            try:
                pid_int = int(value)
            except (TypeError, ValueError):
                raise ValueError("pid_lock must be an integer or sequence of integers")
            if pid_int < 0:
                raise ValueError("pid_lock values must be non-negative")
            pids.append(pid_int)
        # ensure deterministic order and uniqueness
        return sorted(set(pids))

    def _coerce_task_state(self, value: Any, *, allow_none: bool = False) -> Optional[TaskState]:
        if value is None and allow_none:
            return None
        return TaskState.from_any(value)

    def _validate_state_transition(self, pid: int, previous: Optional[TaskState], new: TaskState) -> None:
        allowed = _ALLOWED_STATE_TRANSITIONS.get(previous, set())
        if new not in allowed:
            raise ValueError(f"invalid_state_transition:{previous}->{new}:pid={pid}")

    def _record_state_transition(self, pid: int, previous: Optional[TaskState], new: TaskState) -> None:
        self.last_state_transition[pid] = {
            "from": previous.value if isinstance(previous, TaskState) else None,
            "to": new.value,
            "ts": time.time(),
        }

    def _track_sleep(self, pid: int, deadline: Optional[Any]) -> None:
        if deadline is None:
            self._untrack_sleep(pid)
            return
        try:
            deadline_f = float(deadline)
        except (TypeError, ValueError):
            self._untrack_sleep(pid)
            return
        self.sleeping_deadlines[pid] = deadline_f
        heapq.heappush(self.sleeping_heap, (deadline_f, pid))

    def _untrack_sleep(self, pid: int) -> None:
        self.sleeping_deadlines.pop(pid, None)

    def _advance_sleeping_tasks(self) -> None:
        now = time.monotonic()
        changed = False
        while self.sleeping_heap:
            deadline, pid = self.sleeping_heap[0]
            if deadline > now:
                break
            heapq.heappop(self.sleeping_heap)
            current = self.sleeping_deadlines.get(pid)
            if current is None or current != deadline:
                continue
            self.sleeping_deadlines.pop(pid, None)
            task = self.tasks.get(pid)
            if task is not None:
                task["state"] = "ready"
                task["sleep_pending"] = False
                task.pop("sleep_pending_ms", None)
                task.pop("sleep_deadline", None)
            state_entry = self.task_states.get(pid)
            if isinstance(state_entry, dict):
                ctx = state_entry.get("context", {})
                if isinstance(ctx, dict):
                    ctx["state"] = "ready"
                    ctx.pop("sleep_pending_ms", None)
                    ctx.pop("sleep_deadline", None)
                    state_entry["context"] = ctx
            self._set_task_state_pending(pid, "sleep_wake", target_state="ready", ts=time.time(), force=True)
            changed = True
        if changed:
            self.auto_event.set()

    def _next_sleep_deadline(self) -> Optional[float]:
        while self.sleeping_heap:
            deadline, pid = self.sleeping_heap[0]
            current = self.sleeping_deadlines.get(pid)
            if current is None or current != deadline:
                heapq.heappop(self.sleeping_heap)
                continue
            return deadline
        return None

    def _update_scheduler_context(self, **fields: Any) -> None:
        if not fields:
            return
        context = self._pending_scheduler_context or {}
        for key, value in fields.items():
            if value is None:
                continue
            context[key] = value
        self._pending_scheduler_context = context or None

    def _assert_context_isolation(self, pid: int, context: Dict[str, Any], state: TaskState) -> None:
        if state not in {TaskState.READY, TaskState.RUNNING, TaskState.WAIT_MBX, TaskState.SLEEPING}:
            return
        if "regs" in context:
            self.log("error", "context_isolation_violation", pid=pid, field="regs_present")
            raise AssertionError(f"context_isolation:pid={pid}:context_regs_present")
        reg_base = self._optional_int(context.get("reg_base"))
        stack_base = self._optional_int(context.get("stack_base"))
        stack_limit = self._optional_int(context.get("stack_limit"))
        stack_size = self._optional_int(context.get("stack_size"))
        if not reg_base:
            self.log("error", "context_isolation_violation", pid=pid, field="reg_base", state=state.value)
            raise AssertionError(f"context_isolation:pid={pid}:reg_base_missing")
        if not stack_base:
            self.log("error", "context_isolation_violation", pid=pid, field="stack_base", state=state.value)
            raise AssertionError(f"context_isolation:pid={pid}:stack_base_missing")
        if stack_limit is None and stack_size is None:
            self.log(
                "error",
                "context_isolation_violation",
                pid=pid,
                field="stack_limit",
                stack_base=stack_base,
                stack_limit=stack_limit,
                stack_size=stack_size,
                state=state.value,
            )
            raise AssertionError(f"context_isolation:pid={pid}:stack_limit_invalid")

    def _session_payload(self, session: SessionRecord) -> Dict[str, Any]:
        if not session.pid_locks:
            pid_lock_repr: Optional[Any] = None
        elif len(session.pid_locks) == 1:
            pid_lock_repr = session.pid_locks[0]
        else:
            pid_lock_repr = list(session.pid_locks)
        payload = {
            "id": session.session_id,
            "client": session.client,
            "heartbeat_s": session.heartbeat_s,
            "features": list(session.features),
            "max_events": session.max_events,
            "pid_lock": pid_lock_repr,
        }
        if session.warnings:
            payload["warnings"] = list(session.warnings)
        return payload

    def session_open(
        self,
        *,
        client: Optional[str] = None,
        capabilities: Optional[Dict[str, Any]] = None,
        pid_lock: Any = None,
        heartbeat_s: Optional[int] = None,
    ) -> Dict[str, Any]:
        now = time.time()
        lock_targets = self._normalise_pid_list(pid_lock)
        caps = capabilities or {}
        requested_features = caps.get("features") or []
        if not isinstance(requested_features, (list, tuple)):
            raise ValueError("capabilities.features must be a list when provided")
        features: List[str] = []
        warnings: List[str] = []
        for feature in requested_features:
            feature_name = str(feature)
            if feature_name in self.session_supported_features:
                features.append(feature_name)
            else:
                warnings.append(f"unsupported_feature:{feature_name}")
        max_events_raw = caps.get("max_events")
        if max_events_raw is None:
            max_events = self.session_events_default
        else:
            try:
                max_events = int(max_events_raw)
            except (TypeError, ValueError):
                raise ValueError("capabilities.max_events must be an integer when provided")
            if max_events <= 0:
                raise ValueError("capabilities.max_events must be positive")
            if max_events < 2:
                warnings.append("max_events_clamped:2")
                max_events = 2
            if max_events > self.session_events_max:
                warnings.append(f"max_events_clamped:{self.session_events_max}")
                max_events = self.session_events_max
        if heartbeat_s is None:
            heartbeat = self.session_heartbeat_default
        else:
            try:
                heartbeat = int(heartbeat_s)
            except (TypeError, ValueError):
                raise ValueError("heartbeat_s must be an integer when provided")
            if heartbeat < self.session_heartbeat_min:
                warnings.append(f"heartbeat_clamped:{self.session_heartbeat_min}")
                heartbeat = self.session_heartbeat_min
            elif heartbeat > self.session_heartbeat_max:
                warnings.append(f"heartbeat_clamped:{self.session_heartbeat_max}")
                heartbeat = self.session_heartbeat_max
        session_id = str(uuid.uuid4())
        with self.session_lock:
            for pid in lock_targets:
                owner = self.pid_locks.get(pid)
                if owner is not None:
                    raise SessionError(f"pid_locked:{pid}")
            record = SessionRecord(
                session_id=session_id,
                client=str(client or ""),
                features=features,
                max_events=max_events,
                pid_locks=list(lock_targets),
                heartbeat_s=heartbeat,
                warnings=list(warnings),
                created_at=now,
                last_seen=now,
            )
            self.sessions[session_id] = record
            for pid in lock_targets:
                self.pid_locks[pid] = session_id
        self.log("info", "session opened", session_id=session_id, client=client or "", pid_locks=lock_targets)
        return self._session_payload(record)

    def _get_session(self, session_id: str) -> SessionRecord:
        with self.session_lock:
            record = self.sessions.get(session_id)
            if record is None:
                raise SessionError("session_required")
            return record

    def touch_session(self, session_id: str) -> SessionRecord:
        with self.session_lock:
            record = self.sessions.get(session_id)
            if record is None:
                raise SessionError("session_required")
            record.last_seen = time.time()
            return record

    def session_keepalive(self, session_id: str) -> None:
        record = self.touch_session(session_id)
        self.log("debug", "session keepalive", session_id=record.session_id)

    def _release_session_locks(self, session: SessionRecord) -> None:
        with self.session_lock:
            for pid in list(session.pid_locks):
                owner = self.pid_locks.get(pid)
                if owner == session.session_id:
                    self.pid_locks.pop(pid, None)

    def _close_session(self, session_id: str, reason: str) -> bool:
        with self.session_lock:
            record = self.sessions.pop(session_id, None)
            if record is None:
                return False
        self._release_session_locks(record)
        self.log("info", "session closed", session_id=session_id, reason=reason, pid_locks=list(record.pid_locks))
        self.events_session_disconnected(session_id)
        return True

    def session_close(self, session_id: str) -> None:
        if not self._close_session(session_id, reason="client_close"):
            raise SessionError("session_required")

    def prune_sessions(self) -> None:
        now = time.time()
        if (now - self._last_session_prune) < self._session_prune_interval:
            return
        self._last_session_prune = now
        expired: List[str] = []
        with self.session_lock:
            for session_id, record in list(self.sessions.items()):
                if (now - record.last_seen) > record.heartbeat_s:
                    expired.append(session_id)
        for session_id in expired:
            self._close_session(session_id, reason="timeout")

    def ensure_pid_access(self, pid: int, session_id: Optional[str]) -> None:
        with self.session_lock:
            owner = self.pid_locks.get(pid)
        if owner is None:
            return
        if session_id is None or owner != session_id:
            raise SessionError(f"pid_locked:{pid}")

    @staticmethod
    def _coerce_int(value: Any) -> int:
        if isinstance(value, int):
            return value
        if isinstance(value, str):
            return int(value, 0)
        raise ValueError(f"expected integer-compatible value, got {value!r}")

    @staticmethod
    def _optional_int(value: Any) -> Optional[int]:
        if value is None:
            return None
        try:
            return ExecutiveState._coerce_int(value)
        except (ValueError, TypeError):
            return None

    def _vm_debug(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        response = self.vm.request(payload)
        if response.get("status") != "ok":
            raise RuntimeError(response.get("error", "debug error"))
        block = response.get("debug")
        return block if isinstance(block, dict) else {}

    def _ensure_debug_session(self, pid: int) -> None:
        if pid in self.debug_attached:
            return
        attach_payload = {"cmd": "dbg", "op": "attach", "pid": pid}
        with self.lock:
            debug = self._vm_debug(attach_payload)
        breakpoints = debug.get("breakpoints", []) if isinstance(debug, dict) else []
        if isinstance(breakpoints, list):
            self.breakpoints[pid] = {self._coerce_int(addr) & 0xFFFF for addr in breakpoints}
        else:
            self.breakpoints[pid] = set()
        self.debug_attached.add(pid)

    def _detach_debug_session(self, pid: int) -> None:
        if pid not in self.debug_attached:
            self.breakpoints.pop(pid, None)
            return
        detach_payload = {"cmd": "dbg", "op": "detach", "pid": pid}
        try:
            with self.lock:
                self._vm_debug(detach_payload)
        except Exception:
            pass
        self.debug_attached.discard(pid)
        self.breakpoints.pop(pid, None)

    def _extract_breakpoints(self, pid: int, debug_block: Dict[str, Any]) -> List[int]:
        raw = debug_block.get("breakpoints") if isinstance(debug_block, dict) else []
        result: List[int] = []
        if isinstance(raw, list):
            for item in raw:
                try:
                    result.append(self._coerce_int(item) & 0xFFFF)
                except (TypeError, ValueError):
                    continue
        self.breakpoints[pid] = set(result)
        return sorted(result)

    def breakpoint_list(self, pid: int) -> Dict[str, Any]:
        self.get_task(pid)
        self._ensure_debug_session(pid)
        payload = {"cmd": "dbg", "op": "bp", "pid": pid, "action": "list"}
        with self.lock:
            debug = self._vm_debug(payload)
        breakpoints = self._extract_breakpoints(pid, debug)
        return {"pid": pid, "breakpoints": breakpoints}

    def breakpoint_add(self, pid: int, addr: int) -> Dict[str, Any]:
        self.get_task(pid)
        self._ensure_debug_session(pid)
        addr_int = self._coerce_int(addr) & 0xFFFF
        payload = {"cmd": "dbg", "op": "bp", "pid": pid, "action": "add", "addr": addr_int}
        with self.lock:
            debug = self._vm_debug(payload)
        breakpoints = self._extract_breakpoints(pid, debug)
        self.log("info", "breakpoint added", pid=pid, addr=addr_int)
        return {"pid": pid, "breakpoints": breakpoints}

    def breakpoint_clear(self, pid: int, addr: int) -> Dict[str, Any]:
        self.get_task(pid)
        self._ensure_debug_session(pid)
        addr_int = self._coerce_int(addr) & 0xFFFF
        payload = {"cmd": "dbg", "op": "bp", "pid": pid, "action": "remove", "addr": addr_int}
        with self.lock:
            debug = self._vm_debug(payload)
        breakpoints = self._extract_breakpoints(pid, debug)
        self.log("info", "breakpoint removed", pid=pid, addr=addr_int)
        return {"pid": pid, "breakpoints": breakpoints}

    def breakpoint_clear_all(self, pid: int) -> Dict[str, Any]:
        # ensure session and current snapshot
        info = self.breakpoint_list(pid)
        existing = list(info.get("breakpoints", []))
        for addr in existing:
            payload = {"cmd": "dbg", "op": "bp", "pid": pid, "action": "remove", "addr": addr}
            with self.lock:
                self._vm_debug(payload)
        payload = {"cmd": "dbg", "op": "bp", "pid": pid, "action": "list"}
        with self.lock:
            debug = self._vm_debug(payload)
        breakpoints = self._extract_breakpoints(pid, debug)
        self.log("info", "breakpoints cleared", pid=pid)
        return {"pid": pid, "breakpoints": breakpoints}

    def _handle_breakpoint_hit(self, pid: int, pc: int, *, phase: str) -> Dict[str, Any]:
        self.log("info", "breakpoint hit", pid=pid, pc=pc, phase=phase)
        self.stop_auto()
        self._set_task_state_pending(
            pid,
            "debug_break",
            target_state="paused",
            details={"pc": pc, "phase": phase},
            ts=time.time(),
        )
        try:
            self.pause_task(pid)
        except Exception as exc:
            self.log("error", "pause failed after breakpoint", pid=pid, error=str(exc))
        event = self.emit_event(
            "debug_break",
            pid=pid,
            data={"pc": pc, "phase": phase, "reason": "breakpoint"},
        )
        return event

    def _check_breakpoint_before_step(self, pid: Optional[int]) -> Optional[Dict[str, Any]]:
        if pid is None:
            return None
        bp_set = self.breakpoints.get(pid)
        if not bp_set:
            return None
        with self.lock:
            regs = self.vm.read_regs(pid=pid)
        pc = regs.get("pc")
        if not isinstance(pc, int):
            return None
        if (pc & 0xFFFF) in bp_set:
            return self._handle_breakpoint_hit(pid, pc, phase="pre")
        return None

    def _check_breakpoint_after_step(self, requested_pid: Optional[int], result: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if requested_pid is not None:
            target_pid = requested_pid
        else:
            current = result.get("current_pid")
            target_pid = current if isinstance(current, int) else None
        if target_pid is None:
            return None
        bp_set = self.breakpoints.get(target_pid)
        if not bp_set:
            return None
        with self.lock:
            regs = self.vm.read_regs(pid=target_pid)
        pc = regs.get("pc")
        if not isinstance(pc, int):
            return None
        if (pc & 0xFFFF) in bp_set:
            return self._handle_breakpoint_hit(target_pid, pc, phase="post")
        return None

    def _read_stack_words(self, pid: int, address: int, count: int) -> Optional[List[int]]:
        length = max(0, count) * 4
        if length == 0:
            return []
        try:
            with self.lock:
                raw = self.vm.read_mem(address, length, pid=pid)
        except Exception as exc:
            self.log("error", "stack_read_failed", pid=pid, address=address, error=str(exc))
            return None
        if isinstance(raw, str):
            try:
                raw = bytes.fromhex(raw)
            except ValueError:
                raw = raw.encode("utf-8", errors="ignore")
        if not isinstance(raw, (bytes, bytearray)):
            return None
        if len(raw) < length:
            raw = raw.ljust(length, b"\x00")
        return [int.from_bytes(raw[i * 4:(i + 1) * 4], "little") for i in range(count)]

    def _resolve_symbol_path(self, pid: int, *, program: Optional[str], override: Optional[str]) -> Optional[Path]:
        if override:
            candidate = Path(override)
            if not candidate.is_absolute():
                base = Path(program).parent if program else Path.cwd()
                candidate = (base / candidate).resolve()
            return candidate if candidate.exists() else candidate
        if not program:
            return None
        program_path = Path(program)
        sym_path = program_path.with_suffix(".sym")
        return sym_path

    @staticmethod
    def _extract_symbol_entries(data: Any) -> List[Dict[str, Any]]:
        entries: List[Dict[str, Any]] = []

        def normalise(name: str, info: Dict[str, Any]) -> Dict[str, Any]:
            address = (
                info.get("address")
                or info.get("addr")
                or info.get("abs_addr")
                or info.get("absolute")
                or info.get("offset")
                or 0
            )
            try:
                address_int = int(address)
            except (TypeError, ValueError):
                address_int = 0
            entry = {
                "name": name,
                "address": address_int & 0xFFFFFFFF,
                "size": info.get("size"),
                "type": info.get("type") or info.get("kind") or info.get("section"),
                "file": info.get("file") or info.get("source"),
                "line": info.get("line"),
            }
            return entry

        if isinstance(data, dict):
            sym_block = data.get("symbols")
            if isinstance(sym_block, dict):
                for name, info in sym_block.items():
                    if isinstance(info, dict):
                        entries.append(normalise(str(name), info))
            elif isinstance(sym_block, list):
                for info in sym_block:
                    if isinstance(info, dict):
                        name = info.get("name") or info.get("symbol")
                        if not name:
                            continue
                        entries.append(normalise(str(name), info))
            functions = data.get("functions")
            if isinstance(functions, list):
                for info in functions:
                    if isinstance(info, dict):
                        name = info.get("name")
                        if name:
                            info.setdefault("type", "function")
                            entries.append(normalise(str(name), info))
        return entries

    @staticmethod
    def _extract_line_entries(data: Any) -> List[Dict[str, Any]]:
        line_block = None
        if isinstance(data, dict):
            for key in ("lines", "line_table", "line_map"):
                if key in data:
                    line_block = data[key]
                    break
        lines: List[Dict[str, Any]] = []
        if isinstance(line_block, list):
            for item in line_block:
                if isinstance(item, dict):
                    address = item.get("address")
                    try:
                        address_int = int(address)
                    except (TypeError, ValueError):
                        continue
                    lines.append(
                        {
                            "address": address_int & 0xFFFFFFFF,
                            "file": item.get("file") or item.get("source"),
                            "line": item.get("line"),
                        }
                    )
        elif isinstance(line_block, dict):
            for key, value in line_block.items():
                try:
                    address_int = int(key)
                except (TypeError, ValueError):
                    continue
                if isinstance(value, dict):
                    lines.append(
                        {
                            "address": address_int & 0xFFFFFFFF,
                            "file": value.get("file") or value.get("source"),
                            "line": value.get("line"),
                        }
                    )
        return lines

    def _parse_symbol_file(self, path: Path) -> Dict[str, Any]:
        data = json.loads(path.read_text(encoding="utf-8"))
        entries = self._extract_symbol_entries(data)
        lines = self._extract_line_entries(data)
        by_name = {entry["name"]: entry for entry in entries if entry.get("name")}
        addresses = sorted(entries, key=lambda item: item.get("address", 0))
        line_index = sorted(lines, key=lambda item: item.get("address", 0))
        return {
            "path": str(path),
            "symbols": entries,
            "by_name": by_name,
            "addresses": addresses,
            "lines": line_index,
        }

    def load_symbols_for_pid(
        self,
        pid: int,
        *,
        program: Optional[str] = None,
        override: Optional[str] = None,
    ) -> Dict[str, Any]:
        self.get_task(pid)
        sym_path = self._resolve_symbol_path(pid, program=program, override=override)
        if sym_path is None:
            self.symbol_tables.pop(pid, None)
            return {"pid": pid, "loaded": False, "path": None}
        try:
            table = self._parse_symbol_file(sym_path)
            with self.symbol_cache_lock:
                self.symbol_tables[pid] = table
            self.log("info", "symbols loaded", pid=pid, path=str(sym_path))
            return {"pid": pid, "loaded": True, "path": str(sym_path), "count": len(table["symbols"])}
        except FileNotFoundError:
            self.log("warning", "symbol file missing", pid=pid, path=str(sym_path))
            with self.symbol_cache_lock:
                self.symbol_tables.pop(pid, None)
            return {"pid": pid, "loaded": False, "path": str(sym_path)}
        except Exception as exc:
            self.log("error", "symbol load failed", pid=pid, path=str(sym_path), error=str(exc))
            with self.symbol_cache_lock:
                self.symbol_tables.pop(pid, None)
            return {"pid": pid, "loaded": False, "path": str(sym_path), "error": str(exc)}

    def symbol_info(self, pid: int) -> Dict[str, Any]:
        self.get_task(pid)
        with self.symbol_cache_lock:
            table = self.symbol_tables.get(pid)
            if not table:
                return {"pid": pid, "loaded": False}
            return {
                "pid": pid,
                "loaded": True,
                "path": table.get("path"),
                "count": len(table.get("symbols", [])),
            }

    def symbol_lookup_name(self, pid: int, name: str) -> Optional[Dict[str, Any]]:
        with self.symbol_cache_lock:
            table = self.symbol_tables.get(pid)
            if not table:
                return None
            entry = table["by_name"].get(name)
            if not entry:
                return None
            return dict(entry)

    def symbol_lookup_addr(self, pid: int, address: int) -> Optional[Dict[str, Any]]:
        with self.symbol_cache_lock:
            table = self.symbol_tables.get(pid)
            if not table:
                return None
            addr_list = table["addresses"]
            if not addr_list:
                return None
            addresses = [entry["address"] for entry in addr_list]
            idx = bisect.bisect_right(addresses, address) - 1
            if idx < 0:
                return None
            entry = dict(addr_list[idx])
            entry["offset"] = address - entry.get("address", 0)
            return entry

    def symbol_lookup_line(self, pid: int, address: int) -> Optional[Dict[str, Any]]:
        with self.symbol_cache_lock:
            table = self.symbol_tables.get(pid)
            if not table:
                return None
            lines = table.get("lines", [])
            if not lines:
                return None
            addresses = [item["address"] for item in lines]
            idx = bisect.bisect_right(addresses, address) - 1
            if idx < 0:
                return None
            return dict(lines[idx])

    def symbols_list(
        self,
        pid: int,
        *,
        kind: Optional[str] = None,
        offset: int = 0,
        limit: Optional[int] = None,
    ) -> Dict[str, Any]:
        self.get_task(pid)
        try:
            offset = max(0, int(offset))
        except (TypeError, ValueError):
            offset = 0
        try:
            limit_value = int(limit) if limit is not None else None
        except (TypeError, ValueError):
            limit_value = None
        if limit_value is not None:
            limit_value = max(1, min(limit_value, 256))
        kind_normalised = (kind or "all").lower()
        allowed_kinds = {"functions", "variables", "all"}
        if kind_normalised not in allowed_kinds:
            raise ValueError("symbols.list type must be 'functions', 'variables', or 'all'")
        with self.symbol_cache_lock:
            table = self.symbol_tables.get(pid)
            if not table:
                return {
                    "pid": pid,
                    "count": 0,
                    "offset": 0,
                    "limit": limit_value,
                    "type": kind_normalised,
                    "symbols": [],
                }
            entries = list(table.get("symbols", []))
        if kind_normalised != "all":
            if kind_normalised == "functions":
                entries = [item for item in entries if str(item.get("type") or "").lower() == "function"]
            else:
                entries = [item for item in entries if str(item.get("type") or "").lower() != "function"]
        entries.sort(key=lambda item: item.get("address", 0))
        total = len(entries)
        start = min(offset, total)
        end = total if limit_value is None else min(total, start + limit_value)
        view = [dict(entry) for entry in entries[start:end]]
        return {
            "pid": pid,
            "count": total,
            "offset": start,
            "limit": limit_value,
            "type": kind_normalised,
            "symbols": view,
        }

    def memory_regions(self, pid: int) -> Dict[str, Any]:
        task = self.get_task(pid)
        layout = dict(self.memory_layouts.get(pid, {}))
        state_entry = self.task_states.get(pid, {})
        context = state_entry.get("context", {}) if isinstance(state_entry, dict) else {}

        regions: List[Dict[str, Any]] = []

        def _to_int(value: Any) -> Optional[int]:
            if value is None:
                return None
            try:
                return int(value) & 0xFFFFFFFF
            except (TypeError, ValueError):
                return None

        def _add_region(
            name: str,
            start: Optional[int],
            length: Optional[int],
            *,
            kind: str,
            permissions: str,
            source: Optional[str] = None,
            details: Optional[Dict[str, Any]] = None,
        ) -> None:
            if start is None or length is None:
                return
            if length <= 0:
                return
            start &= 0xFFFFFFFF
            end = start + length
            if VM_ADDRESS_SPACE_SIZE:
                max_len = VM_ADDRESS_SPACE_SIZE - (start & 0xFFFF)
                if max_len <= 0:
                    return
                length = min(length, max_len)
                end = start + length
            region: Dict[str, Any] = {
                "name": name,
                "type": kind,
                "start": start & 0xFFFF,
                "end": end & 0xFFFF,
                "length": int(length),
                "permissions": permissions,
            }
            if source:
                region["source"] = source
            if details:
                region["details"] = details
            regions.append(region)

        code_len = _to_int(layout.get("code_len"))
        if code_len:
            _add_region(
                "code",
                0,
                code_len,
                kind="code",
                permissions="rx",
                source="hxe",
                details={"entry": layout.get("entry")},
            )

        ro_len = _to_int(layout.get("ro_len"))
        if ro_len:
            _add_region(
                "rodata",
                RODATA_BASE,
                ro_len,
                kind="rodata",
                permissions="r",
                source="hxe",
            )

        bss_size = _to_int(layout.get("bss"))
        if bss_size:
            bss_base = RODATA_BASE + (ro_len or 0)
            _add_region(
                "bss",
                bss_base,
                bss_size,
                kind="bss",
                permissions="rw",
                source="hxe",
            )

        reg_base = _to_int(context.get("reg_base"))
        if reg_base:
            _add_region(
                "registers",
                reg_base,
                REGISTER_BANK_BYTES,
                kind="registers",
                permissions="rw",
                source="vm",
            )

        stack_base = _to_int(context.get("stack_base"))
        stack_size = _to_int(context.get("stack_size"))
        if stack_base and stack_size:
            sp_value = _to_int(context.get("sp"))
            details = {"sp": sp_value} if sp_value is not None else None
            _add_region(
                "stack",
                stack_base,
                stack_size,
                kind="stack",
                permissions="rw",
                source="vm",
                details=details,
            )

        regions.sort(key=lambda item: (item.get("start", 0), item.get("name", "")))
        return {
            "pid": pid,
            "program": task.get("program"),
            "regions": regions,
            "layout": layout,
        }

    def watch_add(
        self,
        pid: int,
        expr: str,
        *,
        watch_type: Optional[str] = None,
        length: Optional[int] = None,
    ) -> Dict[str, Any]:
        self.get_task(pid)
        expr_text = str(expr).strip()
        if not expr_text:
            raise ValueError("watch expression must be non-empty")
        resolved = self._resolve_watch_expression(pid, expr_text, watch_type)
        length_value = 4 if length is None else max(1, int(length))
        try:
            address = resolved["address"] & 0xFFFF
            raw = self.vm.read_mem(address, length_value, pid=pid)
        except Exception as exc:
            raise ValueError(f"watch read failed: {exc}") from exc
        watch_id = self._next_watch_id
        self._next_watch_id += 1
        watch_record = {
            "id": watch_id,
            "pid": pid,
            "expr": expr_text,
            "type": resolved["type"],
            "address": address,
            "length": length_value,
            "symbol": resolved.get("symbol"),
            "description": resolved.get("description"),
            "last_value": bytes(raw),
        }
        self.watchers.setdefault(pid, {})[watch_id] = watch_record
        return self._export_watch_record(watch_record)

    def watch_remove(self, pid: int, watch_id: int) -> Dict[str, Any]:
        watch_map = self.watchers.get(pid)
        if not watch_map or watch_id not in watch_map:
            raise ValueError(f"unknown watch {watch_id} for pid {pid}")
        record = watch_map.pop(watch_id)
        if not watch_map:
            self.watchers.pop(pid, None)
        return self._export_watch_record(record)

    def watch_list(self, pid: int) -> Dict[str, Any]:
        watch_map = self.watchers.get(pid, {})
        items = [self._export_watch_record(record) for record in sorted(watch_map.values(), key=lambda item: item["id"])]
        return {"pid": pid, "count": len(items), "watches": items}

    def _resolve_watch_expression(
        self,
        pid: int,
        expr: str,
        watch_type: Optional[str],
    ) -> Dict[str, Any]:
        expr_type = (watch_type or "").strip().lower()
        address: Optional[int] = None
        symbol_name: Optional[str] = None
        description: Optional[str] = None
        if expr_type in {"addr", "address"}:
            try:
                address = int(expr, 0)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"invalid address '{expr}'") from exc
            expr_type = "address"
        elif expr_type in {"symbol", "name"}:
            entry = self.symbol_lookup_name(pid, expr)
            if not entry:
                raise ValueError(f"symbol '{expr}' not found for pid {pid}")
            address = int(entry.get("address", 0))
            symbol_name = entry.get("name")
            description = entry.get("name")
            expr_type = "symbol"
        else:
            try:
                address = int(expr, 0)
                expr_type = "address"
            except (TypeError, ValueError):
                entry = self.symbol_lookup_name(pid, expr)
                if not entry:
                    raise ValueError(f"symbol '{expr}' not found for pid {pid}")
                address = int(entry.get("address", 0))
                symbol_name = entry.get("name")
                description = entry.get("name")
                expr_type = "symbol"
        if address is None:
            raise ValueError("unable to resolve watch expression")
        return {
            "type": expr_type,
            "address": address & 0xFFFF,
            "symbol": symbol_name,
            "description": description,
        }

    def _export_watch_record(self, record: Dict[str, Any]) -> Dict[str, Any]:
        data = {
            "id": record["id"],
            "pid": record["pid"],
            "expr": record["expr"],
            "type": record["type"],
            "address": record["address"],
            "length": record["length"],
            "value": record["last_value"].hex(),
        }
        if record.get("symbol"):
            data["symbol"] = record["symbol"]
        if record.get("description"):
            data["description"] = record["description"]
        return data

    def _check_watches(self, pid: Optional[int] = None) -> List[Dict[str, Any]]:
        events: List[Dict[str, Any]] = []
        if not self.watchers:
            return events
        if pid is not None:
            pids = [pid]
        else:
            pids = list(self.watchers.keys())
        for watch_pid in pids:
            watch_map = self.watchers.get(watch_pid)
            if not watch_map:
                continue
            for watch_id, record in list(watch_map.items()):
                try:
                    addr = int(record.get("address", 0)) & 0xFFFF
                    data = self.vm.read_mem(addr, record["length"], pid=watch_pid)
                except Exception as exc:
                    self.log("warning", "watch read failed", pid=watch_pid, watch_id=watch_id, error=str(exc))
                    continue
                current = bytes(data)
                if current == record["last_value"]:
                    continue
                payload = {
                    "watch_id": watch_id,
                    "address": record["address"],
                    "expr": record["expr"],
                    "type": record["type"],
                    "length": record["length"],
                    "old": record["last_value"].hex(),
                    "new": current.hex(),
                }
                if record.get("symbol"):
                    payload["symbol"] = record["symbol"]
                record["last_value"] = current
                event = self.emit_event("watch_update", pid=watch_pid, data=payload)
                events.append(event)
        return events

    @staticmethod
    def _decode_instruction_word(word: int) -> Dict[str, int]:
        op = (word >> 24) & 0xFF
        rd = (word >> 20) & 0x0F
        rs1 = (word >> 16) & 0x0F
        rs2 = (word >> 12) & 0x0F
        imm_raw = word & 0x0FFF
        imm = imm_raw
        if imm & 0x800:
            imm -= 0x1000
        return {
            "op": op,
            "rd": rd,
            "rs1": rs1,
            "rs2": rs2,
            "imm": imm,
            "imm_raw": imm_raw,
        }

    def _disassemble_bytes(
        self,
        pid: int,
        data: bytes,
        base_addr: int,
        count: int,
        *,
        reg_values: Optional[List[int]] = None,
    ) -> Tuple[List[Dict[str, Any]], bool, int]:
        listing: List[Dict[str, Any]] = []
        offset = 0
        truncated = False
        consumed = 0
        unsigned_ops = {0x21, 0x22, 0x23, 0x30, 0x7F}
        data_len = len(data)
        for index in range(count):
            if offset + 4 > data_len:
                truncated = True
                break
            word = int.from_bytes(data[offset:offset + 4], "big")
            decoded = self._decode_instruction_word(word)
            opcode = decoded["op"]
            mnemonic = disasm_util.OPCODE_NAMES.get(opcode, f"0x{opcode:02X}")
            size = disasm_util.instruction_size(mnemonic)
            next_word = None
            if size == 8:
                if offset + 8 > data_len:
                    truncated = True
                    break
                next_word = int.from_bytes(data[offset + 4:offset + 8], "big")
            imm_effective = decoded["imm_raw"] if opcode in unsigned_ops else decoded["imm"]
            operands = disasm_util.format_operands(
                mnemonic,
                decoded["rd"],
                decoded["rs1"],
                decoded["rs2"],
                imm=imm_effective,
                imm_raw=decoded["imm_raw"],
                reg_values=reg_values,
                next_word=next_word,
                pc=base_addr + offset,
            )
            inst_addr = (base_addr + offset) & 0xFFFFFFFF
            entry: Dict[str, Any] = {
                "index": index,
                "pc": inst_addr,
                "size": size,
                "word": word,
                "mnemonic": mnemonic,
                "rd": decoded["rd"],
                "rs1": decoded["rs1"],
                "rs2": decoded["rs2"],
                "imm": decoded["imm"],
                "imm_raw": decoded["imm_raw"],
                "operands": operands,
                "bytes": data[offset:offset + size].hex(),
            }
            if next_word is not None:
                entry["extended_word"] = next_word
            if mnemonic in {"JMP", "JZ", "JNZ", "CALL"}:
                target = imm_effective & 0xFFFFFFFF
                entry["target"] = target
                target_symbol = self.symbol_lookup_addr(pid, target)
                if target_symbol:
                    entry["target_symbol"] = dict(target_symbol)
            listing.append(entry)
            offset += size
            consumed = offset
        if offset < data_len and len(listing) >= count:
            consumed = offset
        return listing, truncated, consumed

    def disasm_read(
        self,
        pid: int,
        *,
        address: Optional[int] = None,
        count: Optional[int] = None,
        mode: Optional[str] = None,
    ) -> Dict[str, Any]:
        self.get_task(pid)
        try:
            count_value = 8 if count is None else int(count)
        except (TypeError, ValueError):
            raise ValueError("count must be an integer") from None
        count_value = max(1, min(count_value, 64))

        mode_value = (mode or "on-demand").strip().lower()
        if mode_value not in {"on-demand", "cached"}:
            raise ValueError("mode must be 'on-demand' or 'cached'")
        cache_enabled = mode_value == "cached"

        regs = self.request_dump_regs(pid)
        pc = regs.get("pc")
        if address is None:
            start_addr = int(pc) & 0xFFFFFFFF if isinstance(pc, int) else 0
        else:
            try:
                start_addr = int(address) & 0xFFFFFFFF
            except (TypeError, ValueError) as exc:
                raise ValueError("address must be integer") from exc

        cache_key = (start_addr, count_value)
        if cache_enabled:
            cache_for_pid = self.disasm_cache.get(pid, {})
            cached_entry = cache_for_pid.get(cache_key)
            if cached_entry:
                result = dict(cached_entry["result"])
                result["cached"] = True
                return result

        max_bytes = min(count_value * 8, 4096)
        try:
            with self.lock:
                raw = self.vm.read_mem(start_addr, max_bytes, pid=pid)
        except Exception as exc:
            raise ValueError(f"disassembly memory read failed: {exc}") from exc

        if isinstance(raw, str):
            try:
                raw_bytes = bytes.fromhex(raw)
            except ValueError:
                raw_bytes = raw.encode("utf-8", errors="ignore")
        elif isinstance(raw, (bytes, bytearray)):
            raw_bytes = bytes(raw)
        else:
            raise ValueError("unexpected memory payload from VM")

        reg_values = None
        regs_block = regs.get("regs")
        if isinstance(regs_block, list):
            reg_values = [int(val) & 0xFFFFFFFF for val in regs_block if isinstance(val, int)]

        instructions, truncated, consumed = self._disassemble_bytes(
            pid,
            raw_bytes,
            start_addr,
            count_value,
            reg_values=reg_values,
        )

        for entry in instructions:
            symbol = self.symbol_lookup_addr(pid, entry["pc"])
            if symbol:
                entry["symbol"] = dict(symbol)
            line = self.symbol_lookup_line(pid, entry["pc"])
            if line:
                entry["line"] = dict(line)
            offset = symbol.get("offset") if symbol else None
            if symbol and (offset is None or offset == 0):
                entry["label"] = symbol.get("name")

        result = {
            "pid": pid,
            "address": start_addr,
            "count": len(instructions),
            "requested": count_value,
            "mode": mode_value,
            "cached": False,
            "truncated": truncated,
            "bytes_read": consumed,
            "data": raw_bytes[:consumed].hex(),
            "instructions": instructions,
        }

        if cache_enabled:
            cache_for_pid = self.disasm_cache.setdefault(pid, {})
            cache_for_pid[cache_key] = {
                "result": dict(result),
                "timestamp": time.time(),
            }

        return result

    def stack_info(self, pid: int, *, max_frames: Optional[int] = None) -> Dict[str, Any]:
        self.get_task(pid)
        regs = self.request_dump_regs(pid)
        frames: List[Dict[str, Any]] = []
        max_frames = max_frames or self.default_stack_frames
        try:
            max_frames = max(1, min(int(max_frames), 64))
        except (TypeError, ValueError):
            max_frames = self.default_stack_frames

        errors: List[str] = []

        def _coerce_ptr(name: str, value: Any) -> Optional[int]:
            if value is None:
                return None
            try:
                return int(value) & 0xFFFFFFFF
            except (TypeError, ValueError):
                errors.append(f"invalid_{name}")
                return None

        stack_base = _coerce_ptr("stack_base", regs.get("stack_base")) or 0
        stack_size_raw = regs.get("stack_size", 0) or 0
        try:
            stack_size = int(stack_size_raw)
        except (TypeError, ValueError):
            errors.append("invalid_stack_size")
            stack_size = 0
        stack_limit = _coerce_ptr("stack_limit", regs.get("stack_limit")) or stack_base
        stack_low = min(stack_base, stack_limit)
        if stack_size > 0:
            stack_high = stack_base + stack_size
        else:
            stack_high = stack_low + 0x10000

        def _in_stack_range(ptr: Optional[int], *, allow_high: bool = False) -> bool:
            if ptr is None:
                return False
            if stack_low <= ptr < stack_high:
                return True
            if allow_high and ptr == stack_high:
                return True
            return False

        current_pc = _coerce_ptr("pc", regs.get("pc")) or 0
        sp_effective = _coerce_ptr("sp_effective", regs.get("sp_effective"))
        if sp_effective is None:
            sp_raw = _coerce_ptr("sp", regs.get("sp")) or 0
            if stack_base:
                sp_effective = (stack_base + (sp_raw & 0xFFFF)) & 0xFFFFFFFF
            else:
                sp_effective = sp_raw
        current_sp = sp_effective or 0
        start_sp = current_sp
        if not _in_stack_range(current_sp, allow_high=True):
            errors.append(f"sp_out_of_range:0x{current_sp:08X}")

        fp_candidates = [
            ("fp", regs.get("fp")),
            ("frame_pointer", regs.get("frame_pointer")),
            ("r7", regs.get("r7")),
            ("R7", regs.get("R7")),
        ]
        regs_block = regs.get("regs")
        if isinstance(regs_block, list) and len(regs_block) > 7:
            fp_candidates.append(("regs7", regs_block[7]))
        fp: Optional[int] = None
        for name, value in fp_candidates:
            fp = _coerce_ptr(name, value)
            if fp is not None:
                break

        initial_fp = fp
        if fp is not None and not _in_stack_range(fp):
            errors.append(f"fp_out_of_range:0x{fp:08X}")

        truncated = False
        seen_fps: set[int] = set()

        for depth in range(max_frames):
            frame_entry: Dict[str, Any] = {
                "index": depth,
                "pc": current_pc,
                "sp": current_sp,
                "fp": fp,
                "return_pc": None,
            }
            symbol = self.symbol_lookup_addr(pid, current_pc)
            if symbol:
                frame_entry["symbol"] = symbol
                frame_entry["func_name"] = symbol.get("name")
                frame_entry["func_addr"] = symbol.get("address")
                if symbol.get("offset") is not None:
                    frame_entry["func_offset"] = symbol.get("offset")
            line = self.symbol_lookup_line(pid, current_pc)
            if line:
                frame_entry["line"] = line
                if line.get("line") is not None:
                    frame_entry["line_num"] = line.get("line")
            frames.append(frame_entry)

            if fp is None or fp == 0:
                break
            if fp in seen_fps:
                errors.append(f"fp_cycle:0x{fp:08X}")
                truncated = True
                break
            seen_fps.add(fp)
            if fp % 4 != 0:
                errors.append(f"fp_unaligned:0x{fp:08X}")
                truncated = True
                break
            if not _in_stack_range(fp, allow_high=False):
                errors.append(f"fp_out_of_range:0x{fp:08X}")
                truncated = True
                break
            if fp + 8 > stack_high:
                errors.append(f"fp_frame_overflow:0x{fp:08X}")
                truncated = True
                break

            words = self._read_stack_words(pid, fp, 2)
            if not words or len(words) < 2:
                errors.append(f"stack_read_failed:0x{fp:08X}")
                truncated = True
                break
            prev_fp, return_pc = words
            prev_fp &= 0xFFFFFFFF
            return_pc &= 0xFFFFFFFF
            frame_entry["return_pc"] = return_pc
            if prev_fp == 0 and return_pc == 0:
                break
            current_sp = (fp + 8) & 0xFFFFFFFF
            current_pc = return_pc
            fp = prev_fp if prev_fp != 0 else None
            if fp is not None and not _in_stack_range(fp, allow_high=False):
                errors.append(f"fp_out_of_range:0x{fp:08X}")
                fp = None
                truncated = True
                break
        else:
            truncated = True
            errors.append("frame_limit_reached")

        return {
            "pid": pid,
            "frames": frames,
            "truncated": truncated,
            "errors": errors,
            "stack_base": stack_base,
            "stack_limit": stack_limit,
            "stack_low": stack_low,
            "stack_high": stack_high,
            "initial_sp": start_sp,
            "initial_fp": initial_fp,
        }

    def _next_event_seq(self) -> int:
        with self.event_lock:
            seq = self.event_seq
            self.event_seq += 1
            return seq

    def _build_event(
        self,
        event_type: str,
        *,
        pid: Optional[int] = None,
        data: Optional[Dict[str, Any]] = None,
        ts: Optional[float] = None,
        seq: Optional[int] = None,
    ) -> Dict[str, Any]:
        event = {
            "seq": seq if seq is not None else self._next_event_seq(),
            "ts": ts if ts is not None else time.time(),
            "type": event_type,
            "pid": pid,
            "data": data or {},
        }
        return event

    def _store_history(self, event: Dict[str, Any]) -> None:
        with self.event_lock:
            self.event_history.append(event)

    def emit_event(
        self,
        event_type: str,
        *,
        pid: Optional[int] = None,
        data: Optional[Dict[str, Any]] = None,
        ts: Optional[float] = None,
    ) -> Dict[str, Any]:
        event = self._build_event(event_type, pid=pid, data=data, ts=ts)
        self._store_history(event)
        self._broadcast_event(event)
        return event

    def _deliver_warning(self, subscription: EventSubscription, reason: str, **fields: Any) -> None:
        warning_event = self._build_event(
            "warning",
            pid=None,
            data={"reason": reason, **fields, "subscription": subscription.token},
        )
        # do not store warning-only events globally; they are session specific
        with subscription.condition:
            if not subscription.active:
                return
            subscription.queue.append(warning_event)
            pending = self._post_enqueue_locked(subscription, warning_event["seq"])
            subscription.condition.notify_all()
        # warnings are considered part of the backlog but should not recursively trigger new warnings
        # immediately, so skip back-pressure evaluation here.

    def _post_enqueue_locked(self, subscription: EventSubscription, seq: int) -> int:
        """Update delivery metrics after enqueuing an event while the subscription lock is held."""
        subscription.delivered_seq = max(subscription.delivered_seq, seq)
        pending = subscription.pending()
        if pending > subscription.high_water:
            subscription.high_water = pending
        subscription.last_delivery_ts = time.time()
        return pending

    def _apply_backpressure(self, subscription: EventSubscription, pending: Optional[int] = None) -> None:
        if not subscription.active:
            return
        pending_count = subscription.pending() if pending is None else pending
        now = time.time()
        if (now - subscription.created_at) < self.event_backpressure_grace:
            return
        warn_threshold = max(subscription.max_events * self.event_ack_warn_factor, self.event_ack_warn_floor)
        drop_threshold = max(subscription.max_events * self.event_ack_drop_factor, self.event_ack_drop_floor)
        if pending_count >= warn_threshold:
            if (now - subscription.last_warning_ts) >= self.event_slow_warning_interval:
                self._deliver_warning(
                    subscription,
                    "slow_consumer",
                    pending=pending_count,
                    high_water=subscription.high_water,
                    drops=subscription.drop_count,
                )
                subscription.last_warning_ts = now
                subscription.slow_warning_active = True
                if not subscription.slow_since:
                    subscription.slow_since = now
                subscription.slow_count += 1
        else:
            subscription.slow_warning_active = False
            subscription.slow_since = 0.0
        if pending_count >= drop_threshold:
            self.log(
                "warn",
                "events subscription dropped due to backpressure",
                session_id=subscription.session_id,
                token=subscription.token,
                pending=pending_count,
                last_ack=subscription.last_ack,
                delivered=subscription.delivered_seq,
                max_events=subscription.max_events,
                drops=subscription.drop_count,
            )
            self._deliver_warning(
                subscription,
                "slow_consumer_drop",
                pending=pending_count,
                high_water=subscription.high_water,
                drops=subscription.drop_count,
            )
            self.events_unsubscribe(token=subscription.token)

    def _broadcast_event(self, event: Dict[str, Any]) -> None:
        with self.event_lock:
            subscribers = list(self.event_subscriptions.values())
        for sub in subscribers:
            pending: Optional[int] = None
            with sub.condition:
                if not sub.active:
                    continue
                if not sub.matches(event):
                    continue
                if sub.max_events > 0 and len(sub.queue) >= sub.max_events:
                    dropped = sub.queue.popleft()
                    dropped_seq = dropped.get("seq", sub.last_ack)
                    sub.last_ack = max(sub.last_ack, dropped_seq)
                    sub.drop_count += 1
                    self.log(
                        "warn",
                        "events queue drop",
                        session_id=sub.session_id,
                        token=sub.token,
                        dropped_seq=dropped_seq,
                        drop_count=sub.drop_count,
                        max_events=sub.max_events,
                    )
                    self._deliver_warning(
                        sub,
                        "event_dropped",
                        dropped_seq=dropped_seq,
                        drops=sub.drop_count,
                    )
                    # ensure room after warning
                    if sub.max_events > 0 and len(sub.queue) >= sub.max_events:
                        sub.queue.popleft()
                sub.queue.append(event)
                pending = self._post_enqueue_locked(sub, event.get("seq", sub.delivered_seq))
                sub.condition.notify_all()
            if pending is not None:
                self._apply_backpressure(sub, pending)

    def _set_task_state_pending(
        self,
        pid: int,
        reason: str,
        *,
        target_state: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        ts: Optional[float] = None,
        force: bool = False,
    ) -> None:
        if not reason:
            return
        payload: Dict[str, Any] = {
            "reason": reason,
            "target_state": target_state,
            "details": dict(details) if isinstance(details, dict) else (details if details is None else {"value": details}),
            "ts": ts,
            "force": force,
        }
        self.task_state_pending[pid] = payload

    def _emit_task_state_event(
        self,
        pid: int,
        prev_state: Optional[str],
        new_state: Optional[str],
        *,
        reason: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        ts: Optional[float] = None,
        state_entry: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        if state_entry is None:
            state_entry = self.task_states.setdefault(pid, {})
        data: Dict[str, Any] = {
            "prev_state": prev_state,
            "new_state": new_state,
        }
        if reason is not None:
            data["reason"] = reason
        if details:
            data["details"] = details
        event = self.emit_event("task_state", pid=pid, data=data, ts=ts)
        state_entry["state"] = new_state
        if reason is not None:
            state_entry["last_reason"] = reason
        state_entry["last_state_ts"] = time.time()
        return event

    def _maybe_emit_scheduler_event(
        self,
        prev_snapshot: Dict[str, Any],
        *,
        context: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        context = context or {}
        prev_tasks_raw = prev_snapshot.get("tasks")
        prev_tasks: Dict[Any, Dict[str, Any]]
        if isinstance(prev_tasks_raw, dict):
            prev_tasks = prev_tasks_raw
        else:
            prev_tasks = {}

        def _fetch_task(tasks: Dict[Any, Dict[str, Any]], pid: Optional[int]) -> Optional[Dict[str, Any]]:
            if pid is None:
                return None
            entry = tasks.get(pid)
            if entry is None:
                entry = tasks.get(str(pid))
            if isinstance(entry, dict):
                return entry
            return None

        prev_pid = self._optional_int(context.get("prev_pid"))
        if prev_pid is None:
            prev_pid = self._optional_int(prev_snapshot.get("current_pid"))
        if prev_pid is None:
            for key, task in prev_tasks.items():
                pid_candidate = self._optional_int(key)
                if pid_candidate is None:
                    continue
                state_val = str(task.get("state") or "").lower()
                if state_val == "running":
                    prev_pid = pid_candidate
                    break

        next_pid = self._optional_int(context.get("next_pid"))
        if next_pid is None:
            next_pid = self._optional_int(self.current_pid)

        if prev_pid is None or prev_pid == next_pid:
            return None

        prev_task = _fetch_task(prev_tasks, prev_pid)
        prev_state = None
        if prev_task is not None:
            prev_state = prev_task.get("state")

        next_task = _fetch_task(self.tasks, next_pid)
        next_state = None
        if next_task is not None:
            next_state = next_task.get("state")

        post_task = _fetch_task(self.tasks, prev_pid)
        post_state = (post_task.get("state") if isinstance(post_task, dict) else None) if post_task else None
        post_state_norm = str(post_state or "").lower() if post_state is not None else None

        reason = context.get("reason") or context.get("reason_hint")
        if reason is None:
            if post_task is None:
                reason = "killed"
            elif post_state_norm in {"sleeping"}:
                reason = "sleep"
            elif post_state_norm in {"waiting_mbx", "waiting"}:
                reason = "wait_mbx"
            elif post_state_norm == "paused":
                reason = "paused"
            elif post_state_norm in {"terminated", "killed", "returned"}:
                reason = "killed"
            else:
                reason = "quantum_expired"

        quantum_remaining: Optional[int] = None
        if isinstance(prev_task, dict):
            quantum = self._optional_int(prev_task.get("quantum"))
            accounted = self._optional_int(prev_task.get("accounted_steps"))
            if quantum and quantum > 0 and accounted is not None:
                remainder = quantum - (accounted % quantum)
                if remainder == quantum:
                    remainder = 0
                quantum_remaining = remainder

        data: Dict[str, Any] = {
            "state": "switch",
            "prev_pid": prev_pid,
            "next_pid": next_pid,
            "reason": reason,
        }
        if quantum_remaining is not None:
            data["quantum_remaining"] = quantum_remaining
        if prev_state is not None:
            data["prev_state"] = str(prev_state)
        if next_state is not None:
            data["next_state"] = str(next_state)
        if post_state is not None:
            data["post_state"] = str(post_state)
        executed = self._optional_int(context.get("executed"))
        if executed is not None:
            data["executed"] = executed
        source = context.get("source")
        if isinstance(source, str):
            data["source"] = source
        details = context.get("details")
        if isinstance(details, dict) and details:
            data["details"] = dict(details)

        return self.emit_event("scheduler", pid=next_pid, data=data)

    def _infer_task_state_reason(
        self,
        prev_state: Optional[str],
        new_state: Optional[str],
        task: Dict[str, Any],
        state_entry: Dict[str, Any],
    ) -> Optional[str]:
        prev = str(prev_state or "").lower()
        new = str(new_state or "").lower()
        if new == "waiting_mbx":
            return "mailbox_wait"
        if prev == "waiting_mbx" and new in {"ready", "running"}:
            return "mailbox_wake"
        if new == "returned":
            return "returned"
        if new == "terminated":
            last_reason = state_entry.get("last_reason")
            if last_reason in {"killed", "timeout"}:
                return last_reason
            return "killed"
        if new == "paused" and state_entry.get("last_reason") == "debug_break":
            return "debug_break"
        exit_status = task.get("exit_status")
        if exit_status is not None and new in {"stopped", "returned"}:
            return "returned"
        return None

    def _handle_trace_step_event(self, pid: int, payload: Dict[str, Any]) -> None:
        regs_value = payload.get("regs")
        if not isinstance(regs_value, (list, tuple)):
            self.trace_last_regs.pop(pid, None)
            return
        regs_list = list(regs_value[:16])
        clean_regs: List[int] = []
        for value in regs_list:
            try:
                clean_regs.append(int(value) & 0xFFFFFFFF)
            except (TypeError, ValueError):
                clean_regs.append(0)
        while len(clean_regs) < 16:
            clean_regs.append(0)
        pc_value_raw = payload.get("pc")
        pc_value: Optional[int]
        try:
            pc_value = int(pc_value_raw) & 0xFFFFFFFF if pc_value_raw is not None else None
        except (TypeError, ValueError):
            pc_value = None
        flags_raw = payload.get("flags")
        try:
            flags_value = int(flags_raw) & 0xFFFFFFFF if flags_raw is not None else None
        except (TypeError, ValueError):
            flags_value = None
        last_entry = self.trace_last_regs.get(pid)
        changed: List[str] = []
        if last_entry is None or not isinstance(last_entry.get("regs"), list):
            changed = [f"R{i}" for i in range(len(clean_regs))]
        else:
            last_regs = last_entry.get("regs", [])
            for idx, value in enumerate(clean_regs):
                prev_value = last_regs[idx] if idx < len(last_regs) else None
                if prev_value is None or prev_value != value:
                    changed.append(f"R{idx}")
        last_pc = last_entry.get("pc") if last_entry else None
        if pc_value is not None and (last_pc is None or pc_value != last_pc):
            changed.append("PC")
        last_flags = last_entry.get("flags") if last_entry else None
        if flags_value is not None and (last_flags is None or flags_value != last_flags):
            changed.append("PSW")
        if "PC" in changed:
            changed.remove("PC")
        if self.trace_track_changed_regs and changed:
            payload["changed_regs"] = changed
        self.trace_last_regs[pid] = {"regs": clean_regs, "pc": pc_value, "flags": flags_value}
        self._append_trace_record(pid, payload, clean_regs, pc_value, flags_value)

    def _next_trace_seq_locked(self) -> int:
        seq = self._trace_seq
        self._trace_seq += 1
        if self._trace_seq > 1_000_000_000:
            self._trace_seq = 1
        return seq

    def _append_trace_record(
        self,
        pid: int,
        payload: Dict[str, Any],
        regs: List[int],
        pc: Optional[int],
        flags: Optional[int],
    ) -> None:
        if self.trace_buffer_capacity <= 0:
            return
        timestamp = time.time()
        with self.trace_lock:
            if self.trace_buffer_capacity <= 0:
                return
            buffer = self.trace_buffers.get(pid)
            if buffer is None or buffer.maxlen != self.trace_buffer_capacity:
                buffer = deque(maxlen=self.trace_buffer_capacity)
                self.trace_buffers[pid] = buffer
            record_dict: Dict[str, Any] = {
                "seq": self._next_trace_seq_locked(),
                "ts": timestamp,
                "pid": pid,
                "pc": pc if pc is not None else self._optional_int(payload.get("pc")),
                "opcode": self._optional_int(payload.get("opcode")),
            }
            if flags is not None:
                record_dict["flags"] = flags
            if regs:
                record_dict["regs"] = list(regs)
            next_pc = self._optional_int(payload.get("next_pc"))
            if next_pc is not None:
                record_dict["next_pc"] = next_pc
            steps = self._optional_int(payload.get("steps"))
            if steps is not None:
                record_dict["steps"] = steps
            changed = payload.get("changed_regs")
            if isinstance(changed, (list, tuple)):
                record_dict["changed_regs"] = list(changed)
            mem_access = payload.get("mem_access")
            if isinstance(mem_access, dict):
                record_dict["mem_access"] = dict(mem_access)
            source = payload.get("source")
            if source is not None:
                record_dict["source"] = source
            normalized = trace_format.decode_trace_records(
                [record_dict], default_pid=pid
            )[0]
            buffer.append(normalized)

    def _emit_trace_snapshot(self, pid: int, snapshot: Mapping[str, Any]) -> None:
        pid_value = self._optional_int(snapshot.get("pid")) or pid
        payload: Dict[str, Any] = {k: v for k, v in snapshot.items() if k != "pid"}
        regs_value = payload.get("regs")
        if isinstance(regs_value, list):
            payload["regs"] = [int(val) & 0xFFFFFFFF for val in regs_value]
        elif isinstance(regs_value, tuple):
            payload["regs"] = [int(val) & 0xFFFFFFFF for val in regs_value]
        else:
            payload["regs"] = []
        if "flags" in payload:
            try:
                payload["flags"] = int(payload["flags"]) & 0xFF
            except (TypeError, ValueError):
                payload["flags"] = 0
        else:
            payload["flags"] = 0
        mem_access = payload.get("mem_access")
        if isinstance(mem_access, dict):
            payload["mem_access"] = dict(mem_access)
        self._handle_trace_step_event(pid_value, payload)
        self.emit_event("trace_step", pid=pid_value, data=payload)

    def _parse_event_filters(self, filters: Optional[Dict[str, Any]]) -> Tuple[Optional[Set[int]], Optional[Set[str]], Optional[int]]:
        if not isinstance(filters, dict):
            return None, None, None
        pid_values = filters.get("pid")
        pids: Optional[Set[int]]
        if pid_values is None:
            pids = None
        else:
            if not isinstance(pid_values, (list, tuple, set)):
                pid_values = [pid_values]
            pids = set()
            for value in pid_values:
                try:
                    pid = int(value)
                except (TypeError, ValueError):
                    raise ValueError("filters.pid must contain integer PIDs")
                pids.add(pid)
        categories_values = filters.get("categories")
        categories: Optional[Set[str]]
        if categories_values is None:
            categories = None
        else:
            if not isinstance(categories_values, (list, tuple, set)):
                categories_values = [categories_values]
            categories = {str(cat) for cat in categories_values}
        since_seq_value = filters.get("since_seq")
        since_seq: Optional[int]
        if since_seq_value is None:
            since_seq = None
        else:
            try:
                since_seq = int(since_seq_value)
            except (TypeError, ValueError):
                raise ValueError("filters.since_seq must be an integer when provided")
            if since_seq < 0:
                raise ValueError("filters.since_seq must be non-negative")
        return pids, categories, since_seq

    def events_subscribe(
        self,
        session_id: str,
        *,
        filters: Optional[Dict[str, Any]] = None,
    ) -> EventSubscription:
        record = self._get_session(session_id)
        pids, categories, since_seq = self._parse_event_filters(filters)
        with self.event_lock:
            existing_token = self.session_event_map.pop(session_id, None)
            if existing_token:
                old = self.event_subscriptions.pop(existing_token, None)
                if old:
                    with old.condition:
                        old.active = False
                        old.condition.notify_all()
            token = f"{session_id}:{uuid.uuid4()}"
            condition = threading.Condition(self.event_lock)
            current_seq = self.event_seq - 1
            initial_ack = since_seq if since_seq is not None else current_seq
            subscription = EventSubscription(
                token=token,
                session_id=session_id,
                pids=pids,
                categories=categories,
                queue=deque(),
                condition=condition,
                max_events=record.max_events,
                last_ack=initial_ack,
                delivered_seq=initial_ack,
                since_seq=since_seq,
            )
            # preload history if requested
            if since_seq is not None:
                with subscription.condition:
                    for event in self.event_history:
                        if event.get("seq", 0) > since_seq and subscription.matches(event):
                            subscription.queue.append(event)
                            self._post_enqueue_locked(subscription, event.get("seq", initial_ack))
            self.event_subscriptions[token] = subscription
            self.session_event_map[session_id] = token
            subscription.condition.notify_all()
        self.log(
            "info",
            "events subscribed",
            session_id=session_id,
            token=token,
            filters={"pid": sorted(subscription.pids) if subscription.pids else None, "categories": sorted(subscription.categories) if subscription.categories else None},
        )
        return subscription

    def events_unsubscribe(self, session_id: Optional[str] = None, token: Optional[str] = None) -> bool:
        if token is None and session_id is not None:
            with self.event_lock:
                token = self.session_event_map.pop(session_id, None)
        removed = False
        if token is None:
            return False
        with self.event_lock:
            sub = self.event_subscriptions.pop(token, None)
            if sub:
                if sub.session_id in self.session_event_map and self.session_event_map[sub.session_id] == token:
                    self.session_event_map.pop(sub.session_id, None)
                removed = True
                with sub.condition:
                    sub.active = False
                    sub.condition.notify_all()
        if removed:
            self.log("info", "events unsubscribed", token=token, session_id=session_id)
        return removed

    def events_ack(self, session_id: str, seq: int) -> None:
        if seq < 0:
            raise ValueError("ack seq must be non-negative")
        with self.event_lock:
            token = self.session_event_map.get(session_id)
            if not token:
                raise SessionError("session_required")
            subscription = self.event_subscriptions.get(token)
        if subscription is None:
            raise SessionError("session_required")
        with subscription.condition:
            subscription.last_ack = max(subscription.last_ack, seq)
            while subscription.queue and subscription.queue[0].get("seq", 0) <= seq:
                subscription.queue.popleft()
            pending_after = subscription.pending()
            if pending_after <= subscription.max_events:
                subscription.slow_warning_active = False
                subscription.slow_since = 0.0
            subscription.condition.notify_all()

    def events_next(self, subscription: EventSubscription, timeout: float = 1.0) -> Optional[Dict[str, Any]]:
        end_time = time.time() + timeout
        with subscription.condition:
            while True:
                if subscription.queue:
                    return subscription.queue.popleft()
                if not subscription.active:
                    return None
                remaining = end_time - time.time()
                if remaining <= 0:
                    return None
                subscription.condition.wait(timeout=remaining)
        return None

    def events_metrics(self, session_id: str) -> Dict[str, Any]:
        with self.event_lock:
            token = self.session_event_map.get(session_id)
            if not token:
                raise SessionError("session_required")
            subscription = self.event_subscriptions.get(token)
        if subscription is None:
            raise SessionError("session_required")
        with subscription.condition:
            pending = subscription.pending()
            return {
                "token": subscription.token,
                "pending": pending,
                "high_water": subscription.high_water,
                "drop_count": subscription.drop_count,
                "slow_count": subscription.slow_count,
                "last_ack": subscription.last_ack,
                "delivered_seq": subscription.delivered_seq,
                "max_events": subscription.max_events,
                "active": subscription.active,
                "slow_warning_active": subscription.slow_warning_active,
            }

    def events_session_disconnected(self, session_id: str) -> None:
        self.events_unsubscribe(session_id=session_id)

    def _refresh_tasks(self) -> None:
        try:
            snapshot = self.vm.ps()
        except RuntimeError:
            return
        prev_current_pid = self.current_pid
        tasks_block = snapshot.get("tasks", [])
        if isinstance(tasks_block, dict):
            tasks = tasks_block.get("tasks", [])
            new_current_pid = tasks_block.get("current_pid")
        else:
            tasks = tasks_block
            new_current_pid = snapshot.get("current_pid")
        prev_snapshot = {
            "current_pid": prev_current_pid,
            "tasks": {pid: dict(task) for pid, task in self.tasks.items()},
        }
        self.current_pid = self._optional_int(new_current_pid)
        prev_states = self.task_states
        self.tasks = {}
        new_states: Dict[int, Dict[str, Any]] = {}
        current_pids: Set[int] = set()
        now = time.time()
        for task in tasks:
            if not isinstance(task, dict):
                continue
            pid_raw = task.get("pid", 0)
            try:
                pid = int(pid_raw)
            except (TypeError, ValueError):
                continue
            self.tasks[pid] = task
            prev_entry = prev_states.get(pid)
            state_entry: Dict[str, Any]
            if isinstance(prev_entry, dict):
                state_entry = prev_entry
            else:
                state_entry = {}
            context = state_entry.get("context")
            if not isinstance(context, dict):
                context = {}
            context.pop("regs", None)
            context["state"] = task.get("state")
            if "exit_status" in task:
                context["exit_status"] = task.get("exit_status")
            elif "exit_status" in context and "exit_status" not in task:
                context.pop("exit_status", None)
            if "trace" in task:
                context["trace"] = task.get("trace")
            def _propagate_field(name: str) -> None:
                val = self._optional_int(task.get(name))
                if val is not None:
                    context[name] = val
                    task[name] = val
                elif name in context:
                    context.pop(name, None)
            _propagate_field("reg_base")
            _propagate_field("stack_base")
            _propagate_field("stack_limit")
            _propagate_field("stack_size")
            prev_state = state_entry.get("state")
            prev_state_enum = state_entry.get("state_enum")
            if not isinstance(prev_state_enum, TaskState):
                try:
                    prev_state_enum = self._coerce_task_state(prev_state, allow_none=True)
                except ValueError:
                    prev_state_enum = None
            prev_sleep = bool(state_entry.get("sleep_pending"))
            new_state_value = task.get("state")
            if new_state_value is None:
                new_state_str = context.get("state") or prev_state
            else:
                new_state_str = str(new_state_value)
            try:
                new_state_enum = self._coerce_task_state(new_state_str)
            except ValueError as exc:
                raise ValueError(f"task_state_invalid:{new_state_str}:pid={pid}") from exc
            self._validate_state_transition(pid, prev_state_enum, new_state_enum)
            if new_state_enum != prev_state_enum:
                self._record_state_transition(pid, prev_state_enum, new_state_enum)
            new_state = new_state_enum.value
            if new_state_enum == TaskState.SLEEPING:
                self._track_sleep(pid, task.get("sleep_deadline"))
            else:
                self._untrack_sleep(pid)
            state_entry["state"] = new_state
            state_entry["state_enum"] = new_state_enum
            sleep_flag = bool(task.get("sleep_pending"))
            state_entry["sleep_pending"] = sleep_flag
            state_entry["context"] = context
            context["state"] = new_state
            if self.enforce_context_isolation:
                self._assert_context_isolation(pid, context, new_state_enum)
            task["state"] = new_state
            new_states[pid] = state_entry
            current_pids.add(pid)
            bp_set = self.breakpoints.get(pid)
            if bp_set:
                task["breakpoints"] = sorted(bp_set)
            elif "breakpoints" in task:
                task.pop("breakpoints", None)
            symbol_table = self.symbol_tables.get(pid)
            if symbol_table:
                task["symbols"] = {
                    "path": symbol_table.get("path"),
                    "count": len(symbol_table.get("symbols", [])),
                }
            elif "symbols" in task:
                task.pop("symbols", None)

            reason: Optional[str] = None
            details: Optional[Dict[str, Any]] = None
            ts: Optional[float] = None
            emit_same_state = False
            pending = self.task_state_pending.pop(pid, None)
            if pending:
                reason = pending.get("reason")
                details_payload = pending.get("details")
                if isinstance(details_payload, dict):
                    details = dict(details_payload)
                elif details_payload is not None:
                    details = {"value": details_payload}
                ts = pending.get("ts")
                emit_same_state = bool(pending.get("force"))
                expected_state = pending.get("target_state")
                if expected_state and expected_state != new_state:
                    merged = dict(details or {})
                    merged.setdefault("expected_state", expected_state)
                    details = merged
            if reason is None and prev_entry is None:
                reason = "loaded"
                ts = ts or now
            if prev_entry is not None and prev_state != new_state and reason is None:
                inferred = self._infer_task_state_reason(prev_state, new_state, task, state_entry)
                if inferred:
                    reason = inferred
            if not prev_sleep and sleep_flag:
                sleep_details = dict(details or {}) if details else {}
                sleep_details.setdefault("sleep_pending", True)
                sleep_ms = task.get("sleep_pending_ms")
                if sleep_ms is not None:
                    sleep_details.setdefault("sleep_ms", sleep_ms)
                if reason is None:
                    reason = "sleep"
                    details = sleep_details
                else:
                    updated = dict(details or {})
                    updated.update(sleep_details)
                    details = updated
                ts = ts or now
                emit_same_state = True
            if reason == "returned" and task.get("exit_status") is not None:
                exit_details = dict(details or {})
                exit_details.setdefault("exit_status", task.get("exit_status"))
                details = exit_details
            if reason is not None or (prev_state != new_state) or emit_same_state:
                self._emit_task_state_event(
                    pid,
                    prev_state,
                    new_state,
                    reason=reason,
                    details=details,
                    ts=ts,
                    state_entry=state_entry,
                )

        removed_pids = set(prev_states.keys()) - current_pids
        for pid in removed_pids:
            pending = self.task_state_pending.pop(pid, None)
            prev_entry = prev_states.get(pid)
            if not isinstance(prev_entry, dict):
                prev_entry = {}
            prev_state = prev_entry.get("state")
            reason = pending.get("reason") if pending else None
            details_payload = pending.get("details") if pending else None
            ts = pending.get("ts") if pending else None
            if details_payload is not None and not isinstance(details_payload, dict):
                details = {"value": details_payload}
            else:
                details = dict(details_payload) if isinstance(details_payload, dict) else None
            if reason is None:
                if prev_state == "returned":
                    reason = "returned"
                elif prev_state == "terminated" and prev_entry.get("last_reason"):
                    reason = prev_entry.get("last_reason")
                else:
                    reason = "killed"
            self._emit_task_state_event(
                pid,
                prev_state,
                "terminated",
                reason=reason,
                details=details,
                ts=ts,
                state_entry=prev_entry,
            )
            self.trace_last_regs.pop(pid, None)
            self._untrack_sleep(pid)

        self.task_states = new_states
        context = self._pending_scheduler_context or {}
        self._pending_scheduler_context = None
        self._maybe_emit_scheduler_event(prev_snapshot, context=context)
        stale = set(self.breakpoints.keys()) - current_pids
        for pid in stale:
            self.breakpoints.pop(pid, None)
            self.debug_attached.discard(pid)
        stale_symbols = set(self.symbol_tables.keys()) - current_pids
        for pid in stale_symbols:
            self.symbol_tables.pop(pid, None)
        stale_disasm = set(self.disasm_cache.keys()) - current_pids
        for pid in stale_disasm:
            self.disasm_cache.pop(pid, None)
        stale_watchers = set(self.watchers.keys()) - current_pids
        for pid in stale_watchers:
            self.watchers.pop(pid, None)
        stale_values = set(self.value_registry.keys()) - current_pids
        for pid in stale_values:
            self.value_registry.pop(pid, None)
        stale_commands = set(self.command_registry.keys()) - current_pids
        for pid in stale_commands:
            self.command_registry.pop(pid, None)
        stale_mailboxes = set(self.mailbox_registry.keys()) - current_pids
        for pid in stale_mailboxes:
            self.mailbox_registry.pop(pid, None)
        stale_layouts = set(self.memory_layouts.keys()) - current_pids
        for pid in stale_layouts:
            self.memory_layouts.pop(pid, None)
        stale_meta = set(self.image_metadata.keys()) - current_pids
        for pid in stale_meta:
            self.image_metadata.pop(pid, None)
        stale_trace = set(self.trace_last_regs.keys()) - current_pids
        for pid in stale_trace:
            self.trace_last_regs.pop(pid, None)
            with self.trace_lock:
                self.trace_buffers.pop(pid, None)

    def log(self, level: str, message: str, **fields: Any) -> None:
        entry = {
            "seq": self._next_log_seq,
            "ts": time.time(),
            "level": level,
            "message": message,
            "clock_steps": self.total_steps,
        }
        if fields:
            entry.update(fields)
        self.log_buffer.append(entry)
        self._next_log_seq += 1

    def get_logs(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        if limit is None or limit <= 0 or limit >= len(self.log_buffer):
            return list(self.log_buffer)
        return list(self.log_buffer)[-limit:]

    def attach(self) -> Dict[str, Any]:
        info = self.vm.attach()
        self._refresh_tasks()
        return info

    def detach(self) -> Dict[str, Any]:
        self.stop_auto()
        info = self.vm.detach()
        return info

    def info(self, pid: Optional[int] = None) -> Dict[str, Any]:
        payload = self.vm.info(pid=pid)
        clock = self.get_clock_status()
        payload["auto"] = clock["running"]
        payload["clock"] = clock
        return payload

    def load(self, path: str, verbose: bool = False, *, symbols: Optional[str] = None) -> Dict[str, Any]:
        program_path = Path(path)
        info = self.vm.load(str(program_path), verbose=verbose)
        self._refresh_tasks()
        pid = info.get("pid")
        symbol_status: Optional[Dict[str, Any]] = None
        pid_int: Optional[int]
        try:
            pid_int = int(pid) if pid is not None else None
        except (TypeError, ValueError):
            pid_int = None
        if pid_int is not None:
            self.disasm_cache.pop(pid_int, None)
            task = self.tasks.get(pid_int, {})
            program = task.get("program") or info.get("program") or str(program_path)
            symbol_status = self.load_symbols_for_pid(pid_int, program=program, override=symbols)
            metadata_summary = info.get("metadata") or {}
            try:
                self._register_metadata(pid_int, metadata_summary)
            except Exception:
                self.value_registry.pop(pid_int, None)
                self.command_registry.pop(pid_int, None)
                self.mailbox_registry.pop(pid_int, None)
                self.image_metadata.pop(pid_int, None)
                raise
            self.image_metadata[pid_int] = metadata_summary
            layout = {
                "entry": self._coerce_int(info.get("entry")) if info.get("entry") is not None else None,
                "code_len": self._coerce_int(info.get("code_len")) if info.get("code_len") is not None else None,
                "ro_len": self._coerce_int(info.get("ro_len")) if info.get("ro_len") is not None else None,
                "bss": self._coerce_int(info.get("bss")) if info.get("bss") is not None else None,
                "app_name": task.get("app_name") or info.get("app_name"),
                "app_name_base": task.get("app_name_base") or info.get("app_name_base"),
                "meta_count": self._coerce_int(info.get("meta_count")) if info.get("meta_count") is not None else None,
                "allow_multiple": info.get("allow_multiple_instances"),
                "version": self._coerce_int(info.get("version")) if info.get("version") is not None else None,
            }
            self.memory_layouts[pid_int] = {k: v for k, v in layout.items() if v is not None}
        if symbol_status is not None:
            info["symbols"] = symbol_status
            if not symbol_status.get("loaded"):
                warnings = info.setdefault("warnings", [])
                error_text = symbol_status.get("error")
                path_text = symbol_status.get("path")
                if error_text:
                    warnings.append(f"symbols_failed:{error_text}")
                elif path_text:
                    warnings.append(f"symbols_missing:{path_text}")
                else:
                    warnings.append("symbols_unavailable")
        return info

    def step(self, steps: Optional[int] = None, *, pid: Optional[int] = None, source: str = "manual") -> Dict[str, Any]:
        self._advance_sleeping_tasks()
        budget = steps if steps is not None else self.step_batch
        pre_event = self._check_breakpoint_before_step(pid)
        if pre_event is not None:
            if source == "auto":
                self.auto_step_count += 1
            else:
                self.manual_step_count += 1
            result = {
                "executed": 0,
                "running": False,
                "paused": True,
                "current_pid": pid,
                "events": [pre_event],
            }
            self._refresh_tasks()
            return result
        with self.lock:
            result = self.vm.step(budget, pid=pid)
        executed_raw = result.get("executed", 0)
        try:
            executed = int(executed_raw)
        except (TypeError, ValueError):
            executed = 0
        self._update_scheduler_context(
            prev_pid=self._optional_int(result.get("current_pid")),
            next_pid=self._optional_int(result.get("next_pid")),
            executed=executed,
            source=source,
        )
        events = result.get("events") or []
        has_trace_event = any(evt.get("type") == "trace_step" for evt in events)
        self._process_vm_events(events)
        if executed > 0:
            self.total_steps += executed
        if source == "auto":
            self.auto_step_count += 1
            self.auto_step_total += executed
        else:
            self.manual_step_count += 1
            self.manual_step_total += executed
        running_flag = bool(result.get("running", True))
        post_event = self._check_breakpoint_after_step(pid, result)
        if post_event is not None:
            result.setdefault("events", []).append(post_event)
            result["paused"] = True
            result["running"] = False
            running_flag = False
        if (not running_flag) and (executed > 0 or self._last_vm_running):
            self.log(
                "info",
                "vm halted or idle",
                current_pid=result.get("current_pid"),
                executed=result.get("executed"),
                paused=result.get("paused"),
            )
        self._last_vm_running = running_flag
        trace_last = result.pop("trace_last", None)
        if not has_trace_event and trace_last:
            pid_from_trace = self._optional_int(trace_last.get("pid"))
            if pid_from_trace is None:
                pid_from_trace = self._optional_int(result.get("current_pid")) or self.current_pid
            if pid_from_trace is not None:
                try:
                    self._emit_trace_snapshot(pid_from_trace, trace_last)
                except Exception:
                    pass
        self._refresh_tasks()
        watch_events = self._check_watches(pid if pid is not None else None)
        if watch_events:
            result.setdefault("events", []).extend(watch_events)
        return result

    def start_auto(self) -> None:
        if self.auto_thread and self.auto_thread.is_alive():
            return
        self.auto_event.clear()
        self.clock_mode = "rate" if self.clock_rate_hz > 0 else "active"
        self._clock_throttle_reason = None
        self._clock_last_wait = 0.0
        self.auto_thread = threading.Thread(target=self._auto_loop, daemon=True)
        self.auto_thread.start()

    def stop_auto(self) -> None:
        if self.auto_thread and self.auto_thread.is_alive():
            self.auto_event.set()
            self.auto_thread.join(timeout=1.0)
        self.auto_thread = None
        self.clock_mode = "stopped"
        self._clock_throttle_reason = None
        self._clock_last_wait = 0.0

    def get_clock_status(self) -> Dict[str, Any]:
        running = self.auto_thread is not None and self.auto_thread.is_alive()
        rate = self.clock_rate_hz if self.clock_rate_hz > 0 else 0.0
        throttle_reason = self._clock_throttle_reason
        throttled = throttle_reason in {"throttled", "sleep"}
        return {
            "state": "running" if running else "stopped",
            "running": running,
            "mode": self.clock_mode,
            "throttled": throttled,
            "throttle_reason": throttle_reason,
            "last_wait_s": self._clock_last_wait,
            "rate_hz": rate,
            "step_size": self.step_batch,
            "auto_steps": self.auto_step_count,
            "auto_total_steps": self.auto_step_total,
            "manual_steps": self.manual_step_count,
            "manual_total_steps": self.manual_step_total,
        }

    def _has_runnable_tasks(self) -> bool:
        return any(task.get("state") in {"running", "ready"} for task in self.tasks.values())

    def _has_waiting_tasks(self) -> bool:
        if self.sleeping_deadlines:
            return True
        return any(task.get("state") in {"waiting", "waiting_mbx", "waiting_io", "sleeping"} for task in self.tasks.values())

    def set_clock_rate(self, hz: float) -> Dict[str, Any]:
        if hz < 0:
            raise ValueError("clock rate must be non-negative")
        self.clock_rate_hz = float(hz)
        return self.get_clock_status()

    def clock_step(self, steps: Optional[int] = None, pid: Optional[int] = None) -> Dict[str, Any]:
        return self.step(steps, pid=pid, source="manual")

    def get_task(self, pid: int) -> Dict[str, Any]:
        task = self.tasks.get(pid)
        if task is None:
            self._refresh_tasks()
            task = self.tasks.get(pid)
        if task is None:
            raise ValueError(f"unknown pid {pid}")
        return task

    def request_peek(self, pid: int, addr: int, length: int) -> str:
        self.get_task(pid)
        data = self.vm.read_mem(addr, length, pid=pid)
        return data.hex()

    def request_poke(self, pid: int, addr: int, data_hex: str) -> None:
        self.get_task(pid)
        self.vm.write_mem(addr, bytes.fromhex(data_hex), pid=pid)

    def request_dump_regs(self, pid: int) -> Dict[str, Any]:
        regs = self.vm.read_regs(pid=pid)
        task = self.tasks.get(pid)
        if task is not None:
            task['pc'] = regs.get('pc')
        return regs

    def set_trace_changed_regs(self, enabled: bool) -> Dict[str, Any]:
        self.trace_track_changed_regs = bool(enabled)
        if not self.trace_track_changed_regs:
            self.trace_last_regs.clear()
        return {"changed_regs": self.trace_track_changed_regs}

    def trace_task(self, pid: int, enable: Optional[bool]) -> Dict[str, Any]:
        result = dict(self.vm.trace(pid, enable) or {})
        pid_val = int(result.get("pid", pid))
        state_entry = self.task_states.get(pid_val, {})
        context = state_entry.get("context", {})
        context["trace"] = result.get("enabled")
        state_entry["context"] = context
        self.task_states[pid_val] = state_entry
        if pid_val in self.tasks:
            self.tasks[pid_val]["trace"] = result.get("enabled")
        result["buffer_size"] = self.trace_buffer_capacity
        return result

    def set_trace_buffer_size(self, size: int) -> Dict[str, Any]:
        try:
            new_size = int(size)
        except (TypeError, ValueError) as exc:
            raise ValueError("trace buffer size must be integer") from exc
        if new_size < 0:
            raise ValueError("trace buffer size must be non-negative")
        if new_size > self.trace_buffer_max:
            new_size = self.trace_buffer_max
        with self.trace_lock:
            self.trace_buffer_capacity = new_size
            if new_size == 0:
                self.trace_buffers.clear()
            else:
                for pid, buffer in list(self.trace_buffers.items()):
                    if buffer.maxlen != new_size:
                        recent = list(buffer)[-new_size:]
                        self.trace_buffers[pid] = deque(recent, maxlen=new_size)
        return {"buffer_size": self.trace_buffer_capacity}

    def trace_records(self, pid: int, limit: Optional[int] = None) -> Dict[str, Any]:
        capacity = self.trace_buffer_capacity
        with self.trace_lock:
            buffer = self.trace_buffers.get(pid)
            count = len(buffer) if buffer is not None else 0
            if limit is not None:
                try:
                    limit_int = int(limit)
                except (TypeError, ValueError) as exc:
                    raise ValueError("trace records limit must be integer-compatible") from exc
                if limit_int <= 0:
                    raw_records: List[Dict[str, Any]] = []
                else:
                    raw_records = list(buffer)[-limit_int:] if buffer is not None else []
            else:
                raw_records = list(buffer) if buffer is not None else []
            encoded = trace_format.encode_trace_records(raw_records)
        enabled = None
        task = self.tasks.get(pid)
        if isinstance(task, dict):
            enabled = bool(task.get("trace"))
        return {
            "pid": pid,
            "capacity": capacity,
            "count": count,
            "returned": len(encoded),
            "enabled": enabled,
            "format": trace_format.TRACE_FORMAT_VERSION,
            "records": encoded,
        }

    def trace_export(self, pid: int, limit: Optional[int] = None) -> Dict[str, Any]:
        info = self.trace_records(pid, limit=limit)
        return {
            "pid": info.get("pid"),
            "capacity": info.get("capacity"),
            "count": info.get("count"),
            "returned": info.get("returned"),
            "format": trace_format.TRACE_FORMAT_VERSION,
            "records": list(info.get("records", [])),
        }

    def trace_import(
        self,
        pid: int,
        records: Iterable[Mapping[str, Any]],
        *,
        replace: bool = False,
    ) -> Dict[str, Any]:
        if self.trace_buffer_capacity <= 0:
            raise ValueError("trace buffer disabled")
        decoded = trace_format.decode_trace_records(records, default_pid=pid)
        with self.trace_lock:
            buffer = self.trace_buffers.get(pid)
            if replace or buffer is None or buffer.maxlen != self.trace_buffer_capacity:
                buffer = deque(maxlen=self.trace_buffer_capacity)
            else:
                buffer = deque(buffer, maxlen=self.trace_buffer_capacity)
            if decoded:
                if len(decoded) > self.trace_buffer_capacity:
                    decoded = decoded[-self.trace_buffer_capacity :]
                for rec in decoded:
                    buffer.append(rec)
                max_seq = max(rec.get("seq", 0) for rec in decoded)
                if isinstance(max_seq, int):
                    self._trace_seq = max(self._trace_seq, max_seq + 1)
            elif replace:
                buffer.clear()
            self.trace_buffers[pid] = buffer
        return self.trace_records(pid)

    def task_list(self) -> Dict[str, Any]:
        self._refresh_tasks()
        return {"tasks": list(self.tasks.values()), "current_pid": self.current_pid}

    def pause_task(self, pid: int) -> Dict[str, Any]:
        self.get_task(pid)
        if pid not in self.task_state_pending:
            self._set_task_state_pending(pid, "user_pause", target_state="paused", ts=time.time())
        with self.lock:
            self.vm.pause(pid=pid)
        self._refresh_tasks()
        return dict(self.get_task(pid))

    def resume_task(self, pid: int) -> Dict[str, Any]:
        self.get_task(pid)
        self._set_task_state_pending(pid, "resume", target_state="running", ts=time.time())
        with self.lock:
            self.vm.resume(pid=pid)
        self._refresh_tasks()
        return dict(self.get_task(pid))

    def kill_task(self, pid: int) -> Dict[str, Any]:
        self._set_task_state_pending(pid, "killed", target_state="terminated", ts=time.time())
        self.stop_auto()
        with self.lock:
            self.vm.kill(pid)
        self._refresh_tasks()
        self._detach_debug_session(pid)
        with self.symbol_cache_lock:
            self.symbol_tables.pop(pid, None)
        self.disasm_cache.pop(pid, None)
        self.memory_layouts.pop(pid, None)
        self.watchers.pop(pid, None)
        self.value_registry.pop(pid, None)
        self.command_registry.pop(pid, None)
        self.mailbox_registry.pop(pid, None)
        self.image_metadata.pop(pid, None)
        return {"pid": pid, "state": "terminated"}

    def set_task_attrs(self, pid: int, *, priority: Optional[int] = None, quantum: Optional[int] = None) -> Dict[str, Any]:
        attrs = self.vm.sched(pid, priority=priority, quantum=quantum)
        self._refresh_tasks()
        return attrs

    def mailbox_snapshot(self) -> Dict[str, Any]:
        snapshot = self.vm.mailbox_snapshot()
        if isinstance(snapshot, dict):
            return snapshot
        return {"descriptors": snapshot, "stats": {}}

    def mailbox_open(self, pid: int, target: str, flags: int = 0) -> dict:
        return self.vm.mailbox_open(pid, target, flags)

    def mailbox_close(self, pid: int, handle: int) -> dict:
        return self.vm.mailbox_close(pid, handle)

    def mailbox_bind(self, pid: int, target: str, *, capacity: int | None = None, mode: int = 0) -> dict:
        return self.vm.mailbox_bind(pid, target, capacity=capacity, mode=mode)

    def mailbox_send(self, pid: int, handle: int, *, data: str | None = None, data_hex: str | None = None, flags: int = 0, channel: int = 0) -> dict:
        return self.vm.mailbox_send(pid, handle, data=data, data_hex=data_hex, flags=flags, channel=channel)

    def mailbox_recv(self, pid: int, handle: int, *, max_len: int = 512, timeout: int = 0) -> dict:
        return self.vm.mailbox_recv(pid, handle, max_len=max_len, timeout=timeout)

    def mailbox_peek(self, pid: int, handle: int) -> dict:
        return self.vm.mailbox_peek(pid, handle)

    def mailbox_tap(self, pid: int, handle: int, enable: bool = True) -> dict:
        return self.vm.mailbox_tap(pid, handle, enable=enable)

    def list_channels(self, pid: int) -> Dict[str, Any]:
        snapshot = self.mailbox_snapshot()
        descriptors = snapshot.get("descriptors", []) if isinstance(snapshot, dict) else snapshot
        channels: List[Dict[str, Any]] = []
        for desc in descriptors:
            owner = desc.get("owner_pid")
            try:
                owner_pid = int(owner) if owner is not None else None
            except (TypeError, ValueError):
                owner_pid = None
            if owner_pid != pid:
                continue
            target = self._format_descriptor_target(desc)
            channels.append(
                {
                    "descriptor_id": desc.get("descriptor_id"),
                    "target": target,
                    "name": desc.get("name"),
                    "namespace": desc.get("namespace"),
                    "mode_mask": desc.get("mode_mask"),
                    "capacity": desc.get("capacity"),
                    "bytes_used": desc.get("bytes_used"),
                    "queue_depth": desc.get("queue_depth"),
                    "subscriber_count": desc.get("subscriber_count"),
                }
            )
        return {"pid": pid, "channels": channels}

    def reload_task(self, pid: int, *, verbose: bool = False) -> Dict[str, Any]:
        task = self.get_task(pid)
        program = task.get("program")
        if not isinstance(program, str) or not program:
            raise ValueError(f"task {pid} does not have an associated program path")
        was_auto = self.auto_thread is not None and self.auto_thread.is_alive()
        self.kill_task(pid)
        load_info: Dict[str, Any]
        try:
            load_info = self.load(program, verbose=verbose)
        except Exception:
            if was_auto:
                self.start_auto()
            raise
        new_pid_raw = load_info.get("pid")
        try:
            new_pid = int(new_pid_raw) if new_pid_raw is not None else None
        except (TypeError, ValueError):
            new_pid = None
        self._refresh_tasks()
        new_task = self.tasks.get(new_pid) if new_pid is not None else None
        if was_auto:
            self.start_auto()
        return {
            "old_pid": pid,
            "new_pid": new_pid,
            "program": program,
            "image": load_info,
            "task": new_task,
        }

    def configure_stdio_fanout(self, mode: str, *, stream: str = "out", pid: Optional[int] = None) -> Dict[str, Any]:
        stream_value = stream or "out"
        mode_mask = self._fanout_mode_mask(mode)
        streams = self._normalize_stdio_streams(stream_value)
        applied: List[Dict[str, Any]] = []
        try:
            if pid is None:
                for item in streams:
                    resp = self.vm.mailbox_config_stdio(item, mode_mask, update_existing=True)
                    entry = dict(resp)
                    entry["stream"] = item
                    applied.append(entry)
            else:
                for item in streams:
                    target = f"svc:stdio.{item}@{pid}"
                    resp = self.mailbox_bind(0, target, mode=mode_mask)
                    entry = dict(resp)
                    entry["target"] = target
                    entry["stream"] = item
                    applied.append(entry)
        except Exception as exc:
            raise ValueError(f"stdio configure failed: {exc}") from exc
        summary = self.query_stdio_fanout(pid=pid, stream=stream_value)
        summary.update(
            {
                "mode": mode,
                "mode_mask": mode_mask,
                "applied": applied,
            }
        )
        return summary

    def query_stdio_fanout(self, *, pid: Optional[int], stream: Optional[str], default_only: bool = False) -> Dict[str, Any]:
        try:
            raw = self.vm.mailbox_stdio_summary(pid=pid, stream=stream, default_only=default_only)
        except Exception as exc:
            raise ValueError(f"stdio query failed: {exc}") from exc
        streams = raw.get("streams") or ["in", "out", "err"]
        default_map = raw.get("default") or {}
        default_summary = self._summarize_stdio_modes(default_map, streams)
        if default_only or (raw.get("task") is None and raw.get("tasks") is None and pid is None):
            return {
                "scope": "default",
                "streams": default_summary,
            }
        task_entry = raw.get("task")
        if task_entry is not None or pid is not None:
            entry = task_entry or {"pid": pid, "streams": {}}
            entry_pid = entry.get("pid", pid)
            modes = entry.get("streams", {})
            return {
                "scope": "pid",
                "pid": entry_pid,
                "streams": self._summarize_stdio_modes(modes, streams),
                "default": default_summary,
            }
        tasks_summary: List[Dict[str, Any]] = []
        for entry in raw.get("tasks", []):
            entry_pid = entry.get("pid")
            modes = entry.get("streams", {})
            tasks_summary.append(
                {
                    "pid": entry_pid,
                    "streams": self._summarize_stdio_modes(modes, streams),
                }
            )
        return {
            "scope": "all",
            "streams": [],
            "default": default_summary,
            "tasks": tasks_summary,
        }

    @staticmethod
    def _normalize_stdio_streams(stream: str) -> List[str]:
        normalized = (stream or "out").lower()
        if normalized in {"both"}:
            return ["out", "err"]
        if normalized in {"all", "any"}:
            return ["in", "out", "err"]
        if normalized in {"out", "stdout"}:
            return ["out"]
        if normalized in {"err", "stderr"}:
            return ["err"]
        if normalized in {"in", "stdin"}:
            return ["in"]
        raise ValueError(f"unknown stdio stream '{stream}'")

    @staticmethod
    def _fanout_mode_mask(mode: str) -> int:
        normalized = (mode or "off").lower()
        base = mbx_const.HSX_MBX_MODE_RDWR
        if normalized in {"off", "none", "default"}:
            return base
        if normalized in {"drop", "fanout", "fanout_drop"}:
            return base | mbx_const.HSX_MBX_MODE_FANOUT | mbx_const.HSX_MBX_MODE_FANOUT_DROP
        if normalized in {"block", "fanout_block"}:
            return base | mbx_const.HSX_MBX_MODE_FANOUT | mbx_const.HSX_MBX_MODE_FANOUT_BLOCK
        raise ValueError(f"unknown fan-out mode '{mode}'")

    @staticmethod
    def _fanout_mode_name(mode_mask: int) -> str:
        if mode_mask & mbx_const.HSX_MBX_MODE_TAP:
            return "tap"
        if mode_mask & mbx_const.HSX_MBX_MODE_FANOUT:
            if mode_mask & mbx_const.HSX_MBX_MODE_FANOUT_BLOCK:
                return "fanout_block"
            if mode_mask & mbx_const.HSX_MBX_MODE_FANOUT_DROP:
                return "fanout"
            return "fanout"
        return "off"

    @staticmethod
    def _parse_stdio_pid(value: Any) -> Optional[int]:
        if value is None:
            return None
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                return None
            lower = stripped.lower()
            if lower in {"default", "global", "template"}:
                return None
            if lower in {"all", "*"}:
                return None
            return int(stripped, 0)
        return int(value)

    def _summarize_stdio_modes(self, modes: Dict[str, int], streams: List[str]) -> List[Dict[str, Any]]:
        summary: List[Dict[str, Any]] = []
        for stream in streams:
            if stream not in modes:
                continue
            mask = modes[stream]
            summary.append(
                {
                    "stream": stream,
                    "mode_mask": mask,
                    "mode": self._fanout_mode_name(mask),
                }
            )
        return summary

    def _process_vm_events(self, events: List[Dict[str, Any]]) -> None:
        for event in events:
            etype = event.get("type")
            pid_value = event.get("pid")
            pid = int(pid_value) if pid_value is not None else None
            payload = {k: v for k, v in event.items() if k not in {"type", "pid", "ts", "seq"}}
            event_type = str(etype or "vm")
            if etype == "trace_step" and pid is not None:
                self._handle_trace_step_event(pid, payload)
            self.emit_event(event_type, pid=pid, data=payload, ts=event.get("ts"))
            if etype == "mailbox_wait" and pid is not None:
                self._mark_task_wait_mailbox(pid, event)
                self.log(
                    "debug",
                    "task waiting on mailbox",
                    pid=pid,
                    descriptor=event.get("descriptor"),
                    handle=event.get("handle"),
                )
            elif etype in {"mailbox_wake", "mailbox_timeout"} and pid is not None:
                reason = "timeout" if etype == "mailbox_timeout" else "mailbox_wake"
                self._mark_task_ready(pid, event, reason=reason, ts=event.get("ts"))
                self.log(
                    "debug",
                    "task mailbox timeout" if etype == "mailbox_timeout" else "task mailbox wake",
                    pid=pid,
                    descriptor=event.get("descriptor"),
                    timeout=(etype == "mailbox_timeout"),
                )
            elif etype == "mailbox_error":
                self.log(
                    "error",
                    "mailbox error",
                    pid=pid,
                    fn=event.get("fn"),
                    error=event.get("error"),
                )
            elif etype == "vm_error":
                self.log(
                    "error",
                    "vm error",
                    pid=pid,
                    error=event.get("error"),
                    pc=event.get("pc"),
                    code_len=event.get("code_len"),
                )
            else:
                self.log("debug", "vm event", event=event)

    def _mark_task_wait_mailbox(self, pid: int, event: Dict[str, Any]) -> None:
        descriptor = event.get('descriptor')
        handle = event.get('handle')
        task = self.tasks.get(pid)
        if task is not None:
            task['state'] = 'waiting_mbx'
            task['wait_mailbox'] = descriptor
            if handle is not None:
                task['wait_handle'] = handle
        state = self.task_states.get(pid)
        if state is not None:
            state['running'] = False
            ctx = state.setdefault('context', {})
            ctx['state'] = 'waiting_mbx'
            ctx['wait_kind'] = 'mailbox'
            ctx['wait_mailbox'] = descriptor
            if handle is not None:
                ctx['wait_handle'] = handle
        details = {
            k: v
            for k, v in {
                "descriptor": descriptor,
                "handle": handle,
                "timeout": event.get("timeout"),
            }.items()
            if v is not None
        }
        self._set_task_state_pending(
            pid,
            "mailbox_wait",
            target_state="waiting_mbx",
            details=details or None,
            ts=event.get("ts"),
        )

    def _mark_task_ready(self, pid: int, event: Dict[str, Any], *, reason: Optional[str] = None, ts: Optional[float] = None) -> None:
        task = self.tasks.get(pid)
        if task is not None:
            task['state'] = 'ready'
            task.pop('wait_mailbox', None)
            task.pop('wait_handle', None)
        state = self.task_states.get(pid)
        if state is not None:
            ctx = state.setdefault('context', {})
            ctx['state'] = 'ready'
            ctx['wait_kind'] = None
            ctx['wait_mailbox'] = None
            ctx['wait_deadline'] = None
            ctx['wait_handle'] = None
            state['running'] = True
        details = {
            k: v
            for k, v in {
                "descriptor": event.get("descriptor"),
                "status": event.get("status"),
                "length": event.get("length"),
                "flags": event.get("flags"),
                "channel": event.get("channel"),
                "src_pid": event.get("src_pid"),
            }.items()
            if v is not None
        }
        pending_reason = reason or ("timeout" if event.get("status") not in (None, 0) else "mailbox_wake")
        self._set_task_state_pending(
            pid,
            pending_reason,
            target_state="ready",
            details=details or None,
            ts=ts,
        )

    def scheduler_stats(self) -> Dict[int, Dict[str, int]]:
        info = self.vm.info()
        return info.get("scheduler", {}).get("counters", {})

    def scheduler_trace_snapshot(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        info = self.vm.info()
        trace = info.get("scheduler", {}).get("trace", [])
        if limit is not None:
            try:
                limit_int = int(limit)
            except (TypeError, ValueError):
                limit_int = None
            if limit_int is not None:
                if limit_int <= 0:
                    trace = []
                else:
                    trace = trace[-limit_int:]
        return trace

    def listen_stdout(self, pid: Optional[int], *, limit: int = 1, max_len: int = 512) -> Dict[str, Any]:
        snapshot = self.mailbox_snapshot()
        descriptors = snapshot.get("descriptors", []) if isinstance(snapshot, dict) else snapshot
        if pid is not None:
            targets = [f"svc:stdio.out@{pid}"]
        else:
            targets = [f"svc:stdio.out@{desc['owner_pid']}" for desc in descriptors if desc.get('name') == 'stdio.out' and desc.get('owner_pid') is not None]
        messages: List[Dict[str, Any]] = []
        for target in targets:
            open_resp = self.mailbox_open(0, target)
            handle = int(open_resp.get("handle", 0))
            try:
                for _ in range(max(1, limit)):
                    recv_resp = self.mailbox_recv(0, handle, max_len=max_len, timeout=0)
                    if recv_resp.get("mbx_status") != mbx_const.HSX_MBX_STATUS_OK:
                        break
                    messages.append({
                        "target": target,
                        "text": recv_resp.get("text", ""),
                        "data_hex": recv_resp.get("data_hex", ""),
                        "flags": recv_resp.get("flags"),
                        "channel": recv_resp.get("channel"),
                        "length": recv_resp.get("length"),
                        "src_pid": recv_resp.get("src_pid"),
                    })
            finally:
                self.mailbox_close(0, handle)
        return {"messages": messages}

    def send_stdin(self, pid: int, *, data: str | None = None, data_hex: str | None = None, channel: Optional[str] = None) -> Dict[str, Any]:
        if data is None and data_hex is None:
            raise ValueError("send_stdin requires data or data_hex")
        target = channel or f"svc:stdio.in@{pid}"
        open_resp = self.mailbox_open(0, target)
        handle = int(open_resp.get("handle", 0))
        try:
            send_resp = self.mailbox_send(0, handle, data=data, data_hex=data_hex)
        finally:
            self.mailbox_close(0, handle)
        send_resp["target"] = target
        return send_resp

    def _auto_loop(self) -> None:
        while not self.auto_event.is_set():
            start = time.perf_counter()
            result = self.step(source="auto")
            vm_running = bool(result.get("running", True))
            runnable = self._has_runnable_tasks()
            any_tasks = bool(self.tasks)
            wait_time = 0.0
            throttle_reason: Optional[str] = None
            if self.clock_rate_hz > 0:
                period = 1.0 / self.clock_rate_hz
                elapsed = time.perf_counter() - start
                wait_time = max(0.0, period - elapsed)
                if result.get("paused"):
                    throttle_reason = "paused"
                    wait_time = max(wait_time, 0.05)
                elif runnable:
                    throttle_reason = None
                elif result.get("sleep_pending"):
                    throttle_reason = "sleep"
                    wait_time = max(wait_time, 0.01)
                elif not vm_running or not any_tasks:
                    throttle_reason = "idle" if not any_tasks else "throttled"
                    wait_time = max(wait_time, 0.05)
            else:
                if runnable:
                    wait_time = 0.0
                    throttle_reason = None
                elif result.get("paused"):
                    throttle_reason = "paused"
                    wait_time = 0.05
                elif not any_tasks:
                    throttle_reason = "idle"
                    wait_time = 0.05
                elif result.get("sleep_pending") or self._has_waiting_tasks():
                    throttle_reason = "sleep"
                    wait_time = 0.01
                elif not vm_running:
                    throttle_reason = "throttled"
                    wait_time = 0.05
                else:
                    wait_time = 0.001

            next_deadline = self._next_sleep_deadline()
            if next_deadline is not None:
                remaining = max(0.0, next_deadline - time.monotonic())
                if wait_time == 0.0 or remaining < wait_time:
                    wait_time = remaining
                    throttle_reason = throttle_reason or "sleep"

            if not any_tasks:
                throttle_reason = throttle_reason or "idle"

            if throttle_reason is None:
                self.clock_mode = "rate" if self.clock_rate_hz > 0 else "active"
            else:
                self.clock_mode = throttle_reason
            self._clock_throttle_reason = throttle_reason
            self._clock_last_wait = wait_time

            if not vm_running and not runnable and not self.tasks:
                self.clock_mode = "idle"
                self._clock_throttle_reason = "idle"
                self._clock_last_wait = 0.0
                break
            if wait_time > 0:
                self.auto_event.wait(timeout=wait_time)

    def restart(self, targets: List[str]) -> Dict[str, Any]:
        normalized = [t.lower() for t in (targets or [])] or ["exec"]
        results: Dict[str, Any] = {}
        if "vm" in normalized:
            try:
                self.vm.restart(["vm"])
                results["vm"] = "requested"
            except Exception as exc:
                results["vm"] = f"error:{exc}"
        if "exec" in normalized:
            results["exec"] = "scheduled"
            self.restart_requested = True
            self.restart_targets = normalized
            if self.server is not None:
                threading.Thread(target=self._delayed_shutdown, daemon=True).start()
        return results

    def _delayed_shutdown(self) -> None:
        time.sleep(0.1)
        try:
            self.stop_auto()
        except Exception:
            pass
        if self.server is not None:
            self.server.shutdown()

    @staticmethod
    def _format_descriptor_target(desc: Dict[str, Any]) -> str:
        namespace = desc.get("namespace")
        try:
            ns = int(namespace)
        except (TypeError, ValueError):
            ns = mbx_const.HSX_MBX_NAMESPACE_SVC
        name = str(desc.get("name") or "")
        owner = desc.get("owner_pid")
        try:
            owner_pid = int(owner) if owner is not None else None
        except (TypeError, ValueError):
            owner_pid = None
        if ns == mbx_const.HSX_MBX_NAMESPACE_PID:
            return name or (f"pid:{owner_pid}" if owner_pid is not None else "pid:")
        prefix_map = {
            mbx_const.HSX_MBX_NAMESPACE_SVC: "svc",
            mbx_const.HSX_MBX_NAMESPACE_APP: "app",
            mbx_const.HSX_MBX_NAMESPACE_SHARED: "shared",
        }
        prefix = prefix_map.get(ns, "svc")
        base = name
        target = f"{prefix}:{base}" if base else f"{prefix}:"
        if ns != mbx_const.HSX_MBX_NAMESPACE_SHARED and owner_pid is not None:
            target = f"{target}@{owner_pid}"
        return target


class _ShellHandler(socketserver.StreamRequestHandler):
    def handle(self) -> None:
        while True:
            line = self.rfile.readline()
            if not line:
                break
            try:
                request = json.loads(line.decode("utf-8"))
            except json.JSONDecodeError:
                self._send({"version": 1, "status": "error", "error": "invalid_json"})
                continue
            try:
                self.server.state.log(
                    "debug",
                    "shell request",
                    command=str(request.get("cmd")),
                    session=request.get("session"),
                )
            except Exception:
                pass
            response = self.server.exec_state_handle(request)
            stream_info = response.get("__stream__") if isinstance(response, dict) else None
            if stream_info:
                ack_payload = stream_info.get("ack")
                if ack_payload is not None:
                    self._send(ack_payload)
                subscription: EventSubscription = stream_info.get("subscription")
                if subscription is not None:
                    self._stream_events(subscription)
                break
            self._send(response)

    def _send(self, payload: Dict[str, Any]) -> None:
        self._write_json(payload)

    def _write_json(self, payload: Dict[str, Any], *, newline: bool = True) -> None:
        data = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        if newline:
            data += b"\n"
        self.wfile.write(data)
        self.wfile.flush()

    def _stream_events(self, subscription: EventSubscription) -> None:
        try:
            while True:
                event = self.server.state.events_next(subscription, timeout=1.0)
                if event is None:
                    if not subscription.active:
                        break
                    continue
                try:
                    self._write_json(event)
                except Exception:
                    raise
        except Exception:
            pass
        finally:
            self.server.state.events_unsubscribe(token=subscription.token)

class ExecutiveServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True

    def __init__(self, server_address, state: ExecutiveState):
        super().__init__(server_address, _ShellHandler)
        self.state = state
        state.server = self

    def exec_state_handle(self, request: Dict[str, Any]) -> Dict[str, Any]:
        cmd = str(request.get("cmd", "")).lower()
        version = int(request.get("version", 1))
        if version != 1:
            return {"version": 1, "status": "error", "error": f"unsupported_version:{version}"}
        try:
            self.state.prune_sessions()
            session_raw = request.get("session")
            session_id = None
            if isinstance(session_raw, str):
                session_id = session_raw.strip() or None
            if cmd == "session.open":
                session_payload = self.state.session_open(
                    client=request.get("client"),
                    capabilities=request.get("capabilities"),
                    pid_lock=request.get("pid_lock"),
                    heartbeat_s=request.get("heartbeat_s"),
                )
                return {"version": 1, "status": "ok", "session": session_payload}
            if cmd == "session.keepalive":
                if session_id is None:
                    raise SessionError("session_required")
                self.state.session_keepalive(session_id)
                return {"version": 1, "status": "ok"}
            if cmd == "session.close":
                if session_id is None:
                    raise SessionError("session_required")
                self.state.session_close(session_id)
                return {"version": 1, "status": "ok"}
            if session_id is not None:
                self.state.touch_session(session_id)
            if cmd == "events.subscribe":
                if session_id is None:
                    raise SessionError("session_required")
                subscription = self.state.events_subscribe(session_id, filters=request.get("filters"))
                metrics = self.state.events_metrics(session_id)
                ack_payload = {
                    "version": 1,
                    "status": "ok",
                    "events": {
                        "token": subscription.token,
                        "max": subscription.max_events,
                        "cursor": self.state.event_seq - 1,
                        "retention_ms": self.state.event_retention_ms,
                        "pending": metrics.get("pending"),
                        "high_water": metrics.get("high_water"),
                        "drops": metrics.get("drop_count"),
                    },
                }
                if subscription.since_seq is not None:
                    ack_payload["events"]["since_seq"] = subscription.since_seq
                return {"__stream__": {"ack": ack_payload, "subscription": subscription}}
            if cmd == "events.ack":
                if session_id is None:
                    raise SessionError("session_required")
                seq_value = request.get("seq")
                if seq_value is None:
                    raise ValueError("events.ack requires 'seq'")
                try:
                    seq = int(seq_value)
                except (TypeError, ValueError):
                    raise ValueError("events.ack seq must be an integer")
                self.state.events_ack(session_id, seq)
                metrics = self.state.events_metrics(session_id)
                return {
                    "version": 1,
                    "status": "ok",
                    "events": {
                        "pending": metrics.get("pending"),
                        "high_water": metrics.get("high_water"),
                        "drops": metrics.get("drop_count"),
                        "last_ack": metrics.get("last_ack"),
                    },
                }
            if cmd == "events.unsubscribe":
                if session_id is None:
                    raise SessionError("session_required")
                removed = self.state.events_unsubscribe(session_id=session_id)
                return {"version": 1, "status": "ok", "unsubscribed": bool(removed)}
            if cmd == "ping":
                return {"version": 1, "status": "ok", "reply": "pong"}
            if cmd == "info":
                pid_value = request.get("pid")
                pid = int(pid_value) if pid_value is not None else None
                return {"version": 1, "status": "ok", "info": self.state.info(pid)}
            if cmd == "attach":
                info = self.state.attach()
                return {"version": 1, "status": "ok", "info": info}
            if cmd == "detach":
                info = self.state.detach()
                return {"version": 1, "status": "ok", "info": info}
            if cmd == "clock":
                op_value = request.get("op")
                if op_value is None:
                    status = self.state.get_clock_status()
                    return {"version": 1, "status": "ok", "clock": status}
                op = str(op_value).lower()
                if op in {"start", "run"}:
                    self.state.start_auto()
                    status = self.state.get_clock_status()
                    return {"version": 1, "status": "ok", "clock": status}
                if op in {"stop", "halt"}:
                    self.state.stop_auto()
                    status = self.state.get_clock_status()
                    return {"version": 1, "status": "ok", "clock": status}
                if op == "status":
                    status = self.state.get_clock_status()
                    return {"version": 1, "status": "ok", "clock": status}
                if op == "rate":
                    rate_value = request.get("rate")
                    if rate_value is None:
                        raise ValueError("clock rate requires 'rate' value")
                    try:
                        rate = float(rate_value)
                    except (TypeError, ValueError):
                        raise ValueError(f"clock rate expects numeric value, got {rate_value!r}")
                    status = self.state.set_clock_rate(rate)
                    return {"version": 1, "status": "ok", "clock": status}
                if op == "step":
                    steps_value = request.get("steps")
                    steps = None
                    if steps_value is not None:
                        try:
                            steps = int(steps_value)
                        except (TypeError, ValueError):
                            raise ValueError(f"clock step expects integer steps, got {steps_value!r}")
                        if steps <= 0:
                            raise ValueError("clock step steps must be positive")
                    pid_value = request.get("pid")
                    pid_int = int(pid_value) if pid_value is not None else None
                    if pid_int is not None:
                        self.state.ensure_pid_access(pid_int, session_id)
                    result = self.state.clock_step(steps, pid=pid_int)
                    status = self.state.get_clock_status()
                    return {"version": 1, "status": "ok", "result": result, "clock": status}
                raise ValueError(f"unknown clock op '{op}'")
            if cmd in {"load", "exec"}:
                path_value = request.get("path")
                if not path_value:
                    raise ValueError(f"{cmd} requires 'path'")
                symbols_override = request.get("symbols")
                sym_path = str(symbols_override) if isinstance(symbols_override, str) else None
                info = self.state.load(str(path_value), verbose=bool(request.get("verbose")), symbols=sym_path)
                return {"version": 1, "status": "ok", "image": info}
            if cmd == "step":
                steps_value = request.get("steps")
                pid_value = request.get("pid")
                steps_int = int(steps_value) if steps_value is not None else None
                pid_int = int(pid_value) if pid_value is not None else None
                if pid_int is not None:
                    self.state.ensure_pid_access(pid_int, session_id)
                result = self.state.step(steps_int, pid=pid_int, source="manual")
                status = self.state.get_clock_status()
                return {"version": 1, "status": "ok", "result": result, "clock": status}
            if cmd == "bp":
                op_value = request.get("op", request.get("action"))
                op = str(op_value or "").lower()
                pid_value = request.get("pid")
                if pid_value is None:
                    raise ValueError("bp requires 'pid'")
                pid_int = int(pid_value)
                if op in {"", "list", "ls"}:
                    info = self.state.breakpoint_list(pid_int)
                    return {"version": 1, "status": "ok", "pid": pid_int, "breakpoints": info.get("breakpoints", [])}
                if op in {"set", "add"}:
                    addr_value = request.get("addr")
                    if addr_value is None:
                        raise ValueError("bp set requires 'addr'")
                    try:
                        addr_int = int(addr_value, 0) if isinstance(addr_value, str) else int(addr_value)
                    except (TypeError, ValueError) as exc:
                        raise ValueError(f"invalid breakpoint addr '{addr_value}'") from exc
                    self.state.ensure_pid_access(pid_int, session_id)
                    info = self.state.breakpoint_add(pid_int, addr_int)
                    return {"version": 1, "status": "ok", "pid": pid_int, "breakpoints": info.get("breakpoints", [])}
                if op in {"clear", "remove", "rm", "del", "delete"}:
                    addr_value = request.get("addr")
                    if addr_value is None:
                        raise ValueError("bp clear requires 'addr'")
                    try:
                        addr_int = int(addr_value, 0) if isinstance(addr_value, str) else int(addr_value)
                    except (TypeError, ValueError) as exc:
                        raise ValueError(f"invalid breakpoint addr '{addr_value}'") from exc
                    self.state.ensure_pid_access(pid_int, session_id)
                    info = self.state.breakpoint_clear(pid_int, addr_int)
                    return {"version": 1, "status": "ok", "pid": pid_int, "breakpoints": info.get("breakpoints", [])}
                if op in {"clear_all", "clearall", "reset"}:
                    self.state.ensure_pid_access(pid_int, session_id)
                    info = self.state.breakpoint_clear_all(pid_int)
                    return {"version": 1, "status": "ok", "pid": pid_int, "breakpoints": info.get("breakpoints", [])}
                raise ValueError(f"unknown bp op '{op}'")
            if cmd == "stack":
                op_value = request.get("op")
                op = str(op_value or "info").lower()
                pid_value = request.get("pid")
                if pid_value is None:
                    raise ValueError("stack requires 'pid'")
                pid_int = int(pid_value)
                max_value = request.get("max") or request.get("limit") or request.get("frames")
                max_frames = None
                if max_value is not None:
                    try:
                        max_frames = int(max_value)
                    except (TypeError, ValueError) as exc:
                        raise ValueError("stack max must be integer") from exc
                if op in {"info", "list"}:
                    info = self.state.stack_info(pid_int, max_frames=max_frames)
                    return {"version": 1, "status": "ok", "stack": info}
                raise ValueError(f"unknown stack op '{op}'")
            if cmd == "symbols":
                op_value = request.get("op")
                op = str(op_value or "list").lower()
                pid_value = request.get("pid")
                if pid_value is None:
                    raise ValueError("symbols requires 'pid'")
                pid_int = int(pid_value)
                if op in {"", "list", "ls"}:
                    type_value = request.get("type") or request.get("kind")
                    offset_value = request.get("offset")
                    limit_value = request.get("limit") or request.get("count")
                    info = self.state.symbols_list(pid_int, kind=type_value, offset=offset_value or 0, limit=limit_value)
                    return {"version": 1, "status": "ok", "symbols": info}
                raise ValueError(f"unknown symbols op '{op}'")
            if cmd == "memory":
                op_value = request.get("op")
                op = str(op_value or "regions").lower()
                pid_value = request.get("pid")
                if pid_value is None:
                    raise ValueError("memory requires 'pid'")
                pid_int = int(pid_value)
                if op in {"regions", "region", "list"}:
                    info = self.state.memory_regions(pid_int)
                    return {"version": 1, "status": "ok", "memory": info}
                raise ValueError(f"unknown memory op '{op}'")
            if cmd == "watch":
                op_value = request.get("op")
                op = str(op_value or "list").lower()
                pid_value = request.get("pid")
                if pid_value is None:
                    raise ValueError("watch requires 'pid'")
                pid_int = int(pid_value)
                if op in {"add", "create"}:
                    expr = request.get("expr") or request.get("expression")
                    if not isinstance(expr, str):
                        raise ValueError("watch add requires 'expr'")
                    watch_type = request.get("type") or request.get("kind")
                    length_value = request.get("length") or request.get("size")
                    length_int = int(length_value) if length_value is not None else None
                    self.state.ensure_pid_access(pid_int, session_id)
                    info = self.state.watch_add(pid_int, expr, watch_type=watch_type, length=length_int)
                    return {"version": 1, "status": "ok", "watch": info}
                if op in {"remove", "del", "delete"}:
                    watch_id = request.get("watch") or request.get("id")
                    if watch_id is None:
                        raise ValueError("watch remove requires 'id'")
                    self.state.ensure_pid_access(pid_int, session_id)
                    info = self.state.watch_remove(pid_int, int(watch_id))
                    return {"version": 1, "status": "ok", "watch": info}
                if op in {"", "list", "ls"}:
                    info = self.state.watch_list(pid_int)
                    return {"version": 1, "status": "ok", "watch": info}
                raise ValueError(f"unknown watch op '{op}'")
            if cmd == "disasm":
                pid_value = request.get("pid")
                if pid_value is None:
                    raise ValueError("disasm requires 'pid'")
                pid_int = int(pid_value)
                addr_value = request.get("addr") or request.get("address")
                count_value = request.get("count")
                mode_value = request.get("mode")
                address = None
                if addr_value is not None:
                    if isinstance(addr_value, str):
                        address = int(addr_value, 0)
                    else:
                        address = int(addr_value)
                count = None
                if count_value is not None:
                    if isinstance(count_value, str):
                        count = int(count_value, 0)
                    else:
                        count = int(count_value)
                info = self.state.disasm_read(pid_int, address=address, count=count, mode=mode_value)
                return {"version": 1, "status": "ok", "disasm": info}
            if cmd == "sym":
                op = str(request.get("op") or "info").lower()
                pid_value = request.get("pid")
                if pid_value is None:
                    raise ValueError("sym requires 'pid'")
                pid_int = int(pid_value)
                if op == "info":
                    info = self.state.symbol_info(pid_int)
                    return {"version": 1, "status": "ok", "symbols": info}
                if op in {"load", "set"}:
                    path_value = request.get("path")
                    if not path_value:
                        raise ValueError("sym load requires 'path'")
                    self.state.ensure_pid_access(pid_int, session_id)
                    result = self.state.load_symbols_for_pid(pid_int, program=self.state.tasks.get(pid_int, {}).get("program"), override=str(path_value))
                    return {"version": 1, "status": "ok", "symbols": result}
                if op in {"lookup", "lookup_name", "name"}:
                    name_value = request.get("name")
                    if not isinstance(name_value, str):
                        raise ValueError("sym lookup requires 'name'")
                    result = self.state.symbol_lookup_name(pid_int, name_value)
                    return {"version": 1, "status": "ok", "symbol": result, "pid": pid_int, "name": name_value}
                if op in {"lookup_addr", "addr"}:
                    addr_value = request.get("address")
                    if addr_value is None:
                        raise ValueError("sym addr requires 'address'")
                    try:
                        address_int = int(addr_value, 0) if isinstance(addr_value, str) else int(addr_value)
                    except (TypeError, ValueError) as exc:
                        raise ValueError(f"invalid address {addr_value!r}") from exc
                    result = self.state.symbol_lookup_addr(pid_int, address_int)
                    return {"version": 1, "status": "ok", "symbol": result, "pid": pid_int, "address": address_int}
                if op in {"line", "lookup_line"}:
                    addr_value = request.get("address")
                    if addr_value is None:
                        raise ValueError("sym line requires 'address'")
                    try:
                        address_int = int(addr_value, 0) if isinstance(addr_value, str) else int(addr_value)
                    except (TypeError, ValueError) as exc:
                        raise ValueError(f"invalid address {addr_value!r}") from exc
                    result = self.state.symbol_lookup_line(pid_int, address_int)
                    return {"version": 1, "status": "ok", "line": result, "pid": pid_int, "address": address_int}
                raise ValueError(f"unknown sym op '{op}'")
            if cmd == "trace":
                op_raw = request.get("op")
                if op_raw is not None:
                    op = str(op_raw).strip().lower()
                    if op == "config":
                        if "changed_regs" in request:
                            changed_value = request.get("changed_regs")
                            if isinstance(changed_value, bool):
                                enabled = changed_value
                            else:
                                if changed_value is None:
                                    raise ValueError("trace.config requires 'changed-regs <on|off>' or 'buffer <size>'")
                                mode_str = str(changed_value).strip().lower()
                                if mode_str in {"on", "true", "1"}:
                                    enabled = True
                                elif mode_str in {"off", "false", "0"}:
                                    enabled = False
                                else:
                                    raise ValueError("trace.config changed_regs must be 'on' or 'off'")
                            info = self.state.set_trace_changed_regs(enabled)
                            return {"version": 1, "status": "ok", "trace": info}
                        if "buffer_size" in request:
                            info = self.state.set_trace_buffer_size(request.get("buffer_size"))
                            return {"version": 1, "status": "ok", "trace": info}
                        raise ValueError("trace.config requires 'changed-regs <on|off>' or 'buffer <size>'")
                    if op in {"records", "history", "export", "import"}:
                        pid_value = request.get("pid")
                        if pid_value is None:
                            raise ValueError(f"trace {op} requires 'pid'")
                        pid_int = int(pid_value)
                        limit_value = request.get("limit")
                        if op == "import":
                            if session_id is None:
                                raise SessionError("session_required")
                            self.state.ensure_pid_access(pid_int, session_id)
                            records_payload = request.get("records")
                            if not isinstance(records_payload, (list, tuple)):
                                raise ValueError("trace import requires 'records' list")
                            replace_flag = bool(request.get("replace", True))
                            info = self.state.trace_import(pid_int, records_payload, replace=replace_flag)
                        elif op == "export":
                            info = self.state.trace_export(pid_int, limit=limit_value)
                        else:
                            info = self.state.trace_records(pid_int, limit=limit_value)
                        return {"version": 1, "status": "ok", "trace": info}
                    raise ValueError(f"unknown trace op '{op}'")
                pid_value = request.get("pid")
                if pid_value is None:
                    raise ValueError("trace requires 'pid'")
                pid_int = int(pid_value)
                self.state.ensure_pid_access(pid_int, session_id)
                mode_value = request.get("mode")
                if isinstance(mode_value, bool):
                    enable = mode_value
                elif mode_value is None:
                    enable = None
                else:
                    mode_str = str(mode_value).strip().lower()
                    if mode_str in {"on", "true", "1"}:
                        enable = True
                    elif mode_str in {"off", "false", "0"}:
                        enable = False
                    else:
                        raise ValueError("trace mode must be 'on' or 'off'")
                trace_info = self.state.trace_task(pid_int, enable)
                return {"version": 1, "status": "ok", "trace": trace_info}
            if cmd == "reload":
                pid_value = request.get("pid")
                if pid_value is None:
                    raise ValueError("reload requires 'pid'")
                pid_int = int(pid_value)
                self.state.ensure_pid_access(pid_int, session_id)
                verbose = bool(request.get("verbose"))
                reload_info = self.state.reload_task(pid_int, verbose=verbose)
                return {"version": 1, "status": "ok", "reload": reload_info}
            if cmd == "peek":
                pid = int(request.get("pid"))
                addr = int(request.get("addr"))
                length = int(request.get("length", 16))
                data = self.state.request_peek(pid, addr, length)
                return {"version": 1, "status": "ok", "data": data}
            if cmd == "poke":
                pid = int(request.get("pid"))
                self.state.ensure_pid_access(pid, session_id)
                addr = int(request.get("addr"))
                data_hex = request.get("data")
                if not isinstance(data_hex, str):
                    raise ValueError("poke requires 'data' hex string")
                self.state.request_poke(pid, addr, data_hex)
                return {"version": 1, "status": "ok"}
            if cmd == "dumpregs":
                pid = int(request.get("pid"))
                regs = self.state.request_dump_regs(pid)
                return {"version": 1, "status": "ok", "registers": regs}
            if cmd == "pause":
                pid_value = request.get("pid")
                if pid_value is None:
                    raise ValueError("pause requires 'pid'")
                pid_int = int(pid_value)
                self.state.ensure_pid_access(pid_int, session_id)
                task = self.state.pause_task(pid_int)
                return {"version": 1, "status": "ok", "task": task}
            if cmd == "resume":
                pid_value = request.get("pid")
                if pid_value is None:
                    raise ValueError("resume requires 'pid'")
                pid_int = int(pid_value)
                self.state.ensure_pid_access(pid_int, session_id)
                task = self.state.resume_task(pid_int)
                return {"version": 1, "status": "ok", "task": task}
            if cmd == "kill":
                pid_value = request.get("pid")
                if pid_value is None:
                    raise ValueError("kill requires 'pid'")
                pid_int = int(pid_value)
                self.state.ensure_pid_access(pid_int, session_id)
                task = self.state.kill_task(pid_int)
                return {"version": 1, "status": "ok", "task": task}
            if cmd == "ps":
                return {"version": 1, "status": "ok", "tasks": self.state.task_list()}
            if cmd == "list":
                pid_value = request.get("pid")
                if pid_value is None:
                    raise ValueError("list requires 'pid'")
                channels = self.state.list_channels(int(pid_value))
                return {"version": 1, "status": "ok", "channels": channels}
            if cmd == "mailbox_snapshot":
                snapshot = self.state.mailbox_snapshot()
                payload: Dict[str, Any] = {"version": 1, "status": "ok"}
                if isinstance(snapshot, dict):
                    payload.update(snapshot)
                else:
                    payload["descriptors"] = snapshot
                return payload
            if cmd == "dmesg":
                limit = request.get("limit")
                limit_int = int(limit) if limit is not None else None
                logs = self.state.get_logs(limit=limit_int)
                return {"version": 1, "status": "ok", "logs": logs}
            if cmd == "stdio_fanout":
                pid_raw = request.get("pid")
                default_only = False
                if isinstance(pid_raw, str) and pid_raw.strip().lower() in {"default", "global", "template"}:
                    default_only = True
                    pid = None
                else:
                    try:
                        pid = self.state._parse_stdio_pid(pid_raw)
                    except Exception as exc:
                        raise ValueError(f"invalid stdio pid '{pid_raw}': {exc}") from exc
                stream_value = request.get("stream")
                stream = str(stream_value) if isinstance(stream_value, str) else None
                mode_value = request.get("mode")
                if mode_value is None:
                    config = self.state.query_stdio_fanout(pid=pid, stream=stream, default_only=default_only)
                    return {"version": 1, "status": "ok", "config": config}
                mode = str(mode_value)
                config = self.state.configure_stdio_fanout(mode, stream=stream or "out", pid=pid)
                return {"version": 1, "status": "ok", "config": config}
            if cmd == "listen":
                pid_value = request.get("pid")
                pid = int(pid_value) if pid_value is not None else None
                limit = int(request.get("limit", 5))
                max_len = int(request.get("max_len", 512))
                result = self.state.listen_stdout(pid, limit=limit, max_len=max_len)
                return {"version": 1, "status": "ok", **result}
            if cmd == "send":
                pid_value = request.get("pid")
                if pid_value is None:
                    raise ValueError("send requires 'pid'")
                pid_int = int(pid_value)
                self.state.ensure_pid_access(pid_int, session_id)
                data = request.get("data")
                data_hex = request.get("data_hex")
                channel = request.get("channel")
                if data_hex is None and not isinstance(data, str):
                    raise ValueError("send requires 'data' or 'data_hex'")
                result = self.state.send_stdin(pid_int, data=data if isinstance(data, str) else None, data_hex=data_hex if isinstance(data_hex, str) else None, channel=channel)
                return {"version": 1, "status": "ok", **result}
            if cmd == "sched":
                pid_value = request.get("pid")
                if pid_value is not None:
                    pid_int = int(pid_value)
                    self.state.ensure_pid_access(pid_int, session_id)
                    task = self.state.set_task_attrs(pid_int, priority=request.get("priority"), quantum=request.get("quantum"))
                    return {"version": 1, "status": "ok", "task": task}
                stats = self.state.scheduler_stats()
                trace_limit = request.get("limit")
                limit_int = int(trace_limit) if trace_limit is not None else None
                trace = self.state.scheduler_trace_snapshot(limit=limit_int)
                return {"version": 1, "status": "ok", "scheduler": {"counters": stats, "trace": trace}}
            if cmd == "restart":
                targets = request.get("targets")
                if isinstance(targets, str):
                    targets_list = targets.split()
                elif isinstance(targets, list):
                    targets_list = [str(t) for t in targets]
                else:
                    targets_list = ["vm", "exec"]
                result = self.state.restart(targets_list)
                return {"version": 1, "status": "ok", "restart": result}
            if cmd == "start_auto":
                self.state.start_auto()
                status = self.state.get_clock_status()
                return {"version": 1, "status": "ok", "clock": status}
            if cmd == "stop_auto":
                self.state.stop_auto()
                status = self.state.get_clock_status()
                return {"version": 1, "status": "ok", "clock": status}
            if cmd == "shutdown":
                self.state.stop_auto()
                threading.Thread(target=self.shutdown, daemon=True).start()
                return {"version": 1, "status": "ok"}
            return {"version": 1, "status": "error", "error": f"unknown_cmd:{cmd}"}
        except Exception as exc:
            self.state.log("error", "command failed", cmd=cmd, error=str(exc))
            return {"version": 1, "status": "error", "error": str(exc)}


def main() -> None:
    parser = argparse.ArgumentParser(description="HSX executive daemon")
    parser.add_argument("--vm-host", default="127.0.0.1", help="HSX VM host")
    parser.add_argument("--vm-port", type=int, default=9999, help="HSX VM port")
    parser.add_argument("--listen", type=int, default=9998, help="Shell listen port")
    parser.add_argument("--listen-host", default="127.0.0.1", help="Shell listen host")
    parser.add_argument("--step", type=int, default=1, help="Instructions per auto step batch")
    args = parser.parse_args()

    vm = VMClient(args.vm_host, args.vm_port)
    state = ExecutiveState(vm, step_batch=args.step)
    try:
        info = state.attach()
        program = info.get("program")
        if program:
            print(f"[execd] auto-attached to {program}")
        else:
            print("[execd] auto-attached to VM")
    except Exception as exc:
        print(f"[execd] auto-attach failed: {exc}", file=sys.stderr)
    server = ExecutiveServer((args.listen_host, args.listen), state)
    print(f"[execd] connected to VM at {args.vm_host}:{args.vm_port}")
    print(f"[execd] listening for shell on {args.listen_host}:{args.listen}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[execd] shutting down")
    finally:
        server.server_close()
        state.stop_auto()
        try:
            state.vm.detach()
        except Exception:
            pass
        state.vm.close()
    if state.restart_requested and state.restart_targets and "exec" in state.restart_targets:
        print("[execd] restarting executive process")
        os.execv(sys.executable, [sys.executable] + sys.argv)


if __name__ == "__main__":
    main()
