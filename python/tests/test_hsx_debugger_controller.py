from __future__ import annotations

from dataclasses import replace
import itertools
from pathlib import Path
import queue
import sys
import threading
import time

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
PYTHON_SRC = REPO_ROOT / "python"
if str(PYTHON_SRC) not in sys.path:
    sys.path.insert(0, str(PYTHON_SRC))

from hsx_debugger.contracts import (
    CapabilityProfile,
    CommandStatus,
    CompletionAuthority,
    CompletionStatus,
    ControllerCommand,
    DeadlineExpired,
    EventGap,
    EventHealth,
    EvidenceGrade,
    GatewayCompletion,
    GatewayEffect,
    GatewayEvent,
    GenerationStamp,
    HealthNotice,
    ReconcileResult,
    ReconcileStatus,
    RecoveryStatus,
    RpcHealth,
    TargetRunState,
)
from hsx_debugger.controller import ControllerActor, ControllerInboxFullError
from hsx_debugger.model import initial_legacy_model
from hsx_debugger.reducer import reduce_command, reduce_deadline, reduce_notice


def generation(session: int = 3, stream: int = 4) -> GenerationStamp:
    return GenerationStamp(
        executive_instance_id=None,
        session_generation=session,
        target_id=None,
        target_generation=2,
        capability_generation=session,
        stream_generation=stream,
        display_pid=42,
        evidence_grade=EvidenceGrade.LEGACY_DEGRADED,
    )


def event(
    stamp: GenerationStamp,
    category: str,
    *,
    sequence: int = 1,
    stream_id: str = "stream-old",
    payload: dict[str, object] | None = None,
) -> GatewayEvent:
    return GatewayEvent(
        generation=stamp,
        stream_id=stream_id,
        sequence=sequence,
        category=category,
        payload=payload or {},
        evidence_grade=stamp.evidence_grade,
    )


def completion(
    effect: GatewayEffect,
    *,
    status: CompletionStatus = CompletionStatus.OK,
    authority: CompletionAuthority = CompletionAuthority.ACK_ONLY,
    operation_id: str | None = None,
    generation_stamp: GenerationStamp | None = None,
    response: dict[str, object] | None = None,
) -> GatewayCompletion:
    stamp = generation_stamp or effect.generation
    return GatewayCompletion(
        operation_id=operation_id or effect.operation_id,
        generation=stamp,
        status=status,
        evidence_grade=stamp.evidence_grade,
        response=response or {},
        authority=authority,
    )


def profile(stamp: GenerationStamp) -> CapabilityProfile:
    return CapabilityProfile(
        profile_id="hsx.python-debug-legacy/1",
        generation=stamp.capability_generation,
        capabilities=frozenset({"hsx.legacy-event-stream/1"}),
        degraded=True,
        diagnostics=("portable continuity unavailable",),
    )


def deterministic_ids():
    counter = itertools.count(1)
    return lambda kind: f"{kind}-{next(counter)}"


def test_open_reserves_before_dispatch_and_ack_only_keeps_old_continuity_pending() -> None:
    active = generation()
    model = initial_legacy_model(active)
    accepted = reduce_command(
        model, ControllerCommand("connect-1", "open_session"), "open-op"
    )
    operation = accepted.model.pending_operations["open-op"]
    effect = accepted.effects[0]

    assert accepted.model.generation == active
    assert accepted.model.generation_watermarks.session == 4
    assert operation.reservation is not None
    assert operation.reservation.reserved_stamp == effect.generation
    assert effect.generation.session_generation == 4
    assert effect.generation.stream_generation == 0

    acknowledged = reduce_notice(accepted.model, completion(effect))
    assert acknowledged.model is accepted.model
    assert "open-op" in acknowledged.model.pending_operations
    assert acknowledged.events[0].kind == "operation_acknowledged"


