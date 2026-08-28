from __future__ import annotations

from dataclasses import replace

from hsx_debugger import *
from test_hsx_debugger_inspection import IndexDouble, SnapshotPort, foundation, open_session


class ShortInstructionPort(SnapshotPort):
    def read_disassembly(self, context, address, instruction_count):
        self.disassembly_reads += 1
        return InspectionResult(
            InspectionStatus.COMPLETE,
            context,
            (InstructionBytes(address, b"\x01\x02"),),
            (),
        )


class EmptyCompleteInstructionPort(SnapshotPort):
    def read_disassembly(self, context, address, instruction_count):
        self.disassembly_reads += 1
        return InspectionResult(InspectionStatus.COMPLETE, context, (), ())


class PartialInstructionPort(SnapshotPort):
    def read_disassembly(self, context, address, instruction_count):
        self.disassembly_reads += 1
        return InspectionResult(
            InspectionStatus.PARTIAL,
            context,
            (InstructionBytes(address, b"\x04\x03\x02\x01"),),
            (Diagnostic("instruction_tail_unavailable", "missing", component="test"),),
        )


class ForeignBindingInstructionIndex(IndexDouble):
    def __init__(self, f):
        super().__init__(f)
        self.foreign_binding = replace(f.binding, binding_digest="f" * 64)

    def instruction_at(self, address):
        resolved = super().instruction_at(address)
        if resolved.status is ResolutionStatus.RESOLVED:
            return ResolutionResult(
                ResolutionStatus.RESOLVED,
                self.foreign_binding,
                resolved.values,
                (),
            )
        return resolved


def test_snapshot_instruction_byte_size_metadata_mismatch_is_typed_corrupt() -> None:
    f = foundation()
    port = ShortInstructionPort(f)
    _, _, _, _, session = open_session(f, port)

    result = session.disassemble(HsxAddress(f.code, 0x100), 1)
    assert result.status is InspectionStatus.CORRUPT
    assert result.value is None
    assert result.diagnostics[0].code == "disassembly_metadata_mismatch"
    assert port.disassembly_reads == 1


def test_complete_disassembly_requires_exact_requested_instruction_count() -> None:
    f = foundation()
    port = EmptyCompleteInstructionPort(f)
    _, _, _, _, session = open_session(f, port)

    result = session.disassemble(HsxAddress(f.code, 0x104), 1)

    assert result.status is InspectionStatus.CORRUPT
    assert result.value is None
    assert result.diagnostics[0].code == "snapshot_disassembly_count_mismatch"
    assert port.disassembly_reads == 1


def test_complete_exact_count_and_partial_prefix_behavior_remain_unchanged() -> None:
    f = foundation()
    complete_port = SnapshotPort(f)
    _, _, _, _, complete_session = open_session(f, complete_port)
    complete = complete_session.disassemble(HsxAddress(f.code, 0x100), 1)

    partial_port = PartialInstructionPort(f)
    _, _, _, _, partial_session = open_session(f, partial_port)
    partial = partial_session.disassemble(HsxAddress(f.code, 0x100), 2)

    assert complete.status is InspectionStatus.COMPLETE
    assert len(complete.value.instructions) == 1
    assert complete.value.instructions[0].encoded == b"\x04\x03\x02\x01"
    assert partial.status is InspectionStatus.PARTIAL
    assert len(partial.value.instructions) == 1
    assert partial.diagnostics[0].code == "instruction_tail_unavailable"


def test_foreign_binding_metadata_is_omitted_while_snapshot_bytes_are_preserved() -> None:
    f = foundation()
    index = ForeignBindingInstructionIndex(f)
    _, _, _, _, session = open_session(f, index=index)

    result = session.disassemble(HsxAddress(f.code, 0x100), 1)

    assert result.status is InspectionStatus.COMPLETE
    assert result.value.instructions[0].encoded == b"\x04\x03\x02\x01"
    assert result.value.instructions[0].instruction is None
    assert any(
        diagnostic.code == "instruction_artifact_binding_mismatch"
        for diagnostic in result.diagnostics
    )
