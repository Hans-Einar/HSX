from python.hsx_dap import HSXDebugAdapter
from python.hsxdbg.events import TaskStateEvent, TraceStepEvent


class ProtocolRecorder:
    def __init__(self):
        self.events = []

    def send_event(self, event, body):
        self.events.append({"event": event, "body": body})

    def send_response(self, *args, **kwargs):
        pass

    def read_message(self):
        return None


class SymbolStub:
    def lookup_pc(self, pc):
        return {"file": "main.c", "directory": None, "line": 42, "column": 1}

    def lookup(self, *args, **kwargs):
        return []

    def locals_for_function(self, func):
        return []

    def globals_list(self):
        return []


def _make_adapter():
    proto = ProtocolRecorder()
    adapter = HSXDebugAdapter(proto)
    adapter.current_pid = 1
    adapter._symbol_mapper = SymbolStub()
    return adapter, proto


def test_trace_step_event_emits_single_stopped():
    adapter, proto = _make_adapter()
    adapter._pending_step_reason = "step"
    event = TraceStepEvent(seq=1, ts=0.0, type="trace_step", pid=1, data={}, pc=0x10)

    adapter._handle_exec_event(event)

    assert len(proto.events) == 1
    payload = proto.events[0]
    assert payload["event"] == "stopped"
    assert payload["body"]["reason"] == "step"
    assert payload["body"]["line"] == 42

    adapter._handle_exec_event(event)
    assert len(proto.events) == 1


def test_task_state_events_emit_thread_and_stopped():
    adapter, proto = _make_adapter()

    loaded = TaskStateEvent(
        seq=1,
        ts=0.0,
        type="task_state",
        pid=1,
        data={"name": "worker"},
        prev_state=None,
        new_state="ready",
        reason="loaded",
    )
    adapter._handle_exec_event(loaded)
    assert proto.events[-1]["event"] == "thread"
    assert proto.events[-1]["body"]["reason"] == "started"

    running = TaskStateEvent(
        seq=2,
        ts=0.1,
        type="task_state",
        pid=1,
        data={"name": "worker"},
        prev_state="ready",
        new_state="running",
        reason="resume",
    )
    adapter._handle_exec_event(running)
    assert proto.events[-1]["event"] == "continued"

    paused = TaskStateEvent(
        seq=3,
        ts=0.2,
        type="task_state",
        pid=1,
        data={"details": {"pc": 0x30}},
        prev_state="running",
        new_state="paused",
        reason="debug_break",
    )
    adapter._handle_exec_event(paused)
    assert proto.events[-1]["event"] == "stopped"
    assert proto.events[-1]["body"]["reason"] == "debug_break"
    assert proto.events[-1]["body"]["line"] == 42

    terminated = TaskStateEvent(
        seq=4,
        ts=0.3,
        type="task_state",
        pid=1,
        data={},
        prev_state="paused",
        new_state="terminated",
        reason="returned",
    )
    adapter._handle_exec_event(terminated)
    assert proto.events[-1]["event"] == "thread"
    assert proto.events[-1]["body"]["reason"] == "exited"
    assert 1 not in adapter._thread_states


def test_continue_request_starts_clock():
    adapter, proto = _make_adapter()
    calls = []

    class Client:
        def resume(self, pid):
            calls.append(("resume", pid))

        def clock_start(self):
            calls.append(("clock_start", None))

    adapter.client = Client()
    adapter.current_pid = 7
    adapter._handle_continue({})
    assert calls == [("resume", 7), ("clock_start", None)]
    assert proto.events[-1]["event"] == "continued"
