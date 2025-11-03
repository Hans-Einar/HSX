from python import hsx_mailbox_constants as mbx_const
from python.mailbox import MailboxManager


def test_mailbox_manager_handles_bulk_descriptor_creation():
    mgr = MailboxManager(max_descriptors=256, per_pid_handle_limit=128)

    descriptor_targets = []
    for pid in range(1, 9):
        mgr.register_task(pid)
        mgr.ensure_stdio_handles(pid)
        for idx in range(8):
            target = f"app:stress.{pid}.{idx}"
            descriptor_targets.append(target)
            desc = mgr.bind_target(pid=pid, target=target, capacity=64)
            assert desc.capacity == 64
            handle = mgr.open(pid=pid, target=target)
            assert handle > 0
            ok, descriptor_id = mgr.send(
                pid=pid,
                handle=handle,
                payload=f"msg-{pid}-{idx}".encode("ascii"),
                flags=0,
            )
            assert ok is True
            assert descriptor_id == desc.descriptor_id

    stats = mgr.resource_stats()
    assert stats["active_descriptors"] >= len(descriptor_targets)
    assert stats["handles_total"] >= len(descriptor_targets)
    assert stats["queue_depth"] >= len(descriptor_targets)
    # No descriptor exhaustion should have occurred.
    assert not stats["descriptor_pool_exhausted"]

    # Drain messages and ensure they round-trip without error.
    for pid in range(1, 9):
        for idx in range(8):
            target = f"app:stress.{pid}.{idx}"
            handle = mgr.open(pid=pid, target=target)
            msg = mgr.recv(pid=pid, handle=handle, record_waiter=False)
            assert msg is not None
            assert msg.payload.decode("ascii") == f"msg-{pid}-{idx}"


def test_mailbox_manager_interleaves_multi_pid_fanout():
    mgr = MailboxManager()
    producer_pid = 1
    consumer_pids = (2, 3, 4)

    mgr.register_task(producer_pid)
    for pid in consumer_pids:
        mgr.register_task(pid)

    desc = mgr.bind(
        namespace=mbx_const.HSX_MBX_NAMESPACE_SHARED,
        name="stress_bus",
        capacity=128,
        mode_mask=mbx_const.HSX_MBX_MODE_RDWR
        | mbx_const.HSX_MBX_MODE_FANOUT,
    )
    producer_handle = mgr.open(pid=producer_pid, target="shared:stress_bus")
    consumer_handles = {
        pid: mgr.open(pid=pid, target="shared:stress_bus") for pid in consumer_pids
    }

    payloads = [f"packet-{i}".encode("ascii") for i in range(32)]
    for payload in payloads:
        ok, descriptor_id = mgr.send(
            pid=producer_pid, handle=producer_handle, payload=payload, flags=0
        )
        assert ok is True
        assert descriptor_id == desc.descriptor_id

        for pid in consumer_pids:
            handle = consumer_handles[pid]
            msg = mgr.recv(pid=pid, handle=handle, record_waiter=False)
            assert msg is not None, f"expected payload for pid {pid}"
            assert msg.payload == payload
    # After draining alongside each send, queues should be empty.

    stats = mgr.resource_stats()
    assert stats["fanout_descriptors"] >= 1
    assert stats["queue_depth"] == 0
