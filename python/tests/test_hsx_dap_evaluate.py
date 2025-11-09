from types import SimpleNamespace

from python.hsx_dap import HSXDebugAdapter, _FrameRecord
from python.hsxdbg.cache import RegisterState


class DummyProtocol:
    def send_event(self, *args, **kwargs):
        pass

    def send_response(self, *args, **kwargs):
        pass

    def read_message(self):
        return None


class MapperStub:
    def __init__(self, *, globals_list=None, locals_map=None):
        self._globals = globals_list or []
        self._locals = locals_map or {}

    def globals_list(self):
        return list(self._globals)

    def locals_for_function(self, func):
        return list(self._locals.get(func, []))

    def lookup(self, source_path, line):
        return []

    def lookup_pc(self, pc):
        return None


def _register_state():
    return RegisterState(registers={"R0": 0xA}, pc=0x40, sp=0x2000, psw=0)


def test_evaluate_hover_register_returns_register_value():
    adapter = HSXDebugAdapter(DummyProtocol())
    adapter.current_pid = 1
    state = _register_state()
    adapter.client = SimpleNamespace(
        get_register_state=lambda pid: state,
        read_memory=lambda addr, length, pid=None: None,
        list_watches=lambda pid, refresh=False: [],
        symbol_info=lambda pid: {"loaded": False},
    )

    result = adapter._handle_evaluate({"context": "hover", "expression": "pc"})

    assert result["result"] == "0x00000040"
    assert result["type"] == "register"


def test_evaluate_pointer_expression_reads_memory():
    adapter = HSXDebugAdapter(DummyProtocol())
    adapter.current_pid = 1
    state = _register_state()

    def fake_read(address, length, pid=None):
        value = (address & ((1 << (length * 8)) - 1))
        return value.to_bytes(length, "big")

    adapter.client = SimpleNamespace(
        get_register_state=lambda pid: state,
        read_memory=fake_read,
        list_watches=lambda pid, refresh=False: [],
        symbol_info=lambda pid: {"loaded": False},
    )

    result = adapter._handle_evaluate({"context": "hover", "expression": "@0x10"})

    assert "@ 0x00000010" in result["result"]
    assert result["type"] == "memory"


def test_evaluate_global_symbol_uses_symbol_mapper():
    adapter = HSXDebugAdapter(DummyProtocol())
    adapter.current_pid = 1
    adapter._symbol_mapper = MapperStub(globals_list=[{"name": "g_flag", "address": 0x1000, "size": 4}])

    adapter.client = SimpleNamespace(
        get_register_state=lambda pid: _register_state(),
        read_memory=lambda addr, length, pid=None: (0x7B).to_bytes(length, "big"),
        list_watches=lambda pid, refresh=False: [],
        symbol_info=lambda pid: {"loaded": True, "path": "dummy"},
    )

    result = adapter._handle_evaluate({"context": "hover", "expression": "g_flag"})

    assert "0x0000007B" in result["result"]
    assert result["type"] == "symbol"


def test_watch_context_local_symbol_returns_value_without_watch_registration():
    adapter = HSXDebugAdapter(DummyProtocol())
    adapter.current_pid = 1
    locals_map = {
        "main": [
            {
                "name": "counter",
                "locations": [{"location": {"kind": "stack", "offset": -4}}],
                "size": 2,
            }
        ]
    }
    adapter._symbol_mapper = MapperStub(locals_map=locals_map)
    frame = _FrameRecord(pid=1, name="main", line=0, column=1, file=None, pc=None, sp=0x2000, fp=0x2000)
    adapter._frames[5] = frame
    calls = {}

    def fake_read(address, length, pid=None):
        calls["address"] = address
        calls["length"] = length
        return (0x3456).to_bytes(length, "big")

    def fail_watch(*args, **kwargs):
        raise AssertionError("should not register watch for locals")

    adapter.client = SimpleNamespace(
        get_register_state=lambda pid: _register_state(),
        read_memory=fake_read,
        list_watches=lambda pid, refresh=False: [],
        add_watch=fail_watch,
        symbol_info=lambda pid: {"loaded": True, "path": "dummy"},
    )

    result = adapter._handle_evaluate({"context": "watch", "expression": "counter", "frameId": 5})

    assert "0x00003456" in result["result"]
    assert calls["address"] == frame.sp - 4
    assert calls["length"] == 2
