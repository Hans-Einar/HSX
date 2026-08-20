from dataclasses import replace
import threading
import time

import pytest

from python.hsx_debugger.contracts import (
    CompletionAuthority,
    CompletionStatus,
    EffectKind,
    EventHealth,
    EvidenceGrade,
    GatewayCompletion,
    GatewayEffect,
    GenerationStamp,
    HealthNotice,
    RpcHealth,
)
from python.hsx_debugger.gateway import (
    GatewayEffectError,
    GatewayQueueFullError,
    WorkerThreadExecutiveGateway,
)
from python.hsx_debugger.health import GatewayHealthTracker


def _generation() -> GenerationStamp:
    return GenerationStamp(
        executive_instance_id=None,
        session_generation=2,
        target_id=None,
        target_generation=3,
        capability_generation=2,
        stream_generation=5,
        display_pid=7,
        evidence_grade=EvidenceGrade.LEGACY_DEGRADED,
    )


def _effect(
    operation_id: str,
    *,
    generation: GenerationStamp | None = None,
    kind: EffectKind = EffectKind.REQUEST,
    idempotent: bool = False,
    payload=None,
) -> GatewayEffect:
    return GatewayEffect(
        operation_id=operation_id,
        command_id=f"cmd-{operation_id}",
        kind=kind,
        generation=generation or _generation(),
        payload=payload or {"request": {"cmd": "ps"}},
        idempotent=idempotent,
    )


def _completion(
    effect: GatewayEffect,
    *,
    authority: CompletionAuthority = CompletionAuthority.ACK_ONLY,
) -> GatewayCompletion:
    return GatewayCompletion(
        operation_id=effect.operation_id,
        generation=effect.generation,
        status=CompletionStatus.OK,
        response={"accepted": True},
        evidence_grade=effect.generation.evidence_grade,
        authority=authority,
    )


def _wait_for(predicate, timeout: float = 1.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.005)
    raise AssertionError("condition was not satisfied before timeout")


def test_health_tracker_keeps_dimensions_independent_and_never_derives_a_stamp():
    active = _generation()
    reserved = replace(active, stream_generation=91)
    health = GatewayHealthTracker(active)

    rpc_notice = health.transition(rpc_health=RpcHealth.HEALTHY, reason="RPC connected")
    assert rpc_notice.rpc_health is RpcHealth.HEALTHY
    assert rpc_notice.event_health is EventHealth.DISABLED
    assert rpc_notice.generation is active

    event_notice = health.transition(event_health=EventHealth.GAP, reason="event sequence gap")
    assert event_notice.rpc_health is RpcHealth.HEALTHY
    assert event_notice.event_health is EventHealth.GAP
    assert event_notice.generation is active

    established = health.establish(
        reserved,
        event_health=EventHealth.HEALTHY,
        reason="exact reserved stream established",
    )
    assert established.generation is reserved
    assert health.generation is reserved
    with pytest.raises(TypeError):
        health.transition(  # type: ignore[call-arg]
            generation=replace(reserved, stream_generation=92),
            reason="implicit allocation is not an API",
        )


def test_gateway_serializes_handler_and_notice_sink_on_worker_thread():
    health = GatewayHealthTracker(_generation())
    handler_threads = []
    sink_threads = []
    notices = []
    delivered = threading.Event()

    def handler(effect, _publish):
        handler_threads.append(threading.current_thread().name)
        return _completion(effect)

    def sink(notice):
        sink_threads.append(threading.current_thread().name)
        notices.append(notice)
        delivered.set()

    gateway = WorkerThreadExecutiveGateway(handler, health, queue_capacity=2)
    gateway.start(sink)
    gateway.submit(_effect("op-1"))
    assert delivered.wait(1.0)
    gateway.close()

    assert isinstance(notices[0], GatewayCompletion)
    assert notices[0].generation == _generation()
    assert handler_threads == ["hsx-debug-gateway"]
    assert sink_threads == ["hsx-debug-gateway"]
    assert gateway.is_alive is False


