"""Frozen controller/gateway contracts for ``dbg.controller-gateway/1.1``.

This module contains values and pure generation-handshake helpers only.  It deliberately
contains no controller actor, gateway worker, transport, Executive, or frontend behavior.
"""

from __future__ import annotations

from concurrent.futures import Future
from dataclasses import dataclass, field, fields, is_dataclass, replace
from enum import Enum
from types import MappingProxyType
from typing import (
    Any,
    Callable,
    FrozenSet,
    Mapping,
    Optional,
    Protocol,
    Tuple,
    TypeAlias,
    runtime_checkable,
)


class EvidenceGrade(str, Enum):
    PORTABLE = "portable"
    LEGACY_DEGRADED = "legacy_degraded"


class RpcHealth(str, Enum):
    CLOSED = "closed"
    CONNECTING = "connecting"
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    LOST = "lost"


class EventHealth(str, Enum):
    DISABLED = "disabled"
    CONNECTING = "connecting"
    HEALTHY = "healthy"
    GAP = "gap"
    LOST = "lost"


class RecoveryStatus(str, Enum):
    IDLE = "idle"
    REQUIRED = "required"
    IN_PROGRESS = "in_progress"
    RETAINED = "retained"
    TARGET_LOST = "target_lost"
    OWNERSHIP_LOST = "ownership_lost"
    INCOMPATIBLE = "incompatible"
    EXHAUSTED = "exhausted"


class TargetRunState(str, Enum):
    NONE = "none"
    UNKNOWN = "unknown"
    STOPPED = "stopped"
    RUN_PENDING = "run_pending"
    RUNNING = "running"
    STOP_PENDING = "stop_pending"
    STEP_PENDING = "step_pending"
    TERMINATED = "terminated"
    LOST = "lost"


class EffectKind(str, Enum):
    OPEN_SESSION = "open_session"
    CLOSE_SESSION = "close_session"
    REQUEST = "request"
    SUBSCRIBE_EVENTS = "subscribe_events"
    UNSUBSCRIBE_EVENTS = "unsubscribe_events"
    RECONCILE = "reconcile"


class CompletionStatus(str, Enum):
    OK = "ok"
    REJECTED = "rejected"
    TRANSPORT_ERROR = "transport_error"
    PROTOCOL_ERROR = "protocol_error"
    STALE = "stale"
    CANCELLED = "cancelled"
    UNSUPPORTED = "unsupported"


class CompletionAuthority(str, Enum):
    ACK_ONLY = "ack_only"
    AUTHORITATIVE_RESOURCE_ESTABLISHED = "authoritative_resource_established"


class ReconcileStatus(str, Enum):
    RETAINED = "retained"
    TARGET_LOST = "target_lost"
    OWNERSHIP_LOST = "ownership_lost"
    INCOMPATIBLE = "incompatible"
    EXHAUSTED = "exhausted"
    LEGACY_UNPROVEN = "legacy_unproven"


class CommandStatus(str, Enum):
    ACCEPTED = "accepted"
    COMPLETED = "completed"
    REJECTED = "rejected"
    FAILED = "failed"
    CANCELLED = "cancelled"


_EMPTY_MAPPING: Mapping[str, Any] = MappingProxyType({})
_SESSION_NAMESPACE = "session"
_STREAM_NAMESPACE = "stream"
_LEGACY_PROFILE_ID = "hsx.python-debug-legacy/1"
_LEGACY_CAPABILITIES = frozenset(
    {
        "hsx.legacy-event-stream/1",
        "hsx.legacy-debug-resources/1",
    }
)


def _require_nonempty(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field_name} must be a non-empty string")


def _require_optional_nonempty(value: Optional[str], field_name: str) -> None:
    if value is not None:
        _require_nonempty(value, field_name)


