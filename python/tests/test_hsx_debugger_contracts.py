"""Contract evidence for the frozen ``dbg.controller-gateway/1.1`` interface."""

from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from pathlib import Path
import sys

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
PYTHON_SRC = REPO_ROOT / "python"
if str(PYTHON_SRC) not in sys.path:
    sys.path.insert(0, str(PYTHON_SRC))

import hsx_debugger
import hsx_debugger.contracts as contracts
from hsx_debugger.contracts import (
    CapabilityProfile,
    CompletionAuthority,
    CompletionStatus,
    EffectKind,
    EventHealth,
    EvidenceGrade,
    GatewayCompletion,
    GatewayEffect,
    GatewayEvent,
    GenerationReservation,
    GenerationStamp,
    GenerationWatermarks,
    HealthNotice,
    RpcHealth,
    completion_matches_reservation,
    completion_promotes_reservation,
    generation_is_active,
    promote_generation,
    reserve_generation,
)


def stamp(*, session: int = 3, stream: int = 4, capability: int = 3) -> GenerationStamp:
    return GenerationStamp(
        executive_instance_id=None,
        session_generation=session,
        target_id=None,
        target_generation=2,
        capability_generation=capability,
        stream_generation=stream,
        display_pid=17,
        evidence_grade=EvidenceGrade.LEGACY_DEGRADED,
    )


def completion(
    reservation: GenerationReservation,
    *,
    operation_id: str | None = None,
    generation: GenerationStamp | None = None,
    status: CompletionStatus = CompletionStatus.OK,
    authority: CompletionAuthority = CompletionAuthority.AUTHORITATIVE_RESOURCE_ESTABLISHED,
) -> GatewayCompletion:
    return GatewayCompletion(
        operation_id=operation_id or reservation.operation_id,
        generation=generation or reservation.reserved_stamp,
        status=status,
        evidence_grade=reservation.reserved_stamp.evidence_grade,
        authority=authority,
    )


# Steering fixture 1.
def test_successful_open_reserves_then_authoritative_matching_success_promotes_once() -> None:
    active = stamp()
    watermarks, reservation = reserve_generation(
        GenerationWatermarks(session=3, stream=4),
        active,
        "open-1",
        EffectKind.OPEN_SESSION,
    )

    assert active.session_generation == 3
    assert reservation.reserved_stamp.session_generation == 4
    assert reservation.reserved_stamp.stream_generation == 0
    assert watermarks == GenerationWatermarks(session=4, stream=4)
    effect = GatewayEffect(
        operation_id=reservation.operation_id,
        command_id="connect-1",
        kind=reservation.kind,
        generation=reservation.reserved_stamp,
        payload={},
        idempotent=True,
    )
    assert effect.generation is reservation.reserved_stamp

    ack_only = completion(reservation, authority=CompletionAuthority.ACK_ONLY)
    assert completion_matches_reservation(reservation, ack_only)
    assert not completion_promotes_reservation(reservation, ack_only)
    assert promote_generation(active, watermarks, reservation, ack_only) == (
        active,
        watermarks,
        False,
    )

    authoritative = completion(reservation)
    promoted, promoted_watermarks, did_promote = promote_generation(
        active, watermarks, reservation, authoritative
    )
    assert did_promote
    assert promoted == reservation.reserved_stamp
    assert promoted_watermarks == GenerationWatermarks(session=4, stream=0)
    assert not generation_is_active(promoted, active)
    assert promote_generation(promoted, promoted_watermarks, reservation, authoritative) == (
        promoted,
        promoted_watermarks,
        False,
    )
    assert not completion_promotes_reservation(None, authoritative)


# Steering fixture 2.
def test_failed_open_burns_watermark_without_promoting_or_retiring_old_active() -> None:
    active = stamp()
    watermarks, reservation = reserve_generation(
        GenerationWatermarks(session=3, stream=4), active, "open-failed", EffectKind.OPEN_SESSION
    )
    failed = completion(reservation, status=CompletionStatus.TRANSPORT_ERROR)

    assert completion_matches_reservation(reservation, failed)
    assert promote_generation(active, watermarks, reservation, failed) == (
        active,
        watermarks,
        False,
    )
    assert generation_is_active(active, active)
    assert watermarks.session == 4


# Steering fixture 3.
def test_failed_subscribe_burns_only_stream_watermark_and_leaves_old_stream_active() -> None:
    active = stamp()
    watermarks, reservation = reserve_generation(
        GenerationWatermarks(session=3, stream=4),
        active,
        "subscribe-failed",
        EffectKind.SUBSCRIBE_EVENTS,
    )
    failed = completion(reservation, status=CompletionStatus.REJECTED)

    assert watermarks == GenerationWatermarks(session=3, stream=5)
    assert promote_generation(active, watermarks, reservation, failed) == (
        active,
        watermarks,
        False,
    )
    assert generation_is_active(active, active)


