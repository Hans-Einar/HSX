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
        model,
        ControllerCommand("connect-1", "open_session"),
        "open-op",
        "deadline-open",
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
        stopped,
        ControllerCommand("connect-1", "open_session"),
        "open-op",
        "deadline-open",
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
        initial_legacy_model(active),
        ControllerCommand("connect-1", "open_session"),
        "open-1",
        "deadline-open-1",
    )
    failed = reduce_notice(
        first.model,
        completion(first.effects[0], status=CompletionStatus.TRANSPORT_ERROR),
    )

    assert failed.model.generation == active
    assert failed.model.generation_watermarks.session == 4
    assert failed.model.pending_operations == {}

    second = reduce_command(
        failed.model,
        ControllerCommand("connect-2", "open_session"),
        "open-2",
        "deadline-open-2",
    )
    assert second.effects[0].generation.session_generation == 5
    assert second.model.generation_watermarks.session == 5


def test_failed_subscribe_burns_stream_only_and_same_operation_retry_reuses() -> None:
    active = generation()
    command = ControllerCommand("subscribe-1", "subscribe_events")
    first = reduce_command(
        initial_legacy_model(active), command, "sub-op", "deadline-sub-1"
    )
    retried = reduce_command(first.model, command, "sub-op", "deadline-sub-2")

    assert retried.model is not first.model
    assert retried.model.pending_operations["sub-op"].deadline_id == "deadline-sub-2"
    assert "deadline-sub-1" in retried.model.retired_deadline_ids
    assert retried.effects[0] is first.effects[0]
    assert first.model.generation_watermarks.session == 3
    assert first.model.generation_watermarks.stream == 5

    failed = reduce_notice(
        retried.model,
        completion(first.effects[0], status=CompletionStatus.CANCELLED),
    )
    assert failed.model.generation == active
    assert failed.model.generation_watermarks.session == 3
    assert failed.model.generation_watermarks.stream == 5

    retired_retry = reduce_command(
        failed.model, command, "sub-op", "deadline-sub-3"
    )
    assert retired_retry.model is failed.model
    assert retired_retry.effects == ()
    assert retired_retry.results[0].error == "StaleOperation"

    next_operation = reduce_command(
        failed.model,
        ControllerCommand("subscribe-2", "subscribe_events"),
        "sub-op-2",
        "deadline-sub-4",
    )
    assert next_operation.effects[0].generation.stream_generation == 6


