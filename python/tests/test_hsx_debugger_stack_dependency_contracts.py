from __future__ import annotations

from hsx_debugger import *
from test_hsx_debugger_stack import IndexDouble, SnapshotPort, foundation, unwind


class RaisingFunctionsIndex(IndexDouble):
    def functions(self):
        raise RuntimeError("injected functions failure")


class MalformedUnwindQueryIndex(IndexDouble):
    def unwind_rows(self, pc, function_id):
        return object()


class MalformedAnnotationInstructionIndex(IndexDouble):
    def instruction_at(self, address):
        if address.unsigned_value == 0x100:
            return object()
        return super().instruction_at(address)


class MalformedCallSiteInstructionIndex(IndexDouble):
    def instruction_at(self, address):
        if address.unsigned_value == 0x120:
            return object()
        return super().instruction_at(address)


def test_function_index_exception_is_corrupt_and_never_relaxes_row_selection() -> None:
    f = foundation()
    port = SnapshotPort(f)
    result = unwind(f, index=RaisingFunctionsIndex(f), port=port)
    assert result.status is InspectionStatus.CORRUPT
    assert result.frames == ()
    assert result.diagnostics[0].code == "function_index_contract"
    assert port.register_reads == 1
    assert port.memory_reads == []


def test_malformed_unwind_query_result_is_corrupt_not_python_exception() -> None:
    f = foundation()
    port = SnapshotPort(f)
    result = unwind(f, index=MalformedUnwindQueryIndex(f), port=port)
    assert result.status is InspectionStatus.CORRUPT
    assert result.frames == ()
    assert result.diagnostics[0].code == "unwind_index_contract"
    assert port.register_reads == 1
    assert port.memory_reads == []


def test_malformed_optional_instruction_annotation_does_not_destroy_proven_frame() -> None:
    f = foundation()
    result = unwind(f, index=MalformedAnnotationInstructionIndex(f))
    assert result.status is InspectionStatus.COMPLETE
    assert len(result.frames) == 2
    assert any(
        diagnostic.code == "instruction_index_contract"
        for diagnostic in result.frames[0].diagnostics
    )


def test_malformed_call_site_metadata_is_diagnostic_and_resume_pc_remains_authoritative() -> None:
    f = foundation()
    result = unwind(f, index=MalformedCallSiteInstructionIndex(f))
    assert result.status is InspectionStatus.COMPLETE
    assert len(result.frames) == 2
    caller = result.frames[1]
    assert caller.resume_pc == HsxAddress(f.code, 0x124)
    assert caller.call_site_pc is None
    assert caller.pc == HsxAddress(f.code, 0x124)
    assert any(
        diagnostic.code == "call_site_index_contract"
        for diagnostic in caller.diagnostics
    )
