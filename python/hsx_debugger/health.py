"""Thread-safe RPC/event health for one exact debugger generation.

The tracker records transport evidence only.  It never derives, increments, or otherwise
allocates a :class:`GenerationStamp`; a newly established transport resource must supply the
exact controller-reserved stamp through :meth:`establish`.
"""

from __future__ import annotations

import threading

from .contracts import EventHealth, GenerationStamp, HealthNotice, RpcHealth


class GatewayHealthTracker:
    """Own independent RPC and event-stream health for a gateway instance."""

    def __init__(
        self,
        generation: GenerationStamp,
        *,
        rpc_health: RpcHealth = RpcHealth.CLOSED,
        event_health: EventHealth = EventHealth.DISABLED,
    ) -> None:
        if not isinstance(generation, GenerationStamp):
            raise TypeError("generation must be GenerationStamp")
        if not isinstance(rpc_health, RpcHealth):
            raise TypeError("rpc_health must be RpcHealth")
        if not isinstance(event_health, EventHealth):
            raise TypeError("event_health must be EventHealth")
        self._lock = threading.Lock()
        self._generation = generation
        self._rpc_health = rpc_health
        self._event_health = event_health
        self._last_reason = "gateway health initialized"

    @property
    def generation(self) -> GenerationStamp:
        with self._lock:
            return self._generation

    @property
    def rpc_health(self) -> RpcHealth:
        with self._lock:
            return self._rpc_health

    @property
    def event_health(self) -> EventHealth:
        with self._lock:
            return self._event_health

    def matches(self, generation: GenerationStamp) -> bool:
        if not isinstance(generation, GenerationStamp):
            return False
        with self._lock:
            return generation == self._generation

    def snapshot(self, reason: str | None = None) -> HealthNotice:
        """Return an immutable, internally consistent health snapshot."""

        if reason is not None and not isinstance(reason, str):
            raise TypeError("reason must be a string or None")
        with self._lock:
            return HealthNotice(
                generation=self._generation,
                rpc_health=self._rpc_health,
                event_health=self._event_health,
                reason=reason if reason is not None else self._last_reason,
            )

    def transition(
        self,
        *,
        reason: str,
        rpc_health: RpcHealth | None = None,
        event_health: EventHealth | None = None,
    ) -> HealthNotice:
        """Update supplied health dimensions without changing generation identity."""

        self._validate_transition(reason, rpc_health, event_health)
        with self._lock:
            if rpc_health is not None:
                self._rpc_health = rpc_health
            if event_health is not None:
                self._event_health = event_health
            self._last_reason = reason
            return HealthNotice(
                generation=self._generation,
                rpc_health=self._rpc_health,
                event_health=self._event_health,
                reason=reason,
            )

    def establish(
        self,
        generation: GenerationStamp,
        *,
        reason: str,
        rpc_health: RpcHealth | None = None,
        event_health: EventHealth | None = None,
    ) -> HealthNotice:
        """Adopt an exact externally supplied stamp after resource establishment.

        This method intentionally performs no arithmetic and no numeric-greater adoption.
        The caller must already have validated that ``generation`` is the stamp carried by
        the accepted OPEN/SUBSCRIBE effect.
        """

        if not isinstance(generation, GenerationStamp):
            raise TypeError("generation must be GenerationStamp")
        self._validate_transition(reason, rpc_health, event_health)
        with self._lock:
            self._generation = generation
            if rpc_health is not None:
                self._rpc_health = rpc_health
            if event_health is not None:
                self._event_health = event_health
            self._last_reason = reason
            return HealthNotice(
                generation=self._generation,
                rpc_health=self._rpc_health,
                event_health=self._event_health,
                reason=reason,
            )

    @staticmethod
    def _validate_transition(
        reason: str,
        rpc_health: RpcHealth | None,
        event_health: EventHealth | None,
    ) -> None:
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError("reason must be a non-empty string")
        if rpc_health is not None and not isinstance(rpc_health, RpcHealth):
            raise TypeError("rpc_health must be RpcHealth or None")
        if event_health is not None and not isinstance(event_health, EventHealth):
            raise TypeError("event_health must be EventHealth or None")


__all__ = ["GatewayHealthTracker"]
