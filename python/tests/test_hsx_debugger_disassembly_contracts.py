from __future__ import annotations

from hsx_debugger import *
from test_hsx_debugger_inspection import SnapshotPort, foundation, open_session


class ShortInstructionPort(SnapshotPort):
    def read_disassembly(self, context, address, instruction_count):
        self.disassembly_reads += 1
        return InspectionResult(
            InspectionStatus.COMPLETE,
            context,
            (InstructionBytes(address, b"\x01\x02"),),
            (),
        )


def test_snapshot_instruction_byte_size_metadata_mismatch_is_typed_corrupt() -> None:
    f = foundation()
    port = ShortInstructionPort(f)
    _, _, _, _, session = open_session(f, port)

    result = session.disassemble(HsxAddress(f.code, 0x100), 1)
    assert result.status is InspectionStatus.CORRUPT
    assert result.value is None
    assert result.diagnostics[0].code == "disassembly_metadata_mismatch"
    assert port.disassembly_reads == 1
