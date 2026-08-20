"""Pure state transitions for the debugger controller foundation."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from typing import Any

from .contracts import (
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
    GatewayNotice,
    HealthNotice,
    ReconcileResult,
    ReconcileStatus,
    RecoveryStatus,
    RpcHealth,
    TargetRunState,
    completion_matches_reservation,
    promote_generation,
    reserve_generation,
)
from .model import ControllerModel, PendingOperation


RUN_COMMANDS = frozenset({"continue", "resume", "run"})
STEP_COMMANDS = frozenset(
    {"step", "step_into", "step_over", "step_out", "step_instruction"}
)
STOP_COMMANDS = frozenset({"pause", "stop"})
TERMINATE_COMMANDS = frozenset({"terminate"})
CONTROL_COMMANDS = RUN_COMMANDS | STEP_COMMANDS | STOP_COMMANDS | TERMINATE_COMMANDS


@dataclass(frozen=True, slots=True)
class Reduction:
    model: ControllerModel
    effects: tuple[GatewayEffect, ...] = ()
    events: tuple[ControllerEvent, ...] = ()
    results: tuple[CommandResult, ...] = ()


def _event(model: ControllerModel, kind: str, payload: Mapping[str, Any]) -> ControllerEvent:
    return ControllerEvent(model.revision, kind, model.generation, payload)


def _result(
    command_id: str,
    status: CommandStatus,
    revision: int,
    *,
    operation_id: str | None = None,
    error: str | None = None,
    diagnostic: str | None = None,
) -> CommandResult:
    return CommandResult(
        command_id=command_id,
        status=status,
        controller_revision=revision,
        operation_id=operation_id,
        error=error,
        diagnostics=() if diagnostic is None else (diagnostic,),
    )


def _with_revision(model: ControllerModel, **changes: Any) -> ControllerModel:
    return replace(model, revision=model.revision + 1, **changes)


def _effect_kind(command_kind: str) -> EffectKind:
    return {
        "open_session": EffectKind.OPEN_SESSION,
        "close_session": EffectKind.CLOSE_SESSION,
        "subscribe_events": EffectKind.SUBSCRIBE_EVENTS,
        "unsubscribe_events": EffectKind.UNSUBSCRIBE_EVENTS,
        "reconcile": EffectKind.RECONCILE,
    }.get(command_kind, EffectKind.REQUEST)


def _idempotent(command_kind: str) -> bool:
    return command_kind in {
        "open_session",
        "close_session",
        "subscribe_events",
        "unsubscribe_events",
        "reconcile",
        "snapshot",
        "inspect",
    }


def _accepted_target_state(
    model: ControllerModel, command: ControllerCommand
) -> tuple[TargetRunState, tuple[str, str] | None]:
    kind = command.kind
    if kind in RUN_COMMANDS:
        if model.target_state is not TargetRunState.STOPPED:
            return model.target_state, (
                "InvalidTransition",
                "run requires an authoritative stopped state",
            )
        return TargetRunState.RUN_PENDING, None
    if kind in STEP_COMMANDS:
        if model.target_state is not TargetRunState.STOPPED:
            return model.target_state, (
                "InvalidTransition",
                "step requires an authoritative stopped state",
            )
        return TargetRunState.STEP_PENDING, None
    if kind in STOP_COMMANDS:
        if model.target_state is not TargetRunState.RUNNING:
            return model.target_state, (
                "InvalidTransition",
                "pause requires an authoritative running state",
            )
        return TargetRunState.STOP_PENDING, None
    if kind in TERMINATE_COMMANDS:
        if model.target_state in {
            TargetRunState.NONE,
            TargetRunState.TERMINATED,
            TargetRunState.LOST,
        }:
            return model.target_state, (
                "InvalidTransition",
                "terminate requires a live target",
            )
        return TargetRunState.STOP_PENDING, None
    return model.target_state, None


def _reject_command(
    model: ControllerModel, command: ControllerCommand, code: str, message: str
) -> Reduction:
    return Reduction(
        model,
        results=(
            _result(
                command.command_id,
                CommandStatus.REJECTED,
                model.revision,
                error=code,
                diagnostic=message,
            ),
        ),
    )


def reduce_command(
    model: ControllerModel,
    command: ControllerCommand,
    operation_id: str,
    deadline_id: str,
) -> Reduction:
    """Accept/reject a frontend command and reserve generation before effect dispatch."""

    if not isinstance(model, ControllerModel):
        raise TypeError("model must be ControllerModel")
    if not isinstance(command, ControllerCommand):
        raise TypeError("command must be ControllerCommand")
    if not isinstance(operation_id, str) or not operation_id.strip():
        raise ValueError("operation_id must be a non-empty string")
    if not isinstance(deadline_id, str) or not deadline_id.strip():
        raise ValueError("deadline_id must be a non-empty string")

    existing = model.pending_operations.get(operation_id)
    if existing is not None:
        if existing.command != command:
            return _reject_command(
                model,
                command,
                "DuplicateOperation",
                "operation ID is already bound to another command",
            )
        if not existing.effect.idempotent:
            return _reject_command(
                model,
                command,
                "RetryUnsafe",
                "the live operation is not idempotent",
            )
        if existing.reservation is not None:
            watermarks, reservation = reserve_generation(
                model.generation_watermarks,
                model.generation,
                operation_id,
                existing.effect.kind,
                existing=existing.reservation,
            )
            assert watermarks is model.generation_watermarks
            assert reservation is existing.reservation
        if deadline_id in model.retired_deadline_ids:
            raise ValueError("deadline_id has already been retired")
        if any(
            operation.deadline_id == deadline_id
            for pending_id, operation in model.pending_operations.items()
            if pending_id != operation_id
        ):
            raise ValueError("deadline_id is already bound to another operation")
        next_model = model
        if deadline_id != existing.deadline_id:
            pending = dict(model.pending_operations)
            pending[operation_id] = replace(existing, deadline_id=deadline_id)
            next_model = _with_revision(
                model,
                pending_operations=pending,
                retired_deadline_ids=(
                    model.retired_deadline_ids | {existing.deadline_id}
                ),
            )
        return Reduction(
            next_model,
            effects=(existing.effect,),
            events=(
                _event(
                    next_model,
                    "operation_retried",
                    {
                        "operation_id": operation_id,
                        "command_id": command.command_id,
                        "deadline_id": deadline_id,
                    },
                ),
            ),
            results=(
                _result(
                    command.command_id,
                    CommandStatus.ACCEPTED,
                    next_model.revision,
                    operation_id=operation_id,
                ),
            ),
        )

    if operation_id in model.retired_operation_ids:
        return _reject_command(
            model,
            command,
            "StaleOperation",
            "operation ID has already been retired",
        )
    if deadline_id in model.retired_deadline_ids or any(
        operation.deadline_id == deadline_id
        for operation in model.pending_operations.values()
    ):
        raise ValueError("deadline_id has already been allocated")

    if model.closed:
        return _reject_command(
            model, command, "Cancelled", "controller is closed"
        )
    if command.expected_revision is not None and command.expected_revision != model.revision:
        return _reject_command(
            model,
            command,
            "RevisionMismatch",
            "expected controller revision is stale",
        )
    if any(
        operation.command_id == command.command_id
        for operation in model.pending_operations.values()
    ):
        return _reject_command(
            model,
            command,
            "DuplicateCommand",
            "command ID is already pending under another operation",
        )
    if command.kind == "reconcile" and any(
        operation.command_kind == "reconcile"
        for operation in model.pending_operations.values()
    ):
        return _reject_command(
            model,
            command,
            "RecoveryInProgress",
            "one reconciliation barrier is already pending",
        )

    target_state, invalid = _accepted_target_state(model, command)
    if invalid is not None:
        return _reject_command(model, command, invalid[0], invalid[1])

    effect_kind = _effect_kind(command.kind)
    watermarks = model.generation_watermarks
    reservation = None
    effect_generation = model.generation
    if effect_kind in {EffectKind.OPEN_SESSION, EffectKind.SUBSCRIBE_EVENTS}:
        watermarks, reservation = reserve_generation(
            watermarks, model.generation, operation_id, effect_kind
        )
        effect_generation = reservation.reserved_stamp

    effect = GatewayEffect(
        operation_id=operation_id,
        command_id=command.command_id,
        kind=effect_kind,
        generation=effect_generation,
        payload=command.payload,
        idempotent=_idempotent(command.kind),
    )
    operation = PendingOperation(
        command=command,
        effect=effect,
        deadline_id=deadline_id,
        prior_target_state=model.target_state,
        reservation=reservation,
    )
    pending = dict(model.pending_operations)
    pending[operation_id] = operation
    epoch_store = model.epoch_store
    if command.kind in RUN_COMMANDS | STEP_COMMANDS | TERMINATE_COMMANDS:
        epoch_store = epoch_store.invalidate()
    recovery_status = model.recovery_status
    if command.kind == "reconcile":
        recovery_status = RecoveryStatus.IN_PROGRESS
    next_model = _with_revision(
        model,
        generation_watermarks=watermarks,
        target_state=target_state,
        recovery_status=recovery_status,
        epoch_store=epoch_store,
        pending_operations=pending,
    )
    result = _result(
        command.command_id,
        CommandStatus.ACCEPTED,
        next_model.revision,
        operation_id=operation_id,
    )
    event_payload: dict[str, Any] = {
        "command_id": command.command_id,
        "operation_id": operation_id,
        "deadline_id": deadline_id,
        "command_kind": command.kind,
    }
    if reservation is not None:
        event_payload["reserved_namespace"] = reservation.namespace
        event_payload["reserved_session_generation"] = (
            reservation.reserved_stamp.session_generation
        )
        event_payload["reserved_stream_generation"] = (
            reservation.reserved_stamp.stream_generation
        )
    return Reduction(
        next_model,
        effects=(effect,),
        events=(_event(next_model, "command_accepted", event_payload),),
        results=(result,),
    )


def _stale(model: ControllerModel, kind: str, payload: Mapping[str, Any]) -> Reduction:
    return Reduction(model, events=(_event(model, kind, payload),))


def _completion_failure_result(
    operation: PendingOperation, completion: GatewayCompletion, revision: int
) -> CommandResult:
    cancelled = completion.status is CompletionStatus.CANCELLED
    default_errors = {
        CompletionStatus.REJECTED: "Rejected",
        CompletionStatus.TRANSPORT_ERROR: "SessionUnavailable",
        CompletionStatus.PROTOCOL_ERROR: "ProtocolError",
        CompletionStatus.STALE: "Stale",
        CompletionStatus.CANCELLED: "Cancelled",
        CompletionStatus.UNSUPPORTED: "CapabilityUnavailable",
    }
    error = (
        completion.failure.code
        if completion.failure is not None
        else default_errors.get(completion.status, "OperationFailed")
    )
    diagnostic = completion.failure.message if completion.failure is not None else None
    return _result(
        operation.command_id,
        CommandStatus.CANCELLED if cancelled else CommandStatus.FAILED,
        revision,
        operation_id=operation.operation_id,
        error=error,
        diagnostic=diagnostic,
    )


def _profile_from_completion(
    completion: GatewayCompletion,
) -> tuple[CapabilityProfile | None, str | None]:
    raw = completion.response.get("capability_profile")
    if raw is None:
        return None, None
    if isinstance(raw, CapabilityProfile):
        profile = raw
    elif isinstance(raw, Mapping):
        try:
            profile = CapabilityProfile(
                profile_id=raw["profile_id"],
                generation=raw["generation"],
                capabilities=raw.get("capabilities", ()),
                degraded=raw["degraded"],
                diagnostics=raw.get("diagnostics", ()),
            )
        except (KeyError, TypeError, ValueError) as exc:
            return None, f"invalid capability profile: {exc}"
    else:
        return None, "invalid capability profile type"
    if profile.generation != completion.generation.capability_generation:
        return None, "capability profile generation does not match reserved stamp"
    return profile, None


def _promote_reserved(
    model: ControllerModel,
    operation: PendingOperation,
    completion: GatewayCompletion,
) -> Reduction:
    reservation = operation.reservation
    assert reservation is not None
    profile = model.capability_profile
    if reservation.kind is EffectKind.OPEN_SESSION:
        profile, profile_error = _profile_from_completion(completion)
        if profile_error is not None:
            pending = dict(model.pending_operations)
            pending.pop(operation.operation_id)
            next_model = _with_revision(
                model,
                pending_operations=pending,
                retired_operation_ids=(
                    model.retired_operation_ids | {operation.operation_id}
                ),
                retired_deadline_ids=(
                    model.retired_deadline_ids | {operation.deadline_id}
                ),
            )
            failed = _result(
                operation.command_id,
                CommandStatus.FAILED,
                next_model.revision,
                operation_id=operation.operation_id,
                error="ProtocolError",
                diagnostic=profile_error,
            )
            return Reduction(
                next_model,
                events=(
                    _event(
                        next_model,
                        "operation_completed",
                        {
                            "operation_id": operation.operation_id,
                            "command_id": operation.command_id,
                            "status": "protocol_error",
                        },
                    ),
                ),
                results=(failed,),
            )

    generation, watermarks, promoted = promote_generation(
        model.generation,
        model.generation_watermarks,
        reservation,
        completion,
    )
    if not promoted:
        return _stale(
            model,
            "stale_gateway_completion",
            {"operation_id": completion.operation_id},
        )

    retired = tuple(
        pending
        for pending_id, pending in model.pending_operations.items()
        if pending_id != operation.operation_id
    )
    if reservation.kind is EffectKind.OPEN_SESSION:
        rpc_health = RpcHealth.CONNECTING
        event_health = EventHealth.DISABLED
        active_stream_id = None
        target_state = (
            TargetRunState.NONE
            if generation.target_id is None and generation.display_pid is None
            else TargetRunState.UNKNOWN
        )
    else:
        rpc_health = model.rpc_health
        event_health = EventHealth.CONNECTING
        stream_id = completion.response.get("stream_id")
        active_stream_id = stream_id if isinstance(stream_id, str) and stream_id.strip() else None
        target_state = (
            model.target_state
            if model.target_state in {
                TargetRunState.NONE,
                TargetRunState.TERMINATED,
                TargetRunState.LOST,
            }
            else TargetRunState.UNKNOWN
        )

    recovery_status = (
        RecoveryStatus.IDLE
        if target_state in {TargetRunState.NONE, TargetRunState.TERMINATED}
        else RecoveryStatus.REQUIRED
    )
    next_model = _with_revision(
        model,
        generation=generation,
        generation_watermarks=watermarks,
        rpc_health=rpc_health,
        event_health=event_health,
        recovery_status=recovery_status,
        target_state=target_state,
        capability_profile=profile,
        epoch_store=model.epoch_store.reset_for_generation(),
        pending_operations={},
        retired_operation_ids=(
            model.retired_operation_ids | frozenset(model.pending_operations)
        ),
        retired_deadline_ids=(
            model.retired_deadline_ids
            | {pending.deadline_id for pending in model.pending_operations.values()}
        ),
        active_stream_id=active_stream_id,
        last_event_sequence=None,
    )
    results = [
        _result(
            operation.command_id,
            CommandStatus.COMPLETED,
            next_model.revision,
            operation_id=operation.operation_id,
        )
    ]
    results.extend(
        _result(
            pending.command_id,
            CommandStatus.CANCELLED,
            next_model.revision,
            operation_id=pending.operation_id,
            error="Stale",
            diagnostic="operation belongs to superseded continuity",
        )
        for pending in retired
    )
    events = [
        _event(
            next_model,
            "generation_promoted",
            {
                "operation_id": operation.operation_id,
                "namespace": reservation.namespace,
                "session_generation": generation.session_generation,
                "stream_generation": generation.stream_generation,
            },
        )
    ]
    events.extend(
        _event(
            next_model,
            "operation_cancelled",
            {"operation_id": pending.operation_id, "reason": "generation_promoted"},
        )
        for pending in retired
    )
    return Reduction(next_model, events=tuple(events), results=tuple(results))


def _reduce_reserved_completion(
    model: ControllerModel,
    operation: PendingOperation,
    completion: GatewayCompletion,
) -> Reduction:
    reservation = operation.reservation
    assert reservation is not None
    if not completion_matches_reservation(reservation, completion):
        return _stale(
            model,
            "stale_gateway_completion",
            {"operation_id": completion.operation_id},
        )
    if (
        completion.status is CompletionStatus.OK
        and completion.authority is CompletionAuthority.AUTHORITATIVE_RESOURCE_ESTABLISHED
    ):
        return _promote_reserved(model, operation, completion)
    if completion.status is CompletionStatus.OK:
        return Reduction(
            model,
            events=(
                _event(
                    model,
                    "operation_acknowledged",
                    {"operation_id": completion.operation_id},
                ),
            ),
        )

    pending = dict(model.pending_operations)
    pending.pop(operation.operation_id)
    next_model = _with_revision(
        model,
        pending_operations=pending,
        retired_operation_ids=model.retired_operation_ids | {operation.operation_id},
        retired_deadline_ids=model.retired_deadline_ids | {operation.deadline_id},
    )
    payload: dict[str, Any] = {
        "operation_id": completion.operation_id,
        "command_id": operation.command_id,
        "status": completion.status.value,
    }
    if completion.failure is not None:
        payload["error_code"] = completion.failure.code
    return Reduction(
        next_model,
        events=(_event(next_model, "operation_completed", payload),),
        results=(_completion_failure_result(operation, completion, next_model.revision),),
    )


def _reduce_completion(model: ControllerModel, completion: GatewayCompletion) -> Reduction:
    operation = model.pending_operations.get(completion.operation_id)
    if operation is None:
        return _stale(
            model,
            "unknown_gateway_completion",
            {"operation_id": completion.operation_id},
        )
    if operation.reservation is not None:
        return _reduce_reserved_completion(model, operation, completion)
    if completion.generation != model.generation or completion.generation != operation.generation:
        return _stale(
            model,
            "stale_gateway_completion",
            {"operation_id": completion.operation_id},
        )

    if completion.status is CompletionStatus.OK and (
        operation.command_kind in CONTROL_COMMANDS or operation.command_kind == "reconcile"
    ):
        return Reduction(
            model,
            events=(
                _event(
                    model,
                    "operation_acknowledged",
                    {"operation_id": completion.operation_id},
                ),
            ),
        )

    pending = dict(model.pending_operations)
    pending.pop(operation.operation_id)
    target_state = model.target_state
    recovery = model.recovery_status
    epoch_store = model.epoch_store
    if completion.status is not CompletionStatus.OK and operation.command_kind in CONTROL_COMMANDS:
        target_state = TargetRunState.UNKNOWN
        recovery = RecoveryStatus.REQUIRED
        epoch_store = epoch_store.invalidate()
    elif completion.status is not CompletionStatus.OK and operation.command_kind == "reconcile":
        target_state = (
            model.target_state
            if model.target_state
            in {TargetRunState.NONE, TargetRunState.TERMINATED, TargetRunState.LOST}
            else TargetRunState.UNKNOWN
        )
        recovery = RecoveryStatus.REQUIRED
        epoch_store = epoch_store.invalidate()
    next_model = _with_revision(
        model,
        pending_operations=pending,
        retired_operation_ids=model.retired_operation_ids | {operation.operation_id},
        retired_deadline_ids=model.retired_deadline_ids | {operation.deadline_id},
        target_state=target_state,
        recovery_status=recovery,
        epoch_store=epoch_store,
    )
    payload: dict[str, Any] = {
        "operation_id": completion.operation_id,
        "command_id": operation.command_id,
        "status": completion.status.value,
    }
    if completion.failure is not None:
        payload["error_code"] = completion.failure.code
    result = (
        _result(
            operation.command_id,
            CommandStatus.COMPLETED,
            next_model.revision,
            operation_id=operation.operation_id,
        )
        if completion.status is CompletionStatus.OK
        else _completion_failure_result(operation, completion, next_model.revision)
    )
    return Reduction(
        next_model,
        events=(_event(next_model, "operation_completed", payload),),
        results=(result,),
    )


def _event_target_state(event: GatewayEvent) -> TargetRunState | None:
    category = event.category.casefold()
    raw_state = event.payload.get("state")
    authoritative = {
        TargetRunState.UNKNOWN,
        TargetRunState.STOPPED,
        TargetRunState.RUNNING,
        TargetRunState.TERMINATED,
        TargetRunState.LOST,
    }
    if isinstance(raw_state, TargetRunState):
        return raw_state if raw_state in authoritative else None
    if isinstance(raw_state, str):
        try:
            parsed = TargetRunState(raw_state.casefold())
            return parsed if parsed in authoritative else None
        except ValueError:
            pass
    return {
        "stopped": TargetRunState.STOPPED,
        "running": TargetRunState.RUNNING,
        "resumed": TargetRunState.RUNNING,
        "terminated": TargetRunState.TERMINATED,
        "target_lost": TargetRunState.LOST,
    }.get(category)


def _stop_token(model: ControllerModel, event: GatewayEvent) -> tuple[Any | None, int]:
    supplied = event.payload.get("stop_token")
    if supplied is not None:
        return supplied, model.epoch_store.legacy_stop_counter
    if event.evidence_grade is EvidenceGrade.LEGACY_DEGRADED:
        return model.epoch_store.local_legacy_token(event.generation, event.sequence)
    return None, model.epoch_store.legacy_stop_counter


def _event_gap(
    model: ControllerModel,
    event: GatewayEvent,
    gap: EventGap,
) -> Reduction:
    next_model = _with_revision(
        model,
        event_health=EventHealth.GAP,
        recovery_status=RecoveryStatus.REQUIRED,
        target_state=(
            model.target_state
            if model.target_state in {
                TargetRunState.NONE,
                TargetRunState.TERMINATED,
                TargetRunState.LOST,
            }
            else TargetRunState.UNKNOWN
        ),
        epoch_store=model.epoch_store.invalidate(),
        # The observed event was not applied.  Keep the resumable cursor at the last event
        # whose state mutation was authoritative; reconciliation may later establish a new
        # baseline, but merely observing a later sequence can never advance application.
        last_event_sequence=model.last_event_sequence,
    )
    return Reduction(
        next_model,
        events=(
            _event(
                next_model,
                "event_gap",
                {
                    "stream_id": event.stream_id,
                    "expected_sequence": gap.expected_sequence,
                    "observed_sequence": gap.observed_sequence,
                },
            ),
        ),
    )


def _completed_kinds(target_state: TargetRunState) -> frozenset[str]:
    if target_state is TargetRunState.STOPPED:
        return STOP_COMMANDS | STEP_COMMANDS
    if target_state is TargetRunState.RUNNING:
        return RUN_COMMANDS
    if target_state in {TargetRunState.TERMINATED, TargetRunState.LOST}:
        return CONTROL_COMMANDS
    return frozenset()


def _reduce_event(
    model: ControllerModel, event: GatewayEvent, epoch_id: str | None
) -> Reduction:
    if event.generation != model.generation:
        return _stale(
            model,
            "stale_gateway_event",
            {"stream_id": event.stream_id, "sequence": event.sequence},
        )
    if model.active_stream_id is not None and event.stream_id != model.active_stream_id:
        return _stale(
            model,
            "stale_gateway_event",
            {"stream_id": event.stream_id, "sequence": event.sequence},
        )
    if model.event_health in {EventHealth.GAP, EventHealth.LOST} or model.recovery_status not in {
        RecoveryStatus.IDLE,
        RecoveryStatus.RETAINED,
    }:
        return _stale(
            model,
            "event_awaiting_reconcile",
            {
                "stream_id": event.stream_id,
                "sequence": event.sequence,
                "event_health": model.event_health.value,
                "recovery_status": model.recovery_status.value,
            },
        )
    if event.sequence is not None and model.last_event_sequence is not None:
        if event.sequence <= model.last_event_sequence:
            return _stale(
                model,
                "duplicate_gateway_event",
                {"stream_id": event.stream_id, "sequence": event.sequence},
            )
        if event.sequence > model.last_event_sequence + 1 and event.gap is None:
            return _event_gap(
                model,
                event,
                EventGap(
                    expected_sequence=model.last_event_sequence + 1,
                    observed_sequence=event.sequence,
                    reason="non-contiguous controller event sequence",
                    reconciliation_required=True,
                ),
            )
    if event.gap is not None:
        return _event_gap(model, event, event.gap)

    target_state = _event_target_state(event)
    last_sequence = event.sequence or model.last_event_sequence
    if target_state is None:
        next_model = (
            _with_revision(model, last_event_sequence=last_sequence)
            if last_sequence != model.last_event_sequence
            else model
        )
        return Reduction(
            next_model,
            events=(_event(next_model, "gateway_event", {"category": event.category}),),
        )

    epoch_store = model.epoch_store
    recovery = model.recovery_status
    if target_state is TargetRunState.STOPPED:
        token, counter = _stop_token(model, event)
        if token is None or not isinstance(epoch_id, str) or not epoch_id.strip():
            return _stale(
                model,
                "invalid_stop_evidence",
                {"stream_id": event.stream_id, "sequence": event.sequence},
            )
        if (
            epoch_store.active is not None
            and epoch_store.active.generation == event.generation
            and epoch_store.active.stop_token == token
        ):
            next_model = (
                _with_revision(model, last_event_sequence=last_sequence)
                if last_sequence != model.last_event_sequence
                else model
            )
            return Reduction(
                next_model,
                events=(
                    _event(
                        next_model,
                        "duplicate_stop_ignored",
                        {"epoch_id": epoch_store.active.epoch_id},
                    ),
                ),
            )
        epoch_store = epoch_store.open_epoch(
            epoch_id=epoch_id,
            generation=event.generation,
            stop_token=token,
            snapshot_ref=event.payload.get("snapshot_ref"),
            evidence_grade=event.evidence_grade,
            legacy_stop_counter=counter,
        )
    else:
        epoch_store = epoch_store.invalidate()
        if target_state is TargetRunState.LOST:
            recovery = RecoveryStatus.TARGET_LOST

    pending = dict(model.pending_operations)
    completed: list[PendingOperation] = []
    explicit_operation_id = event.payload.get("operation_id")
    if isinstance(explicit_operation_id, str):
        candidate = pending.get(explicit_operation_id)
        if candidate is not None and candidate.command_kind in _completed_kinds(target_state):
            completed.append(pending.pop(explicit_operation_id))
    else:
        completed_kinds = _completed_kinds(target_state)
        for operation_id, operation in tuple(pending.items()):
            if operation.command_kind in completed_kinds:
                completed.append(pending.pop(operation_id))

    next_model = _with_revision(
        model,
        target_state=target_state,
        epoch_store=epoch_store,
        recovery_status=recovery,
        pending_operations=pending,
        retired_operation_ids=(
            model.retired_operation_ids
            | {operation.operation_id for operation in completed}
        ),
        retired_deadline_ids=(
            model.retired_deadline_ids
            | {operation.deadline_id for operation in completed}
        ),
        last_event_sequence=last_sequence,
    )
    payload: dict[str, Any] = {
        "target_state": target_state.value,
        "stream_id": event.stream_id,
    }
    if event.sequence is not None:
        payload["sequence"] = event.sequence
    if epoch_store.active is not None:
        payload["epoch_id"] = epoch_store.active.epoch_id
    results = tuple(
        _result(
            operation.command_id,
            CommandStatus.COMPLETED,
            next_model.revision,
            operation_id=operation.operation_id,
        )
        for operation in completed
    )
    return Reduction(
        next_model,
        events=(_event(next_model, "target_state_changed", payload),),
        results=results,
    )


def _reduce_health(model: ControllerModel, notice: HealthNotice) -> Reduction:
    if notice.generation != model.generation:
        return _stale(model, "stale_health_notice", {"reason": notice.reason})
    epoch_store = model.epoch_store
    target_state = model.target_state
    recovery = model.recovery_status
    if (
        notice.rpc_health in {RpcHealth.CLOSED, RpcHealth.LOST}
        or notice.event_health in {EventHealth.GAP, EventHealth.LOST}
    ):
        epoch_store = epoch_store.invalidate()
        if target_state not in {
            TargetRunState.NONE,
            TargetRunState.TERMINATED,
            TargetRunState.LOST,
        }:
            target_state = TargetRunState.UNKNOWN
        recovery = RecoveryStatus.REQUIRED
    if (
        notice.rpc_health is model.rpc_health
        and notice.event_health is model.event_health
        and epoch_store is model.epoch_store
        and recovery is model.recovery_status
        and target_state is model.target_state
    ):
        return Reduction(model)
    next_model = _with_revision(
        model,
        rpc_health=notice.rpc_health,
        event_health=notice.event_health,
        epoch_store=epoch_store,
        target_state=target_state,
        recovery_status=recovery,
    )
    return Reduction(
        next_model,
        events=(
            _event(
                next_model,
                "health_changed",
                {
                    "rpc_health": notice.rpc_health.value,
                    "event_health": notice.event_health.value,
                    "reason": notice.reason,
                },
            ),
        ),
    )


def _baseline_target_state(result: ReconcileResult) -> TargetRunState:
    raw = result.baseline.get("target_state", TargetRunState.UNKNOWN)
    authoritative = {
        TargetRunState.UNKNOWN,
        TargetRunState.STOPPED,
        TargetRunState.RUNNING,
        TargetRunState.TERMINATED,
        TargetRunState.LOST,
    }
    if isinstance(raw, TargetRunState):
        return raw if raw in authoritative else TargetRunState.UNKNOWN
    if isinstance(raw, str):
        try:
            parsed = TargetRunState(raw.casefold())
            return parsed if parsed in authoritative else TargetRunState.UNKNOWN
        except ValueError:
            pass
    return TargetRunState.UNKNOWN


def _reduce_reconcile(
    model: ControllerModel, result: ReconcileResult, epoch_id: str | None
) -> Reduction:
    if result.generation != model.generation:
        return _stale(model, "stale_reconcile_result", {"status": result.status.value})

    reconciled_operations = tuple(
        operation
        for operation in model.pending_operations.values()
        if operation.command_kind == "reconcile"
    )
    if len(reconciled_operations) != 1:
        return _stale(
            model,
            "uncorrelated_reconcile_result",
            {"status": result.status.value},
        )
    operation = reconciled_operations[0]

    epoch_store = model.epoch_store
    target_state = model.target_state
    recovery_map = {
        ReconcileStatus.RETAINED: RecoveryStatus.RETAINED,
        ReconcileStatus.TARGET_LOST: RecoveryStatus.TARGET_LOST,
        ReconcileStatus.OWNERSHIP_LOST: RecoveryStatus.OWNERSHIP_LOST,
        ReconcileStatus.INCOMPATIBLE: RecoveryStatus.INCOMPATIBLE,
        ReconcileStatus.EXHAUSTED: RecoveryStatus.EXHAUSTED,
        ReconcileStatus.LEGACY_UNPROVEN: RecoveryStatus.REQUIRED,
    }
    recovery = recovery_map[result.status]

    if result.status is ReconcileStatus.RETAINED:
        target_state = _baseline_target_state(result)
        if target_state is TargetRunState.STOPPED:
            token = result.baseline.get("stop_token")
            if token is None or not isinstance(epoch_id, str) or not epoch_id.strip():
                target_state = TargetRunState.UNKNOWN
                recovery = RecoveryStatus.REQUIRED
                epoch_store = epoch_store.invalidate()
            elif (
                epoch_store.active is None
                or epoch_store.active.stop_token != token
                or epoch_store.active.generation != result.generation
            ):
                epoch_store = epoch_store.open_epoch(
                    epoch_id=epoch_id,
                    generation=result.generation,
                    stop_token=token,
                    snapshot_ref=result.baseline.get("snapshot_ref"),
                    evidence_grade=result.evidence_grade,
                )
        else:
            epoch_store = epoch_store.invalidate()
    else:
        epoch_store = epoch_store.invalidate()
        target_state = (
            TargetRunState.LOST
            if result.status is ReconcileStatus.TARGET_LOST
            else TargetRunState.UNKNOWN
        )

    pending = {
        operation_id: operation
        for operation_id, operation in model.pending_operations.items()
        if operation.command_kind != "reconcile"
    }
    next_model = _with_revision(
        model,
        recovery_status=recovery,
        target_state=target_state,
        epoch_store=epoch_store,
        pending_operations=pending,
        retired_operation_ids=(
            model.retired_operation_ids
            | {operation.operation_id}
        ),
        retired_deadline_ids=model.retired_deadline_ids | {operation.deadline_id},
        event_health=(
            EventHealth.HEALTHY
            if recovery is RecoveryStatus.RETAINED
            and model.event_health in {EventHealth.GAP, EventHealth.LOST}
            else model.event_health
        ),
    )
    if recovery is RecoveryStatus.RETAINED:
        command_result = _result(
            operation.command_id,
            CommandStatus.COMPLETED,
            next_model.revision,
            operation_id=operation.operation_id,
        )
    else:
        errors = {
            ReconcileStatus.RETAINED: "RecoveryFailed",
            ReconcileStatus.TARGET_LOST: "TargetLost",
            ReconcileStatus.OWNERSHIP_LOST: "OwnershipLost",
            ReconcileStatus.INCOMPATIBLE: "CapabilityUnavailable",
            ReconcileStatus.EXHAUSTED: "RecoveryFailed",
            ReconcileStatus.LEGACY_UNPROVEN: "RecoveryFailed",
        }
        command_result = _result(
            operation.command_id,
            CommandStatus.FAILED,
            next_model.revision,
            operation_id=operation.operation_id,
            error=errors[result.status],
            diagnostic=(
                result.diagnostics[0]
                if result.diagnostics
                else f"reconciliation ended with {result.status.value}"
            ),
        )
    return Reduction(
        next_model,
        events=(
            _event(
                next_model,
                "reconciled",
                {
                    "status": result.status.value,
                    "target_state": target_state.value,
                    "command_id": operation.command_id,
                    "operation_id": operation.operation_id,
                },
            ),
        ),
        results=(command_result,),
    )


def reduce_notice(
    model: ControllerModel, notice: GatewayNotice, *, epoch_id: str | None = None
) -> Reduction:
    """Apply one exact-fenced gateway notice without I/O or waiting."""

    if not isinstance(model, ControllerModel):
        raise TypeError("model must be ControllerModel")
    if isinstance(notice, GatewayCompletion):
        return _reduce_completion(model, notice)
    if isinstance(notice, GatewayEvent):
        return _reduce_event(model, notice, epoch_id)
    if isinstance(notice, HealthNotice):
        return _reduce_health(model, notice)
    if isinstance(notice, ReconcileResult):
        return _reduce_reconcile(model, notice, epoch_id)
    raise TypeError(f"unsupported gateway notice {type(notice).__name__}")


def reduce_deadline(model: ControllerModel, expired: DeadlineExpired) -> Reduction:
    """Expire only the exact pending effect; never infer target run/stop truth."""

    if not isinstance(model, ControllerModel):
        raise TypeError("model must be ControllerModel")
    if not isinstance(expired, DeadlineExpired):
        raise TypeError("expired must be DeadlineExpired")
    operation = model.pending_operations.get(expired.operation_id)
    if operation is None:
        return _stale(
            model,
            "unknown_deadline",
            {"deadline_id": expired.deadline_id, "operation_id": expired.operation_id},
        )
    if (
        expired.generation != operation.generation
        or expired.deadline_id != operation.deadline_id
    ):
        return _stale(
            model,
            "stale_deadline",
            {"deadline_id": expired.deadline_id, "operation_id": expired.operation_id},
        )

    pending = dict(model.pending_operations)
    pending.pop(expired.operation_id)
    target_state = model.target_state
    recovery_status = model.recovery_status
    epoch_store = model.epoch_store
    if operation.command_kind in CONTROL_COMMANDS:
        target_state = TargetRunState.UNKNOWN
        recovery_status = RecoveryStatus.REQUIRED
        epoch_store = epoch_store.invalidate()
    elif operation.command_kind == "reconcile":
        target_state = (
            model.target_state
            if model.target_state
            in {TargetRunState.NONE, TargetRunState.TERMINATED, TargetRunState.LOST}
            else TargetRunState.UNKNOWN
        )
        recovery_status = RecoveryStatus.REQUIRED
        epoch_store = epoch_store.invalidate()
    next_model = _with_revision(
        model,
        pending_operations=pending,
        retired_operation_ids=model.retired_operation_ids | {operation.operation_id},
        retired_deadline_ids=model.retired_deadline_ids | {operation.deadline_id},
        target_state=target_state,
        recovery_status=recovery_status,
        epoch_store=epoch_store,
    )
    return Reduction(
        next_model,
        events=(
            _event(
                next_model,
                "operation_deadline_expired",
                {
                    "deadline_id": expired.deadline_id,
                    "operation_id": expired.operation_id,
                    "command_id": operation.command_id,
                },
            ),
        ),
        results=(
            _result(
                operation.command_id,
                CommandStatus.FAILED,
                next_model.revision,
                operation_id=operation.operation_id,
                error="OperationTimeout",
                diagnostic="operation deadline expired",
            ),
        ),
    )


def close_model(model: ControllerModel) -> Reduction:
    """Close idempotently, invalidating state and resolving every live operation once."""

    if not isinstance(model, ControllerModel):
        raise TypeError("model must be ControllerModel")
    if model.closed:
        return Reduction(
            model,
            results=(
                _result(
                    "controller-close",
                    CommandStatus.COMPLETED,
                    model.revision,
                ),
            ),
        )
    next_model = _with_revision(
        model,
        rpc_health=RpcHealth.CLOSED,
        event_health=EventHealth.DISABLED,
        recovery_status=RecoveryStatus.IDLE,
        target_state=(
            model.target_state
            if model.target_state in {
                TargetRunState.NONE,
                TargetRunState.TERMINATED,
                TargetRunState.LOST,
            }
            else TargetRunState.UNKNOWN
        ),
        epoch_store=model.epoch_store.invalidate(),
        pending_operations={},
        retired_operation_ids=(
            model.retired_operation_ids | frozenset(model.pending_operations)
        ),
        retired_deadline_ids=(
            model.retired_deadline_ids
            | {operation.deadline_id for operation in model.pending_operations.values()}
        ),
        closed=True,
    )
    cancelled = tuple(
        _result(
            operation.command_id,
            CommandStatus.CANCELLED,
            next_model.revision,
            operation_id=operation.operation_id,
            error="Cancelled",
            diagnostic="controller closed while operation was pending",
        )
        for operation in model.pending_operations.values()
    )
    closed = _result(
        "controller-close", CommandStatus.COMPLETED, next_model.revision
    )
    return Reduction(
        next_model,
        events=(_event(next_model, "controller_closed", {}),),
        results=cancelled + (closed,),
    )


__all__ = [
    "CONTROL_COMMANDS",
    "RUN_COMMANDS",
    "Reduction",
    "STEP_COMMANDS",
    "STOP_COMMANDS",
    "TERMINATE_COMMANDS",
    "close_model",
    "reduce_command",
    "reduce_deadline",
    "reduce_notice",
]
