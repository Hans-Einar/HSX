"""Typed command helpers built on top of SessionManager."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .cache import RegisterState, RuntimeCache, StackFrame, WatchValue
from .session import SessionManager


@dataclass
class CommandClient:
    session: SessionManager
    cache: Optional[RuntimeCache] = None
    defaults: Dict[str, Optional[int]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.cache is None and hasattr(self.session, "runtime_cache"):
            self.cache = getattr(self.session, "runtime_cache")

    def _request(self, payload: Dict) -> Dict:
        if not self.session.state.session_id:
            self.session.open()
        payload.setdefault("session", self.session.state.session_id)
        return self.session.transport.send_request(payload)

    def pause(self, pid: Optional[int] = None) -> Dict:
        target = pid or self.session.state.pid
        response = self._request({"cmd": "pause", "pid": target})
        self._invalidate_cache(target, registers=True, stack=True)
        return response

    def resume(self, pid: Optional[int] = None) -> Dict:
        target = pid or self.session.state.pid
        response = self._request({"cmd": "resume", "pid": target})
        self._invalidate_cache(target, registers=True, stack=True)
        return response

    def step(self, pid: Optional[int] = None, *, source_only: bool = False) -> Dict:
        payload = {
            "cmd": "step",
            "pid": pid or self.session.state.pid,
        }
        if source_only:
            payload["source_only"] = True
        response = self._request(payload)
        self._invalidate_cache(payload["pid"], registers=True, stack=True)
        return response

    def set_breakpoint(self, address: int, pid: Optional[int] = None) -> Dict:
        payload = {"cmd": "bp.add", "pid": pid or self.session.state.pid, "address": address}
        return self._request(payload)

    def clear_breakpoint(self, address: int, pid: Optional[int] = None) -> Dict:
        payload = {"cmd": "bp.remove", "pid": pid or self.session.state.pid, "address": address}
        return self._request(payload)

    def list_breakpoints(self, pid: Optional[int] = None) -> Dict:
        payload = {"cmd": "bp.list", "pid": pid or self.session.state.pid}
        return self._request(payload)

    def _invalidate_cache(
        self,
        pid: Optional[int],
        *,
        registers: bool = False,
        stack: bool = False,
        watches: bool = False,
    ) -> None:
        if not self.cache or pid is None:
            return
        if registers:
            self.cache.invalidate_registers(pid)
        if stack:
            self.cache.invalidate_stack(pid)
        if watches:
            self.cache.invalidate_watches(pid)

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------
    def get_register_state(self, pid: Optional[int] = None, *, refresh: bool = False) -> Optional[RegisterState]:
        pid = pid or self.session.state.pid
        if pid is None:
            return None
        if not self.cache:
            registers = self._fetch_registers(pid)
            temp_cache = RuntimeCache()
            return temp_cache.update_registers(pid, registers)
        state = self.cache.get_registers(pid)
        if state is None or refresh:
            registers = self._fetch_registers(pid)
            self.cache.update_registers(pid, registers)
            state = self.cache.get_registers(pid)
        return state

    def get_call_stack(
        self,
        pid: Optional[int] = None,
        *,
        max_frames: Optional[int] = None,
        refresh: bool = False,
    ) -> List[StackFrame]:
        pid = pid or self.session.state.pid
        if pid is None:
            return []
        if not self.cache or refresh:
            frames = self._fetch_stack(pid, max_frames=max_frames)
            if self.cache:
                self.cache.update_call_stack(pid, frames)
                return self.cache.get_call_stack(pid)
            temp_cache = RuntimeCache()
            return temp_cache.update_call_stack(pid, frames)

        def fallback() -> Optional[List[Dict]]:
            return self._fetch_stack(pid, max_frames=max_frames)

        return self.cache.query_call_stack(pid, fallback=fallback)

    def list_watches(self, pid: Optional[int] = None, *, refresh: bool = False) -> List[WatchValue]:
        pid = pid or self.session.state.pid
        if pid is None:
            return []
        if not self.cache or refresh:
            entries = self._fetch_watch_list(pid)
            if self.cache:
                for entry in entries:
                    self.cache.update_watch(pid, entry)
                return self.cache.iter_watches(pid)
            temp_cache = RuntimeCache()
            for entry in entries:
                temp_cache.update_watch(pid, entry)
            return temp_cache.iter_watches(pid)

        def fallback() -> Optional[List[Dict]]:
            return self._fetch_watch_list(pid)

        return self.cache.query_watches(pid, fallback=fallback)

    def add_watch(self, expr: str, pid: Optional[int] = None, *, watch_type: Optional[str] = None, length: Optional[int] = None) -> Dict:
        target = pid or self.session.state.pid
        payload = {"cmd": "watch", "op": "add", "pid": target, "expr": expr}
        if watch_type:
            payload["type"] = watch_type
        if length is not None:
            payload["length"] = length
        response = self._request(payload)
        if response.get("status") != "ok":
            raise RuntimeError(f"watch add failed: {response}")
        watch = response.get("watch") or {}
        if self.cache:
            self.cache.update_watch(target, watch)
        return watch

    def remove_watch(self, watch_id: int, pid: Optional[int] = None) -> Dict:
        target = pid or self.session.state.pid
        payload = {"cmd": "watch", "op": "remove", "pid": target, "id": watch_id}
        response = self._request(payload)
        if response.get("status") != "ok":
            raise RuntimeError(f"watch remove failed: {response}")
        if self.cache:
            self.cache.invalidate_watches(target)
        return response.get("watch") or {}

    def symbol_info(self, pid: Optional[int] = None) -> Dict:
        target = pid or self.session.state.pid
        payload = {"cmd": "sym", "op": "info", "pid": target}
        response = self._request(payload)
        if response.get("status") != "ok":
            raise RuntimeError(f"sym info failed: {response}")
        return response.get("symbols") or {}

    def read_memory(
        self,
        addr: int,
        length: int,
        *,
        pid: Optional[int] = None,
        refresh: bool = False,
    ) -> Optional[bytes]:
        pid = pid or self.session.state.pid
        if pid is None:
            return None
        if not self.cache or refresh:
            data = self._peek_memory(pid, addr, length)
            if self.cache and data is not None:
                self.cache.cache_memory(pid, addr, data)
            return data

        def fallback(a: int, l: int) -> Optional[bytes]:
            return self._peek_memory(pid, a, l)

        return self.cache.query_memory(pid, addr, length, fallback=fallback)

    # ------------------------------------------------------------------
    # RPC fetchers
    # ------------------------------------------------------------------
    def _fetch_registers(self, pid: int) -> Dict:
        response = self._request({"cmd": "dumpregs", "pid": pid})
        if response.get("status") != "ok":
            raise RuntimeError(f"dumpregs failed: {response}")
        registers = response.get("registers") or {}
        if not isinstance(registers, dict):
            raise RuntimeError("dumpregs returned invalid payload")
        return registers

    def _peek_memory(self, pid: int, addr: int, length: int) -> Optional[bytes]:
        payload = {"cmd": "peek", "pid": pid, "addr": int(addr), "length": int(length)}
        response = self._request(payload)
        if response.get("status") != "ok":
            return None
        data_hex = response.get("data")
        if not isinstance(data_hex, str):
            return None
        try:
            raw = bytes.fromhex(data_hex)
        except ValueError:
            return None
        if len(raw) >= length:
            return raw[:length]
        return raw

    def _fetch_stack(self, pid: int, *, max_frames: Optional[int]) -> List[Dict]:
        payload = {"cmd": "stack", "pid": pid}
        if max_frames is not None:
            payload["max"] = int(max_frames)
        response = self._request(payload)
        if response.get("status") != "ok":
            raise RuntimeError(f"stack failed: {response}")
        stack_block = response.get("stack")
        if not isinstance(stack_block, dict):
            return []
        frames = stack_block.get("frames")
        if isinstance(frames, list):
            return [dict(frame) for frame in frames]
        return []

    def _fetch_watch_list(self, pid: int) -> List[Dict]:
        payload = {"cmd": "watch", "op": "list", "pid": pid}
        response = self._request(payload)
        if response.get("status") != "ok":
            raise RuntimeError(f"watch list failed: {response}")
        watch_block = response.get("watch") or {}
        entries = watch_block.get("entries") or watch_block.get("watches") or []
        if isinstance(entries, list):
            return [dict(entry) for entry in entries]
        return []
