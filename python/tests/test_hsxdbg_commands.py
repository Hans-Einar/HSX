from python.hsxdbg.cache import RuntimeCache
from python.hsxdbg.commands import CommandClient
from python.hsxdbg.session import SessionState


class DummyTransport:
    def set_event_handler(self, handler):
        self.handler = handler

    def send_request(self, payload):
        return {"status": "ok"}


class DummySession:
    def __init__(self):
        self.transport = DummyTransport()
        self.state = SessionState(session_id="sess-1", pid=1)
        self.runtime_cache = RuntimeCache()
        self.runtime_cache.update_registers(1, {"R0": 1, "PC": 0x10})
        self.runtime_cache.update_call_stack(1, [{"pc": 0x10}])


def test_command_client_invalidates_cache_on_step():
    session = DummySession()
    client = CommandClient(session=session)
    client._request = lambda payload: {"status": "ok"}  # type: ignore[attr-defined]
    assert session.runtime_cache.get_registers(1) is not None
    client.step()
    assert session.runtime_cache.get_registers(1) is None
    assert session.runtime_cache.get_call_stack(1) == []


def test_command_client_uses_explicit_cache():
    session = DummySession()
    external_cache = RuntimeCache()
    external_cache.update_registers(1, {"R0": 2})
    client = CommandClient(session=session, cache=external_cache)
    client._request = lambda payload: {"status": "ok"}  # type: ignore[attr-defined]
    client.pause()
    assert external_cache.get_registers(1) is None


def test_get_register_state_refreshes_cache():
    session = DummySession()
    client = CommandClient(session=session)
    calls = []

    def fake_request(payload):
        calls.append(payload)
        return {"status": "ok", "registers": {"R0": 9, "PC": 0x40}}

    client._request = fake_request  # type: ignore[attr-defined]
    state = client.get_register_state(refresh=True)
    assert state is not None
    assert state.registers["R0"] == 9
    assert state.pc == 0x40
    assert calls and calls[0]["cmd"] == "dumpregs"


def test_read_memory_uses_peek_and_cache():
    session = DummySession()
    client = CommandClient(session=session)
    calls = []

    def fake_request(payload):
        calls.append(payload)
        return {"status": "ok", "data": "01020304"}

    client._request = fake_request  # type: ignore[attr-defined]
    data1 = client.read_memory(0x100, 2)
    data2 = client.read_memory(0x100, 2)
    assert data1 == b"\x01\x02"
    assert data2 == b"\x01\x02"
    assert len(calls) == 1


def test_list_watches_uses_cache_when_not_refreshing():
    session = DummySession()
    client = CommandClient(session=session)

    def first_request(payload):
        return {"status": "ok", "watch": {"entries": [{"id": 3, "expr": "foo", "length": 4, "value": "0000"}]}}

    client._request = first_request  # type: ignore[attr-defined]
    watches = client.list_watches(refresh=True)
    assert len(watches) == 1

    def second_request(payload):
        raise AssertionError("should not be called")

    client._request = second_request  # type: ignore[attr-defined]
    watches_cached = client.list_watches()
    assert watches_cached[0].watch_id == 3
