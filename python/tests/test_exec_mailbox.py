import pytest

from python.execd import ExecutiveState
from python import hsx_mailbox_constants as mbx_const


class FakeVM:
    def __init__(self) -> None:
        self.calls = []
        self._recv_calls = 0

    # Mailbox RPC facades -------------------------------------------------
    def mailbox_snapshot(self):
        return {
            "descriptors": [
                {
                    "name": "stdio.out",
                    "owner_pid": 5,
                    "queue_depth": 0,
                    "bytes_used": 0,
                    "mode_mask": 0,
                }
            ],
            "stats": {
                "max_descriptors": 16,
                "active_descriptors": 1,
                "free_descriptors": 15,
                "bytes_used": 0,
                "bytes_available": 0,
                "queue_depth": 0,
                "handles_total": 0,
                "handles_per_pid": {},
            },
        }

    def mailbox_open(self, pid, target, flags=0):
        self.calls.append(("open", pid, target, flags))
        return {"status": "ok", "handle": 1}

    def mailbox_close(self, pid, handle):
        self.calls.append(("close", pid, handle))
        return {"status": "ok"}

    def mailbox_recv(self, pid, handle, *, max_len=512, timeout=0):
        self.calls.append(("recv", pid, handle, max_len, timeout))
        if self._recv_calls == 0:
            self._recv_calls += 1
            return {
                "status": "ok",
                "mbx_status": mbx_const.HSX_MBX_STATUS_OK,
                "length": 5,
                "flags": 0,
                "channel": 0,
                "src_pid": 5,
                "data_hex": "68656c6c6f",
                "text": "hello",
            }
        return {
            "status": "ok",
            "mbx_status": mbx_const.HSX_MBX_STATUS_NO_DATA,
            "length": 0,
        }

    def mailbox_send(self, pid, handle, *, data=None, data_hex=None, flags=0, channel=0):
        self.calls.append(("send", pid, handle, data, data_hex, flags, channel))
        payload = data_hex if data_hex is not None else (data or "")
        length = len(payload if isinstance(payload, str) else str(payload))
        return {
            "status": "ok",
            "mbx_status": mbx_const.HSX_MBX_STATUS_OK,
            "length": length,
        }


def test_listen_stdout_returns_message():
    fake = FakeVM()
    state = ExecutiveState(fake)

    result = state.listen_stdout(pid=5, limit=2, max_len=16)

    assert result["messages"]
    msg = result["messages"][0]
    assert msg["text"] == "hello"
    assert msg["target"] == "svc:stdio.out@5"
    assert any(call[0] == "open" for call in fake.calls)
    assert any(call[0] == "close" for call in fake.calls)


def test_send_stdin_produces_target_and_calls_send():
    fake = FakeVM()
    state = ExecutiveState(fake)

    resp = state.send_stdin(7, data="hi")

    assert resp["target"] == "svc:stdio.in@7"
    assert any(call[0] == "send" and call[1] == 0 for call in fake.calls)


def test_send_stdin_requires_data():
    fake = FakeVM()
    state = ExecutiveState(fake)

    with pytest.raises(ValueError):
        state.send_stdin(1)
