from types import SimpleNamespace

from python.hsx_dap import HSXDebugAdapter


class DummyProtocol:
    def send_event(self, *args, **kwargs):
        pass

    def send_response(self, *args, **kwargs):
        pass

    def read_message(self):
        return None


class FakeMapper:
    def __init__(self):
        self.locals = {"main": [{"name": "counter", "locations": [{"location": {"kind": "stack", "offset": -8}}]}]}
        self.globals = [{"name": "g_flag", "address": 0x200}]

    def locals_for_function(self, func):
        return list(self.locals.get(func, []))

    def globals_list(self):
        return list(self.globals)


def _make_adapter():
    adapter = HSXDebugAdapter(DummyProtocol())
    adapter.current_pid = 1
    adapter.client = SimpleNamespace(
        get_register_state=lambda pid: None,
        list_watches=lambda pid, refresh=False: [],
        read_memory=lambda addr, size, pid=None: b"\x00" * size,
    )
    adapter._symbol_mapper = FakeMapper()
    return adapter


def test_scopes_include_locals_and_globals():
    adapter = _make_adapter()
    adapter._frames[1] = SimpleNamespace(pid=1, name="main", line=0, column=1, file=None, pc=None, sp=0x2000, fp=0x2004)

    result = adapter._handle_scopes({"frameId": 1})

    names = [scope["name"] for scope in result["scopes"]]
    assert "Locals" in names
    assert "Globals" in names
