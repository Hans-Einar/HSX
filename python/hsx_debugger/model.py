"""Immutable internal state for the serialized debugger controller."""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Mapping

from .contracts import (
    CapabilityProfile,
    ControllerCommand,
    ControllerSnapshot,
    EventHealth,
    EvidenceGrade,
    GatewayEffect,
    GenerationReservation,
    GenerationStamp,
    GenerationWatermarks,
    RecoveryStatus,
    RpcHealth,
    TargetRunState,
)
from .epochs import StopEpochStore


LEGACY_PROFILE_ID = "hsx.python-debug-legacy/1"


@dataclass(frozen=True, slots=True)
class PendingOperation:
    """One accepted operation and any controller-owned generation reservation."""

    command: ControllerCommand
    effect: GatewayEffect
    deadline_id: str
    prior_target_state: TargetRunState
    reservation: GenerationReservation | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.command, ControllerCommand):
            raise TypeError("command must be ControllerCommand")
        if not isinstance(self.effect, GatewayEffect):
            raise TypeError("effect must be GatewayEffect")
        if self.effect.command_id != self.command.command_id:
            raise ValueError("effect command_id must match the accepted command")
        if not isinstance(self.deadline_id, str) or not self.deadline_id.strip():
            raise ValueError("deadline_id must be a non-empty string")
        if not isinstance(self.prior_target_state, TargetRunState):
            raise TypeError("prior_target_state must be TargetRunState")
        if self.reservation is not None:
            if not isinstance(self.reservation, GenerationReservation):
                raise TypeError("reservation must be GenerationReservation or None")
            if self.reservation.operation_id != self.effect.operation_id:
                raise ValueError("reservation operation_id must match the effect")
            if self.reservation.kind is not self.effect.kind:
                raise ValueError("reservation kind must match the effect")
            if self.reservation.reserved_stamp != self.effect.generation:
                raise ValueError("reserved stamp must be the effect stamp")

    @property
    def operation_id(self) -> str:
        return self.effect.operation_id

    @property
    def command_id(self) -> str:
        return self.command.command_id

    @property
    def command_kind(self) -> str:
        return self.command.kind

    @property
    def generation(self) -> GenerationStamp:
        return self.effect.generation


