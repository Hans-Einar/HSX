from platforms.python.host_vm import VMController
from python import hsx_mailbox_constants as mbx_const


def test_zero_length_stdout_write_produces_no_message():
    controller = VMController()
    mgr = controller.mailboxes
    pid = 1
    mgr.register_task(pid)
    handle = mgr.open(pid=pid, target="svc:stdio.out")

    ok, descriptor_id = mgr.send(pid=pid, handle=handle, payload=b"", flags=mbx_const.HSX_MBX_FLAG_STDOUT)
    assert ok
    desc = mgr.descriptor_by_id(descriptor_id)
    assert not desc.queue

    host_handle = controller.mailbox_open(0, f"svc:stdio.out@{pid}")
    resp = controller.mailbox_recv(0, host_handle["handle"], max_len=32)
    assert resp["mbx_status"] == mbx_const.HSX_MBX_STATUS_NO_DATA


def test_stdout_payload_preserves_embedded_null_bytes():
    controller = VMController()
    mgr = controller.mailboxes
    pid = 2
    mgr.register_task(pid)
    handle = mgr.open(pid=pid, target="svc:stdio.out")

    payload = b"abc\x00def"
    ok, descriptor_id = mgr.send(pid=pid, handle=handle, payload=payload, flags=mbx_const.HSX_MBX_FLAG_STDOUT)
    assert ok
    desc = mgr.descriptor_by_id(descriptor_id)
    assert desc.queue

    host_handle = controller.mailbox_open(0, f"svc:stdio.out@{pid}")
    resp = controller.mailbox_recv(0, host_handle["handle"], max_len=64)
    assert resp["mbx_status"] == mbx_const.HSX_MBX_STATUS_OK
    assert resp["length"] == len(payload)
    assert resp["data_hex"] == payload.hex()
    assert resp["text"] == "abc\x00def"
