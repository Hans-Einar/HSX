from __future__ import annotations

from hsx_debugger import *
from test_hsx_debugger_stack import IndexDouble, SnapshotPort, foundation, unwind


class WrongAddressCallIndex(IndexDouble):
    def instruction_at(self, address):
        if address.unsigned_value == 0x120:
            wrong = InstructionRecord(
                "wrong-address-call",
                HsxAddress(self.f.code, 0x124),
                4,
                0x24 << 24,
                "caller",
                None,
                InstructionClassification.USER,
            )
            return ResolutionResult(
                ResolutionStatus.RESOLVED,
                self._binding,
                (wrong,),
                (),
            )
        return super().instruction_at(address)


def test_wrong_address_resolved_call_is_corrupt_before_caller_state_reads() -> None:
    f = foundation()
    port = SnapshotPort(f)

    result = unwind(f, index=WrongAddressCallIndex(f), port=port)

    assert result.status is InspectionStatus.CORRUPT
    assert len(result.frames) == 1
    assert result.frames[0].pc == HsxAddress(f.code, 0x100)
    assert result.diagnostics[0].code == "call_site_index_contract"
    assert "address differs from the checked candidate" in result.diagnostics[0].message

    # Caller PC recovery at CFA-4 is the only caller-side read allowed before the
    # exact call-site metadata fence rejects the mismatched record. Caller SP is
    # pure CFA evidence and saved-R7 recovery at CFA-8 must not run.
    assert [(address.unsigned_value, length) for address, length in port.memory_reads] == [
        (0x204, 4)
    ]


def test_exact_address_resolved_call_still_unwinds_normally() -> None:
    f = foundation()
    port = SnapshotPort(f)

    result = unwind(f, index=IndexDouble(f), port=port)

    assert result.status is InspectionStatus.COMPLETE
    assert len(result.frames) == 2
    assert result.frames[1].pc == HsxAddress(f.code, 0x120)
    assert result.frames[1].call_site_pc == HsxAddress(f.code, 0x120)
    assert result.frames[1].resume_pc == HsxAddress(f.code, 0x124)
