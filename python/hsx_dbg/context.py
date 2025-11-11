"""Debugger context and session helpers."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from python.executive_session import ExecutiveSession, ExecutiveSessionError
from .symbols import SymbolIndex

LOGGER = logging.getLogger("hsx_dbg.context")


@dataclass
class DebuggerContext:
    """Holds shared CLI debugger state."""

    host: str = "127.0.0.1"
    port: int = 9998
    json_output: bool = False
    _session: Optional[ExecutiveSession] = field(default=None, init=False, repr=False)
    aliases: Dict[str, str] = field(default_factory=dict)
    keepalive_enabled: bool = True
    keepalive_interval: Optional[int] = None
    observer_mode: bool = False
    symbol_path: Optional[Path] = None
    _symbol_index: Optional[SymbolIndex] = field(default=None, init=False, repr=False)
    disabled_breakpoints: Dict[int, set[int]] = field(default_factory=dict)
    _breakpoint_ids: Dict[int, Dict[int, int]] = field(default_factory=dict)
    _breakpoint_lookup: Dict[int, Dict[int, int]] = field(default_factory=dict)
    _next_breakpoint_id: int = 1
    current_frames: Dict[int, int] = field(default_factory=dict)
    _stack_cache: Dict[int, Dict[str, Any]] = field(default_factory=dict)

    def ensure_session(self, *, auto_events: bool = True) -> ExecutiveSession:
        """Create the ExecutiveSession if needed."""
        if self._session and not self._session.session_disabled:
            return self._session
        self._session = ExecutiveSession(
            self.host,
            self.port,
            client_name="hsx-dbg",
            features=["events", "stack", "symbols", "memory", "watch", "disasm"],
            max_events=512,
        )
        try:
            self._session.configure_keepalive(
                enabled=self.keepalive_enabled,
                interval=self.keepalive_interval,
            )
        except Exception as exc:  # pragma: no cover
            LOGGER.debug("keepalive configure failed: %s", exc)
        if auto_events:
            try:
                self._session.start_event_stream(filters={"categories": ["debug_break", "task_state", "scheduler"]})
            except ExecutiveSessionError as exc:
                LOGGER.debug("event stream start failed: %s", exc)
        return self._session

    @property
    def session(self) -> Optional[ExecutiveSession]:
        return self._session

    def disconnect(self) -> None:
        session = self._session
        if not session:
            return
        try:
            session.close()
        except Exception as exc:
            LOGGER.debug("session close failed: %s", exc)
        self._session = None

    def resolve_alias(self, name: str) -> str:
        return self.aliases.get(name, name)

    def set_alias(self, alias: str, command: str) -> None:
        if alias == command:
            self.aliases.pop(alias, None)
            return
        self.aliases[alias] = command

    def list_aliases(self) -> Dict[str, str]:
        return dict(self.aliases)

    def set_symbol_file(self, path: Optional[str]) -> None:
        if path is None:
            self.symbol_path = None
            self._symbol_index = None
            return
        candidate = Path(path).expanduser()
        if not candidate.is_absolute():
            candidate = (Path.cwd() / candidate).resolve()
        self.symbol_path = candidate
        self._symbol_index = None

    def _ensure_symbol_index(self) -> Optional[SymbolIndex]:
        if not self.symbol_path:
            return None
        if self._symbol_index is None:
            try:
                self._symbol_index = SymbolIndex(self.symbol_path)
            except Exception as exc:  # pragma: no cover
                LOGGER.warning("failed to load symbols from %s: %s", self.symbol_path, exc)
                self._symbol_index = None
        return self._symbol_index

    def lookup_symbol(self, name: str) -> List[int]:
        index = self._ensure_symbol_index()
        return index.lookup_symbol(name) if index else []

    def lookup_line(self, path: str, line: int) -> List[int]:
        index = self._ensure_symbol_index()
        return index.lookup_line(path, line) if index else []

    def register_breakpoint(self, pid: int, address: int) -> int:
        store = self._breakpoint_ids.setdefault(pid, {})
        reverse = self._breakpoint_lookup.setdefault(pid, {})
        address = int(address) & 0xFFFF
        if address in reverse:
            return reverse[address]
        bp_id = self._next_breakpoint_id
        self._next_breakpoint_id += 1
        store[bp_id] = address
        reverse[address] = bp_id
        return bp_id

    def breakpoint_id_for(self, pid: int, spec: str) -> Optional[int]:
        store = self._breakpoint_ids.get(pid, {})
        reverse = self._breakpoint_lookup.get(pid, {})
        spec = spec.strip()
        if spec.startswith("#"):
            try:
                candidate = int(spec[1:], 0)
            except ValueError:
                return None
            return candidate if candidate in store else None
        try:
            value = int(spec, 0)
        except ValueError:
            return None
        # treat numeric without prefix as id, hex as address
        if spec.lower().startswith("0x"):
            return reverse.get(value & 0xFFFF)
        return value if value in store else reverse.get(value & 0xFFFF)

    def breakpoint_address_for_id(self, pid: int, bp_id: int) -> Optional[int]:
        return self._breakpoint_ids.get(pid, {}).get(bp_id)

    def forget_breakpoint(self, pid: int, address: int) -> None:
        reverse = self._breakpoint_lookup.setdefault(pid, {})
        store = self._breakpoint_ids.setdefault(pid, {})
        address &= 0xFFFF
        bp_id = reverse.pop(address, None)
        if bp_id is not None:
            store.pop(bp_id, None)
        disabled = self.disabled_breakpoints.get(pid)
        if disabled:
            disabled.discard(address)

    def set_stack_cache(self, pid: int, stack: Dict[str, Any]) -> None:
        self._stack_cache[pid] = stack
        if pid not in self.current_frames:
            self.current_frames[pid] = 0

    def get_stack_cache(self, pid: int) -> Optional[Dict[str, Any]]:
        return self._stack_cache.get(pid)

    def select_frame(self, pid: int, index: int) -> int:
        stack = self._stack_cache.get(pid)
        if not stack:
            self.current_frames[pid] = 0
            return 0
        frames = stack.get("frames") or []
        if not isinstance(frames, list) or not frames:
            self.current_frames[pid] = 0
            return 0
        clamped = max(0, min(int(index), len(frames) - 1))
        self.current_frames[pid] = clamped
        return clamped
