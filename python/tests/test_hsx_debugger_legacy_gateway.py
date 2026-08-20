from dataclasses import replace
from collections import deque
import json
import threading
import time
from types import SimpleNamespace

from python.executive_session import ConnectionLostError
from python.hsx_debugger.contracts import (
    CompletionAuthority,
    CompletionStatus,
    EffectKind,
    EventHealth,
    EvidenceGrade,
    GatewayCompletion,
    GatewayEffect,
    GatewayEvent,
    HealthNotice,
    ReconcileResult,
    ReconcileStatus,
    RpcHealth,
)
from python.hsx_debugger.legacy_gateway import (
    LEGACY_EVENT_CAPABILITY,
    LEGACY_PROFILE_ID,
    LEGACY_RESOURCE_CAPABILITY,
    PORTABLE_ACK_AFTER_APPLY_CAPABILITY,
    PORTABLE_EVENT_RESUME_CAPABILITY,
    PORTABLE_IDENTITY_CAPABILITY,
    PORTABLE_RESOURCE_CAPABILITY,
    LegacyExecutiveGateway,
    initial_legacy_generation,
)


class StubLegacySession:
    def __init__(self, responses=None, *, features=None, events_available=True):
        self.responses = list(responses or [])
        self.negotiated_features = list(features or ["events", "watch"])
        self.session_id = None
        self.session_disabled = False
        self.events_available = events_available
        self.event_availability = []
        self.requests = []
        self.configurations = []
        self.close_calls = 0
        self.stop_event_calls = 0
        self.event_callbacks = []
        self.fault_callbacks = []
        self.event_options = []
        self.synchronous_start_events = []
        self.block_next_start = False
        self.start_entered = threading.Event()
        self.start_release = threading.Event()

    def configure_session(self, **kwargs):
        self.configurations.append(kwargs)

    def request(self, payload, *, use_session=True, retry=True):
        self.requests.append((dict(payload), use_session, retry))
        if self.session_id is None and not self.session_disabled:
            self.session_id = "legacy-session-local-token"
        if self.responses:
            response = self.responses.pop(0)
            if isinstance(response, BaseException):
                raise response
            return response
        return {"status": "ok", "result": {"accepted": True}}

    def start_observed_event_stream(
        self,
        *,
        filters,
        event_callback,
        fault_callback,
        ack_interval,
    ):
        self.event_callbacks.append(event_callback)
        self.fault_callbacks.append(fault_callback)
        self.event_options.append((filters, ack_interval))
        synchronous = list(self.synchronous_start_events)
        self.synchronous_start_events.clear()
        for event in synchronous:
            event_callback(event)
        if self.block_next_start:
            self.block_next_start = False
            self.start_entered.set()
            self.start_release.wait(1.0)
        if self.event_availability:
            return self.event_availability.pop(0)
        return self.events_available

    def emit(self, event, *, stream=-1):
        return self.event_callbacks[stream](event)

    def fault(self, code, cause=None, *, lost=False, stream=-1):
        self.fault_callbacks[stream](code, cause, lost=lost)

    def stop_event_stream(self):
        self.stop_event_calls += 1

    def close(self):
        self.close_calls += 1


class _LineReader:
    def __init__(self, lines):
        self.lines = deque(lines)

    def readline(self):
        return self.lines.popleft() if self.lines else ""


class _SocketStub:
    def close(self):
        return None

    def shutdown(self, _how):
        return None


class PrivateEventSession:
    """Small double exercising the adapter's production ExecutiveSession private seam."""

    def __init__(self):
        self._session_lock = threading.Lock()
        self._event_stream = None
        self.session_disabled = False
        self.session_id = "legacy-session"
        self.negotiated_features = ["events"]
        self.requests = []
        self.close_calls = 0

    def _ensure_session(self):
        return None

    def _open_event_stream(self, _filters, _ack_interval):
        return SimpleNamespace(
            sock=_SocketStub(),
            rfile=_LineReader(
                [
                    "{\n",
                    json.dumps({"seq": 1, "type": "task_state", "pid": 3}) + "\n",
                    "",
                ]
            ),
            stop_event=threading.Event(),
            thread=None,
            token="private-stream-token",
        )

    def request(self, payload, *, use_session=True, retry=True):
        self.requests.append((dict(payload), use_session, retry))
        return {"status": "ok", "tasks": []}

    def stop_event_stream(self):
        stream = self._event_stream
        if stream is None:
            return
        stream.stop_event.set()
        stream.sock.close()
        if stream.thread is not threading.current_thread():
            stream.thread.join(timeout=0.2)
        self._event_stream = None

    def close(self):
        self.close_calls += 1
        self.stop_event_stream()


