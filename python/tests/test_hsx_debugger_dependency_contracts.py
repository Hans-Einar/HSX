from __future__ import annotations

from hsx_debugger import *
from hsx_debugger.inspection import InspectionService
from test_hsx_debugger_inspection import (
    IndexDouble,
    SnapshotPort,
    StaticStack,
    open_session,
    first_frame,
    scope_by_kind,
    foundation,
)


class RaisingLocationIndex(IndexDouble):
    def location_rows(self, symbol_id, function_id, lexical_scope_id, frame_pc):
        raise RuntimeError("injected location index failure")


class WrongLocationRowIndex(IndexDouble):
    def location_rows(self, symbol_id, function_id, lexical_scope_id, frame_pc):
        return ResolutionResult(ResolutionStatus.RESOLVED, self.f.binding, (1,), ())


class RaisingSymbolIndex(IndexDouble):
    def symbol_by_id(self, symbol_id):
        raise RuntimeError("injected symbol index failure")


class WrongSymbolIndex(IndexDouble):
    def symbol_by_id(self, symbol_id):
        return ResolutionResult(ResolutionStatus.RESOLVED, self.f.binding, (1,), ())


class RaisingInstructionIndex(IndexDouble):
    def instruction_at(self, address):
        raise RuntimeError("injected instruction index failure")


class MalformedLocationEvaluator:
    @staticmethod
    def evaluate(*args, **kwargs):
        return object()


def _open_with_location_evaluator(f, index, evaluator):
    port = SnapshotPort(f)
    created = InspectionService.create(
        index,
        port,
        f.architecture,
        f.abi,
        RecipeLimits(),
        StaticStack,
        evaluator,
    )
    assert created.status is ResolutionStatus.RESOLVED
    opened = created.service.open_epoch(f.context, RecipeRequestLimits(64, 16))
    assert opened.status is InspectionOpenStatus.OPENED
    return opened.session


def test_variable_query_classifies_location_index_exception() -> None:
    f = foundation()
    index = RaisingLocationIndex(f)
    _, _, _, _, session = open_session(f, index=index)
    frame = first_frame(session)
    scope = scope_by_kind(session, frame.handle, ScopeKind.LOCALS)

    result = session.variables(scope.handle, PageRequest(0, 16))
    assert result.status is InspectionStatus.CORRUPT
    assert result.value is None
    assert result.diagnostics[0].code == "artifact_index_contract"


def test_variable_query_rejects_non_location_row_resolution_value() -> None:
    f = foundation()
    index = WrongLocationRowIndex(f)
    _, _, _, _, session = open_session(f, index=index)
    frame = first_frame(session)
    scope = scope_by_kind(session, frame.handle, ScopeKind.LOCALS)

    result = session.variables(scope.handle, PageRequest(0, 16))
    assert result.status is InspectionStatus.CORRUPT
    assert result.value is None
    assert result.diagnostics[0].code == "artifact_index_contract"


def test_variable_query_rejects_malformed_location_evaluator_result() -> None:
    f = foundation()
    index = IndexDouble(f)
    session = _open_with_location_evaluator(f, index, MalformedLocationEvaluator)
    frame = first_frame(session)
    scope = scope_by_kind(session, frame.handle, ScopeKind.LOCALS)

    result = session.variables(scope.handle, PageRequest(0, 16))
    assert result.status is InspectionStatus.CORRUPT
    assert result.value is None
    assert result.diagnostics[0].code == "location_evaluator_contract"


def test_snapshot_expression_classifies_symbol_index_exception() -> None:
    f = foundation()
    index = RaisingSymbolIndex(f)
    _, _, _, _, session = open_session(f, index=index)
    frame = first_frame(session)

    result = session.evaluate_snapshot(
        frame.handle,
        SymbolExpression("label"),
    )
    assert result.status is InspectionStatus.CORRUPT
    assert result.value is None
    assert result.diagnostics[0].code == "artifact_index_contract"


def test_snapshot_expression_rejects_non_symbol_resolution_value() -> None:
    f = foundation()
    index = WrongSymbolIndex(f)
    _, _, _, _, session = open_session(f, index=index)
    frame = first_frame(session)

    result = session.evaluate_snapshot(frame.handle, SymbolExpression("label"))
    assert result.status is InspectionStatus.CORRUPT
    assert result.value is None
    assert result.diagnostics[0].code == "artifact_index_contract"


def test_disassembly_keeps_exact_bytes_and_reports_optional_annotation_failure() -> None:
    f = foundation()
    index = RaisingInstructionIndex(f)
    _, _, _, _, session = open_session(f, index=index)

    result = session.disassemble(HsxAddress(f.code, 0x100), 1)
    assert result.status is InspectionStatus.COMPLETE
    assert result.value.instructions[0].encoded == b"\x04\x03\x02\x01"
    assert result.value.instructions[0].instruction is None
    assert any(
        diagnostic.code == "instruction_index_contract"
        for diagnostic in result.diagnostics
    )
