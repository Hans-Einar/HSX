import pytest

from python.mailbox import MailboxError, MailboxManager


def test_send_and_recv_fail_after_handle_closed():
    mgr = MailboxManager()
    handle = mgr.open(pid=1, target="svc:stdio.out")

    mgr.close(pid=1, handle=handle)

    with pytest.raises(MailboxError, match="invalid handle"):
        mgr.send(pid=1, handle=handle, payload=b"msg")

    with pytest.raises(MailboxError, match="invalid handle"):
        mgr.recv(pid=1, handle=handle)

    # Reopening allocates a fresh handle for the PID.
    new_handle = mgr.open(pid=1, target="svc:stdio.out")
    assert new_handle != handle
