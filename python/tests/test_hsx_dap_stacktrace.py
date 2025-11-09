from types import SimpleNamespace

from python.hsx_dap import HSXDebugAdapter


class DummyProtocol:
    def send_event(self, *args, **kwargs):
        pass

    def send_response(self, *args, **kwargs):
        pass

    def read_message(self):
        return None


class FakeSymbolMapper:
    def __init__(self):
        self._pc_map = {0x10: {"file": "foo.c", "directory": "/tmp", "line": 42}}

    def lookup_pc(self, pc):
        return self._pc_map.get(pc)


def test_stacktrace_maps_pc_to_source_when_missing():
    adapter = HSXDebugAdapter(DummyProtocol())
    adapter.current_pid = 1
    adapter._symbol_mapper = FakeSymbolMapper()
    frame = SimpleNamespace(index=0, func_name="main", symbol=None, line=None, file=None, pc=0x10, sp=0, fp=0)
    adapter.client = SimpleNamespace(get_call_stack=lambda pid, max_frames=None: [frame])

    result = adapter._handle_stackTrace({})

    frame_out = result["stackFrames"][0]
    assert frame_out["line"] == 42
    assert frame_out["source"]["path"].endswith("foo.c")