def test_authoritative_open_promotes_exact_reservation_and_invalidates_old_epoch() -> None:
    active = generation()
    stopped = reduce_notice(
        initial_legacy_model(active), event(active, "stopped"), epoch_id="epoch-old"
    ).model
    accepted = reduce_command(
        stopped, ControllerCommand("connect-1", "open_session"), "open-op"
    )
    effect = accepted.effects[0]
    promoted = reduce_notice(
        accepted.model,
        completion(
            effect,
            authority=CompletionAuthority.AUTHORITATIVE_RESOURCE_ESTABLISHED,
            response={"capability_profile": profile(effect.generation)},
        ),
    )

    assert promoted.model.generation == effect.generation
    assert promoted.model.generation_watermarks.session == 4
    assert promoted.model.generation_watermarks.stream == 0
    assert promoted.model.capability_profile == profile(effect.generation)
    assert promoted.model.epoch_store.active is None
    assert "epoch-old" in promoted.model.epoch_store.invalidated_epoch_ids
    assert promoted.model.pending_operations == {}
    assert promoted.events[0].kind == "generation_promoted"

    replay = reduce_notice(
        promoted.model,
        completion(
            effect,
            authority=CompletionAuthority.AUTHORITATIVE_RESOURCE_ESTABLISHED,
            response={"capability_profile": profile(effect.generation)},
        ),
    )
    assert replay.model is promoted.model
    assert replay.events[0].kind == "unknown_gateway_completion"


def test_failed_open_burns_then_new_operation_advances_without_promoting() -> None:
    active = generation()
    first = reduce_command(
        initial_legacy_model(active), ControllerCommand("connect-1", "open_session"), "open-1"
    )
    failed = reduce_notice(
        first.model,
        completion(first.effects[0], status=CompletionStatus.TRANSPORT_ERROR),
    )

    assert failed.model.generation == active
    assert failed.model.generation_watermarks.session == 4
    assert failed.model.pending_operations == {}

    second = reduce_command(
        failed.model, ControllerCommand("connect-2", "open_session"), "open-2"
    )
    assert second.effects[0].generation.session_generation == 5
    assert second.model.generation_watermarks.session == 5


def test_failed_subscribe_burns_stream_only_and_same_operation_retry_reuses() -> None:
    active = generation()
    command = ControllerCommand("subscribe-1", "subscribe_events")
    first = reduce_command(initial_legacy_model(active), command, "sub-op")
    retried = reduce_command(first.model, command, "sub-op")

    assert retried.model is first.model
    assert retried.effects[0] is first.effects[0]
    assert first.model.generation_watermarks.session == 3
    assert first.model.generation_watermarks.stream == 5

    failed = reduce_notice(
        first.model,
        completion(first.effects[0], status=CompletionStatus.CANCELLED),
    )
    assert failed.model.generation == active
    assert failed.model.generation_watermarks.session == 3
    assert failed.model.generation_watermarks.stream == 5

    retired_retry = reduce_command(failed.model, command, "sub-op")
    assert retired_retry.model is failed.model
    assert retired_retry.effects == ()
    assert retired_retry.results[0].error == "StaleOperation"

    next_operation = reduce_command(
        failed.model,
        ControllerCommand("subscribe-2", "subscribe_events"),
        "sub-op-2",
    )
    assert next_operation.effects[0].generation.stream_generation == 6


def test_pending_subscribe_keeps_old_events_and_fences_premature_new_events() -> None:
    active = generation()
    pending = reduce_command(
        initial_legacy_model(active),
        ControllerCommand("subscribe-1", "subscribe_events"),
        "sub-op",
    )
    effect = pending.effects[0]

    old_event = reduce_notice(
        pending.model,
        event(active, "stopped", sequence=8),
        epoch_id="epoch-old",
    )
    assert old_event.model.target_state is TargetRunState.STOPPED
    assert "sub-op" in old_event.model.pending_operations

    premature = reduce_notice(
        old_event.model,
        event(effect.generation, "running", sequence=1, stream_id="stream-new"),
        epoch_id="unused",
    )
    assert premature.model is old_event.model
    assert premature.events[0].kind == "stale_gateway_event"

    promoted = reduce_notice(
        old_event.model,
        completion(
            effect,
            authority=CompletionAuthority.AUTHORITATIVE_RESOURCE_ESTABLISHED,
            response={"stream_id": "stream-new"},
        ),
    )
    assert promoted.model.generation == effect.generation
    assert promoted.model.target_state is TargetRunState.UNKNOWN
    assert promoted.model.epoch_store.active is None

    late_old = reduce_notice(
        promoted.model,
        event(active, "running", sequence=9),
        epoch_id="unused",
    )
    assert late_old.model is promoted.model
    accepted_new = reduce_notice(
        promoted.model,
        event(effect.generation, "running", sequence=1, stream_id="stream-new"),
        epoch_id="unused",
    )
    assert accepted_new.model.target_state is TargetRunState.RUNNING