def _effect(operation_id, kind, generation, *, payload=None, idempotent=False):
    return GatewayEffect(
        operation_id=operation_id,
        command_id=f"cmd-{operation_id}",
        kind=kind,
        generation=generation,
        payload=payload or {},
        idempotent=idempotent,
    )


def _open_stamp(active, session_generation):
    return replace(
        active,
        session_generation=session_generation,
        capability_generation=session_generation,
        stream_generation=0,
    )


def _stream_stamp(active, stream_generation):
    return replace(active, stream_generation=stream_generation)


def _wait_for(predicate, timeout=1.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.005)
    raise AssertionError("condition was not satisfied before timeout")


def _has_completion(notices, operation_id):
    return any(
        isinstance(item, GatewayCompletion) and item.operation_id == operation_id
        for item in notices
    )


def _completion(notices, operation_id):
    return next(
        notice
        for notice in notices
        if isinstance(notice, GatewayCompletion) and notice.operation_id == operation_id
    )


def _open(gateway, notices, generation, *, operation_id="open", pid=7):
    gateway.submit(
        _effect(
            operation_id,
            EffectKind.OPEN_SESSION,
            generation,
            payload={"pid_lock": pid, "heartbeat_s": 12},
            idempotent=True,
        )
    )
    _wait_for(lambda: _has_completion(notices, operation_id))
    return _completion(notices, operation_id)


def test_open_echoes_controller_reserved_stamp_before_health_and_exposes_only_legacy_profile():
    active = initial_legacy_generation(display_pid=7)
    reserved = _open_stamp(active, 11)
    session = StubLegacySession([{"status": "ok", "tasks": []}])
    notices = []
    gateway = LegacyExecutiveGateway(session, initial_generation=active)
    gateway.start(notices.append)

    completion = _open(gateway, notices, reserved)
    gateway.close()

    assert completion.status is CompletionStatus.OK
    assert completion.authority is CompletionAuthority.AUTHORITATIVE_RESOURCE_ESTABLISHED
    assert completion.generation is reserved
    assert gateway.health.generation is reserved
    assert completion.generation.executive_instance_id is None
    assert completion.generation.target_id is None
    assert completion.evidence_grade is EvidenceGrade.LEGACY_DEGRADED

    candidate_notices = [item for item in notices if item.generation == reserved]
    assert candidate_notices[0] is completion
    assert isinstance(candidate_notices[1], HealthNotice)
    assert candidate_notices[1].rpc_health is RpcHealth.HEALTHY

    profile = completion.response["capability_profile"]
    assert profile["profile_id"] == LEGACY_PROFILE_ID
    assert profile["generation"] == 11
    assert profile["degraded"] is True
    assert set(profile["capabilities"]) == {
        LEGACY_EVENT_CAPABILITY,
        LEGACY_RESOURCE_CAPABILITY,
    }
    forbidden = {
        PORTABLE_IDENTITY_CAPABILITY,
        PORTABLE_ACK_AFTER_APPLY_CAPABILITY,
        PORTABLE_EVENT_RESUME_CAPABILITY,
        PORTABLE_RESOURCE_CAPABILITY,
    }
    assert forbidden.isdisjoint(profile["capabilities"])
    assert "portable_identity=false" in profile["diagnostics"]
    assert "ack_after_controller_apply=false" in profile["diagnostics"]
    assert "event_resume=false" in profile["diagnostics"]
    assert session.requests[0][0] == {"cmd": "ps"}
    assert session.requests[0][2] is True
    assert session.configurations == [{"pid_lock": 7, "heartbeat_s": 12}]


