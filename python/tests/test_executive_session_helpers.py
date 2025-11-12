import threading

import pytest

from python.executive_session import (
    ConnectionLostError,
    ExecutiveSession,
    ExecutiveSessionError,
    ProtocolVersionError,
    _EventStream,
)


class StubSession(ExecutiveSession):
    def __init__(self, responses, *, features=None):
        super().__init__("127.0.0.1", 9998, client_name="test", features=features or ["stack"])
        self._responses = list(responses)
        self.sent = []

    def _send_raw(self, payload):
        self.sent.append(payload)
        if not self._responses:
            raise AssertionError("no response queued")
        result = self._responses.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


def make_handshake(features):
    return {
        "status": "ok",
        "session": {
            "id": "sess-1",
            "heartbeat_s": 30,
            "features": list(features),
            "max_events": 128,
        },
    }


def test_configure_session_sets_pid_lock_on_first_open():
    stack_payload = {"status": "ok", "stack": {"frames": []}}
    session = StubSession(
        [make_handshake(["events", "stack"]), stack_payload],
        features=["stack"],
    )
    session.configure_session(pid_lock=5, heartbeat_s=12)
    session.stack_info(1)
    assert session.sent[0]["cmd"] == "session.open"
    assert session.sent[0]["pid_lock"] == 5
    assert session.sent[0]["heartbeat_s"] == 12


def test_configure_session_reopens_existing_session():
    responses = [
        make_handshake(["events", "stack"]),
        {"status": "ok", "stack": {"frames": []}},
        make_handshake(["events", "stack"]),
    ]
    session = StubSession(responses, features=["stack"])
    session.stack_info(1)
    session.configure_session(pid_lock=None)
    # The most recent payload should be a reopened handshake with explicit null pid_lock.
    assert session.sent[-1]["cmd"] == "session.open"
    assert "pid_lock" in session.sent[-1]
    assert session.sent[-1]["pid_lock"] is None


def test_stack_info_success_and_cache():
    stack_payload = {
        "status": "ok",
        "stack": {
            "frames": [
                {"pc": 0x1234, "func_name": "main", "func_offset": 0},
                {"pc": 0x1010, "func_name": "caller", "func_offset": 4},
            ],
            "truncated": False,
            "errors": [],
        },
    }
    session = StubSession([make_handshake(["events", "stack"]), stack_payload])
    info = session.stack_info(1, max_frames=4)
    assert info is not None
    assert session.supports_stack() is True
    frames = info["frames"]
    assert len(frames) == 2
    assert frames[0]["pc"] == 0x1234

    cached = session.stack_info(1, refresh=False)
    assert cached is not None
    assert cached != {}
    assert cached["frames"][0]["pc"] == 0x1234
    # ensure cache result is detached copy
    cached["frames"][0]["pc"] = 0xFFFF
    cached_again = session.stack_info(1, refresh=False)
    assert cached_again["frames"][0]["pc"] == 0x1234

    frames_only = session.stack_frames(1, refresh=False)
    assert len(frames_only) == 2


def test_stack_info_unsupported_graceful():
    error_payload = {
        "status": "error",
        "error": "unknown_cmd:stack",
    }
    session = StubSession([make_handshake(["events"]), error_payload])
    result = session.stack_info(2)
    assert result is None
    assert session.supports_stack() is False
    assert session.stack_info(2, refresh=False) is None
    assert session.stack_frames(2, refresh=False) == []


def test_symbols_list_success_and_payload_copy():
    symbol_block = {
        "pid": 5,
        "count": 3,
        "offset": 1,
        "limit": 1,
        "type": "functions",
        "symbols": [
            {"name": "alpha", "address": 0x100, "size": 12, "type": "function"},
            {"name": "beta", "address": 0x110, "size": 8, "type": "function"},
            {"name": "gamma", "address": 0x120, "size": 6, "type": "function"},
        ],
    }
    session = StubSession(
        [make_handshake(["events"]), {"status": "ok", "symbols": symbol_block}],
        features=["symbols"],
    )
    info = session.symbols_list(5, kind="functions", offset=1, limit=1)
    assert info == symbol_block
    assert session.supports_symbols() is True
    assert session.sent[-1]["cmd"] == "symbols"
    assert session.sent[-1]["type"] == "functions"
    assert session.sent[-1]["offset"] == 1
    assert session.sent[-1]["limit"] == 1
    # result should be a detached copy
    info["symbols"][0]["name"] = "mutated"
    assert symbol_block["symbols"][0]["name"] == "alpha"


def test_symbols_list_unknown_marks_unsupported():
    session = StubSession(
        [make_handshake(["events"]), {"status": "error", "error": "unknown_cmd:symbols"}],
        features=["symbols"],
    )
    result = session.symbols_list(3)
    assert result is None
    assert session.supports_symbols() is False