def test_wrong_operation_parent_stamp_and_numeric_higher_completion_never_adopt() -> None:
    active = generation()
    accepted = reduce_command(
        initial_legacy_model(active), ControllerCommand("connect-1", "open_session"), "open-right"
    )
    effect = accepted.effects[0]
    wrong_operation = completion(
        effect,
        authority=CompletionAuthority.AUTHORITATIVE_RESOURCE_ESTABLISHED,
        operation_id="open-wrong",
        response={"capability_profile": profile(effect.generation)},
    )
    higher = replace(effect.generation, session_generation=99, capability_generation=99)
    numeric_higher = completion(
        effect,
        authority=CompletionAuthority.AUTHORITATIVE_RESOURCE_ESTABLISHED,
        generation_stamp=higher,
    )

    for notice in (wrong_operation, numeric_higher):
        rejected = reduce_notice(accepted.model, notice)
        assert rejected.model is accepted.model
        assert rejected.model.generation == active
        assert "open-right" in rejected.model.pending_operations


def test_session_promotion_retires_pending_old_parent_stream_reservation() -> None:
    active = generation()
    stream_pending = reduce_command(
        initial_legacy_model(active),
        ControllerCommand("subscribe-1", "subscribe_events"),
        "sub-op",
    )
    open_pending = reduce_command(
        stream_pending.model,
        ControllerCommand("connect-1", "open_session"),
        "open-op",
    )
    open_effect = open_pending.effects[0]
    promoted = reduce_notice(
        open_pending.model,
        completion(
            open_effect,
            authority=CompletionAuthority.AUTHORITATIVE_RESOURCE_ESTABLISHED,
            response={"capability_profile": profile(open_effect.generation)},
        ),
    )

    assert promoted.model.pending_operations == {}
    assert promoted.model.generation_watermarks.stream == 0
    assert any(item.operation_id == "sub-op" for item in promoted.results)
    late_stream = reduce_notice(
        promoted.model,
        completion(
            stream_pending.effects[0],
            authority=CompletionAuthority.AUTHORITATIVE_RESOURCE_ESTABLISHED,
        ),
    )
    assert late_stream.model is promoted.model


def test_rpc_ok_for_control_waits_for_authoritative_event_and_keeps_deadline_live() -> None:
    stamp = generation()
    stopped = reduce_notice(
        initial_legacy_model(stamp), event(stamp, "stopped"), epoch_id="epoch-1"
    ).model
    accepted = reduce_command(stopped, ControllerCommand("c1", "continue"), "op-1")

    assert accepted.model.target_state is TargetRunState.RUN_PENDING
    assert accepted.model.epoch_store.active is None
    acknowledged = reduce_notice(accepted.model, completion(accepted.effects[0]))
    assert acknowledged.model is accepted.model
    assert "op-1" in acknowledged.model.pending_operations

    running = reduce_notice(
        acknowledged.model,
        event(stamp, "running", sequence=2, payload={"operation_id": "op-1"}),
        epoch_id="unused",
    )
    assert running.model.target_state is TargetRunState.RUNNING
    assert "op-1" not in running.model.pending_operations


def test_matching_reserved_deadline_burns_without_promoting_and_wrong_deadline_is_stale() -> None:
    active = generation()
    accepted = reduce_command(
        initial_legacy_model(active),
        ControllerCommand("subscribe-1", "subscribe_events"),
        "sub-op",
    )
    wrong = reduce_deadline(
        accepted.model, DeadlineExpired("deadline-wrong", "sub-op", active)
    )
    assert wrong.model is accepted.model

    expired = reduce_deadline(
        accepted.model,
        DeadlineExpired("deadline-right", "sub-op", accepted.effects[0].generation),
    )
    assert expired.model.generation == active
    assert expired.model.generation_watermarks.stream == 5
    assert expired.model.pending_operations == {}
    assert expired.results[0].error == "OperationTimeout"


