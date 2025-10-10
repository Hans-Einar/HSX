from python.mailbox import MailboxManager, MailboxError
from python import hsx_mailbox_constants as mbx_const


def test_bind_creates_descriptor():
    mgr = MailboxManager()
    desc = mgr.bind(namespace=1, name="stdio")
    snapshot = mgr.descriptor_snapshot()
    assert snapshot[0]["name"] == "stdio"
    assert snapshot[0]["capacity"] > 0
    assert mgr.bind(namespace=1, name="stdio").descriptor_id == desc.descriptor_id


def test_register_task_creates_stdio_mailboxes():
    mgr = MailboxManager()
    mgr.register_task(7)
    names = {(item["name"], item["owner_pid"]) for item in mgr.descriptor_snapshot()}
    assert ("stdio.out", 7) in names
    assert ("pid:7", 7) in names


def test_open_assigns_handle_per_pid():
    mgr = MailboxManager()
    h1 = mgr.open(pid=1, target="svc:stdio.out")
    h2 = mgr.open(pid=1, target="svc:stdio.err")
    h3 = mgr.open(pid=2, target="pid:2")
    assert h1 == 1
    assert h2 == 2
    assert h3 == 1  # handles are per-pid


def test_send_and_recv_roundtrip():
    mgr = MailboxManager()
    handle = mgr.open(pid=1, target="svc:stdio.out")
    ok, _ = mgr.send(pid=1, handle=handle, payload=b"hello", flags=0x1)
    assert ok is True
    message = mgr.recv(pid=1, handle=handle)
    assert message is not None
    assert message.payload == b"hello"
    assert message.flags == 0x1


def test_send_raises_when_message_exceeds_capacity():
    mgr = MailboxManager()
    mgr.bind_target(pid=1, target="svc:small", capacity=16)
    handle = mgr.open(pid=1, target="svc:small")
    try:
        mgr.send(pid=1, handle=handle, payload=b"123456789012", flags=0)
    except MailboxError:
        pass
    else:
        raise AssertionError("expected MailboxError for oversize message")


def test_close_unknown_handle_raises():
    mgr = MailboxManager()
    mgr.open(pid=1, target="svc:stdio")
    try:
        mgr.close(pid=1, handle=99)
    except MailboxError:
        pass
    else:
        raise AssertionError("expected failure for invalid handle")

def test_recv_records_waiter():
    mgr = MailboxManager()
    handle = mgr.open(pid=1, target="svc:stdio.out")
    msg = mgr.recv(pid=1, handle=handle)
    assert msg is None
    snapshot = mgr.descriptor_snapshot()
    waiter_lists = [entry["waiters"] for entry in snapshot if entry["name"] == "stdio.out"]
    assert waiter_lists and 1 in waiter_lists[0]


def test_fanout_delivery_to_multiple_handles():
    mgr = MailboxManager()
    desc = mgr.bind(
        namespace=mbx_const.HSX_MBX_NAMESPACE_SHARED,
        name="fan",
        capacity=32,
        mode_mask=(
            mbx_const.HSX_MBX_MODE_RDWR
            | mbx_const.HSX_MBX_MODE_FANOUT
            | mbx_const.HSX_MBX_MODE_FANOUT_DROP
        ),
    )
    producer = mgr.open(pid=1, target="shared:fan")
    handle_a = mgr.open(pid=2, target="shared:fan")
    handle_b = mgr.open(pid=3, target="shared:fan")

    ok, _ = mgr.send(pid=1, handle=producer, payload=b"alpha")
    assert ok is True

    msg_a = mgr.recv(pid=2, handle=handle_a)
    msg_b = mgr.recv(pid=3, handle=handle_b)
    assert msg_a is not None and msg_a.payload == b"alpha"
    assert msg_b is not None and msg_b.payload == b"alpha"
    assert not (msg_a.flags & mbx_const.HSX_MBX_FLAG_OVERRUN)
    assert not (msg_b.flags & mbx_const.HSX_MBX_FLAG_OVERRUN)

    # Queue should be empty after all subscribers have consumed the frame.
    snapshot = mgr.descriptor_snapshot()
    entry = next(item for item in snapshot if item["descriptor_id"] == desc.descriptor_id)
    assert entry["queue_depth"] == 0
    assert entry["bytes_used"] == 0


def test_fanout_drop_policy_sets_overrun_flag():
    mgr = MailboxManager()
    mgr.bind(
        namespace=mbx_const.HSX_MBX_NAMESPACE_SHARED,
        name="fan_drop",
        capacity=16,
        mode_mask=(
            mbx_const.HSX_MBX_MODE_RDWR
            | mbx_const.HSX_MBX_MODE_FANOUT
            | mbx_const.HSX_MBX_MODE_FANOUT_DROP
        ),
    )
    producer = mgr.open(pid=1, target="shared:fan_drop")
    consumer = mgr.open(pid=2, target="shared:fan_drop")

    ok, _ = mgr.send(pid=1, handle=producer, payload=b"first")
    assert ok

    ok, _ = mgr.send(pid=1, handle=producer, payload=b"second")
    assert ok

    msg = mgr.recv(pid=2, handle=consumer)
    assert msg is not None
    assert msg.payload == b"second"
    assert msg.flags & mbx_const.HSX_MBX_FLAG_OVERRUN


def test_fanout_block_policy_prevents_overfill():
    mgr = MailboxManager()
    mgr.bind(
        namespace=mbx_const.HSX_MBX_NAMESPACE_SHARED,
        name="fan_block",
        capacity=16,
        mode_mask=(
            mbx_const.HSX_MBX_MODE_RDWR
            | mbx_const.HSX_MBX_MODE_FANOUT
            | mbx_const.HSX_MBX_MODE_FANOUT_BLOCK
        ),
    )
    producer = mgr.open(pid=1, target="shared:fan_block")
    consumer = mgr.open(pid=2, target="shared:fan_block")

    ok, _ = mgr.send(pid=1, handle=producer, payload=b"first")
    assert ok

    ok, _ = mgr.send(pid=1, handle=producer, payload=b"second")
    assert ok is False

    msg = mgr.recv(pid=2, handle=consumer)
    assert msg is not None and msg.payload == b"first"
    assert not (msg.flags & mbx_const.HSX_MBX_FLAG_OVERRUN)

    ok, _ = mgr.send(pid=1, handle=producer, payload=b"third")
    assert ok is True


def test_set_default_stdio_mode_updates_existing():
    mgr = MailboxManager()
    mgr.register_task(5)
    updated = mgr.set_default_stdio_mode("out", mbx_const.HSX_MBX_MODE_RDWR | mbx_const.HSX_MBX_MODE_FANOUT, update_existing=True)
    assert updated  # default stdout descriptors updated
    handle = mgr.open(pid=99, target="svc:stdio.out@5")
    state_info = mgr.peek(pid=99, handle=handle)
    assert state_info["mode_mask"] & mbx_const.HSX_MBX_MODE_FANOUT
