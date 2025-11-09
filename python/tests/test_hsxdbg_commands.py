from types import SimpleNamespace
from unittest.mock import MagicMock

from python.hsxdbg import CommandClient


def _make_session():
    session = MagicMock()
    session.state = SimpleNamespace(session_id="sess-1", pid=None)
    session.runtime_cache = None
    session.transport.send_request = MagicMock()
    session.reopen = MagicMock()
    session.open = MagicMock()
    session.close = MagicMock()
    return session


def test_request_retries_after_session_required():
    session = _make_session()
    session.transport.send_request.side_effect = [
        {"status": "error", "error": "session_required"},
        {"status": "ok", "pong": True},
    ]
    client = CommandClient(session=session)

    result = client._request({"cmd": "ping"})

    assert result["status"] == "ok"
    assert result["pong"] is True
    session.reopen.assert_called_once()
    assert session.transport.send_request.call_count == 2


def test_load_symbols_includes_path_when_provided():
    session = _make_session()
    session.transport.send_request.return_value = {"status": "ok", "symbols": {"loaded": True}}
    client = CommandClient(session=session)

    result = client.load_symbols(pid=7, path="/tmp/test.sym")

    assert result == {"loaded": True}
    payload = session.transport.send_request.call_args[0][0]
    assert payload["cmd"] == "sym"
    assert payload["op"] == "load"
    assert payload["pid"] == 7
    assert payload["path"] == "/tmp/test.sym"
