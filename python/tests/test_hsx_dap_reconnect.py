from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
PYTHON_SRC = REPO_ROOT / "python"
for entry in (REPO_ROOT, PYTHON_SRC):
    if str(entry) not in sys.path:
        sys.path.append(str(entry))

from hsx_dap import HSXDebugAdapter
from hsx_dbg import DebuggerBackendError


class _DummyProtocol:
    def send_event(self, *_, **__):
        pass

    def send_response(self, *_, **__):
        pass


def _make_backend_error(message: str, cause: Exception | None = None) -> DebuggerBackendError:
    try:
        if cause is not None:
            raise DebuggerBackendError(message) from cause
        raise DebuggerBackendError(message)
    except DebuggerBackendError as exc:  # pragma: no cover - helper
        return exc


def _make_adapter() -> HSXDebugAdapter:
    return HSXDebugAdapter(_DummyProtocol())


def test_should_not_reconnect_for_pid_validation_errors():
    adapter = _make_adapter()
    exc = _make_backend_error("watch add failed: watch requires 'pid'")
    assert adapter._should_attempt_reconnect(exc) is False


def test_should_not_reconnect_for_disassemble_validation_errors():
    adapter = _make_adapter()
    exc = _make_backend_error("disasm requires 'pid'")
    assert adapter._should_attempt_reconnect(exc) is False


def test_should_reconnect_for_transport_errors():
    adapter = _make_adapter()
    exc = _make_backend_error("transport error: connection reset")
    assert adapter._should_attempt_reconnect(exc) is True


def test_should_reconnect_when_underlying_cause_is_timeout():
    adapter = _make_adapter()
    exc = _make_backend_error("request failed", TimeoutError("timed out"))
    assert adapter._should_attempt_reconnect(exc) is True
