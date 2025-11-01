#!/usr/bin/env python3
try:
    from .vmclient import VMClient
except ImportError:
    from vmclient import VMClient

try:
    from . import hsx_mailbox_constants as mbx_const
except ImportError:
    import hsx_mailbox_constants as mbx_const

"""HSX executive daemon.

Connects to the HSX VM RPC server, takes over scheduling (attach/pause/resume),
and exposes a TCP JSON interface for shell clients. This is an initial scaffold;
future work will add task tables, stdout routing, and richer scheduling.
"""
import argparse
import json
import os
import socketserver
import threading
import time
import sys
import uuid
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional, List, Iterable, Deque, Set, Tuple


class SessionError(RuntimeError):
    """Raised when session validation or locking fails."""


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
        self.session_supported_features = {"events", "stack"}
        self.event_lock = threading.RLock()
        self.event_seq = 1
        self.event_history: Deque[Dict[str, Any]] = deque(maxlen=4096)
        self.event_subscriptions: Dict[str, EventSubscription] = {}
        self.session_event_map: Dict[str, str] = {}
        self.event_retention_ms = 5000

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
            subscription.condition.notify_all()

    def _broadcast_event(self, event: Dict[str, Any]) -> None:
        with self.event_lock:
            subscribers = list(self.event_subscriptions.values())
        for sub in subscribers:
            with sub.condition:
                if not sub.active:
                    continue
                if not sub.matches(event):
                    continue
                if sub.max_events > 0 and len(sub.queue) >= sub.max_events:
                    dropped = sub.queue.popleft()
                    sub.last_ack = max(sub.last_ack, dropped.get("seq", sub.last_ack))
                    self._deliver_warning(sub, "event_dropped", dropped_seq=dropped.get("seq"))
                    # ensure room after warning
                    if sub.max_events > 0 and len(sub.queue) >= sub.max_events:
                        sub.queue.popleft()
                sub.queue.append(event)
                sub.condition.notify_all()

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
            subscription = EventSubscription(
                token=token,
                session_id=session_id,
                pids=pids,
                categories=categories,
                queue=deque(),
                condition=condition,
                max_events=record.max_events,
                since_seq=since_seq,
            )
            # preload history if requested
            if since_seq is not None:
                for event in self.event_history:
                    if event.get("seq", 0) > since_seq and subscription.matches(event):
                        subscription.queue.append(event)
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
            subscription.condition.notify_all()

    def events_next(self, subscription: EventSubscription, timeout: float = 1.0) -> Optional[Dict[str, Any]]:
        end_time = time.time() + timeout
        with subscription.condition:
            while subscription.active:
                if subscription.queue:
                    return subscription.queue.popleft()
                remaining = end_time - time.time()
                if remaining <= 0:
                    return None
                subscription.condition.wait(timeout=remaining)
        return None

    def events_session_disconnected(self, session_id: str) -> None:
        self.events_unsubscribe(session_id=session_id)

    def _refresh_tasks(self) -> None:
        try:
            snapshot = self.vm.ps()
        except RuntimeError:
            return
        tasks_block = snapshot.get("tasks", [])
        if isinstance(tasks_block, dict):
            tasks = tasks_block.get("tasks", [])
            self.current_pid = tasks_block.get("current_pid")
        else:
            tasks = tasks_block
            self.current_pid = snapshot.get("current_pid")
        self.tasks = {}
        new_states: Dict[int, Dict[str, Any]] = {}
        for task in tasks:
            if not isinstance(task, dict):
                continue
            pid = int(task.get("pid", 0))
            self.tasks[pid] = task
            state_entry = self.task_states.get(pid, {})
            context = state_entry.get("context", {})
            context["state"] = task.get("state")
            if "exit_status" in task:
                context["exit_status"] = task.get("exit_status")
            if "trace" in task:
                context["trace"] = task.get("trace")
            state_entry["context"] = context
            new_states[pid] = state_entry
        self.task_states = new_states

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

    def load(self, path: str, verbose: bool = False) -> Dict[str, Any]:
        info = self.vm.load(str(Path(path)), verbose=verbose)
        self._refresh_tasks()
        return info

    def step(self, steps: Optional[int] = None, *, pid: Optional[int] = None, source: str = "manual") -> Dict[str, Any]:
        budget = steps if steps is not None else self.step_batch
        with self.lock:
            result = self.vm.step(budget, pid=pid)
        events = result.get('events') or []
        self._process_vm_events(events)
        executed_raw = result.get("executed", 0)
        try:
            executed = int(executed_raw)
        except (TypeError, ValueError):
            executed = 0
        if executed > 0:
            self.total_steps += executed
        if source == "auto":
            self.auto_step_count += 1
            self.auto_step_total += executed
        else:
            self.manual_step_count += 1
            self.manual_step_total += executed
        running_flag = bool(result.get("running", True))
        if (not running_flag) and (executed > 0 or self._last_vm_running):
            self.log(
                "info",
                "vm halted or idle",
                current_pid=result.get("current_pid"),
                executed=result.get("executed"),
                paused=result.get("paused"),
            )
        self._last_vm_running = running_flag
        self._refresh_tasks()
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
        return any(task.get("state") in {"waiting", "waiting_mbx", "waiting_io"} for task in self.tasks.values())

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

    def trace_task(self, pid: int, enable: Optional[bool]) -> Dict[str, Any]:
        result = self.vm.trace(pid, enable)
        pid_val = int(result.get("pid", pid))
        state_entry = self.task_states.get(pid_val, {})
        context = state_entry.get("context", {})
        context["trace"] = result.get("enabled")
        state_entry["context"] = context
        self.task_states[pid_val] = state_entry
        if pid_val in self.tasks:
            self.tasks[pid_val]["trace"] = result.get("enabled")
        return result

    def task_list(self) -> Dict[str, Any]:
        self._refresh_tasks()
        return {"tasks": list(self.tasks.values()), "current_pid": self.current_pid}

    def pause_task(self, pid: int) -> Dict[str, Any]:
        self.get_task(pid)
        with self.lock:
            self.vm.pause(pid=pid)
        self._refresh_tasks()
        return dict(self.get_task(pid))

    def resume_task(self, pid: int) -> Dict[str, Any]:
        self.get_task(pid)
        with self.lock:
            self.vm.resume(pid=pid)
        self._refresh_tasks()
        return dict(self.get_task(pid))

    def kill_task(self, pid: int) -> Dict[str, Any]:
        self.stop_auto()
        with self.lock:
            self.vm.kill(pid)
        self._refresh_tasks()
        return {"pid": pid, "state": "terminated"}

    def set_task_attrs(self, pid: int, *, priority: Optional[int] = None, quantum: Optional[int] = None) -> Dict[str, Any]:
        attrs = self.vm.sched(pid, priority=priority, quantum=quantum)
        self._refresh_tasks()
        return attrs

    def mailbox_snapshot(self) -> List[Dict[str, Any]]:
        return self.vm.mailbox_snapshot()

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
        descriptors = self.mailbox_snapshot()
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
                self._mark_task_ready(pid, event)
                self.log(
                    "debug",
                    "task mailbox wake",
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

    def _mark_task_ready(self, pid: int, event: Dict[str, Any]) -> None:
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
        descriptors = self.mailbox_snapshot()
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
                ack_payload = {
                    "version": 1,
                    "status": "ok",
                    "events": {
                        "token": subscription.token,
                        "max": subscription.max_events,
                        "cursor": self.state.event_seq - 1,
                        "retention_ms": self.state.event_retention_ms,
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
                return {"version": 1, "status": "ok"}
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
                info = self.state.load(str(path_value), verbose=bool(request.get("verbose")))
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
            if cmd == "trace":
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
                descriptors = self.state.mailbox_snapshot()
                return {"version": 1, "status": "ok", "descriptors": descriptors}
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