# Steering fixture 4.
def test_same_operation_idempotent_retry_reuses_exact_reservation_and_stamp() -> None:
    active = stamp()
    watermarks, reservation = reserve_generation(
        GenerationWatermarks(session=3, stream=4), active, "retry-1", EffectKind.SUBSCRIBE_EVENTS
    )
    retry_watermarks, retry = reserve_generation(
        watermarks, active, "retry-1", EffectKind.SUBSCRIBE_EVENTS, existing=reservation
    )

    assert retry_watermarks is watermarks
    assert retry is reservation
    assert retry.reserved_stamp == reservation.reserved_stamp


# Steering fixture 5.
def test_new_operation_after_failure_advances_burned_generation() -> None:
    active = stamp()
    watermarks, failed_reservation = reserve_generation(
        GenerationWatermarks(session=3, stream=4),
        active,
        "subscribe-1",
        EffectKind.SUBSCRIBE_EVENTS,
    )
    assert completion_matches_reservation(
        failed_reservation,
        completion(failed_reservation, status=CompletionStatus.CANCELLED),
    )

    next_watermarks, next_reservation = reserve_generation(
        watermarks,
        active,
        "subscribe-2",
        EffectKind.SUBSCRIBE_EVENTS,
        existing=failed_reservation,
    )
    assert failed_reservation.reserved_stamp.stream_generation == 5
    assert next_reservation.reserved_stamp.stream_generation == 6
    assert next_watermarks == GenerationWatermarks(session=3, stream=6)


# Steering fixture 6.
def test_old_active_stream_event_remains_legal_while_replacement_is_pending() -> None:
    active = stamp()
    _, reservation = reserve_generation(
        GenerationWatermarks(session=3, stream=4),
        active,
        "subscribe-pending",
        EffectKind.SUBSCRIBE_EVENTS,
    )
    old_event = GatewayEvent(
        generation=active,
        stream_id="old-stream",
        sequence=8,
        category="task_state",
        payload={"state": "stopped"},
        evidence_grade=EvidenceGrade.LEGACY_DEGRADED,
    )
    premature_new_event = replace(
        old_event,
        generation=reservation.reserved_stamp,
        stream_id="new-stream",
        sequence=1,
    )

    assert generation_is_active(active, old_event.generation)
    assert not generation_is_active(active, premature_new_event.generation)


# Steering fixture 7.
def test_stream_promotion_rejects_old_events_and_accepts_new_exact_stamp() -> None:
    old_active = stamp()
    watermarks, reservation = reserve_generation(
        GenerationWatermarks(session=3, stream=4),
        old_active,
        "subscribe-ok",
        EffectKind.SUBSCRIBE_EVENTS,
    )
    new_active, _, promoted = promote_generation(
        old_active, watermarks, reservation, completion(reservation)
    )

    assert promoted
    assert not generation_is_active(new_active, old_active)
    assert generation_is_active(new_active, reservation.reserved_stamp)


# Steering fixture 8.
def test_wrong_operation_stamp_retired_and_numeric_higher_completions_are_rejected() -> None:
    active = stamp()
    watermarks, reservation = reserve_generation(
        GenerationWatermarks(session=3, stream=4), active, "open-right", EffectKind.OPEN_SESSION
    )
    wrong_operation = completion(reservation, operation_id="open-wrong")
    wrong_stamp = completion(
        reservation,
        generation=replace(reservation.reserved_stamp, target_generation=99),
    )
    numerically_higher = completion(
        reservation,
        generation=replace(
            reservation.reserved_stamp,
            session_generation=reservation.reserved_stamp.session_generation + 100,
        ),
    )
    exact_but_retired = completion(reservation)

    for rejected in (wrong_operation, wrong_stamp, numerically_higher):
        assert not completion_matches_reservation(reservation, rejected)
        assert promote_generation(active, watermarks, reservation, rejected) == (
            active,
            watermarks,
            False,
        )
    assert not completion_matches_reservation(None, exact_but_retired)
    assert promote_generation(active, watermarks, None, exact_but_retired) == (
        active,
        watermarks,
        False,
    )


