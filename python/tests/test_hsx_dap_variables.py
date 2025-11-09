from types import SimpleNamespace

from python.hsx_dap import HSXDebugAdapter


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


def test_local_scope_formats_stack_variable():
    adapter = _make_adapter(FakeMapperLocals())
    scopes = adapter._handle_scopes({"frameId": 1})["scopes"]
    locals_scope = next(scope for scope in scopes if scope["name"] == "Locals")
    variables = adapter._scopes[locals_scope["variablesReference"]].variables
    assert "counter" in variables[0]["name"]
    assert "0x" in variables[0]["value"]