def test_failed_open_does_not_promote_and_burns_stamp_for_new_operation():
    active = initial_legacy_generation(display_pid=7)
    failed_stamp = _open_stamp(active, 4)
    next_stamp = _open_stamp(active, 7)
    session = StubLegacySession(
        [
            {"status": "error", "error": "session denied"},
            {"status": "ok", "tasks": []},
        ]
    )
    notices = []
    gateway = LegacyExecutiveGateway(session, initial_generation=active)
    gateway.start(notices.append)

    failed = _open(gateway, notices, failed_stamp, operation_id="open-failed")
    assert failed.status is CompletionStatus.REJECTED
    assert failed.authority is CompletionAuthority.ACK_ONLY
    assert failed.generation is failed_stamp
    assert gateway.health.generation is active

    gateway.submit(
        _effect(
            "open-reused-stamp",
            EffectKind.OPEN_SESSION,
            failed_stamp,
            idempotent=True,
        )
    )
    _wait_for(lambda: _has_completion(notices, "open-reused-stamp"))
    assert _completion(notices, "open-reused-stamp").status is CompletionStatus.STALE
    assert len(session.requests) == 1

    succeeded = _open(gateway, notices, next_stamp, operation_id="open-next")
    gateway.close()
    assert succeeded.status is CompletionStatus.OK
    assert succeeded.generation is next_stamp
    assert gateway.health.generation is next_stamp


def test_same_operation_retry_reuses_exact_stamp_without_reopening_successful_resource():
    active = initial_legacy_generation()
    reserved = _open_stamp(active, 3)
    session = StubLegacySession([{"status": "ok", "tasks": []}])
    notices = []
    gateway = LegacyExecutiveGateway(session, initial_generation=active)
    gateway.start(notices.append)
    effect = _effect(
        "open",
        EffectKind.OPEN_SESSION,
        reserved,
        payload={"request": {"cmd": "ps"}},
        idempotent=True,
    )

    gateway.submit(effect)
    _wait_for(lambda: _has_completion(notices, "open"))
    first_count = len([item for item in notices if isinstance(item, GatewayCompletion)])
    gateway.submit(effect)
    _wait_for(
        lambda: len([item for item in notices if isinstance(item, GatewayCompletion)])
        == first_count + 1
    )
    gateway.close()

    assert len(session.requests) == 1
    completions = [
        item
        for item in notices
        if isinstance(item, GatewayCompletion) and item.operation_id == "open"
    ]
    assert len(completions) == 2
    assert all(item.generation is reserved for item in completions)
    assert all(
        item.authority is CompletionAuthority.AUTHORITATIVE_RESOURCE_ESTABLISHED
        for item in completions
    )
    assert gateway.last_notice_error is None


def test_successful_resource_retry_is_stale_after_a_later_generation_supersedes_it():
    initial = initial_legacy_generation()
    first_stamp = _open_stamp(initial, 1)
    second_stamp = _open_stamp(first_stamp, 2)
    session = StubLegacySession(
        [
            {"status": "ok", "tasks": []},
            {"status": "ok", "tasks": []},
        ]
    )
    notices = []
    gateway = LegacyExecutiveGateway(session, initial_generation=initial)
    gateway.start(notices.append)
    first_effect = _effect(
        "open-first",
        EffectKind.OPEN_SESSION,
        first_stamp,
        idempotent=True,
    )
    gateway.submit(first_effect)
    _wait_for(lambda: _has_completion(notices, "open-first"))
    _open(gateway, notices, second_stamp, operation_id="open-second")
    first_completion_count = len(
        [
            item
            for item in notices
            if isinstance(item, GatewayCompletion) and item.operation_id == "open-first"
        ]
    )

    gateway.submit(first_effect)
    _wait_for(
        lambda: len(
            [
                item
                for item in notices
                if isinstance(item, GatewayCompletion) and item.operation_id == "open-first"
            ]
        )
        == first_completion_count + 1
    )
    gateway.close()

    replay = [
        item
        for item in notices
        if isinstance(item, GatewayCompletion) and item.operation_id == "open-first"
    ][-1]
    assert replay.status is CompletionStatus.STALE
    assert replay.generation is first_stamp
    assert gateway.health.generation is second_stamp
    assert len(session.requests) == 2


