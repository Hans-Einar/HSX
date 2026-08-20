"""Bounded worker-thread implementation of the frozen Executive gateway port."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
import queue
import threading
from typing import Callable, Iterable, Protocol, TypeAlias

from .contracts import (
    CompletionAuthority,
    CompletionStatus,
    EffectKind,
    EventHealth,
    GatewayCompletion,
    GatewayEffect,
    GatewayEvent,
    GatewayFailure,
    GatewayNotice,
    HealthNotice,
    ReconcileResult,
    RpcHealth,
)
from .health import GatewayHealthTracker


NoticePublisher: TypeAlias = Callable[[GatewayNotice], bool]
EffectResult: TypeAlias = GatewayNotice | Iterable[GatewayNotice] | None


class GatewayEffectHandler(Protocol):
    def __call__(self, effect: GatewayEffect, publish: NoticePublisher) -> EffectResult: ...


class GatewayEffectError(RuntimeError):
    """Typed internal effect failure converted into a frozen completion envelope."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        status: CompletionStatus,
        retryable: bool = False,
        cause: BaseException | None = None,
    ) -> None:
        super().__init__(message)
        if not isinstance(code, str) or not code:
            raise ValueError("code must be a non-empty string")
        if not isinstance(status, CompletionStatus):
            raise TypeError("status must be CompletionStatus")
        if not isinstance(retryable, bool):
            raise TypeError("retryable must be a bool")
        self.code = code
        self.status = status
        self.retryable = retryable
        self.cause = cause


class GatewayQueueFullError(RuntimeError):
    """Raised when the bounded gateway inbox cannot accept an effect."""


@dataclass(frozen=True, slots=True)
class _EffectItem:
    effect: GatewayEffect


@dataclass(frozen=True, slots=True)
class _NoticeItem:
    notice: GatewayNotice


_STOP = object()
_NOTICE_TYPES = (GatewayCompletion, GatewayEvent, HealthNotice, ReconcileResult)
_RESOURCE_EFFECTS = (EffectKind.OPEN_SESSION, EffectKind.SUBSCRIBE_EVENTS)