# Steering fixture 9.
def test_session_stream_namespaces_and_subscribe_parent_fence_are_independent() -> None:
    active = stamp(session=7, stream=11, capability=7)
    initial = GenerationWatermarks(session=7, stream=11)
    stream_watermarks, stream_reservation = reserve_generation(
        initial, active, "subscribe-independent", EffectKind.SUBSCRIBE_EVENTS
    )
    session_watermarks, session_reservation = reserve_generation(
        initial, active, "open-independent", EffectKind.OPEN_SESSION
    )

    assert stream_watermarks == GenerationWatermarks(session=7, stream=12)
    assert session_watermarks == GenerationWatermarks(session=8, stream=11)
    assert stream_reservation.reserved_stamp.session_generation == 7
    assert session_reservation.reserved_stamp.session_generation == 8
    assert session_reservation.reserved_stamp.stream_generation == 0

    wrong_session_parent = replace(active, session_generation=6)
    with pytest.raises(ValueError, match="exact active session parent"):
        GenerationReservation(
            operation_id="bad-parent",
            kind=EffectKind.SUBSCRIBE_EVENTS,
            reserved_stamp=stream_reservation.reserved_stamp,
            active_parent_stamp=wrong_session_parent,
            namespace="stream",
        )


def test_nested_payloads_are_defensively_copied_and_immutable() -> None:
    source = {"nested": [{"numbers": [1, 2]}, {"labels": {"a", "b"}}]}
    effect = GatewayEffect(
        operation_id="effect-1",
        command_id="command-1",
        kind=EffectKind.REQUEST,
        generation=stamp(),
        payload=source,
        idempotent=False,
    )
    source["nested"][0]["numbers"].append(3)

    assert effect.payload["nested"][0]["numbers"] == (1, 2)
    assert effect.payload["nested"][1]["labels"] == frozenset({"a", "b"})
    with pytest.raises(TypeError):
        effect.payload["new"] = "forbidden"  # type: ignore[index]
    with pytest.raises(FrozenInstanceError):
        effect.idempotent = True  # type: ignore[misc]


@pytest.mark.parametrize(
    ("factory", "message"),
    [
        (
            lambda: GenerationStamp(None, -1, None, 0, 0, 0, None, EvidenceGrade.LEGACY_DEGRADED),
            "session_generation",
        ),
        (
            lambda: GenerationWatermarks(session=0, stream=-1),
            "stream",
        ),
        (
            lambda: GatewayEffect(
                operation_id="",
                command_id="command",
                kind=EffectKind.REQUEST,
                generation=stamp(),
                payload={},
                idempotent=False,
            ),
            "operation_id",
        ),
        (
            lambda: reserve_generation(
                GenerationWatermarks(session=3, stream=4),
                active_stamp=stamp(),
                operation_id="x",
                kind=EffectKind.REQUEST,
            ),
            "OPEN_SESSION",
        ),
    ],
)
def test_invalid_ids_generations_and_reservation_kinds_are_rejected(factory, message: str) -> None:
    with pytest.raises((TypeError, ValueError), match=message):
        factory()


def test_legacy_profile_cannot_claim_portable_identity_resume_or_resource_guarantees() -> None:
    forbidden = {
        "portable.identity",
        "portable.event_resume",
        "portable.resource_ownership",
        "portable.ack_after_apply",
    }
    profile = CapabilityProfile(
        profile_id="hsx.python-debug-legacy/1",
        generation=3,
        capabilities={"hsx.legacy-event-stream/1", "hsx.legacy-debug-resources/1"},
        degraded=True,
        diagnostics=["portable continuity is unavailable"],
    )

    assert profile.degraded
    assert profile.capabilities.isdisjoint(forbidden)
    assert profile.diagnostics == ("portable continuity is unavailable",)
    with pytest.raises(ValueError, match="only legacy capabilities"):
        CapabilityProfile(
            profile_id="hsx.python-debug-legacy/1",
            generation=3,
            capabilities={"hsx.event-stream.resume/1"},
            degraded=True,
        )


def test_gateway_completion_defaults_to_ack_only_and_health_axes_are_independent() -> None:
    active = stamp()
    ack = GatewayCompletion(
        operation_id="request-1",
        generation=active,
        status=CompletionStatus.OK,
        evidence_grade=EvidenceGrade.LEGACY_DEGRADED,
    )
    rpc_lost = HealthNotice(
        generation=active,
        rpc_health=RpcHealth.LOST,
        event_health=EventHealth.HEALTHY,
        reason="rpc eof",
    )
    event_lost = replace(
        rpc_lost,
        rpc_health=RpcHealth.HEALTHY,
        event_health=EventHealth.LOST,
        reason="event eof",
    )

    assert ack.authority is CompletionAuthority.ACK_ONLY
    assert rpc_lost.event_health is EventHealth.HEALTHY
    assert event_lost.rpc_health is RpcHealth.HEALTHY


def test_package_and_contract_module_export_identical_dto_objects() -> None:
    names = (
        "GenerationStamp",
        "GatewayEffect",
        "GatewayCompletion",
        "CompletionAuthority",
        "GenerationWatermarks",
        "GenerationReservation",
    )
    for name in names:
        assert getattr(hsx_debugger, name) is getattr(contracts, name)
