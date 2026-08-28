from __future__ import annotations

from dataclasses import replace

from hsx_debugger import *
import hsx_debugger.stack as stack_module
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


class ForeignBindingCallSiteInstructionIndex(IndexDouble):
    def __init__(self, f):
        super().__init__(f)
        self.foreign_binding = replace(f.binding, binding_digest="f" * 64)

    def instruction_at(self, address):
        if address.unsigned_value == 0x120:
            return ResolutionResult(
                ResolutionStatus.RESOLVED,
                self.foreign_binding,
                (self.f.instruction,),
                (),
            )
        return super().instruction_at(address)


class ForeignBindingAnnotationInstructionIndex(IndexDouble):
    def __init__(self, f):
        super().__init__(f)
        self.foreign_binding = replace(f.binding, binding_digest="f" * 64)
        source = SourceLocation(
            SourceRef(
                f.bundle_ref,
                "src/foreign.c",
                ContentDigest("sha256", "5" * 64),
                CanonicalUInt64(16),
            ),
            7,
        )
        self.annotation = replace(
            f.instruction,
            instruction_id="foreign-annotation",
            address=HsxAddress(f.code, 0x100),
            function_id="callee",
            source=source,
        )

    def instruction_at(self, address):
        if address.unsigned_value == 0x100:
            return ResolutionResult(
                ResolutionStatus.RESOLVED,
                self.foreign_binding,
                (self.annotation,),
                (),
            )
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


def test_malformed_call_site_metadata_is_corrupt_and_never_fabricates_caller() -> None:
    f = foundation()
    port = SnapshotPort(f)
    result = unwind(f, index=MalformedCallSiteInstructionIndex(f), port=port)
    assert result.status is InspectionStatus.CORRUPT
    assert len(result.frames) == 1
    assert result.frames[0].pc == HsxAddress(f.code, 0x100)
    assert result.diagnostics[0].code == "call_site_index_contract"
    assert [(address.unsigned_value, length) for address, length in port.memory_reads] == [
        (0x204, 4)
    ]


def test_foreign_binding_call_site_stops_before_proof_and_caller_continuation(
    monkeypatch,
) -> None:
    f = foundation()
    port = SnapshotPort(f)

    def forbidden_proof(*args, **kwargs):
        raise AssertionError("prove_call must not consume foreign-bound instruction evidence")

    monkeypatch.setattr(stack_module, "prove_call", forbidden_proof)
    result = unwind(f, index=ForeignBindingCallSiteInstructionIndex(f), port=port)

    assert result.status is InspectionStatus.ARTIFACT_MISMATCH
    assert len(result.frames) == 1
    assert result.frames[0].pc == HsxAddress(f.code, 0x100)
    assert result.diagnostics[0].code == "call_site_artifact_binding_mismatch"
    assert [(address.unsigned_value, length) for address, length in port.memory_reads] == [
        (0x204, 4)
    ]


def test_foreign_binding_optional_annotation_never_publishes_source() -> None:
    f = foundation()
    result = unwind(f, index=ForeignBindingAnnotationInstructionIndex(f))

    assert result.status is InspectionStatus.COMPLETE
    assert len(result.frames) == 2
    assert result.frames[0].source is None
    assert any(
        diagnostic.code == "instruction_artifact_binding_mismatch"
        for diagnostic in result.frames[0].diagnostics
    )
