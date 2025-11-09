from python.hsxdbg.events import (
    EventBus,
    EventSubscription,
    StdStreamEvent,
    TraceStepEvent,
    WatchUpdateEvent,
    parse_event,
)


def test_parse_trace_step_event():
    raw = {
        "seq": 10,
        "ts": 123.5,
        "type": "trace_step",
        "pid": 2,
        "data": {
            "pc": 0x100,
            "next_pc": 0x104,
            "opcode": 0x21,
            "flags": 3,
            "regs": [1, 2, 3],
            "changed_regs": ["R0", "R1"],
        },
    }
    event = parse_event(raw)
    assert isinstance(event, TraceStepEvent)
    assert event.pc == 0x100
    assert event.next_pc == 0x104
    assert event.opcode == 0x21
    assert event.flags == 3
    assert event.pid == 2
    assert event.changed_regs == ["R0", "R1"]


def test_parse_watch_update_event():
    raw = {
        "seq": 5,
        "ts": 1.5,
        "type": "watch_update",
        "pid": 1,
        "data": {
            "watch_id": 4,
            "expr": "foo",
            "length": 4,
            "old": "0000",
            "new": "0101",
            "address": 0x200,
        },
    }
    event = parse_event(raw)
    assert isinstance(event, WatchUpdateEvent)
    assert event.watch_id == 4
    assert event.expr == "foo"
    assert event.address == 0x200
    assert event.new_value == "0101"


def test_parse_stdout_event():
    raw = {
        "seq": 7,
        "ts": 2.0,
        "type": "stdout",
        "pid": 3,
        "data": {"text": "hello"},
    }
    event = parse_event(raw)
    assert isinstance(event, StdStreamEvent)
    assert event.text == "hello"
    assert event.stream == "stdout"


def test_event_bus_start_stop_handles_events():
    bus = EventBus()
    received = []
    bus.subscribe(EventSubscription(handler=lambda ev: received.append(ev)))
    bus.start(interval=0.001)
    bus.publish(
        {
            "seq": 1,
            "ts": 0.0,
            "type": "stdout",
            "pid": 1,
            "data": {"text": "ping"},
        }
    )
    bus.stop()
    assert received and isinstance(received[0], StdStreamEvent)
