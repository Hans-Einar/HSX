"""The pure RF-004 snapshot-read port and exact result fencing helpers."""

from __future__ import annotations

from typing import Protocol, TypeVar, runtime_checkable

from .addresses import HsxAddress
from .identity import InspectionContext
from .results import (
    Diagnostic,
    InspectionResult,
    InspectionStatus,
    InstructionBytes,
    MemoryBlock,
    RegisterSelection,
    RegisterSet,
)


T = TypeVar("T")
_READ_SETS = frozenset({"registers", "memory", "disassembly", "stack", "resources"})


@runtime_checkable
class SnapshotReadPort(Protocol):
    """Frontend-neutral immutable/revision-fenced snapshot read boundary."""

    def read_registers(
        self, context: InspectionContext, selection: RegisterSelection
    ) -> InspectionResult[RegisterSet]: ...

    def read_memory(
        self, context: InspectionContext, address: HsxAddress, byte_length: int
    ) -> InspectionResult[MemoryBlock]: ...

    def read_disassembly(
        self, context: InspectionContext, address: HsxAddress, instruction_count: int
    ) -> InspectionResult[tuple[InstructionBytes, ...]]: ...


def fence_snapshot_result(
    expected_context: InspectionContext,
    result: InspectionResult[T],
) -> InspectionResult[T]:
    """Reject a late/mixed result instead of merging it into ``expected_context``."""

    if not isinstance(expected_context, InspectionContext):
        raise TypeError("expected_context must be InspectionContext")
    if not isinstance(result, InspectionResult):
        raise TypeError("result must be InspectionResult")
    if result.context == expected_context:
        return result
    return InspectionResult(
        status=InspectionStatus.STALE,
        context=expected_context,
        value=None,
        diagnostics=(
            Diagnostic(
                "snapshot_context_stale",
                "snapshot result does not match the complete requested inspection context",
                component="snapshot",
            ),
        ),
    )


def require_snapshot_read_set(
    context: InspectionContext,
    read_set: str,
) -> InspectionResult[bool]:
    """Fence one read against the snapshot's exact advertised coverage."""

    if not isinstance(context, InspectionContext):
        raise TypeError("context must be InspectionContext")
    if not isinstance(read_set, str) or not read_set:
        raise ValueError("read_set must be a non-empty string")
    if read_set not in _READ_SETS:
        raise ValueError("read_set must be one of the frozen snapshot read-set names")
    if read_set in context.epoch.snapshot.supported_read_sets:
        return InspectionResult(InspectionStatus.COMPLETE, context, True, ())
    return InspectionResult(
        InspectionStatus.UNAVAILABLE,
        context,
        None,
        (
            Diagnostic(
                "snapshot_read_set_unavailable",
                f"snapshot does not advertise the {read_set!r} read set",
                component="snapshot",
            ),
        ),
    )


__all__ = [
    "SnapshotReadPort",
    "fence_snapshot_result",
    "require_snapshot_read_set",
]
