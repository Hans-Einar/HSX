"""Epoch-bound domain handles for RF-004 inspection.

The store owns only handle identity/lifetime. Snapshot reads, artifact lookup, stack walking,
frontend IDs, and controller lifecycle remain outside this module.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from threading import Lock

from .identity import InspectionContext, StopEpochId
from .results import (
    Diagnostic,
    InspectionStatus,
    InvalidationStatus,
    _register_contract_enums,
)


def _require_int(value: int, field_name: str, *, minimum: int = 0) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ValueError(f"{field_name} must be an integer >= {minimum}")


def _require_nonempty(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field_name} must be a non-empty string")


def _diagnostics(value) -> tuple[Diagnostic, ...]:
    diagnostics = tuple(value)
    if not all(isinstance(item, Diagnostic) for item in diagnostics):
        raise TypeError("diagnostics must contain Diagnostic values")
    return diagnostics


class HandleKind(str, Enum):
    FRAME = "frame"
    SCOPE = "scope"
    VARIABLE = "variable"


class ScopeKind(str, Enum):
    REGISTERS = "registers"
    LOCALS = "locals"
    GLOBALS = "globals"


_register_contract_enums(HandleKind, ScopeKind)


@dataclass(frozen=True, slots=True)
class DomainHandle:
    context: InspectionContext
    kind: HandleKind
    serial: int

    def __post_init__(self) -> None:
        if not isinstance(self.context, InspectionContext):
            raise TypeError("context must be InspectionContext")
        if type(self.kind) is not HandleKind:
            raise TypeError("kind must be HandleKind")
        _require_int(self.serial, "serial", minimum=1)


@dataclass(frozen=True, slots=True)
class HandleInternResult:
    """Dedicated 1.7 envelope for an epoch-bound handle reference."""

    status: InspectionStatus
    context: InspectionContext
    handle: DomainHandle | None
    diagnostics: tuple[Diagnostic, ...] = ()

    def __post_init__(self) -> None:
        if type(self.status) is not InspectionStatus or self.status not in {
            InspectionStatus.COMPLETE,
            InspectionStatus.CORRUPT,
            InspectionStatus.STALE,
        }:
            raise ValueError("HandleInternResult status must be COMPLETE/CORRUPT/STALE")
        if not isinstance(self.context, InspectionContext):
            raise TypeError("context must be InspectionContext")
        diagnostics = _diagnostics(self.diagnostics)
        object.__setattr__(self, "diagnostics", diagnostics)
        if self.status is InspectionStatus.COMPLETE:
            if not isinstance(self.handle, DomainHandle):
                raise TypeError("COMPLETE handle interning requires DomainHandle")
            if self.handle.context != self.context:
                raise ValueError("interned handle must retain exact result context")
            if diagnostics:
                raise ValueError("COMPLETE handle interning carries no diagnostics")
        else:
            if self.handle is not None:
                raise ValueError("failed handle interning publishes no handle")
            if not diagnostics:
                raise ValueError("failed handle interning requires diagnostics")


@dataclass(frozen=True, slots=True)
class HandleResolution:
    status: InspectionStatus
    context: InspectionContext
    kind: HandleKind
    object_key: tuple | None
    diagnostics: tuple[Diagnostic, ...] = ()

    def __post_init__(self) -> None:
        if self.status not in {
            InspectionStatus.COMPLETE,
            InspectionStatus.UNKNOWN_HANDLE,
            InspectionStatus.STALE,
        }:
            raise ValueError("HandleResolution status must be COMPLETE/UNKNOWN_HANDLE/STALE")
        if not isinstance(self.context, InspectionContext):
            raise TypeError("context must be InspectionContext")
        if type(self.kind) is not HandleKind:
            raise TypeError("kind must be HandleKind")
        diagnostics = _diagnostics(self.diagnostics)
        if self.status is InspectionStatus.COMPLETE:
            if not isinstance(self.object_key, tuple):
                raise TypeError("COMPLETE handle resolution requires tuple object_key")
            normalized = _normalized_object_key(self.kind, self.object_key)
            object.__setattr__(self, "object_key", normalized)
            if diagnostics:
                raise ValueError("COMPLETE handle resolution carries no diagnostics")
        else:
            if self.object_key is not None:
                raise ValueError("failed handle resolution publishes no object_key")
            if not diagnostics:
                raise ValueError("failed handle resolution requires a diagnostic")
        object.__setattr__(self, "diagnostics", diagnostics)


@dataclass(frozen=True, slots=True)
class InvalidationResult:
    status: InvalidationStatus
    stop_epoch_id: StopEpochId
    diagnostics: tuple[Diagnostic, ...] = ()

    def __post_init__(self) -> None:
        if type(self.status) is not InvalidationStatus:
            raise TypeError("status must be InvalidationStatus")
        if not isinstance(self.stop_epoch_id, StopEpochId):
            raise TypeError("stop_epoch_id must be StopEpochId")
        object.__setattr__(self, "diagnostics", _diagnostics(self.diagnostics))


def _diagnostic(code: str, message: str) -> Diagnostic:
    return Diagnostic(code, message, component="handles")


def _normalized_object_key(kind: HandleKind, object_key: tuple) -> tuple:
    if not isinstance(object_key, tuple):
        raise TypeError("object_key must be tuple")
    if kind is HandleKind.FRAME:
        if len(object_key) != 1:
            raise ValueError("FRAME object_key must be (frame_index,)")
        _require_int(object_key[0], "frame_index")
        return object_key
    if kind is HandleKind.SCOPE:
        if len(object_key) != 2:
            raise ValueError("SCOPE object_key must be (frame_serial, scope_kind)")
        _require_int(object_key[0], "frame_serial", minimum=1)
        if type(object_key[1]) is not ScopeKind:
            raise TypeError("scope_kind must be ScopeKind")
        return object_key
    if kind is HandleKind.VARIABLE:
        if len(object_key) != 4:
            raise ValueError("VARIABLE object_key must contain four fields")
        _require_int(object_key[0], "scope_serial", minimum=1)
        discriminator = object_key[1]
        if discriminator == "symbol":
            _require_int(object_key[2], "declaration_order")
            _require_nonempty(object_key[3], "symbol_id")
        elif discriminator == "register":
            _require_int(object_key[2], "register_order")
            _require_nonempty(object_key[3], "register_id")
        else:
            raise ValueError("VARIABLE object_key discriminator must be symbol/register")
        return object_key
    raise TypeError("unsupported HandleKind")


class EpochHandleStore:
    """Linearizable exact-key interning for one immutable InspectionContext."""

    def __init__(self, context: InspectionContext) -> None:
        if not isinstance(context, InspectionContext):
            raise TypeError("context must be InspectionContext")
        self._context = context
        self._lock = Lock()
        self._active = True
        self._next_serial = 1
        self._by_key: dict[tuple[HandleKind, tuple], DomainHandle] = {}
        self._by_serial: dict[int, tuple[HandleKind, tuple]] = {}

    @classmethod
    def create(cls, context: InspectionContext) -> EpochHandleStore:
        return cls(context)

    def context(self) -> InspectionContext:
        return self._context

    def is_active(self) -> bool:
        with self._lock:
            return self._active

    def intern(self, kind: HandleKind, object_key: tuple) -> HandleInternResult:
        if type(kind) is not HandleKind:
            raise TypeError("kind must be HandleKind")
        try:
            key = _normalized_object_key(kind, object_key)
        except (TypeError, ValueError) as exc:
            return HandleInternResult(
                InspectionStatus.CORRUPT,
                self._context,
                None,
                (_diagnostic("invalid_handle_key", str(exc)),),
            )
        with self._lock:
            if not self._active:
                return HandleInternResult(
                    InspectionStatus.STALE,
                    self._context,
                    None,
                    (_diagnostic("epoch_handle_store_stale", "handle store is invalidated"),),
                )
            composite = (kind, key)
            existing = self._by_key.get(composite)
            if existing is not None:
                return HandleInternResult(InspectionStatus.COMPLETE, self._context, existing, ())
            serial = self._next_serial
            self._next_serial += 1
            handle = DomainHandle(self._context, kind, serial)
            self._by_key[composite] = handle
            self._by_serial[serial] = composite
            return HandleInternResult(InspectionStatus.COMPLETE, self._context, handle, ())

    def resolve(self, handle: DomainHandle, expected_kind: HandleKind) -> HandleResolution:
        if not isinstance(handle, DomainHandle):
            raise TypeError("handle must be DomainHandle")
        if type(expected_kind) is not HandleKind:
            raise TypeError("expected_kind must be HandleKind")
        if handle.context != self._context:
            return HandleResolution(
                InspectionStatus.UNKNOWN_HANDLE,
                self._context,
                expected_kind,
                None,
                (_diagnostic("foreign_handle_context", "handle belongs to another context"),),
            )
        with self._lock:
            if not self._active:
                return HandleResolution(
                    InspectionStatus.STALE,
                    self._context,
                    expected_kind,
                    None,
                    (_diagnostic("epoch_handle_store_stale", "handle store is invalidated"),),
                )
            record = self._by_serial.get(handle.serial)
            if record is None or handle.kind is not expected_kind:
                return HandleResolution(
                    InspectionStatus.UNKNOWN_HANDLE,
                    self._context,
                    expected_kind,
                    None,
                    (_diagnostic("unknown_handle", "handle serial/kind is not interned here"),),
                )
            kind, key = record
            if kind is not expected_kind:
                return HandleResolution(
                    InspectionStatus.UNKNOWN_HANDLE,
                    self._context,
                    expected_kind,
                    None,
                    (_diagnostic("unknown_handle", "interned handle kind differs"),),
                )
            return HandleResolution(
                InspectionStatus.COMPLETE,
                self._context,
                expected_kind,
                key,
                (),
            )

    def invalidate(self, reason: str) -> InvalidationResult:
        _require_nonempty(reason, "reason")
        with self._lock:
            if not self._active:
                return InvalidationResult(
                    InvalidationStatus.ALREADY_STALE,
                    self._context.epoch.stop_epoch_id,
                    (_diagnostic("epoch_already_stale", reason),),
                )
            self._active = False
            return InvalidationResult(
                InvalidationStatus.INVALIDATED,
                self._context.epoch.stop_epoch_id,
                (_diagnostic("epoch_invalidated", reason),),
            )


__all__ = [
    "DomainHandle",
    "EpochHandleStore",
    "HandleInternResult",
    "HandleKind",
    "HandleResolution",
    "InvalidationResult",
    "ScopeKind",
]
