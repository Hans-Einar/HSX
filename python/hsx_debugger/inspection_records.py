"""Immutable public inspection records and dedicated epoch-reference result envelopes.

This module owns data shapes only. It performs no artifact lookup, snapshot I/O, stack walk,
epoch mutation, handle allocation, runtime RPC or frontend mapping.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TypeAlias

from .handles import DomainHandle, HandleKind, ScopeKind
from .identity import InspectionContext
from .recipes import UnwindFrame
from .results import (
    Diagnostic,
    EvaluatedValue,
    ExpressionKind,
    ExpressionValue,
    InspectionStatus,
)
from .stack import STACK_RESULT_STATUSES


_SCOPE_ORDER = {
    ScopeKind.REGISTERS: 0,
    ScopeKind.LOCALS: 1,
    ScopeKind.GLOBALS: 2,
}


def _diagnostics(value) -> tuple[Diagnostic, ...]:
    items = tuple(value)
    if not all(isinstance(item, Diagnostic) for item in items):
        raise TypeError("diagnostics must contain Diagnostic values")
    return items


def _require_nonnegative(value: int, field_name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{field_name} must be an integer >= 0")


@dataclass(frozen=True, slots=True)
class FrameRecord:
    context: InspectionContext
    handle: DomainHandle
    unwind: UnwindFrame

    def __post_init__(self) -> None:
        if not isinstance(self.context, InspectionContext):
            raise TypeError("context must be InspectionContext")
        if not isinstance(self.handle, DomainHandle) or self.handle.kind is not HandleKind.FRAME:
            raise TypeError("handle must be a FRAME DomainHandle")
        if not isinstance(self.unwind, UnwindFrame):
            raise TypeError("unwind must be UnwindFrame")
        if self.handle.context != self.context or self.unwind.context != self.context:
            raise ValueError("frame record evidence must share one exact context")


@dataclass(frozen=True, slots=True)
class FramePage:
    total_frames: int
    offset: int
    frames: tuple[FrameRecord, ...]

    def __post_init__(self) -> None:
        _require_nonnegative(self.total_frames, "total_frames")
        _require_nonnegative(self.offset, "offset")
        frames = tuple(self.frames)
        if not all(isinstance(item, FrameRecord) for item in frames):
            raise TypeError("frames must contain FrameRecord values")
        if len(frames) > self.total_frames:
            raise ValueError("paged frames cannot exceed total_frames")
        if frames:
            indices = tuple(item.unwind.frame_index for item in frames)
            if self.offset >= self.total_frames or indices[0] != self.offset:
                raise ValueError("non-empty frame page must start at the requested offset")
            if indices != tuple(range(self.offset, self.offset + len(frames))):
                raise ValueError("paged frame indices must be contiguous")
            if indices[-1] >= self.total_frames:
                raise ValueError("paged frame index exceeds total_frames")
        object.__setattr__(self, "frames", frames)


@dataclass(frozen=True, slots=True)
class StackPageResult:
    """Exact stack termination plus a paged handle view of the proven prefix."""

    status: InspectionStatus
    context: InspectionContext
    page: FramePage
    diagnostics: tuple[Diagnostic, ...] = ()

    def __post_init__(self) -> None:
        if type(self.status) is not InspectionStatus or self.status not in STACK_RESULT_STATUSES:
            raise ValueError("status must be one frozen stack-result InspectionStatus")
        if not isinstance(self.context, InspectionContext):
            raise TypeError("context must be InspectionContext")
        if not isinstance(self.page, FramePage):
            raise TypeError("page must be FramePage")
        diagnostics = _diagnostics(self.diagnostics)
        if any(record.context != self.context for record in self.page.frames):
            raise ValueError("every paged frame must retain the exact result context")
        if self.status is InspectionStatus.COMPLETE:
            if self.page.total_frames < 1 or diagnostics:
                raise ValueError("COMPLETE stack page requires a proven prefix and no terminating diagnostic")
        elif self.status is InspectionStatus.PARTIAL:
            if self.page.total_frames < 1 or not diagnostics:
                raise ValueError("PARTIAL stack page requires a proven prefix and diagnostic")
        elif self.status is InspectionStatus.UNAVAILABLE:
            if self.page.total_frames != 0 or not diagnostics:
                raise ValueError("UNAVAILABLE stack page requires no proven frame and a diagnostic")
        elif not diagnostics:
            raise ValueError("terminating stack page failures require diagnostics")
        object.__setattr__(self, "diagnostics", diagnostics)


@dataclass(frozen=True, slots=True)
class ScopeRecord:
    context: InspectionContext
    handle: DomainHandle
    frame_handle: DomainHandle
    kind: ScopeKind
    name: str
    expensive: bool

    def __post_init__(self) -> None:
        if not isinstance(self.context, InspectionContext):
            raise TypeError("context must be InspectionContext")
        if not isinstance(self.handle, DomainHandle) or self.handle.kind is not HandleKind.SCOPE:
            raise TypeError("handle must be a SCOPE DomainHandle")
        if not isinstance(self.frame_handle, DomainHandle) or self.frame_handle.kind is not HandleKind.FRAME:
            raise TypeError("frame_handle must be a FRAME DomainHandle")
        if type(self.kind) is not ScopeKind:
            raise TypeError("kind must be ScopeKind")
        if not isinstance(self.name, str) or not self.name:
            raise ValueError("name must be non-empty")
        if not isinstance(self.expensive, bool):
            raise TypeError("expensive must be bool")
        if self.handle.context != self.context or self.frame_handle.context != self.context:
            raise ValueError("scope handles must share the record context")


@dataclass(frozen=True, slots=True)
class ScopeSet:
    frame_handle: DomainHandle
    scopes: tuple[ScopeRecord, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.frame_handle, DomainHandle) or self.frame_handle.kind is not HandleKind.FRAME:
            raise TypeError("frame_handle must be a FRAME DomainHandle")
        scopes = tuple(self.scopes)
        if not all(isinstance(item, ScopeRecord) for item in scopes):
            raise TypeError("scopes must contain ScopeRecord values")
        if any(item.frame_handle != self.frame_handle for item in scopes):
            raise ValueError("scope set must reference one frame handle")
        if any(item.context != self.frame_handle.context for item in scopes):
            raise ValueError("scope set must retain one exact context")
        kinds = tuple(item.kind for item in scopes)
        if len(set(kinds)) != len(kinds):
            raise ValueError("scope kinds must be unique")
        if kinds != tuple(sorted(kinds, key=_SCOPE_ORDER.__getitem__)):
            raise ValueError("scope kinds must follow Registers/Locals/Globals order")
        object.__setattr__(self, "scopes", scopes)


@dataclass(frozen=True, slots=True)
class ScopeQueryResult:
    """Dedicated 1.7 envelope for ScopeSet values carrying epoch-bound handles."""

    status: InspectionStatus
    context: InspectionContext
    value: ScopeSet | None
    diagnostics: tuple[Diagnostic, ...] = ()

    def __post_init__(self) -> None:
        if type(self.status) is not InspectionStatus:
            raise TypeError("status must be InspectionStatus")
        if not isinstance(self.context, InspectionContext):
            raise TypeError("context must be InspectionContext")
        diagnostics = _diagnostics(self.diagnostics)
        object.__setattr__(self, "diagnostics", diagnostics)
        if self.status is InspectionStatus.COMPLETE:
            if not isinstance(self.value, ScopeSet) or diagnostics:
                raise ValueError("COMPLETE requires ScopeSet and no diagnostics")
        elif self.status is InspectionStatus.PARTIAL:
            if not isinstance(self.value, ScopeSet) or not diagnostics:
                raise ValueError("PARTIAL requires ScopeSet and diagnostics")
        else:
            if self.value is not None or not diagnostics:
                raise ValueError("failed scope query requires no value and diagnostics")
        if self.value is not None and self.value.frame_handle.context != self.context:
            raise ValueError("ScopeSet must retain exact result context")


@dataclass(frozen=True, slots=True)
class SymbolVariableRecord:
    context: InspectionContext
    handle: DomainHandle
    scope_handle: DomainHandle
    symbol_id: str
    declaration_order: int
    evaluated: EvaluatedValue

    def __post_init__(self) -> None:
        if not isinstance(self.context, InspectionContext):
            raise TypeError("context must be InspectionContext")
        if not isinstance(self.handle, DomainHandle) or self.handle.kind is not HandleKind.VARIABLE:
            raise TypeError("handle must be a VARIABLE DomainHandle")
        if not isinstance(self.scope_handle, DomainHandle) or self.scope_handle.kind is not HandleKind.SCOPE:
            raise TypeError("scope_handle must be a SCOPE DomainHandle")
        if not isinstance(self.symbol_id, str) or not self.symbol_id:
            raise ValueError("symbol_id must be non-empty")
        _require_nonnegative(self.declaration_order, "declaration_order")
        if not isinstance(self.evaluated, EvaluatedValue):
            raise TypeError("evaluated must be EvaluatedValue")
        if self.evaluated.symbol_id != self.symbol_id:
            raise ValueError("evaluated symbol_id must equal record symbol_id")
        if self.handle.context != self.context or self.scope_handle.context != self.context:
            raise ValueError("variable handles must share one context")


@dataclass(frozen=True, slots=True)
class RegisterVariableRecord:
    context: InspectionContext
    handle: DomainHandle
    scope_handle: DomainHandle
    register_id: str
    register_order: int
    evaluated: ExpressionValue

    def __post_init__(self) -> None:
        if not isinstance(self.context, InspectionContext):
            raise TypeError("context must be InspectionContext")
        if not isinstance(self.handle, DomainHandle) or self.handle.kind is not HandleKind.VARIABLE:
            raise TypeError("handle must be a VARIABLE DomainHandle")
        if not isinstance(self.scope_handle, DomainHandle) or self.scope_handle.kind is not HandleKind.SCOPE:
            raise TypeError("scope_handle must be a SCOPE DomainHandle")
        if not isinstance(self.register_id, str) or not self.register_id:
            raise ValueError("register_id must be non-empty")
        _require_nonnegative(self.register_order, "register_order")
        if not isinstance(self.evaluated, ExpressionValue):
            raise TypeError("evaluated must be ExpressionValue")
        if self.evaluated.expression_kind is not ExpressionKind.REGISTER or self.evaluated.source_id != self.register_id:
            raise ValueError("evaluated register identity differs")
        if self.handle.context != self.context or self.scope_handle.context != self.context:
            raise ValueError("variable handles must share one context")


ScopeValueRecord: TypeAlias = SymbolVariableRecord | RegisterVariableRecord


@dataclass(frozen=True, slots=True)
class VariablePage:
    scope_handle: DomainHandle
    total_variables: int
    offset: int
    variables: tuple[ScopeValueRecord, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.scope_handle, DomainHandle) or self.scope_handle.kind is not HandleKind.SCOPE:
            raise TypeError("scope_handle must be a SCOPE DomainHandle")
        _require_nonnegative(self.total_variables, "total_variables")
        _require_nonnegative(self.offset, "offset")
        variables = tuple(self.variables)
        if not all(isinstance(item, (SymbolVariableRecord, RegisterVariableRecord)) for item in variables):
            raise TypeError("variables must contain ScopeValueRecord values")
        if len(variables) > self.total_variables:
            raise ValueError("paged variables cannot exceed total_variables")
        if any(item.scope_handle != self.scope_handle for item in variables):
            raise ValueError("variable page must retain one exact scope handle")
        if any(item.context != self.scope_handle.context for item in variables):
            raise ValueError("variable page must retain one exact context")
        handles = tuple(item.handle for item in variables)
        if len(set(handles)) != len(handles):
            raise ValueError("paged variable handles must be unique")
        object.__setattr__(self, "variables", variables)


@dataclass(frozen=True, slots=True)
class VariableQueryResult:
    """Dedicated 1.7 envelope for VariablePage values carrying epoch-bound handles."""

    status: InspectionStatus
    context: InspectionContext
    value: VariablePage | None
    diagnostics: tuple[Diagnostic, ...] = ()

    def __post_init__(self) -> None:
        if type(self.status) is not InspectionStatus:
            raise TypeError("status must be InspectionStatus")
        if not isinstance(self.context, InspectionContext):
            raise TypeError("context must be InspectionContext")
        diagnostics = _diagnostics(self.diagnostics)
        object.__setattr__(self, "diagnostics", diagnostics)
        if self.status is InspectionStatus.COMPLETE:
            if not isinstance(self.value, VariablePage) or diagnostics:
                raise ValueError("COMPLETE requires VariablePage and no diagnostics")
        elif self.status is InspectionStatus.PARTIAL:
            if not isinstance(self.value, VariablePage) or not diagnostics:
                raise ValueError("PARTIAL requires VariablePage and diagnostics")
        else:
            if self.value is not None or not diagnostics:
                raise ValueError("failed variable query requires no value and diagnostics")
        if self.value is not None and self.value.scope_handle.context != self.context:
            raise ValueError("VariablePage must retain exact result context")


__all__ = [
    "FramePage",
    "FrameRecord",
    "RegisterVariableRecord",
    "ScopeQueryResult",
    "ScopeRecord",
    "ScopeSet",
    "ScopeValueRecord",
    "StackPageResult",
    "SymbolVariableRecord",
    "VariablePage",
    "VariableQueryResult",
]