class WorkerThreadExecutiveGateway:
    """Serialize effects and sink calls on one bounded worker lane.

    Event readers may call the supplied ``publish`` callback from any thread.  Publication
    only enqueues immutable evidence; controller callbacks always run on the gateway worker.
    Operation reuse and handler output are checked so no completion can substitute a stamp,
    and new-generation health/events cannot pass the resource-establishment completion.
    """

    def __init__(
        self,
        handler: GatewayEffectHandler,
        health: GatewayHealthTracker,
        *,
        queue_capacity: int = 64,
        close_timeout: float = 2.0,
        on_close: Callable[[], None] | None = None,
        worker_name: str = "hsx-debug-gateway",
    ) -> None:
        if not callable(handler):
            raise TypeError("handler must be callable")
        if not isinstance(health, GatewayHealthTracker):
            raise TypeError("health must be GatewayHealthTracker")
        if isinstance(queue_capacity, bool) or not isinstance(queue_capacity, int) or queue_capacity < 1:
            raise ValueError("queue_capacity must be a positive integer")
        if isinstance(close_timeout, bool) or not isinstance(close_timeout, (int, float)):
            raise TypeError("close_timeout must be numeric")
        if close_timeout < 0:
            raise ValueError("close_timeout must be non-negative")
        if on_close is not None and not callable(on_close):
            raise TypeError("on_close must be callable or None")
        self._handler = handler
        self.health = health
        self._queue: queue.Queue[object] = queue.Queue(maxsize=queue_capacity)
        self._deferred: deque[object] = deque()
        self._close_timeout = float(close_timeout)
        self._on_close = on_close
        self._worker_name = worker_name
        self._state_lock = threading.Lock()
        self._pending_lock = threading.Lock()
        self._close_call_lock = threading.Lock()
        self._closing = threading.Event()
        self._stopped = threading.Event()
        self._close_called = threading.Event()
        self._started = False
        self._sink: Callable[[GatewayNotice], None] | None = None
        self._worker: threading.Thread | None = None
        self._pending_health: HealthNotice | None = None
        self._last_sink_error: str | None = None
        self._last_notice_error: str | None = None

        # Accessed only by the worker thread.  This is correlation state, never generation
        # allocation: every stored stamp came verbatim from a submitted effect.
        self._operations: dict[str, GatewayEffect] = {}
        self._established_generations = {health.generation}

    @property
    def is_alive(self) -> bool:
        with self._state_lock:
            return bool(self._worker and self._worker.is_alive())

    @property
    def last_sink_error(self) -> str | None:
        with self._pending_lock:
            return self._last_sink_error

    @property
    def last_notice_error(self) -> str | None:
        with self._pending_lock:
            return self._last_notice_error

    def start(self, notice_sink: Callable[[GatewayNotice], None]) -> None:
        if not callable(notice_sink):
            raise TypeError("notice_sink must be callable")
        with self._state_lock:
            if self._started:
                raise RuntimeError("gateway already started")
            if self._closing.is_set():
                raise RuntimeError("gateway is closed")
            self._sink = notice_sink
            self._started = True
            worker = threading.Thread(target=self._worker_main, name=self._worker_name, daemon=True)
            self._worker = worker
            worker.start()

    def submit(self, effect: GatewayEffect) -> None:
        if not isinstance(effect, GatewayEffect):
            raise TypeError("effect must be GatewayEffect")
        with self._state_lock:
            started = self._started
            closing = self._closing.is_set()
        if not started:
            raise RuntimeError("gateway has not been started")
        if closing:
            raise RuntimeError("gateway is closed")
        try:
            self._queue.put_nowait(_EffectItem(effect))
        except queue.Full as exc:
            self._remember_health(
                self.health.transition(
                    rpc_health=RpcHealth.DEGRADED,
                    reason="gateway effect queue saturated",
                )
            )
            raise GatewayQueueFullError("gateway effect queue is full") from exc

    def publish_notice(self, notice: GatewayNotice) -> bool:
        """Thread-safe publication entry used by event/session callbacks."""

        if not isinstance(notice, _NOTICE_TYPES):
            raise TypeError("notice must be a frozen GatewayNotice")
        if self._closing.is_set():
            return False
        try:
            self._queue.put_nowait(_NoticeItem(notice))
            return True
        except queue.Full:
            self._remember_health(
                self.health.transition(
                    event_health=EventHealth.GAP,
                    reason="gateway notice queue saturated; reconciliation required",
                )
            )
            return False

    def close(self) -> None:
        """Stop accepting work, returning after at most ``close_timeout`` seconds."""

        with self._state_lock:
            if not self._closing.is_set():
                self._closing.set()
                try:
                    self._queue.put_nowait(_STOP)
                except queue.Full:
                    pass
            worker = self._worker
        if worker is None:
            self._invoke_on_close()
            self._stopped.set()
            return
        if worker is threading.current_thread():
            return
        self._stopped.wait(timeout=self._close_timeout)

    def _worker_main(self) -> None:
        try:
            while True:
                if self._closing.is_set() and self._queue.empty() and not self._deferred:
                    break
                try:
                    item = self._deferred.popleft() if self._deferred else self._queue.get(timeout=0.05)
                except queue.Empty:
                    continue
                try:
                    if item is _STOP:
                        break
                    if isinstance(item, _EffectItem):
                        if self._closing.is_set():
                            self._deliver_notice(self._cancelled(item.effect))
                        else:
                            self._execute(item.effect)
                    elif isinstance(item, _NoticeItem) and not self._closing.is_set():
                        self._deliver_published_notice(item.notice)
                finally:
                    self._queue.task_done()
        finally:
            self._cancel_queued_effects()
            self._invoke_on_close()
            self._stopped.set()

    def _execute(self, effect: GatewayEffect) -> None:
        validation_error = self._register_operation(effect)
        if validation_error is not None:
            self._deliver_effect_error(effect, validation_error)
            return
        try:
            notices = self._coerce_notices(self._handler(effect, self.publish_notice))
            self._validate_effect_result(effect, notices)
            if effect.kind in _RESOURCE_EFFECTS:
                self._deliver_old_continuity_notices(effect)
            for notice in notices:
                self._deliver_notice(notice)
        except GatewayEffectError as exc:
            if effect.kind in _RESOURCE_EFFECTS:
                self._deliver_old_continuity_notices(effect)
            self._deliver_effect_error(effect, exc)
        except Exception as exc:
            if effect.kind in _RESOURCE_EFFECTS:
                self._deliver_old_continuity_notices(effect)
            self._deliver_effect_error(
                effect,
                GatewayEffectError(
                    "gateway_handler_failure",
                    "gateway effect handler failed",
                    status=CompletionStatus.PROTOCOL_ERROR,
                    cause=exc,
                ),
            )

    def _deliver_old_continuity_notices(self, effect: GatewayEffect) -> None:
        """Deliver queued old-active evidence before a replacement completion.

        A blocking OPEN/SUBSCRIBE handler can overlap an existing event reader.  Those event
        callbacks enqueue onto this worker lane while the handler is busy.  Drain only the
        queue snapshot that existed when the handler returned, and only exact already-
        established notices from that snapshot.  A live producer therefore cannot postpone
        the authoritative completion indefinitely.  Effects, STOP, candidate-generation
        evidence, and anything appended after the snapshot resume through normal FIFO work.
        """

        deferred: list[object] = []
        snapshot_size = self._queue.qsize()
        for _ in range(snapshot_size):
            try:
                item = self._queue.get_nowait()
            except queue.Empty:
                break
            if (
                isinstance(item, _NoticeItem)
                and item.notice.generation != effect.generation
                and self._notice_is_established(item.notice)
            ):
                try:
                    self._deliver_published_notice(item.notice)
                finally:
                    self._queue.task_done()
            else:
                deferred.append(item)
        self._deferred.extend(deferred)

    def _register_operation(self, effect: GatewayEffect) -> GatewayEffectError | None:
        previous = self._operations.get(effect.operation_id)
        if previous is None:
            self._operations[effect.operation_id] = effect
            return None
        if previous != effect:
            return GatewayEffectError(
                "operation_identity_mismatch",
                "operation ID was reused with a different effect or generation stamp",
                status=CompletionStatus.PROTOCOL_ERROR,
            )
        if not effect.idempotent:
            return GatewayEffectError(
                "non_idempotent_retry_rejected",
                "a non-idempotent effect cannot be retried",
                status=CompletionStatus.REJECTED,
            )
        return None

    @staticmethod
    def _coerce_notices(result: EffectResult) -> tuple[GatewayNotice, ...]:
        if result is None:
            return ()
        if isinstance(result, _NOTICE_TYPES):
            return (result,)
        try:
            notices = tuple(result)
        except TypeError as exc:
            raise GatewayEffectError(
                "invalid_handler_result",
                "effect handler result must contain GatewayNotice values",
                status=CompletionStatus.PROTOCOL_ERROR,
                cause=exc,
            ) from exc
        if not all(isinstance(notice, _NOTICE_TYPES) for notice in notices):
            raise GatewayEffectError(
                "invalid_handler_result",
                "effect handler result must contain GatewayNotice values",
                status=CompletionStatus.PROTOCOL_ERROR,
            )
        return notices

    def _validate_effect_result(
        self,
        effect: GatewayEffect,
        notices: tuple[GatewayNotice, ...],
    ) -> None:
        saw_completion = False
        saw_reconcile = False
        resource_established = effect.generation in self._established_generations
        for notice in notices:
            if isinstance(notice, GatewayCompletion):
                if notice.operation_id != effect.operation_id or notice.generation != effect.generation:
                    raise GatewayEffectError(
                        "completion_stamp_mismatch",
                        "handler completion did not echo the exact operation and generation stamp",
                        status=CompletionStatus.PROTOCOL_ERROR,
                    )
                saw_completion = True
                authoritative = (
                    notice.status is CompletionStatus.OK
                    and notice.authority
                    is CompletionAuthority.AUTHORITATIVE_RESOURCE_ESTABLISHED
                )
                if notice.authority is CompletionAuthority.AUTHORITATIVE_RESOURCE_ESTABLISHED:
                    if effect.kind not in _RESOURCE_EFFECTS or notice.status is not CompletionStatus.OK:
                        raise GatewayEffectError(
                            "invalid_completion_authority",
                            "resource-established authority is valid only for successful OPEN/SUBSCRIBE",
                            status=CompletionStatus.PROTOCOL_ERROR,
                        )
                if effect.kind in _RESOURCE_EFFECTS and notice.status is CompletionStatus.OK:
                    if not authoritative:
                        raise GatewayEffectError(
                            "missing_resource_establishment_authority",
                            "successful OPEN/SUBSCRIBE must carry resource-established authority",
                            status=CompletionStatus.PROTOCOL_ERROR,
                        )
                    resource_established = True
            elif isinstance(notice, ReconcileResult):
                saw_reconcile = True
                if notice.generation != effect.generation:
                    raise GatewayEffectError(
                        "reconcile_stamp_mismatch",
                        "reconcile result did not echo the exact effect generation stamp",
                        status=CompletionStatus.PROTOCOL_ERROR,
                    )
            elif (
                effect.kind in _RESOURCE_EFFECTS
                and notice.generation == effect.generation
                and not resource_established
            ):
                raise GatewayEffectError(
                    "pre_establishment_notice",
                    "new-generation health/event preceded authoritative resource establishment",
                    status=CompletionStatus.PROTOCOL_ERROR,
                )

        if effect.kind is EffectKind.RECONCILE:
            if not (saw_reconcile or saw_completion):
                raise GatewayEffectError(
                    "missing_reconcile_result",
                    "RECONCILE produced no typed result",
                    status=CompletionStatus.PROTOCOL_ERROR,
                )
        elif not saw_completion:
            raise GatewayEffectError(
                "missing_completion",
                "gateway effect produced no typed completion",
                status=CompletionStatus.PROTOCOL_ERROR,
            )

    def _deliver_effect_error(self, effect: GatewayEffect, error: GatewayEffectError) -> None:
        if error.status is CompletionStatus.TRANSPORT_ERROR:
            event_lost = self.health.event_health is EventHealth.LOST
            self._deliver_notice(
                self.health.transition(
                    rpc_health=RpcHealth.LOST,
                    reason=(
                        f"RPC transport failure: {error.code}; reconciliation required; "
                        "event continuity lost"
                        if event_lost
                        else f"RPC transport failure: {error.code}; reconciliation required"
                    ),
                )
            )
        elif error.status is CompletionStatus.PROTOCOL_ERROR:
            event_lost = self.health.event_health is EventHealth.LOST
            self._deliver_notice(
                self.health.transition(
                    rpc_health=RpcHealth.DEGRADED,
                    reason=(
                        f"RPC protocol failure: {error.code}; "
                        "event continuity lost; reconciliation required"
                        if event_lost
                        else f"RPC protocol failure: {error.code}"
                    ),
                )
            )
        cause = type(error.cause).__name__ if error.cause is not None else None
        self._deliver_notice(
            GatewayCompletion(
                operation_id=effect.operation_id,
                generation=effect.generation,
                status=error.status,
                failure=GatewayFailure(
                    code=error.code,
                    message=str(error),
                    retryable=bool(error.retryable and effect.idempotent),
                    cause=cause,
                ),
                evidence_grade=effect.generation.evidence_grade,
            )
        )

    def _deliver_published_notice(self, notice: GatewayNotice) -> None:
        if isinstance(notice, GatewayCompletion):
            effect = self._operations.get(notice.operation_id)
            if effect is None or notice.generation != effect.generation:
                self._reject_notice("published completion has no exact submitted operation/stamp")
                return
            if notice.authority is CompletionAuthority.AUTHORITATIVE_RESOURCE_ESTABLISHED and not (
                effect.kind in _RESOURCE_EFFECTS and notice.status is CompletionStatus.OK
            ):
                self._reject_notice("published completion has invalid resource authority")
                return
        self._deliver_notice(notice)

    def _deliver_notice(self, notice: GatewayNotice) -> bool:
        pending = self._take_pending_health()
        if pending is not None and pending != notice:
            if self._notice_is_established(pending):
                if not self._call_sink(pending):
                    return False
            else:
                # Keep evidence until the authoritative completion is actually accepted by
                # the sink.  This preserves the completion-before-new-health barrier even
                # when the completion callback itself failed.
                self._remember_health(pending)

        if not self._notice_is_established(notice):
            self._reject_notice("notice generation has no delivered resource establishment")
            return False
        if isinstance(notice, HealthNotice) and self.health.matches(notice.generation):
            # A sink/queue failure may have degraded the tracker after the handler created an
            # immutable health notice.  Publish the current dimensions so stale HEALTHY
            # evidence cannot overwrite the newer observable degradation.
            notice = self.health.snapshot(reason=notice.reason)
        delivered = self._call_sink(notice)
        if delivered and isinstance(notice, GatewayCompletion):
            self._record_delivered_resource_establishment(notice)
        return delivered

    def _notice_is_established(self, notice: GatewayNotice) -> bool:
        if isinstance(notice, GatewayCompletion):
            return True
        return notice.generation in self._established_generations

    def _record_delivered_resource_establishment(self, completion: GatewayCompletion) -> None:
        if (
            completion.status is not CompletionStatus.OK
            or completion.authority
            is not CompletionAuthority.AUTHORITATIVE_RESOURCE_ESTABLISHED
        ):
            return
        effect = self._operations.get(completion.operation_id)
        if effect is None or effect.kind not in _RESOURCE_EFFECTS:
            return
        if effect.generation != completion.generation:
            return
        # A delivered establishment supersedes the prior full continuity domain.  No numeric
        # generation is calculated here; the exact effect stamp becomes the delivery fence.
        self._established_generations = {completion.generation}

    def _call_sink(self, notice: GatewayNotice) -> bool:
        sink = self._sink
        if sink is None:
            return False
        try:
            sink(notice)
            return True
        except Exception as exc:
            degraded = self.health.transition(
                event_health=EventHealth.GAP,
                reason=f"notice sink failed: {type(exc).__name__}; reconciliation required",
            )
            with self._pending_lock:
                self._last_sink_error = f"{type(exc).__name__}: {exc}"
                self._pending_health = degraded
            return False

    def _reject_notice(self, reason: str) -> None:
        with self._pending_lock:
            self._last_notice_error = reason

    def _remember_health(self, notice: HealthNotice) -> None:
        with self._pending_lock:
            self._pending_health = notice

    def _take_pending_health(self) -> HealthNotice | None:
        with self._pending_lock:
            notice = self._pending_health
            self._pending_health = None
            return notice

    @staticmethod
    def _cancelled(effect: GatewayEffect) -> GatewayCompletion:
        return GatewayCompletion(
            operation_id=effect.operation_id,
            generation=effect.generation,
            status=CompletionStatus.CANCELLED,
            failure=GatewayFailure(
                code="gateway_closed",
                message="gateway closed before effect execution",
                retryable=False,
            ),
            evidence_grade=effect.generation.evidence_grade,
        )

    def _cancel_queued_effects(self) -> None:
        while self._deferred:
            item = self._deferred.popleft()
            try:
                if isinstance(item, _EffectItem):
                    self._deliver_notice(self._cancelled(item.effect))
            finally:
                self._queue.task_done()
        while True:
            try:
                item = self._queue.get_nowait()
            except queue.Empty:
                return
            try:
                if isinstance(item, _EffectItem):
                    self._deliver_notice(self._cancelled(item.effect))
            finally:
                self._queue.task_done()

    def _invoke_on_close(self) -> None:
        with self._close_call_lock:
            if self._close_called.is_set():
                return
            self._close_called.set()
        if self._on_close is None:
            return
        try:
            self._on_close()
        except Exception as exc:  # cleanup evidence must not disappear
            self._deliver_notice(
                self.health.transition(
                    rpc_health=RpcHealth.DEGRADED,
                    reason=f"gateway cleanup failed: {type(exc).__name__}",
                )
            )


__all__ = [
    "EffectResult",
    "GatewayEffectError",
    "GatewayEffectHandler",
    "GatewayQueueFullError",
    "NoticePublisher",
    "WorkerThreadExecutiveGateway",
]
