from types import SimpleNamespace

from python.hsx_dap import HSXDebugAdapter
from python.hsxdbg.cache import RegisterState


class DummyProtocol:
    def send_event(self, *args, **kwargs):
        pass

    def send_response(self, *args, **kwargs):
        pass

    def read_message(self):
        return None


def _make_adapter():
    adapter = HSXDebugAdapter(DummyProtocol())
    adapter.current_pid = 1
    return adapter


def test_watch_register_expression_returns_register_value():
    adapter = _make_adapter()
    state = RegisterState(registers={"R0": 0xA}, pc=0, sp=0, psw=0)
    adapter.client = SimpleNamespace(
        get_register_state=lambda pid: state,
        symbol_lookup_name=lambda name, pid=None: None,
        add_watch=lambda expr, pid=None: {"watch_id": 1},
        list_watches=lambda pid, refresh=False: [],
    )

    result = adapter._handle_evaluate({"context": "watch", "expression": "R0"})

    assert result["result"] == "0x0000000A"


def test_watch_local_symbol_reports_not_supported():
    adapter = _make_adapter()
    called = {"add": 0}

    def fake_add_watch(expr, pid=None):
        called["add"] += 1
        return {"watch_id": 1}

    adapter.client = SimpleNamespace(
        get_register_state=lambda pid: None,
        symbol_lookup_name=lambda name, pid=None: {
            "name": name,
            "locations": [{"location": {"kind": "stack", "offset": -4}}],
        },
        add_watch=fake_add_watch,
        list_watches=lambda pid, refresh=False: [],
    )

    result = adapter._handle_evaluate({"context": "watch", "expression": "counter"})

    assert "local/stack variable" in result["result"]
    assert called["add"] == 0