def _require_nonnegative(value: int, field_name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{field_name} must be a non-negative integer")


def _require_optional_nonnegative(value: Optional[int], field_name: str) -> None:
    if value is not None:
        _require_nonnegative(value, field_name)


def _require_bool(value: bool, field_name: str) -> None:
    if not isinstance(value, bool):
        raise TypeError(f"{field_name} must be a bool")


def _require_enum(value: Any, enum_type: type[Enum], field_name: str) -> None:
    if not isinstance(value, enum_type):
        raise TypeError(f"{field_name} must be {enum_type.__name__}")


def _frozen_dataclass_instance(value: Any) -> bool:
    if not is_dataclass(value) or isinstance(value, type):
        return False
    params = getattr(type(value), "__dataclass_params__", None)
    return bool(params and params.frozen)


def _assert_deeply_immutable(value: Any) -> None:
    if isinstance(value, MappingProxyType):
        for key, item in value.items():
            _assert_deeply_immutable(key)
            _assert_deeply_immutable(item)
        return
    if isinstance(value, (tuple, frozenset)):
        for item in value:
            _assert_deeply_immutable(item)
        return
    if isinstance(value, (str, bytes, int, float, bool, type(None), Enum)):
        return
    if _frozen_dataclass_instance(value):
        for field_info in fields(value):
            _assert_deeply_immutable(getattr(value, field_info.name))
        return
    raise TypeError(f"unsupported mutable payload value: {type(value).__name__}")


def _freeze(value: Any) -> Any:
    """Defensively copy containers and reject opaque mutable payload objects."""

    if isinstance(value, Mapping):
        return MappingProxyType({_freeze(key): _freeze(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    if isinstance(value, (set, frozenset)):
        return frozenset(_freeze(item) for item in value)
    if isinstance(value, (str, bytes, int, float, bool, type(None), Enum)):
        return value
    if _frozen_dataclass_instance(value):
        _assert_deeply_immutable(value)
        return value
    raise TypeError(f"unsupported mutable payload value: {type(value).__name__}")


def _freeze_mapping(value: Mapping[str, Any], field_name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{field_name} must be a mapping")
    frozen = _freeze(value)
    assert isinstance(frozen, Mapping)
    return frozen


def _freeze_strings(value: Any, field_name: str, *, as_set: bool = False) -> Any:
    if isinstance(value, str) or not isinstance(value, (list, tuple, set, frozenset)):
        raise TypeError(f"{field_name} must be a collection of strings")
    items = tuple(value)
    for item in items:
        _require_nonempty(item, field_name)
    return frozenset(items) if as_set else items


@dataclass(frozen=True, slots=True)
class GenerationStamp:
    executive_instance_id: Optional[str]
    session_generation: int
    target_id: Optional[str]
    target_generation: int
    capability_generation: int
    stream_generation: int
    display_pid: Optional[int]
    evidence_grade: EvidenceGrade

    def __post_init__(self) -> None:
        _require_optional_nonempty(self.executive_instance_id, "executive_instance_id")
        _require_nonnegative(self.session_generation, "session_generation")
        _require_optional_nonempty(self.target_id, "target_id")
        _require_nonnegative(self.target_generation, "target_generation")
        _require_nonnegative(self.capability_generation, "capability_generation")
        _require_nonnegative(self.stream_generation, "stream_generation")
        if self.display_pid is not None and (
            isinstance(self.display_pid, bool) or not isinstance(self.display_pid, int)
        ):
            raise TypeError("display_pid must be an integer or None")
        _require_enum(self.evidence_grade, EvidenceGrade, "evidence_grade")


@dataclass(frozen=True, slots=True)
class GenerationWatermarks:
    session: int = 0
    stream: int = 0

    def __post_init__(self) -> None:
        _require_nonnegative(self.session, "session")
        _require_nonnegative(self.stream, "stream")


@dataclass(frozen=True, slots=True)
class GenerationReservation:
    operation_id: str
    kind: EffectKind
    reserved_stamp: GenerationStamp
    active_parent_stamp: GenerationStamp
    namespace: str

    def __post_init__(self) -> None:
        _require_nonempty(self.operation_id, "operation_id")
        _require_enum(self.kind, EffectKind, "kind")
        if not isinstance(self.reserved_stamp, GenerationStamp):
            raise TypeError("reserved_stamp must be GenerationStamp")
        if not isinstance(self.active_parent_stamp, GenerationStamp):
            raise TypeError("active_parent_stamp must be GenerationStamp")
        if self.kind is EffectKind.OPEN_SESSION:
            if self.namespace != _SESSION_NAMESPACE:
                raise ValueError("OPEN_SESSION must consume the session namespace")
            if (
                self.reserved_stamp.session_generation
                <= self.active_parent_stamp.session_generation
            ):
                raise ValueError("OPEN_SESSION must reserve a later session generation")
            if self.reserved_stamp.stream_generation != 0:
                raise ValueError("OPEN_SESSION candidate stream generation must be zero")
        elif self.kind is EffectKind.SUBSCRIBE_EVENTS:
            if self.namespace != _STREAM_NAMESPACE:
                raise ValueError("SUBSCRIBE_EVENTS must consume the stream namespace")
            expected = replace(
                self.active_parent_stamp,
                stream_generation=self.reserved_stamp.stream_generation,
            )
            if self.reserved_stamp != expected:
                raise ValueError("SUBSCRIBE_EVENTS must retain the exact active session parent")
            if self.reserved_stamp.stream_generation <= self.active_parent_stamp.stream_generation:
                raise ValueError("SUBSCRIBE_EVENTS must reserve a later stream generation")
        else:
            raise ValueError("generation reservations are limited to OPEN_SESSION/SUBSCRIBE_EVENTS")


@dataclass(frozen=True, slots=True)
class CapabilityProfile:
    profile_id: str
    generation: int
    capabilities: FrozenSet[str]
    degraded: bool
    diagnostics: Tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _require_nonempty(self.profile_id, "profile_id")
        _require_nonnegative(self.generation, "generation")
        object.__setattr__(
            self, "capabilities", _freeze_strings(self.capabilities, "capabilities", as_set=True)
        )
        _require_bool(self.degraded, "degraded")
        object.__setattr__(self, "diagnostics", _freeze_strings(self.diagnostics, "diagnostics"))
        if self.profile_id == _LEGACY_PROFILE_ID:
            if not self.degraded:
                raise ValueError("the legacy capability profile must be degraded")
            unsupported = self.capabilities - _LEGACY_CAPABILITIES
            if unsupported:
                raise ValueError("the legacy capability profile may name only legacy capabilities")


@dataclass(frozen=True, slots=True)
class ControllerCommand:
    command_id: str
    kind: str
    expected_revision: Optional[int] = None
    payload: Mapping[str, Any] = field(default_factory=lambda: _EMPTY_MAPPING)

    def __post_init__(self) -> None:
        _require_nonempty(self.command_id, "command_id")
        _require_nonempty(self.kind, "kind")
        _require_optional_nonnegative(self.expected_revision, "expected_revision")
        object.__setattr__(self, "payload", _freeze_mapping(self.payload, "payload"))


@dataclass(frozen=True, slots=True)
class GatewayEffect:
    operation_id: str
    command_id: str
    kind: EffectKind
    generation: GenerationStamp
    payload: Mapping[str, Any]
    idempotent: bool

    def __post_init__(self) -> None:
        _require_nonempty(self.operation_id, "operation_id")
        _require_nonempty(self.command_id, "command_id")
        _require_enum(self.kind, EffectKind, "kind")
        if not isinstance(self.generation, GenerationStamp):
            raise TypeError("generation must be GenerationStamp")
        object.__setattr__(self, "payload", _freeze_mapping(self.payload, "payload"))
        _require_bool(self.idempotent, "idempotent")


@dataclass(frozen=True, slots=True)
class GatewayFailure:
    code: str
    message: str
    retryable: bool
    cause: Optional[str] = None

    def __post_init__(self) -> None:
        _require_nonempty(self.code, "code")
        if not isinstance(self.message, str):
            raise TypeError("message must be a string")
        _require_bool(self.retryable, "retryable")
        _require_optional_nonempty(self.cause, "cause")


@dataclass(frozen=True, slots=True)
class GatewayCompletion:
    operation_id: str
    generation: GenerationStamp
    status: CompletionStatus
    evidence_grade: EvidenceGrade
    response: Mapping[str, Any] = field(default_factory=lambda: _EMPTY_MAPPING)
    failure: Optional[GatewayFailure] = None
    authority: CompletionAuthority = CompletionAuthority.ACK_ONLY

    def __post_init__(self) -> None:
        _require_nonempty(self.operation_id, "operation_id")
        if not isinstance(self.generation, GenerationStamp):
            raise TypeError("generation must be GenerationStamp")
        _require_enum(self.status, CompletionStatus, "status")
        _require_enum(self.evidence_grade, EvidenceGrade, "evidence_grade")
        if self.evidence_grade is not self.generation.evidence_grade:
            raise ValueError("completion evidence_grade must match its generation stamp")
        object.__setattr__(self, "response", _freeze_mapping(self.response, "response"))
        if self.failure is not None and not isinstance(self.failure, GatewayFailure):
            raise TypeError("failure must be GatewayFailure or None")
        _require_enum(self.authority, CompletionAuthority, "authority")


@dataclass(frozen=True, slots=True)
class EventGap:
    expected_sequence: int
    observed_sequence: int
    reason: str
    reconciliation_required: bool

    def __post_init__(self) -> None:
        _require_nonnegative(self.expected_sequence, "expected_sequence")
        _require_nonnegative(self.observed_sequence, "observed_sequence")
        _require_nonempty(self.reason, "reason")
        _require_bool(self.reconciliation_required, "reconciliation_required")


@dataclass(frozen=True, slots=True)
class GatewayEvent:
    generation: GenerationStamp
    stream_id: str
    sequence: Optional[int]
    category: str
    payload: Mapping[str, Any]
    evidence_grade: EvidenceGrade
    gap: Optional[EventGap] = None

    def __post_init__(self) -> None:
        if not isinstance(self.generation, GenerationStamp):
            raise TypeError("generation must be GenerationStamp")
        _require_nonempty(self.stream_id, "stream_id")
        if self.sequence is not None:
            _require_nonnegative(self.sequence, "sequence")
            if self.sequence == 0:
                raise ValueError("sequence must be positive when present")
        _require_nonempty(self.category, "category")
        object.__setattr__(self, "payload", _freeze_mapping(self.payload, "payload"))
        _require_enum(self.evidence_grade, EvidenceGrade, "evidence_grade")
        if self.evidence_grade is not self.generation.evidence_grade:
            raise ValueError("event evidence_grade must match its generation stamp")
        if self.gap is not None and not isinstance(self.gap, EventGap):
            raise TypeError("gap must be EventGap or None")


@dataclass(frozen=True, slots=True)
class HealthNotice:
    generation: GenerationStamp
    rpc_health: RpcHealth
    event_health: EventHealth
    reason: str

    def __post_init__(self) -> None:
        if not isinstance(self.generation, GenerationStamp):
            raise TypeError("generation must be GenerationStamp")
        _require_enum(self.rpc_health, RpcHealth, "rpc_health")
        _require_enum(self.event_health, EventHealth, "event_health")
        if not isinstance(self.reason, str):
            raise TypeError("reason must be a string")


@dataclass(frozen=True, slots=True)
class ReconcileResult:
    generation: GenerationStamp
    status: ReconcileStatus
    evidence_grade: EvidenceGrade
    baseline: Mapping[str, Any] = field(default_factory=lambda: _EMPTY_MAPPING)
    diagnostics: Tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.generation, GenerationStamp):
            raise TypeError("generation must be GenerationStamp")
        _require_enum(self.status, ReconcileStatus, "status")
        _require_enum(self.evidence_grade, EvidenceGrade, "evidence_grade")
        if self.evidence_grade is not self.generation.evidence_grade:
            raise ValueError("reconcile evidence_grade must match its generation stamp")
        object.__setattr__(self, "baseline", _freeze_mapping(self.baseline, "baseline"))
        object.__setattr__(self, "diagnostics", _freeze_strings(self.diagnostics, "diagnostics"))


@dataclass(frozen=True, slots=True)
class DeadlineExpired:
    deadline_id: str
    operation_id: str
    generation: GenerationStamp

    def __post_init__(self) -> None:
        _require_nonempty(self.deadline_id, "deadline_id")
        _require_nonempty(self.operation_id, "operation_id")
        if not isinstance(self.generation, GenerationStamp):
            raise TypeError("generation must be GenerationStamp")


@dataclass(frozen=True, slots=True)
class StopEpoch:
    epoch_id: str
    generation: GenerationStamp
    stop_token: Any
    snapshot_ref: Any
    evidence_grade: EvidenceGrade

    def __post_init__(self) -> None:
        _require_nonempty(self.epoch_id, "epoch_id")
        if not isinstance(self.generation, GenerationStamp):
            raise TypeError("generation must be GenerationStamp")
        if self.stop_token is None:
            raise ValueError("stop_token must be present")
        object.__setattr__(self, "stop_token", _freeze(self.stop_token))
        if self.snapshot_ref is not None:
            object.__setattr__(self, "snapshot_ref", _freeze(self.snapshot_ref))
        _require_enum(self.evidence_grade, EvidenceGrade, "evidence_grade")
        if self.evidence_grade is not self.generation.evidence_grade:
            raise ValueError("epoch evidence_grade must match its generation stamp")


@dataclass(frozen=True, slots=True)
class ControllerSnapshot:
    controller_revision: int
    generation: GenerationStamp
    rpc_health: RpcHealth
    event_health: EventHealth
    recovery_status: RecoveryStatus
    target_state: TargetRunState
    capability_profile: Optional[CapabilityProfile] = None
    active_epoch: Optional[StopEpoch] = None
    pending_operation_ids: Tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _require_nonnegative(self.controller_revision, "controller_revision")
        if not isinstance(self.generation, GenerationStamp):
            raise TypeError("generation must be GenerationStamp")
        _require_enum(self.rpc_health, RpcHealth, "rpc_health")
        _require_enum(self.event_health, EventHealth, "event_health")
        _require_enum(self.recovery_status, RecoveryStatus, "recovery_status")
        _require_enum(self.target_state, TargetRunState, "target_state")
        if self.capability_profile is not None and not isinstance(
            self.capability_profile, CapabilityProfile
        ):
            raise TypeError("capability_profile must be CapabilityProfile or None")
        if self.active_epoch is not None and not isinstance(self.active_epoch, StopEpoch):
            raise TypeError("active_epoch must be StopEpoch or None")
        pending = _freeze_strings(self.pending_operation_ids, "pending_operation_ids")
        if len(set(pending)) != len(pending):
            raise ValueError("pending_operation_ids must be unique")
        object.__setattr__(self, "pending_operation_ids", pending)


@dataclass(frozen=True, slots=True)
class CommandResult:
    command_id: str
    status: CommandStatus
    controller_revision: int
    operation_id: Optional[str] = None
    error: Optional[str] = None
    diagnostics: Tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _require_nonempty(self.command_id, "command_id")
        _require_enum(self.status, CommandStatus, "status")
        _require_nonnegative(self.controller_revision, "controller_revision")
        _require_optional_nonempty(self.operation_id, "operation_id")
        _require_optional_nonempty(self.error, "error")
        object.__setattr__(self, "diagnostics", _freeze_strings(self.diagnostics, "diagnostics"))


@dataclass(frozen=True, slots=True)
class ControllerEvent:
    controller_revision: int
    kind: str
    generation: GenerationStamp
    payload: Mapping[str, Any] = field(default_factory=lambda: _EMPTY_MAPPING)

    def __post_init__(self) -> None:
        _require_nonnegative(self.controller_revision, "controller_revision")
        _require_nonempty(self.kind, "kind")
        if not isinstance(self.generation, GenerationStamp):
            raise TypeError("generation must be GenerationStamp")
        object.__setattr__(self, "payload", _freeze_mapping(self.payload, "payload"))


GatewayNotice: TypeAlias = GatewayCompletion | GatewayEvent | HealthNotice | ReconcileResult


@runtime_checkable
class Subscription(Protocol):
    def close(self) -> None:
        ...


@runtime_checkable
class DebuggerController(Protocol):
    def start(self) -> None:
        ...

    def submit(self, command: ControllerCommand) -> Future[CommandResult]:
        ...

    def accept_gateway_notice(self, notice: GatewayNotice) -> None:
        ...

    def accept_deadline(self, expired: DeadlineExpired) -> None:
        ...

    def snapshot(self) -> Future[ControllerSnapshot]:
        ...

    def subscribe(self, callback: Callable[[ControllerEvent], None]) -> Subscription:
        ...

    def close(self) -> Future[CommandResult]:
        ...


@runtime_checkable
class ExecutiveGatewayPort(Protocol):
    def start(self, notice_sink: Callable[[GatewayNotice], None]) -> None:
        ...

    def submit(self, effect: GatewayEffect) -> None:
        ...

    def close(self) -> None:
        ...


def reserve_generation(
    watermarks: GenerationWatermarks,
    active_stamp: GenerationStamp,
    operation_id: str,
    kind: EffectKind,
    existing: Optional[GenerationReservation] = None,
) -> tuple[GenerationWatermarks, GenerationReservation]:
    """Reserve a controller-owned generation without changing ``active_stamp``.

    Passing the same live reservation models an idempotent retry and returns it unchanged.
    A different operation consumes a new number.  The returned OPEN candidate binds its
    capability generation to the same session reservation and starts stream generation zero.
    """

    if not isinstance(watermarks, GenerationWatermarks):
        raise TypeError("watermarks must be GenerationWatermarks")
    if not isinstance(active_stamp, GenerationStamp):
        raise TypeError("active_stamp must be GenerationStamp")
    _require_nonempty(operation_id, "operation_id")
    _require_enum(kind, EffectKind, "kind")
    if kind not in (EffectKind.OPEN_SESSION, EffectKind.SUBSCRIBE_EVENTS):
        raise ValueError("only OPEN_SESSION and SUBSCRIBE_EVENTS reserve generations")
    if watermarks.session < active_stamp.session_generation:
        raise ValueError("session watermark cannot trail the active session generation")
    if watermarks.stream < active_stamp.stream_generation:
        raise ValueError("stream watermark cannot trail the active stream generation")

    if existing is not None:
        if not isinstance(existing, GenerationReservation):
            raise TypeError("existing must be GenerationReservation or None")
        if existing.operation_id == operation_id:
            if existing.kind is not kind or existing.active_parent_stamp != active_stamp:
                raise ValueError("same-operation retry does not match the live reservation")
            consumed = (
                watermarks.session
                if existing.kind is EffectKind.OPEN_SESSION
                else watermarks.stream
            )
            reserved = (
                existing.reserved_stamp.session_generation
                if existing.kind is EffectKind.OPEN_SESSION
                else existing.reserved_stamp.stream_generation
            )
            if consumed < reserved:
                raise ValueError("allocation watermark cannot roll back below a reservation")
            return watermarks, existing

    if kind is EffectKind.OPEN_SESSION:
        next_session = watermarks.session + 1
        reserved_stamp = replace(
            active_stamp,
            session_generation=next_session,
            capability_generation=next_session,
            stream_generation=0,
        )
        next_watermarks = replace(watermarks, session=next_session)
        namespace = _SESSION_NAMESPACE
    else:
        next_stream = watermarks.stream + 1
        reserved_stamp = replace(active_stamp, stream_generation=next_stream)
        next_watermarks = replace(watermarks, stream=next_stream)
        namespace = _STREAM_NAMESPACE

    return next_watermarks, GenerationReservation(
        operation_id=operation_id,
        kind=kind,
        reserved_stamp=reserved_stamp,
        active_parent_stamp=active_stamp,
        namespace=namespace,
    )


def completion_matches_reservation(
    reservation: Optional[GenerationReservation], completion: GatewayCompletion
) -> bool:
    """Return whether a completion is exact pending-operation evidence.

    Status and authority do not affect correlation.  Passing ``None`` represents a retired,
    cancelled, failed, or otherwise absent reservation and always rejects the completion.
    """

    if reservation is not None and not isinstance(reservation, GenerationReservation):
        raise TypeError("reservation must be GenerationReservation or None")
    if not isinstance(completion, GatewayCompletion):
        raise TypeError("completion must be GatewayCompletion")
    return bool(
        reservation is not None
        and completion.operation_id == reservation.operation_id
        and completion.generation == reservation.reserved_stamp
    )


def completion_promotes_reservation(
    reservation: Optional[GenerationReservation], completion: GatewayCompletion
) -> bool:
    """Require exact correlation plus authoritative resource-established success."""

    return bool(
        completion_matches_reservation(reservation, completion)
        and completion.status is CompletionStatus.OK
        and completion.authority is CompletionAuthority.AUTHORITATIVE_RESOURCE_ESTABLISHED
    )


def promote_generation(
    active_stamp: GenerationStamp,
    watermarks: GenerationWatermarks,
    reservation: Optional[GenerationReservation],
    completion: GatewayCompletion,
) -> tuple[GenerationStamp, GenerationWatermarks, bool]:
    """Purely promote one matching reservation, otherwise preserve active continuity.

    The caller owns the pending-operation table and retires a reservation only after exact
    completion correlation or explicit cancellation.  A successful new session starts a new
    independent stream namespace at zero.
    """

    if not isinstance(active_stamp, GenerationStamp):
        raise TypeError("active_stamp must be GenerationStamp")
    if not isinstance(watermarks, GenerationWatermarks):
        raise TypeError("watermarks must be GenerationWatermarks")
    if not completion_promotes_reservation(reservation, completion):
        return active_stamp, watermarks, False
    assert reservation is not None
    if reservation.active_parent_stamp != active_stamp:
        return active_stamp, watermarks, False
    if (
        reservation.kind is EffectKind.OPEN_SESSION
        and watermarks.session < reservation.reserved_stamp.session_generation
    ) or (
        reservation.kind is EffectKind.SUBSCRIBE_EVENTS
        and watermarks.stream < reservation.reserved_stamp.stream_generation
    ):
        raise ValueError("allocation watermark cannot roll back below a reservation")

    next_watermarks = watermarks
    if reservation.kind is EffectKind.OPEN_SESSION:
        next_watermarks = replace(watermarks, stream=0)
    return reservation.reserved_stamp, next_watermarks, True


def generation_is_active(active_stamp: GenerationStamp, candidate: GenerationStamp) -> bool:
    """Fence event/health evidence by exact active stamp, never numeric ordering."""

    if not isinstance(active_stamp, GenerationStamp) or not isinstance(candidate, GenerationStamp):
        raise TypeError("active_stamp and candidate must be GenerationStamp")
    return candidate == active_stamp


__all__ = [
    "CapabilityProfile",
    "CommandResult",
    "CommandStatus",
    "CompletionAuthority",
    "CompletionStatus",
    "ControllerCommand",
    "ControllerEvent",
    "ControllerSnapshot",
    "DeadlineExpired",
    "DebuggerController",
    "EffectKind",
    "EventGap",
    "EventHealth",
    "EvidenceGrade",
    "ExecutiveGatewayPort",
    "GatewayCompletion",
    "GatewayEffect",
    "GatewayEvent",
    "GatewayFailure",
    "GatewayNotice",
    "GenerationReservation",
    "GenerationStamp",
    "GenerationWatermarks",
    "HealthNotice",
    "ReconcileResult",
    "ReconcileStatus",
    "RecoveryStatus",
    "RpcHealth",
    "StopEpoch",
    "Subscription",
    "TargetRunState",
    "completion_matches_reservation",
    "completion_promotes_reservation",
    "generation_is_active",
    "promote_generation",
    "reserve_generation",
]
