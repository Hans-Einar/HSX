from __future__ import annotations

from dataclasses import replace

import pytest

from hsx_debugger import *
from hsx_debugger.artifacts import DebugArtifactIndex
from hsx_debugger.inspection import InspectionService
from hsx_debugger.stack import StackService
from test_hsx_debugger_inspection import IndexDouble as InspectionIndex, SnapshotPort as InspectionPort, StaticStack, foundation as inspection_foundation
from test_hsx_debugger_stack import IndexDouble as StackIndex, SnapshotPort as StackPort, foundation as stack_foundation


def test_stack_requires_register_read_set_before_touching_snapshot_port() -> None:
    f = stack_foundation()
    snapshot = replace(
        f.context.epoch.snapshot,
        supported_read_sets=frozenset({"memory", "disassembly"}),
    )
    context = replace(f.context, epoch=replace(f.context.epoch, snapshot=snapshot))
    f.context = context
    port = StackPort(f)
    result = StackService.unwind(
        context, StackIndex(f), port, f.architecture, f.abi,
        RecipeLimits(), RecipeRequestLimits(64, 16)
    )
    assert result.status is InspectionStatus.UNAVAILABLE
    assert result.frames == ()
    assert result.diagnostics[0].code == "snapshot_read_set_unavailable"
    assert port.register_reads == 0


def test_inspection_rejects_unknown_register_selection_before_port_io() -> None:
    f = inspection_foundation()
    port = InspectionPort(f)
    created = InspectionService.create(
        InspectionIndex(f), port, f.architecture, f.abi,
        RecipeLimits(), StaticStack, LocationEvaluator
    )
    session = created.service.open_epoch(
        f.context, RecipeRequestLimits(64, 16)
    ).session
    result = session.registers(RegisterSelection(False, ("RX",)))
    assert result.status is InspectionStatus.CORRUPT
    assert result.diagnostics[0].code == "register_selection_invalid"
    assert port.register_reads == 0


def test_checked_call_site_without_instruction_evidence_stops_before_caller_frame() -> None:
    f = stack_foundation()
    result = StackService.unwind(
        f.context,
        StackIndex(f, instructions={}),
        StackPort(f),
        f.architecture,
        f.abi,
        RecipeLimits(),
        RecipeRequestLimits(64, 16),
    )
    assert result.status is InspectionStatus.PARTIAL
    assert len(result.frames) == 1
    assert result.frames[0].pc == HsxAddress(f.code, 0x100)
    assert result.diagnostics[0].code in {"instruction_unavailable", "call_site_unavailable"}


def test_location_validator_type_error_names_location_row() -> None:
    f = inspection_foundation()
    with pytest.raises(TypeError, match="row must be LocationRow"):
        RecipeComponentValidator.validate_location_row(
            object(), f.local, f.architecture, f.abi
        )


def test_exact_symbol_id_query_is_present_on_real_artifact_index() -> None:
    assert hasattr(DebugArtifactIndex, "symbol_by_id")
    assert callable(getattr(DebugArtifactIndex, "symbol_by_id", None))
