from __future__ import annotations

from hsx_debugger import *
from test_hsx_debugger_inspection import (
    IndexDouble,
    open_session,
    first_frame,
    scope_by_kind,
    foundation,
)


class RaisingLocationIndex(IndexDouble):
    def location_rows(self, symbol_id, function_id, lexical_scope_id, frame_pc):
        raise RuntimeError("injected location index failure")


class RaisingSymbolIndex(IndexDouble):
    def symbol_by_id(self, symbol_id):
        raise RuntimeError("injected symbol index failure")


class RaisingInstructionIndex(IndexDouble):
    def instruction_at(self, address):
        raise RuntimeError("injected instruction index failure")


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