def test_request_passes_retry_only_for_explicitly_idempotent_effects():
    active = initial_legacy_generation(display_pid=7)
    reserved = _open_stamp(active, 1)
    session = StubLegacySession(
        [
            {"status": "ok", "tasks": []},
            {"status": "ok", "result": 1},
            {"status": "ok", "result": 2},
        ]
    )
    notices = []
    gateway = LegacyExecutiveGateway(session, initial_generation=active)
    gateway.start(notices.append)
    _open(gateway, notices, reserved)

    gateway.submit(
        _effect(
            "write",
            EffectKind.REQUEST,
            reserved,
            payload={"request": {"cmd": "debug.state", "pid": 7, "state": "running"}},
            idempotent=False,
        )
    )
    gateway.submit(
        _effect(
            "read",
            EffectKind.REQUEST,
            reserved,
            payload={"request": {"cmd": "ps"}},
            idempotent=True,
        )
    )
    _wait_for(lambda: _has_completion(notices, "write") and _has_completion(notices, "read"))
    gateway.close()

    assert session.requests[1][2] is False
    assert session.requests[2][2] is True
    assert _completion(notices, "write").generation is reserved
    assert _completion(notices, "read").generation is reserved


def test_non_idempotent_transport_failure_is_typed_exact_and_not_retryable():
    active = initial_legacy_generation(display_pid=7)
    reserved = _open_stamp(active, 1)
    session = StubLegacySession(
        [
            {"status": "ok", "tasks": []},
            ConnectionLostError("connection reset"),
        ]
    )
    notices = []
    gateway = LegacyExecutiveGateway(session, initial_generation=active)
    gateway.start(notices.append)
    _open(gateway, notices, reserved)
    gateway.submit(
        _effect(
            "mutate",
            EffectKind.REQUEST,
            reserved,
            payload={"request": {"cmd": "breakpoint.add", "pid": 7, "address": 3}},
            idempotent=False,
        )
    )
    _wait_for(lambda: _has_completion(notices, "mutate"))
    gateway.close()

    completion = _completion(notices, "mutate")
    assert completion.status is CompletionStatus.TRANSPORT_ERROR
    assert completion.generation is reserved
    assert completion.failure is not None
    assert completion.failure.retryable is False
    assert session.requests[-1][2] is False
    assert any(
        isinstance(item, HealthNotice)
        and item.generation is reserved
        and item.rpc_health is RpcHealth.LOST
        for item in notices
    )


def test_subscribe_buffers_candidate_event_until_authoritative_completion():
    initial = initial_legacy_generation(display_pid=7)
    session_stamp = _open_stamp(initial, 2)
    stream_stamp = _stream_stamp(session_stamp, 13)
    session = StubLegacySession([{"status": "ok", "tasks": []}])
    session.synchronous_start_events = [
        {"seq": 1, "type": "task_state", "pid": 7, "data": {"state": "paused"}}
    ]
    notices = []
    gateway = LegacyExecutiveGateway(session, initial_generation=initial)
    gateway.start(notices.append)
    _open(gateway, notices, session_stamp)

    gateway.submit(
        _effect(
            "subscribe",
            EffectKind.SUBSCRIBE_EVENTS,
            stream_stamp,
            payload={"filters": {"categories": ["scheduler"]}, "ack_interval": 2},
            idempotent=True,
        )
    )
    _wait_for(lambda: _has_completion(notices, "subscribe") and any(
        isinstance(item, GatewayEvent) and item.generation == stream_stamp for item in notices
    ))
    gateway.close()

    candidate_notices = [item for item in notices if item.generation == stream_stamp]
    assert isinstance(candidate_notices[0], GatewayCompletion)
    assert candidate_notices[0].authority is CompletionAuthority.AUTHORITATIVE_RESOURCE_ESTABLISHED
    assert isinstance(candidate_notices[1], HealthNotice)
    assert isinstance(candidate_notices[2], GatewayEvent)
    assert candidate_notices[2].sequence == 1
    assert gateway.health.generation is stream_stamp
    assert session.event_options == [({"categories": ["scheduler"]}, 2)]


