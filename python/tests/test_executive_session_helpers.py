import pytest

from python.executive_session import ExecutiveSession, ExecutiveSessionError


class StubSession(ExecutiveSession):
    def __init__(self, responses, *, features=None):
        super().__init__("127.0.0.1", 9998, client_name="test", features=features or ["stack"])
        self._responses = list(responses)
        self.sent = []

    def _send_raw(self, payload):
        self.sent.append(payload)
        if not self._responses:
            raise AssertionError("no response queued")
        return self._responses.pop(0)


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
