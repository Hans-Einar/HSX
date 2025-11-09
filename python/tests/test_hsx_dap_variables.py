from types import SimpleNamespace

from python.hsx_dap import HSXDebugAdapter, _FrameRecord


class DummyProtocol:
    def send_event(self, *args, **kwargs):
        pass

    def send_response(self, *args, **kwargs):
        pass

    def read_message(self):
        return None


class FakeMapperGlobals:
    def __init__(self):
        self.globals = [{"name": "g_flag", "address": 0x1000, "size": 2}]

    def globals_list(self):
        return list(self.globals)

    def locals_for_function(self, func):
        return []


class FakeMapperLocals(FakeMapperGlobals):
    def __init__(self):
        super().__init__()
        self.locals = {
            "main": [
                {
                    "name": "counter",
                    "locations": [{"location": {"kind": "stack", "offset": -2}}],
                    "length": 2,
                }
            ]
        }

    def locals_for_function(self, func):
        return list(self.locals.get(func, []))


def _make_adapter(mapper):
    adapter = HSXDebugAdapter(DummyProtocol())
    adapter.current_pid = 1
    adapter._symbol_mapper = mapper
    adapter.client = SimpleNamespace(
        get_register_state=lambda pid: None,
        read_memory=lambda addr, size, pid=None: (addr.to_bytes(size, "big") if addr is not None else None),
        list_watches=lambda pid, refresh=False: [],
    )
    adapter._frames[1] = SimpleNamespace(pid=1, name="main", line=0, column=1, file=None, pc=None, sp=0x2000, fp=0x2004)
    return adapter


def test_global_scope_reads_memory():
    adapter = _make_adapter(FakeMapperGlobals())
    scopes = adapter._handle_scopes({"frameId": 1})["scopes"]
    globals_scope = next(scope for scope in scopes if scope["name"] == "Globals")
    variables = adapter._scopes[globals_scope["variablesReference"]].variables
    assert "0x00001000" in variables[0]["value"]
    assert variables[0]["variablesReference"] == 0


def test_local_scope_formats_stack_variable():
    adapter = _make_adapter(FakeMapperLocals())
    scopes = adapter._handle_scopes({"frameId": 1})["scopes"]
    locals_scope = next(scope for scope in scopes if scope["name"] == "Locals")
    variables = adapter._scopes[locals_scope["variablesReference"]].variables
    assert "counter" in variables[0]["name"]
    assert "0x" in variables[0]["value"]
    assert variables[0]["variablesReference"] == 0


def test_local_stack_defaults_to_fp_when_available():
    adapter = HSXDebugAdapter(DummyProtocol())
    adapter.current_pid = 1
    adapter._symbol_mapper = FakeMapperLocals()
    captured = {}

    def fake_read(addr, size, pid=None):
        captured["addr"] = addr
        value = 0x1234 & ((1 << (size * 8)) - 1)
        return value.to_bytes(size, "big")

    adapter.client = SimpleNamespace(
        read_memory=fake_read,
        get_register_state=lambda pid: None,
    )
    frame = _FrameRecord(pid=1, name="main", line=0, column=0, file=None, pc=None, sp=0x1000, fp=0x2000)
    symbol = adapter._symbol_mapper.locals_for_function("main")[0]
    value = adapter._format_symbol_value(symbol, frame)
    assert captured["addr"] == frame.fp - 2
    assert "0x00001234" in value