def test_buffered_pre_completion_gap_is_retained_in_tracker_after_subscribe():
    initial = initial_legacy_generation()
    session_stamp = _open_stamp(initial, 1)
    stream_stamp = _stream_stamp(session_stamp, 1)
    session = StubLegacySession([{"status": "ok", "tasks": []}])
    session.synchronous_start_events = [{"type": "task_state", "pid": 1}]
    notices = []
    gateway = LegacyExecutiveGateway(session, initial_generation=initial)
    gateway.start(notices.append)
    _open(gateway, notices, session_stamp)
    gateway.submit(
        _effect("subscribe", EffectKind.SUBSCRIBE_EVENTS, stream_stamp, idempotent=True)
    )
    _wait_for(lambda: _has_completion(notices, "subscribe") and any(
        isinstance(item, GatewayEvent) and item.generation == stream_stamp for item in notices
    ))

    candidate_notices = [item for item in notices if item.generation == stream_stamp]
    assert isinstance(candidate_notices[0], GatewayCompletion)
    assert candidate_notices[0].authority is CompletionAuthority.AUTHORITATIVE_RESOURCE_ESTABLISHED
    assert isinstance(candidate_notices[1], HealthNotice)
    assert candidate_notices[1].event_health is EventHealth.GAP
    assert gateway.health.snapshot().event_health is EventHealth.GAP
    gateway.close()


def test_old_active_stream_event_is_delivered_while_replacement_is_pending_then_fenced():
    initial = initial_legacy_generation(display_pid=7)
    session_stamp = _open_stamp(initial, 1)
    old_stream = _stream_stamp(session_stamp, 2)
    replacement = _stream_stamp(session_stamp, 5)
    session = StubLegacySession([{"status": "ok", "tasks": []}])
    notices = []
    gateway = LegacyExecutiveGateway(session, initial_generation=initial)
    gateway.start(notices.append)
    _open(gateway, notices, session_stamp)
    gateway.submit(
        _effect("subscribe-old", EffectKind.SUBSCRIBE_EVENTS, old_stream, idempotent=True)
    )
    _wait_for(lambda: _has_completion(notices, "subscribe-old"))
    old_callback = session.event_callbacks[-1]

    session.block_next_start = True
    gateway.submit(
        _effect("subscribe-new", EffectKind.SUBSCRIBE_EVENTS, replacement, idempotent=True)
    )
    assert session.start_entered.wait(1.0)
    assert old_callback({"seq": 1, "type": "task_state", "pid": 7}) is True
    session.start_release.set()
    _wait_for(lambda: _has_completion(notices, "subscribe-new"))

    old_event_index = next(
        index
        for index, item in enumerate(notices)
        if isinstance(item, GatewayEvent) and item.generation == old_stream
    )
    promotion_index = next(
        index
        for index, item in enumerate(notices)
        if isinstance(item, GatewayCompletion) and item.operation_id == "subscribe-new"
    )
    assert old_event_index < promotion_index
    count_before = len(notices)
    assert old_callback({"seq": 2, "type": "task_state", "pid": 7}) is False
    time.sleep(0.02)
    gateway.close()
    assert len(notices) == count_before


def test_failed_subscribe_retains_old_generation_and_burns_stream_stamp():
    initial = initial_legacy_generation()
    session_stamp = _open_stamp(initial, 1)
    failed_stream = _stream_stamp(session_stamp, 4)
    next_stream = _stream_stamp(session_stamp, 9)
    session = StubLegacySession([{"status": "ok", "tasks": []}])
    session.event_availability = [False, True]
    notices = []
    gateway = LegacyExecutiveGateway(session, initial_generation=initial)
    gateway.start(notices.append)
    _open(gateway, notices, session_stamp)

    gateway.submit(
        _effect("subscribe-failed", EffectKind.SUBSCRIBE_EVENTS, failed_stream, idempotent=True)
    )
    _wait_for(lambda: _has_completion(notices, "subscribe-failed"))
    assert _completion(notices, "subscribe-failed").status is CompletionStatus.UNSUPPORTED
    assert gateway.health.generation is session_stamp

    gateway.submit(
        _effect("subscribe-reuse", EffectKind.SUBSCRIBE_EVENTS, failed_stream, idempotent=True)
    )
    _wait_for(lambda: _has_completion(notices, "subscribe-reuse"))
    assert _completion(notices, "subscribe-reuse").status is CompletionStatus.STALE
    assert len(session.event_callbacks) == 1

    gateway.submit(
        _effect("subscribe-next", EffectKind.SUBSCRIBE_EVENTS, next_stream, idempotent=True)
    )
    _wait_for(lambda: _has_completion(notices, "subscribe-next"))
    gateway.close()
    assert _completion(notices, "subscribe-next").status is CompletionStatus.OK
    assert gateway.health.generation is next_stream


