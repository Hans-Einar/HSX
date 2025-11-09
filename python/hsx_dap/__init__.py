"""
HSX Debug Adapter implementation for VS Code (Debug Adapter Protocol).
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import threading
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
    print(f"[hsx-dap] Added repo root to sys.path: {REPO_ROOT}", flush=True)

from python.hsxdbg import (
    CommandClient,
    EventBus,
    EventSubscription,
    RuntimeCache,
    SessionConfig,
    SessionManager,
    TraceStepEvent,
    WarningEvent,
    WatchUpdateEvent,
    DebugBreakEvent,
    StdStreamEvent,
)
from python.hsxdbg.transport import TransportConfig


JsonDict = Dict[str, Any]
REGISTER_NAMES = {
    f"R{idx}": f"R{idx}" for idx in range(16)
}
REGISTER_NAMES.update({"PC": "PC", "SP": "SP", "PSW": "PSW"})


class DAPProtocol:
    """Basic Debug Adapter Protocol transport over stdin/stdout."""

    def __init__(self, reader, writer) -> None:
        self.reader = reader
        self.writer = writer
        self.seq = 1
        self._write_lock = threading.Lock()

    def send_event(self, event: str, body: Optional[JsonDict] = None) -> None:
        message = {
            "seq": self.seq,
            "type": "event",
            "event": event,
            "body": body or {},
        }
        self.seq += 1
        self._send_message(message)

    def send_response(
        self,
        request_seq: int,
        command: str,
        *,
        success: bool = True,
        body: Optional[JsonDict] = None,
        message: Optional[str] = None,
    ) -> None:
        payload: JsonDict = {
            "seq": self.seq,
            "type": "response",
            "request_seq": request_seq,
            "command": command,
            "success": success,
            "body": body or {},
        }
        if message:
            payload["message"] = message
        self.seq += 1
        self._send_message(payload)

    def _send_message(self, message: JsonDict) -> None:
        data = json.dumps(message)
        encoded = data.encode("utf-8")
        header = f"Content-Length: {len(encoded)}\r\n\r\n".encode("ascii")
        with self._write_lock:
            self.writer.write(header)
            self.writer.write(encoded)
            self.writer.flush()

    def read_message(self) -> Optional[JsonDict]:
        """Read a single DAP message. Returns None on EOF."""
        content_length: Optional[int] = None
        while True:
            line = self.reader.readline()
            if not line:
                return None
            if isinstance(line, bytes):
                decoded = line.decode("utf-8")
            else:
                decoded = line
            decoded = decoded.strip()
            if not decoded:
                break
            if decoded.lower().startswith("content-length:"):
                _, value = decoded.split(":", 1)
                content_length = int(value.strip())
        if content_length is None:
            return None
        body = self.reader.read(content_length)
        if not body:
            return None
        if isinstance(body, bytes):
            body = body.decode("utf-8")
        return json.loads(body)


def _canonical_path(value: str) -> str:
    return str(value).replace("\\", "/").lower()


class SymbolMapper:
    """Helper to map source lines to PCs using .sym metadata."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._line_map: Dict[str, Dict[int, List[int]]] = defaultdict(lambda: defaultdict(list))
        self._pc_map: Dict[int, Dict[str, Any]] = {}
        self._locals_by_function: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        self._globals: List[Dict[str, Any]] = []
        self._load()

    def _load(self) -> None:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return
        instructions = data.get("instructions") or []
        for inst in instructions:
            line = inst.get("line")
            pc = inst.get("pc")
            file_value = inst.get("file")
            if line is None or pc is None or not file_value:
                continue
            directory = inst.get("directory")
            keys = {_canonical_path(file_value), _canonical_path(Path(file_value).name)}
            if directory:
                try:
                    full = Path(directory) / file_value
                    keys.add(_canonical_path(full))
                    keys.add(_canonical_path(str(full.resolve())))
                except Exception:
                    pass
            for key in keys:
                lines = self._line_map[key]
                lines.setdefault(int(line), []).append(int(pc))
            self._pc_map[int(pc)] = {
                "file": file_value,
                "directory": directory,
                "line": line,
                "column": inst.get("column"),
            }
        symbols_block = data.get("symbols") or {}
        if isinstance(symbols_block, dict):
            locals_block = symbols_block.get("locals") or []
            if isinstance(locals_block, list):
                for loc in locals_block:
                    func = loc.get("function")
                    if isinstance(func, str):
                        self._locals_by_function[func].append(loc)
            globals_block = symbols_block.get("variables") or []
            if isinstance(globals_block, list):
                self._globals = [entry for entry in globals_block if isinstance(entry, dict)]
        elif isinstance(symbols_block, list):
            self._globals = [entry for entry in symbols_block if isinstance(entry, dict)]

    def lookup(self, source_path: str, line: int) -> List[int]:
        key = _canonical_path(source_path)
        if key in self._line_map:
            return self._line_map[key].get(int(line), [])
        filename_key = _canonical_path(Path(source_path).name)
        return self._line_map.get(filename_key, {}).get(int(line), [])

    def lookup_pc(self, pc: int) -> Optional[Dict[str, Any]]:
        return self._pc_map.get(int(pc) & 0xFFFF)

    def locals_for_function(self, func_name: Optional[str]) -> List[Dict[str, Any]]:
        if not func_name:
            return []
        return list(self._locals_by_function.get(func_name, []))

    def globals_list(self) -> List[Dict[str, Any]]:
        return list(self._globals)


