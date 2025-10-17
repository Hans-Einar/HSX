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
from collections import deque
from pathlib import Path
from typing import Any, Dict, Optional, List



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
        self.auto_thread = threading.Thread(target=self._auto_loop, daemon=True)
        self.auto_thread.start()

    def stop_auto(self) -> None:
        if self.auto_thread and self.auto_thread.is_alive():
            self.auto_event.set()
            self.auto_thread.join(timeout=1.0)
        self.auto_thread = None

    def get_clock_status(self) -> Dict[str, Any]:
        running = self.auto_thread is not None and self.auto_thread.is_alive()
        rate = self.clock_rate_hz if self.clock_rate_hz > 0 else 0.0
        return {
            "state": "running" if running else "stopped",
            "running": running,
            "rate_hz": rate,
            "step_size": self.step_batch,
            "auto_steps": self.auto_step_count,
            "auto_total_steps": self.auto_step_total,
            "manual_steps": self.manual_step_count,
            "manual_total_steps": self.manual_step_total,
        }

    def _has_runnable_tasks(self) -> bool:
        return any(task.get("state") in {"running", "ready"} for task in self.tasks.values())

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
            wait_time = 0.0
            if self.clock_rate_hz > 0:
                period = 1.0 / self.clock_rate_hz
                elapsed = time.perf_counter() - start
                wait_time = max(0.0, period - elapsed)
                if result.get("paused"):
                    wait_time = max(wait_time, 0.05)
                elif result.get("sleep_pending"):
                    wait_time = max(wait_time, 0.01)
            else:
                if result.get("paused"):
                    wait_time = 0.05
                elif result.get("sleep_pending"):
                    wait_time = 0.01
                elif not vm_running and not runnable:
                    wait_time = 0.05
                else:
                    wait_time = 0.001
            if not vm_running and not runnable and not self.tasks:
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
            self._send(response)

    def _send(self, payload: Dict[str, Any]) -> None:
        data = json.dumps(payload, separators=(",", ":")).encode("utf-8") + b"\n"
        self.wfile.write(data)
        self.wfile.flush()

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
                result = self.state.step(steps_int, pid=pid_int, source="manual")
                status = self.state.get_clock_status()
                return {"version": 1, "status": "ok", "result": result, "clock": status}
            if cmd == "trace":
                pid_value = request.get("pid")
                if pid_value is None:
                    raise ValueError("trace requires 'pid'")
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
                trace_info = self.state.trace_task(int(pid_value), enable)
                return {"version": 1, "status": "ok", "trace": trace_info}
            if cmd == "reload":
                pid_value = request.get("pid")
                if pid_value is None:
                    raise ValueError("reload requires 'pid'")
                verbose = bool(request.get("verbose"))
                reload_info = self.state.reload_task(int(pid_value), verbose=verbose)
                return {"version": 1, "status": "ok", "reload": reload_info}
            if cmd == "peek":
                pid = int(request.get("pid"))
                addr = int(request.get("addr"))
                length = int(request.get("length", 16))
                data = self.state.request_peek(pid, addr, length)
                return {"version": 1, "status": "ok", "data": data}
            if cmd == "poke":
                pid = int(request.get("pid"))
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
                task = self.state.pause_task(int(pid_value))
                return {"version": 1, "status": "ok", "task": task}
            if cmd == "resume":
                pid_value = request.get("pid")
                if pid_value is None:
                    raise ValueError("resume requires 'pid'")
                task = self.state.resume_task(int(pid_value))
                return {"version": 1, "status": "ok", "task": task}
            if cmd == "kill":
                pid_value = request.get("pid")
                if pid_value is None:
                    raise ValueError("kill requires 'pid'")
                task = self.state.kill_task(int(pid_value))
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
                data = request.get("data")
                data_hex = request.get("data_hex")
                channel = request.get("channel")
                if data_hex is None and not isinstance(data, str):
                    raise ValueError("send requires 'data' or 'data_hex'")
                result = self.state.send_stdin(int(pid_value), data=data if isinstance(data, str) else None, data_hex=data_hex if isinstance(data_hex, str) else None, channel=channel)
                return {"version": 1, "status": "ok", **result}
            if cmd == "sched":
                pid_value = request.get("pid")
                if pid_value is not None:
                    task = self.state.set_task_attrs(int(pid_value), priority=request.get("priority"), quantum=request.get("quantum"))
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