def test_pending_subscribe_keeps_old_events_and_fences_premature_new_events() -> None:
    active = generation()
    pending = reduce_command(
        initial_legacy_model(active),
        ControllerCommand("subscribe-1", "subscribe_events"),
        "sub-op",
        "deadline-sub",
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
    assert accepted_new.model is promoted.model
    assert accepted_new.events[0].kind == "event_awaiting_reconcile"

    reconciling = reduce_command(
        promoted.model,
        ControllerCommand("reconcile-1", "reconcile"),
        "reconcile-op",
        "deadline-reconcile",
    )
    reconciled = reduce_notice(
        reconciling.model,
        ReconcileResult(
            generation=effect.generation,
            status=ReconcileStatus.RETAINED,
            evidence_grade=effect.generation.evidence_grade,
            baseline={"target_state": "unknown"},
        ),
        epoch_id="unused",
    )
    accepted_new = reduce_notice(
        reconciled.model,
        event(effect.generation, "running", sequence=1, stream_id="stream-new"),
        epoch_id="unused",
    )
    assert accepted_new.model.target_state is TargetRunState.RUNNING


def test_wrong_operation_parent_stamp_and_numeric_higher_completion_never_adopt() -> None:
    active = generation()
    accepted = reduce_command(
        initial_legacy_model(active),
        ControllerCommand("connect-1", "open_session"),
        "open-right",
        "deadline-open",
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
        "deadline-sub",
    )
    open_pending = reduce_command(
        stream_pending.model,
        ControllerCommand("connect-1", "open_session"),
        "open-op",
        "deadline-open",
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
    accepted = reduce_command(
        stopped, ControllerCommand("c1", "continue"), "op-1", "deadline-1"
    )

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
        "deadline-right",
    )
    wrong = reduce_deadline(
        accepted.model,
        DeadlineExpired("deadline-wrong", "sub-op", accepted.effects[0].generation),
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


def test_retry_replaces_exact_deadline_and_cancel_retires_the_live_deadline() -> None:
    stamp = generation()
    command = ControllerCommand("inspect-1", "inspect")
    first = reduce_command(
        initial_legacy_model(stamp), command, "inspect-op", "deadline-old"
    )
    retried = reduce_command(
        first.model, command, "inspect-op", "deadline-current"
    )

    assert retried.model.pending_operations["inspect-op"].deadline_id == "deadline-current"
    assert "deadline-old" in retried.model.retired_deadline_ids
    for index in range(64):
        deadline_id = "deadline-old" if index % 2 else f"deadline-wrong-{index}"
        stale = reduce_deadline(
            retried.model,
            DeadlineExpired(deadline_id, "inspect-op", stamp),
        )
        assert stale.model is retried.model
        assert "inspect-op" in stale.model.pending_operations

    with pytest.raises(ValueError, match="already been retired"):
        reduce_command(retried.model, command, "inspect-op", "deadline-old")

    cancelled = reduce_notice(
        retried.model,
        completion(retried.effects[0], status=CompletionStatus.CANCELLED),
    )
    assert cancelled.results[0].command_id == "inspect-1"
    assert cancelled.results[0].operation_id == "inspect-op"
    assert cancelled.results[0].status is CommandStatus.CANCELLED
    assert "deadline-current" in cancelled.model.retired_deadline_ids
    late_current = reduce_deadline(
        cancelled.model,
        DeadlineExpired("deadline-current", "inspect-op", stamp),
    )
    assert late_current.model is cancelled.model


def test_stale_active_completion_event_and_deadline_never_mutate() -> None:
    current = generation()
    stale = generation(session=2)
    accepted = reduce_command(
        initial_legacy_model(current),
        ControllerCommand("c1", "request"),
        "op-1",
        "deadline-1",
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


def test_gap_and_required_recovery_fence_all_later_events_until_reconcile() -> None:
    stamp = generation()
    stopped = reduce_notice(
        initial_legacy_model(stamp),
        event(stamp, "stopped", sequence=5),
        epoch_id="epoch-before-gap",
    ).model
    gap = reduce_notice(
        stopped,
        event(stamp, "running", sequence=8),
        epoch_id="unused",
    )

    assert gap.model.event_health is EventHealth.GAP
    assert gap.model.recovery_status is RecoveryStatus.REQUIRED
    assert gap.model.last_event_sequence == 5
    assert gap.model.epoch_store.active is None

    for index in range(64):
        late = reduce_notice(
            gap.model,
            event(
                stamp,
                "stopped" if index % 2 else "running",
                sequence=6 + index,
            ),
            epoch_id=f"forbidden-epoch-{index}",
        )
        assert late.model is gap.model
        assert late.events[0].kind == "event_awaiting_reconcile"
        assert late.model.last_event_sequence == 5
        assert late.model.epoch_store.active is None

    transport_healthy = reduce_notice(
        gap.model,
        HealthNotice(stamp, RpcHealth.HEALTHY, EventHealth.HEALTHY, "stream resumed"),
    )
    assert transport_healthy.model.recovery_status is RecoveryStatus.REQUIRED
    still_fenced = reduce_notice(
        transport_healthy.model,
        event(stamp, "stopped", sequence=6),
        epoch_id="still-forbidden",
    )
    assert still_fenced.model is transport_healthy.model

    reconciling = reduce_command(
        transport_healthy.model,
        ControllerCommand("reconcile-gap", "reconcile"),
        "reconcile-gap-op",
        "reconcile-gap-deadline",
    )
    reconciled = reduce_notice(
        reconciling.model,
        ReconcileResult(
            generation=stamp,
            status=ReconcileStatus.RETAINED,
            evidence_grade=stamp.evidence_grade,
            baseline={"target_state": "running"},
        ),
        epoch_id="unused",
    )
    assert reconciled.model.recovery_status is RecoveryStatus.RETAINED
    assert reconciled.model.last_event_sequence == 5
    assert len(reconciled.results) == 1
    assert reconciled.results[0].command_id == "reconcile-gap"
    assert reconciled.results[0].operation_id == "reconcile-gap-op"
    assert reconciled.results[0].status is CommandStatus.COMPLETED

    authoritative_stop = reduce_notice(
        reconciled.model,
        event(stamp, "stopped", sequence=6),
        epoch_id="epoch-after-reconcile",
    )
    assert authoritative_stop.model.target_state is TargetRunState.STOPPED
    assert authoritative_stop.model.last_event_sequence == 6
    assert authoritative_stop.model.epoch_store.active is not None
    assert authoritative_stop.model.epoch_store.active.epoch_id == "epoch-after-reconcile"


def test_lost_health_fences_late_stop_events_without_opening_epochs() -> None:
    stamp = generation()
    running = reduce_notice(
        initial_legacy_model(stamp), event(stamp, "running", sequence=1)
    ).model
    lost = reduce_notice(
        running,
        HealthNotice(stamp, RpcHealth.HEALTHY, EventHealth.LOST, "event eof"),
    ).model

    for index in range(64):
        late = reduce_notice(
            lost,
            event(stamp, "stopped", sequence=2 + index),
            epoch_id=f"late-lost-{index}",
        )
        assert late.model is lost
        assert late.model.target_state is TargetRunState.UNKNOWN
        assert late.model.last_event_sequence == 1
        assert late.model.epoch_store.active is None


def test_rpc_and_event_health_are_independent_and_candidate_health_is_rejected() -> None:
    active = generation()
    stopped = reduce_notice(
        initial_legacy_model(active), event(active, "stopped"), epoch_id="epoch-1"
    ).model
    pending = reduce_command(
        stopped,
        ControllerCommand("subscribe-1", "subscribe_events"),
        "sub-op",
        "deadline-sub",
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
        initial_legacy_model(active),
        ControllerCommand("connect-1", "open_session"),
        "open-op",
        "deadline-open",
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
        "deadline-sub",
    ).model
    reconciling = reduce_command(
        pending,
        ControllerCommand("reconcile-1", "reconcile"),
        "reconcile-op",
        "deadline-reconcile",
    ).model
    recovered = reduce_notice(
        reconciling,
        ReconcileResult(
            generation=stamp,
            status=ReconcileStatus.LEGACY_UNPROVEN,
            evidence_grade=stamp.evidence_grade,
            baseline={"target_state": "stopped", "stop_token": "not-authoritative"},
        ),
        epoch_id="epoch-2",
    )

    assert recovered.model.target_state is TargetRunState.UNKNOWN
    assert recovered.model.recovery_status is RecoveryStatus.REQUIRED
    assert recovered.model.epoch_store.active is None
    assert "sub-op" in recovered.model.pending_operations
    assert recovered.results[0].command_id == "reconcile-1"
    assert recovered.results[0].operation_id == "reconcile-op"
    assert recovered.results[0].status is CommandStatus.FAILED


@pytest.mark.parametrize(
    ("status", "error"),
    [
        (ReconcileStatus.TARGET_LOST, "TargetLost"),
        (ReconcileStatus.OWNERSHIP_LOST, "OwnershipLost"),
        (ReconcileStatus.INCOMPATIBLE, "CapabilityUnavailable"),
        (ReconcileStatus.EXHAUSTED, "RecoveryFailed"),
        (ReconcileStatus.LEGACY_UNPROVEN, "RecoveryFailed"),
    ],
)
def test_reconcile_failure_returns_one_exact_correlated_command_result(
    status: ReconcileStatus, error: str
) -> None:
    stamp = generation()
    command_id = f"reconcile-{status.value}"
    operation_id = f"operation-{status.value}"
    accepted = reduce_command(
        initial_legacy_model(stamp),
        ControllerCommand(command_id, "reconcile"),
        operation_id,
        f"deadline-{status.value}",
    )
    completed = reduce_notice(
        accepted.model,
        ReconcileResult(
            generation=stamp,
            status=status,
            evidence_grade=stamp.evidence_grade,
            diagnostics=("adversarial recovery outcome",),
        ),
        epoch_id="unused",
    )

    assert len(completed.results) == 1
    result = completed.results[0]
    assert result.command_id == command_id
    assert result.operation_id == operation_id
    assert result.status is CommandStatus.FAILED
    assert result.error == error
    assert operation_id not in completed.model.pending_operations


def test_reconcile_cancel_is_correlated_and_late_result_cannot_restore_authority() -> None:
    stamp = generation()
    stopped = reduce_notice(
        initial_legacy_model(stamp),
        event(stamp, "stopped", sequence=1),
        epoch_id="epoch-before-recovery",
    ).model
    accepted = reduce_command(
        stopped,
        ControllerCommand("reconcile-cancel", "reconcile"),
        "reconcile-cancel-op",
        "reconcile-cancel-deadline",
    )
    cancelled = reduce_notice(
        accepted.model,
        completion(accepted.effects[0], status=CompletionStatus.CANCELLED),
    )

    assert len(cancelled.results) == 1
    result = cancelled.results[0]
    assert result.command_id == "reconcile-cancel"
    assert result.operation_id == "reconcile-cancel-op"
    assert result.status is CommandStatus.CANCELLED
    assert cancelled.model.recovery_status is RecoveryStatus.REQUIRED
    assert cancelled.model.target_state is TargetRunState.UNKNOWN
    assert cancelled.model.epoch_store.active is None

    late = reduce_notice(
        cancelled.model,
        ReconcileResult(
            generation=stamp,
            status=ReconcileStatus.RETAINED,
            evidence_grade=stamp.evidence_grade,
            baseline={"target_state": "stopped", "stop_token": "too-late"},
        ),
        epoch_id="forbidden-late-epoch",
    )
    assert late.model is cancelled.model
    assert late.events[0].kind == "uncorrelated_reconcile_result"


def test_retained_reconcile_with_invalid_stop_evidence_fails_correlated_operation() -> None:
    stamp = generation()
    accepted = reduce_command(
        initial_legacy_model(stamp),
        ControllerCommand("reconcile-invalid-stop", "reconcile"),
        "reconcile-invalid-stop-op",
        "reconcile-invalid-stop-deadline",
    )
    invalid = reduce_notice(
        accepted.model,
        ReconcileResult(
            generation=stamp,
            status=ReconcileStatus.RETAINED,
            evidence_grade=stamp.evidence_grade,
            baseline={"target_state": "stopped"},
        ),
        epoch_id="never-opened",
    )

    assert len(invalid.results) == 1
    assert invalid.results[0].command_id == "reconcile-invalid-stop"
    assert invalid.results[0].operation_id == "reconcile-invalid-stop-op"
    assert invalid.results[0].status is CommandStatus.FAILED
    assert invalid.results[0].error == "RecoveryFailed"
    assert invalid.model.recovery_status is RecoveryStatus.REQUIRED
    assert invalid.model.epoch_store.active is None


def test_only_one_reconcile_barrier_can_be_live() -> None:
    stamp = generation()
    first = reduce_command(
        initial_legacy_model(stamp),
        ControllerCommand("reconcile-1", "reconcile"),
        "reconcile-op-1",
        "reconcile-deadline-1",
    )
    second = reduce_command(
        first.model,
        ControllerCommand("reconcile-2", "reconcile"),
        "reconcile-op-2",
        "reconcile-deadline-2",
    )

    assert second.model is first.model
    assert second.results[0].status is CommandStatus.REJECTED
    assert second.results[0].error == "RecoveryInProgress"
    assert tuple(second.model.pending_operations) == ("reconcile-op-1",)


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
    command_future = controller.submit(ControllerCommand("connect-1", "open_session"))
    assert not command_future.done()
    assert pending_seen.wait(1)

    result = command_future.result(timeout=1)
    assert result.status is CommandStatus.FAILED
    assert result.error == "SessionUnavailable"

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


def test_public_future_waits_for_correlated_success_and_late_duplicate_is_ignored() -> None:
    stamp = generation()
    effects: queue.Queue[GatewayEffect] = queue.Queue()
    controller = ControllerActor(
        effects.put,
        initial_generation=stamp,
        id_factory=deterministic_ids(),
    )
    controller.start()

    command_future = controller.submit(ControllerCommand("request-1", "request"))
    effect = effects.get(timeout=1)
    assert not command_future.done()

    controller.accept_gateway_notice(completion(effect))
    result = command_future.result(timeout=1)
    assert result.status is CommandStatus.COMPLETED
    assert result.command_id == "request-1"
    assert result.operation_id == effect.operation_id
    assert controller._operation_futures == {}

    controller.accept_gateway_notice(completion(effect))
    controller.snapshot().result(timeout=1)
    assert command_future.result(timeout=0) is result
    assert controller._operation_futures == {}
    controller.close().result(timeout=1)


def test_public_future_resolves_on_exact_deadline_and_not_late_completion() -> None:
    stamp = generation()
    effects: queue.Queue[GatewayEffect] = queue.Queue()
    controller = ControllerActor(
        effects.put,
        initial_generation=stamp,
        id_factory=deterministic_ids(),
    )
    controller.start()

    command_future = controller.submit(ControllerCommand("request-timeout", "request"))
    effect = effects.get(timeout=1)
    assert not command_future.done()
    controller.accept_deadline(
        DeadlineExpired("deadline-2", effect.operation_id, effect.generation)
    )

    result = command_future.result(timeout=1)
    assert result.status is CommandStatus.FAILED
    assert result.error == "OperationTimeout"
    assert result.operation_id == effect.operation_id
    assert controller._operation_futures == {}

    controller.accept_gateway_notice(completion(effect))
    controller.snapshot().result(timeout=1)
    assert command_future.result(timeout=0) is result
    assert controller._operation_futures == {}
    controller.close().result(timeout=1)


def test_public_future_waits_through_reconcile_ack_for_authoritative_result() -> None:
    stamp = generation()
    effects: queue.Queue[GatewayEffect] = queue.Queue()
    controller = ControllerActor(
        effects.put,
        initial_generation=stamp,
        id_factory=deterministic_ids(),
    )
    controller.start()

    command_future = controller.submit(ControllerCommand("reconcile-actor", "reconcile"))
    effect = effects.get(timeout=1)
    controller.accept_gateway_notice(completion(effect))
    controller.snapshot().result(timeout=1)
    assert not command_future.done()

    controller.accept_gateway_notice(
        ReconcileResult(
            generation=stamp,
            status=ReconcileStatus.RETAINED,
            evidence_grade=stamp.evidence_grade,
            baseline={"target_state": "none"},
        )
    )
    result = command_future.result(timeout=1)
    assert result.status is CommandStatus.COMPLETED
    assert result.command_id == "reconcile-actor"
    assert result.operation_id == effect.operation_id
    assert controller._operation_futures == {}
    controller.close().result(timeout=1)


def test_public_future_resolves_exact_cancel_and_immediate_rejection() -> None:
    stamp = generation()
    effects: queue.Queue[GatewayEffect] = queue.Queue()
    controller = ControllerActor(
        effects.put,
        initial_generation=stamp,
        id_factory=deterministic_ids(),
    )
    controller.start()

    rejected = controller.submit(
        ControllerCommand("stale-command", "request", expected_revision=99)
    ).result(timeout=1)
    assert rejected.status is CommandStatus.REJECTED
    assert rejected.error == "RevisionMismatch"
    assert effects.empty()

    command_future = controller.submit(ControllerCommand("cancel-command", "request"))
    effect = effects.get(timeout=1)
    assert not command_future.done()
    controller.accept_gateway_notice(
        completion(effect, status=CompletionStatus.CANCELLED)
    )
    cancelled = command_future.result(timeout=1)
    assert cancelled.status is CommandStatus.CANCELLED
    assert cancelled.error == "Cancelled"
    assert cancelled.operation_id == effect.operation_id
    assert controller._operation_futures == {}
    controller.close().result(timeout=1)


def test_same_operation_retry_resolves_every_public_future_without_replacement() -> None:
    stamp = generation()
    effects: queue.Queue[GatewayEffect] = queue.Queue()
    allocated_ids = iter(
        (
            "operation-retry",
            "deadline-first",
            "operation-retry",
            "deadline-second",
            "epoch-completion",
        )
    )
    controller = ControllerActor(
        effects.put,
        initial_generation=stamp,
        id_factory=lambda _kind: next(allocated_ids),
    )
    controller.start()

    command = ControllerCommand("inspect-retry", "inspect")
    first_future = controller.submit(command)
    first_effect = effects.get(timeout=1)
    second_future = controller.submit(command)
    second_effect = effects.get(timeout=1)
    assert first_effect is second_effect
    assert not first_future.done()
    assert not second_future.done()

    controller.accept_gateway_notice(completion(first_effect))
    first_result = first_future.result(timeout=1)
    second_result = second_future.result(timeout=1)
    assert first_result is second_result
    assert first_result.status is CommandStatus.COMPLETED
    assert first_result.operation_id == "operation-retry"
    assert controller._operation_futures == {}
    controller.close().result(timeout=1)


def test_multiple_pending_operations_resolve_to_their_own_out_of_order_results() -> None:
    stamp = generation()
    effects: queue.Queue[GatewayEffect] = queue.Queue()
    controller = ControllerActor(
        effects.put,
        initial_generation=stamp,
        id_factory=deterministic_ids(),
    )
    controller.start()

    futures = {
        f"request-{index}": controller.submit(
            ControllerCommand(f"request-{index}", "request")
        )
        for index in range(16)
    }
    dispatched = [effects.get(timeout=1) for _ in futures]
    assert all(not future.done() for future in futures.values())

    for effect_value in reversed(dispatched):
        controller.accept_gateway_notice(completion(effect_value))

    results = {
        command_id: future.result(timeout=1)
        for command_id, future in futures.items()
    }
    assert {
        command_id: (result.command_id, result.status)
        for command_id, result in results.items()
    } == {
        command_id: (command_id, CommandStatus.COMPLETED)
        for command_id in futures
    }
    assert {result.operation_id for result in results.values()} == {
        effect_value.operation_id for effect_value in dispatched
    }
    assert controller._operation_futures == {}
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

    controller: ControllerActor

    def complete(effect_value: GatewayEffect) -> None:
        controller.accept_gateway_notice(completion(effect_value))

    controller = ControllerActor(
        complete,
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
    assert all(result.status is CommandStatus.COMPLETED for result in results)
    assert len(controller.snapshot().result(timeout=1).pending_operation_ids) == 0
    assert controller._operation_futures == {}
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


def test_subscribe_and_close_share_one_atomic_admission_boundary() -> None:
    for iteration in range(32):
        controller = ControllerActor(
            initial_generation=generation(),
            close_timeout=0.2,
        )
        controller.start()
        registered: list[object] = []
        registration_errors: list[BaseException] = []
        close_results: list[object] = []

        def register() -> None:
            try:
                registered.append(controller.subscribe(lambda _event: None))
            except BaseException as exc:  # pragma: no cover - assertion captures any failure
                registration_errors.append(exc)

        def close_controller() -> None:
            close_results.append(controller.close().result(timeout=1))

        # Hold subscriber publication while registration owns the lifecycle boundary.  Close
        # is then forced to arrive second: the accepted subscriber must be in the actor's
        # cleanup snapshot, closed, and joined before close completes.
        controller._subscribers_lock.acquire()
        register_thread = threading.Thread(target=register)
        register_thread.start()
        acquisition_deadline = time.monotonic() + 1
        while time.monotonic() < acquisition_deadline:
            if not controller._lifecycle_lock.acquire(blocking=False):
                break
            controller._lifecycle_lock.release()
            time.sleep(0.001)
        else:
            controller._subscribers_lock.release()
            pytest.fail("registration did not acquire the lifecycle boundary")

        close_thread = threading.Thread(target=close_controller)
        close_thread.start()
        controller._subscribers_lock.release()
        register_thread.join(1)
        close_thread.join(1)

        assert not registration_errors
        assert len(registered) == 1
        subscription = registered[0]
        assert subscription.closed
        subscription.join(1)
        assert not subscription._thread.is_alive()
        assert len(close_results) == 1
        assert close_results[0].status is CommandStatus.COMPLETED
        with pytest.raises(RuntimeError, match="closed"):
            controller.subscribe(lambda _event: None)


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
    assert not command_future.done()
    controller.close().result(timeout=1)
    assert command_future.result(timeout=1).status is CommandStatus.CANCELLED
    assert controller._operation_futures == {}
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
    command_future = controller.submit(ControllerCommand("c1", "request"))
    assert sink_entered.wait(1)
    assert not command_future.done()

    before = time.monotonic()
    first = controller.close()
    second = controller.close()
    result = first.result(timeout=1)

    assert first is second
    assert result.status is CommandStatus.COMPLETED
    assert command_future.result(timeout=1).status is CommandStatus.CANCELLED
    assert controller._operation_futures == {}
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

    assert result.status is CommandStatus.FAILED
    assert result.error == "EffectSinkFailure"
    assert snapshot.pending_operation_ids == ()
    assert controller._operation_futures == {}
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


def test_internal_effect_failure_bypasses_saturated_one_slot_public_inbox() -> None:
    stamp = generation()
    sink_entered = threading.Event()
    release_failure = threading.Event()
    second_operation_entered = threading.Event()
    release_second_operation = threading.Event()
    id_lock = threading.Lock()
    id_counter = itertools.count(1)
    operation_count = 0
    sink_count = 0

    def blocking_ids(kind: str) -> str:
        nonlocal operation_count
        with id_lock:
            value = next(id_counter)
            if kind == "operation":
                operation_count += 1
                current_operation = operation_count
            else:
                current_operation = 0
        if current_operation == 2:
            second_operation_entered.set()
            release_second_operation.wait(1)
        return f"{kind}-{value}"

    def fail_first_effect(_effect_value: GatewayEffect) -> None:
        nonlocal sink_count
        sink_count += 1
        if sink_count == 1:
            sink_entered.set()
            release_failure.wait(1)
            raise RuntimeError("deterministic first dispatch failure")

    controller = ControllerActor(
        fail_first_effect,
        initial_generation=stamp,
        inbox_capacity=1,
        id_factory=blocking_ids,
    )
    controller.start()
    first = controller.submit(ControllerCommand("first", "request"))
    assert sink_entered.wait(1)

    second = controller.submit(ControllerCommand("second", "request"))
    assert second_operation_entered.wait(1)
    controller.accept_gateway_notice(
        HealthNotice(stamp, RpcHealth.HEALTHY, EventHealth.HEALTHY, "fills public slot")
    )
    with pytest.raises(ControllerInboxFullError):
        controller.accept_gateway_notice(
            HealthNotice(stamp, RpcHealth.DEGRADED, EventHealth.HEALTHY, "overflow")
        )

    release_failure.set()
    assert controller._internal_failures_ready.wait(1)
    assert not first.done()
    release_second_operation.set()

    first_result = first.result(timeout=1)
    assert first_result.status is CommandStatus.FAILED
    assert first_result.error == "EffectSinkFailure"
    assert first_result.operation_id not in controller._operation_futures
    assert controller.dropped_internal_notices == 0
    assert controller._internal_failure_peak == 1

    controller.close().result(timeout=1)
    assert second.result(timeout=1).status is CommandStatus.CANCELLED
    assert controller._operation_futures == {}
    assert len(controller.mutation_thread_ids) == 1


def test_multiple_accumulated_effect_failures_reduce_fifo_without_correlation_leaks() -> None:
    stamp = generation()
    release_failures = threading.Event()
    first_sink_entered = threading.Event()
    blocker_entered = threading.Event()
    release_blocker = threading.Event()
    operation_lock = threading.Lock()
    operation_count = 0
    id_counter = itertools.count(1)
    command_count = 8

    def blocking_ids(kind: str) -> str:
        nonlocal operation_count
        with operation_lock:
            value = next(id_counter)
            if kind == "operation":
                operation_count += 1
                current_operation = operation_count
            else:
                current_operation = 0
        if current_operation == command_count + 1:
            blocker_entered.set()
            release_blocker.wait(1)
        return f"{kind}-{value}"

    def failing_sink(_effect_value: GatewayEffect) -> None:
        first_sink_entered.set()
        release_failures.wait(1)
        raise RuntimeError("batch transport failure")

    controller = ControllerActor(
        failing_sink,
        initial_generation=stamp,
        inbox_capacity=command_count + 1,
        effect_capacity=command_count + 1,
        id_factory=blocking_ids,
    )
    controller.start()
    futures = [
        controller.submit(ControllerCommand(f"batch-{index}", "request"))
        for index in range(command_count)
    ]
    assert first_sink_entered.wait(1)

    deadline = time.monotonic() + 1
    while controller._effects.qsize() < command_count - 1 and time.monotonic() < deadline:
        time.sleep(0.001)
    assert controller._effects.qsize() == command_count - 1

    blocker = controller.submit(ControllerCommand("blocker", "request"))
    assert blocker_entered.wait(1)
    release_failures.set()
    deadline = time.monotonic() + 1
    while controller._internal_failure_peak < command_count and time.monotonic() < deadline:
        time.sleep(0.001)
    assert controller._internal_failure_peak == command_count
    assert controller._internal_failure_peak <= controller._internal_failure_limit
    release_blocker.set()

    results = [future.result(timeout=1) for future in futures]
    assert [result.command_id for result in results] == [
        f"batch-{index}" for index in range(command_count)
    ]
    assert all(result.status is CommandStatus.FAILED for result in results)
    assert all(result.error == "EffectSinkFailure" for result in results)
    assert len({result.operation_id for result in results}) == command_count
    assert controller.dropped_internal_notices == 0

    assert blocker.result(timeout=1).status is CommandStatus.FAILED
    assert controller._operation_futures == {}
    controller.close().result(timeout=1)


def test_duplicate_same_operation_effect_failures_resolve_all_callers_once() -> None:
    stamp = generation()
    release_sink = threading.Event()
    first_sink_entered = threading.Event()
    sink_operations: list[str] = []
    allocated_ids = iter(
        (
            "operation-duplicate",
            "deadline-first",
            "operation-duplicate",
            "deadline-second",
        )
    )

    def failing_sink(effect_value: GatewayEffect) -> None:
        sink_operations.append(effect_value.operation_id)
        first_sink_entered.set()
        release_sink.wait(1)
        raise RuntimeError("duplicate dispatch failure")

    controller = ControllerActor(
        failing_sink,
        initial_generation=stamp,
        id_factory=lambda _kind: next(allocated_ids),
    )
    events: queue.Queue[object] = queue.Queue()
    subscription = controller.subscribe(events.put)
    controller.start()
    command = ControllerCommand("duplicate", "inspect")
    first = controller.submit(command)
    assert first_sink_entered.wait(1)
    second = controller.submit(command)
    deadline = time.monotonic() + 1
    while controller._effects.empty() and time.monotonic() < deadline:
        time.sleep(0.001)
    assert not controller._effects.empty()
    release_sink.set()

    first_result = first.result(timeout=1)
    second_result = second.result(timeout=1)
    assert first_result is second_result
    assert first_result.status is CommandStatus.FAILED
    assert first_result.operation_id == "operation-duplicate"
    assert sink_operations == ["operation-duplicate", "operation-duplicate"]
    controller.snapshot().result(timeout=1)
    assert controller._operation_futures == {}
    assert controller.dropped_internal_notices == 0

    observed = []
    event_deadline = time.monotonic() + 1
    while time.monotonic() < event_deadline:
        try:
            observed.append(events.get(timeout=0.01))
        except queue.Empty:
            if any(
                getattr(item, "kind", None) == "operation_completed"
                for item in observed
            ):
                break
    assert sum(
        getattr(item, "kind", None) == "operation_completed" for item in observed
    ) == 1
    subscription.close()
    controller.close().result(timeout=1)


def test_close_seals_internal_failure_lane_and_cancels_late_sink_failure() -> None:
    stamp = generation()
    sink_entered = threading.Event()
    release_sink = threading.Event()

    def late_failing_sink(_effect_value: GatewayEffect) -> None:
        sink_entered.set()
        release_sink.wait(2)
        raise RuntimeError("failure after close linearization")

    controller = ControllerActor(
        late_failing_sink,
        initial_generation=stamp,
        close_timeout=0.05,
        id_factory=deterministic_ids(),
    )
    controller.start()
    command_future = controller.submit(ControllerCommand("closing", "request"))
    assert sink_entered.wait(1)

    close_result = controller.close().result(timeout=1)
    command_result = command_future.result(timeout=1)
    assert close_result.status is CommandStatus.COMPLETED
    assert command_result.status is CommandStatus.CANCELLED
    assert controller._operation_futures == {}

    release_sink.set()
    deadline = time.monotonic() + 1
    while controller.effect_thread_alive and time.monotonic() < deadline:
        time.sleep(0.005)
    assert not controller.effect_thread_alive
    assert controller.dropped_internal_notices == 0
    assert controller._take_internal_failures() == ()
