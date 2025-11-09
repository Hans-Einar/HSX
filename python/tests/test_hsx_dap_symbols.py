from types import SimpleNamespace

from python.hsx_dap import HSXDebugAdapter


class DummyProtocol:
    def send_event(self, *args, **kwargs):
        pass

    def send_response(self, *args, **kwargs):
        pass

    def read_message(self):
        return None


def test_symbol_loader_skips_load_when_no_hint():
    adapter = HSXDebugAdapter(DummyProtocol())
    adapter.current_pid = 1

    calls = {"load": 0}

    def symbol_info(pid):
        return {"loaded": False}

    def load_symbols(pid, path=None):
        calls["load"] += 1
        raise AssertionError("load_symbols should not be called without hint")

    adapter.client = SimpleNamespace(symbol_info=symbol_info, load_symbols=load_symbols)

    adapter._ensure_symbol_mapper(force=True)

    assert calls["load"] == 0
