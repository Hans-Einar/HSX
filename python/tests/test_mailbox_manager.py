import importlib.util
from pathlib import Path
from typing import Any, Dict, List

import pytest

from python.mailbox import MailboxManager, MailboxError
from python import hsx_mailbox_constants as mbx_const


def _load_hsx_llc():
    root = Path(__file__).resolve().parents[1] / "hsx-llc.py"
    spec = importlib.util.spec_from_file_location("hsx_llc", root)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


HSX_LLC = _load_hsx_llc()


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
    with pytest.raises(MailboxError) as exc:
        mgr.send(pid=1, handle=handle, payload=b"123456789012", flags=0)
    assert exc.value.code == mbx_const.HSX_MBX_STATUS_MSG_TOO_LARGE


def test_close_unknown_handle_raises():
    mgr = MailboxManager()
    mgr.open(pid=1, target="svc:stdio")
    with pytest.raises(MailboxError) as exc:
        mgr.close(pid=1, handle=99)
    assert exc.value.code == mbx_const.HSX_MBX_STATUS_INVALID_HANDLE

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


def test_descriptor_pool_exhaustion_raises_with_status():
    mgr = MailboxManager(max_descriptors=4)
    # Create descriptors up to the limit
    mgr.register_task(1)  # consumes 4 descriptors for pid:1 stdio + control
    assert mgr.descriptor_count == mgr.max_descriptors

    with pytest.raises(MailboxError) as exc:
        mgr.bind_target(pid=1, target="app:overflow")

    assert exc.value.code == mbx_const.HSX_MBX_STATUS_NO_DESCRIPTOR


def test_resource_stats_initial_state():
    mgr = MailboxManager(max_descriptors=32)
    stats = mgr.resource_stats()
    assert stats["max_descriptors"] == 32
    assert stats["active_descriptors"] == 0
    assert stats["handles_total"] == 0
    assert stats["handles_per_pid"] == {}


def test_resource_stats_with_handles_and_messages():
    mgr = MailboxManager(max_descriptors=8)
    mgr.register_task(1)
    handle = mgr.open(pid=1, target="svc:stdio.out")
    ok, _ = mgr.send(pid=1, handle=handle, payload=b"ping")
    assert ok is True
    stats = mgr.resource_stats()
    assert stats["active_descriptors"] >= 1
    assert stats["handles_total"] >= 1
    assert stats["handles_per_pid"].get(1) >= 1
    assert stats["bytes_used"] >= len("ping")
    assert stats["queue_depth"] >= 1



def test_fanout_reclaims_after_all_consumers_ack():
    mgr = MailboxManager()
    desc = mgr.bind(
        namespace=mbx_const.HSX_MBX_NAMESPACE_SHARED,
        name="fan_reclaim",
        capacity=64,
        mode_mask=(
            mbx_const.HSX_MBX_MODE_RDWR
            | mbx_const.HSX_MBX_MODE_FANOUT
            | mbx_const.HSX_MBX_MODE_FANOUT_BLOCK
        ),
    )
    producer = mgr.open(pid=1, target="shared:fan_reclaim")
    consumer_a = mgr.open(pid=2, target="shared:fan_reclaim")
    consumer_b = mgr.open(pid=3, target="shared:fan_reclaim")

    ok, descriptor_id = mgr.send(pid=1, handle=producer, payload=b"data", flags=0)
    assert ok is True
    desc_obj = mgr.descriptor_by_id(descriptor_id)
    assert len(desc_obj.queue) == 1

    msg_a = mgr.recv(pid=2, handle=consumer_a)
    assert msg_a is not None and msg_a.payload == b"data"
    desc_obj = mgr.descriptor_by_id(descriptor_id)
    assert len(desc_obj.queue) == 1

    msg_b = mgr.recv(pid=3, handle=consumer_b)
    assert msg_b is not None and msg_b.payload == b"data"
    desc_obj = mgr.descriptor_by_id(descriptor_id)
    assert len(desc_obj.queue) == 0