def test_symbols_list_other_error_raises():
    session = StubSession(
        [make_handshake(["events"]), {"status": "error", "error": "internal failure"}],
        features=["symbols"],
    )
    with pytest.raises(ExecutiveSessionError):
        session.symbols_list(4)


def test_memory_regions_success():
    memory_block = {
        "pid": 7,
        "program": "demo.hxe",
        "regions": [
            {"name": "code", "type": "code", "start": 0x0000, "end": 0x007F, "length": 0x80, "permissions": "rx", "source": "hxe"},
            {"name": "stack", "type": "stack", "start": 0xF000, "end": 0xF1FF, "length": 0x200, "permissions": "rw", "details": {"sp": 0xF140}},
        ],
        "layout": {"code_len": 0x80},
    }
    session = StubSession(
        [make_handshake(["events", "memory"]), {"status": "ok", "memory": memory_block}],
        features=["memory"],
    )
    info = session.memory_regions(7)
    assert info == memory_block
    assert session.supports_memory() is True
    assert session.sent[-1]["cmd"] == "memory"
    assert session.sent[-1]["op"] == "regions"
    assert session.sent[-1]["pid"] == 7
    info["regions"][0]["name"] = "mutated"
    assert memory_block["regions"][0]["name"] == "code"


def test_memory_regions_unknown_marks_unsupported():
    session = StubSession(
        [make_handshake(["events"]), {"status": "error", "error": "unknown_cmd:memory"}],
        features=["memory"],
    )
    result = session.memory_regions(9)
    assert result is None
    assert session.supports_memory() is False


def test_watch_add_remove_list():
    watch_block = {"id": 3, "pid": 5, "expr": "0x200", "type": "address", "address": 0x200, "length": 4, "value": "00112233"}
    session = StubSession(
        [
            make_handshake(["events", "watch"]),
            {"status": "ok", "watch": watch_block},
            {"status": "ok", "watch": {"pid": 5, "count": 1, "watches": [watch_block]}},
            {"status": "ok", "watch": watch_block},
        ],
        features=["watch"],
    )
    added = session.watch_add(5, "0x200", watch_type="address", length=4)
    assert added["id"] == 3
    assert session.supports_watch() is True
    listed = session.watch_list(5)
    assert listed["count"] == 1
    removed = session.watch_remove(5, 3)
    assert removed["id"] == 3
    assert session.sent[-1]["cmd"] == "watch"
    assert session.sent[-1]["op"] == "remove"
    assert session.sent[-1]["id"] == 3


def test_watch_unknown_marks_unsupported():
    session = StubSession(
        [make_handshake(["events"]), {"status": "error", "error": "unknown_cmd:watch"}],
        features=["watch"],
    )
    result = session.watch_list(2)
    assert result is None
    assert session.supports_watch() is False


def test_request_retries_after_connection_loss():
    session = StubSession(
        [
            make_handshake(["events"]),
            ConnectionLostError("transport error"),
            make_handshake(["events"]),
            {"status": "ok", "result": {"ok": True}},
        ],
        features=["events"],
    )
    response = session.request({"cmd": "ps"})
    assert response["status"] == "ok"
    handshake_calls = [entry for entry in session.sent if entry.get("cmd") == "session.open"]
    assert len(handshake_calls) == 2


def test_protocol_version_mismatch_raises():
    session = StubSession([
        {"status": "error", "error": "protocol version mismatch"}
    ], features=["events"])
    with pytest.raises(ProtocolVersionError):
        session.request({"cmd": "ps"})


def test_start_event_stream_establishes_once():
    handshake = make_handshake(["events"])
    stream_started = threading.Event()

    class EventSession(StubSession):
        def __init__(self):
            super().__init__([handshake], features=["events"])
            self.open_calls = 0
            self.stream_filters = None
            self.stream_ack_interval = None

        def _open_event_stream(self, filters, ack_interval):
            self.open_calls += 1
            self.stream_filters = filters
            self.stream_ack_interval = ack_interval
            thread = threading.Thread(target=stream_started.set, daemon=True)
            return _EventStream(
                sock=None,
                rfile=None,
                stop_event=threading.Event(),
                thread=thread,
                token="tok",
            )

    session = EventSession()
    assert session.start_event_stream(filters={"categories": ["scheduler"]}, ack_interval=5) is True
    assert stream_started.wait(0.5)
    assert session.open_calls == 1
    assert session.stream_filters == {"categories": ["scheduler"]}
    assert session.stream_ack_interval == 5
    assert len(session.sent) == 1
    assert session.sent[0]["cmd"] == "session.open"
    assert session.start_event_stream() is True
    assert session.open_calls == 1