@dataclass(frozen=True, slots=True)
class ControllerModel:
    """Complete immutable controller truth, replaced only by the actor reducer."""

    revision: int
    generation: GenerationStamp
    generation_watermarks: GenerationWatermarks
    rpc_health: RpcHealth
    event_health: EventHealth
    recovery_status: RecoveryStatus
    target_state: TargetRunState
    capability_profile: CapabilityProfile | None = None
    epoch_store: StopEpochStore = field(default_factory=StopEpochStore)
    pending_operations: Mapping[str, PendingOperation] = field(default_factory=dict)
    retired_operation_ids: frozenset[str] = field(default_factory=frozenset)
    retired_deadline_ids: frozenset[str] = field(default_factory=frozenset)
    active_stream_id: str | None = None
    last_event_sequence: int | None = None
    closed: bool = False

    def __post_init__(self) -> None:
        if (
            isinstance(self.revision, bool)
            or not isinstance(self.revision, int)
            or self.revision < 0
        ):
            raise ValueError("revision must be a non-negative integer")
        if not isinstance(self.generation, GenerationStamp):
            raise TypeError("generation must be GenerationStamp")
        if not isinstance(self.generation_watermarks, GenerationWatermarks):
            raise TypeError("generation_watermarks must be GenerationWatermarks")
        if self.generation_watermarks.session < self.generation.session_generation:
            raise ValueError("session watermark cannot trail active session generation")
        if self.generation_watermarks.stream < self.generation.stream_generation:
            raise ValueError("stream watermark cannot trail active stream generation")
        if not isinstance(self.rpc_health, RpcHealth):
            raise TypeError("rpc_health must be RpcHealth")
        if not isinstance(self.event_health, EventHealth):
            raise TypeError("event_health must be EventHealth")
        if not isinstance(self.recovery_status, RecoveryStatus):
            raise TypeError("recovery_status must be RecoveryStatus")
        if not isinstance(self.target_state, TargetRunState):
            raise TypeError("target_state must be TargetRunState")
        if self.capability_profile is not None:
            if not isinstance(self.capability_profile, CapabilityProfile):
                raise TypeError("capability_profile must be CapabilityProfile or None")
            if self.capability_profile.generation != self.generation.capability_generation:
                raise ValueError("capability profile generation must match active generation")
        if not isinstance(self.epoch_store, StopEpochStore):
            raise TypeError("epoch_store must be StopEpochStore")
        if self.epoch_store.active is not None:
            if self.epoch_store.active.generation != self.generation:
                raise ValueError("active epoch generation must match active controller generation")
            if self.target_state is not TargetRunState.STOPPED:
                raise ValueError("an active epoch requires STOPPED target state")
        if self.active_stream_id is not None and (
            not isinstance(self.active_stream_id, str) or not self.active_stream_id.strip()
        ):
            raise ValueError("active_stream_id must be a non-empty string or None")
        if self.last_event_sequence is not None and (
            isinstance(self.last_event_sequence, bool)
            or not isinstance(self.last_event_sequence, int)
            or self.last_event_sequence < 1
        ):
            raise ValueError("last_event_sequence must be a positive integer or None")
        if not isinstance(self.closed, bool):
            raise TypeError("closed must be bool")

        retired = frozenset(self.retired_operation_ids)
        if any(
            not isinstance(operation_id, str) or not operation_id.strip()
            for operation_id in retired
        ):
            raise ValueError("retired operation IDs must be non-empty strings")
        pending = dict(self.pending_operations)
        retired_deadlines = frozenset(self.retired_deadline_ids)
        if any(
            not isinstance(deadline_id, str) or not deadline_id.strip()
            for deadline_id in retired_deadlines
        ):
            raise ValueError("retired deadline IDs must be non-empty strings")
        active_deadlines: set[str] = set()
        for operation_id, operation in pending.items():
            if not isinstance(operation, PendingOperation):
                raise TypeError("pending operation values must be PendingOperation")
            if operation_id != operation.operation_id:
                raise ValueError("pending operation key must match operation_id")
            if operation.deadline_id in active_deadlines:
                raise ValueError("pending deadline IDs must be unique")
            active_deadlines.add(operation.deadline_id)
            reservation = operation.reservation
            if reservation is None:
                if operation.generation != self.generation:
                    raise ValueError("ordinary pending operation must use the active generation")
                continue
            if reservation.active_parent_stamp != self.generation:
                raise ValueError("pending reservation must name the exact active parent")
            consumed = (
                self.generation_watermarks.session
                if reservation.namespace == "session"
                else self.generation_watermarks.stream
            )
            reserved = (
                reservation.reserved_stamp.session_generation
                if reservation.namespace == "session"
                else reservation.reserved_stamp.stream_generation
            )
            if consumed < reserved:
                raise ValueError("allocation watermark cannot trail a pending reservation")
        if retired.intersection(pending):
            raise ValueError("an operation cannot be both pending and retired")
        if retired_deadlines.intersection(active_deadlines):
            raise ValueError("a deadline cannot be both pending and retired")
        if self.closed and pending:
            raise ValueError("closed controller cannot retain pending operations")
        object.__setattr__(self, "pending_operations", MappingProxyType(pending))
        object.__setattr__(self, "retired_operation_ids", retired)
        object.__setattr__(self, "retired_deadline_ids", retired_deadlines)

    def snapshot(self) -> ControllerSnapshot:
        return ControllerSnapshot(
            controller_revision=self.revision,
            generation=self.generation,
            rpc_health=self.rpc_health,
            event_health=self.event_health,
            recovery_status=self.recovery_status,
            target_state=self.target_state,
            capability_profile=self.capability_profile,
            active_epoch=self.epoch_store.active,
            pending_operation_ids=tuple(self.pending_operations),
        )


def initial_legacy_model(
    generation: GenerationStamp | None = None,
    capability_profile: CapabilityProfile | None = None,
    generation_watermarks: GenerationWatermarks | None = None,
) -> ControllerModel:
    """Create a conservative, explicitly degraded controller baseline."""

    if generation is None:
        generation = GenerationStamp(
            executive_instance_id=None,
            session_generation=0,
            target_id=None,
            target_generation=0,
            capability_generation=0,
            stream_generation=0,
            display_pid=None,
            evidence_grade=EvidenceGrade.LEGACY_DEGRADED,
        )
    if capability_profile is None:
        capability_profile = CapabilityProfile(
            profile_id=LEGACY_PROFILE_ID,
            generation=generation.capability_generation,
            capabilities=frozenset(),
            degraded=True,
            diagnostics=("identity continuity is unproven",),
        )
    if generation_watermarks is None:
        generation_watermarks = GenerationWatermarks(
            session=generation.session_generation,
            stream=generation.stream_generation,
        )
    return ControllerModel(
        revision=0,
        generation=generation,
        generation_watermarks=generation_watermarks,
        rpc_health=RpcHealth.CLOSED,
        event_health=EventHealth.DISABLED,
        recovery_status=RecoveryStatus.IDLE,
        target_state=TargetRunState.NONE,
        capability_profile=capability_profile,
    )


__all__ = [
    "ControllerModel",
    "LEGACY_PROFILE_ID",
    "PendingOperation",
    "initial_legacy_model",
]