def test_fanout_overrun_sets_flag_and_triggers_event():
    events: List[Dict[str, Any]] = []
    mgr = MailboxManager()
    mgr.set_event_hook(events.append)
    desc = mgr.bind(
        namespace=mbx_const.HSX_MBX_NAMESPACE_SHARED,
        name="fan_overrun",
        capacity=16,
        mode_mask=(
            mbx_const.HSX_MBX_MODE_RDWR
            | mbx_const.HSX_MBX_MODE_FANOUT
            | mbx_const.HSX_MBX_MODE_FANOUT_DROP
        ),
    )
    producer = mgr.open(pid=1, target="shared:fan_overrun")
    consumer = mgr.open(pid=2, target="shared:fan_overrun")

    ok, _ = mgr.send(pid=1, handle=producer, payload=b"msg1")
    assert ok is True

    ok, _ = mgr.send(pid=1, handle=producer, payload=b"msg2")
    assert ok is True

    overrun_events = [evt for evt in events if evt.get("type") == "mailbox_overrun"]
    assert overrun_events, "expected mailbox_overrun event"
    event = overrun_events[-1]
    assert event["descriptor"] == desc.descriptor_id

    msg = mgr.recv(pid=2, handle=consumer)
    assert msg is not None
    assert msg.payload == b"msg2"
    assert msg.flags & mbx_const.HSX_MBX_FLAG_OVERRUN


def test_app_namespace_reused_across_pids():
    mgr = MailboxManager()
    consumer_handle = mgr.open(pid=1, target="app:demo")
    producer_handle = mgr.open(pid=2, target="app:demo")

    desc_consumer = mgr.descriptor_for_handle(1, consumer_handle)
    desc_producer = mgr.descriptor_for_handle(2, producer_handle)
    assert desc_consumer.descriptor_id == desc_producer.descriptor_id
    assert desc_consumer.namespace == mbx_const.HSX_MBX_NAMESPACE_APP
    assert desc_consumer.owner_pid is None

    ok, descriptor_id = mgr.send(pid=2, handle=producer_handle, payload=b"ping")
    assert ok is True
    assert descriptor_id == desc_consumer.descriptor_id

    msg = mgr.recv(pid=1, handle=consumer_handle)
    assert msg is not None
    assert msg.payload == b"ping"


def test_set_default_stdio_mode_updates_existing():
    mgr = MailboxManager()
    mgr.register_task(5)
    updated = mgr.set_default_stdio_mode("out", mbx_const.HSX_MBX_MODE_RDWR | mbx_const.HSX_MBX_MODE_FANOUT, update_existing=True)
    assert updated  # default stdout descriptors updated
    handle = mgr.open(pid=99, target="svc:stdio.out@5")
    state_info = mgr.peek(pid=99, handle=handle)
    assert state_info["mode_mask"] & mbx_const.HSX_MBX_MODE_FANOUT


def test_register_allocator_spill_sequence_detected():
    ir = """
define dso_local i32 @main() {
entry:
  %v1 = add i32 0, 1
  %v2 = add i32 0, 2
  %v3 = add i32 0, 3
  %v4 = add i32 0, 4
  %v5 = add i32 0, 5
  %v6 = add i32 0, 6
  %v7 = add i32 0, 7
  %v8 = add i32 0, 8
  %v9 = add i32 0, 9
  %v10 = add i32 0, 10
  %s1 = add i32 %v1, %v2
  %s2 = add i32 %s1, %v3
  %s3 = add i32 %s2, %v4
  %s4 = add i32 %s3, %v5
  %s5 = add i32 %s4, %v6
  %s6 = add i32 %s5, %v7
  %s7 = add i32 %s6, %v8
  %s8 = add i32 %s7, %v9
  %s9 = add i32 %s8, %v10
  ret i32 %s9
}
"""

    asm_text = HSX_LLC.compile_ll_to_mvasm(ir, trace=False)
    assert "[R7" in asm_text

    mgr = MailboxManager()
    handle = mgr.open(pid=1, target="svc:stdio.out")
    ok, _ = mgr.send(pid=1, handle=handle, payload=b"ok")
    assert ok is True
    msg = mgr.recv(pid=1, handle=handle)
    assert msg is not None and msg.payload == b"ok"
