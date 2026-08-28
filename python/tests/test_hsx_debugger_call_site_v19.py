from __future__ import annotations

from dataclasses import replace

from hsx_debugger import *
from test_hsx_debugger_stack import IndexDouble, SnapshotPort, foundation


def _instruction(f, *, encoded_word=(0x24 << 24), byte_size=4):
    return InstructionRecord(
        "call-site",
        HsxAddress(f.code, 0x120),
        byte_size,
        encoded_word,
        "caller",
        None,
        InstructionClassification.USER,
    )


def _run(f, instruction, *, architecture=None, rows=None):
    index = IndexDouble(
        f,
        rows=rows,
        instructions={} if instruction is None else {0x120: instruction},
    )
    port = SnapshotPort(f)
    result = StackService.unwind(
        f.context,
        index,
        port,
        architecture or f.architecture,
        f.abi,
        RecipeLimits(),
        RecipeRequestLimits(64, 16),
    )
    return result, port


def test_proven_call_uses_checked_call_site_for_caller_row_selection_and_keeps_resume_separate() -> None:
    f = foundation()
    # Half-open [0x120,0x124) contains the CALL but explicitly excludes resume_pc 0x124.
    # A regression to legacy resume-PC lookup therefore cannot select this terminal row.
    terminal_at_call = replace(
        f.terminal,
        pc_range=HsxAddressRange(HsxAddress(f.code, 0x120), 4),
    )
    result, _ = _run(f, _instruction(f), rows=(f.body, terminal_at_call))
    assert result.status is InspectionStatus.COMPLETE
    assert len(result.frames) == 2
    top, caller = result.frames
    assert top.pc == HsxAddress(f.code, 0x100)
    assert caller.pc == HsxAddress(f.code, 0x120)
    assert caller.resume_pc == HsxAddress(f.code, 0x124)
    assert caller.call_site_pc == HsxAddress(f.code, 0x120)
    assert caller.terminal is True


def test_missing_encoded_semantics_stops_with_partial_prefix_and_never_uses_resume_as_pc() -> None:
    f = foundation()
    result, port = _run(f, _instruction(f, encoded_word=None))
    assert result.status is InspectionStatus.PARTIAL
    assert len(result.frames) == 1
    assert result.frames[0].pc == HsxAddress(f.code, 0x100)
    assert result.diagnostics[0].code == "instruction_semantics_unavailable"
    # Caller PC requires one dereference. Caller SP/R7 recovery must not continue after
    # semantic proof fails, so no CFA-8 saved-R7 dereference is permitted.
    assert [(address.unsigned_value, length) for address, length in port.memory_reads] == [
        (0x204, 4)
    ]


def test_proven_non_call_is_corrupt_and_preserves_only_trustworthy_prefix() -> None:
    f = foundation()
    result, port = _run(f, _instruction(f, encoded_word=(0x04 << 24)))
    assert result.status is InspectionStatus.CORRUPT
    assert len(result.frames) == 1
    assert result.diagnostics[0].code == "call_site_not_call"
    assert [(address.unsigned_value, length) for address, length in port.memory_reads] == [
        (0x204, 4)
    ]


def test_unsupported_instruction_encoding_stops_unsupported_without_resume_fallback() -> None:
    f = foundation()
    architecture = replace(f.architecture, instruction_encoding="future.variable/2")
    result, port = _run(f, _instruction(f), architecture=architecture)
    assert result.status is InspectionStatus.UNSUPPORTED
    assert len(result.frames) == 1
    assert result.diagnostics[0].code == "instruction_encoding_unsupported"
    assert [(address.unsigned_value, length) for address, length in port.memory_reads] == [
        (0x204, 4)
    ]


def test_missing_instruction_record_stops_partial_without_fabricated_caller() -> None:
    f = foundation()
    result, port = _run(f, None)
    assert result.status is InspectionStatus.PARTIAL
    assert len(result.frames) == 1
    assert result.frames[0].resume_pc is None
    assert result.diagnostics[0].code in {
        "instruction_unavailable",
        "call_site_unavailable",
    }
    assert [(address.unsigned_value, length) for address, length in port.memory_reads] == [
        (0x204, 4)
    ]


def test_malformed_fixed32_instruction_record_stops_corrupt() -> None:
    f = foundation()
    result, _ = _run(f, _instruction(f, encoded_word=0x2400, byte_size=2))
    assert result.status is InspectionStatus.CORRUPT
    assert len(result.frames) == 1
    assert result.diagnostics[0].code == "instruction_encoding_contract"
