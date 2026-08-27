from __future__ import annotations

from dataclasses import replace

from hsx_debugger import *
from test_hsx_debugger_stack import IndexDouble, SnapshotPort, foundation, rvalue, unwind


def _expr(f, role, operations, result=RecipeResultKind.ADDRESS, width=None):
    return f.expr(role, tuple(operations), result, width)


def _caller_pc_rule(f):
    return RecipeRule(
        RecipeRuleKind.EXPRESSION,
        _expr(
            f,
            RecipeRole.CALLER_PC,
            (
                CfaOp("cfa"),
                AddSConstCheckedOp("add_sconst_checked", -4),
                DerefUOp("deref_u", 4, ByteOrder.LITTLE),
                ToAddressOp("to_address", f.code),
            ),
        ),
        None,
    )


def _caller_sp_rule(f):
    return RecipeRule(
        RecipeRuleKind.EXPRESSION,
        _expr(f, RecipeRole.CALLER_SP, (CfaOp("cfa"),)),
        None,
    )


def _saved_r7_rule(f):
    return RecipeRule(
        RecipeRuleKind.EXPRESSION,
        _expr(
            f,
            RecipeRole.REGISTER,
            (
                CfaOp("cfa"),
                AddSConstCheckedOp("add_sconst_checked", -8),
                DerefUOp("deref_u", 4, ByteOrder.LITTLE),
            ),
            RecipeResultKind.UNSIGNED_SCALAR,
            32,
        ),
        None,
    )


def _phase_row(f, row_id, boundary, cfa_ops, r7_rule):
    return UnwindRow(
        row_id,
        f.binding,
        HsxAddressRange(HsxAddress(f.code, 0x100), 4),
        f.abi,
        f.schema,
        _expr(f, RecipeRole.CFA, cfa_ops),
        _caller_pc_rule(f),
        _caller_sp_rule(f),
        None,
        (("R7", r7_rule),),
        boundary,
        -4,
    )


def _registers(f, *, sp, r7):
    return RegisterSet(
        (
            RegisterValue("R0", 32, 1, True),
            RegisterValue("R1", 32, 2, True),
            RegisterValue("R7", 32, r7, r7 is not None),
            RegisterValue("PC", 16, 0x100, True),
            RegisterValue("SP", 16, sp, True),
            RegisterValue("PSW", 8, 0xA5, True),
        )
    )


def _run_phase(f, row, *, sp, r7, memory):
    port = SnapshotPort(f, registers=_registers(f, sp=sp, r7=r7), memory=memory)
    result = unwind(f, index=IndexDouble(f, rows=(row, f.terminal)), port=port)
    return result, port


def test_entry_before_push_uses_sp_row_and_never_treats_caller_r7_as_current_frame_base() -> None:
    f = foundation()
    row = _phase_row(
        f,
        "entry-before-push",
        UnwindBoundary.ENTRY,
        (
            SpecialValueOp("special_value", RecipeSpecial.SP),
            AddSConstCheckedOp("add_sconst_checked", 4),
        ),
        RecipeRule(RecipeRuleKind.SAME, None, None),
    )
    result, port = _run_phase(
        f,
        row,
        sp=0x1E0,
        r7=0x180,
        memory={0x1E0: (0x124).to_bytes(4, "little")},
    )
    assert result.status is InspectionStatus.COMPLETE
    assert len(result.frames) == 2
    top, caller = result.frames
    assert (top.cfa.unsigned_value, top.frame_base) == (0x1E4, None)
    assert caller.resume_pc == HsxAddress(f.code, 0x124)
    assert caller.sp == HsxAddress(f.data, 0x1E4)
    assert rvalue(caller, "R7") == RegisterValue("R7", 32, 0x180, True)
    assert port.register_reads == 1
    assert [(address.unsigned_value, length) for address, length in port.memory_reads] == [(0x1E0, 4)]


def test_entry_after_push_at_mov_recovers_saved_r7_but_current_frame_base_is_still_unavailable() -> None:
    f = foundation()
    row = _phase_row(
        f,
        "entry-after-push",
        UnwindBoundary.ENTRY,
        (
            SpecialValueOp("special_value", RecipeSpecial.SP),
            AddSConstCheckedOp("add_sconst_checked", 8),
        ),
        _saved_r7_rule(f),
    )
    result, port = _run_phase(
        f,
        row,
        sp=0x1E0,
        r7=0x180,
        memory={
            0x1E4: (0x124).to_bytes(4, "little"),
            0x1E0: (0x180).to_bytes(4, "little"),
        },
    )
    assert result.status is InspectionStatus.COMPLETE
    top, caller = result.frames
    assert (top.cfa.unsigned_value, top.frame_base) == (0x1E8, None)
    assert caller.sp == HsxAddress(f.data, 0x1E8)
    assert caller.resume_pc == HsxAddress(f.code, 0x124)
    assert rvalue(caller, "R7") == RegisterValue("R7", 32, 0x180, True)
    assert [(address.unsigned_value, length) for address, length in port.memory_reads] == [
        (0x1E4, 4),
        (0x1E0, 4),
    ]


