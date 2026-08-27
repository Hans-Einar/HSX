from __future__ import annotations

from dataclasses import replace

from hsx_debugger import *
from test_hsx_debugger_stack import IndexDouble, SnapshotPort, foundation, unwind


class LocationIndex:
    def __init__(self, f):
        self.f = f

    def binding(self):
        return self.f.binding

    def bundle_identity(self):
        return self.f.bundle

    def type_by_id(self, type_id):
        return ResolutionResult(
            ResolutionStatus.UNAVAILABLE,
            self.f.binding,
            (),
            (Diagnostic("type_unavailable", "not used", component="test"),),
        )


def _local_and_row(f):
    variable = SymbolRecord(
        "local-fb",
        "local-fb",
        SymbolKind.LOCAL,
        None,
        2,
        "callee",
        "scope",
        None,
        0,
    )
    row = LocationRow(
        "loc-frame-base",
        f.binding,
        variable.symbol_id,
        variable.lexical_scope_id,
        variable.function_id,
        HsxAddressRange(HsxAddress(f.code, 0x100), 4),
        None,
        16,
        f.abi,
        ByteOrder.LITTLE,
        FrameBinding.SELECTED_FRAME,
        RecipeSchemaRef("hsx.location-recipe/1", "3" * 64),
        LocationForm(
            LocationKind.ADDRESS,
            RecipeExpression(
                RecipeRole.LOCATION,
                (
                    FrameBaseOp("frame_base"),
                    AddSConstCheckedOp("add_sconst_checked", -4),
                ),
                RecipeResultKind.ADDRESS,
                None,
            ),
            (),
            None,
        ),
    )
    return variable, row


def _evaluate(f, frame, port):
    variable, row = _local_and_row(f)
    return LocationEvaluator.evaluate(
        f.context,
        frame,
        LocationIndex(f),
        variable,
        row,
        port,
        f.architecture,
        f.abi,
        RecipeLimits(),
        RecipeRequestLimits(1, 16),
    )


def test_ordinary_frame_base_location_uses_exact_snapshot_r7_evidence() -> None:
    f = foundation()
    port = SnapshotPort(f, memory={0x1FC: b"\x34\x12"})
    stack = unwind(f, port=port, request=RecipeRequestLimits(1, 16))
    assert stack.status is InspectionStatus.UNSUPPORTED
    assert len(stack.frames) == 1
    frame = stack.frames[0]
    assert frame.frame_base == HsxAddress(f.data, 0x200)

    result = _evaluate(f, frame, port)
    assert result.status is InspectionStatus.COMPLETE
    assert result.value.location_status is ValueAvailability.AVAILABLE
    assert result.value.raw_bytes == b"\x34\x12"
    assert result.value.display_value == str(0x1234)


def test_entry_frame_base_location_is_explicitly_unavailable_not_caller_r7_fallback() -> None:
    f = foundation()
    entry = replace(
        f.body,
        row_id="entry",
        boundary=UnwindBoundary.ENTRY,
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
    port = SnapshotPort(f, memory={0x1FC: b"\x34\x12"})
    stack = unwind(
        f,
        index=IndexDouble(f, rows=(entry,)),
        port=port,
        request=RecipeRequestLimits(1, 16),
    )
    assert stack.status is InspectionStatus.UNSUPPORTED
    assert len(stack.frames) == 1
    frame = stack.frames[0]
    assert frame.frame_base is None

    result = _evaluate(f, frame, port)
    assert result.status is InspectionStatus.COMPLETE
    assert result.value.location_status is ValueAvailability.UNAVAILABLE
    assert result.value.raw_bytes is None
    assert "frame_base_unavailable" in result.value.display_value
    # No location-memory read may be attempted when frame-base evidence is unavailable.
    assert port.memory_reads == []


def test_epilogue_frame_base_location_is_explicitly_unavailable_after_r7_restore() -> None:
    f = foundation()
    epilogue = replace(
        f.body,
        row_id="epilogue",
        boundary=UnwindBoundary.EPILOGUE,
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
    port = SnapshotPort(f, memory={0x1FC: b"\x34\x12"})
    stack = unwind(
        f,
        index=IndexDouble(f, rows=(epilogue,)),
        port=port,
        request=RecipeRequestLimits(1, 16),
    )
    assert stack.status is InspectionStatus.UNSUPPORTED
    frame = stack.frames[0]
    assert frame.frame_base is None

    result = _evaluate(f, frame, port)
    assert result.status is InspectionStatus.COMPLETE
    assert result.value.location_status is ValueAvailability.UNAVAILABLE
    assert result.value.raw_bytes is None
    assert port.memory_reads == []