def test_stale_active_completion_event_and_deadline_never_mutate() -> None:
    current = generation()
    stale = generation(session=2)
    accepted = reduce_command(
        initial_legacy_model(current), ControllerCommand("c1", "request"), "op-1"
    ).model

    completion_result = reduce_notice(
        accepted,
        GatewayCompletion(
            operation_id="op-1",
            generation=stale,
            status=CompletionStatus.OK,
            evidence_grade=stale.evidence_grade,
        ),
    )
    event_result = reduce_notice(
        accepted, event(stale, "running", stream_id="stream-stale"), epoch_id="epoch-stale"
    )
    deadline_result = reduce_deadline(
        accepted, DeadlineExpired("d1", "op-1", stale)
    )

    assert completion_result.model is accepted
    assert event_result.model is accepted
    assert deadline_result.model is accepted
    assert "op-1" in accepted.pending_operations


def test_stop_event_opens_one_epoch_duplicate_sequence_is_ignored_and_gap_invalidates() -> None:
    stamp = generation()
    first = reduce_notice(
        initial_legacy_model(stamp), event(stamp, "stopped", sequence=5), epoch_id="epoch-1"
    )
    duplicate = reduce_notice(
        first.model, event(stamp, "stopped", sequence=5), epoch_id="epoch-2"
    )
    gap = reduce_notice(
        first.model,
        GatewayEvent(
            generation=stamp,
            stream_id="stream-old",
            sequence=8,
            category="task_state",
            payload={"state": "running"},
            evidence_grade=stamp.evidence_grade,
            gap=EventGap(6, 8, "dropped", True),
        ),
        epoch_id="unused",
    )

    assert first.model.epoch_store.active is not None
    assert first.model.epoch_store.active.epoch_id == "epoch-1"
    assert duplicate.model is first.model
    assert duplicate.events[0].kind == "duplicate_gateway_event"
    assert gap.model.event_health is EventHealth.GAP
    assert gap.model.target_state is TargetRunState.UNKNOWN
    assert gap.model.epoch_store.active is None


def test_rpc_and_event_health_are_independent_and_candidate_health_is_rejected() -> None:
    active = generation()
    stopped = reduce_notice(
        initial_legacy_model(active), event(active, "stopped"), epoch_id="epoch-1"
    ).model
    pending = reduce_command(
        stopped,
        ControllerCommand("subscribe-1", "subscribe_events"),
        "sub-op",
    )
    candidate_health = reduce_notice(
        pending.model,
        HealthNotice(
            pending.effects[0].generation,
            RpcHealth.HEALTHY,
            EventHealth.HEALTHY,
            "premature",
        ),
    )
    assert candidate_health.model is pending.model

    rpc_degraded = reduce_notice(
        pending.model,
        HealthNotice(active, RpcHealth.DEGRADED, EventHealth.HEALTHY, "rpc slow"),
    ).model
    assert rpc_degraded.rpc_health is RpcHealth.DEGRADED
    assert rpc_degraded.event_health is EventHealth.HEALTHY
    assert rpc_degraded.epoch_store.active is not None

    event_lost = reduce_notice(
        rpc_degraded,
        HealthNotice(active, RpcHealth.DEGRADED, EventHealth.LOST, "event eof"),
    ).model
    assert event_lost.rpc_health is RpcHealth.DEGRADED
    assert event_lost.event_health is EventHealth.LOST
    assert event_lost.target_state is TargetRunState.UNKNOWN
    assert event_lost.epoch_store.active is None


def test_invalid_open_capability_evidence_burns_reservation_without_adoption() -> None:
    active = generation()
    accepted = reduce_command(
        initial_legacy_model(active), ControllerCommand("connect-1", "open_session"), "open-op"
    )
    invalid_profile = replace(
        profile(accepted.effects[0].generation),
        generation=accepted.effects[0].generation.capability_generation + 1,
    )
    rejected = reduce_notice(
        accepted.model,
        completion(
            accepted.effects[0],
            authority=CompletionAuthority.AUTHORITATIVE_RESOURCE_ESTABLISHED,
            response={"capability_profile": invalid_profile},
        ),
    )

    assert rejected.model.generation == active
    assert rejected.model.generation_watermarks.session == 4
    assert rejected.model.pending_operations == {}
    assert rejected.results[0].error == "ProtocolError"


