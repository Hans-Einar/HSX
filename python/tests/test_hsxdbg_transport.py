import json
import socket
import threading
import time
from typing import Optional

from python.hsxdbg.transport import HSXTransport, TransportConfig
from python.hsxdbg.session import SessionManager, SessionConfig
from python.hsxdbg.events import EventBus, EventSubscription


class DummyDebuggerServer:
    def __init__(self) -> None:
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.bind(("127.0.0.1", 0))
        self.port = self._sock.getsockname()[1]
        self._sock.listen(5)
        self._stop = threading.Event()
        self._next_seq = 100
        self.last_ack_seq: Optional[int] = None
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                conn, _ = self._sock.accept()
            except OSError:
                break
            conn.settimeout(1.0)
            thread = threading.Thread(target=self._handle_client, args=(conn,), daemon=True)
            thread.start()

    def _handle_client(self, conn: socket.socket) -> None:
        buffer = b""
        with conn:
            while not self._stop.is_set():
                try:
                    chunk = conn.recv(4096)
                except socket.timeout:
                    continue
                except OSError:
                    break
                if not chunk:
                    break
                buffer += chunk
                while b"\n" in buffer:
                    line, buffer = buffer.split(b"\n", 1)
                    if not line:
                        continue
                    msg = json.loads(line.decode("utf-8"))
                    cmd = msg.get("cmd")
                    response = self._handle_command(cmd, msg)
                    if response is not None:
                        try:
                            conn.sendall(json.dumps(response).encode("utf-8") + b"\n")
                        except OSError:
                            return
                    if cmd == "event.test":
                        event = {
                            "type": "debug_break",
                            "seq": self._next_seq,
                            "pid": 1,
                            "ts": time.time(),
                            "data": {"pc": 0x1000},
                        }
                        self._next_seq += 1
                        try:
                            conn.sendall(json.dumps(event).encode("utf-8") + b"\n")
                        except OSError:
                            return
                    if cmd == "force_close":
                        return

    def _handle_command(self, cmd: str, msg: dict) -> dict:
        if cmd == "session.open":
            caps = msg.get("capabilities") or {}
            return {
                "version": 1,
                "status": "ok",
                "session": {
                    "id": "sess-123",
                    "client": msg.get("client", ""),
                    "heartbeat_s": 30,
                    "features": caps.get("features", []),
                    "max_events": caps.get("max_events", 128),
                    "pid_lock": msg.get("pid_lock"),
                    "warnings": ["max_events_clamped:256"],
                },
            }
        if cmd == "session.keepalive":
            return {"version": 1, "status": "ok"}
        if cmd == "ping":
            return {"version": 1, "status": "ok", "reply": "pong"}
        if cmd == "event.test":
            return {"version": 1, "status": "ok"}
        if cmd == "events.subscribe":
            return {
                "version": 1,
                "status": "ok",
                "events": {
                    "token": "sub-dummy",
                    "max": 128,
                    "cursor": self._next_seq - 1,
                    "retention_ms": 1000,
                },
            }
        if cmd == "events.ack":
            seq = msg.get("seq")
            self.last_ack_seq = seq
            return {
                "version": 1,
                "status": "ok",
                "events": {"last_ack": seq, "pending": 0},
            }
        if cmd == "force_close":
            return {"version": 1, "status": "ok", "note": "closing"}
        return {"version": 1, "status": "ok"}

    def stop(self) -> None:
        self._stop.set()
        try:
            dummy = socket.create_connection(("127.0.0.1", self.port), timeout=0.2)
            dummy.close()
        except OSError:
            pass
        self._sock.close()
        self._thread.join(timeout=0.5)


def test_transport_round_trip():
    server = DummyDebuggerServer()
    try:
        transport = HSXTransport(TransportConfig(port=server.port))
        resp = transport.send_request({"cmd": "ping"})
        assert resp["status"] == "ok"
        transport.close()
    finally:
        server.stop()


def test_transport_reconnects_after_drop():
    server = DummyDebuggerServer()
    try:
        transport = HSXTransport(TransportConfig(port=server.port))
        transport.send_request({"cmd": "ping"})
        transport.send_request({"cmd": "force_close"})
        time.sleep(0.1)
        resp = transport.send_request({"cmd": "ping"})
        assert resp["status"] == "ok"
        assert transport.state == "connected"
        transport.close()
    finally:
        server.stop()


def test_transport_event_callback_and_state_hooks():
    server = DummyDebuggerServer()
    try:
        events = []
        transitions = []
        ready = threading.Event()

        transport = HSXTransport(TransportConfig(port=server.port))
        transport.register_on_connect(lambda state: transitions.append(state))
        transport.register_on_disconnect(lambda state: transitions.append(f"{state}:down"))

        def handler(message):
            events.append(message)
            ready.set()

        transport.set_event_handler(handler)
        transport.send_request({"cmd": "event.test"})
        assert ready.wait(1.0), "event handler never invoked"
        assert events[0]["type"] == "debug_break"
        transport.close()
        assert transitions[0] == "connected"
        assert transitions[-1].startswith("disconnected")
    finally:
        server.stop()


def test_session_manager_open_and_keepalive():
    server = DummyDebuggerServer()
    try:
        transport = HSXTransport(TransportConfig(port=server.port))
        session = SessionManager(
            transport=transport,
            session_config=SessionConfig(client_name="test-client", pid_lock=2),
        )
        state = session.open()
        assert state.session_id == "sess-123"
        assert state.locked and state.pid == 2
        assert state.pid_locks == [2]
        assert state.heartbeat_s == 30
        assert state.warnings == ["max_events_clamped:256"]
        session.keepalive()
        session.close()
    finally:
        server.stop()


def test_session_manager_event_bus_receives_events():
    server = DummyDebuggerServer()
    try:
        transport = HSXTransport(TransportConfig(port=server.port))
        bus = EventBus()
        bus.start(interval=0.01)
        received = []
        bus.subscribe(EventSubscription(handler=lambda event: received.append(event)))
        session = SessionManager(
            transport=transport,
            session_config=SessionConfig(client_name="bus-client", pid_lock=None),
            event_bus=bus,
        )
        session.open()
        session.subscribe_events(ack_interval=0.05)
        transport.send_request({"cmd": "event.test"})
        deadline = time.time() + 1.0
        while not received and time.time() < deadline:
            bus.pump()
            time.sleep(0.01)
        assert received and received[0].type == "debug_break"
        session.close()
        bus.stop()
    finally:
        server.stop()


def test_session_manager_auto_ack_sends_events_ack():
    server = DummyDebuggerServer()
    try:
        transport = HSXTransport(TransportConfig(port=server.port))
        bus = EventBus()
        bus.start(interval=0.01)
        session = SessionManager(transport=transport, session_config=SessionConfig(), event_bus=bus)
        session.open()
        session.subscribe_events(ack_interval=0.05)
        transport.send_request({"cmd": "event.test"})
        deadline = time.time() + 1.0
        while server.last_ack_seq is None and time.time() < deadline:
            bus.pump()
            time.sleep(0.02)
        assert server.last_ack_seq is not None
        session.close()
        bus.stop()
    finally:
        server.stop()