def test_subscribe_rejects_wrong_active_session_parent_without_opening_stream():
    initial = initial_legacy_generation()
    session_stamp = _open_stamp(initial, 1)
    wrong_parent = replace(
        session_stamp,
        target_generation=session_stamp.target_generation + 1,
        stream_generation=1,
    )
    session = StubLegacySession([{"status": "ok", "tasks": []}])
    notices = []
    gateway = LegacyExecutiveGateway(session, initial_generation=initial)
    gateway.start(notices.append)
    _open(gateway, notices, session_stamp)
    gateway.submit(
        _effect("subscribe-wrong-parent", EffectKind.SUBSCRIBE_EVENTS, wrong_parent, idempotent=True)
    )
    _wait_for(lambda: _has_completion(notices, "subscribe-wrong-parent"))
    gateway.close()

    completion = _completion(notices, "subscribe-wrong-parent")
    assert completion.status is CompletionStatus.STALE
    assert completion.generation is wrong_parent
    assert session.event_callbacks == []


def test_event_gap_malformed_callback_and_eof_are_visible_typed_health():
    initial = initial_legacy_generation(display_pid=7)
    session_stamp = _open_stamp(initial, 1)
    stream_stamp = _stream_stamp(session_stamp, 1)
    session = StubLegacySession([{"status": "ok", "tasks": []}])
    notices = []
    gateway = LegacyExecutiveGateway(session, initial_generation=initial)
    gateway.start(notices.append)
    _open(gateway, notices, session_stamp)
    gateway.submit(
        _effect("subscribe", EffectKind.SUBSCRIBE_EVENTS, stream_stamp, idempotent=True)
    )
    _wait_for(lambda: _has_completion(notices, "subscribe"))

    assert session.emit({"seq": 10, "type": "task_state", "pid": 7}) is True
    assert session.emit({"seq": 12, "type": "task_state", "pid": 7}) is True
    session.fault("event_malformed", json.JSONDecodeError("bad", "{", 0), lost=False)
    session.fault("event_callback_error", RuntimeError("callback"), lost=False)
    session.fault("event_eof", lost=True)
    _wait_for(lambda: any(
        isinstance(item, HealthNotice) and item.event_health is EventHealth.LOST
        for item in notices
    ))
    gateway.close()

    events = [item for item in notices if isinstance(item, GatewayEvent)]
    assert [item.sequence for item in events] == [10, 12]
    assert events[0].gap is None
    assert events[1].gap is not None
    assert events[1].gap.expected_sequence == 11
    assert events[1].gap.observed_sequence == 12
    health_reasons = [item.reason for item in notices if isinstance(item, HealthNotice)]
    assert any("event_malformed" in reason for reason in health_reasons)
    assert any("event_callback_error" in reason for reason in health_reasons)
    assert any("event_eof" in reason for reason in health_reasons)
    assert all(event.generation is stream_stamp for event in events)


def test_private_event_reader_surfaces_malformed_frame_and_eof_without_silent_health():
    initial = initial_legacy_generation()
    session_stamp = _open_stamp(initial, 1)
    stream_stamp = _stream_stamp(session_stamp, 1)
    session = PrivateEventSession()
    notices = []
    gateway = LegacyExecutiveGateway(session, initial_generation=initial)
    gateway.start(notices.append)
    _open(gateway, notices, session_stamp)
    gateway.submit(
        _effect("subscribe", EffectKind.SUBSCRIBE_EVENTS, stream_stamp, idempotent=True)
    )
    _wait_for(lambda: _has_completion(notices, "subscribe") and any(
        isinstance(item, HealthNotice)
        and item.generation == stream_stamp
        and item.event_health is EventHealth.LOST
        for item in notices
    ))
    gateway.close()

    reasons = [
        item.reason
        for item in notices
        if isinstance(item, HealthNotice) and item.generation == stream_stamp
    ]
    assert any("event_malformed" in reason for reason in reasons)
    assert any("event_eof" in reason for reason in reasons)
    assert any(
        isinstance(item, GatewayEvent)
        and item.generation == stream_stamp
        and item.sequence == 1
        for item in notices
    )


