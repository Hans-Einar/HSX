from python.hsxdbg.cache import CacheController, MailboxDescriptor, MemoryBlock, RuntimeCache, StackFrame, WatchValue
from python.hsxdbg.events import EventBus
from python.hsxdbg.events import TraceStepEvent, WatchUpdateEvent


def test_update_registers_from_mapping():
    cache = RuntimeCache()
    state = cache.update_registers(
        pid=1,
        regs={
            "r0": 1,
            "R1": 2,
            "pc": 0x1234,
            "sp": 0x2000,
            "psw": 0xFF,
        },
    )
    assert state.pc == 0x1234
    assert state.sp == 0x2000
    assert state.psw == 0xFF
    assert state.registers["R0"] == 1
    assert state.registers["R1"] == 2
    assert cache.get_registers(1) is state


def test_update_registers_from_list_with_overrides():
    cache = RuntimeCache()
    regs = [10, 11] + [0] * 14
    state = cache.update_registers(2, regs, pc=0x900, sp=0x8000)
    assert state.registers["R0"] == 10
    assert state.registers["R1"] == 11
    assert state.pc == 0x900
    assert state.sp == 0x8000


def test_update_registers_accepts_zero_padded_keys():
    cache = RuntimeCache()
    state = cache.update_registers(
        5,
        {
            "r00": 42,
            "R15": 0xAA55,
        },
    )
    assert state.registers["R0"] == 42
    assert state.registers["R15"] == 0xAA55
    assert cache.query_registers(5, "R00") == 42
    assert cache.query_registers(5, "r15") == 0xAA55


def test_memory_cache_read_exact_range():
    cache = RuntimeCache()
    block = cache.cache_memory(1, base=0x100, data=b"abcdef")
    assert isinstance(block, MemoryBlock)
    assert cache.read_memory(1, 0x102, 2) == b"cd"
    assert cache.read_memory(1, 0x200, 1) is None


def test_call_stack_storage():
    cache = RuntimeCache()
    frames = cache.update_call_stack(
        3,
        [
            {"pc": 0x1000, "sp": 0x7FF0, "fp": 0x7FF8, "func_name": "main", "line": 42, "file": "main.c"},
            {"pc": 0x1100, "sp": 0x7FD0, "fp": 0x7FD8, "func_name": "helper"},
        ],
    )
    assert isinstance(frames[0], StackFrame)
    assert frames[0].func_name == "main"
    assert cache.get_call_stack(3)[1].pc == 0x1100


def test_watch_cache_updates_and_lookup():
    cache = RuntimeCache()
    watch = cache.update_watch(
        4,
        {
            "id": 5,
            "expr": "foo",
            "length": 4,
            "value": "00010203",
            "address": 0x200,
        },
    )
    assert isinstance(watch, WatchValue)
    assert cache.get_watch(4, 5).value == "00010203"
    assert cache.iter_watches(4)[0].address == 0x200


def test_mailbox_descriptor_cache():
    cache = RuntimeCache()
    entries = cache.update_mailboxes(
        2,
        [
            {"name": "svc:log", "owner": 0, "capacity": 16, "mode": 3},
            {"name": "app:telemetry", "owner": 2, "capacity": 4},
        ],
    )
    assert isinstance(entries["svc:log"], MailboxDescriptor)
    assert len(cache.list_mailboxes(2)) == 2


def test_seed_snapshot_and_clear_pid():
    cache = RuntimeCache()
    cache.seed_snapshot(
        pid=7,
        registers={"R0": 1, "PC": 0x10},
        stack=[{"pc": 0x10}],
        watches=[{"id": 1, "expr": "foo", "length": 2, "value": "0000"}],
        mailboxes=[{"name": "svc:log", "owner": 7}],
    )
    assert cache.get_registers(7) is not None
    assert cache.get_call_stack(7)
    assert cache.iter_watches(7)
    assert cache.list_mailboxes(7)
    cache.clear_pid(7)
    assert cache.get_registers(7) is None


def test_query_helpers_with_fallbacks():
    cache = RuntimeCache()

    def memory_fallback(addr, length):
        return b"abc" if addr == 0x10 and length == 3 else None

    mem = cache.query_memory(1, 0x10, 3, fallback=memory_fallback)
    assert mem == b"abc"
    # second call should hit cache
    assert cache.query_memory(1, 0x10, 3) == b"abc"

    def stack_fallback():
        return [{"pc": 0x20}]

    stack = cache.query_call_stack(1, fallback=stack_fallback)
    assert stack[0].pc == 0x20

    def watch_fallback():
        return [{"id": 9, "expr": "bar", "length": 4, "value": "0000"}]

    watches = cache.query_watches(1, fallback=watch_fallback)
    assert watches[0].watch_id == 9

    cache.update_registers(1, {"R0": 7, "PC": 0x30})
    assert cache.query_registers(1, "R0") == 7
    assert cache.query_registers(1, "pc") == 0x30


def test_apply_trace_event_updates_cache():
    cache = RuntimeCache()
    event = TraceStepEvent(
        seq=1,
        ts=0.0,
        type="trace_step",
        pid=9,
        data={"regs": [5, 6]},
        pc=0x400,
        flags=3,
        regs=[5, 6],
    )
    cache.apply_event(event)
    state = cache.get_registers(9)
    assert state is not None
    assert state.pc == 0x400
    assert state.registers["R0"] == 5


def test_apply_watch_event_updates_cache():
    cache = RuntimeCache()
    event = WatchUpdateEvent(
        seq=2,
        ts=0.1,
        type="watch_update",
        pid=1,
        data={},
        watch_id=7,
        expr="foo",
        length=4,
        new_value="01020304",
    )
    cache.apply_event(event)
    watch = cache.get_watch(1, 7)
    assert watch is not None
    assert watch.value == "01020304"
    assert watch.expr == "foo"


def test_cache_controller_receives_events_from_bus():
    cache = RuntimeCache()
    bus = EventBus()
    controller = CacheController(cache, bus)
    bus.publish(
        {
            "seq": 1,
            "ts": 0.0,
            "type": "trace_step",
            "pid": 4,
            "data": {"pc": 0x10, "regs": [1, 2]},
        }
    )
    bus.pump()
    controller.detach()
    state = cache.get_registers(4)
    assert state is not None
    assert state.pc == 0x10
