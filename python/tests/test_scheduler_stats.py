import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from platforms.python.host_vm import VMController


def test_info_exposes_scheduler_counters_and_trace():
    repo_root = Path(__file__).resolve().parents[2]
    controller = VMController()
    consumer = controller.load_from_path(str(repo_root / "examples/demos/build/mailbox/consumer.hxe"))
    producer = controller.load_from_path(str(repo_root / "examples/demos/build/mailbox/producer.hxe"))

    controller.step(6)

    info = controller.info()
    scheduler = info.get("scheduler", {})
    counters = scheduler.get("counters", {})
    mailbox_counters = scheduler.get("mailbox_counters", {})
    trace = scheduler.get("trace", [])

    assert consumer["pid"] in counters
    assert producer["pid"] in counters
    assert counters[consumer["pid"]]["step"] > 0
    assert consumer["pid"] in mailbox_counters
    assert producer["pid"] in mailbox_counters
    assert "MAILBOX_STEP" in mailbox_counters[consumer["pid"]]
    assert any(entry.get("event") == "rotate" for entry in trace)
