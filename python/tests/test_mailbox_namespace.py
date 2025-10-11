from python.mailbox import MailboxManager


def test_app_namespace_is_global_and_stdio_is_per_pid():
    mgr = MailboxManager()
    pid_a = 10
    pid_b = 11
    mgr.register_task(pid_a)
    mgr.register_task(pid_b)

    app_handle = mgr.open(pid=pid_a, target="app:demo")
    payload = b"hello"
    ok, descriptor_id = mgr.send(pid=pid_a, handle=app_handle, payload=payload, flags=0)
    assert ok

    host_handle = mgr.open(pid=0, target="app:demo")
    msg = mgr.recv(pid=0, handle=host_handle)
    assert msg is not None
    assert msg.payload == payload

    global_stdout = mgr.open(pid=0, target="svc:stdio.out")
    pid_stdout = mgr.open(pid=0, target=f"svc:stdio.out@{pid_a}")

    global_desc = mgr.descriptor_for_handle(0, global_stdout)
    pid_desc = mgr.descriptor_for_handle(0, pid_stdout)

    assert global_desc.descriptor_id != pid_desc.descriptor_id
