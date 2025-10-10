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
from typing import List
from pathlib import Path
from typing import Any, Dict, Optional



class ExecutiveState:
    def __init__(self, vm: VMClient, step_cycles: int = 500) -> None:
        self.vm = vm
        self.step_cycles = max(1, step_cycles)
        self.auto_event = threading.Event()
        self.auto_thread: Optional[threading.Thread] = None
        self.lock = threading.Lock()
        self.tasks: Dict[int, Dict[str, Any]] = {}
        self.current_pid: Optional[int] = None
        self.restart_requested: bool = False
        self.restart_targets: Optional[List[str]] = None
        self.server: Optional["ExecutiveServer"] = None
        self.task_states: Dict[int, Dict[str, Any]] = {}

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
            state_entry["context"] = context
            new_states[pid] = state_entry
        self.task_states = new_states

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
        payload["auto"] = self.auto_thread is not None and self.auto_thread.is_alive()
        return payload

    def load(self, path: str, verbose: bool = False) -> Dict[str, Any]:
        info = self.vm.load(str(Path(path)), verbose=verbose)
        self._refresh_tasks()
        return info

    def step(self, cycles: Optional[int] = None) -> Dict[str, Any]:
        budget = cycles if cycles is not None else self.step_cycles
        with self.lock:
            result = self.vm.step(budget)
        events = result.get('events') or []
        self._process_vm_events(events)
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

    def configure_stdio_fanout(self, mode: str, *, stream: str = "out", pid: Optional[int] = None) -> Dict[str, Any]:
        mode_mask = self._fanout_mode_mask(mode)
        streams = self._normalize_stdio_streams(stream)
        results: List[Dict[str, Any]] = []
        if pid is None:
            for item in streams:
                resp = self.vm.mailbox_config_stdio(item, mode_mask, update_existing=True)
                results.append(resp)
        else:
            for item in streams:
                target = f"svc:stdio.{item}@{pid}"
                resp = self.mailbox_bind(0, target, mode=mode_mask)
                result = dict(resp)
                result["target"] = target
                results.append(result)
        return {
            "mode": mode,
            "mode_mask": mode_mask,
            "streams": streams,
            "pid": pid,
            "results": results,
        }

    @staticmethod
    def _normalize_stdio_streams(stream: str) -> List[str]:
        normalized = (stream or "out").lower()
        if normalized in {"both", "all"}:
            return ["out", "err"]
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

    def _process_vm_events(self, events: List[Dict[str, Any]]) -> None:
        for event in events:
            etype = event.get('type')
            pid_value = event.get('pid')
            pid = int(pid_value) if pid_value is not None else None
            if etype == 'mailbox_wait' and pid is not None:
                self._mark_task_wait_mailbox(pid, event)
            elif etype in {'mailbox_wake', 'mailbox_timeout'} and pid is not None:
                self._mark_task_ready(pid, event)

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
            result = self.step()
            if not result.get("running", True):
                break
            if result.get("paused"):
                time.sleep(0.05)
                continue
            if result.get("sleep_pending"):
                time.sleep(0.01)
            else:
                time.sleep(0.001)

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
            if cmd in {"load", "exec"}:
                path_value = request.get("path")
                if not path_value:
                    raise ValueError(f"{cmd} requires 'path'")
                info = self.state.load(str(path_value), verbose=bool(request.get("verbose")))
                return {"version": 1, "status": "ok", "image": info}
            if cmd == "step":
                cycles = request.get("cycles")
                cycles = int(cycles) if cycles is not None else None
                return {"version": 1, "status": "ok", "result": self.state.step(cycles)}
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
            if cmd == "stdio_fanout":
                mode = str(request.get("mode", "off"))
                stream = str(request.get("stream", "out"))
                pid_value = request.get("pid")
                pid = int(pid_value) if pid_value is not None else None
                result = self.state.configure_stdio_fanout(mode, stream=stream, pid=pid)
                return {"version": 1, "status": "ok", "config": result}
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
                if pid_value is None:
                    raise ValueError("sched requires 'pid'")
                task = self.state.set_task_attrs(int(pid_value), priority=request.get("priority"), quantum=request.get("quantum"))
                return {"version": 1, "status": "ok", "task": task}
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
                return {"version": 1, "status": "ok"}
            if cmd == "stop_auto":
                self.state.stop_auto()
                return {"version": 1, "status": "ok"}
            if cmd == "shutdown":
                self.state.stop_auto()
                threading.Thread(target=self.shutdown, daemon=True).start()
                return {"version": 1, "status": "ok"}
            return {"version": 1, "status": "error", "error": f"unknown_cmd:{cmd}"}
        except Exception as exc:
            return {"version": 1, "status": "error", "error": str(exc)}


def main() -> None:
    parser = argparse.ArgumentParser(description="HSX executive daemon")
    parser.add_argument("--vm-host", default="127.0.0.1", help="HSX VM host")
    parser.add_argument("--vm-port", type=int, default=9999, help="HSX VM port")
    parser.add_argument("--listen", type=int, default=9998, help="Shell listen port")
    parser.add_argument("--listen-host", default="127.0.0.1", help="Shell listen host")
    parser.add_argument("--step", type=int, default=500, help="Cycles per step when auto stepping")
    args = parser.parse_args()

    vm = VMClient(args.vm_host, args.vm_port)
    state = ExecutiveState(vm, step_cycles=args.step)
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

