def test_legacy_unproven_recovery_invalidates_epoch_without_cancelling_reservation() -> None:
    stamp = generation()
    stopped = reduce_notice(
        initial_legacy_model(stamp), event(stamp, "stopped"), epoch_id="epoch-1"
    ).model
    pending = reduce_command(
        stopped,
        ControllerCommand("subscribe-1", "subscribe_events"),
        "sub-op",
    ).model
    recovered = reduce_notice(
        pending,
        ReconcileResult(
            generation=stamp,
            status=ReconcileStatus.LEGACY_UNPROVEN,
            evidence_grade=stamp.evidence_grade,
            baseline={"target_state": "stopped", "stop_token": "not-authoritative"},
        ),
        epoch_id="epoch-2",
    ).model

    assert recovered.target_state is TargetRunState.UNKNOWN
    assert recovered.recovery_status is RecoveryStatus.REQUIRED
    assert recovered.epoch_store.active is None
    assert "sub-op" in recovered.pending_operations


def test_actor_effect_observes_reservation_already_committed_and_only_actor_mutates() -> None:
    stamp = generation()
    sink_thread_ids: list[int] = []
    observed_effects: list[GatewayEffect] = []
    pending_seen = threading.Event()
    controller: ControllerActor

    def sink(effect_value: GatewayEffect) -> None:
        sink_thread_ids.append(threading.get_ident())
        observed_effects.append(effect_value)
        snapshot = controller.snapshot().result(timeout=1)
        if effect_value.operation_id in snapshot.pending_operation_ids:
            pending_seen.set()
        controller.accept_gateway_notice(
            completion(effect_value, status=CompletionStatus.TRANSPORT_ERROR)
        )

    controller = ControllerActor(
        sink, initial_generation=stamp, id_factory=deterministic_ids()
    )
    controller.start()
    result = controller.submit(
        ControllerCommand("connect-1", "open_session")
    ).result(timeout=1)
    assert result.status is CommandStatus.ACCEPTED
    assert pending_seen.wait(1)

    deadline = time.monotonic() + 1
    snapshot = controller.snapshot().result(timeout=1)
    while snapshot.pending_operation_ids and time.monotonic() < deadline:
        time.sleep(0.005)
        snapshot = controller.snapshot().result(timeout=1)
    assert snapshot.pending_operation_ids == ()
    assert observed_effects[0].generation.session_generation == 4
    assert len(controller.mutation_thread_ids) == 1
    writer_id = next(iter(controller.mutation_thread_ids))
    assert sink_thread_ids[0] != writer_id
    controller.close().result(timeout=1)


def test_subscriber_exception_backpressure_and_unsubscribe_cannot_block_actor() -> None:
    stamp = generation()
    release = threading.Event()
    entered = threading.Event()

    def callback(_event_value: object) -> None:
        entered.set()
        release.wait(1)
        raise RuntimeError("subscriber failure")

    controller = ControllerActor(
        initial_generation=stamp,
        subscriber_capacity=1,
        subscriber_limit=1,
        close_timeout=0.05,
        id_factory=deterministic_ids(),
    )
    subscription = controller.subscribe(callback)
    controller.start()
    for sequence in range(1, 8):
        category = "running" if sequence % 2 else "stopped"
        controller.accept_gateway_notice(event(stamp, category, sequence=sequence))
    assert entered.wait(1)
    assert controller.snapshot().result(timeout=1).controller_revision >= 1
    assert subscription.dropped_events > 0

    release.set()
    deadline = time.monotonic() + 1
    while subscription.callback_errors == 0 and time.monotonic() < deadline:
        time.sleep(0.005)
    assert subscription.callback_errors > 0
    subscription.close()
    replacement = controller.subscribe(lambda _: None)
    replacement.close()
    controller.close().result(timeout=1)


def test_concurrent_submitters_converge_through_one_actor_writer() -> None:
    stamp = generation()
    controller = ControllerActor(
        initial_generation=stamp,
        inbox_capacity=32,
        id_factory=deterministic_ids(),
    )
    controller.start()
    barrier = threading.Barrier(9)
    results: list[object] = []
    result_lock = threading.Lock()

    def submit(index: int) -> None:
        barrier.wait()
        result = controller.submit(
            ControllerCommand(f"inspect-{index}", "inspect")
        ).result(timeout=1)
        with result_lock:
            results.append(result)

    workers = [threading.Thread(target=submit, args=(index,)) for index in range(8)]
    for worker in workers:
        worker.start()
    barrier.wait()
    for worker in workers:
        worker.join(1)

    assert len(results) == 8
    assert all(result.status is CommandStatus.ACCEPTED for result in results)
    assert len(controller.snapshot().result(timeout=1).pending_operation_ids) == 8
    assert len(controller.mutation_thread_ids) == 1
    controller.close().result(timeout=1)


