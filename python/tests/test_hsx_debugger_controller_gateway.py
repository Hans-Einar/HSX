from __future__ import annotations

from concurrent.futures import Future
from dataclasses import replace
from pathlib import Path
import queue
import sys
import threading
import time
from typing import Any, Callable


REPO_ROOT = Path(__file__).resolve().parents[2]
PYTHON_SRC = REPO_ROOT / "python"
if str(PYTHON_SRC) not in sys.path:
    sys.path.insert(0, str(PYTHON_SRC))

from hsx_debugger.contracts import (
    CapabilityProfile,
    CommandResult,
    CommandStatus,
    CompletionAuthority,
    CompletionStatus,
    ControllerCommand,
    ControllerEvent,
    DeadlineExpired,
    EffectKind,
    EventGap,
    EventHealth,
    EvidenceGrade,
    GatewayCompletion,
    GatewayEffect,
    GatewayEvent,
    GatewayFailure,
    GatewayNotice,
    GenerationStamp,
    ReconcileResult,
    ReconcileStatus,
    RecoveryStatus,
    RpcHealth,
    TargetRunState,
)
from hsx_debugger.controller import ControllerActor
from hsx_debugger.gateway import NoticePublisher, WorkerThreadExecutiveGateway
from hsx_debugger.health import GatewayHealthTracker
from hsx_debugger.legacy_gateway import (
    LEGACY_EVENT_CAPABILITY,
    LEGACY_PROFILE_ID,
    LEGACY_RESOURCE_CAPABILITY,
    LegacyExecutiveGateway,
    initial_legacy_generation,
)
from hsx_debugger.runtime import ControllerGatewayRuntime


def _wait_for(predicate: Callable[[], bool], timeout: float = 1.5) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.005)
    raise AssertionError("condition was not satisfied before timeout")


def _snapshot(runtime: ControllerGatewayRuntime):
    return runtime.controller.snapshot().result(timeout=1.0)


def _wait_snapshot(runtime: ControllerGatewayRuntime, predicate: Callable[[Any], bool]):
    observed = None

    def matches() -> bool:
        nonlocal observed
        observed = _snapshot(runtime)
        return bool(predicate(observed))

    _wait_for(matches)
    return observed


def _completion(
    effect: GatewayEffect,
    *,
    status: CompletionStatus = CompletionStatus.OK,
    authority: CompletionAuthority = CompletionAuthority.ACK_ONLY,
    response: dict[str, Any] | None = None,
    failure: GatewayFailure | None = None,
    operation_id: str | None = None,
    generation: GenerationStamp | None = None,
) -> GatewayCompletion:
    stamp = generation or effect.generation
    return GatewayCompletion(
        operation_id=operation_id or effect.operation_id,
        generation=stamp,
        status=status,
        evidence_grade=stamp.evidence_grade,
        response=response or {},
        failure=failure,
        authority=authority,
    )


def _event(
    generation: GenerationStamp,
    *,
    sequence: int,
    state: str,
    stream_id: str = "legacy-stream-active",
    operation_id: str | None = None,
    gap: EventGap | None = None,
) -> GatewayEvent:
    payload: dict[str, Any] = {"state": state}
    if operation_id is not None:
        payload["operation_id"] = operation_id
    return GatewayEvent(
        generation=generation,
        stream_id=stream_id,
        sequence=sequence,
        category="task_state",
        payload=payload,
        evidence_grade=EvidenceGrade.LEGACY_DEGRADED,
        gap=gap,
    )


def _legacy_profile(generation: GenerationStamp) -> CapabilityProfile:
    return CapabilityProfile(
        profile_id=LEGACY_PROFILE_ID,
        generation=generation.capability_generation,
        capabilities=frozenset({LEGACY_EVENT_CAPABILITY, LEGACY_RESOURCE_CAPABILITY}),
        degraded=True,
        diagnostics=("portable_identity=false", "event_resume=false"),
    )


class _AckHandler:
    def __init__(self) -> None:
        self.effects: queue.Queue[GatewayEffect] = queue.Queue()

    def __call__(
        self, effect: GatewayEffect, publish: NoticePublisher
    ) -> GatewayNotice:
        del publish
        self.effects.put(effect)
        return _completion(effect)


