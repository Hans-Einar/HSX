"""Bounded single-writer actor for the side-by-side debugger foundation."""

from __future__ import annotations

from collections import deque
from concurrent.futures import Future
from dataclasses import dataclass
import queue
import threading
import time
from typing import Callable
import uuid

from .contracts import (
    CapabilityProfile,
    CommandResult,
    CommandStatus,
    CompletionStatus,
    ControllerCommand,
    ControllerEvent,
    ControllerSnapshot,
    DeadlineExpired,
    GatewayCompletion,
    GatewayEffect,
    GatewayEvent,
    GatewayFailure,
    GatewayNotice,
    GenerationStamp,
    GenerationWatermarks,
    HealthNotice,
    ReconcileResult,
)
from .model import ControllerModel, initial_legacy_model
from .reducer import Reduction, close_model, reduce_command, reduce_deadline, reduce_notice


class ControllerInboxFullError(RuntimeError):
    """The bounded controller inbox cannot accept another asynchronous input."""


@dataclass(frozen=True, slots=True)
class _CommandMessage:
    command: ControllerCommand
    future: Future[CommandResult]


@dataclass(frozen=True, slots=True)
class _NoticeMessage:
    notice: GatewayNotice


@dataclass(frozen=True, slots=True)
class _DeadlineMessage:
    expired: DeadlineExpired


@dataclass(frozen=True, slots=True)
class _SnapshotMessage:
    future: Future[ControllerSnapshot]


@dataclass(frozen=True, slots=True)
class _CloseMessage:
    future: Future[CommandResult]


@dataclass(frozen=True, slots=True)
class _InternalFailureWakeMessage:
    pass


_ActorMessage = (
    _CommandMessage
    | _NoticeMessage
    | _DeadlineMessage
    | _SnapshotMessage
    | _CloseMessage
    | _InternalFailureWakeMessage
)


class ControllerSubscription:
    """A bounded callback lane that cannot block or mutate the controller actor."""

    def __init__(
        self,
        callback: Callable[[ControllerEvent], None],
        *,
        capacity: int,
        close_timeout: float,
        name: str,
        on_close: Callable[[ControllerSubscription], None],
    ) -> None:
        if not callable(callback):
            raise TypeError("callback must be callable")
        if isinstance(capacity, bool) or not isinstance(capacity, int) or capacity < 1:
            raise ValueError("capacity must be a positive integer")
        self._callback = callback
        self._queue: queue.Queue[ControllerEvent] = queue.Queue(maxsize=capacity)
        self._close_timeout = close_timeout
        self._on_close = on_close
        self._closed = threading.Event()
        self._lock = threading.Lock()
        self._dropped_events = 0
        self._callback_errors = 0
        self._removed = False
        self._thread = threading.Thread(target=self._run, name=name, daemon=True)
        self._thread.start()

    @property
    def dropped_events(self) -> int:
        with self._lock:
            return self._dropped_events

    @property
    def callback_errors(self) -> int:
        with self._lock:
            return self._callback_errors

    @property
    def closed(self) -> bool:
        return self._closed.is_set()

    def offer(self, event: ControllerEvent) -> bool:
        if self._closed.is_set():
            return False
        try:
            self._queue.put_nowait(event)
            return True
        except queue.Full:
            with self._lock:
                self._dropped_events += 1
            return False

    def _run(self) -> None:
        while not self._closed.is_set() or not self._queue.empty():
            try:
                event = self._queue.get(timeout=0.05)
            except queue.Empty:
                continue
            try:
                self._callback(event)
            except Exception:
                with self._lock:
                    self._callback_errors += 1

    def _request_close(self, *, remove: bool) -> None:
        self._closed.set()
        call_remove = False
        with self._lock:
            if remove and not self._removed:
                self._removed = True
                call_remove = True
        if call_remove:
            self._on_close(self)

    def close(self) -> None:
        self._request_close(remove=True)
        self.join(self._close_timeout)

    def _owner_close(self) -> None:
        self._request_close(remove=False)

    def join(self, timeout: float | None = None) -> None:
        if threading.current_thread() is not self._thread:
            self._thread.join(timeout)