def test_gateway_enforces_completion_before_new_generation_health():
    active = _generation()
    reserved = replace(
        active,
        session_generation=17,
        capability_generation=17,
        stream_generation=0,
    )
    effect = _effect(
        "open-17",
        kind=EffectKind.OPEN_SESSION,
        generation=reserved,
        idempotent=True,
    )
    health = GatewayHealthTracker(active, rpc_health=RpcHealth.HEALTHY)
    notices = []

    def handler(value, _publish):
        return (
            HealthNotice(active, RpcHealth.HEALTHY, EventHealth.DISABLED, "old still active"),
            _completion(
                value,
                authority=CompletionAuthority.AUTHORITATIVE_RESOURCE_ESTABLISHED,
            ),
            HealthNotice(reserved, RpcHealth.HEALTHY, EventHealth.DISABLED, "new established"),
        )

    gateway = WorkerThreadExecutiveGateway(handler, health)
    gateway.start(notices.append)
    gateway.submit(effect)
    _wait_for(lambda: len(notices) == 3)
    gateway.close()

    assert [notice.generation for notice in notices] == [active, reserved, reserved]
    assert isinstance(notices[1], GatewayCompletion)
    assert notices[1].authority is CompletionAuthority.AUTHORITATIVE_RESOURCE_ESTABLISHED


def test_gateway_rejects_pre_establishment_new_generation_notice():
    active = _generation()
    reserved = replace(active, stream_generation=9)
    effect = _effect(
        "subscribe-9",
        kind=EffectKind.SUBSCRIBE_EVENTS,
        generation=reserved,
        idempotent=True,
    )
    health = GatewayHealthTracker(active)
    notices = []

    def handler(value, _publish):
        return (
            HealthNotice(reserved, RpcHealth.HEALTHY, EventHealth.HEALTHY, "too early"),
            _completion(
                value,
                authority=CompletionAuthority.AUTHORITATIVE_RESOURCE_ESTABLISHED,
            ),
        )

    gateway = WorkerThreadExecutiveGateway(handler, health)
    gateway.start(notices.append)
    gateway.submit(effect)
    _wait_for(lambda: any(isinstance(item, GatewayCompletion) for item in notices))
    gateway.close()

    completion = next(item for item in notices if isinstance(item, GatewayCompletion))
    assert completion.generation is reserved
    assert completion.status is CompletionStatus.PROTOCOL_ERROR
    assert completion.failure is not None
    assert completion.failure.code == "pre_establishment_notice"
    assert not any(
        isinstance(item, HealthNotice) and item.generation == reserved for item in notices
    )


def test_effect_failure_echoes_effect_stamp_not_mutable_health_generation():
    active = _generation()
    reserved = replace(active, stream_generation=23)
    effect = _effect(
        "subscribe-23",
        kind=EffectKind.SUBSCRIBE_EVENTS,
        generation=reserved,
        idempotent=False,
    )
    notices = []

    def handler(_effect_value, _publish):
        raise GatewayEffectError(
            "transport_down",
            "transport unavailable",
            status=CompletionStatus.TRANSPORT_ERROR,
            retryable=True,
        )

    gateway = WorkerThreadExecutiveGateway(handler, GatewayHealthTracker(active))
    gateway.start(notices.append)
    gateway.submit(effect)
    _wait_for(lambda: any(isinstance(item, GatewayCompletion) for item in notices))
    gateway.close()

    completion = next(item for item in notices if isinstance(item, GatewayCompletion))
    assert completion.generation is reserved
    assert completion.status is CompletionStatus.TRANSPORT_ERROR
    assert completion.failure is not None
    assert completion.failure.retryable is False
    rpc_notice = next(item for item in notices if isinstance(item, HealthNotice))
    assert rpc_notice.generation is active
    assert rpc_notice.rpc_health is RpcHealth.LOST


def test_operation_retry_requires_idempotent_exact_same_effect_and_stamp():
    calls = []
    notices = []

    def handler(effect, _publish):
        calls.append(effect)
        return _completion(effect)

    gateway = WorkerThreadExecutiveGateway(handler, GatewayHealthTracker(_generation()))
    gateway.start(notices.append)
    first = _effect("write", idempotent=False)
    gateway.submit(first)
    gateway.submit(first)
    altered = _effect(
        "write",
        generation=replace(_generation(), target_generation=99),
        idempotent=False,
    )
    gateway.submit(altered)
    _wait_for(lambda: len([item for item in notices if isinstance(item, GatewayCompletion)]) == 3)
    gateway.close()

    completions = [item for item in notices if isinstance(item, GatewayCompletion)]
    assert len(calls) == 1
    assert [item.status for item in completions] == [
        CompletionStatus.OK,
        CompletionStatus.REJECTED,
        CompletionStatus.PROTOCOL_ERROR,
    ]
    assert completions[2].generation == altered.generation