@dataclass
class _FrameRecord:
    pid: int
    name: str
    line: int
    column: int
    file: Optional[str]
    pc: Optional[int]
    sp: Optional[int] = None
    fp: Optional[int] = None


@dataclass
class _ScopeRecord:
    variables: List[JsonDict] = field(default_factory=list)


class HSXDebugAdapter:
    """DAP request dispatcher bridging VS Code to hsxdbg."""

    def __init__(self, protocol: DAPProtocol) -> None:
        self.protocol = protocol
        self.logger = logging.getLogger("hsx-dap")
        self.event_bus: Optional[EventBus] = None
        self.runtime_cache: Optional[RuntimeCache] = None
        self.session: Optional[SessionManager] = None
        self.client: Optional[CommandClient] = None
        self.current_pid: Optional[int] = None
        self._initialized = False
        self._event_token: Optional[int] = None
        self._frames: Dict[int, _FrameRecord] = {}
        self._next_frame_id = 1
        self._scopes: Dict[int, _ScopeRecord] = {}
        self._next_scope_id = 1
        self._breakpoints: Dict[str, List[JsonDict]] = {}
        self._symbol_mapper: Optional[SymbolMapper] = None
        self._symbol_path: Optional[Path] = None
        self._symbol_mtime: Optional[float] = None
        self._watch_expr_to_id: Dict[str, int] = {}
        self._watch_id_to_expr: Dict[int, str] = {}
        self._pending_breakpoints: Dict[str, Dict[str, Any]] = {}
        self._sym_hint: Optional[Path] = None

    def serve(self) -> None:
        while True:
            message = self.protocol.read_message()
            if message is None:
                print("[hsx-dap] EOF on stdin, shutting down", flush=True)
                break
            if message.get("type") != "request":
                continue
            self._handle_request(message)
        self._shutdown()

    # Request handlers -------------------------------------------------
    def _handle_request(self, request: JsonDict) -> None:
        command = request.get("command")
        seq = int(request.get("seq", 0))
        arguments = request.get("arguments") or {}
        handler = getattr(self, f"_handle_{command}", None)
        if handler is None:
            self.protocol.send_response(seq, command or "", success=False, message=f"Unsupported command: {command}")
            return
        try:
            body = handler(arguments) or {}
            self.protocol.send_response(seq, command or "", body=body)
        except Exception as exc:  # pragma: no cover - protective
            self.logger.exception("DAP command failed: %s", command)
            self.protocol.send_response(seq, command or "", success=False, message=str(exc))

    def _handle_initialize(self, args: JsonDict) -> JsonDict:
        capabilities = {
            "supportsConfigurationDoneRequest": True,
            "supportsPauseRequest": True,
            "supportsSetVariable": False,
            "supportsEvaluateForHovers": False,
            "supportsConditionalBreakpoints": False,
            "supportsStepBack": False,
            "supportsReadMemoryRequest": False,
            "supportsWriteMemoryRequest": False,
            "supportsTerminateRequest": True,
        }
        self._initialized = True
        self.protocol.send_event("initialized", {})
        return {"capabilities": capabilities}

    def _handle_launch(self, args: JsonDict) -> JsonDict:
        host = str(args.get("host") or "127.0.0.1")
        port = int(args.get("port") or 9998)
        pid_value = args.get("pid")
        if pid_value is None:
            raise ValueError("launch request missing 'pid'")
        self.current_pid = int(pid_value)
        sym_arg = args.get("symPath") or args.get("sym_path")
        program_path = args.get("program")
        self._sym_hint = None
        search_paths = [sym_arg]
        if program_path:
            search_paths.append(program_path)
        for candidate in search_paths:
            if not candidate:
                continue
            try:
                path = Path(candidate)
            except Exception:
                continue
            try:
                if program_path and Path(candidate) == Path(program_path):
                    path = path.with_suffix(".sym")
            except Exception:
                pass
            if not path.is_absolute():
                path = (Path.cwd() / path).resolve(strict=False)
            if path.exists():
                self._sym_hint = path
                break
        self._connect(host, port, self.current_pid)
        self._reapply_pending_breakpoints()
        return {}

    def _handle_attach(self, args: JsonDict) -> JsonDict:
        return self._handle_launch(args)

    def _handle_configurationDone(self, args: JsonDict) -> JsonDict:  # noqa: N802
        return {}

    def _handle_disconnect(self, args: JsonDict) -> JsonDict:
        self.protocol.send_event("terminated", {})
        self._shutdown()
        return {}

    def _handle_threads(self, args: JsonDict) -> JsonDict:
        pid = self.current_pid or 0
        return {"threads": [{"id": pid, "name": f"PID {pid}"}]}

    def _handle_continue(self, args: JsonDict) -> JsonDict:
        self._ensure_client()
        self.client.resume(self.current_pid)
        self.protocol.send_event("continued", {"threadId": self.current_pid})
        return {"allThreadsContinued": True}

    def _handle_pause(self, args: JsonDict) -> JsonDict:
        self._ensure_client()
        self.client.pause(self.current_pid)
        self.protocol.send_event(
            "stopped",
            {
                "reason": "pause",
                "threadId": self.current_pid,
                "description": "Paused by client",
            },
        )
        return {}

    def _handle_next(self, args: JsonDict) -> JsonDict:
        self._ensure_client()
        self.client.step(self.current_pid, source_only=False)
        return {}

    def _handle_stepIn(self, args: JsonDict) -> JsonDict:  # noqa: N802
        return self._handle_next(args)

    def _handle_stepOut(self, args: JsonDict) -> JsonDict:  # noqa: N802
        return self._handle_next(args)

    def _handle_stackTrace(self, args: JsonDict) -> JsonDict:  # noqa: N802
        self._ensure_client()
        start = int(args.get("startFrame") or 0)
        levels = int(args.get("levels") or 20)
        frames = self.client.get_call_stack(self.current_pid, max_frames=start + levels)
        dap_frames = []
        self._frames.clear()
        self._next_frame_id = 1
        for idx, frame in enumerate(frames[start : start + levels]):
            frame_id = self._next_frame_id
            self._next_frame_id += 1
            self._frames[frame_id] = _FrameRecord(
                pid=self.current_pid or 0,
                name=frame.func_name or frame.symbol or f"frame {frame.index}",
                line=frame.line or 0,
                column=1,
                file=frame.file,
                pc=frame.pc,
                sp=frame.sp,
                fp=frame.fp,
            )
            if (not self._frames[frame_id].file or not self._frames[frame_id].line) and frame.pc is not None:
                mapped = self._map_pc_to_source(frame.pc)
                if mapped:
                    self._frames[frame_id].file = mapped.get("path")
                    self._frames[frame_id].line = mapped.get("line", 0)
            dap_frames.append(
                {
                    "id": frame_id,
                    "name": self._frames[frame_id].name,
                    "line": self._frames[frame_id].line,
                    "column": 1,
                    "source": self._render_source(self._frames[frame_id].file),
                    "instructionPointerReference": f"{frame.pc:#x}" if frame.pc is not None else None,
                }
            )
        return {"stackFrames": dap_frames, "totalFrames": len(frames)}

    def _handle_scopes(self, args: JsonDict) -> JsonDict:
        frame_id = int(args.get("frameId"))
        frame = self._frames.get(frame_id)
        if not frame:
            return {"scopes": []}
        scopes = []
        self._scopes.clear()
        self._next_scope_id = 1
        registers = self._format_registers()
        if registers:
            scopes.append(self._make_scope("Registers", registers, expensive=False))
        locals_scope = self._format_locals(frame)
        if locals_scope:
            scopes.append(self._make_scope("Locals", locals_scope, expensive=False))
        globals_scope = self._format_globals()
        if globals_scope:
            scopes.append(self._make_scope("Globals", globals_scope, expensive=True))
        watches = self._format_watches()
        scopes.append(self._make_scope("Watches", watches, expensive=False))
        return {"scopes": scopes}

    def _handle_variables(self, args: JsonDict) -> JsonDict:
        reference = int(args.get("variablesReference"))
        scope = self._scopes.get(reference)
        return {"variables": scope.variables[:] if scope else []}

    def _handle_setBreakpoints(self, args: JsonDict) -> JsonDict:  # noqa: N802
        source = args.get("source") or {}
        source_path = source.get("path") or source.get("name")
        source_key = self._canonical_source_key(source)
        breakpoints = args.get("breakpoints") or []
        self._ensure_symbol_mapper()
        if not self.client:
            self._pending_breakpoints[source_key] = {"source": source, "breakpoints": breakpoints}
            results = []
            for bp in breakpoints:
                results.append(
                    {
                        "verified": False,
                        "line": bp.get("line"),
                        "message": "pending connection",
                    }
                )
            return {"breakpoints": results}
        results, entries = self._apply_breakpoints_for_source(source_key, source_path, source, breakpoints)
        self._breakpoints[source_key] = entries
        return {"breakpoints": results}

    def _handle_threadsRequest(self, args: JsonDict) -> JsonDict:  # pragma: no cover - compatibility alias
        return self._handle_threads(args)

    def _handle_evaluate(self, args: JsonDict) -> JsonDict:
        expression = str(args.get("expression") or "").strip()
        context = str(args.get("context") or "")
        frame = self._resolve_frame(args.get("frameId"))
        if not expression:
            return {"result": "", "variablesReference": 0}
        self._ensure_client()
        self._ensure_symbol_mapper()

        register_value = self._evaluate_register_expression(expression)
        if register_value is not None:
            return {"result": register_value, "type": "register", "variablesReference": 0}

        pointer_value = self._evaluate_pointer_expression(expression, frame)
        if pointer_value is not None:
            return pointer_value

        include_globals = context != "watch"
        symbol_value = self._evaluate_symbol_expression(
            expression,
            frame,
            include_globals=include_globals,
        )
        if symbol_value is not None:
            return symbol_value

        if context == "watch":
            try:
                watch = self._ensure_watch_entry(expression)
            except RuntimeError as exc:
                return {"result": str(exc), "variablesReference": 0}
            except Exception as exc:
                return {"result": f"watch error: {exc}", "variablesReference": 0}
            if not watch:
                return {"result": "watch unavailable", "variablesReference": 0}
            return {"result": self._describe_watch_value(watch), "variablesReference": 0}

        return {"result": f"unsupported expression '{expression}'", "variablesReference": 0}

    def _handle_setExceptionBreakpoints(self, args: JsonDict) -> JsonDict:  # noqa: N802
        return {"breakpoints": []}

    # Internal helpers -------------------------------------------------
    def _connect(self, host: str, port: int, pid: int) -> None:
        self.logger.info("Connecting to executive at %s:%d (PID %d)", host, port, pid)
        self.event_bus = EventBus()
        self.event_bus.start()
        self.runtime_cache = RuntimeCache()
        session_config = SessionConfig(client_name="hsx-dap", pid_lock=pid)
        transport_config = TransportConfig(host=host, port=port)
        self.session = SessionManager(
            transport_config=transport_config,
            session_config=session_config,
            event_bus=self.event_bus,
            runtime_cache=self.runtime_cache,
        )
        self.session.open()
        self.session.subscribe_events({"pid": [pid], "categories": ["debug_break", "watch_update", "stdout", "stderr", "warning"]})
        self.client = CommandClient(session=self.session, cache=self.runtime_cache)
        self._watch_expr_to_id.clear()
        self._watch_id_to_expr.clear()
        self._ensure_symbol_mapper(force=True)
        if self.event_bus:
            subscription = EventSubscription(handler=self._handle_exec_event)
            self._event_token = self.event_bus.subscribe(subscription)

    def _handle_exec_event(self, event) -> None:
        if isinstance(event, DebugBreakEvent):
            reason = event.reason or "breakpoint"
            self.protocol.send_event(
                "stopped",
                {
                    "reason": reason,
                    "threadId": event.pid or self.current_pid,
                    "description": event.symbol or reason,
                },
            )
        elif isinstance(event, WarningEvent):
            text = f"warning: {event.reason or 'warning'}\n"
            self.protocol.send_event("output", {"category": "console", "output": text})
        elif isinstance(event, StdStreamEvent):
            category = "stdout" if event.stream == "stdout" else "stderr"
            self.protocol.send_event("output", {"category": category, "output": event.text + ("\n" if not event.text.endswith("\n") else "")})
        elif isinstance(event, WatchUpdateEvent):
            if event.watch_id is not None and event.expr:
                self._watch_expr_to_id.setdefault(event.expr, event.watch_id)
                self._watch_id_to_expr.setdefault(event.watch_id, event.expr)
            expr = event.expr or self._watch_id_to_expr.get(event.watch_id or -1) or ""
            label = f"{expr} " if expr else ""
            text = f"watch {label}[{event.watch_id}] -> {event.new_value}\n"
            self.protocol.send_event("output", {"category": "console", "output": text})
            self._invalidate_variables_scope()
        elif isinstance(event, TraceStepEvent):
            # no-op; cache controller already updated registers
            return

    def _ensure_client(self) -> None:
        if not self.client:
            raise RuntimeError("debug session not connected")

    def _format_registers(self) -> List[JsonDict]:
        if not self.client:
            return []
        state = self.client.get_register_state(self.current_pid)
        if not state:
            return []
        variables = []
        for name in sorted(state.registers.keys()):
            variables.append({"name": name, "value": f"0x{state.registers[name]:08X}", "type": "register"})
        if state.pc is not None:
            variables.append({"name": "PC", "value": f"0x{state.pc:08X}", "type": "register"})
        if state.sp is not None:
            variables.append({"name": "SP", "value": f"0x{state.sp:08X}", "type": "register"})
        if state.psw is not None:
            variables.append({"name": "PSW", "value": f"0x{state.psw:08X}", "type": "register"})
        return variables

    def _format_watches(self) -> List[JsonDict]:
        if not self.client:
            return []
        watches = self.client.list_watches(self.current_pid, refresh=True)
        results = []
        for watch in watches:
            display = self._describe_watch_value(watch)
            memory_ref = f"0x{watch.address:08X}" if getattr(watch, "address", None) is not None else None
            results.append(
                {
                    "name": watch.expr or f"watch {watch.watch_id}",
                    "value": display,
                    "type": "watch",
                    "evaluateName": watch.expr or None,
                    "variablesReference": 0,
                    **({"memoryReference": memory_ref} if memory_ref else {}),
                }
            )
        return results

    def _make_scope(self, name: str, variables: List[JsonDict], *, expensive: bool) -> JsonDict:
        scope_id = self._next_scope_id
        self._next_scope_id += 1
        self._scopes[scope_id] = _ScopeRecord(variables=variables)
        return {"name": name, "variablesReference": scope_id, "expensive": expensive}

    def _format_locals(self, frame: _FrameRecord) -> List[JsonDict]:
        if not self._symbol_mapper or not frame.name:
            return []
        symbols = self._symbol_mapper.locals_for_function(frame.name)
        variables: List[JsonDict] = []
        for symbol in symbols:
            name = symbol.get("name") or "<local>"
            value = self._format_symbol_value(symbol, frame)
            location_desc = value or self._describe_local_symbol(symbol)
            variables.append(
                {
                    "name": name,
                    "value": location_desc,
                    "type": "local",
                }
            )
        return variables

    def _format_globals(self) -> List[JsonDict]:
        if not self._symbol_mapper:
            return []
        entries = self._symbol_mapper.globals_list()
        variables: List[JsonDict] = []
        for entry in entries:
            name = entry.get("name") or "<global>"
            address = entry.get("address")
            if isinstance(address, str) and address.startswith("0x"):
                try:
                    address = int(address, 16)
                except ValueError:
                    address = None
            if isinstance(address, (int, float)):
                located = self._format_symbol_value(entry, None, address=int(address))
                value = located or f"@0x{int(address):04X} (use watch to inspect)"
            else:
                value = "use watch to inspect"
            variables.append(
                {
                    "name": name,
                    "value": value,
                    "type": "global",
                }
            )
        return variables

    def _parse_address(self, bp: JsonDict) -> Optional[int]:
        value = bp.get("instructionReference") or bp.get("address")
        if value is None:
            return None
        if isinstance(value, str):
            value = value.strip()
            base = 16 if value.lower().startswith("0x") else 10
            return int(value, base)
        if isinstance(value, (int, float)):
            return int(value)
        return None

    def _canonical_source_key(self, source: JsonDict) -> str:
        path = source.get("path")
        if path:
            return _canonical_path(path)
        name = source.get("name")
        return str(name).lower() if name else "<global>"

    def _clear_breakpoints(self, source_key: str) -> None:
        entries = self._breakpoints.get(source_key, [])
        if not entries or not self.client:
            self._breakpoints[source_key] = []
            return
        for entry in entries:
            addresses = entry.get("addresses") or []
            if isinstance(addresses, int):
                addresses = [addresses]
            for address in addresses:
                try:
                    self.client.clear_breakpoint(int(address), pid=self.current_pid)
                except Exception:
                    self.logger.debug("failed to clear breakpoint 0x%X", address)
        self._breakpoints[source_key] = []

    def _resolve_breakpoint_addresses(self, source_path: Optional[str], line: Optional[int], bp: JsonDict) -> List[int]:
        addresses: List[int] = []
        lookup_path = source_path or bp.get("sourcePath") or bp.get("sourceName")
        if self._symbol_mapper and lookup_path and line:
            try:
                addresses.extend(self._symbol_mapper.lookup(lookup_path, int(line)))
            except Exception as exc:
                self.logger.debug("symbol lookup failed for %s:%s (%s)", lookup_path, line, exc)
        parsed = self._parse_address(bp)
        if parsed is not None:
            addresses.append(parsed)
        ordered: List[int] = []
        seen: set[int] = set()
        for addr in addresses:
            if addr in seen:
                continue
            seen.add(addr)
            ordered.append(addr)
        return ordered

    def _resolve_sym_path(self, raw_path: str) -> Optional[Path]:
        candidates = []
        try:
            candidates.append(Path(raw_path))
        except Exception:
            return None
        if REPO_ROOT:
            candidates.append(REPO_ROOT / raw_path)
        candidates.append(Path.cwd() / raw_path)
        for candidate in candidates:
            try:
                if candidate.exists():
                    return candidate.resolve()
            except OSError:
                continue
        return None

    def _ensure_symbol_mapper(self, force: bool = False) -> None:
        if not self.client or self.current_pid is None:
            return
        if not force and self._symbol_mapper is not None:
            return
        info: Dict[str, Any]
        try:
            info = self.client.symbol_info(self.current_pid)
        except Exception as exc:
            self.logger.debug("symbol_info failed: %s", exc)
            return
        if not info.get("loaded"):
            hint = str(self._sym_hint) if self._sym_hint else None
            if hint:
                try:
                    self.client.load_symbols(self.current_pid, path=hint)
                    info = self.client.symbol_info(self.current_pid)
                except Exception as exc:
                    self.logger.warning("symbol load failed for pid %s: %s", self.current_pid, exc)
                    info = {}
            if not info.get("loaded"):
                if force:
                    self.logger.info("symbols not loaded for pid %s", self.current_pid)
                self._symbol_mapper = None
                self._symbol_path = None
                self._symbol_mtime = None
                return
        path_value = info.get("path") or (str(self._sym_hint) if self._sym_hint else None)
        if not path_value:
            return
        resolved = self._resolve_sym_path(path_value)
        if not resolved:
            self.logger.warning("symbol file not found: %s", path_value)
            self._symbol_mapper = None
            return
        mtime: Optional[float] = None
        try:
            mtime = resolved.stat().st_mtime
        except OSError:
            pass
        if (
            not force
            and self._symbol_mapper is not None
            and self._symbol_path == resolved
            and (mtime is None or self._symbol_mtime == mtime)
        ):
            return
        try:
            self._symbol_mapper = SymbolMapper(resolved)
            self._symbol_path = resolved
            self._symbol_mtime = mtime
            if not self._sym_hint:
                self._sym_hint = resolved
            self.logger.info("Loaded symbol map for pid %s from %s", self.current_pid, resolved)
        except Exception as exc:
            self.logger.warning("failed to parse %s: %s", resolved, exc)
            self._symbol_mapper = None

    def _apply_breakpoints_for_source(
        self,
        source_key: str,
        source_path: Optional[str],
        source: JsonDict,
        breakpoints: List[JsonDict],
    ) -> tuple[List[JsonDict], List[JsonDict]]:
        self._clear_breakpoints(source_key)
        results: List[JsonDict] = []
        new_entries: List[JsonDict] = []
        for bp in breakpoints:
            line = bp.get("line")
            addresses = self._resolve_breakpoint_addresses(source_path, line, bp)
            if not addresses:
                reason = "unmapped source line" if line and self._symbol_mapper else "address required"
                results.append({"verified": False, "line": line, "message": reason})
                continue
            verified_any = False
            failed_error: Optional[str] = None
            for addr in addresses:
                try:
                    self.client.set_breakpoint(addr, pid=self.current_pid)
                    verified_any = True
                except Exception as exc:
                    failed_error = str(exc)
                    self.logger.debug("breakpoint set failed for 0x%X: %s", addr, exc)
            entry = {
                "verified": verified_any,
                "instructionReference": f"{addresses[0]:#x}",
                "address": addresses[0],
                "id": addresses[0],
                "line": line,
                "source": source if source else None,
            }
            if failed_error and not verified_any:
                entry["message"] = failed_error
            new_entries.append({"addresses": addresses})
            results.append(entry)
        return results, new_entries

    def _reapply_pending_breakpoints(self) -> None:
        if not self.client or not self._pending_breakpoints:
            return
        pending = dict(self._pending_breakpoints)
        self._pending_breakpoints.clear()
        for source_key, entry in pending.items():
            source = entry.get("source") or {}
            bps = entry.get("breakpoints") or []
            source_path = source.get("path") or source.get("name")
            results, new_entries = self._apply_breakpoints_for_source(source_key, source_path, source, bps)
            self._breakpoints[source_key] = new_entries
            for bp in results:
                if bp.get("verified"):
                    self.protocol.send_event("breakpoint", {"reason": "changed", "breakpoint": bp})

    def _ensure_watch_entry(self, expression: str):
        expr = expression.strip()
        if not expr or not self.client:
            return None
        self._ensure_symbol_mapper()
        kind = self._classify_watch_expression(expr)
        if kind == "symbol":
            symbol_meta = self._lookup_symbol_metadata(expr)
            if symbol_meta is None:
                raise RuntimeError(f"symbol '{expr}' not found (ensure .sym is loaded)")
            if self._symbol_requires_stack(symbol_meta):
                raise RuntimeError(f"symbol '{expr}' refers to a local/stack variable (not yet supported)")
        watch_id = self._watch_expr_to_id.get(expr)
        if watch_id is None:
            record = self.client.add_watch(expr, pid=self.current_pid)
            watch_id = int(record.get("watch_id") or record.get("id") or 0)
            if watch_id:
                self._watch_expr_to_id[expr] = watch_id
                self._watch_id_to_expr[watch_id] = expr
                self._invalidate_variables_scope()
        if not watch_id:
            return None
        watches = self.client.list_watches(self.current_pid, refresh=True)
        for watch in watches:
            if getattr(watch, "watch_id", None) == watch_id:
                return watch
        raise RuntimeError("watch registered but not returned by executive")

    def _describe_watch_value(self, watch) -> str:
        value = getattr(watch, "value", None) or ""
        address = getattr(watch, "address", None)
        location = getattr(watch, "location", None)
        parts = [str(value)]
        meta: List[str] = []
        if address is not None:
            meta.append(f"@ 0x{int(address):08X}")
        if location:
            meta.append(str(location))
        if meta:
            parts.append(f"({' '.join(meta)})")
        return " ".join(part for part in parts if part)

    def _invalidate_variables_scope(self) -> None:
        try:
            self.protocol.send_event("invalidated", {"areas": ["variables"]})
        except Exception:
            pass

    def _cleanup_watches(self) -> None:
        if not self._watch_expr_to_id:
            return
        if self.client:
            for watch_id in set(self._watch_expr_to_id.values()):
                try:
                    self.client.remove_watch(watch_id, pid=self.current_pid)
                except Exception:
                    self.logger.debug("failed to remove watch %s", watch_id)
        self._watch_expr_to_id.clear()
        self._watch_id_to_expr.clear()

    def _shutdown(self) -> None:
        self._cleanup_watches()
        self._symbol_mapper = None
        self._symbol_path = None
        self._symbol_mtime = None
        if self._event_token and self.event_bus:
            self.event_bus.unsubscribe(self._event_token)
            self._event_token = None
        if self.event_bus:
            self.event_bus.stop()
            self.event_bus = None
        if self.session:
            try:
                self.session.close()
            except Exception:
                pass
            self.session = None
        self.client = None

    def _render_source(self, path: Optional[str]) -> Optional[JsonDict]:
        if not path:
            return None
        return {"name": Path(path).name, "path": path}

    def _resolve_frame(self, raw_frame_id) -> Optional[_FrameRecord]:
        if isinstance(raw_frame_id, _FrameRecord):
            return raw_frame_id
        frame_id: Optional[int] = None
        try:
            if raw_frame_id is not None:
                frame_id = int(raw_frame_id)
        except (TypeError, ValueError):
            frame_id = None
        if frame_id is not None and frame_id in self._frames:
            return self._frames[frame_id]
        if self._frames:
            # fall back to the most recent frame
            first_key = next(iter(self._frames))
            return self._frames[first_key]
        return None

    def _evaluate_register_expression(self, expression: str) -> Optional[str]:
        token = expression.strip().upper()
        normalized = REGISTER_NAMES.get(token)
        if not normalized or not self.client:
            return None
        state = self.client.get_register_state(self.current_pid)
        if not state:
            return None
        if normalized == "PC":
            value = state.pc
        elif normalized == "SP":
            value = state.sp
        elif normalized == "PSW":
            value = state.psw
        else:
            value = state.registers.get(normalized)
        if value is None:
            return None
        return f"0x{int(value) & 0xFFFFFFFF:08X}"

    def _evaluate_pointer_expression(self, expression: str, frame: Optional[_FrameRecord]) -> Optional[JsonDict]:
        token = expression.strip()
        if not token or token[0] not in {"@", "*", "&"}:
            return None
        deref = token[0] in {"@", "*"}
        body = token[1:].strip()
        length = 4
        if ":" in body:
            addr_expr, _, length_expr = body.partition(":")
            body = addr_expr.strip()
            try:
                parsed_length = int(length_expr, 0)
                if parsed_length > 0:
                    length = max(1, min(parsed_length, 16))
            except ValueError:
                pass
        address = self._resolve_address_token(body, frame, include_globals=True)
        if address is None:
            return {
                "result": f"unresolved address '{expression}'",
                "variablesReference": 0,
            }
        address = int(address) & 0xFFFFFFFF
        if not deref:
            return {
                "result": f"0x{address:08X}",
                "type": "address",
                "variablesReference": 0,
            }
        formatted = self._format_memory_value(address, length=length)
        if formatted is None:
            return {
                "result": f"unreadable memory @0x{address:08X}",
                "variablesReference": 0,
            }
        if length != 4:
            formatted = f"{formatted} (len={length})"
        return {"result": formatted, "type": "memory", "variablesReference": 0}

    def _evaluate_symbol_expression(
        self,
        expression: str,
        frame: Optional[_FrameRecord],
        *,
        include_globals: bool,
    ) -> Optional[JsonDict]:
        symbol = self._find_symbol(expression, frame, include_globals=include_globals)
        if not symbol:
            return None
        formatted = self._format_symbol_value(symbol, frame)
        if formatted is None:
            formatted = self._describe_local_symbol(symbol)
        return {"result": formatted, "type": "symbol", "variablesReference": 0}

    def _classify_watch_expression(self, expression: str) -> str:
        token = expression.strip()
        if not token:
            return "unknown"
        upper = token.upper()
        if upper in REGISTER_NAMES:
            return "register"
        try:
            int(token, 0)
            return "address"
        except ValueError:
            pass
        if token.startswith("&") or token.startswith("*") or token.startswith("@"):
            return "address"
        if all(ch.isalnum() or ch == "_" for ch in token):
            return "symbol"
        return "expression"

    def _lookup_symbol_metadata(self, name: str) -> Optional[Dict[str, Any]]:
        if not self.client or self.current_pid is None:
            return None
        if hasattr(self.client, "symbol_lookup_name"):
            try:
                return self.client.symbol_lookup_name(name, pid=self.current_pid)
            except Exception:
                return None
        return None

    def _lookup_local_symbol(self, name: str, frame: Optional[_FrameRecord]) -> Optional[Dict[str, Any]]:
        if not name or not self._symbol_mapper or not frame or not getattr(frame, "name", None):
            return None
        function = getattr(frame, "name", None)
        if not function:
            return None
        for entry in self._symbol_mapper.locals_for_function(function):
            if entry.get("name") == name:
                return entry
        return None

    def _lookup_global_symbol(self, name: str) -> Optional[Dict[str, Any]]:
        if not name or not self._symbol_mapper:
            return None
        for entry in self._symbol_mapper.globals_list():
            if entry.get("name") == name:
                return entry
        return None

    def _find_symbol(
        self,
        name: str,
        frame: Optional[_FrameRecord],
        *,
        include_globals: bool,
    ) -> Optional[Dict[str, Any]]:
        if not name:
            return None
        local_entry = self._lookup_local_symbol(name, frame)
        if local_entry:
            return local_entry
        if include_globals:
            global_entry = self._lookup_global_symbol(name)
            if global_entry:
                return global_entry
            return self._lookup_symbol_metadata(name)
        return None

    def _resolve_address_token(
        self,
        token: str,
        frame: Optional[_FrameRecord],
        *,
        include_globals: bool,
    ) -> Optional[int]:
        token = token.strip()
        if not token:
            return None
        try:
            return int(token, 0) & 0xFFFFFFFF
        except ValueError:
            pass
        symbol = self._find_symbol(token, frame, include_globals=include_globals)
        if not symbol:
            return None
        return self._resolve_symbol_address(symbol, frame)

    def _format_memory_value(self, addr: int, *, length: int = 4) -> Optional[str]:
        if not self.client:
            return None
        data = self.client.read_memory(addr, length, pid=self.current_pid)
        if not data:
            return None
        if len(data) < length:
            data = data.ljust(length, b"\x00")
        value = int.from_bytes(data[:length], byteorder="big")
        return f"0x{value:08X} ({value}) @ 0x{addr:08X}"

    @staticmethod
    def _symbol_requires_stack(symbol: Dict[str, Any]) -> bool:
        locations = symbol.get("locations")
        if isinstance(locations, list):
            for location in locations:
                loc = location.get("location") if isinstance(location, dict) else None
                if isinstance(loc, dict) and loc.get("kind") == "stack":
                    return True
        return False

    def _map_pc_to_source(self, pc: int) -> Optional[Dict[str, Any]]:
        if not self._symbol_mapper:
            return None
        info = self._symbol_mapper.lookup_pc(pc)
        if not info:
            return None
        directory = info.get("directory")
        file_value = info.get("file")
        if not file_value:
            return None
        try:
            path = Path(file_value)
            if directory:
                path = Path(directory) / path
        except Exception:
            path = Path(file_value)
        return {"path": str(path), "line": info.get("line"), "column": info.get("column")}

    def _describe_local_symbol(self, symbol: Dict[str, Any]) -> str:
        locations = symbol.get("locations")
        if not isinstance(locations, list) or not locations:
            return "location unknown"
        loc = locations[0].get("location") if isinstance(locations[0], dict) else None
        if not isinstance(loc, dict):
            return "location unknown"
        kind = loc.get("kind")
        if kind == "stack":
            offset = loc.get("offset")
            return f"stack offset {offset}"
        if kind == "register":
            return f"register {loc.get('name')}"
        if kind == "address":
            addr = loc.get("address")
            return f"@0x{int(addr):04X}" if isinstance(addr, (int, float)) else str(addr)
        return str(loc)

    def _format_symbol_value(self, symbol: Dict[str, Any], frame: Optional[_FrameRecord], *, address: Optional[int] = None) -> Optional[str]:
        addr = address
        size = symbol.get("size") or symbol.get("length") or 4
        if addr is None:
            resolved = self._resolve_symbol_address(symbol, frame)
            addr = resolved
        if addr is None or not self.client:
            return None
        data = self.client.read_memory(int(addr), int(size), pid=self.current_pid)
        if not data:
            return None
        value = int.from_bytes(data[: min(len(data), 4)], byteorder="big")
        return f"0x{value:08X} ({value})"

    def _resolve_symbol_address(self, symbol: Dict[str, Any], frame: Optional[_FrameRecord]) -> Optional[int]:
        locations = symbol.get("locations")
        if isinstance(locations, list):
            for location in locations:
                loc = location.get("location") if isinstance(location, dict) else None
                if not isinstance(loc, dict):
                    continue
                kind = loc.get("kind")
                if kind == "stack" and frame:
                    offset = loc.get("offset")
                    base = frame.sp if loc.get("relative") != "fp" else frame.fp
                    if base is not None and offset is not None:
                        try:
                            return int(base) + int(offset)
                        except (TypeError, ValueError):
                            continue
                if kind == "address":
                    addr = loc.get("address")
                    if isinstance(addr, str) and addr.startswith("0x"):
                        try:
                            addr = int(addr, 16)
                        except ValueError:
                            addr = None
                    if isinstance(addr, (int, float)):
                        return int(addr)
        addr_field = symbol.get("address")
        if isinstance(addr_field, str) and addr_field.startswith("0x"):
            try:
                return int(addr_field, 16)
            except ValueError:
                return None
        if isinstance(addr_field, (int, float)):
            return int(addr_field)
        return None


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="HSX Debug Adapter", add_help=False)
    parser.add_argument("--pid", type=int, required=True)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=9998)
    parser.add_argument("--log-file")
    parser.add_argument("--log-level", default="INFO")
    args, _ = parser.parse_known_args(argv)
    print(f"[hsx-dap] CLI args: pid={args.pid} host={args.host} port={args.port} log={args.log_file}", flush=True)
    if args.log_file:
        log_path = Path(args.log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        filename=args.log_file,
        level=getattr(logging, str(args.log_level).upper(), logging.INFO),
        format="[%(asctime)s] %(levelname)s: %(message)s",
        force=True,
    )
    protocol = DAPProtocol(sys.stdin.buffer, sys.stdout.buffer)
    adapter = HSXDebugAdapter(protocol)
    adapter.current_pid = args.pid
    logger = logging.getLogger("hsx-dap")
    logger.info("HSX DAP adapter starting (pid=%s)", os.getpid())
    try:
        adapter.serve()
        logger.info("HSX DAP adapter exiting normally")
        return 0
    except Exception:
        logger.exception("HSX DAP adapter crashed")
        raise
