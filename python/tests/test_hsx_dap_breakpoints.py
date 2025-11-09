from python.hsx_dap import HSXDebugAdapter


class DummyProtocol:
    def __init__(self):
        self.events = []

    def send_event(self, event, body):
        self.events.append((event, body))

    def send_response(self, *args, **kwargs):
        pass

    def read_message(self):
        return None


class DummyClient:
    def __init__(self):
        self.breaks = []

    def set_breakpoint(self, addr, pid=None):
        self.breaks.append(addr)


def _make_adapter():
    protocol = DummyProtocol()
    adapter = HSXDebugAdapter(protocol)
    adapter.current_pid = 1
    return adapter, protocol


def test_pending_breakpoints_reapplied_on_connect():
    adapter, protocol = _make_adapter()
    source = {"path": "/tmp/foo.c"}
    breakpoints = [{"line": 10}]
    adapter._symbol_mapper = None

    result = adapter._handle_setBreakpoints({"source": source, "breakpoints": breakpoints})

    assert result["breakpoints"][0]["verified"] is False
    adapter.client = DummyClient()
    adapter._symbol_mapper = type("Mapper", (), {"lookup": lambda self, path, line: [0x10]})()
    adapter._reapply_pending_breakpoints()
    assert adapter.client.breaks == [0x10]
    assert protocol.events[0][0] == "breakpoint"


def test_breakpoint_lookup_falls_back_to_basename():
    adapter, _ = _make_adapter()

    class Mapper:
        def lookup(self, path, line):
            if path == "main.c" and line == 5:
                return [0x40]
            return []

    adapter._symbol_mapper = Mapper()
    adapter.client = DummyClient()
    adapter._handle_setBreakpoints({"source": {"path": "/work/src/main.c"}, "breakpoints": [{"line": 5}]})
    assert adapter.client.breaks == [0x40]
