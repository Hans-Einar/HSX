"""Conservative ``hsx.python-debug-legacy/1`` Executive gateway adapter.

The adapter wraps the unchanged :mod:`executive_session` implementation side by side.  It
exposes only evidence the legacy protocol actually provides: no portable Executive/target
identity, event resume, ACK-after-controller-apply, or durable resource ownership is claimed.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
import json
import socket
import threading
from typing import Any, Iterable, Mapping

try:  # Support both repository-root and ``python/`` import layouts.
    from python.executive_session import (
        ConnectionLostError,
        ExecutiveSession,
        ExecutiveSessionError,
        ProtocolVersionError,
    )
except ImportError:  # pragma: no cover - exercised by the installed/python-path layout
    from executive_session import (  # type: ignore[no-redef]
        ConnectionLostError,
        ExecutiveSession,
        ExecutiveSessionError,
        ProtocolVersionError,
    )

from .contracts import (
    CapabilityProfile,
    CompletionAuthority,
    CompletionStatus,
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
    HealthNotice,
    ReconcileResult,
    ReconcileStatus,
    RpcHealth,
)
from .gateway import (
    EffectResult,
    GatewayEffectError,
    NoticePublisher,
    WorkerThreadExecutiveGateway,
)
from .health import GatewayHealthTracker


LEGACY_PROFILE_ID = "hsx.python-debug-legacy/1"
LEGACY_EVENT_CAPABILITY = "hsx.legacy-event-stream/1"
LEGACY_RESOURCE_CAPABILITY = "hsx.legacy-debug-resources/1"

# Negative fixtures: none may appear in the legacy capability profile.
PORTABLE_IDENTITY_CAPABILITY = "hsx.debug.identity/1"
PORTABLE_ACK_AFTER_APPLY_CAPABILITY = "hsx.debug.event-ack-after-apply/1"
PORTABLE_EVENT_RESUME_CAPABILITY = "hsx.debug.event-resume/1"
PORTABLE_RESOURCE_CAPABILITY = "hsx.debug.resource-revision/1"

_RESOURCE_EFFECTS = (EffectKind.OPEN_SESSION, EffectKind.SUBSCRIBE_EVENTS)
_CACHE_MISS = object()
_UNOBSERVED_EVENT_TRANSPORT = object()


def initial_legacy_generation(*, display_pid: int | None = None) -> GenerationStamp:
    """Return the unconnected debugger-local stamp for the legacy profile."""

    return GenerationStamp(
        executive_instance_id=None,
        session_generation=0,
        target_id=None,
        target_generation=0,
        capability_generation=0,
        stream_generation=0,
        display_pid=display_pid,
        evidence_grade=EvidenceGrade.LEGACY_DEGRADED,
    )


def _validate_legacy_generation(generation: GenerationStamp) -> None:
    if not isinstance(generation, GenerationStamp):
        raise TypeError("generation must be GenerationStamp")
    if generation.evidence_grade is not EvidenceGrade.LEGACY_DEGRADED:
        raise ValueError("legacy gateway requires LEGACY_DEGRADED evidence")
    if generation.executive_instance_id is not None or generation.target_id is not None:
        raise ValueError("legacy gateway cannot accept portable Executive/target identity")


def _thaw(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _thaw(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw(item) for item in value]
    if isinstance(value, frozenset):
        return [_thaw(item) for item in sorted(value, key=str)]
    return value


def _profile_payload(profile: CapabilityProfile) -> dict[str, Any]:
    return {
        "profile_id": profile.profile_id,
        "generation": profile.generation,
        "capabilities": sorted(profile.capabilities),
        "degraded": profile.degraded,
        "diagnostics": list(profile.diagnostics),
    }


@dataclass(slots=True)
class _LegacyEventState:
    generation: GenerationStamp
    stream_id: str
    publish: NoticePublisher
    last_sequence: int | None = None
    established: bool = False
    stop_requested: bool = False
    buffered: list[GatewayNotice] = field(default_factory=list)
    transport_stream: Any = None


@dataclass(frozen=True, slots=True)
class _LegacyTransportSnapshot:
    session_id: Any
    active_event_state: _LegacyEventState | None
    session_event_stream: Any


class LegacyExecutiveAdapter:
    """Translate frozen effects to one unchanged ``ExecutiveSession`` instance."""

    def __init__(self, session: ExecutiveSession, health: GatewayHealthTracker) -> None:
        if not isinstance(health, GatewayHealthTracker):
            raise TypeError("health must be GatewayHealthTracker")
        _validate_legacy_generation(health.generation)
        self._session = session
        self.health = health
        self._event_lock = threading.Lock()
        self._close_lock = threading.Lock()
        self._closed = False
        self._active_event_state: _LegacyEventState | None = None
        self._pending_event_state: _LegacyEventState | None = None
        self._seen_effects: dict[str, GatewayEffect] = {}
        self._completed_effects: dict[str, tuple[GatewayNotice, ...]] = {}
        self._session_watermark = health.generation.session_generation
        self._stream_watermark = health.generation.stream_generation

    def __call__(self, effect: GatewayEffect, publish: NoticePublisher) -> EffectResult:
        if not isinstance(effect, GatewayEffect):
            raise TypeError("effect must be GatewayEffect")
        if not callable(publish):
            raise TypeError("publish must be callable")
        if not self._is_legacy_effect(effect):
            return self._unsupported_identity(effect)

        validation = self._validate_and_record_effect(effect)
        if isinstance(validation, GatewayCompletion):
            return validation
        if validation is not _CACHE_MISS:
            return validation

        transport_before = self._transport_snapshot()
        try:
            result = self._dispatch(effect, publish)
        except ConnectionLostError as exc:
            self._invalidate_event_continuity(
                rpc_health=RpcHealth.LOST,
                reason="legacy RPC transport lost",
            )
            raise GatewayEffectError(
                "legacy_rpc_transport_lost",
                "legacy Executive RPC transport was lost",
                status=CompletionStatus.TRANSPORT_ERROR,
                retryable=effect.idempotent,
                cause=exc,
            ) from exc
        except ProtocolVersionError as exc:
            if self._transport_disruption_reasons(transport_before):
                self._invalidate_event_continuity(
                    rpc_health=RpcHealth.DEGRADED,
                    reason="legacy protocol failure followed hidden transport replacement",
                )
            raise GatewayEffectError(
                "legacy_protocol_incompatible",
                "legacy Executive protocol is incompatible",
                status=CompletionStatus.PROTOCOL_ERROR,
                cause=exc,
            ) from exc
        except (ExecutiveSessionError, json.JSONDecodeError, TypeError, ValueError) as exc:
            if self._transport_disruption_reasons(transport_before):
                self._invalidate_event_continuity(
                    rpc_health=RpcHealth.DEGRADED,
                    reason="legacy protocol failure followed hidden transport replacement",
                )
            raise GatewayEffectError(
                "legacy_protocol_error",
                "legacy Executive request or response was malformed",
                status=CompletionStatus.PROTOCOL_ERROR,
                cause=exc,
            ) from exc
        except OSError as exc:
            self._invalidate_event_continuity(
                rpc_health=RpcHealth.LOST,
                reason="legacy RPC transport lost",
            )
            raise GatewayEffectError(
                "legacy_rpc_transport_lost",
                "legacy Executive RPC transport was lost",
                status=CompletionStatus.TRANSPORT_ERROR,
                retryable=effect.idempotent,
                cause=exc,
            ) from exc

        notices = self._normalise_result(result)
        self._completed_effects[effect.operation_id] = notices
        return notices

    def _dispatch(self, effect: GatewayEffect, publish: NoticePublisher) -> EffectResult:
        if effect.kind is EffectKind.OPEN_SESSION:
            return self._open_session(effect)
        if effect.kind is EffectKind.CLOSE_SESSION:
            return self._close_session(effect)
        if effect.kind is EffectKind.REQUEST:
            return self._request(effect)
        if effect.kind is EffectKind.SUBSCRIBE_EVENTS:
            return self._subscribe(effect, publish)
        if effect.kind is EffectKind.UNSUBSCRIBE_EVENTS:
            return self._unsubscribe(effect)
        if effect.kind is EffectKind.RECONCILE:
            return self._reconcile(effect)
        raise GatewayEffectError(
            "unsupported_effect",
            f"unsupported gateway effect {effect.kind.value}",
            status=CompletionStatus.UNSUPPORTED,
        )

    def close(self) -> None:
        with self._close_lock:
            if self._closed:
                return
            self._closed = True
        self._mark_event_states_stopped()
        self._session.close()
        self.health.transition(
            rpc_health=RpcHealth.CLOSED,
            event_health=EventHealth.DISABLED,
            reason="legacy gateway closed",
        )

    def capability_profile(
        self,
        generation: GenerationStamp | None = None,
    ) -> CapabilityProfile:
        stamp = generation or self.health.generation
        _validate_legacy_generation(stamp)
        features = tuple(sorted(str(item) for item in getattr(self._session, "negotiated_features", [])))
        capabilities: set[str] = set()
        if "events" in features:
            capabilities.add(LEGACY_EVENT_CAPABILITY)
        if "watch" in features:
            capabilities.add(LEGACY_RESOURCE_CAPABILITY)
        feature_text = ",".join(features) if features else "none"
        return CapabilityProfile(
            profile_id=LEGACY_PROFILE_ID,
            generation=stamp.capability_generation,
            capabilities=frozenset(capabilities),
            degraded=True,
            diagnostics=(
                f"negotiated_legacy_features={feature_text}",
                "portable_identity=false",
                "ack_after_controller_apply=false",
                "event_resume=false",
                "resource_identity_or_revision=false",
            ),
        )

    def _validate_and_record_effect(
        self,
        effect: GatewayEffect,
    ) -> object | GatewayCompletion | tuple[GatewayNotice, ...]:
        previous = self._seen_effects.get(effect.operation_id)
        if previous is not None:
            if previous != effect:
                return self._failure_completion(
                    effect,
                    CompletionStatus.PROTOCOL_ERROR,
                    "operation_identity_mismatch",
                    "operation ID was reused with a different effect or generation stamp",
                )
            if not effect.idempotent:
                return self._failure_completion(
                    effect,
                    CompletionStatus.REJECTED,
                    "non_idempotent_retry_rejected",
                    "a non-idempotent legacy effect cannot be retried",
                )
            cached = self._completed_effects.get(effect.operation_id)
            if cached is None:
                if not self._retry_matches_active(effect):
                    return self._stale_generation(
                        effect,
                        "retry no longer matches the active parent generation",
                    )
                return _CACHE_MISS
            if effect.kind in _RESOURCE_EFFECTS:
                established = any(
                    isinstance(notice, GatewayCompletion)
                    and notice.status is CompletionStatus.OK
                    and notice.authority
                    is CompletionAuthority.AUTHORITATIVE_RESOURCE_ESTABLISHED
                    for notice in cached
                )
                if established and not self.health.matches(effect.generation):
                    return self._stale_generation(
                        effect,
                        "established operation was superseded by another generation",
                    )
                # Pending-phase old-continuity notices are historical by the time a
                # successful exact retry is replayed.  Replay only the candidate-stamped
                # completion/health evidence and never relabel or re-emit the old stamp.
                return tuple(notice for notice in cached if notice.generation == effect.generation)
            if not self.health.matches(effect.generation):
                return self._stale_generation(
                    effect,
                    "completed operation belongs to a superseded generation",
                )
            return cached

        active = self.health.generation
        candidate = effect.generation
        if effect.kind is EffectKind.OPEN_SESSION:
            expected = replace(
                active,
                session_generation=candidate.session_generation,
                capability_generation=candidate.session_generation,
                stream_generation=0,
            )
            if candidate != expected or candidate.session_generation <= self._session_watermark:
                return self._stale_generation(effect, "invalid controller-reserved session stamp")
            self._session_watermark = candidate.session_generation
        elif effect.kind is EffectKind.SUBSCRIBE_EVENTS:
            expected = replace(active, stream_generation=candidate.stream_generation)
            if candidate != expected or candidate.stream_generation <= self._stream_watermark:
                return self._stale_generation(effect, "invalid controller-reserved stream stamp")
            self._stream_watermark = candidate.stream_generation
        elif candidate != active:
            return self._stale_generation(effect, "effect does not match the active generation")

        self._seen_effects[effect.operation_id] = effect
        return _CACHE_MISS

    def _retry_matches_active(self, effect: GatewayEffect) -> bool:
        active = self.health.generation
        candidate = effect.generation
        if effect.kind is EffectKind.OPEN_SESSION:
            expected = replace(
                active,
                session_generation=candidate.session_generation,
                capability_generation=candidate.session_generation,
                stream_generation=0,
            )
            return candidate == expected and candidate.session_generation > active.session_generation
        if effect.kind is EffectKind.SUBSCRIBE_EVENTS:
            expected = replace(active, stream_generation=candidate.stream_generation)
            return candidate == expected and candidate.stream_generation > active.stream_generation
        return candidate == active

    def _open_session(self, effect: GatewayEffect) -> tuple[GatewayNotice, ...]:
        before = self.health.snapshot()
        transport_before = self._transport_snapshot()
        connecting_state = (
            RpcHealth.CONNECTING
            if before.rpc_health in (RpcHealth.CLOSED, RpcHealth.LOST)
            else before.rpc_health
        )
        connecting = self.health.transition(
            rpc_health=connecting_state,
            reason="opening controller-reserved legacy Executive session",
        )

        # Reconfiguring an already-open ExecutiveSession force-closes its current session and
        # event stream.  Preserve legal old continuity while replacement OPEN is pending by
        # applying configuration only before the first physical session is opened.
        if getattr(self._session, "session_id", None) is None:
            configure = getattr(self._session, "configure_session", None)
            if callable(configure):
                kwargs: dict[str, Any] = {}
                if "pid_lock" in effect.payload:
                    kwargs["pid_lock"] = _thaw(effect.payload["pid_lock"])
                if "heartbeat_s" in effect.payload:
                    kwargs["heartbeat_s"] = _thaw(effect.payload["heartbeat_s"])
                if kwargs:
                    configure(**kwargs)

        request = self._request_payload(effect.payload, default={"cmd": "ps"})
        response = self._session.request(request, use_session=True, retry=effect.idempotent)
        completion = self._response_completion(
            effect,
            response,
            response={
                "legacy_response": _thaw(response),
                "capability_profile": _profile_payload(
                    self.capability_profile(effect.generation)
                ),
            },
            authoritative_resource=True,
        )
        disruption_reasons = self._transport_disruption_reasons(transport_before)
        if completion.status is not CompletionStatus.OK:
            if disruption_reasons:
                failed_health = self._invalidate_event_continuity(
                    rpc_health=RpcHealth.DEGRADED,
                    reason=(
                        "legacy session OPEN failed after hidden transport replacement: "
                        f"{'; '.join(disruption_reasons)}"
                    ),
                )
                # The request has already disproved the pre-call HEALTHY snapshot.  Do not
                # emit that stale connecting notice after the wrapped session changed.
                return failed_health, completion
            else:
                failed_health = self.health.transition(
                    rpc_health=before.rpc_health,
                    event_health=before.event_health,
                    reason="legacy session OPEN failed; prior continuity retained",
                )
            return connecting, completion, failed_health

        lost_continuity: tuple[HealthNotice, ...] = ()
        if disruption_reasons:
            lost_continuity = (
                self._invalidate_event_continuity(
                    rpc_health=RpcHealth.DEGRADED,
                    reason=(
                        "legacy session reopened behind successful OPEN: "
                        f"{'; '.join(disruption_reasons)}"
                    ),
                ),
            )
        else:
            self._stop_active_event_transport()
        healthy = self.health.establish(
            effect.generation,
            rpc_health=RpcHealth.HEALTHY,
            event_health=EventHealth.DISABLED,
            reason="legacy Executive session established; portable continuity unavailable",
        )
        self._stream_watermark = 0
        # Completion deliberately precedes every notice stamped with the reserved generation.
        if lost_continuity:
            # As above, the pre-call connecting snapshot must not be delivered as current
            # health after hidden replacement has been observed.
            return (*lost_continuity, completion, healthy)
        return connecting, completion, healthy

    def _close_session(self, effect: GatewayEffect) -> tuple[GatewayNotice, ...]:
        self._mark_event_states_stopped()
        self._session.close()
        completion = GatewayCompletion(
            operation_id=effect.operation_id,
            generation=effect.generation,
            status=CompletionStatus.OK,
            response={"closed": True},
            evidence_grade=effect.generation.evidence_grade,
        )
        notice = self.health.transition(
            rpc_health=RpcHealth.CLOSED,
            event_health=EventHealth.DISABLED,
            reason="legacy Executive session closed",
        )
        return completion, notice

    def _request(self, effect: GatewayEffect) -> tuple[GatewayNotice, ...]:
        request = self._request_payload(effect.payload)
        transport_before = self._transport_snapshot()
        response = self._session.request(request, use_session=True, retry=effect.idempotent)
        disruption_reasons = self._transport_disruption_reasons(transport_before)
        if disruption_reasons:
            health_notice = self._invalidate_event_continuity(
                rpc_health=RpcHealth.DEGRADED,
                reason=(
                    "legacy session/stream changed during RPC: "
                    f"{'; '.join(disruption_reasons)}"
                ),
            )
        else:
            health_notice = self.health.transition(
                rpc_health=RpcHealth.HEALTHY,
                reason="legacy Executive RPC completed",
            )
        completion = self._response_completion(effect, response)
        return health_notice, completion

    def _subscribe(
        self,
        effect: GatewayEffect,
        publish: NoticePublisher,
    ) -> tuple[GatewayNotice, ...]:
        filters = effect.payload.get("filters", {})
        if not isinstance(filters, Mapping):
            raise ValueError("subscribe filters must be a mapping")
        ack_interval = effect.payload.get("ack_interval", 1)
        if isinstance(ack_interval, bool) or not isinstance(ack_interval, int) or ack_interval < 1:
            raise ValueError("ack_interval must be a positive integer")

        state = _LegacyEventState(
            generation=effect.generation,
            stream_id=(
                f"legacy-stream-{effect.generation.session_generation}-"
                f"{effect.generation.stream_generation}"
            ),
            publish=publish,
        )
        session_id_before = getattr(self._session, "session_id", None)
        with self._event_lock:
            self._pending_event_state = state
        try:
            started = self._start_observed_event_stream(
                state=state,
                filters=_thaw(filters),
                ack_interval=ack_interval,
            )
        except Exception:
            with self._event_lock:
                state.stop_requested = True
                if self._pending_event_state is state:
                    self._pending_event_state = None
            raise
        session_id_after = getattr(self._session, "session_id", None)
        if session_id_after != session_id_before:
            lost = self._invalidate_event_continuity(
                rpc_health=RpcHealth.DEGRADED,
                reason="legacy session changed while establishing event subscription",
            )
            return (
                lost,
                self._failure_completion(
                    effect,
                    CompletionStatus.STALE,
                    "legacy_session_changed_during_subscribe",
                    "event subscription was established against unproven replacement session",
                ),
            )
        if not started:
            with self._event_lock:
                state.stop_requested = True
                if self._pending_event_state is state:
                    self._pending_event_state = None
            return (
                self._failure_completion(
                    effect,
                    CompletionStatus.UNSUPPORTED,
                    "legacy_events_unavailable",
                    "legacy Executive did not establish a new observable event stream",
                ),
            )

        completion = GatewayCompletion(
            operation_id=effect.operation_id,
            generation=effect.generation,
            status=CompletionStatus.OK,
            response={"stream_id": state.stream_id, "portable_resume": False},
            evidence_grade=effect.generation.evidence_grade,
            authority=CompletionAuthority.AUTHORITATIVE_RESOURCE_ESTABLISHED,
        )
        with self._event_lock:
            old_state = self._active_event_state
            if old_state is not None and old_state is not state:
                old_state.stop_requested = True
            buffered_health = [
                notice.event_health
                for notice in state.buffered
                if isinstance(notice, HealthNotice)
            ]
            established_event_health = (
                buffered_health[-1] if buffered_health else EventHealth.HEALTHY
            )
            healthy = self.health.establish(
                effect.generation,
                event_health=established_event_health,
                reason=(
                    "legacy event stream established with buffered degradation"
                    if buffered_health
                    else "legacy event stream established without portable resume/ACK guarantee"
                ),
            )
            state.established = True
            buffered = tuple(state.buffered)
            state.buffered.clear()
            self._active_event_state = state
            if self._pending_event_state is state:
                self._pending_event_state = None
        if old_state is not None and old_state is not state:
            self._stop_event_state_transport(old_state)
        # The worker delivers this tuple in order before processing callback-enqueued notices.
        return (completion, healthy, *buffered)

    def _unsubscribe(self, effect: GatewayEffect) -> tuple[GatewayNotice, ...]:
        self._mark_event_states_stopped()
        self._session.stop_event_stream()
        completion = GatewayCompletion(
            operation_id=effect.operation_id,
            generation=effect.generation,
            status=CompletionStatus.OK,
            response={"unsubscribed": True},
            evidence_grade=effect.generation.evidence_grade,
        )
        notice = self.health.transition(
            event_health=EventHealth.DISABLED,
            reason="legacy event stream closed",
        )
        return completion, notice

    def _reconcile(self, effect: GatewayEffect) -> tuple[GatewayNotice, ...]:
        request = self._request_payload(effect.payload, default={"cmd": "ps"})
        transport_before = self._transport_snapshot()
        try:
            response = self._session.request(request, use_session=True, retry=effect.idempotent)
        except ProtocolVersionError as exc:
            notices: tuple[GatewayNotice, ...] = ()
            disruption_reasons = self._transport_disruption_reasons(transport_before)
            if disruption_reasons:
                notices = (
                    self._invalidate_event_continuity(
                        rpc_health=RpcHealth.DEGRADED,
                        reason=(
                            "legacy reconciliation encountered hidden transport replacement: "
                            f"{'; '.join(disruption_reasons)}"
                        ),
                    ),
                )
            return (
                *notices,
                ReconcileResult(
                    generation=effect.generation,
                    status=ReconcileStatus.INCOMPATIBLE,
                    diagnostics=(
                        "code=legacy_protocol_incompatible",
                        f"cause={type(exc).__name__}",
                    ),
                    evidence_grade=effect.generation.evidence_grade,
                ),
            )
        except (ConnectionLostError, ExecutiveSessionError, OSError, json.JSONDecodeError) as exc:
            notice = self._invalidate_event_continuity(
                rpc_health=RpcHealth.LOST,
                reason=f"legacy reconciliation failed: {type(exc).__name__}",
            )
            result = ReconcileResult(
                generation=effect.generation,
                status=ReconcileStatus.EXHAUSTED,
                diagnostics=(
                    "code=legacy_reconcile_failed",
                    f"cause={type(exc).__name__}",
                ),
                evidence_grade=effect.generation.evidence_grade,
            )
            return notice, result

        if not isinstance(response, Mapping):
            raise ValueError("legacy reconciliation response must be an object")

        disruption_reasons = self._transport_disruption_reasons(transport_before)
        if disruption_reasons:
            notice = self._invalidate_event_continuity(
                rpc_health=RpcHealth.DEGRADED,
                reason=(
                    "legacy reconciliation reopened transport but continuity remains unproven: "
                    f"{'; '.join(disruption_reasons)}"
                ),
            )
        else:
            notice = self.health.transition(
                rpc_health=RpcHealth.HEALTHY,
                reason="legacy snapshot received; target continuity remains unproven",
            )
        result = ReconcileResult(
            generation=effect.generation,
            status=ReconcileStatus.LEGACY_UNPROVEN,
            baseline={"legacy_response": _thaw(response)},
            diagnostics=(
                "portable_target_identity=false",
                "portable_ownership_evidence=false",
                "portable_event_resume=false",
            ),
            evidence_grade=effect.generation.evidence_grade,
        )
        return notice, result

    def _transport_snapshot(self) -> _LegacyTransportSnapshot:
        with self._event_lock:
            active_event_state = self._active_event_state
        return _LegacyTransportSnapshot(
            session_id=getattr(self._session, "session_id", None),
            active_event_state=active_event_state,
            session_event_stream=getattr(
                self._session,
                "_event_stream",
                _UNOBSERVED_EVENT_TRANSPORT,
            ),
        )

    def _transport_disruption_reasons(
        self,
        before: _LegacyTransportSnapshot,
    ) -> tuple[str, ...]:
        reasons: list[str] = []
        session_after = getattr(self._session, "session_id", None)
        if before.session_id is not None and session_after != before.session_id:
            reasons.append("wrapped session_id changed")

        state = before.active_event_state
        if state is None:
            return tuple(reasons)

        session_stream_before = before.session_event_stream
        if session_stream_before is not _UNOBSERVED_EVENT_TRANSPORT:
            session_stream_after = getattr(self._session, "_event_stream", None)
            if session_stream_after is not session_stream_before:
                reasons.append("wrapped event transport stopped or was replaced")

        transport = state.transport_stream
        stop_event = getattr(transport, "stop_event", None)
        if (
            stop_event is not None
            and callable(getattr(stop_event, "is_set", None))
            and stop_event.is_set()
            and "wrapped event transport stopped or was replaced" not in reasons
        ):
            reasons.append("wrapped event transport stopped")
        return tuple(reasons)

    def _invalidate_event_continuity(
        self,
        *,
        rpc_health: RpcHealth,
        reason: str,
    ) -> HealthNotice:
        with self._event_lock:
            had_event_state = (
                self._active_event_state is not None
                or self._pending_event_state is not None
            )
        previous = self.health.snapshot()
        self._mark_event_states_stopped()
        cleanup_error: BaseException | None = None
        try:
            self._session.stop_event_stream()
        except Exception as exc:  # cleanup failure is retained in the typed diagnostic
            cleanup_error = exc
        event_was_enabled = previous.event_health is not EventHealth.DISABLED
        event_health = (
            EventHealth.LOST
            if had_event_state or event_was_enabled
            else EventHealth.DISABLED
        )
        detail = f"{reason}; reconciliation required"
        if event_health is EventHealth.LOST:
            detail += "; event continuity lost"
        if cleanup_error is not None:
            detail += f"; event cleanup failed: {type(cleanup_error).__name__}"
        return self.health.transition(
            rpc_health=rpc_health,
            event_health=event_health,
            reason=detail,
        )

    def _start_observed_event_stream(
        self,
        *,
        state: _LegacyEventState,
        filters: dict[str, Any],
        ack_interval: int,
    ) -> bool:
        callback = lambda event: self._accept_legacy_event(state, event)
        fault_callback = lambda code, cause=None, lost=False: self._report_event_failure(
            state, code, cause, lost=lost
        )

        custom_start = getattr(self._session, "start_observed_event_stream", None)
        if callable(custom_start):
            return bool(
                custom_start(
                    filters=filters,
                    event_callback=callback,
                    fault_callback=fault_callback,
                    ack_interval=ack_interval,
                )
            )

        required_private = ("_session_lock", "_ensure_session", "_open_event_stream", "_event_stream")
        if all(hasattr(self._session, name) for name in required_private):
            return self._start_private_observed_stream(state, filters, ack_interval)

        # Compatibility-only test/double path.  It cannot add observability absent from the
        # wrapped implementation, so the profile remains explicitly degraded.
        return bool(
            self._session.start_event_stream(
                filters=filters,
                callback=callback,
                ack_interval=ack_interval,
            )
        )

    def _start_private_observed_stream(
        self,
        state: _LegacyEventState,
        filters: dict[str, Any],
        ack_interval: int,
    ) -> bool:
        session = self._session
        with session._session_lock:
            session_disabled = session.session_disabled
        if session_disabled:
            return False
        session._ensure_session()
        with session._session_lock:
            if session.session_disabled or "events" not in session.negotiated_features:
                return False
            stream = session._open_event_stream(filters, ack_interval)
            if stream is None:
                return False
            if getattr(stream, "token", None):
                state.stream_id = str(stream.token)
            stream.thread = threading.Thread(
                target=self._observed_event_worker,
                name="hsx-debug-legacy-events",
                daemon=True,
                args=(stream, ack_interval, state),
            )
            state.transport_stream = stream
            # Keep the old stream object alive until this handshake succeeds.  Installing the
            # new object here only changes ExecutiveSession's cleanup pointer; the adapter
            # retains and explicitly retires the old transport after authoritative success.
            session._event_stream = stream
            stream.thread.start()
            return True

    def _observed_event_worker(
        self,
        stream: Any,
        ack_interval: int,
        state: _LegacyEventState,
    ) -> None:
        pending_ack = 0
        last_seq_ack = 0
        terminal_loss_reported = False
        try:
            while not stream.stop_event.is_set():
                try:
                    line = stream.rfile.readline()
                except TimeoutError:
                    continue
                except OSError as exc:
                    if getattr(exc, "errno", None) == socket.timeout:
                        continue
                    self._report_event_failure(state, "event_transport_error", exc, lost=True)
                    terminal_loss_reported = True
                    break
                if not line:
                    if not stream.stop_event.is_set():
                        self._report_event_failure(state, "event_eof", None, lost=True)
                        terminal_loss_reported = True
                    break
                try:
                    event = json.loads(line)
                except json.JSONDecodeError as exc:
                    self._report_event_failure(state, "event_malformed", exc, lost=False)
                    continue
                if not isinstance(event, dict):
                    self._report_event_failure(
                        state,
                        "event_malformed",
                        TypeError("event is not an object"),
                        lost=False,
                    )
                    continue
                accepted = self._accept_legacy_event(state, event)
                seq_value = event.get("seq")
                if accepted and isinstance(seq_value, int) and not isinstance(seq_value, bool) and seq_value > 0:
                    pending_ack += 1
                    last_seq_ack = max(last_seq_ack, seq_value)
                if pending_ack >= max(1, ack_interval) and last_seq_ack > 0 and self._session.session_id:
                    try:
                        response = self._session.request(
                            {"cmd": "events.ack", "seq": last_seq_ack},
                            use_session=True,
                            retry=False,
                        )
                        if not isinstance(response, Mapping) or response.get("status") != "ok":
                            raise ExecutiveSessionError("events.ack rejected")
                    except Exception as exc:
                        self._report_event_failure(state, "event_ack_error", exc, lost=False)
                        break
                    pending_ack = 0
        except Exception as exc:
            self._report_event_failure(state, "event_callback_error", exc, lost=True)
            terminal_loss_reported = True
        finally:
            with self._event_lock:
                unexpected_stop = not state.stop_requested
            if unexpected_stop and not terminal_loss_reported:
                # ExecutiveSession may stop this transport behind the adapter during a
                # keepalive/RPC reopen.  Its stop flag is transport evidence, not an
                # adapter-requested unsubscribe, so it must become observable LOST health.
                self._report_event_failure(
                    state,
                    "event_transport_stopped",
                    None,
                    lost=True,
                )
            stream.stop_event.set()
            try:
                stream.sock.close()
            except Exception:
                pass
            with self._session._session_lock:
                if self._session._event_stream is stream:
                    self._session._event_stream = None

    def _accept_legacy_event(
        self,
        state: _LegacyEventState,
        event: Mapping[str, Any],
    ) -> bool:
        with self._event_lock:
            if state.stop_requested:
                return False
            previous_sequence = state.last_sequence
        if not isinstance(event, Mapping):
            self._report_event_failure(
                state,
                "event_malformed",
                TypeError("event is not a mapping"),
                lost=False,
            )
            return False

        sequence_value = event.get("seq")
        sequence = (
            sequence_value
            if isinstance(sequence_value, int)
            and not isinstance(sequence_value, bool)
            and sequence_value > 0
            else None
        )
        category_value = event.get("type")
        category = str(category_value) if category_value else "legacy_event"
        payload = {
            str(key): _thaw(value)
            for key, value in event.items()
            if key not in {"seq", "type"}
        }
        gap: EventGap | None = None
        gap_reason: str | None = None
        if sequence is None:
            gap_reason = "legacy event has no valid sequence"
        elif previous_sequence is not None and sequence != previous_sequence + 1:
            gap_reason = "legacy event sequence is non-contiguous"
            gap = EventGap(
                expected_sequence=previous_sequence + 1,
                observed_sequence=sequence,
                reason="duplicate, out-of-order, or missing legacy event",
                reconciliation_required=True,
            )
        if category in {"event_dropped", "slow_consumer_drop", "seq_evicted"}:
            gap_reason = f"legacy event stream reported {category}"
            if gap is None and sequence is not None:
                expected = previous_sequence + 1 if previous_sequence is not None else sequence
                gap = EventGap(
                    expected_sequence=expected,
                    observed_sequence=sequence,
                    reason=gap_reason,
                    reconciliation_required=True,
                )
        if sequence is not None:
            with self._event_lock:
                if state.last_sequence is None or sequence > state.last_sequence:
                    state.last_sequence = sequence

        published = True
        if gap_reason is not None:
            health_notice = self._event_health_notice(
                state,
                EventHealth.GAP,
                f"{gap_reason}; reconciliation required",
            )
            published = self._publish_event_notice(state, health_notice) and published
        event_notice = GatewayEvent(
            generation=state.generation,
            stream_id=state.stream_id,
            sequence=sequence,
            category=category,
            payload=payload,
            gap=gap,
            evidence_grade=state.generation.evidence_grade,
        )
        return self._publish_event_notice(state, event_notice) and published

    def report_event_failure(
        self,
        code: str,
        cause: BaseException | None = None,
        *,
        lost: bool = False,
    ) -> None:
        """Surface a test/double-reported legacy event failure as typed health."""

        with self._event_lock:
            state = self._pending_event_state or self._active_event_state
        if state is None:
            return
        self._report_event_failure(state, code, cause, lost=lost)

    def _report_event_failure(
        self,
        state: _LegacyEventState,
        code: str,
        cause: BaseException | None,
        *,
        lost: bool,
    ) -> None:
        with self._event_lock:
            if state.stop_requested:
                return
        event_health = EventHealth.LOST if lost else EventHealth.GAP
        cause_name = type(cause).__name__ if cause is not None else "none"
        notice = self._event_health_notice(
            state,
            event_health,
            f"{code}: {cause_name}; reconciliation required",
        )
        self._publish_event_notice(state, notice)

    def _event_health_notice(
        self,
        state: _LegacyEventState,
        event_health: EventHealth,
        reason: str,
    ) -> HealthNotice:
        if state.established and self.health.matches(state.generation):
            return self.health.transition(event_health=event_health, reason=reason)
        current = self.health.snapshot()
        return HealthNotice(
            generation=state.generation,
            rpc_health=current.rpc_health,
            event_health=event_health,
            reason=reason,
        )

    def _publish_event_notice(
        self,
        state: _LegacyEventState,
        notice: GatewayNotice,
    ) -> bool:
        with self._event_lock:
            if state.stop_requested:
                return False
            if not state.established:
                state.buffered.append(notice)
                return True
            publish = state.publish
        try:
            return bool(publish(notice))
        except Exception as exc:
            # The normal publisher never invokes the controller directly and reports sink
            # failures itself.  A foreign publisher exception is still not allowed to escape
            # the legacy event thread or leave health falsely healthy.
            if state.established and self.health.matches(state.generation):
                self.health.transition(
                    event_health=EventHealth.GAP,
                    reason=(
                        f"event publish callback failed: {type(exc).__name__}; "
                        "reconciliation required"
                    ),
                )
            return False

    def _stop_active_event_transport(self) -> None:
        with self._event_lock:
            state = self._active_event_state
            if state is not None:
                state.stop_requested = True
            pending = self._pending_event_state
            if pending is not None:
                pending.stop_requested = True
            self._active_event_state = None
            self._pending_event_state = None
        if state is not None:
            self._session.stop_event_stream()

    def _stop_event_state_transport(self, state: _LegacyEventState) -> None:
        stream = state.transport_stream
        if stream is None:
            return
        stream.stop_event.set()
        try:
            stream.sock.shutdown(socket.SHUT_RDWR)
        except Exception:
            pass
        try:
            stream.sock.close()
        except Exception:
            pass
        thread = getattr(stream, "thread", None)
        if thread is not None and thread is not threading.current_thread() and thread.is_alive():
            thread.join(timeout=1.0)
        with self._session._session_lock:
            if self._session._event_stream is stream:
                self._session._event_stream = None

    def _mark_event_states_stopped(self) -> None:
        with self._event_lock:
            if self._active_event_state is not None:
                self._active_event_state.stop_requested = True
            if self._pending_event_state is not None:
                self._pending_event_state.stop_requested = True
            self._active_event_state = None
            self._pending_event_state = None

    @staticmethod
    def _normalise_result(result: EffectResult) -> tuple[GatewayNotice, ...]:
        if result is None:
            return ()
        if isinstance(result, (GatewayCompletion, GatewayEvent, HealthNotice, ReconcileResult)):
            return (result,)
        return tuple(result)

    @staticmethod
    def _request_payload(
        payload: Mapping[str, Any],
        *,
        default: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        request = payload.get("request", default)
        if not isinstance(request, Mapping):
            raise ValueError("effect payload requires a request mapping")
        thawed = _thaw(request)
        if not isinstance(thawed, dict) or not isinstance(thawed.get("cmd"), str) or not thawed["cmd"]:
            raise ValueError("legacy request requires a non-empty cmd")
        # Session identity belongs to ExecutiveSession and cannot be supplied by a controller.
        thawed.pop("session", None)
        return thawed

    def _response_completion(
        self,
        effect: GatewayEffect,
        response_value: Any,
        *,
        response: Mapping[str, Any] | None = None,
        authoritative_resource: bool = False,
    ) -> GatewayCompletion:
        if not isinstance(response_value, Mapping):
            raise ValueError("legacy Executive response must be an object")
        status_value = response_value.get("status")
        if status_value == "ok":
            return GatewayCompletion(
                operation_id=effect.operation_id,
                generation=effect.generation,
                status=CompletionStatus.OK,
                response=response or {"legacy_response": _thaw(response_value)},
                evidence_grade=effect.generation.evidence_grade,
                authority=(
                    CompletionAuthority.AUTHORITATIVE_RESOURCE_ESTABLISHED
                    if authoritative_resource
                    else CompletionAuthority.ACK_ONLY
                ),
            )
        error_text = str(response_value.get("error") or "legacy Executive rejected request")
        unsupported = "unknown_cmd" in error_text or "unsupported" in error_text
        return GatewayCompletion(
            operation_id=effect.operation_id,
            generation=effect.generation,
            status=CompletionStatus.UNSUPPORTED if unsupported else CompletionStatus.REJECTED,
            response={"legacy_response": _thaw(response_value)},
            failure=GatewayFailure(
                code="legacy_unsupported" if unsupported else "legacy_request_rejected",
                message=error_text,
                retryable=False,
            ),
            evidence_grade=effect.generation.evidence_grade,
        )

    @staticmethod
    def _is_legacy_effect(effect: GatewayEffect) -> bool:
        generation = effect.generation
        return (
            generation.evidence_grade is EvidenceGrade.LEGACY_DEGRADED
            and generation.executive_instance_id is None
            and generation.target_id is None
        )

    def _unsupported_identity(self, effect: GatewayEffect) -> GatewayCompletion:
        return self._failure_completion(
            effect,
            CompletionStatus.UNSUPPORTED,
            "portable_identity_unsupported_by_legacy_gateway",
            "legacy Executive cannot prove portable Executive or target identity",
        )

    def _stale_generation(self, effect: GatewayEffect, message: str) -> GatewayCompletion:
        return self._failure_completion(
            effect,
            CompletionStatus.STALE,
            "stale_gateway_generation",
            message,
        )

    @staticmethod
    def _failure_completion(
        effect: GatewayEffect,
        status: CompletionStatus,
        code: str,
        message: str,
    ) -> GatewayCompletion:
        return GatewayCompletion(
            operation_id=effect.operation_id,
            generation=effect.generation,
            status=status,
            failure=GatewayFailure(
                code=code,
                message=message,
                retryable=False,
            ),
            evidence_grade=effect.generation.evidence_grade,
        )


class LegacyExecutiveGateway:
    """Frozen-port facade combining the worker gateway and legacy adapter."""

    def __init__(
        self,
        session: ExecutiveSession,
        *,
        initial_generation: GenerationStamp | None = None,
        queue_capacity: int = 64,
        close_timeout: float = 2.0,
    ) -> None:
        generation = initial_generation or initial_legacy_generation()
        _validate_legacy_generation(generation)
        self.health = GatewayHealthTracker(generation)
        self.adapter = LegacyExecutiveAdapter(session, self.health)
        self._gateway = WorkerThreadExecutiveGateway(
            self.adapter,
            self.health,
            queue_capacity=queue_capacity,
            close_timeout=close_timeout,
            on_close=self.adapter.close,
            worker_name="hsx-debug-legacy-gateway",
        )

    @classmethod
    def from_endpoint(
        cls,
        host: str,
        port: int,
        *,
        client_name: str,
        features: Iterable[str] | None = None,
        initial_generation: GenerationStamp | None = None,
        queue_capacity: int = 64,
        close_timeout: float = 2.0,
        timeout: float = 5.0,
        max_events: int = 256,
    ) -> "LegacyExecutiveGateway":
        session = ExecutiveSession(
            host,
            port,
            client_name=client_name,
            features=features,
            timeout=timeout,
            max_events=max_events,
        )
        return cls(
            session,
            initial_generation=initial_generation,
            queue_capacity=queue_capacity,
            close_timeout=close_timeout,
        )

    @property
    def is_alive(self) -> bool:
        return self._gateway.is_alive

    @property
    def last_sink_error(self) -> str | None:
        return self._gateway.last_sink_error

    @property
    def last_notice_error(self) -> str | None:
        return self._gateway.last_notice_error

    def capability_profile(self) -> CapabilityProfile:
        return self.adapter.capability_profile()

    def start(self, notice_sink: Any) -> None:
        self._gateway.start(notice_sink)

    def submit(self, effect: GatewayEffect) -> None:
        self._gateway.submit(effect)

    def close(self) -> None:
        self._gateway.close()


__all__ = [
    "LEGACY_EVENT_CAPABILITY",
    "LEGACY_PROFILE_ID",
    "LEGACY_RESOURCE_CAPABILITY",
    "LegacyExecutiveAdapter",
    "LegacyExecutiveGateway",
    "PORTABLE_ACK_AFTER_APPLY_CAPABILITY",
    "PORTABLE_EVENT_RESUME_CAPABILITY",
    "PORTABLE_IDENTITY_CAPABILITY",
    "PORTABLE_RESOURCE_CAPABILITY",
    "initial_legacy_generation",
]
