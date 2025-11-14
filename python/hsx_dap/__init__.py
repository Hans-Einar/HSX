"""
HSX Debug Adapter implementation for VS Code (Debug Adapter Protocol).
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import importlib
import sys
import threading
import time
from dataclasses import dataclass, field
import copy
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
    print(f"[hsx-dap] Added repo root to sys.path: {REPO_ROOT}", flush=True)

from hsx_dbg import DebuggerBackend, DebuggerBackendError, DebuggerSession, RegisterState, StackFrame, WatchValue
from hsx_dbg.symbols import SymbolIndex


JsonDict = Dict[str, Any]
REGISTER_NAMES: Dict[str, str] = {}
for idx in range(16):
    REGISTER_NAMES[f"R{idx}"] = f"R{idx}"
    REGISTER_NAMES[f"R{idx:02d}"] = f"R{idx}"
REGISTER_NAMES.update(
    {
        "PC": "PC",
        "SP": "SP",
        "PSW": "PSW",
        "REG_BASE": "REG_BASE",
        "STACK_BASE": "STACK_BASE",
        "STACK_LIMIT": "STACK_LIMIT",
        "STACK_SIZE": "STACK_SIZE",
        "SP_EFFECTIVE": "SP_EFFECTIVE",
        "BP": "STACK_BASE",
        "WP": "REG_BASE",
    }
)
BACKEND_FACTORY_ENV = "HSX_DAP_BACKEND_FACTORY"


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


def _to_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        try:
            return int(value, 0)
        except ValueError:
            return None
    return None


def _detect_extension_version() -> str:
    package_json = REPO_ROOT / "vscode-hsx" / "package.json"
    try:
        data = json.loads(package_json.read_text(encoding="utf-8"))
    except Exception:
        return "unknown"
    version = data.get("version")
    return str(version) if isinstance(version, (str, int, float)) else "unknown"


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


class AdapterCommandError(RuntimeError):
    """Raised when a DAP request fails for expected/user-level reasons."""


class HSXDebugAdapter:
    """DAP request dispatcher bridging VS Code to hsxdbg."""

    _SESSION_FEATURES = ["events", "stack", "symbols", "memory", "watch", "disasm"]
    _EVENT_CATEGORIES = [
        "debug_break",
        "task_state",
        "watch_update",
        "stdout",
        "stderr",
        "warning",
        "mailbox_wait",
        "mailbox_wake",
        "mailbox_timeout",
        "trace_step",
        "sleep_request",
        "sleep_complete",
    ]
    _RECONNECT_FATAL_TOKENS = {
        "requires 'pid'",
        'requires "pid"',
        "watch requires",
        "disasm requires",
        "missing pid",
        "unknown_cmd",
        "unsupported",
        "invalid argument",
        "invalid request",
        "bad request",
    }
    _RECONNECT_TRANSIENT_TOKENS = {
        "transport",
        "connection",
        "session_required",
        "keepalive",
        "timeout",
        "timed out",
        "broken pipe",
        "reset by peer",
    }

    def __init__(self, protocol: DAPProtocol) -> None:
        self.protocol = protocol
        self.logger = logging.getLogger("hsx-dap")
        self.backend: Optional[DebuggerBackend] = None
        self.client: Optional[DebuggerBackend] = None
        self.current_pid: Optional[int] = None
        self._initialized = False
        self._event_stream_active = False
        self._frames: Dict[int, _FrameRecord] = {}
        self._next_frame_id = 1
        self._scopes: Dict[int, _ScopeRecord] = {}
        self._next_scope_id = 1
        self._breakpoints: Dict[str, List[JsonDict]] = {}
        self._symbol_mapper: Optional[SymbolIndex] = None
        self._symbol_path: Optional[Path] = None
        self._symbol_mtime: Optional[float] = None
        self._watch_expr_to_id: Dict[str, int] = {}
        self._watch_id_to_expr: Dict[int, str] = {}
        self._pending_breakpoints: Dict[str, Dict[str, Any]] = {}
        self._breakpoint_specs: Dict[str, Dict[str, Any]] = {}
        self._sym_hint: Optional[Path] = None
        self._thread_states: Dict[int, Dict[str, Any]] = {}
        self._pending_pause: bool = False
        self._pause_fallback_timer: Optional[threading.Timer] = None
        self._synthetic_pause_pending: bool = False
        self._source_ref_to_path: Dict[int, str] = {}
        self._source_path_to_ref: Dict[str, int] = {}
        self._next_source_id: int = 1
        self.project_root = REPO_ROOT
        self._source_base_dirs: List[Path] = [REPO_ROOT]
        self._connection_config: Dict[str, Any] = {}
        self._reconnecting = False
        self._has_session = False
        self._connection_state = "idle"
        self._observer_mode: bool = False
        self._keepalive_override: Optional[int] = None
        self._remote_breakpoint_timer: Optional[threading.Timer] = None
        self._remote_breakpoint_interval: float = 5.0
        self._last_stop_event: Dict[int, Tuple[str, Optional[int], float]] = {}
        self._remote_bp_backoff_until: float = 0.0
        self._remote_bp_backoff_attempts: int = 0
        self._state_sync_backoff_until: float = 0.0
        self._state_sync_backoff_attempts: int = 0
        self._pending_step: bool = False
        self._step_description: Optional[str] = None
        self._step_fallback_timer: Optional[threading.Timer] = None
        self._task_snapshot_cache: Dict[int, Tuple[float, Dict[str, Any]]] = {}
        self._debug_state_pids: Set[int] = set()
        self._debugger_session: Optional[DebuggerSession] = None
        self._backend_factory: Optional[Callable[..., DebuggerBackend]] = None

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
        except AdapterCommandError as exc:
            self.logger.info("DAP command failed: %s (%s)", command, exc)
            self.protocol.send_response(seq, command or "", success=False, message=str(exc))
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
            "supportsReadMemoryRequest": True,
            "supportsWriteMemoryRequest": True,
            "supportsDisassembleRequest": True,
            "supportsTerminateRequest": True,
            "supportsInstructionBreakpoints": True,
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
        self._debug_state_pids.clear()
        observer_mode = self._coerce_bool(args.get("observerMode") or args.get("observer_mode"))
        keepalive_interval = self._coerce_optional_int(args.get("keepaliveInterval") or args.get("keepalive_interval"))
        heartbeat_override = self._coerce_optional_int(
            args.get("sessionHeartbeat") or args.get("heartbeatSeconds") or args.get("heartbeatInterval")
        )
        if heartbeat_override is None:
            heartbeat_override = keepalive_interval
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
        self._update_project_root(args)
        self._observer_mode = observer_mode
        self._keepalive_override = keepalive_interval
        self._emit_status_event(
            "connecting",
            details={
                "host": host,
                "port": port,
                "pid": self.current_pid,
                "observer": observer_mode,
            },
        )
        self._connect(
            host,
            port,
            self.current_pid,
            observer_mode=observer_mode,
            keepalive_interval=keepalive_interval,
            heartbeat_override=heartbeat_override,
        )
        self._reapply_pending_breakpoints()
        return {}

    def _handle_attach(self, args: JsonDict) -> JsonDict:
        return self._handle_launch(args)

    def _handle_configurationDone(self, args: JsonDict) -> JsonDict:  # noqa: N802
        return {}

    def _handle_disconnect(self, args: JsonDict) -> JsonDict:
        self._disable_debug_state(reason="disconnect")
        self.protocol.send_event("terminated", {})
        self._shutdown()
        return {}

    def _handle_terminate(self, args: JsonDict) -> JsonDict:
        restart = bool(args.get("restart"))
        self._disable_debug_state(reason="terminate")
        if self.current_pid is not None and self.client:
            try:
                self._call_backend("pause", self.current_pid)
            except Exception:
                self.logger.debug("terminate pause failed", exc_info=True)
        self.protocol.send_event("terminated", {"restart": restart})
        self._shutdown()
        return {}

    def _handle_threads(self, args: JsonDict) -> JsonDict:
        threads: List[JsonDict] = []
        for pid in sorted(self._thread_states.keys()):
            meta = self._thread_states.get(pid, {})
            threads.append({"id": pid, "name": meta.get("name") or f"PID {pid}"})
        if not threads and self.current_pid:
            pid = self.current_pid
            threads.append({"id": pid, "name": f"PID {pid}"})
        return {"threads": threads}

    def _handle_continue(self, args: JsonDict) -> JsonDict:
        self._ensure_client()
        self.logger.info("Continue: resuming PID %s", self.current_pid)
        self._disable_debug_state(reason="continue")
        self._cancel_pause_fallback()
        self._pending_pause = False  # Clear any pending pause state
        self._synthetic_pause_pending = False
        self._cancel_step_fallback()
        self._pending_step = False
        self._step_description = None
        self._call_backend("resume", self.current_pid)
        try:
            self._call_backend("clock_start")
        except Exception:
            self.logger.debug("clock_start failed (continuing anyway)", exc_info=True)
        self.protocol.send_event("continued", {"threadId": self.current_pid})
        self._set_thread_state(self.current_pid, "running")
        self._synchronize_execution_state(source="continue", refresh_breakpoints=True)
        return {"allThreadsContinued": True}

    def _handle_pause(self, args: JsonDict) -> JsonDict:
        self._ensure_client()
        self.logger.info("Pause requested for PID %s", self.current_pid)
        self._pending_pause = True
        self._schedule_pause_fallback()
        self._cancel_step_fallback()
        self._pending_step = False
        self._step_description = None
        self._call_backend("pause", self.current_pid)
        return {}

    def _schedule_pause_fallback(self) -> None:
        if not self.current_pid:
            return
        self._cancel_pause_fallback()
        timer = threading.Timer(0.3, self._pause_fallback_check)
        timer.daemon = True
        self._pause_fallback_timer = timer
        timer.start()

    def _cancel_pause_fallback(self) -> None:
        timer = self._pause_fallback_timer
        if timer is not None:
            timer.cancel()
            self._pause_fallback_timer = None

    def _pause_fallback_check(self) -> None:
        # Timer callback that emits a synthetic stopped event if the executive never sent one.
        self._pause_fallback_timer = None
        if not self._pending_pause or not self.client or not self.current_pid:
            return
        self.logger.debug("Pause response missing task_state event; emitting fallback stopped event")
        self._emit_pause_snapshot(description="pause (fallback)")

    def _emit_pause_snapshot(self, description: str) -> None:
        pc = self._read_current_pc()
        self._pending_pause = False
        self._synthetic_pause_pending = True
        self._cancel_pause_fallback()
        self.logger.info("Pause completed for PID %s (%s)", self.current_pid, description)
        self._emit_stopped_event(
            pid=self.current_pid,
            reason="user_pause",
            description=description,
            pc=pc,
        )
        self._set_thread_state(self.current_pid, "paused")
        self._synchronize_execution_state(source="pause", refresh_breakpoints=True)

    def _handle_next(self, args: JsonDict) -> JsonDict:
        self._ensure_client()
        if self.current_pid is None:
            raise RuntimeError("No HSX PID attached.")
        self._ensure_debug_state_enabled()
        self._call_backend("step", self.current_pid, source_only=True)
        self._after_step_request("step over")
        return {}

    def _handle_stepIn(self, args: JsonDict) -> JsonDict:  # noqa: N802
        self._ensure_client()
        if self.current_pid is None:
            raise RuntimeError("No HSX PID attached.")
        self._ensure_debug_state_enabled()
        self._call_backend("step", self.current_pid, source_only=True)
        self._after_step_request("step in")
        return {}

    def _handle_stepOut(self, args: JsonDict) -> JsonDict:  # noqa: N802
        self._ensure_client()
        if self.current_pid is None:
            raise RuntimeError("No HSX PID attached.")
        self._ensure_debug_state_enabled()
        self._call_backend("step", self.current_pid, source_only=True)
        self._after_step_request("step out")
        return {}

    def _handle_stepInstruction(self, args: JsonDict) -> JsonDict:
        self._ensure_client()
        if self.current_pid is None:
            raise RuntimeError("No HSX PID attached.")
        origin = str(args.get("origin") or "").strip()
        if origin:
            self.logger.info("Instruction step requested via %s", origin)
        pc_before = self._read_current_pc()
        debug_state_active = self._ensure_debug_state_enabled()
        disabled_breakpoints: List[int] = []
        if not debug_state_active and pc_before is not None:
            disabled_breakpoints = self._temporarily_disable_breakpoint(pc_before)
        try:
            self._call_backend("step", self.current_pid, source_only=False)
        finally:
            if disabled_breakpoints:
                self._restore_temporarily_disabled_breakpoints(disabled_breakpoints)
        self._after_step_request("instruction step", fallback_delay=0.05)
        return {}

    def _handle_clearAllBreakpoints(self, args: JsonDict) -> JsonDict:
        self._ensure_client()
        if self.current_pid is None:
            raise RuntimeError("clearAllBreakpoints requires an attached PID")
        addresses = self._collect_breakpoint_addresses(include_remote=True)
        self._clear_all_breakpoints(force_backend=True)
        self._sync_remote_breakpoints()
        return {"cleared": len(addresses)}

    def _handle_stackTrace(self, args: JsonDict) -> JsonDict:  # noqa: N802
        self._ensure_client()
        start = int(args.get("startFrame") or 0)
        levels = int(args.get("levels") or 20)
        frames = self._call_backend("get_call_stack", self.current_pid, max_frames=start + levels)
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

    def _handle_source(self, args: JsonDict) -> JsonDict:
        source_obj = args.get("source") or {}
        ref = source_obj.get("sourceReference") or args.get("sourceReference")
        path = source_obj.get("path") or args.get("path")
        resolved_path: Optional[Path] = None
        if ref is not None:
            try:
                ref_id = int(ref)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"Invalid sourceReference: {ref}") from exc
            stored = self._source_ref_to_path.get(ref_id)
            if stored:
                resolved_path = Path(stored)
        if resolved_path is None and path:
            candidate = Path(path)
            if not candidate.is_absolute():
                candidate = (Path.cwd() / candidate).resolve()
            resolved_path = candidate
        if resolved_path is None:
            raise RuntimeError("Source request missing valid path/sourceReference")
        try:
            content = resolved_path.read_text(encoding="utf-8")
        except FileNotFoundError as exc:
            raise RuntimeError(f"Source file not found: {resolved_path}") from exc
        except OSError as exc:
            raise RuntimeError(f"Failed to read source file {resolved_path}: {exc}") from exc
        return {
            "content": content,
            "mimeType": "text/x-c",
        }

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
        if isinstance(source_path, str) and source_path.startswith("hsx-disassembly:"):
            self.logger.info("setBreakpoints: ignoring HSX disassembly pseudo-source %s", source_path)
            results: List[JsonDict] = []
            for bp in breakpoints:
                results.append(
                    {
                        "verified": True,
                        "line": bp.get("line"),
                        "message": "Managed by HSX disassembly view.",
                    }
                )
            return {"breakpoints": results}
        self.logger.info("setBreakpoints: source=%s, count=%d", source_path, len(breakpoints))
        self._ensure_symbol_mapper()
        if not self.client:
            self.logger.warning("setBreakpoints: no client connected, storing as pending")
            self._pending_breakpoints[source_key] = {"source": source, "breakpoints": breakpoints, "kind": "source"}
            if breakpoints:
                self._record_breakpoint_spec(source_key, source, breakpoints, kind="source")
            else:
                self._breakpoint_specs.pop(source_key, None)
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
        if breakpoints:
            self._record_breakpoint_spec(source_key, source, breakpoints, kind="source")
        else:
            self._breakpoint_specs.pop(source_key, None)
        self.logger.info("setBreakpoints: set %d breakpoints for %s", len(results), source_path)
        return {"breakpoints": results}

    def _handle_threadsRequest(self, args: JsonDict) -> JsonDict:  # pragma: no cover - compatibility alias
        return self._handle_threads(args)

    def _handle_setFunctionBreakpoints(self, args: JsonDict) -> JsonDict:  # noqa: N802
        breakpoints = args.get("breakpoints") or []
        self._ensure_symbol_mapper()
        requested_keys: List[str] = []
        results: List[JsonDict] = []
        if not self.client:
            self.logger.warning("setFunctionBreakpoints: no client connected, storing as pending")
            for bp in breakpoints:
                name = bp.get("name")
                if not name:
                    results.append({"verified": False, "message": "name required"})
                    continue
                source_key = self._function_source_key(name)
                requested_keys.append(source_key)
                payload = {"source": {"name": name}, "breakpoints": [bp], "kind": "function"}
                self._pending_breakpoints[source_key] = payload
                self._record_breakpoint_spec(source_key, payload["source"], payload["breakpoints"], kind="function")
                results.append({"verified": False, "name": name, "message": "pending connection"})
            self._cleanup_obsolete_function_breakpoints(set(requested_keys))
            return {"breakpoints": results}

        for bp in breakpoints:
            name = bp.get("name")
            if not name:
                results.append({"verified": False, "message": "name required"})
                continue
            source_key = self._function_source_key(name)
            requested_keys.append(source_key)
            result, entries = self._apply_function_breakpoint(source_key, name, bp)
            if entries:
                self._breakpoints[source_key] = entries
                self._record_breakpoint_spec(source_key, {"name": name}, [bp], kind="function")
            else:
                self._breakpoints.pop(source_key, None)
                self._breakpoint_specs.pop(source_key, None)
            results.append(result)
        self._cleanup_obsolete_function_breakpoints(set(requested_keys))
        return {"breakpoints": results}

    def _handle_setInstructionBreakpoints(self, args: JsonDict) -> JsonDict:  # noqa: N802
        breakpoints = args.get("breakpoints") or []
        self.logger.info("setInstructionBreakpoints: count=%d", len(breakpoints))
        source_key = self._instruction_breakpoint_key()
        parsed_addresses: List[int] = []
        results: List[JsonDict] = []
        for bp in breakpoints:
            address = self._parse_instruction_breakpoint(bp)
            if address is None:
                results.append({"verified": False, "message": "instructionReference required"})
                continue
            parsed_addresses.append(address)
        if not self.client:
            self.logger.warning("setInstructionBreakpoints: no client connected, storing as pending")
            payload = {
                "source": {},
                "breakpoints": [{"address": addr} for addr in parsed_addresses],
                "kind": "instruction",
            }
            self._pending_breakpoints[source_key] = payload
            if parsed_addresses:
                self._record_breakpoint_spec(
                    source_key,
                    payload["source"],
                    payload["breakpoints"],
                    kind="instruction",
                )
            else:
                self._breakpoint_specs.pop(source_key, None)
            for addr in parsed_addresses:
                results.append(
                    {
                        "verified": False,
                        "instructionReference": f"{addr:#x}",
                        "address": addr,
                        "message": "pending connection",
                    }
                )
            return {"breakpoints": results}

        results = self._apply_instruction_breakpoints(source_key, parsed_addresses)
        if parsed_addresses:
            self._record_breakpoint_spec(
                source_key,
                {},
                [{"address": addr} for addr in parsed_addresses],
                kind="instruction",
            )
        else:
            self._breakpoint_specs.pop(source_key, None)
        return {"breakpoints": results}

    def _handle_traceRecords(self, args: JsonDict) -> JsonDict:  # noqa: N802
        self._ensure_client()
        if self.current_pid is None:
            self._emit_console_message("Trace records require an attached HSX PID.")
            return {"records": []}
        limit = self._coerce_optional_int(args.get("limit"))
        export = self._coerce_bool(args.get("export"))
        info = self._call_backend("trace_records", self.current_pid, limit=limit, export=export)
        if not isinstance(info, dict):
            return {"records": []}
        return info

    def _handle_traceControl(self, args: JsonDict) -> JsonDict:  # noqa: N802
        self._ensure_client()
        if self.current_pid is None:
            raise RuntimeError("traceControl requires an attached PID")
        enabled_value = args.get("enabled")
        if enabled_value is None:
            mode = None
        elif isinstance(enabled_value, bool):
            mode = enabled_value
        else:
            mode = str(enabled_value).strip().lower() in {"1", "true", "on"}
        info = self._call_backend("trace_control", self.current_pid, enable=mode)
        return info or {}

    def _handle_readRegisters(self, args: JsonDict) -> JsonDict:  # noqa: N802
        if not self.client or self.current_pid is None:
            return {"registers": []}
        registers = self._format_registers()
        return {"registers": registers}

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

        include_globals = True
        symbol_value = self._evaluate_symbol_expression(
            expression,
            frame,
            include_globals=include_globals,
        )
        if symbol_value is not None:
            return symbol_value

        if context == "watch":
            try:
                watch = self._ensure_watch_entry(expression, frame)
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

    def _handle_readMemory(self, args: JsonDict) -> JsonDict:  # noqa: N802
        """Handle DAP readMemory request to read raw memory from the target."""
        self._ensure_client()
        memory_reference = args.get("memoryReference")
        offset = int(args.get("offset", 0))
        count = int(args.get("count", 0))
        
        if not memory_reference:
            raise ValueError("memoryReference is required")
        
        # Parse memory reference (should be hex address like "0x1234")
        try:
            if isinstance(memory_reference, str):
                base_addr = int(memory_reference, 0)
            else:
                base_addr = int(memory_reference)
        except (ValueError, TypeError) as exc:
            raise ValueError(f"Invalid memoryReference: {memory_reference}") from exc
        
        # Calculate actual address with offset
        address = (base_addr + offset) & 0xFFFFFFFF
        
        if count <= 0 or count > 0x10000:  # Limit to 64KB
            raise ValueError(f"Invalid count: {count} (must be 1-65536)")
        
        self.logger.info("readMemory: address=0x%08X, count=%d", address, count)
        
        # Read memory from executive
        data = self._call_backend("read_memory", address, count, pid=self.current_pid)
        
        if data is None:
            # Return unreadable memory indication
            return {
                "address": f"0x{address:08X}",
                "unreadableBytes": count,
            }
        
        # Encode data as base64 for DAP protocol
        import base64
        encoded_data = base64.b64encode(data).decode("ascii")
        
        return {
            "address": f"0x{address:08X}",
            "data": encoded_data,
            "unreadableBytes": max(0, count - len(data)),
        }

    def _handle_writeMemory(self, args: JsonDict) -> JsonDict:  # noqa: N802
        """Handle DAP writeMemory request to write raw memory to the target."""
        self._ensure_client()
        memory_reference = args.get("memoryReference")
        offset = int(args.get("offset", 0))
        data_b64 = args.get("data")
        
        if not memory_reference:
            raise ValueError("memoryReference is required")
        if not data_b64:
            raise ValueError("data is required")
        
        # Parse memory reference
        try:
            if isinstance(memory_reference, str):
                base_addr = int(memory_reference, 0)
            else:
                base_addr = int(memory_reference)
        except (ValueError, TypeError) as exc:
            raise ValueError(f"Invalid memoryReference: {memory_reference}") from exc
        
        # Calculate actual address with offset
        address = (base_addr + offset) & 0xFFFFFFFF
        
        # Decode base64 data
        import base64
        try:
            data = base64.b64decode(data_b64)
        except Exception as exc:
            raise ValueError(f"Invalid base64 data: {exc}") from exc
        
        if not data or len(data) > 0x10000:  # Limit to 64KB
            raise ValueError(f"Invalid data length: {len(data)} (must be 1-65536)")
        
        self.logger.info("writeMemory: address=0x%08X, count=%d", address, len(data))

        # Write memory to executive
        try:
            self._call_backend("write_memory", address, data, pid=self.current_pid)
        except Exception as exc:
            self.logger.warning("writeMemory failed: %s", exc)
            raise

        return {
            "bytesWritten": len(data),
        }

    def _handle_disassemble(self, args: JsonDict) -> JsonDict:
        self._ensure_client()
        if self.current_pid is None:
            raise AdapterCommandError("Cannot disassemble because no HSX PID is attached.")
        count = self._coerce_positive_int(args.get("instructionCount"), default=32, limit=128)
        offset = self._coerce_optional_int(args.get("instructionOffset")) or 0
        around_pc = self._coerce_bool(args.get("aroundPc"))
        address = self._coerce_address(
            args.get("memoryReference")
            or args.get("instructionPointerReference")
            or args.get("address")
            or args.get("instructionReference"),
        )
        if address is None:
            frame = self._resolve_frame(args.get("frameId"))
            address = frame.pc if frame and frame.pc is not None else self._read_current_pc()
        if address is None:
            raise RuntimeError("disassemble request requires address or active frame")
        start_addr = (int(address) + int(offset)) & 0xFFFFFFFF
        view_mode = "around_pc" if around_pc else "from_addr"
        payload = {
            "cmd": "disasm.read",
            "pid": self.current_pid,
            "addr": start_addr,
            "count": count,
            "view": view_mode,
        }
        response = self._call_backend("request", payload)
        if response.get("status") != "ok" and payload["cmd"] == "disasm.read":
            error_text = str(response.get("error", ""))
            if "unknown_cmd" in error_text or "unsupported" in error_text:
                payload = {
                    "cmd": "disasm",
                    "pid": self.current_pid,
                    "addr": start_addr,
                    "count": count,
                }
                response = self._call_backend("request", payload)
        if response.get("status") != "ok":
            raise RuntimeError(response.get("error", "disassemble failed"))
        block = response.get("disasm") or {}
        resolve_symbols = bool(args.get("resolveSymbols"))
        instructions = self._format_disassembly(block, resolve_symbols=resolve_symbols)
        view_mode = block.get("view") or ("around_pc" if around_pc else "from_addr")
        reference_addr = block.get("reference")
        ref_hex: Optional[str] = None
        if isinstance(reference_addr, (int, float)):
            ref_hex = f"0x{int(reference_addr) & 0xFFFFFFFF:08X}"
        self.logger.info(
            "disassemble: view=%s count=%d reference=%s",
            view_mode,
            len(instructions),
            ref_hex or "n/a",
        )
        body: JsonDict = {"instructions": instructions, "view": view_mode}
        if ref_hex:
            body["referenceAddress"] = ref_hex
        return body

    # Internal helpers -------------------------------------------------
    def _connect(
        self,
        host: str,
        port: int,
        pid: int,
        *,
        observer_mode: bool = False,
        keepalive_interval: Optional[int] = None,
        heartbeat_override: Optional[int] = None,
    ) -> None:
        self.logger.info(
            "Connecting to executive at %s:%d (PID %d, observer=%s)",
            host,
            port,
            pid,
            observer_mode,
        )
        self._thread_states.clear()
        self._pending_pause = False
        self._synthetic_pause_pending = False
        self._cancel_pause_fallback()
        self._stop_event_stream()
        session = self._get_debugger_session()
        try:
            backend = session.connect(
                host,
                port,
                pid,
                observer_mode=observer_mode,
                keepalive_interval=keepalive_interval,
                heartbeat_override=heartbeat_override,
            )
        except DebuggerBackendError as exc:
            self.logger.error("Failed to establish debugger session: %s", exc)
            self._emit_status_event("error", message=str(exc))
            raise
        self.backend = backend
        self.client = backend
        self._connection_config = session.connection_config or {
            "host": host,
            "port": port,
            "pid": pid,
            "observer_mode": observer_mode,
            "keepalive_interval": keepalive_interval,
            "heartbeat_override": heartbeat_override,
        }
        self.current_pid = pid
        try:
            started = backend.start_event_stream(
                filters={"pid": [pid], "categories": self._EVENT_CATEGORIES},
                callback=self._handle_exec_event,
                ack_interval=16,
            )
            self._event_stream_active = started
            if not started:
                self.logger.warning("Executive did not accept event stream subscription; stop/console events may be delayed")
        except DebuggerBackendError as exc:
            self.logger.warning("Unable to start event stream: %s", exc)
            self._event_stream_active = False
        self._emit_status_event(
            "connected",
            details={
                "host": host,
                "port": port,
                "pid": pid,
                "observer": observer_mode,
            },
        )
        self._sync_remote_breakpoints()
        self._schedule_remote_breakpoint_poll()
        self._watch_expr_to_id.clear()
        self._watch_id_to_expr.clear()
        self._ensure_symbol_mapper(force=True)
        self._synchronize_execution_state(source="connect", refresh_breakpoints=False)

    def _resolve_backend_factory(self) -> Callable[..., DebuggerBackend]:
        cached = self._backend_factory
        if cached:
            return cached
        factory_path = os.environ.get(BACKEND_FACTORY_ENV)
        if factory_path:
            module_name, _, attr = factory_path.partition(":")
            if not module_name or not attr:
                raise RuntimeError(f"Invalid {BACKEND_FACTORY_ENV} value: {factory_path}")
            module = importlib.import_module(module_name)
            factory = getattr(module, attr)

            def custom_factory(**kwargs: Any) -> DebuggerBackend:
                return factory(**kwargs)

            self._backend_factory = custom_factory
            return custom_factory

        def default_factory(**kwargs: Any) -> DebuggerBackend:
            return DebuggerBackend(**kwargs)

        self._backend_factory = default_factory
        return default_factory

    def _get_debugger_session(self) -> DebuggerSession:
        session = self._debugger_session
        if session is None:
            session = DebuggerSession(
                client_name="hsx-dap",
                features=self._SESSION_FEATURES,
                keepalive_interval=10,
                backend_factory=self._resolve_backend_factory(),
            )
            self._debugger_session = session
        return session

    def _handle_exec_event(self, event: JsonDict) -> None:
        event_type = str(event.get("type") or "")
        data = event.get("data") or {}
        pid = event.get("pid")
        if event_type == "trace_step":
            pc = _to_int(data.get("pc"))
            target_pid = pid or self.current_pid
            if target_pid is not None and pc is not None:
                meta = self._thread_states.setdefault(target_pid, {"name": f"PID {target_pid}", "state": None})
                meta["last_pc"] = pc
            if pc is not None:
                self._emit_disassembly_refresh_event(pc)
            return
        if event_type == "mailbox_wait":
            details = dict(data) if isinstance(data, dict) else {}
            self._handle_task_state_event(
                {"pid": pid, "data": {"new_state": "waiting_mbx", "reason": "mailbox_wait", "details": details}}
            )
            return
        if event_type == "mailbox_wake":
            details = dict(data) if isinstance(data, dict) else {}
            self._handle_task_state_event(
                {"pid": pid, "data": {"new_state": "running", "reason": "mailbox_wake", "details": details}}
            )
            return
        if event_type == "mailbox_timeout":
            details = dict(data) if isinstance(data, dict) else {}
            self._handle_task_state_event(
                {"pid": pid, "data": {"new_state": "running", "reason": "mailbox_timeout", "details": details}}
            )
            return
        if event_type == "sleep_request":
            details = dict(data) if isinstance(data, dict) else {}
            self._handle_task_state_event(
                {"pid": pid, "data": {"new_state": "sleeping", "reason": "sleep", "details": details}}
            )
            return
        if event_type == "sleep_complete":
            details = dict(data) if isinstance(data, dict) else {}
            self._handle_task_state_event(
                {"pid": pid, "data": {"new_state": "running", "reason": "sleep_wake", "details": details}}
            )
            return
        if event_type == "task_state":
            self._handle_task_state_event(event)
            return
        if event_type == "debug_break":
            reason = data.get("reason") or "breakpoint"
            pc = _to_int(data.get("pc"))
            self.logger.info("DebugBreakEvent: pid=%s, pc=%s, reason=%s", pid, f"0x{pc:04X}" if pc is not None else "?", reason)
            self._emit_stopped_event(
                pid=pid or self.current_pid,
                reason=reason,
                description=data.get("symbol") or reason,
                pc=pc,
            )
            self._complete_pending_step()
            self._sync_remote_breakpoints()
            return
        if event_type in {"stdout", "stderr"}:
            text = ""
            if isinstance(data, dict):
                text = str(data.get("text") or "")
            if text and not text.endswith("\n"):
                text += "\n"
            category = "stdout" if event_type == "stdout" else "stderr"
            self.protocol.send_event("output", {"category": category, "output": text})
            return
        if event_type == "warning":
            reason = data.get("reason") or "warning"
            text = f"warning: {reason}\n"
            self.protocol.send_event("output", {"category": "console", "output": text})
            return
        if event_type == "watch_update":
            watch_id = _to_int(data.get("watch_id"))
            expr = data.get("expr")
            if watch_id is not None and expr:
                self._watch_expr_to_id.setdefault(expr, watch_id)
                self._watch_id_to_expr.setdefault(watch_id, expr)
            resolved_expr = expr or self._watch_id_to_expr.get(watch_id or -1) or ""
            label = f"{resolved_expr} " if resolved_expr else ""
            text = f"watch {label}[{watch_id}] -> {data.get('new')}\n"
            self.protocol.send_event("output", {"category": "console", "output": text})
            self._invalidate_variables_scope()
            return

    def _ensure_client(self) -> None:
        if not self.client:
            raise RuntimeError("debug session not connected")

    def _call_backend(self, method: str, *args, **kwargs):
        self._ensure_client()
        backend = self.client
        func = getattr(backend, method)
        try:
            return func(*args, **kwargs)
        except DebuggerBackendError as exc:
            if self._is_unknown_pid_error(exc):
                self._handle_missing_pid(str(exc))
                raise
            if self._should_attempt_reconnect(exc) and self._attempt_reconnect(exc):
                backend = self.client
                func = getattr(backend, method)
                return func(*args, **kwargs)
            raise

    def _emit_status_event(self, state: str, *, message: Optional[str] = None, details: Optional[Dict[str, Any]] = None) -> None:
        self._connection_state = state
        body: JsonDict = {
            "subsystem": "hsx-connection",
            "state": state,
        }
        if message:
            body["message"] = message
        if details:
            body["details"] = details
        try:
            self.protocol.send_event("telemetry", body)
        except Exception:
            self.logger.debug("failed to emit connection status event", exc_info=True)

    def _emit_debug_state_event(self, pid: int, state: str) -> None:
        body = {"subsystem": "hsx-step-mode", "pid": pid, "state": state, "label": "debug-state"}
        try:
            self.protocol.send_event("telemetry", body)
        except Exception:
            self.logger.debug("failed to emit debug state telemetry", exc_info=True)

    def _emit_disassembly_refresh_event(self, pc: Optional[int]) -> None:
        body: JsonDict = {
            "subsystem": "hsx-disassembly",
            "action": "refresh",
        }
        if pc is not None:
            body["pc"] = f"0x{int(pc) & 0xFFFFFFFF:04X}"
        try:
            self.protocol.send_event("telemetry", body)
        except Exception:
            self.logger.debug("failed to emit disassembly refresh event", exc_info=True)

    def _emit_breakpoint_sync_telemetry(self, added: List[int], removed: List[int]) -> None:
        body: JsonDict = {
            "subsystem": "hsx-breakpoints",
            "action": "external-sync",
            "addedCount": len(added),
            "removedCount": len(removed),
        }
        if added:
            body["addedSamples"] = [f"0x{addr:04X}" for addr in added[:8]]
        if removed:
            body["removedSamples"] = [f"0x{addr:04X}" for addr in removed[:8]]
        try:
            self.protocol.send_event("telemetry", body)
        except Exception:
            self.logger.debug("failed to emit breakpoint telemetry", exc_info=True)

    def _schedule_step_fallback(self, delay: float = 0.35) -> None:
        if not self.current_pid:
            return
        self._cancel_step_fallback()
        timer = threading.Timer(delay, self._step_fallback_check)
        timer.daemon = True
        self._step_fallback_timer = timer
        timer.start()

    def _cancel_step_fallback(self) -> None:
        timer = self._step_fallback_timer
        if timer is not None:
            timer.cancel()
        self._step_fallback_timer = None

    def _step_fallback_check(self) -> None:
        self._step_fallback_timer = None
        if not self._pending_step or not self.client or not self.current_pid:
            return
        description = self._step_description or "step"
        self.logger.debug("Step completion event missing; emitting fallback stopped event")
        self._complete_pending_step()
        pc = self._read_current_pc()
        self._emit_stopped_event(
            pid=self.current_pid,
            reason="step",
            description=f"{description} (fallback)",
            pc=pc,
        )
        self._set_thread_state(self.current_pid, "paused")
        self._synchronize_execution_state(source="step-fallback", refresh_breakpoints=False)

    def _after_step_request(self, description: str, *, fallback_delay: float = 0.35) -> None:
        self._pending_step = True
        self._step_description = description
        self._schedule_step_fallback(delay=fallback_delay)

    def _complete_pending_step(self) -> None:
        if not self._pending_step:
            return
        self._pending_step = False
        self._step_description = None
        self._cancel_step_fallback()

    def _ensure_debug_state_enabled(self) -> bool:
        pid = self.current_pid
        if pid is None or not self.client:
            return False
        if pid in self._debug_state_pids:
            return True
        if not hasattr(self.client, "set_debug_state"):
            return False
        try:
            self._call_backend("set_debug_state", pid, True)
        except Exception:
            self.logger.debug("Failed to enable debug state for PID %s", pid, exc_info=True)
            return False
        self.logger.debug("Enabled debug state for PID %s", pid)
        self._emit_debug_state_event(pid, "enabled")
        self._debug_state_pids.add(pid)
        return True

    def _disable_debug_state(self, *, pid: Optional[int] = None, reason: str = "manual") -> None:
        target = pid or self.current_pid
        if target is None or target not in self._debug_state_pids:
            return
        if not self.client or not hasattr(self.client, "set_debug_state"):
            self._debug_state_pids.discard(target)
            return
        try:
            self._call_backend("set_debug_state", target, False)
        except Exception as exc:
            message = f"Failed to disable debug state for PID {target}: {exc}"
            self.logger.warning(message, exc_info=True)
            self._emit_console_message(message)
        else:
            self.logger.debug("Disabled debug state for PID %s (%s)", target, reason)
            self._emit_debug_state_event(target, "disabled")
        self._debug_state_pids.discard(target)

    def _remaining_backoff(self, kind: str) -> float:
        now = time.monotonic()
        if kind == "breakpoint":
            return max(0.0, self._remote_bp_backoff_until - now)
        if kind == "state":
            return max(0.0, self._state_sync_backoff_until - now)
        return 0.0

    def _reset_backoff(self, kind: str) -> None:
        if kind == "breakpoint":
            self._remote_bp_backoff_attempts = 0
            self._remote_bp_backoff_until = 0.0
        elif kind == "state":
            self._state_sync_backoff_attempts = 0
            self._state_sync_backoff_until = 0.0

    def _enter_backoff(self, kind: str, exc: Exception) -> None:
        prev_remaining = self._remaining_backoff(kind)
        attempts_attr: Optional[str] = None
        until_attr: Optional[str] = None
        label = kind
        if kind == "breakpoint":
            attempts_attr = "_remote_bp_backoff_attempts"
            until_attr = "_remote_bp_backoff_until"
            label = "breakpoint-sync"
        elif kind == "state":
            attempts_attr = "_state_sync_backoff_attempts"
            until_attr = "_state_sync_backoff_until"
            label = "state-sync"
        if not attempts_attr or not until_attr:
            return
        attempts = getattr(self, attempts_attr, 0) + 1
        attempts = min(attempts, 6)
        setattr(self, attempts_attr, attempts)
        delay = min(30.0, 1.0 * (2 ** (attempts - 1)))
        until_value = time.monotonic() + delay
        setattr(self, until_attr, until_value)
        if prev_remaining <= 0.0:
            message = f"{label} temporarily disabled after transport error: {exc}"
            self._emit_transport_warning(label, message, delay=delay)

    def _emit_transport_warning(self, subsystem: str, message: str, *, delay: float) -> None:
        body: JsonDict = {
            "subsystem": f"hsx-{subsystem}",
            "state": "degraded",
            "message": message,
            "details": {"retryDelay": round(delay, 2)},
        }
        try:
            self.protocol.send_event("telemetry", body)
        except Exception:
            self.logger.debug("failed to emit transport warning", exc_info=True)

    def _cache_task_snapshot(self, pid: int, snapshot: Dict[str, Any]) -> None:
        if pid is None:
            return
        self._task_snapshot_cache[int(pid)] = (time.monotonic(), dict(snapshot))

    def _get_cached_snapshot(self, pid: int, *, max_age: float = 1.0) -> Optional[Dict[str, Any]]:
        if pid is None:
            return None
        entry = self._task_snapshot_cache.get(int(pid))
        if not entry:
            return None
        ts, snapshot = entry
        if time.monotonic() - ts > max_age:
            return None
        return dict(snapshot)

    def _read_current_pc(self) -> Optional[int]:
        if not self.client or not self.current_pid:
            return None
        try:
            state = self._call_backend("get_register_state", self.current_pid)
        except Exception:
            self.logger.debug("Failed to refresh register state for pause fallback", exc_info=True)
            return None
        if state and state.pc is not None:
            return int(state.pc)
        return None

    def _format_registers(self) -> List[JsonDict]:
        if not self.client or self.current_pid is None:
            return []
        state = self._call_backend("get_register_state", self.current_pid)
        if not state:
            return []
        variables: List[JsonDict] = []
        for idx in range(16):
            raw_key = f"R{idx}"
            if raw_key not in state.registers:
                continue
            display_name = f"R{idx:02d}"
            variables.append(
                {
                    "name": display_name,
                    "value": f"0x{state.registers[raw_key]:08X}",
                    "type": "register",
                    "variablesReference": 0,
                }
            )
        if state.pc is not None:
            variables.append({"name": "PC", "value": f"0x{state.pc:08X}", "type": "register", "variablesReference": 0})
        if state.sp is not None:
            variables.append({"name": "SP", "value": f"0x{state.sp:08X}", "type": "register", "variablesReference": 0})
        if state.psw is not None:
            variables.append(
                {"name": "PSW", "value": f"0x{state.psw:08X}", "type": "register", "variablesReference": 0}
            )
        if state.reg_base is not None:
            variables.append(
                {
                    "name": "REG_BASE",
                    "value": f"0x{state.reg_base:08X}",
                    "type": "register",
                    "variablesReference": 0,
                }
            )
        if state.stack_base is not None:
            variables.append(
                {
                    "name": "STACK_BASE",
                    "value": f"0x{state.stack_base:08X}",
                    "type": "register",
                    "variablesReference": 0,
                }
            )
        if state.stack_limit is not None:
            variables.append(
                {
                    "name": "STACK_LIMIT",
                    "value": f"0x{state.stack_limit:08X}",
                    "type": "register",
                    "variablesReference": 0,
                }
            )
        if state.stack_size is not None:
            variables.append(
                {
                    "name": "STACK_SIZE",
                    "value": f"0x{state.stack_size:08X}",
                    "type": "register",
                    "variablesReference": 0,
                }
            )
        if state.sp_effective is not None:
            variables.append(
                {
                    "name": "SP_EFFECTIVE",
                    "value": f"0x{state.sp_effective:08X}",
                    "type": "register",
                    "variablesReference": 0,
                }
            )
        return variables

    def _format_watches(self) -> List[JsonDict]:
        if not self.client:
            return []
        watches = self._call_backend("list_watches", self.current_pid)
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
                    "variablesReference": 0,
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
                    "variablesReference": 0,
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

    def _function_source_key(self, name: str) -> str:
        return f"function::{name}"

    def _coerce_optional_int(self, value: Any) -> Optional[int]:
        if value is None:
            return None
        if isinstance(value, bool):
            return int(value)
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def _coerce_positive_int(self, value: Any, *, default: int, limit: Optional[int] = None) -> int:
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            parsed = default
        parsed = parsed if parsed > 0 else default
        if limit is not None:
            parsed = min(parsed, limit)
        return max(1, parsed)

    def _coerce_address(self, value: Any) -> Optional[int]:
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return int(value) & 0xFFFFFFFF
        if isinstance(value, str):
            token = value.strip()
            if not token:
                return None
            try:
                return int(token, 0) & 0xFFFFFFFF
            except ValueError:
                return None
        return None

    def _format_disassembly(self, block: JsonDict, *, resolve_symbols: bool) -> List[JsonDict]:
        instructions = []
        entries = block.get("instructions") or []
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            pc_value = entry.get("pc")
            if pc_value is None:
                continue
            try:
                pc_int = int(pc_value)
            except (TypeError, ValueError):
                continue
            pc_int &= 0xFFFFFFFF
            address = f"0x{pc_int:08X}"
            mnemonic = str(entry.get("mnemonic") or "").strip()
            operands_raw = entry.get("operands")
            if isinstance(operands_raw, str):
                operand_text = operands_raw.strip()
            else:
                operands = operands_raw if isinstance(operands_raw, list) else []
                operand_text = ", ".join(str(op) for op in operands if op is not None)
            instruction_text = mnemonic
            if operand_text:
                instruction_text = f"{mnemonic} {operand_text}".strip()
            line: JsonDict = {
                "address": address,
                "instructionBytes": str(entry.get("bytes") or ""),
                "instruction": instruction_text or address,
                "instructionPointerReference": address,
                "memoryReference": address,
            }
            if resolve_symbols:
                label = entry.get("label")
                if not label:
                    symbol_meta = entry.get("symbol")
                    if isinstance(symbol_meta, dict):
                        label = symbol_meta.get("name")
                if label:
                    line["symbol"] = str(label)
            location_meta = self._disassembly_source(entry)
            if location_meta:
                line.update(location_meta)
            instructions.append(line)
        return instructions

    def _disassembly_source(self, entry: Dict[str, Any]) -> Optional[JsonDict]:
        line_info = entry.get("line")
        if not isinstance(line_info, dict):
            return None
        path = line_info.get("file")
        directory = line_info.get("directory")
        if path and directory:
            try:
                resolved = Path(directory) / path
                path = str(resolved)
            except Exception:
                path = str(path)
        location: JsonDict = {}
        source = self._render_source(path) if path else None
        if source:
            location["location"] = source
        line_number = line_info.get("line")
        if isinstance(line_number, (int, float)):
            location["line"] = int(line_number)
        column = line_info.get("column")
        if isinstance(column, (int, float)):
            location["column"] = int(column)
        return location or None

    def _coerce_bool(self, value: Any) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)
        if isinstance(value, str):
            lowered = value.strip().lower()
            if lowered in {"1", "true", "yes", "on"}:
                return True
            if lowered in {"0", "false", "no", "off"}:
                return False
        return False

    def _parse_instruction_breakpoint(self, bp: JsonDict) -> Optional[int]:
        base = self._coerce_address(bp.get("instructionReference") or bp.get("address"))
        offset = self._coerce_optional_int(bp.get("offset")) or 0
        if base is None:
            return None
        return (int(base) + int(offset)) & 0xFFFFFFFF

    def _emit_console_message(self, text: str) -> None:
        output = text if text.endswith("\n") else f"{text}\n"
        try:
            self.protocol.send_event("output", {"category": "console", "output": output})
        except Exception:
            self.logger.debug("failed to emit console output: %s", text, exc_info=True)

    def _fetch_task_list(self) -> Optional[Dict[str, Any]]:
        if not self.client:
            return None
        try:
            listing = self._call_backend("list_tasks")
        except DebuggerBackendError as exc:
            self.logger.debug("list_tasks failed: %s", exc)
            return None
        return listing if isinstance(listing, dict) else None

    def _pid_exists(self, pid: Optional[int]) -> bool:
        if pid is None or not self.client:
            return False
        listing = self._fetch_task_list()
        if not listing:
            self.logger.debug("PID existence check failed (no task snapshot)")
            # Unable to confirm; assume it might still exist to avoid dropping the PID prematurely.
            return True
        tasks = listing.get("tasks")
        if isinstance(tasks, list):
            for entry in tasks:
                if isinstance(entry, dict) and int(entry.get("pid", -1)) == int(pid):
                    return True
        return False

    def _handle_missing_pid(self, message: str) -> None:
        pid = self.current_pid
        if pid is not None:
            warning = f"Target PID {pid} is no longer running ({message})"
        else:
            warning = f"Target PID unavailable ({message})"
        self.logger.error(warning)
        self._emit_status_event("error", message=warning)
        self._emit_console_message(warning)
        self.current_pid = None
        if pid is not None:
            self._debug_state_pids.discard(pid)
        self._cancel_remote_breakpoint_poll()

    @staticmethod
    def _is_unknown_pid_error(error: Exception) -> bool:
        text = str(error).lower()
        return "unknown pid" in text or "pid not found" in text

    def _clear_breakpoints(self, source_key: str, *, force_backend: bool = False) -> None:
        entries = self._breakpoints.get(source_key, [])
        if not entries:
            self._breakpoints[source_key] = []
            return
        for entry in entries:
            addresses = entry.get("addresses") or []
            if isinstance(addresses, int):
                addresses = [addresses]
            if entry.get("readonly") and not force_backend:
                continue
            if not self.client:
                continue
            for address in addresses:
                try:
                    self._call_backend("clear_breakpoint", self.current_pid, int(address))
                except Exception:
                    self.logger.debug("failed to clear breakpoint 0x%X", address)
        self._breakpoints[source_key] = []

    def _clear_all_breakpoints(self, *, force_backend: bool = False) -> None:
        if not self._breakpoints:
            return
        keys = list(self._breakpoints.keys())
        for source_key in keys:
            self._clear_breakpoints(source_key, force_backend=force_backend)
        self._breakpoints.clear()

    def _sync_remote_breakpoints(self) -> None:
        if not self.client or self.current_pid is None:
            return
        remaining = self._remaining_backoff("breakpoint")
        if remaining > 0:
            self.logger.debug("Skipping remote breakpoint sync (backoff %.2fs remaining)", remaining)
            return
        try:
            entries = self._call_backend("list_breakpoints", self.current_pid)
        except DebuggerBackendError as exc:
            self.logger.debug("list_breakpoints sync failed: %s", exc)
            self._enter_backoff("breakpoint", exc)
            return
        self._reset_backoff("breakpoint")
        if not isinstance(entries, list):
            return
        remote_addresses: Set[int] = set()
        for entry in entries:
            try:
                remote_addresses.add(int(entry) & 0xFFFFFFFF)
            except (TypeError, ValueError):
                self.logger.debug("Skipping invalid remote breakpoint %r", entry)
        local_addresses = self._collect_breakpoint_addresses(include_remote=False)
        filtered = {addr for addr in remote_addresses if addr not in local_addresses}
        remote_key = self._remote_breakpoint_key()
        existing = set(self._extract_addresses_for_key(remote_key))
        added = sorted(filtered - existing)
        removed = sorted(existing - filtered)
        if filtered:
            self._breakpoints[remote_key] = [{"addresses": sorted(filtered), "readonly": True}]
        elif remote_key in self._breakpoints:
            self._breakpoints.pop(remote_key, None)
        for addr in added:
            breakpoint_payload = {
                "id": addr,
                "verified": True,
                "instructionReference": f"{addr:#x}",
                "address": addr,
                "message": "Breakpoint set outside VS Code",
            }
            self.protocol.send_event("breakpoint", {"reason": "new", "breakpoint": breakpoint_payload})
            self.logger.info("Registered external breakpoint at 0x%04X", addr)
        for addr in removed:
            breakpoint_payload = {
                "id": addr,
                "verified": False,
                "instructionReference": f"{addr:#x}",
                "address": addr,
            }
            self.protocol.send_event("breakpoint", {"reason": "removed", "breakpoint": breakpoint_payload})
            self.logger.info("External breakpoint removed at 0x%04X", addr)
        if added or removed:
            self._emit_breakpoint_sync_telemetry(added, removed)

    def _resolve_breakpoint_addresses(self, source_path: Optional[str], line: Optional[int], bp: JsonDict) -> List[int]:
        addresses: List[int] = []
        explicit_addresses: List[int] = []
        lookup_path = source_path or bp.get("sourcePath") or bp.get("sourceName")
        if self._symbol_mapper and lookup_path and line:
            try:
                canonical = _canonical_path(lookup_path)
                candidates = self._symbol_mapper.lookup(canonical, int(line))
                if not candidates:
                    filename = Path(lookup_path).name
                    if filename:
                        candidates = self._symbol_mapper.lookup(filename, int(line))
                if candidates:
                    addresses.append(int(candidates[0]))
                    self.logger.debug("Resolved %s:%s to addresses: %s", lookup_path, line, 
                                    [f"0x{addr:04X}" for addr in candidates])
                else:
                    self.logger.debug("No address mapping found for %s:%s", lookup_path, line)
            except Exception as exc:
                self.logger.debug("symbol lookup failed for %s:%s (%s)", lookup_path, line, exc)
        parsed = self._parse_address(bp)
        if parsed is not None:
            explicit_addresses.append(parsed)
        addresses.extend(explicit_addresses)
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

    def _lookup_symbol_addresses(self, name: str) -> List[int]:
        if not self._symbol_mapper:
            return []
        try:
            return [int(value) & 0xFFFF for value in self._symbol_mapper.lookup_symbol(str(name))]
        except Exception:
            return []

    def _ensure_symbol_mapper(self, force: bool = False) -> None:
        if not self.client or self.current_pid is None:
            return
        if not force and self._symbol_mapper is not None:
            return
        info: Dict[str, Any]
        try:
            info = self._call_backend("symbol_info", self.current_pid)
        except Exception as exc:
            self.logger.debug("symbol_info failed: %s", exc)
            return
        if not info.get("loaded"):
            hint = str(self._sym_hint) if self._sym_hint else None
            if hint:
                self.logger.info("Attempting to load symbols from hint: %s", hint)
                try:
                    self._call_backend("load_symbols", self.current_pid, path=hint)
                    info = self._call_backend("symbol_info", self.current_pid)
                    self.logger.info("Symbols loaded successfully from: %s", hint)
                except Exception as exc:
                    self.logger.warning("symbol load failed for pid %s: %s", self.current_pid, exc)
                    info = {}
            if not info.get("loaded"):
                if force:
                    self.logger.warning("Symbols not loaded for pid %s - breakpoint source mapping will not work", self.current_pid)
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
            self._symbol_mapper = SymbolIndex(resolved)
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
                self.logger.warning("Breakpoint at %s:%s could not be resolved: %s", source_path, line, reason)
                results.append({"verified": False, "line": line, "message": reason})
                continue
            verified_any = False
            failed_error: Optional[str] = None
            for addr in addresses:
                try:
                    self._call_backend("set_breakpoint", self.current_pid, addr)
                    verified_any = True
                    self.logger.info("Breakpoint set at %s:%s -> 0x%04X", source_path, line, addr)
                except DebuggerBackendError:
                    raise
                except Exception as exc:
                    failed_error = str(exc)
                    self.logger.warning("Breakpoint set failed for 0x%04X at %s:%s: %s", addr, source_path, line, exc)
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

    def _apply_function_breakpoint(
        self,
        source_key: str,
        function_name: str,
        breakpoint_spec: JsonDict,
    ) -> tuple[JsonDict, List[JsonDict]]:
        self._clear_breakpoints(source_key)
        addresses = self._lookup_symbol_addresses(function_name)
        verified = False
        message: Optional[str] = None
        entry: JsonDict = {
            "name": function_name,
            "verified": False,
        }
        new_entries: List[JsonDict] = []
        if not addresses:
            message = "symbol not found"
        else:
            for addr in addresses:
                try:
                    self._call_backend("set_breakpoint", self.current_pid, addr)
                    verified = True
                    self.logger.info("Function breakpoint %s -> 0x%04X", function_name, addr)
                except DebuggerBackendError:
                    raise
                except Exception as exc:
                    message = str(exc)
                    self.logger.warning("Function breakpoint failed for %s at 0x%04X: %s", function_name, addr, exc)
            if verified:
                entry["instructionReference"] = f"{addresses[0]:#x}"
                entry["address"] = addresses[0]
                entry["line"] = None
                new_entries.append({"addresses": addresses})
        entry["verified"] = verified
        if message:
            entry["message"] = message
        return entry, new_entries

    def _record_breakpoint_spec(
        self,
        source_key: str,
        source: JsonDict,
        breakpoints: List[JsonDict],
        *,
        kind: str = "source",
    ) -> None:
        cloned_source = copy.deepcopy(source)
        cloned_bps = copy.deepcopy(breakpoints)
        self._breakpoint_specs[source_key] = {"source": cloned_source, "breakpoints": cloned_bps, "kind": kind}

    def _reapply_pending_breakpoints(self) -> None:
        if not self.client or not self._pending_breakpoints:
            return
        remaining = self._remaining_backoff("breakpoint")
        if remaining > 0:
            self.logger.debug("Skipping breakpoint reapply (backoff %.2fs remaining)", remaining)
            return
        self.logger.info("Reapplying %d pending breakpoint sources", len(self._pending_breakpoints))
        pending_items = list(self._pending_breakpoints.items())
        self._pending_breakpoints.clear()
        for index, (source_key, entry) in enumerate(pending_items):
            source = entry.get("source") or {}
            bps = entry.get("breakpoints") or []
            kind = entry.get("kind") or "source"
            if kind == "function":
                try:
                    self._reapply_function_breakpoints(source_key, source, bps)
                except DebuggerBackendError as exc:
                    self.logger.warning("Deferring function breakpoint reapply for %s: %s", source.get("name"), exc)
                    self._requeue_pending_breakpoints(source_key, entry, pending_items[index + 1 :])
                    self._enter_backoff("breakpoint", exc)
                    break
                continue
            if kind == "instruction":
                try:
                    self._reapply_instruction_breakpoints(source_key, bps)
                except DebuggerBackendError as exc:
                    self.logger.warning("Deferring instruction breakpoint reapply for %s: %s", source_key, exc)
                    self._requeue_pending_breakpoints(source_key, entry, pending_items[index + 1 :])
                    self._enter_backoff("breakpoint", exc)
                    break
                continue
            source_path = source.get("path") or source.get("name")
            self.logger.info("Reapplying breakpoints for source: %s (%d breakpoints)", source_path, len(bps))
            try:
                results, new_entries = self._apply_breakpoints_for_source(source_key, source_path, source, bps)
            except DebuggerBackendError as exc:
                self.logger.warning("Deferring breakpoint reapply for %s: %s", source_path, exc)
                self._requeue_pending_breakpoints(source_key, entry, pending_items[index + 1 :])
                self._enter_backoff("breakpoint", exc)
                break
            self._breakpoints[source_key] = new_entries
            for bp in results:
                if bp.get("verified"):
                    self.logger.info(
                        "Breakpoint verified after connection: %s:%s -> 0x%04X",
                        source_path,
                        bp.get("line"),
                        bp.get("address", 0),
                    )
                    self.protocol.send_event("breakpoint", {"reason": "changed", "breakpoint": bp})
                else:
                    self.logger.warning(
                        "Breakpoint not verified after connection: %s:%s - %s",
                        source_path,
                        bp.get("line"),
                        bp.get("message", "unknown reason"),
                    )
        else:
            self._reset_backoff("breakpoint")

    def _requeue_pending_breakpoints(
        self,
        source_key: str,
        entry: Dict[str, Any],
        remaining: List[Tuple[str, Dict[str, Any]]],
    ) -> None:
        self._pending_breakpoints[source_key] = entry
        for key, payload in remaining:
            self._pending_breakpoints[key] = payload

    def _reapply_function_breakpoints(self, source_key: str, source: JsonDict, breakpoints: List[JsonDict]) -> None:
        name = source.get("name")
        if not name:
            return
        result, new_entries = self._apply_function_breakpoint(source_key, name, breakpoints[0] if breakpoints else {})
        self._breakpoints[source_key] = new_entries
        if result.get("verified"):
            self.protocol.send_event("breakpoint", {"reason": "changed", "breakpoint": result})
        else:
            self.logger.warning("Function breakpoint %s not verified after reconnect: %s", name, result.get("message", "unknown"))

    def _reapply_instruction_breakpoints(self, source_key: str, breakpoints: List[JsonDict]) -> None:
        addresses: List[int] = []
        for bp in breakpoints:
            address = bp.get("address")
            if isinstance(address, (int, float)):
                addresses.append(int(address) & 0xFFFFFFFF)
                continue
            parsed = self._parse_instruction_breakpoint(bp)
            if parsed is not None:
                addresses.append(parsed)
        results = self._apply_instruction_breakpoints(source_key, addresses)
        for entry in results:
            self.protocol.send_event("breakpoint", {"reason": "changed", "breakpoint": entry})

    def _apply_instruction_breakpoints(self, source_key: str, addresses: List[int]) -> List[JsonDict]:
        self._clear_breakpoints(source_key)
        results: List[JsonDict] = []
        if not addresses:
            self._breakpoints[source_key] = []
            return results
        errors: Dict[int, str] = {}
        for addr in addresses:
            try:
                self._call_backend("set_breakpoint", self.current_pid, addr)
                self.logger.info("Instruction breakpoint set at 0x%04X", addr)
            except DebuggerBackendError:
                raise
            except Exception as exc:
                errors[addr] = str(exc)
                self.logger.warning("Instruction breakpoint failed at 0x%04X: %s", addr, exc)
        entry = {"addresses": addresses}
        self._breakpoints[source_key] = [entry]
        for addr in addresses:
            result: JsonDict = {
                "instructionReference": f"{addr:#x}",
                "address": addr,
                "id": addr,
                "verified": addr not in errors,
            }
            if addr in errors:
                result["message"] = errors[addr]
            results.append(result)
        return results

    def _cleanup_obsolete_function_breakpoints(self, active_keys: Set[str]) -> None:
        all_keys = [key for key in list(self._breakpoints.keys()) if key.startswith("function::")]
        for key in all_keys:
            if key in active_keys:
                continue
            self._clear_breakpoints(key)
            self._breakpoints.pop(key, None)
            self._breakpoint_specs.pop(key, None)
            self._pending_breakpoints.pop(key, None)

    def _ensure_watch_entry(self, expression: str, frame: Optional[_FrameRecord]):
        expr = expression.strip()
        if not expr or not self.client:
            return None
        normalized_expr = expr
        self._ensure_symbol_mapper()
        expr_lower = expr.lower()
        kind = "local" if expr_lower.startswith("local:") else self._classify_watch_expression(expr)
        if kind == "symbol":
            symbol_meta = self._find_symbol(expr, frame, include_globals=True)
            if symbol_meta is None:
                raise RuntimeError(f"symbol '{expr}' not found (ensure .sym is loaded)")
            if self._symbol_requires_stack(symbol_meta):
                normalized_expr = self._format_local_watch_expression(expr, frame, symbol_meta)
                if not normalized_expr:
                    raise RuntimeError(f"symbol '{expr}' refers to a stack variable but no frame is selected")
        if kind == "local":
            normalized_expr = self._format_local_watch_expression(expr, frame, None)
            if not normalized_expr:
                raise RuntimeError("local watches require an active stack frame")
        watch_id = self._watch_expr_to_id.get(normalized_expr)
        if watch_id is None:
            record = self._call_backend("add_watch", self.current_pid, normalized_expr)
            watch_id = getattr(record, "watch_id", None)
            if watch_id is None and isinstance(record, dict):
                watch_id = record.get("watch_id") or record.get("id")
            watch_id = int(watch_id or 0)
            if watch_id:
                self._watch_expr_to_id[normalized_expr] = watch_id
                self._watch_id_to_expr[watch_id] = normalized_expr
                self._invalidate_variables_scope()
        if not watch_id:
            return None
        watches = self._call_backend("list_watches", self.current_pid)
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

    def _format_local_watch_expression(
        self,
        expr: str,
        frame: Optional[_FrameRecord],
        symbol_meta: Optional[Dict[str, Any]],
    ) -> Optional[str]:
        if expr.lower().startswith("local:"):
            return expr
        function_name = None
        if symbol_meta:
            function_name = symbol_meta.get("function") or symbol_meta.get("scope")
        if not function_name and frame and frame.name:
            function_name = frame.name
        if not frame and not function_name:
            return None
        if function_name:
            return f"local:{function_name}::{expr}"
        return f"local:{expr}"

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
                    self._call_backend("remove_watch", self.current_pid, watch_id)
                except Exception:
                    self.logger.debug("failed to remove watch %s", watch_id)
        self._watch_expr_to_id.clear()
        self._watch_id_to_expr.clear()

    def _restore_watches(self, expressions: List[str]) -> None:
        if not self.client or self.current_pid is None:
            return
        self._watch_expr_to_id.clear()
        self._watch_id_to_expr.clear()
        for expr in expressions:
            try:
                record = self._call_backend("add_watch", self.current_pid, expr)
            except DebuggerBackendError:
                self.logger.warning("Failed to restore watch expression %s", expr)
                continue
            watch_id = getattr(record, "watch_id", None)
            if watch_id is None and isinstance(record, dict):
                watch_id = record.get("watch_id") or record.get("id")
            if watch_id is None:
                continue
            watch_id = int(watch_id)
            self._watch_expr_to_id[expr] = watch_id
            self._watch_id_to_expr[watch_id] = expr

    def _should_attempt_reconnect(self, exc: Exception) -> bool:
        message = str(exc).lower()
        if any(token in message for token in self._RECONNECT_FATAL_TOKENS):
            return False
        cause = getattr(exc, "__cause__", None)
        if cause and self._is_transient_exception(cause):
            return True
        return any(token in message for token in self._RECONNECT_TRANSIENT_TOKENS)

    def _is_transient_exception(self, error: Exception) -> bool:
        if isinstance(error, (TimeoutError, ConnectionError, OSError)):
            return True
        name = error.__class__.__name__.lower()
        if "connection" in name or "timeout" in name:
            return True
        text = " ".join(str(arg) for arg in getattr(error, "args", ()))
        text = text.lower()
        return any(token in text for token in self._RECONNECT_TRANSIENT_TOKENS)

    def _attempt_reconnect(self, exc: Exception) -> bool:
        if self._reconnecting or not self._connection_config:
            return False
        self._reconnecting = True
        stored_specs = copy.deepcopy(self._breakpoint_specs)
        watch_exprs = list(self._watch_expr_to_id.keys())
        self.logger.warning("Debugger backend error (%s); attempting reconnect", exc)
        self._emit_status_event("reconnecting", message=str(exc))
        try:
            self._connect(**self._connection_config)
            if self.current_pid and not self._pid_exists(self.current_pid):
                message = f"Target PID {self.current_pid} is no longer available"
                self.logger.error(message)
                self._emit_status_event("error", message=message)
                self._emit_console_message(message)
                self.current_pid = None
                return False
            if stored_specs:
                self._pending_breakpoints.update(stored_specs)
                self._reapply_pending_breakpoints()
            if watch_exprs:
                self._restore_watches(watch_exprs)
            self._emit_status_event("connected", message="Reconnected")
            return True
        except DebuggerBackendError as reconnect_exc:
            self.logger.error("Reconnect failed: %s", reconnect_exc)
            self._emit_status_event("error", message=str(reconnect_exc))
            return False
        finally:
            self._reconnecting = False
        return False

    def _instruction_breakpoint_key(self) -> str:
        pid = self.current_pid if self.current_pid is not None else 0
        return f"instruction::{pid}"

    def _remote_breakpoint_key(self) -> str:
        pid = self.current_pid if self.current_pid is not None else 0
        return f"remote::{pid}"

    def _extract_addresses_for_key(self, source_key: str) -> List[int]:
        entries = self._breakpoints.get(source_key, [])
        addresses: List[int] = []
        for entry in entries:
            value = entry.get("addresses")
            if isinstance(value, int):
                addresses.append(value & 0xFFFFFFFF)
            elif isinstance(value, list):
                for addr in value:
                    try:
                        addresses.append(int(addr) & 0xFFFFFFFF)
                    except (TypeError, ValueError):
                        continue
        return addresses

    def _collect_breakpoint_addresses(self, *, include_remote: bool = True) -> Set[int]:
        addresses: Set[int] = set()
        remote_key = self._remote_breakpoint_key()
        for key, entries in self._breakpoints.items():
            if not include_remote and key == remote_key:
                continue
            for entry in entries:
                value = entry.get("addresses")
                if isinstance(value, int):
                    addresses.add(int(value) & 0xFFFFFFFF)
                elif isinstance(value, list):
                    for addr in value:
                        try:
                            addresses.add(int(addr) & 0xFFFFFFFF)
                        except (TypeError, ValueError):
                            continue
        return addresses

    def _schedule_remote_breakpoint_poll(self, delay: Optional[float] = None) -> None:
        if delay is None:
            delay = self._remote_breakpoint_interval
        delay = max(delay, self._remaining_backoff("breakpoint"))
        self._cancel_remote_breakpoint_poll()
        if not self.client or self.current_pid is None:
            return
        timer = threading.Timer(delay, self._run_remote_breakpoint_poll)
        timer.daemon = True
        self._remote_breakpoint_timer = timer
        timer.start()

    def _cancel_remote_breakpoint_poll(self) -> None:
        timer = self._remote_breakpoint_timer
        if timer is not None:
            timer.cancel()
        self._remote_breakpoint_timer = None

    def _run_remote_breakpoint_poll(self) -> None:
        self._remote_breakpoint_timer = None
        if not self.client or self.current_pid is None:
            return
        try:
            self._sync_remote_breakpoints()
        except Exception:
            self.logger.debug("Remote breakpoint poll failed", exc_info=True)
        self._schedule_remote_breakpoint_poll()

    def _stop_event_stream(self) -> None:
        if self.backend:
            try:
                self.backend.stop_event_stream()
            except DebuggerBackendError:
                pass
        self._event_stream_active = False

    def _shutdown(self) -> None:
        self._cleanup_watches()
        self._clear_all_breakpoints()
        self._cancel_remote_breakpoint_poll()
        self._cancel_step_fallback()
        self._symbol_mapper = None
        self._symbol_path = None
        self._symbol_mtime = None
        self._thread_states.clear()
        self._cancel_pause_fallback()
        self._synthetic_pause_pending = False
        self._stop_event_stream()
        if self._debugger_session:
            try:
                self._debugger_session.disconnect()
            except Exception:
                pass
            self._debugger_session = None
        elif self.backend:
            try:
                self.backend.disconnect()
            except Exception:
                pass
        self.backend = None
        self.client = None
        self._connection_config.clear()
        self._emit_status_event("disconnected")
        self._source_ref_to_path.clear()
        self._source_path_to_ref.clear()
        self._next_source_id = 1
        self.project_root = REPO_ROOT
        self._source_base_dirs = [REPO_ROOT]
        self._task_snapshot_cache.clear()
        self._debug_state_pids.clear()

    def _update_project_root(self, args: JsonDict) -> None:
        workspace_hint = args.get("workspaceFolder") or args.get("workspaceRoot") or args.get("workspace")
        candidate_root: Optional[Path] = None
        if workspace_hint:
            try:
                candidate_root = Path(workspace_hint).expanduser().resolve()
            except Exception:
                self.logger.debug("Failed to resolve workspace hint %s", workspace_hint, exc_info=True)
        if candidate_root is None and self._sym_hint:
            inferred = self._infer_repo_root(self._sym_hint.parent)
            candidate_root = inferred or self._sym_hint.parent
        if candidate_root is None:
            candidate_root = REPO_ROOT
        self.project_root = candidate_root
        base_dirs: List[Path] = []

        def _add_base(path: Optional[Path]) -> None:
            if not path:
                return
            resolved = path.resolve()
            if resolved not in base_dirs:
                base_dirs.append(resolved)

        _add_base(candidate_root)
        _add_base(REPO_ROOT)
        if self._sym_hint:
            sym_dir = self._sym_hint.parent.resolve()
            chain: List[Path] = [sym_dir]
            chain.extend(list(sym_dir.parents))
            for parent in chain:
                _add_base(parent)
                if candidate_root and parent == candidate_root:
                    break
                if parent == REPO_ROOT:
                    break
        self._source_base_dirs = base_dirs

    def _infer_repo_root(self, start: Path) -> Optional[Path]:
        try:
            current = start.resolve()
        except Exception:
            current = start
        for candidate in [current] + list(current.parents):
            if (candidate / ".git").is_dir():
                return candidate
            if (candidate / "python").is_dir() and (candidate / "examples").is_dir():
                return candidate
        return None

    def _render_source(self, path: Optional[str]) -> Optional[JsonDict]:
        if not path:
            return None
        source_path = Path(path)
        if not source_path.is_absolute():
            resolved: Optional[Path] = None
            for base in self._source_base_dirs:
                candidate = (base / source_path).resolve()
                if candidate.exists():
                    resolved = candidate
                    break
            if resolved is None:
                fallback = (self.project_root / source_path).resolve()
                self.logger.debug(
                    "Source path %s not found in bases %s, falling back to %s",
                    path,
                    [str(b) for b in self._source_base_dirs],
                    fallback,
                )
                resolved = fallback
            source_path = resolved
        else:
            source_path = source_path.resolve()
        if not source_path.exists():
            self.logger.debug("Resolved source path %s still missing on disk", source_path)
        key = source_path.as_posix()
        ref = self._source_path_to_ref.get(key)
        if ref is None:
            ref = self._next_source_id
            self._next_source_id += 1
            self._source_path_to_ref[key] = ref
            self._source_ref_to_path[ref] = key
        else:
            self.logger.debug("Resolved source %s -> %s (ref=%s)", path, key, ref)
        return {"name": source_path.name, "path": key, "sourceReference": ref}

    def _emit_stopped_event(
        self,
        *,
        pid: Optional[int],
        reason: Optional[str],
        description: Optional[str] = None,
        pc: Optional[int] = None,
    ) -> None:
        thread_id = pid or self.current_pid
        if thread_id is None:
            return
        reason_value = reason or "stopped"
        body: JsonDict = {
            "reason": reason_value,
            "threadId": thread_id,
            "description": description or reason_value,
            "allThreadsStopped": False,
        }
        self._ensure_symbol_mapper()
        pc_int: Optional[int] = None
        if pc is not None:
            pc_int = int(pc) & 0xFFFFFFFF
            body["instructionPointerReference"] = f"{pc_int:#x}"
            mapped = self._map_pc_to_source(pc_int)
            if mapped:
                body["source"] = self._render_source(mapped.get("path"))
                if mapped.get("line") is not None:
                    body["line"] = mapped.get("line")
                if mapped.get("column") is not None:
                    body["column"] = mapped.get("column")
                self.logger.info("Stopped event: reason=%s, pc=0x%04X, source=%s:%s", 
                                reason_value, pc_int, mapped.get("path"), mapped.get("line"))
            else:
                self.logger.info("Stopped event: reason=%s, pc=0x%04X (no source mapping)", reason_value, pc_int)
        else:
            self.logger.info("Stopped event: reason=%s (no PC available)", reason_value)
        thread_id_int = int(thread_id)
        if self._suppress_duplicate_stop(thread_id_int, reason_value, pc_int):
            self.logger.debug("Suppressing duplicate stopped event for pid=%s reason=%s pc=%s", thread_id_int, reason_value, pc_int)
            return
        self.protocol.send_event("stopped", body)
        self._emit_disassembly_refresh_event(pc)

    def _handle_task_state_event(self, event: JsonDict) -> None:
        data = event.get("data") or {}
        pid = event.get("pid") or self.current_pid
        if pid is None:
            return
        name = None
        if isinstance(data, dict):
            name = data.get("name")
        created = self._ensure_thread_entry(pid, name=name)
        state = str(data.get("new_state") or "").lower()
        reason = str(data.get("reason") or "").lower()
        previous_state = self._thread_states.get(pid, {}).get("state")
        meta = self._thread_states.get(pid)
        if meta is not None:
            if state:
                meta["state"] = state
            if name:
                meta["name"] = name
        details = data.get("details") if isinstance(data, dict) else None
        snapshot_record: Dict[str, Any] = {
            "pid": pid,
            "state": state or previous_state,
            "name": (meta or {}).get("name"),
            "details": details,
            "reason": reason,
        }
        if created:
            self.protocol.send_event("thread", {"reason": "started", "threadId": pid})
        if state == "terminated":
            self.protocol.send_event("thread", {"reason": "exited", "threadId": pid})
            self._thread_states.pop(pid, None)
            if self.current_pid == pid:
                self.current_pid = None
            snapshot_record["state"] = "terminated"
            self._cache_task_snapshot(pid, snapshot_record)
            return
        if state == "running":
            if previous_state != "running":
                self.protocol.send_event("continued", {"threadId": pid})
            snapshot_record["state"] = "running"
            self._cache_task_snapshot(pid, snapshot_record)
            return
        stoppable_states = {"paused", "stopped", "waiting_mbx", "sleeping"}
        stoppable_reasons = {"user_pause", "debug_break", "mailbox_wait", "sleep", "sleep_request"}
        if state in stoppable_states or reason in stoppable_reasons:
            pc = self._extract_task_state_pc(data)
            description = self._describe_stop_reason(state, reason, data)
            if reason == "user_pause":
                if self._pending_pause:
                    self._pending_pause = False
                    self._cancel_pause_fallback()
                    self.logger.info("Pause completed for PID %s (event)", pid)
                if self._synthetic_pause_pending:
                    self.logger.debug("Suppressing duplicate user_pause event (snapshot already emitted)")
                    self._synthetic_pause_pending = False
                    self._complete_pending_step()
                    snapshot_record["state"] = state or previous_state
                    self._cache_task_snapshot(pid, snapshot_record)
                    return
                self._synthetic_pause_pending = False
            self._emit_stopped_event(
                pid=pid,
                reason=reason or state or "stopped",
                description=description,
                pc=pc,
            )
            self._complete_pending_step()
            snapshot_record["state"] = state or previous_state or reason or "stopped"
            self._cache_task_snapshot(pid, snapshot_record)
            return
        self._cache_task_snapshot(pid, snapshot_record)

    def _ensure_thread_entry(self, pid: Optional[int], *, name: Optional[str] = None) -> bool:
        if pid is None:
            return False
        if pid not in self._thread_states:
            self._thread_states[pid] = {"name": name or f"PID {pid}", "state": None}
            return True
        if name:
            self._thread_states[pid]["name"] = name
        return False

    def _set_thread_state(self, pid: Optional[int], state: Optional[str]) -> None:
        if pid is None:
            return
        entry = self._thread_states.setdefault(pid, {"name": f"PID {pid}", "state": None})
        entry["state"] = state
        if state in {"terminated", "exited"}:
            self._debug_state_pids.discard(pid)

    def _extract_task_state_pc(self, task_data: JsonDict) -> Optional[int]:
        details = None
        if isinstance(task_data, dict):
            details = task_data.get("details")
        if isinstance(details, dict):
            pc = details.get("pc")
            if isinstance(pc, str):
                try:
                    return int(pc, 0)
                except ValueError:
                    return None
            if isinstance(pc, (int, float)):
                return int(pc)
        return None

    def _fetch_task_snapshot(self, pid: int) -> Optional[Dict[str, Any]]:
        try:
            listing = self._call_backend("list_tasks")
        except DebuggerBackendError:
            raise
        except Exception as exc:
            self.logger.debug("State sync list_tasks failed: %s", exc)
            return None
        tasks = listing.get("tasks")
        if not isinstance(tasks, list):
            return None
        for entry in tasks:
            if not isinstance(entry, dict):
                continue
            raw_pid = entry.get("pid")
            try:
                entry_pid = int(raw_pid)
            except (TypeError, ValueError):
                continue
            if entry_pid == pid:
                snapshot = dict(entry)
                self._cache_task_snapshot(pid, snapshot)
                return snapshot
        return None

    def _extract_snapshot_pc(self, snapshot: Dict[str, Any]) -> Optional[int]:
        for key in ("pc", "PC"):
            value = snapshot.get(key)
            if isinstance(value, (int, float)):
                return int(value)
            if isinstance(value, str):
                try:
                    return int(value, 0)
                except ValueError:
                    continue
        context = snapshot.get("context")
        if isinstance(context, dict):
            for key in ("pc", "PC"):
                value = context.get(key)
                if isinstance(value, (int, float)):
                    return int(value)
                if isinstance(value, str):
                    try:
                        return int(value, 0)
                    except ValueError:
                        continue
        details = snapshot.get("details")
        if isinstance(details, dict):
            for key in ("pc", "PC"):
                value = details.get(key)
                if isinstance(value, (int, float)):
                    return int(value)
                if isinstance(value, str):
                    try:
                        return int(value, 0)
                    except ValueError:
                        continue
        return None

    def _describe_stop_reason(self, state: Optional[str], reason: Optional[str], payload: JsonDict) -> str:
        details = payload.get("details")
        if not isinstance(details, dict):
            details = {}
        descriptor = details.get("descriptor") or payload.get("descriptor")
        handle = details.get("handle") or payload.get("handle")
        deadline = details.get("deadline") or payload.get("deadline")
        timeout = details.get("timeout") or details.get("sleep_ms") or payload.get("sleep_pending_ms")
        base = reason or state or "stopped"
        normalized_state = (state or "").lower()
        normalized_reason = (reason or "").lower()
        if normalized_reason == "user_pause":
            return "Paused by user"
        if normalized_state == "waiting_mbx" or normalized_reason == "mailbox_wait":
            target = descriptor if descriptor is not None else handle
            if target is not None:
                return f"Waiting on mailbox {target}"
            return "Waiting on mailbox"
        if normalized_state == "sleeping" or normalized_reason in {"sleep", "sleep_request"}:
            if timeout:
                return f"Sleeping ({timeout} ms)"
            return "Sleeping"
        if normalized_reason == "debug_break":
            symbol = details.get("symbol") or payload.get("symbol")
            if symbol:
                return f"Breakpoint hit ({symbol})"
            return "Breakpoint hit"
        if normalized_reason == "step":
            return "Step complete"
        if normalized_reason == "instruction step":
            return "Instruction step complete"
        if normalized_reason == "mailbox_timeout":
            return "Mailbox wait timed out"
        if normalized_state:
            return f"Task {normalized_state}"
        return base

    def _synchronize_execution_state(self, *, source: str, refresh_breakpoints: bool = False) -> None:
        pid = self.current_pid
        if pid is None or not self.client:
            return
        remaining = self._remaining_backoff("state")
        if remaining > 0:
            self.logger.debug("Skipping execution state sync (backoff %.2fs remaining)", remaining)
            return
        if refresh_breakpoints:
            try:
                self._sync_remote_breakpoints()
            except Exception:
                self.logger.debug("Breakpoint sync (%s) failed", source, exc_info=True)
        snapshot = self._get_cached_snapshot(pid)
        if snapshot is None:
            try:
                snapshot = self._fetch_task_snapshot(pid)
            except DebuggerBackendError as exc:
                self.logger.debug("State sync list_tasks failed: %s", exc)
                self._enter_backoff("state", exc)
                return
            self._reset_backoff("state")
            if not snapshot:
                return
        else:
            self.logger.debug("Using cached task snapshot for pid %s", pid)
        state_raw = snapshot.get("state")
        if not state_raw:
            return
        state = str(state_raw).lower()
        reason_raw = snapshot.get("last_reason") or snapshot.get("reason")
        reason = str(reason_raw).lower() if isinstance(reason_raw, str) else None
        details_payload = snapshot.get("details")
        details = dict(details_payload) if isinstance(details_payload, dict) else {}
        pc_value = self._extract_snapshot_pc(snapshot)
        if pc_value is None and state in {"paused", "stopped"}:
            pc_value = self._read_current_pc()
        if pc_value is not None and "pc" not in details:
            details["pc"] = f"0x{pc_value & 0xFFFFFFFF:08X}"
        cached_state = self._thread_states.get(pid, {}).get("state")
        if cached_state == state:
            return
        event_data: JsonDict = {"new_state": state}
        if reason:
            event_data["reason"] = reason
        if details:
            event_data["details"] = details
        name_value = snapshot.get("name")
        if isinstance(name_value, str):
            event_data["name"] = name_value
        self.logger.info("State sync (%s): pid=%s state=%s reason=%s", source, pid, state, reason or "n/a")
        self._handle_task_state_event({"pid": pid, "data": event_data})

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
        if not normalized or not self.client or self.current_pid is None:
            return None
        state = self._call_backend("get_register_state", self.current_pid)
        if not state:
            return None
        if normalized == "PC":
            value = state.pc
        elif normalized == "SP":
            value = state.sp
        elif normalized == "PSW":
            value = state.psw
        elif normalized == "REG_BASE":
            value = state.reg_base
        elif normalized == "STACK_BASE":
            value = state.stack_base
        elif normalized == "STACK_LIMIT":
            value = state.stack_limit
        elif normalized == "STACK_SIZE":
            value = state.stack_size
        elif normalized == "SP_EFFECTIVE":
            value = state.sp_effective
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
                result = self._call_backend("symbol_lookup_name", self.current_pid, name)
                if result:
                    return result
            except Exception:
                return None
        if self._symbol_mapper:
            addresses = self._symbol_mapper.lookup_symbol(name)
            if addresses:
                return {"name": name, "address": addresses[0]}
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
        data = self._call_backend("read_memory", addr, length, pid=self.current_pid)
        if not data:
            return None
        if len(data) < length:
            data = data.ljust(length, b"\x00")
        value = int.from_bytes(data[:length], byteorder="little")
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
        data = self._call_backend("read_memory", int(addr), int(size), pid=self.current_pid)
        if not data:
            return None
        value = int.from_bytes(data[: min(len(data), 4)], byteorder="little")
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
                    relative = loc.get("relative")
                    base: Optional[int]
                    if relative == "fp":
                        base = frame.fp
                    elif relative == "sp":
                        base = frame.sp
                    else:
                        base = frame.fp if frame.fp is not None else frame.sp
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


    def _suppress_duplicate_stop(self, pid: int, reason: str, pc: Optional[int]) -> bool:
        now = time.monotonic()
        last = self._last_stop_event.get(pid)
        if last:
            last_reason, last_pc, last_time = last
            if last_reason == reason and last_pc == pc and now - last_time < 0.2:
                return True
        self._last_stop_event[pid] = (reason, pc, now)
        return False

    def _temporarily_disable_breakpoint(self, address: int) -> List[int]:
        if not self.client or self.current_pid is None:
            return []
        normalized = address & 0xFFFFFFFF
        candidates: List[int] = []
        try:
            entries = self._call_backend("list_breakpoints", self.current_pid)
        except Exception as exc:
            self.logger.debug("list_breakpoints failed during step: %s", exc)
            entries = []
        if isinstance(entries, list):
            for item in entries:
                try:
                    value = int(item, 0) if isinstance(item, str) else int(item)
                except (TypeError, ValueError):
                    continue
                if (value & 0xFFFFFFFF) == normalized:
                    candidates.append(value & 0xFFFFFFFF)
        disabled: List[int] = []
        for addr in candidates:
            try:
                self._call_backend("clear_breakpoint", self.current_pid, addr)
                disabled.append(addr)
            except Exception:
                self.logger.debug("temporary breakpoint clear failed at 0x%X", addr, exc_info=True)
        return disabled

    def _restore_temporarily_disabled_breakpoints(self, addresses: List[int]) -> None:
        if not self.client or self.current_pid is None:
            return
        for addr in addresses:
            try:
                self._call_backend("set_breakpoint", self.current_pid, addr)
            except Exception:
                self.logger.debug("failed to restore breakpoint at 0x%X", addr, exc_info=True)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="HSX Debug Adapter", add_help=False)
    parser.add_argument("--pid", type=int, required=True)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=9998)
    parser.add_argument("--log-file")
    parser.add_argument("--log-level", default="INFO")
    parser.add_argument("--adapter-version", default=os.environ.get("HSX_EXTENSION_VERSION", "unknown"))
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
    adapter_version = args.adapter_version or "unknown"
    if adapter_version == "unknown":
        adapter_version = _detect_extension_version()
    logger = logging.getLogger("hsx-dap")
    logger.info("HSX DAP adapter starting (pid=%s, version=%s)", os.getpid(), adapter_version)
    try:
        adapter.serve()
        logger.info("HSX DAP adapter exiting normally")
        return 0
    except Exception:
        logger.exception("HSX DAP adapter crashed")
        raise