def test_reconcile_with_same_legacy_pid_is_always_legacy_unproven():
    initial = initial_legacy_generation(display_pid=7)
    session_stamp = _open_stamp(initial, 1)
    session = StubLegacySession(
        [
            {"status": "ok", "tasks": [{"pid": 7, "state": "paused"}]},
            {"status": "ok", "tasks": [{"pid": 7, "state": "paused"}]},
        ]
    )
    notices = []
    gateway = LegacyExecutiveGateway(session, initial_generation=initial)
    gateway.start(notices.append)
    _open(gateway, notices, session_stamp)
    gateway.submit(
        _effect(
            "reconcile",
            EffectKind.RECONCILE,
            session_stamp,
            payload={"request": {"cmd": "ps"}},
            idempotent=True,
        )
    )
    _wait_for(lambda: any(isinstance(item, ReconcileResult) for item in notices))
    gateway.close()

    result = next(item for item in notices if isinstance(item, ReconcileResult))
    assert result.status is ReconcileStatus.LEGACY_UNPROVEN
    assert result.generation is session_stamp
    assert result.generation.target_id is None
    assert "portable_target_identity=false" in result.diagnostics
    assert "portable_ownership_evidence=false" in result.diagnostics


def test_portable_identity_effect_is_unsupported_and_exactly_echoed():
    session = StubLegacySession()
    notices = []
    gateway = LegacyExecutiveGateway(session)
    gateway.start(notices.append)
    portable = replace(
        initial_legacy_generation(display_pid=7),
        executive_instance_id="exec-1",
        target_id="target-1",
        evidence_grade=EvidenceGrade.PORTABLE,
    )
    gateway.submit(
        _effect(
            "portable",
            EffectKind.REQUEST,
            portable,
            payload={"request": {"cmd": "ps"}},
        )
    )
    _wait_for(lambda: _has_completion(notices, "portable"))
    gateway.close()

    completion = _completion(notices, "portable")
    assert completion.status is CompletionStatus.UNSUPPORTED
    assert completion.generation is portable
    assert completion.evidence_grade is EvidenceGrade.PORTABLE
    assert session.requests == []


def test_notice_sink_failure_from_event_callback_degrades_health_observably():
    initial = initial_legacy_generation(display_pid=7)
    session_stamp = _open_stamp(initial, 1)
    stream_stamp = _stream_stamp(session_stamp, 1)
    session = StubLegacySession(
        [
            {"status": "ok", "tasks": []},
            {"status": "ok", "tasks": []},
        ]
    )
    accepted = []
    fail_next_event = threading.Event()

    def sink(notice):
        if fail_next_event.is_set() and isinstance(notice, GatewayEvent):
            fail_next_event.clear()
            raise RuntimeError("controller callback failed")
        accepted.append(notice)

    gateway = LegacyExecutiveGateway(session, initial_generation=initial)
    gateway.start(sink)
    _open(gateway, accepted, session_stamp)
    gateway.submit(
        _effect("subscribe", EffectKind.SUBSCRIBE_EVENTS, stream_stamp, idempotent=True)
    )
    _wait_for(lambda: _has_completion(accepted, "subscribe"))
    fail_next_event.set()
    assert session.emit({"seq": 1, "type": "task_state", "pid": 7}) is True
    gateway.submit(
        _effect(
            "probe",
            EffectKind.REQUEST,
            stream_stamp,
            payload={"request": {"cmd": "ps"}},
            idempotent=True,
        )
    )
    _wait_for(lambda: any(
        isinstance(item, HealthNotice) and "notice sink failed" in item.reason
        for item in accepted
    ))
    assert gateway.health.snapshot().event_health is EventHealth.GAP
    assert "RuntimeError" in (gateway.last_sink_error or "")
    gateway.close()


def test_gateway_close_is_idempotent_and_closes_legacy_session_once():
    session = StubLegacySession()
    gateway = LegacyExecutiveGateway(session)
    gateway.start(lambda _notice: None)
    gateway.close()
    gateway.close()
    assert session.close_calls == 1
    assert gateway.is_alive is False
