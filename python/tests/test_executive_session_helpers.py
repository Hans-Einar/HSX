from python.executive_session import ExecutiveSession


class StubSession(ExecutiveSession):
    def __init__(self, responses):
        super().__init__("127.0.0.1", 9998, client_name="test", features=["stack"])
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
