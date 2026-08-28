from __future__ import annotations

from hsx_debugger import *
from test_hsx_debugger_inspection import SnapshotPort, first_frame, open_session, scope_by_kind


class PartialMemoryPort(SnapshotPort):
    def read_memory(self, context, address, byte_length):
        self.memory_reads += 1
        if address.unsigned_value == 0x300 and byte_length == 4:
            block = MemoryBlock(
                address,
                4,
                (
                    MemorySegment(0, 2, b"\x78\x56", MemorySegmentStatus.COMPLETE),
                    MemorySegment(2, 2, b"", MemorySegmentStatus.UNAVAILABLE),
                ),
            )
            return InspectionResult(
                InspectionStatus.PARTIAL,
                context,
                block,
                (Diagnostic("memory_tail_unavailable", "last two bytes unavailable", component="test"),),
            )
        return super().read_memory(context, address, byte_length)


class PartialDisassemblyPort(SnapshotPort):
    def read_disassembly(self, context, address, instruction_count):
        self.disassembly_reads += 1
        values = self.disassembly_values.get(address.unsigned_value, ())[:1]
        return InspectionResult(
            InspectionStatus.PARTIAL,
            context,
            tuple(values),
            (Diagnostic("instruction_tail_unavailable", "later instruction unavailable", component="test"),),
        )


def test_register_variable_paging_is_exact_and_reuses_handles_across_query_order() -> None:
    _, _, _, _, session = open_session()
    frame = first_frame(session)
    scope = scope_by_kind(session, frame.handle, ScopeKind.REGISTERS)

    middle = session.variables(scope.handle, PageRequest(2, 2))
    tail = session.variables(scope.handle, PageRequest(5, 8))
    head = session.variables(scope.handle, PageRequest(0, 2))
    full = session.variables(scope.handle, PageRequest(0, 32))
    empty = session.variables(scope.handle, PageRequest(6, 8))

    assert middle.status is tail.status is head.status is full.status is empty.status is InspectionStatus.COMPLETE
    assert middle.value.total_variables == tail.value.total_variables == head.value.total_variables == full.value.total_variables == empty.value.total_variables == 6
    assert [item.register_id for item in middle.value.variables] == ["R7", "PC"]
    assert [item.register_id for item in tail.value.variables] == ["PSW"]
    assert [item.register_id for item in head.value.variables] == ["R0", "R1"]
    assert empty.value.variables == ()

    by_id = {item.register_id: item.handle for item in full.value.variables}
    for page in (middle, tail, head):
        for item in page.value.variables:
            assert item.handle == by_id[item.register_id]


def test_partial_memory_preserves_exact_segments_and_memory_expression_fails_closed() -> None:
    f, _, _, _, session = open_session(port=None)
    # Re-open with an explicit partial port so both calls share one exact session/context.
    port = PartialMemoryPort(f)
    _, _, _, _, session = open_session(f, port)

    result = session.memory(HsxAddress(f.data, 0x300), 4)
    assert result.status is InspectionStatus.PARTIAL
    assert result.value.requested_length == 4
    assert [(segment.offset, segment.requested_length, segment.data, segment.status) for segment in result.value.segments] == [
        (0, 2, b"\x78\x56", MemorySegmentStatus.COMPLETE),
        (2, 2, b"", MemorySegmentStatus.UNAVAILABLE),
    ]
    assert result.diagnostics[0].code == "memory_tail_unavailable"

    frame = first_frame(session)
    expression = session.evaluate_snapshot(
        frame.handle,
        MemoryExpression(HsxAddress(f.data, 0x300), 32, ByteOrder.LITTLE),
    )
    assert expression.status is InspectionStatus.UNAVAILABLE
    assert expression.value is None
    assert expression.diagnostics[0].code == "memory_expression_unavailable"


def test_partial_disassembly_preserves_proven_instruction_prefix_and_diagnostic() -> None:
    f, _, _, _, _ = open_session()
    port = PartialDisassemblyPort(f)
    _, _, _, _, session = open_session(f, port)

    result = session.disassemble(HsxAddress(f.code, 0x100), 2)
    assert result.status is InspectionStatus.PARTIAL
    assert result.value.start == HsxAddress(f.code, 0x100)
    assert result.value.requested_count == 2
    assert len(result.value.instructions) == 1
    assert result.value.instructions[0].encoded == b"\x04\x03\x02\x01"
    assert result.diagnostics[0].code == "instruction_tail_unavailable"


def test_invalid_memory_and_disassembly_ranges_fail_before_snapshot_port_io() -> None:
    f, _, port, _, session = open_session()
    bad_space = HsxAddress(AddressSpaceId("other"), 0)

    memory = session.memory(bad_space, 2)
    disassembly = session.disassemble(HsxAddress(f.data, 0x100), 1)

    assert memory.status is InspectionStatus.CORRUPT
    assert disassembly.status is InspectionStatus.CORRUPT
    assert port.memory_reads == 0
    assert port.disassembly_reads == 0