def test_exact_idempotent_retry_is_the_only_duplicate_sent_to_handler():
    calls = []
    notices = []

    def handler(effect, _publish):
        calls.append(effect)
        return _completion(effect)

    gateway = WorkerThreadExecutiveGateway(handler, GatewayHealthTracker(_generation()))
    gateway.start(notices.append)
    effect = _effect("read", idempotent=True)
    gateway.submit(effect)
    gateway.submit(effect)
    _wait_for(lambda: len(notices) == 2)
    gateway.close()

    assert calls == [effect, effect]
    assert all(item.generation is effect.generation for item in notices)


def test_sink_failure_is_retained_as_event_health_degradation():
    health = GatewayHealthTracker(_generation(), event_health=EventHealth.HEALTHY)
    received = []
    calls = 0

    def sink(notice):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("consumer failed")
        received.append(notice)

    gateway = WorkerThreadExecutiveGateway(lambda effect, _: _completion(effect), health)
    gateway.start(sink)
    gateway.submit(_effect("op-1"))
    gateway.submit(_effect("op-2"))
    _wait_for(lambda: any(isinstance(item, GatewayCompletion) for item in received))
    gateway.close()

    assert health.snapshot().event_health is EventHealth.GAP
    assert "RuntimeError" in (gateway.last_sink_error or "")
    degradation = next(item for item in received if isinstance(item, HealthNotice))
    assert "notice sink failed" in degradation.reason
    assert degradation.generation == _generation()


def test_bounded_queue_surfaces_saturation_without_unbounded_growth():
    health = GatewayHealthTracker(_generation())
    entered = threading.Event()
    release = threading.Event()

    def handler(effect, _publish):
        entered.set()
        release.wait(1.0)
        return _completion(effect)

    gateway = WorkerThreadExecutiveGateway(handler, health, queue_capacity=1)
    gateway.start(lambda _notice: None)
    gateway.submit(_effect("op-1"))
    assert entered.wait(1.0)
    gateway.submit(_effect("op-2"))
    with pytest.raises(GatewayQueueFullError):
        gateway.submit(_effect("op-3"))
    assert health.snapshot().rpc_health is RpcHealth.DEGRADED
    release.set()
    gateway.close()
    assert gateway.is_alive is False


def test_close_is_idempotent_self_join_safe_and_bounded_for_slow_cleanup():
    cleanup_entered = threading.Event()
    cleanup_release = threading.Event()
    sink_returned = threading.Event()
    gateway = None

    def cleanup():
        cleanup_entered.set()
        cleanup_release.wait(1.0)

    def sink(_notice):
        assert gateway is not None
        gateway.close()
        sink_returned.set()

    gateway = WorkerThreadExecutiveGateway(
        lambda effect, _: _completion(effect),
        GatewayHealthTracker(_generation()),
        close_timeout=0.02,
        on_close=cleanup,
    )
    gateway.start(sink)
    gateway.submit(_effect("op-1"))
    assert sink_returned.wait(1.0)
    assert cleanup_entered.wait(1.0)

    started = time.monotonic()
    gateway.close()
    assert time.monotonic() - started < 0.2
    cleanup_release.set()
    _wait_for(lambda: not gateway.is_alive)
    gateway.close()


def test_gateway_rejects_start_reuse_and_submit_after_close():
    gateway = WorkerThreadExecutiveGateway(
        lambda effect, _: _completion(effect),
        GatewayHealthTracker(_generation()),
    )
    gateway.start(lambda _notice: None)
    with pytest.raises(RuntimeError, match="already started"):
        gateway.start(lambda _notice: None)
    gateway.close()
    with pytest.raises(RuntimeError, match="closed"):
        gateway.submit(_effect("late"))