def test_ordinary_stable_body_uses_exact_snapshot_r7_as_current_frame_base() -> None:
    f = foundation()
    result, port = _run_phase(
        f,
        f.body,
        sp=0x1C0,
        r7=0x1E0,
        memory={
            0x1E4: (0x124).to_bytes(4, "little"),
            0x1E0: (0x180).to_bytes(4, "little"),
        },
    )
    assert result.status is InspectionStatus.COMPLETE
    top, caller = result.frames
    assert top.cfa == HsxAddress(f.data, 0x1E8)
    assert top.frame_base == HsxAddress(f.data, 0x1E0)
    assert caller.sp == HsxAddress(f.data, 0x1E8)
    assert caller.resume_pc == HsxAddress(f.code, 0x124)
    assert rvalue(caller, "R7") == RegisterValue("R7", 32, 0x180, True)
    assert port.register_reads == 1


def test_epilogue_after_pop_uses_sp_row_and_does_not_reinterpret_restored_caller_r7() -> None:
    f = foundation()
    row = _phase_row(
        f,
        "epilogue-after-pop",
        UnwindBoundary.EPILOGUE,
        (
            SpecialValueOp("special_value", RecipeSpecial.SP),
            AddSConstCheckedOp("add_sconst_checked", 4),
        ),
        RecipeRule(RecipeRuleKind.SAME, None, None),
    )
    result, port = _run_phase(
        f,
        row,
        sp=0x1E4,
        r7=0x180,
        memory={0x1E4: (0x124).to_bytes(4, "little")},
    )
    assert result.status is InspectionStatus.COMPLETE
    top, caller = result.frames
    assert (top.cfa.unsigned_value, top.frame_base) == (0x1E8, None)
    assert caller.sp == HsxAddress(f.data, 0x1E8)
    assert caller.resume_pc == HsxAddress(f.code, 0x124)
    assert rvalue(caller, "R7") == RegisterValue("R7", 32, 0x180, True)
    assert [(address.unsigned_value, length) for address, length in port.memory_reads] == [(0x1E4, 4)]


def test_terminal_top_level_never_fabricates_frame_base_or_caller() -> None:
    f = foundation()
    terminal = replace(
        f.terminal,
        row_id="top-terminal",
        pc_range=HsxAddressRange(HsxAddress(f.code, 0x100), 4),
    )
    port = SnapshotPort(f, registers=_registers(f, sp=0x1E0, r7=0x180), memory={})
    result = unwind(f, index=IndexDouble(f, rows=(terminal,)), port=port)
    assert result.status is InspectionStatus.COMPLETE
    assert len(result.frames) == 1
    top = result.frames[0]
    assert top.terminal is True
    assert top.frame_base is None
    assert top.resume_pc is None and top.call_site_pc is None
    assert port.memory_reads == []


def test_ordinary_row_with_unavailable_r7_keeps_frame_but_no_guessed_frame_base() -> None:
    f = foundation()
    ordinary_sp_cfa = replace(
        f.body,
        row_id="ordinary-no-r7-cfa",
        cfa_expression=RecipeExpression(
            RecipeRole.CFA,
            (
                SpecialValueOp("special_value", RecipeSpecial.SP),
                AddSConstCheckedOp("add_sconst_checked", 4),
            ),
            RecipeResultKind.ADDRESS,
            None,
        ),
    )
    port = SnapshotPort(f, registers=_registers(f, sp=0x1C0, r7=None), memory={})
    result = unwind(
        f,
        index=IndexDouble(f, rows=(ordinary_sp_cfa,)),
        port=port,
        request=RecipeRequestLimits(1, 16),
    )
    assert result.status is InspectionStatus.UNSUPPORTED
    assert len(result.frames) == 1
    frame = result.frames[0]
    assert frame.cfa == HsxAddress(f.data, 0x1C4)
    assert frame.frame_base is None
    assert any(
        diagnostic.code == "top_frame_base_unavailable"
        for diagnostic in frame.diagnostics
    )
    assert port.register_reads == 1
    assert port.memory_reads == []
