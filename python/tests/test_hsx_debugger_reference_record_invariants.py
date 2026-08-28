from __future__ import annotations

import pytest

from hsx_debugger import *
from hsx_debugger.handles import DomainHandle, HandleKind, HandleResolution, ScopeKind
from hsx_debugger.inspection import (
    FramePage,
    FrameRecord,
    RegisterVariableRecord,
    ScopeRecord,
    ScopeSet,
    VariablePage,
)
from test_hsx_debugger_inspection import foundation


def _frame_record(f, index=0, serial=1):
    frame = f.frame
    if index != frame.frame_index:
        frame = UnwindFrame(
            frame.context,
            index,
            frame.pc,
            frame.sp,
            frame.cfa,
            frame.recovered_registers,
            frame.recovered_psw,
            frame.frame_base,
            frame.resume_pc,
            frame.call_site_pc,
            frame.function,
            frame.source,
            frame.terminal,
            frame.diagnostics,
        )
    return FrameRecord(
        f.context,
        DomainHandle(f.context, HandleKind.FRAME, serial),
        frame,
    )


def test_complete_handle_resolution_validates_kind_specific_object_key_shape() -> None:
    f = foundation()
    with pytest.raises(ValueError, match="FRAME object_key"):
        HandleResolution(
            InspectionStatus.COMPLETE,
            f.context,
            HandleKind.FRAME,
            (),
            (),
        )
    with pytest.raises(ValueError, match="frame_serial"):
        HandleResolution(
            InspectionStatus.COMPLETE,
            f.context,
            HandleKind.SCOPE,
            (0, ScopeKind.LOCALS),
            (),
        )


def test_frame_page_enforces_offset_and_contiguous_frame_indices() -> None:
    f = foundation()
    frame0 = _frame_record(f, 0, 1)
    frame1 = _frame_record(f, 1, 2)

    valid = FramePage(2, 1, (frame1,))
    assert valid.frames == (frame1,)
    with pytest.raises(ValueError, match="requested offset"):
        FramePage(2, 1, (frame0,))
    with pytest.raises(ValueError, match="contiguous"):
        FramePage(3, 0, (frame0, _frame_record(f, 2, 3)))


def test_scope_set_enforces_unique_fixed_scope_order() -> None:
    f = foundation()
    frame = DomainHandle(f.context, HandleKind.FRAME, 1)

    def scope(serial, kind, name):
        return ScopeRecord(
            f.context,
            DomainHandle(f.context, HandleKind.SCOPE, serial),
            frame,
            kind,
            name,
            False,
        )

    registers = scope(2, ScopeKind.REGISTERS, "Registers")
    locals_ = scope(3, ScopeKind.LOCALS, "Locals")
    globals_ = scope(4, ScopeKind.GLOBALS, "Globals")
    assert ScopeSet(frame, (registers, locals_, globals_)).scopes[0] is registers
    with pytest.raises(ValueError, match="unique"):
        ScopeSet(frame, (registers, registers))
    with pytest.raises(ValueError, match="Registers/Locals/Globals"):
        ScopeSet(frame, (locals_, registers))


def test_variable_page_rejects_duplicate_variable_handles() -> None:
    f = foundation()
    scope = DomainHandle(f.context, HandleKind.SCOPE, 2)
    handle = DomainHandle(f.context, HandleKind.VARIABLE, 3)
    value = ExpressionValue(
        ExpressionKind.REGISTER,
        "R1",
        "17",
        b"\x11\x00\x00\x00",
        32,
        ValueAvailability.AVAILABLE,
        (),
    )
    first = RegisterVariableRecord(f.context, handle, scope, "R1", 0, value)
    second = RegisterVariableRecord(f.context, handle, scope, "R1", 1, value)
    with pytest.raises(ValueError, match="unique"):
        VariablePage(scope, 2, 0, (first, second))