class _LegacySessionFixture:
    """Small unchanged-Executive seam used only by the real legacy gateway adapter."""

    def __init__(self) -> None:
        self.negotiated_features = ["events", "watch"]
        self.session_id = None
        self.session_disabled = False
        self.requests: list[tuple[dict[str, Any], bool, bool]] = []
        self.configurations: list[dict[str, Any]] = []
        self.close_calls = 0
        self.stop_event_calls = 0

    def configure_session(self, **kwargs: Any) -> None:
        self.configurations.append(dict(kwargs))

    def request(
        self, payload: dict[str, Any], *, use_session: bool = True, retry: bool = True
    ) -> dict[str, Any]:
        self.requests.append((dict(payload), use_session, retry))
        self.session_id = self.session_id or "legacy-session-fixture"
        return {"status": "ok", "tasks": []}

    def start_observed_event_stream(self, **kwargs: Any) -> bool:
        del kwargs
        return False

    def stop_event_stream(self) -> None:
        self.stop_event_calls += 1

    def close(self) -> None:
        self.close_calls += 1


def _worker_runtime(
    handler: Callable[[GatewayEffect, NoticePublisher], Any],
    generation: GenerationStamp,
    *,
    on_close: Callable[[], None] | None = None,
) -> tuple[ControllerGatewayRuntime, WorkerThreadExecutiveGateway, GatewayHealthTracker]:
    health = GatewayHealthTracker(generation)
    gateway = WorkerThreadExecutiveGateway(
        handler,
        health,
        queue_capacity=64,
        close_timeout=1.0,
        on_close=on_close,
    )
    runtime = ControllerGatewayRuntime(gateway, initial_generation=generation)
    return runtime, gateway, health


def test_runtime_owns_actual_ports_and_start_close_are_idempotent() -> None:
    active = initial_legacy_generation()
    handler = _AckHandler()
    close_calls = 0

    def on_close() -> None:
        nonlocal close_calls
        close_calls += 1

    runtime, gateway, _ = _worker_runtime(handler, active, on_close=on_close)
    assert runtime.controller.__class__ is ControllerActor
    assert runtime.gateway is gateway

    runtime.start()
    runtime.start()
    assert runtime.started
    assert runtime.controller.actor_thread_alive
    assert gateway.is_alive

    runtime.close()
    runtime.close()
    assert runtime.closed
    assert not runtime.controller.actor_thread_alive
    assert not runtime.controller.effect_thread_alive
    assert not gateway.is_alive
    assert close_calls == 1


def test_real_legacy_open_promotes_typed_degraded_capability_and_health() -> None:
    active = initial_legacy_generation(display_pid=7)
    session = _LegacySessionFixture()
    gateway = LegacyExecutiveGateway(session, initial_generation=active)
    runtime = ControllerGatewayRuntime(gateway, initial_generation=active)
    runtime.start()
    try:
        result = runtime.controller.submit(
            ControllerCommand(
                "open-legacy",
                "open_session",
                payload={"pid_lock": 7, "heartbeat_s": 12},
            )
        ).result(timeout=1.0)
        snapshot = _wait_snapshot(
            runtime,
            lambda item: item.rpc_health is RpcHealth.HEALTHY,
        )

        assert result.status is CommandStatus.COMPLETED
        assert snapshot.generation.session_generation == 1
        assert snapshot.generation.stream_generation == 0
        assert snapshot.event_health is EventHealth.DISABLED
        assert snapshot.capability_profile is not None
        assert snapshot.capability_profile.profile_id == LEGACY_PROFILE_ID
        assert snapshot.capability_profile.degraded is True
        assert snapshot.capability_profile.capabilities == frozenset(
            {LEGACY_EVENT_CAPABILITY, LEGACY_RESOURCE_CAPABILITY}
        )
        assert session.requests == [({"cmd": "ps"}, True, True)]
        assert session.configurations == [{"pid_lock": 7, "heartbeat_s": 12}]
    finally:
        runtime.close()
    assert session.close_calls == 1