class ControllerActor:
    """Serialized controller implementing the frozen ``DebuggerController`` port."""

    def __init__(
        self,
        effect_sink: Callable[[GatewayEffect], None] | None = None,
        *,
        initial_generation: GenerationStamp | None = None,
        capability_profile: CapabilityProfile | None = None,
        generation_watermarks: GenerationWatermarks | None = None,
        inbox_capacity: int = 256,
        effect_capacity: int = 256,
        subscriber_capacity: int = 64,
        subscriber_limit: int = 32,
        close_timeout: float = 0.25,
        id_factory: Callable[[str], str] | None = None,
    ) -> None:
        for value, name in (
            (inbox_capacity, "inbox_capacity"),
            (effect_capacity, "effect_capacity"),
            (subscriber_capacity, "subscriber_capacity"),
            (subscriber_limit, "subscriber_limit"),
        ):
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise ValueError(f"{name} must be a positive integer")
        if (
            isinstance(close_timeout, bool)
            or not isinstance(close_timeout, (int, float))
            or close_timeout < 0
        ):
            raise ValueError("close_timeout must be a non-negative number")
        if effect_sink is not None and not callable(effect_sink):
            raise TypeError("effect_sink must be callable")
        if id_factory is not None and not callable(id_factory):
            raise TypeError("id_factory must be callable")

        self._model: ControllerModel = initial_legacy_model(
            initial_generation, capability_profile, generation_watermarks
        )
        self._effect_sink = effect_sink or (lambda effect: None)
        self._id_factory = id_factory or (lambda kind: f"{kind}-{uuid.uuid4().hex}")
        # Two physical slots are reserved for close and the coalesced internal-failure wake.
        # The semaphore remains the public bounded inbox budget, so neither terminal delivery
        # nor shutdown can be starved by ordinary messages.
        self._inbox: queue.Queue[_ActorMessage] = queue.Queue(maxsize=inbox_capacity + 2)
        self._inbox_slots = threading.BoundedSemaphore(inbox_capacity)
        self._effects: queue.Queue[GatewayEffect] = queue.Queue(maxsize=effect_capacity)
        # Effect-sink failures are terminal reducer inputs, not optional public notices.  They
        # therefore use a private FIFO lane which cannot consume the bounded public inbox.
        # The lane has a structural bound of effect_capacity + 1: at most effect_capacity
        # previously queued effects plus the one effect emitted by the actor's current turn
        # can fail before the actor drains this lane at the next turn boundary.  The deque has
        # no maxlen so an invariant violation can never evict a terminal result silently.
        self._internal_failures: deque[GatewayCompletion] = deque()
        self._internal_failures_lock = threading.Lock()
        self._internal_failures_ready = threading.Event()
        self._internal_failures_open = True
        self._internal_failure_wake_outstanding = False
        self._internal_failure_limit = effect_capacity + 1
        self._internal_failure_peak = 0
        self._subscriber_capacity = subscriber_capacity
        self._subscriber_limit = subscriber_limit
        self._close_timeout = float(close_timeout)
        self._lifecycle_lock = threading.Lock()
        self._subscribers_lock = threading.Lock()
        self._subscribers: list[ControllerSubscription] = []
        self._started = False
        self._accepting = False
        self._closed = False
        self._close_future: Future[CommandResult] | None = None
        # Public command Futures are terminal-result channels.  ACCEPTED is an internal
        # reducer acknowledgement; the actor retains exact operation correlation until a
        # later reducer input produces COMPLETED, FAILED, or CANCELLED.  A list preserves
        # same-operation idempotent retry callers without replacing/leaking the first Future.
        self._operation_futures: dict[str, list[Future[CommandResult]]] = {}
        self._effect_stop = threading.Event()
        self._mutation_thread_ids: set[int] = set()
        self._dropped_internal_notices = 0
        self._actor_thread = threading.Thread(
            target=self._run_actor, name="hsx-debugger-controller", daemon=True
        )
        self._effect_thread = threading.Thread(
            target=self._run_effects, name="hsx-debugger-effects", daemon=True
        )

    @property
    def mutation_thread_ids(self) -> frozenset[int]:
        return frozenset(self._mutation_thread_ids)

    @property
    def actor_thread_alive(self) -> bool:
        return self._actor_thread.is_alive()

    @property
    def effect_thread_alive(self) -> bool:
        return self._effect_thread.is_alive()

    @property
    def dropped_internal_notices(self) -> int:
        return self._dropped_internal_notices

    def _new_id(self, kind: str) -> str:
        value = self._id_factory(kind)
        if not isinstance(value, str) or not value.strip():
            raise ValueError("id_factory must return a non-empty string")
        return value

    def start(self) -> None:
        with self._lifecycle_lock:
            if self._closed:
                raise RuntimeError("controller is closed")
            if self._started:
                return
            self._started = True
            self._accepting = True
            self._effect_thread.start()
            self._actor_thread.start()

    @staticmethod
    def _not_accepting_result(command: ControllerCommand, revision: int) -> CommandResult:
        return CommandResult(
            command_id=command.command_id,
            status=CommandStatus.REJECTED,
            controller_revision=revision,
            error="Cancelled",
            diagnostics=("controller is not accepting commands",),
        )

    def submit(self, command: ControllerCommand) -> Future[CommandResult]:
        if not isinstance(command, ControllerCommand):
            future: Future[CommandResult] = Future()
            future.set_exception(TypeError("command must be ControllerCommand"))
            return future
        future = Future()
        with self._lifecycle_lock:
            if not self._accepting:
                future.set_result(self._not_accepting_result(command, self._model.revision))
                return future
            enqueued = self._enqueue_user(_CommandMessage(command, future))
        if not enqueued:
            future.set_result(
                CommandResult(
                    command_id=command.command_id,
                    status=CommandStatus.FAILED,
                    controller_revision=self._model.revision,
                    error="ControllerBusy",
                    diagnostics=("controller inbox is full",),
                )
            )
        return future

    def accept_gateway_notice(self, notice: GatewayNotice) -> None:
        if not isinstance(
            notice, (GatewayCompletion, GatewayEvent, HealthNotice, ReconcileResult)
        ):
            raise TypeError("notice must be a frozen gateway notice")
        with self._lifecycle_lock:
            if not self._accepting:
                return
            enqueued = self._enqueue_user(_NoticeMessage(notice))
        if not enqueued:
            raise ControllerInboxFullError("controller inbox is full")

    def accept_deadline(self, expired: DeadlineExpired) -> None:
        if not isinstance(expired, DeadlineExpired):
            raise TypeError("expired must be DeadlineExpired")
        with self._lifecycle_lock:
            if not self._accepting:
                return
            enqueued = self._enqueue_user(_DeadlineMessage(expired))
        if not enqueued:
            raise ControllerInboxFullError("controller inbox is full")

    def snapshot(self) -> Future[ControllerSnapshot]:
        future: Future[ControllerSnapshot] = Future()
        with self._lifecycle_lock:
            if not self._started or not self._accepting:
                future.set_result(self._model.snapshot())
                return future
            enqueued = self._enqueue_user(_SnapshotMessage(future))
        if not enqueued:
            future.set_exception(ControllerInboxFullError("controller inbox is full"))
        return future

    def _remove_subscription(self, subscription: ControllerSubscription) -> None:
        with self._subscribers_lock:
            try:
                self._subscribers.remove(subscription)
            except ValueError:
                pass

    def subscribe(self, callback: Callable[[ControllerEvent], None]) -> ControllerSubscription:
        if not callable(callback):
            raise TypeError("callback must be callable")
        # Admission and the close boundary share the lifecycle lock.  Lock order is always
        # lifecycle -> subscribers here; the actor releases subscribers before publishing
        # final lifecycle state, so an accepted registration is necessarily visible to the
        # close snapshot and a post-boundary registration is necessarily rejected.
        with self._lifecycle_lock:
            if self._close_future is not None or self._closed:
                raise RuntimeError("controller is closed")
            with self._subscribers_lock:
                if len(self._subscribers) >= self._subscriber_limit:
                    raise ControllerInboxFullError("controller subscriber limit reached")
                subscription = ControllerSubscription(
                    callback,
                    capacity=self._subscriber_capacity,
                    close_timeout=self._close_timeout,
                    name=f"hsx-debugger-subscriber-{uuid.uuid4().hex[:8]}",
                    on_close=self._remove_subscription,
                )
                self._subscribers.append(subscription)
                return subscription

    def close(self) -> Future[CommandResult]:
        with self._lifecycle_lock:
            if self._close_future is not None:
                return self._close_future
            if not self._started:
                self._started = True
                self._accepting = True
                self._effect_thread.start()
                self._actor_thread.start()
            self._accepting = False
            self._close_future = Future()
            close_future = self._close_future
            self._inbox.put_nowait(_CloseMessage(close_future))
        return close_future

    def wait_closed(self, timeout: float | None = None) -> bool:
        if threading.current_thread() is self._actor_thread:
            return False
        with self._lifecycle_lock:
            started = self._started
            closed = self._closed
        if not started:
            return closed
        self._actor_thread.join(timeout)
        return not self._actor_thread.is_alive()

    def _publish(self, events: tuple[ControllerEvent, ...]) -> None:
        if not events:
            return
        with self._subscribers_lock:
            subscribers = tuple(self._subscribers)
        for event in events:
            for subscriber in subscribers:
                subscriber.offer(event)

    def _enqueue_user(self, message: _ActorMessage) -> bool:
        if not self._inbox_slots.acquire(blocking=False):
            return False
        try:
            self._inbox.put_nowait(message)
        except queue.Full:
            self._inbox_slots.release()
            return False
        return True

    def _apply(self, reduction: Reduction) -> None:
        actor_ident = self._actor_thread.ident
        current_ident = threading.get_ident()
        if actor_ident is None or current_ident != actor_ident:
            raise RuntimeError("controller state mutation attempted outside actor thread")
        if reduction.model is not self._model:
            self._mutation_thread_ids.add(current_ident)
            self._model = reduction.model
        self._publish(reduction.events)

    def _track_command_future(
        self, future: Future[CommandResult], reduction: Reduction
    ) -> None:
        """Bind one public submission to its operation or finish an immediate rejection."""

        if len(reduction.results) != 1:
            raise RuntimeError("command reduction must produce exactly one result")
        result = reduction.results[0]
        if result.status is CommandStatus.ACCEPTED:
            operation_id = result.operation_id
            if operation_id is None:
                raise RuntimeError("accepted command result must carry operation_id")
            self._operation_futures.setdefault(operation_id, []).append(future)
            return
        if not future.done():
            future.set_result(result)

    def _resolve_terminal_results(self, reduction: Reduction) -> None:
        """Resolve and retire exact operation-correlated public Futures once."""

        for result in reduction.results:
            if result.status is CommandStatus.ACCEPTED or result.operation_id is None:
                continue
            futures = self._operation_futures.pop(result.operation_id, ())
            for future in futures:
                if not future.done():
                    future.set_result(result)

    def _queue_effect(self, effect: GatewayEffect) -> None:
        try:
            self._effects.put_nowait(effect)
        except queue.Full:
            completion = GatewayCompletion(
                operation_id=effect.operation_id,
                generation=effect.generation,
                status=CompletionStatus.TRANSPORT_ERROR,
                evidence_grade=effect.generation.evidence_grade,
                failure=GatewayFailure(
                    "EffectQueueFull", "effect queue is full", True
                ),
            )
            reduction = reduce_notice(self._model, completion)
            self._apply(reduction)
            self._resolve_terminal_results(reduction)

    def _offer_internal_failure(self, completion: GatewayCompletion) -> bool:
        """Offer terminal effect failure without blocking or using public inbox capacity.

        ``False`` means close already sealed the lane and owns terminal cancellation for every
        operation still live at that actor boundary.  While the lane is open every accepted
        failure is retained until the actor reduces it.
        """

        with self._internal_failures_lock:
            if not self._internal_failures_open:
                return False
            if len(self._internal_failures) >= self._internal_failure_limit:
                raise RuntimeError("internal effect-failure lane bound exceeded")
            self._internal_failures.append(completion)
            self._internal_failure_peak = max(
                self._internal_failure_peak, len(self._internal_failures)
            )
            self._internal_failures_ready.set()
            if not self._internal_failure_wake_outstanding:
                self._internal_failure_wake_outstanding = True
                # Public messages are semaphore-bounded and close/wake each have one reserved
                # physical slot, so this nonblocking wake cannot contend with public capacity.
                self._inbox.put_nowait(_InternalFailureWakeMessage())
            return True

    def _take_internal_failures(
        self, *, seal: bool = False, consume_wake: bool = False
    ) -> tuple[GatewayCompletion, ...]:
        """Atomically take the FIFO lane and optionally close its lifetime boundary."""

        with self._internal_failures_lock:
            if seal:
                self._internal_failures_open = False
            if seal or consume_wake:
                self._internal_failure_wake_outstanding = False
            failures = tuple(self._internal_failures)
            self._internal_failures.clear()
            self._internal_failures_ready.clear()
            return failures

    def _reduce_internal_failures(
        self, failures: tuple[GatewayCompletion, ...]
    ) -> None:
        for completion in failures:
            try:
                reduction = reduce_notice(self._model, completion)
                self._apply(reduction)
                self._resolve_terminal_results(reduction)
            except Exception as exc:
                self._publish_input_error("effect_failure", exc)

    def _drain_internal_failures(self) -> None:
        if self._internal_failures_ready.is_set():
            self._reduce_internal_failures(self._take_internal_failures())

    def _run_actor(self) -> None:
        while True:
            # Internal terminal failures take priority at actor turn boundaries.  The single
            # coalesced wake makes an empty public inbox immediately runnable; under saturation
            # this pre-turn drain happens before another public message is reduced.
            self._drain_internal_failures()
            message = self._inbox.get()
            if isinstance(message, _InternalFailureWakeMessage):
                self._reduce_internal_failures(
                    self._take_internal_failures(consume_wake=True)
                )
                continue
            if not isinstance(message, _CloseMessage):
                self._inbox_slots.release()
            if isinstance(message, _CommandMessage):
                try:
                    operation_id = self._new_id("operation")
                    deadline_id = self._new_id("deadline")
                    reduction = reduce_command(
                        self._model,
                        message.command,
                        operation_id,
                        deadline_id,
                    )
                    self._apply(reduction)
                    self._track_command_future(message.future, reduction)
                    for effect in reduction.effects:
                        self._queue_effect(effect)
                except Exception as exc:
                    if not message.future.done():
                        message.future.set_exception(exc)
            elif isinstance(message, _NoticeMessage):
                try:
                    reduction = reduce_notice(
                        self._model, message.notice, epoch_id=self._new_id("epoch")
                    )
                    self._apply(reduction)
                    self._resolve_terminal_results(reduction)
                except Exception as exc:
                    self._publish_input_error("gateway_notice", exc)
            elif isinstance(message, _DeadlineMessage):
                try:
                    reduction = reduce_deadline(self._model, message.expired)
                    self._apply(reduction)
                    self._resolve_terminal_results(reduction)
                except Exception as exc:
                    self._publish_input_error("deadline", exc)
            elif isinstance(message, _SnapshotMessage):
                if not message.future.done():
                    message.future.set_result(self._model.snapshot())
            elif isinstance(message, _CloseMessage):
                # Seal against the effect worker first.  Failures that linearized before the
                # seal are reduced in FIFO order; failures whose sink returns afterwards are
                # superseded by close_model's exact terminal cancellation and cannot leak a
                # correlation into an actor that has exited.
                self._effect_stop.set()
                self._reduce_internal_failures(
                    self._take_internal_failures(seal=True)
                )
                reduction = close_model(self._model)
                self._apply(reduction)
                self._resolve_terminal_results(reduction)
                with self._subscribers_lock:
                    subscribers = tuple(self._subscribers)
                    self._subscribers.clear()
                close_deadline = time.monotonic() + self._close_timeout
                for subscriber in subscribers:
                    subscriber._owner_close()
                for subscriber in subscribers:
                    subscriber.join(max(0.0, close_deadline - time.monotonic()))
                if threading.current_thread() is not self._effect_thread:
                    self._effect_thread.join(max(0.0, close_deadline - time.monotonic()))
                with self._lifecycle_lock:
                    self._closed = True
                if not message.future.done():
                    message.future.set_result(reduction.results[-1])
                return

    def _publish_input_error(self, input_kind: str, exc: Exception) -> None:
        event = ControllerEvent(
            controller_revision=self._model.revision,
            kind="controller_input_error",
            generation=self._model.generation,
            payload={"input_kind": input_kind, "cause": str(exc) or type(exc).__name__},
        )
        self._publish((event,))

    def _run_effects(self) -> None:
        while not self._effect_stop.is_set():
            try:
                effect = self._effects.get(timeout=0.05)
            except queue.Empty:
                continue
            try:
                self._effect_sink(effect)
            except Exception as exc:
                completion = GatewayCompletion(
                    operation_id=effect.operation_id,
                    generation=effect.generation,
                    status=CompletionStatus.TRANSPORT_ERROR,
                    evidence_grade=effect.generation.evidence_grade,
                    failure=GatewayFailure(
                        "EffectSinkFailure",
                        "effect sink rejected the operation",
                        True,
                        cause=str(exc) or type(exc).__name__,
                    ),
                )
                self._offer_internal_failure(completion)


__all__ = [
    "ControllerActor",
    "ControllerInboxFullError",
    "ControllerSubscription",
]