def test_subscription_can_close_itself_without_self_join() -> None:
    stamp = generation()
    callback_returned = threading.Event()
    holder: dict[str, object] = {}

    def callback(_event_value: object) -> None:
        holder["subscription"].close()
        callback_returned.set()

    controller = ControllerActor(initial_generation=stamp)
    holder["subscription"] = controller.subscribe(callback)
    controller.start()
    controller.accept_gateway_notice(event(stamp, "running"))

    assert callback_returned.wait(1)
    controller.close().result(timeout=1)


def test_bounded_inbox_reports_saturation_without_secondary_state_writer() -> None:
    stamp = generation()
    id_entered = threading.Event()
    release_id = threading.Event()

    def blocking_id(kind: str) -> str:
        id_entered.set()
        release_id.wait(1)
        return f"{kind}-1"

    controller = ControllerActor(
        initial_generation=stamp,
        inbox_capacity=1,
        id_factory=blocking_id,
    )
    controller.start()
    command_future = controller.submit(ControllerCommand("c1", "request"))
    assert id_entered.wait(1)
    controller.accept_gateway_notice(
        HealthNotice(stamp, RpcHealth.HEALTHY, EventHealth.HEALTHY, "first")
    )
    with pytest.raises(ControllerInboxFullError):
        controller.accept_gateway_notice(
            HealthNotice(stamp, RpcHealth.DEGRADED, EventHealth.HEALTHY, "overflow")
        )
    release_id.set()
    assert command_future.result(timeout=1).status is CommandStatus.ACCEPTED
    controller.close().result(timeout=1)
    assert len(controller.mutation_thread_ids) == 1


def test_close_is_idempotent_and_bounded_when_effect_sink_is_blocked() -> None:
    stamp = generation()
    sink_entered = threading.Event()
    release_sink = threading.Event()

    def blocking_sink(_effect_value: GatewayEffect) -> None:
        sink_entered.set()
        release_sink.wait(2)

    controller = ControllerActor(
        blocking_sink,
        initial_generation=stamp,
        close_timeout=0.05,
        id_factory=deterministic_ids(),
    )
    controller.start()
    controller.submit(ControllerCommand("c1", "request")).result(timeout=1)
    assert sink_entered.wait(1)

    before = time.monotonic()
    first = controller.close()
    second = controller.close()
    result = first.result(timeout=1)

    assert first is second
    assert result.status is CommandStatus.COMPLETED
    assert time.monotonic() - before < 0.5
    assert controller.wait_closed(1)

    release_sink.set()
    deadline = time.monotonic() + 1
    while controller.effect_thread_alive and time.monotonic() < deadline:
        time.sleep(0.005)
    assert not controller.effect_thread_alive


def test_effect_sink_exception_returns_exact_typed_failure_to_actor() -> None:
    stamp = generation()

    def failing_sink(_effect_value: GatewayEffect) -> None:
        raise RuntimeError("socket closed")

    controller = ControllerActor(
        failing_sink,
        initial_generation=stamp,
        id_factory=deterministic_ids(),
    )
    events: queue.Queue[object] = queue.Queue()
    subscription = controller.subscribe(events.put)
    controller.start()
    result = controller.submit(ControllerCommand("c1", "request")).result(timeout=1)

    deadline = time.monotonic() + 1
    snapshot = controller.snapshot().result(timeout=1)
    while snapshot.pending_operation_ids and time.monotonic() < deadline:
        time.sleep(0.005)
        snapshot = controller.snapshot().result(timeout=1)

    assert result.status is CommandStatus.ACCEPTED
    assert snapshot.pending_operation_ids == ()
    observed = []
    event_deadline = time.monotonic() + 1
    while (
        not any(getattr(item, "kind", None) == "operation_completed" for item in observed)
        and time.monotonic() < event_deadline
    ):
        try:
            observed.append(events.get(timeout=0.05))
        except queue.Empty:
            pass
    assert any(getattr(item, "kind", None) == "operation_completed" for item in observed)
    assert len(controller.mutation_thread_ids) == 1
    subscription.close()
    controller.close().result(timeout=1)
