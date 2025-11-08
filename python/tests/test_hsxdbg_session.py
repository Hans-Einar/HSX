from python.hsxdbg.cache import RuntimeCache
from python.hsxdbg.events import EventBus
from python.hsxdbg.session import SessionConfig, SessionManager, SessionState


class DummyTransport:
    def __init__(self):
        self.handler = None

    def set_event_handler(self, handler):
        self.handler = handler

    def send_request(self, payload):
        if payload.get("cmd") == "session.open":
            return {
                "status": "ok",
                "session": {
                    "id": "sess-1",
                    "client": "test",
                    "features": [],
                    "max_events": 128,
                },
            }
        return {"status": "ok"}


def test_session_manager_attaches_cache_controller_with_bus():
    transport = DummyTransport()
    cache = RuntimeCache()
    bus = EventBus()
    session = SessionManager(
        transport=transport,
        session_config=SessionConfig(client_name="test"),
        event_bus=bus,
        runtime_cache=cache,
    )
    assert getattr(session, "_cache_controller") is not None
    bus.publish(
        {
            "seq": 1,
            "ts": 0.0,
            "type": "trace_step",
            "pid": 1,
            "data": {"pc": 0x20, "regs": [1, 2]},
        }
    )
    bus.pump()
    assert cache.get_registers(1).pc == 0x20