def test_ack_is_not_state_authority_and_matching_task_event_completes_exact_future() -> None:
    active = initial_legacy_generation(display_pid=7)
    handler = _AckHandler()
    runtime, gateway, _ = _worker_runtime(handler, active)
    controller_events: list[ControllerEvent] = []
    runtime.start()
    subscription = runtime.controller.subscribe(controller_events.append)
    try:
        assert gateway.publish_notice(_event(active, sequence=1, state="running"))
        _wait_snapshot(runtime, lambda item: item.target_state is TargetRunState.RUNNING)

        command_future: Future[CommandResult] = runtime.controller.submit(
            ControllerCommand("pause-1", "pause")
        )
        effect = handler.effects.get(timeout=1.0)
        pending = _wait_snapshot(
            runtime,
            lambda item: item.target_state is TargetRunState.STOP_PENDING,
        )
        assert effect.kind is EffectKind.REQUEST
        assert effect.operation_id in pending.pending_operation_ids
        assert not command_future.done()

        assert gateway.publish_notice(
            _event(
                active,
                sequence=2,
                state="stopped",
                operation_id=effect.operation_id,
            )
        )
        result = command_future.result(timeout=1.0)
        stopped = _wait_snapshot(
            runtime,
            lambda item: item.target_state is TargetRunState.STOPPED,
        )
        assert result.status is CommandStatus.COMPLETED
        assert result.operation_id == effect.operation_id
        assert stopped.pending_operation_ids == ()
        assert stopped.active_epoch is not None
        assert stopped.active_epoch.evidence_grade is EvidenceGrade.LEGACY_DEGRADED
        _wait_for(
            lambda: sum(
                event.kind == "target_state_changed"
                and event.payload.get("target_state") == "stopped"
                for event in controller_events
            )
            == 1
        )
    finally:
        subscription.close()
        runtime.close()


def test_stale_completion_and_event_are_ignored_across_real_gateway_port() -> None:
    active = initial_legacy_generation(display_pid=7)
    handler = _AckHandler()
    runtime, gateway, _ = _worker_runtime(handler, active)
    runtime.start()
    try:
        command = runtime.controller.submit(ControllerCommand("request-1", "request"))
        effect = handler.effects.get(timeout=1.0)
        assert command.result(timeout=1.0).status is CommandStatus.COMPLETED
        before = _snapshot(runtime)
        stale = replace(
            active,
            session_generation=active.session_generation + 9,
            capability_generation=active.capability_generation + 9,
        )

        assert gateway.publish_notice(_completion(effect, generation=stale))
        assert gateway.publish_notice(_event(stale, sequence=1, state="stopped"))
        _wait_for(lambda: gateway.last_notice_error is not None)
        after = _snapshot(runtime)

        assert after == before
        assert after.generation == active
    finally:
        runtime.close()


class _LegacyReconcileHandler(_AckHandler):
    def __call__(
        self, effect: GatewayEffect, publish: NoticePublisher
    ) -> GatewayNotice:
        del publish
        self.effects.put(effect)
        if effect.kind is EffectKind.RECONCILE:
            return ReconcileResult(
                generation=effect.generation,
                status=ReconcileStatus.LEGACY_UNPROVEN,
                evidence_grade=effect.generation.evidence_grade,
                baseline={"target_state": "stopped", "stop_token": "unproven"},
                diagnostics=("portable_target_identity=false",),
            )
        return _completion(effect)


def test_gap_invalidates_epoch_and_legacy_unproven_reconcile_cannot_retain() -> None:
    active = initial_legacy_generation(display_pid=7)
    handler = _LegacyReconcileHandler()
    runtime, gateway, _ = _worker_runtime(handler, active)
    runtime.start()
    try:
        assert gateway.publish_notice(_event(active, sequence=1, state="stopped"))
        stopped = _wait_snapshot(runtime, lambda item: item.active_epoch is not None)
        assert stopped.target_state is TargetRunState.STOPPED

        gap = EventGap(
            expected_sequence=2,
            observed_sequence=3,
            reason="fixture loss",
            reconciliation_required=True,
        )
        assert gateway.publish_notice(
            _event(active, sequence=3, state="running", gap=gap)
        )
        lost = _wait_snapshot(
            runtime,
            lambda item: item.event_health is EventHealth.GAP,
        )
        assert lost.active_epoch is None
        assert lost.target_state is TargetRunState.UNKNOWN
        assert lost.recovery_status is RecoveryStatus.REQUIRED

        reconciliation = runtime.controller.submit(
            ControllerCommand("reconcile-legacy", "reconcile")
        )
        effect = handler.effects.get(timeout=1.0)
        assert effect.kind is EffectKind.RECONCILE
        result = reconciliation.result(timeout=1.0)
        reconciled = _snapshot(runtime)
        assert result.status is CommandStatus.FAILED
        assert result.error == "RecoveryFailed"
        assert reconciled.active_epoch is None
        assert reconciled.target_state is TargetRunState.UNKNOWN
        assert reconciled.recovery_status is RecoveryStatus.REQUIRED
        assert reconciled.event_health is EventHealth.GAP
    finally:
        runtime.close()


