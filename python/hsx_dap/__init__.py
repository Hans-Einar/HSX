"""
HSX Debug Adapter implementation for VS Code (Debug Adapter Protocol).
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

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


@dataclass
class _FrameRecord:
    pid: int
    name: str
    line: int
    column: int
    file: Optional[str]
    pc: Optional[int]


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

    def serve(self) -> None:
        while True:
            message = self.protocol.read_message()
            if message is None:
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
        self._connect(host, port, self.current_pid)
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
            )
            dap_frames.append(
                {
                    "id": frame_id,
                    "name": self._frames[frame_id].name,
                    "line": self._frames[frame_id].line,
                    "column": 1,
                    "source": {"name": frame.file or "unknown", "path": frame.file} if frame.file else None,
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
        watches = self._format_watches()
        if watches:
            scopes.append(self._make_scope("Watches", watches, expensive=False))
        return {"scopes": scopes}

    def _handle_variables(self, args: JsonDict) -> JsonDict:
        reference = int(args.get("variablesReference"))
        scope = self._scopes.get(reference)
        return {"variables": scope.variables[:] if scope else []}

    def _handle_setBreakpoints(self, args: JsonDict) -> JsonDict:  # noqa: N802
        source = args.get("source") or {}
        source_key = source.get("path") or source.get("name") or "<global>"
        breakpoints = args.get("breakpoints") or []
        self._ensure_client()
        existing = self._breakpoints.get(source_key, [])
        for bp in existing:
            addr = bp.get("address")
            if addr is not None and bp.get("verified"):
                try:
                    self.client.clear_breakpoint(addr, pid=self.current_pid)
                except Exception:
                    pass
        results: List[JsonDict] = []
        new_entries: List[JsonDict] = []
        for bp in breakpoints:
            parsed = self._parse_address(bp)
            if parsed is None:
                results.append({"verified": False, "message": "address or instructionReference required"})
                continue
            try:
                self.client.set_breakpoint(parsed, pid=self.current_pid)
                entry = {
                    "verified": True,
                    "instructionReference": f"{parsed:#x}",
                    "address": parsed,
                    "id": parsed,
                }
                new_entries.append(entry)
                results.append(entry.copy())
            except Exception as exc:
                results.append({"verified": False, "message": str(exc)})
        self._breakpoints[source_key] = new_entries
        return {"breakpoints": results}

    def _handle_threadsRequest(self, args: JsonDict) -> JsonDict:  # pragma: no cover - compatibility alias
        return self._handle_threads(args)

    def _handle_evaluate(self, args: JsonDict) -> JsonDict:
        return {"result": "not supported", "variablesReference": 0}

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
            text = f"watch {event.watch_id} updated: {event.new_value}\n"
            self.protocol.send_event("output", {"category": "console", "output": text})
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
        watches = self.client.list_watches(self.current_pid)
        results = []
        for watch in watches:
            results.append(
                {
                    "name": watch.expr or f"watch {watch.watch_id}",
                    "value": watch.value,
                    "type": "watch",
                }
            )
        return results

    def _make_scope(self, name: str, variables: List[JsonDict], *, expensive: bool) -> JsonDict:
        scope_id = self._next_scope_id
        self._next_scope_id += 1
        self._scopes[scope_id] = _ScopeRecord(variables=variables)
        return {"name": name, "variablesReference": scope_id, "expensive": expensive}

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

    def _shutdown(self) -> None:
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


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="HSX Debug Adapter", add_help=False)
    parser.add_argument("--log-file")
    parser.add_argument("--log-level", default="INFO")
    args, _ = parser.parse_known_args(argv)
    logging.basicConfig(
        filename=args.log_file,
        level=getattr(logging, str(args.log_level).upper(), logging.INFO),
        format="[%(asctime)s] %(levelname)s: %(message)s",
    )
    protocol = DAPProtocol(sys.stdin.buffer, sys.stdout.buffer)
    adapter = HSXDebugAdapter(protocol)
    adapter.serve()
    return 0
