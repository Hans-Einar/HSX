"""Shared debugger backend used by IDE/automation front-ends."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence

from python.executive_session import ExecutiveSession, ExecutiveSessionError


class DebuggerBackendError(RuntimeError):
    """Raised when an RPC call fails."""


def _mask_u32(value: Optional[int]) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(value) & 0xFFFFFFFF
    except (TypeError, ValueError):
        return None


@dataclass
class RegisterState:
    registers: Dict[str, int]
    pc: Optional[int]
    sp: Optional[int]
    psw: Optional[int]
    reg_base: Optional[int] = None
    stack_base: Optional[int] = None
    stack_limit: Optional[int] = None
    stack_size: Optional[int] = None
    sp_effective: Optional[int] = None

    def as_list(self) -> List[int]:
        return [self.registers.get(f"R{i}", 0) for i in range(16)]


@dataclass
class StackFrame:
    index: int
    pc: Optional[int]
    sp: Optional[int]
    fp: Optional[int]
    func_name: Optional[str] = None
    symbol: Optional[str] = None
    line: Optional[int] = None
    file: Optional[str] = None


@dataclass
class WatchValue:
    watch_id: int
    expr: str
    length: int
    value: Any
    old_value: Optional[Any] = None
    address: Optional[int] = None
    location: Optional[str] = None


class DebuggerBackend:
    """Minimal RPC helper that wraps ExecutiveSession."""

    def __init__(
        self,
        *,
        host: str = "127.0.0.1",
        port: int = 9998,
        client_name: str = "hsx-dbg-backend",
        features: Optional[Iterable[str]] = None,
        keepalive_enabled: bool = True,
        keepalive_interval: Optional[int] = None,
        session_factory: Callable[..., ExecutiveSession] = ExecutiveSession,
    ) -> None:
        self.host = host
        self.port = int(port)
        self.client_name = client_name
        self.features = list(features or ["events", "stack", "symbols", "memory", "watch", "disasm"])
        self.keepalive_enabled = keepalive_enabled
        self.keepalive_interval = keepalive_interval
        self._session_factory = session_factory
        self._session: Optional[ExecutiveSession] = None
        self._attached_pid: Optional[int] = None

    # ------------------------------------------------------------------
    # Session lifecycle
    # ------------------------------------------------------------------
    def configure(
        self,
        *,
        host: Optional[str] = None,
        port: Optional[int] = None,
        client_name: Optional[str] = None,
        keepalive_enabled: Optional[bool] = None,
        keepalive_interval: Optional[int] = None,
    ) -> None:
        if host:
            self.host = host
        if port is not None:
            self.port = int(port)
        if client_name:
            self.client_name = client_name
        if keepalive_enabled is not None:
            self.keepalive_enabled = keepalive_enabled
        if keepalive_interval is not None:
            self.keepalive_interval = keepalive_interval
        self.disconnect()

    def ensure_session(self) -> ExecutiveSession:
        session = self._session
        if session and not session.session_disabled:
            return session
        session = self._session_factory(
            self.host,
            self.port,
            client_name=self.client_name,
            features=self.features,
            max_events=512,
        )
        try:
            session.configure_keepalive(enabled=self.keepalive_enabled, interval=self.keepalive_interval)
        except Exception:  # pragma: no cover - keepalive errors are non-fatal
            pass
        self._session = session
        return session

    def disconnect(self) -> None:
        session = self._session
        if not session:
            return
        try:
            session.close()
        except Exception:  # pragma: no cover - best effort
            pass
        self._session = None
        self._attached_pid = None

    def start_event_stream(
        self,
        *,
        filters: Optional[Dict[str, Any]] = None,
        callback: Optional[Callable[[Dict[str, Any]], None]] = None,
        ack_interval: int = 10,
    ) -> bool:
        """Start streaming events from the executive."""

        session = self.ensure_session()
        return session.start_event_stream(filters=filters, callback=callback, ack_interval=ack_interval)

    def stop_event_stream(self) -> None:
        """Stop the active event stream, if any."""

        session = self._session
        if session is None:
            return
        session.stop_event_stream()

    def recent_events(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Return up to *limit* of the most recent streamed events."""

        session = self._session
        if session is None:
            return []
        return session.get_recent_events(limit)

    # ------------------------------------------------------------------
    # Generic RPC helper
    # ------------------------------------------------------------------
    def request(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        session = self.ensure_session()
        try:
            return session.request(payload)
        except ExecutiveSessionError as exc:
            raise DebuggerBackendError(str(exc)) from exc

    def _expect_ok(self, response: Dict[str, Any], context: str) -> Dict[str, Any]:
        if response.get("status") != "ok":
            raise DebuggerBackendError(f"{context} failed: {response.get('error', 'unknown')}")
        return response

    # ------------------------------------------------------------------
    # Execution control
    # ------------------------------------------------------------------
    def pause(self, pid: int) -> None:
        resp = self.request({"cmd": "pause", "pid": pid})
        self._expect_ok(resp, "pause")

    def resume(self, pid: int) -> None:
        resp = self.request({"cmd": "resume", "pid": pid})
        self._expect_ok(resp, "resume")

    def clock_start(self) -> None:
        resp = self.request({"cmd": "clock", "op": "start"})
        self._expect_ok(resp, "clock start")

    def step(self, pid: int, *, source_only: bool = False) -> None:
        payload: Dict[str, Any] = {"cmd": "step", "pid": pid}
        if source_only:
            payload["source_only"] = True
        resp = self.request(payload)
        self._expect_ok(resp, "step")

    def attach(self, pid: Optional[int], *, observer: bool = False, heartbeat_s: Optional[int] = None) -> None:
        """Request a pid lock (or observer mode) for the current session."""

        session = self.ensure_session()
        lock_value: Optional[int]
        if observer:
            lock_value = None
        elif pid is None:
            lock_value = None
        else:
            lock_value = int(pid)
        session.configure_session(pid_lock=lock_value, heartbeat_s=heartbeat_s)
        self._attached_pid = pid

    def attached_pid(self) -> Optional[int]:
        """Return the most recently attached PID (if any)."""

        return self._attached_pid

    # ------------------------------------------------------------------
    # Breakpoints
    # ------------------------------------------------------------------
    def set_breakpoint(self, pid: int, address: int) -> None:
        resp = self.request({"cmd": "bp", "op": "set", "pid": pid, "addr": int(address)})
        self._expect_ok(resp, "bp set")

    def clear_breakpoint(self, pid: int, address: int) -> None:
        resp = self.request({"cmd": "bp", "op": "clear", "pid": pid, "addr": int(address)})
        self._expect_ok(resp, "bp clear")

    def list_breakpoints(self, pid: int) -> List[int]:
        resp = self.request({"cmd": "bp", "op": "list", "pid": pid})
        self._expect_ok(resp, "bp list")
        entries = resp.get("breakpoints")
        if isinstance(entries, list):
            result: List[int] = []
            for entry in entries:
                try:
                    value = int(entry, 0) if isinstance(entry, str) else int(entry)
                except (TypeError, ValueError):
                    continue
                result.append(value & 0xFFFFFFFF)
            return result
        return []

    # ------------------------------------------------------------------
    # Task listing
    # ------------------------------------------------------------------
    def list_tasks(self) -> Dict[str, Any]:
        resp = self.request({"cmd": "ps"})
        self._expect_ok(resp, "ps")
        payload = resp.get("tasks")
        if isinstance(payload, dict):
            tasks = payload.get("tasks")
            current = payload.get("current_pid")
        else:
            tasks = []
            current = None
        task_list = []
        if isinstance(tasks, list):
            for entry in tasks:
                if isinstance(entry, dict):
                    task_list.append(dict(entry))
        return {"tasks": task_list, "current_pid": current}

    # ------------------------------------------------------------------
    # Stack & registers
    # ------------------------------------------------------------------
    def get_call_stack(self, pid: int, *, max_frames: Optional[int] = None) -> List[StackFrame]:
        payload: Dict[str, Any] = {"cmd": "stack", "pid": pid}
        if max_frames is not None:
            payload["max"] = max(1, int(max_frames))
        resp = self.request(payload)
        self._expect_ok(resp, "stack")
        frames = []
        stack_block = resp.get("stack") or {}
        for entry in stack_block.get("frames", []):
            if not isinstance(entry, dict):
                continue
            frames.append(
                StackFrame(
                    index=int(entry.get("index") or len(frames)),
                    pc=_mask_u32(entry.get("pc")),
                    sp=_mask_u32(entry.get("sp")),
                    fp=_mask_u32(entry.get("fp")),
                    func_name=entry.get("function") or entry.get("symbol", {}).get("name"),
                    symbol=entry.get("symbol", {}).get("name") if isinstance(entry.get("symbol"), dict) else entry.get("symbol"),
                    line=entry.get("line"),
                    file=entry.get("file"),
                )
            )
        return frames

    def get_register_state(self, pid: int) -> RegisterState:
        resp = self.request({"cmd": "dumpregs", "pid": pid})
        self._expect_ok(resp, "dumpregs")
        registers = resp.get("registers") or resp.get("selected_registers") or {}
        reg_map: Dict[str, int] = {}
        regs_seq = registers.get("regs") if isinstance(registers, dict) else None
        if isinstance(regs_seq, Sequence):
            for idx in range(16):
                value = regs_seq[idx] if idx < len(regs_seq) else 0
                reg_map[f"R{idx}"] = _mask_u32(value) or 0
        else:
            for idx in range(16):
                raw = None
                if isinstance(registers, dict):
                    raw = registers.get(f"R{idx}")
                reg_map[f"R{idx}"] = _mask_u32(raw) or 0
        def _field(*keys: str) -> Optional[int]:
            if not isinstance(registers, dict):
                return None
            for key in keys:
                if key in registers:
                    return registers.get(key)
            return None
        pc = _mask_u32(_field("PC", "pc"))
        sp = _mask_u32(_field("SP", "sp"))
        psw = _mask_u32(_field("PSW", "psw", "flags"))
        reg_base = _mask_u32(_field("reg_base", "REG_BASE"))
        stack_base = _mask_u32(_field("stack_base", "STACK_BASE"))
        stack_limit = _mask_u32(_field("stack_limit", "STACK_LIMIT"))
        stack_size = _mask_u32(_field("stack_size", "STACK_SIZE"))
        sp_effective = _mask_u32(_field("sp_effective", "SP_EFFECTIVE"))
        return RegisterState(
            reg_map,
            pc,
            sp,
            psw,
            reg_base=reg_base,
            stack_base=stack_base,
            stack_limit=stack_limit,
            stack_size=stack_size,
            sp_effective=sp_effective,
        )

    # ------------------------------------------------------------------
    # Watches
    # ------------------------------------------------------------------
    def list_watches(self, pid: int) -> List[WatchValue]:
        resp = self.request({"cmd": "watch", "op": "list", "pid": pid})
        self._expect_ok(resp, "watch list")
        watch_block = resp.get("watch") or {}
        entries = watch_block.get("watches") or watch_block.get("entries") or []
        watches: List[WatchValue] = []
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            watch_id = entry.get("watch_id") or entry.get("id")
            expr = entry.get("expr")
            if watch_id is None or expr is None:
                continue
            watches.append(
                WatchValue(
                    watch_id=int(watch_id),
                    expr=str(expr),
                    length=int(entry.get("length") or 0),
                    value=entry.get("value"),
                    old_value=entry.get("old"),
                    address=_mask_u32(entry.get("address")),
                    location=entry.get("location"),
                )
            )
        return watches

    def add_watch(self, pid: int, expr: str, *, watch_type: Optional[str] = None, length: Optional[int] = None) -> WatchValue:
        payload: Dict[str, Any] = {"cmd": "watch", "op": "add", "pid": pid, "expr": expr}
        if watch_type:
            payload["type"] = watch_type
        if length is not None:
            payload["length"] = max(1, int(length))
        resp = self.request(payload)
        self._expect_ok(resp, "watch add")
        watch = resp.get("watch") or {}
        return WatchValue(
            watch_id=int(watch.get("watch_id", 0)),
            expr=expr,
            length=int(watch.get("length") or 0),
            value=watch.get("value"),
            old_value=watch.get("old"),
            address=_mask_u32(watch.get("address")),
            location=watch.get("location"),
        )

    def remove_watch(self, pid: int, watch_id: int) -> None:
        resp = self.request({"cmd": "watch", "op": "remove", "pid": pid, "watch_id": int(watch_id)})
        self._expect_ok(resp, "watch remove")

    def set_step_mode(self, pid: int, enable: bool) -> None:
        payload: Dict[str, Any] = {"cmd": "step.mode", "pid": int(pid), "mode": bool(enable)}
        resp = self.request(payload)
        self._expect_ok(resp, "step mode")

    # ------------------------------------------------------------------
    # Trace helpers
    # ------------------------------------------------------------------
    def trace_control(self, pid: int, enable: Optional[bool]) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"cmd": "trace", "pid": int(pid)}
        if enable is not None:
            payload["mode"] = bool(enable)
        resp = self.request(payload)
        self._expect_ok(resp, "trace control")
        return resp.get("trace") or {}

    def trace_records(self, pid: int, *, limit: Optional[int] = None, export: bool = False) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"cmd": "trace", "pid": int(pid), "op": "export" if export else "records"}
        if limit is not None:
            payload["limit"] = int(limit)
        resp = self.request(payload)
        self._expect_ok(resp, "trace records")
        trace_info = resp.get("trace") or {}
        records = trace_info.get("records")
        if isinstance(records, list):
            trace_info["records"] = [dict(record) for record in records if isinstance(record, dict)]
        else:
            trace_info["records"] = []
        return trace_info

    # ------------------------------------------------------------------
    # Symbols
    # ------------------------------------------------------------------
    def symbol_info(self, pid: int) -> Dict[str, Any]:
        resp = self.request({"cmd": "sym", "op": "info", "pid": pid})
        self._expect_ok(resp, "sym info")
        return resp.get("symbols") or {}

    def load_symbols(self, pid: int, path: Optional[str] = None) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"cmd": "sym", "op": "load", "pid": pid}
        if path:
            payload["path"] = path
        resp = self.request(payload)
        self._expect_ok(resp, "sym load")
        return resp.get("symbols") or {}

    def symbol_lookup_name(self, pid: int, name: str) -> Optional[Dict[str, Any]]:
        resp = self.request({"cmd": "sym", "op": "lookup_name", "pid": pid, "name": name})
        if resp.get("status") != "ok":
            return None
        return resp.get("symbol")

    # ------------------------------------------------------------------
    # Memory helpers
    # ------------------------------------------------------------------
    def read_memory(self, addr: int, length: int, *, pid: int) -> Optional[bytes]:
        payload = {"cmd": "peek", "pid": pid, "addr": int(addr), "length": int(length)}
        resp = self.request(payload)
        if resp.get("status") != "ok":
            return None
        data = resp.get("data")
        if isinstance(data, str):
            try:
                raw = bytes.fromhex(data)
            except ValueError:
                return None
            if len(raw) >= length:
                return raw[:length]
            return raw
        return None

    def write_memory(self, addr: int, data: bytes, *, pid: int) -> None:
        payload = {"cmd": "poke", "pid": pid, "addr": int(addr), "data": data.hex()}
        resp = self.request(payload)
        self._expect_ok(resp, "poke")