def test_event_health_loss_invalidates_epoch_and_requires_reconcile() -> None:
    active = initial_legacy_generation(display_pid=7)
    handler = _AckHandler()
    runtime, gateway, health = _worker_runtime(handler, active)
    runtime.start()
    try:
        assert gateway.publish_notice(_event(active, sequence=1, state="stopped"))
        _wait_snapshot(runtime, lambda item: item.active_epoch is not None)

        loss = health.transition(
            event_health=EventHealth.LOST,
            reason="fixture event reader reached EOF; reconciliation required",
        )
        assert gateway.publish_notice(loss)
        lost = _wait_snapshot(
            runtime,
            lambda item: item.event_health is EventHealth.LOST,
        )
        assert lost.active_epoch is None
        assert lost.target_state is TargetRunState.UNKNOWN
        assert lost.recovery_status is RecoveryStatus.REQUIRED
    finally:
        runtime.close()


class _BlockingAckHandler:
    def __init__(self) -> None:
        self.effect: GatewayEffect | None = None
        self.entered = threading.Event()
        self.release = threading.Event()

    def __call__(
        self, effect: GatewayEffect, publish: NoticePublisher
    ) -> GatewayNotice:
        del publish
        self.effect = effect
        self.entered.set()
        if not self.release.wait(1.0):
            raise TimeoutError("test did not release gateway handler")
        return _completion(effect)


def test_deadline_fails_operation_without_synthetic_target_state() -> None:
    active = initial_legacy_generation(display_pid=7)
    handler = _BlockingAckHandler()
    runtime, gateway, _ = _worker_runtime(handler, active)
    controller_events: queue.Queue[ControllerEvent] = queue.Queue()
    runtime.start()
    subscription = runtime.controller.subscribe(controller_events.put)
    try:
        assert gateway.publish_notice(_event(active, sequence=1, state="stopped"))
        before = _wait_snapshot(runtime, lambda item: item.active_epoch is not None)

        command_future = runtime.controller.submit(
            ControllerCommand("deadline-request", "request")
        )
        assert handler.entered.wait(1.0)
        accepted = None
        deadline = time.monotonic() + 1.0
        while accepted is None and time.monotonic() < deadline:
            event = controller_events.get(timeout=1.0)
            if event.kind == "command_accepted" and event.payload.get("command_id") == "deadline-request":
                accepted = event
        assert accepted is not None
        operation_id = accepted.payload["operation_id"]
        deadline_id = accepted.payload["deadline_id"]
        assert isinstance(operation_id, str)
        assert isinstance(deadline_id, str)

        runtime.controller.accept_deadline(
            DeadlineExpired(deadline_id, operation_id, active)
        )
        result = command_future.result(timeout=1.0)
        after = _snapshot(runtime)
        assert result.status is CommandStatus.FAILED
        assert result.error == "OperationTimeout"
        assert after.target_state is TargetRunState.STOPPED
        assert after.active_epoch == before.active_epoch
        assert after.recovery_status is before.recovery_status

        handler.release.set()
        _wait_for(lambda: handler.effect is not None)
        assert command_future.result(timeout=0) is result
    finally:
        handler.release.set()
        subscription.close()
        runtime.close()


class _ReservationHandler:
    def __init__(self) -> None:
        self.effects: queue.Queue[GatewayEffect] = queue.Queue()
        self.block_entered = threading.Event()
        self.block_release = threading.Event()

    def __call__(
        self, effect: GatewayEffect, publish: NoticePublisher
    ) -> GatewayNotice:
        del publish
        self.effects.put(effect)
        mode = effect.payload.get("fixture_mode", "success")
        if mode == "block":
            self.block_entered.set()
            if not self.block_release.wait(1.0):
                raise TimeoutError("test did not release reserved resource handler")
        if mode == "fail":
            return _completion(
                effect,
                status=CompletionStatus.REJECTED,
                failure=GatewayFailure("fixture_rejected", "fixture rejected resource", False),
            )
        response: dict[str, Any] = {}
        if effect.kind is EffectKind.OPEN_SESSION:
            response["capability_profile"] = _legacy_profile(effect.generation)
        elif effect.kind is EffectKind.SUBSCRIBE_EVENTS:
            response["stream_id"] = f"legacy-stream-{effect.generation.stream_generation}"
        return _completion(
            effect,
            authority=CompletionAuthority.AUTHORITATIVE_RESOURCE_ESTABLISHED,
            response=response,
        )


