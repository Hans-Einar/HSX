"""Small lifecycle coordinator for the signed controller and gateway foundations.

The coordinator owns wiring and shutdown order only.  Debugger state policy remains in
``ControllerActor`` and all transport/session mechanics remain in the supplied gateway.
"""

from __future__ import annotations

from collections.abc import Callable
import threading

from .contracts import (
    CapabilityProfile,
    ExecutiveGatewayPort,
    GenerationStamp,
    GenerationWatermarks,
)
from .controller import ControllerActor


class ControllerGatewayRuntime:
    """Own one controller/gateway pair behind their frozen public ports.

    ``start`` and ``close`` are idempotent.  Startup makes the controller notice sink live
    before the gateway can publish evidence.  Shutdown first seals the controller command
    boundary and then closes the gateway, so no transport callback can outlive its owner.
    """

    def __init__(
        self,
        gateway: ExecutiveGatewayPort,
        *,
        initial_generation: GenerationStamp,
        capability_profile: CapabilityProfile | None = None,
        generation_watermarks: GenerationWatermarks | None = None,
        controller_id_factory: Callable[[str], str] | None = None,
        controller_close_timeout: float = 0.25,
    ) -> None:
        if not isinstance(gateway, ExecutiveGatewayPort):
            raise TypeError("gateway must implement ExecutiveGatewayPort")
        if not isinstance(initial_generation, GenerationStamp):
            raise TypeError("initial_generation must be GenerationStamp")

        self._gateway = gateway
        self._controller_close_wait = float(controller_close_timeout) + 1.0
        self._controller = ControllerActor(
            gateway.submit,
            initial_generation=initial_generation,
            capability_profile=capability_profile,
            generation_watermarks=generation_watermarks,
            close_timeout=controller_close_timeout,
            id_factory=controller_id_factory,
        )
        self._lock = threading.Lock()
        self._close_complete = threading.Event()
        self._started = False
        self._closing = False
        self._closed = False

    @property
    def controller(self) -> ControllerActor:
        """Return the actual frozen-port controller owned by this runtime."""

        return self._controller

    @property
    def gateway(self) -> ExecutiveGatewayPort:
        """Return the actual frozen-port gateway owned by this runtime."""

        return self._gateway

    @property
    def started(self) -> bool:
        with self._lock:
            return self._started

    @property
    def closed(self) -> bool:
        with self._lock:
            return self._closed

    def start(self) -> None:
        """Start the pair once, with the controller ready before gateway publication."""

        with self._lock:
            if self._closed or self._closing:
                raise RuntimeError("runtime is closed")
            if self._started:
                return
            # No external command can be submitted through this owned runtime before start
            # returns, so bringing up the actor first cannot dispatch an effect prematurely.
            self._controller.start()
            try:
                self._gateway.start(self._controller.accept_gateway_notice)
            except BaseException:
                self._closing = True
                try:
                    self._controller.close().result(timeout=self._controller_close_wait)
                    self._controller.wait_closed(self._controller_close_wait)
                finally:
                    try:
                        self._gateway.close()
                    finally:
                        self._closed = True
                        self._close_complete.set()
                raise
            self._started = True

    def close(self) -> None:
        """Seal controller ownership, then close transport; concurrent calls converge."""

        wait_for_owner = False
        with self._lock:
            if self._closed:
                return
            if self._closing:
                wait_for_owner = True
            else:
                self._closing = True

        if wait_for_owner:
            self._close_complete.wait()
            return

        try:
            # Controller.close() is itself idempotent and exact-result correlated.  It also
            # stops the effect dispatcher before completing, so the gateway may then close
            # without a later controller effect racing its transport boundary.
            self._controller.close().result(timeout=self._controller_close_wait)
            self._controller.wait_closed(self._controller_close_wait)
        finally:
            try:
                self._gateway.close()
            finally:
                with self._lock:
                    self._closed = True
                self._close_complete.set()

    def __enter__(self) -> "ControllerGatewayRuntime":
        self.start()
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.close()


__all__ = ["ControllerGatewayRuntime"]