def test_reserve_failure_burn_old_continuity_promotion_and_late_rejection() -> None:
    active = initial_legacy_generation()
    handler = _ReservationHandler()
    runtime, gateway, _ = _worker_runtime(handler, active)
    controller_events: list[ControllerEvent] = []
    runtime.start()
    subscription = runtime.controller.subscribe(controller_events.append)
    try:
        failed_open = runtime.controller.submit(
            ControllerCommand(
                "open-failed", "open_session", payload={"fixture_mode": "fail"}
            )
        )
        failed_effect = handler.effects.get(timeout=1.0)
        failed_result = failed_open.result(timeout=1.0)
        after_failure = _snapshot(runtime)
        assert failed_result.status is CommandStatus.FAILED
        assert failed_effect.generation.session_generation == 1
        assert after_failure.generation == active

        successful_open = runtime.controller.submit(
            ControllerCommand("open-next", "open_session")
        )
        open_effect = handler.effects.get(timeout=1.0)
        assert successful_open.result(timeout=1.0).status is CommandStatus.COMPLETED
        opened = _snapshot(runtime)
        assert open_effect.generation.session_generation == 2
        assert opened.generation == open_effect.generation
        assert opened.generation.stream_generation == 0

        first_subscription = runtime.controller.submit(
            ControllerCommand("subscribe-first", "subscribe_events")
        )
        first_sub_effect = handler.effects.get(timeout=1.0)
        assert first_subscription.result(timeout=1.0).status is CommandStatus.COMPLETED
        stream_one = _snapshot(runtime)
        assert first_sub_effect.generation.stream_generation == 1
        assert stream_one.generation == first_sub_effect.generation

        stream_one_id = "legacy-stream-1"
        assert gateway.publish_notice(
            _event(
                stream_one.generation,
                sequence=1,
                state="stopped",
                stream_id=stream_one_id,
            )
        )
        old_stopped = _wait_snapshot(runtime, lambda item: item.active_epoch is not None)

        replacement = runtime.controller.submit(
            ControllerCommand(
                "subscribe-replacement",
                "subscribe_events",
                payload={"fixture_mode": "block"},
            )
        )
        replacement_effect = handler.effects.get(timeout=1.0)
        assert handler.block_entered.wait(1.0)
        while_pending = _snapshot(runtime)
        assert replacement_effect.generation.stream_generation == 2
        assert while_pending.generation == stream_one.generation
        assert while_pending.active_epoch == old_stopped.active_epoch
        assert not replacement.done()

        # This exact old-active event is queued while resource establishment blocks.  The
        # actual gateway drains its bounded old-continuity snapshot before the completion.
        assert gateway.publish_notice(
            _event(
                stream_one.generation,
                sequence=2,
                state="running",
                stream_id=stream_one_id,
            )
        )
        handler.block_release.set()
        assert replacement.result(timeout=1.0).status is CommandStatus.COMPLETED
        promoted = _wait_snapshot(
            runtime,
            lambda item: item.generation == replacement_effect.generation,
        )
        assert promoted.active_epoch is None
        assert promoted.generation.stream_generation == 2
        _wait_for(
            lambda: any(
                event.kind == "generation_promoted"
                and event.payload.get("operation_id") == replacement_effect.operation_id
                for event in controller_events
            )
        )
        state_event_index = next(
            index
            for index, event in enumerate(controller_events)
            if event.kind == "target_state_changed"
            and event.payload.get("target_state") == "running"
            and event.generation == stream_one.generation
        )
        promotion_index = next(
            index
            for index, event in enumerate(controller_events)
            if event.kind == "generation_promoted"
            and event.payload.get("operation_id") == replacement_effect.operation_id
        )
        assert state_event_index < promotion_index

        revision = promoted.controller_revision
        assert gateway.publish_notice(
            _event(
                stream_one.generation,
                sequence=3,
                state="stopped",
                stream_id=stream_one_id,
            )
        )
        _wait_for(lambda: gateway.last_notice_error is not None)
        assert _snapshot(runtime).controller_revision == revision

        late_failed_success = _completion(
            failed_effect,
            authority=CompletionAuthority.AUTHORITATIVE_RESOURCE_ESTABLISHED,
            response={"capability_profile": _legacy_profile(failed_effect.generation)},
        )
        assert gateway.publish_notice(late_failed_success)
        _wait_for(
            lambda: any(
                event.kind == "unknown_gateway_completion"
                and event.payload.get("operation_id") == failed_effect.operation_id
                for event in controller_events
            )
        )
        final = _snapshot(runtime)
        assert final.generation == replacement_effect.generation
        assert final.generation.session_generation == 2
        assert final.generation.stream_generation == 2
    finally:
        handler.block_release.set()
        subscription.close()
        runtime.close()
