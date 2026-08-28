from __future__ import annotations

from dataclasses import replace

import pytest

from hsx_debugger import *
from hsx_debugger.handles import DomainHandle, HandleInternResult, HandleKind
from hsx_debugger.inspection import (
    InspectionService,
    ScopeQueryResult,
    ScopeSet,
    VariablePage,
    VariableQueryResult,
)
from hsx_debugger.results import _deep_freeze
from test_hsx_debugger_inspection import IndexDouble, SnapshotPort, StaticStack, foundation


def test_evidence_grade_remains_forbidden_as_direct_generic_payload_after_package_import() -> None:
    f = foundation()
    with pytest.raises(TypeError, match="approved closed contract Enum"):
        _deep_freeze(EvidenceGrade.PORTABLE, "evidence")
    with pytest.raises(TypeError, match="approved closed contract Enum"):
        InspectionResult(
            InspectionStatus.COMPLETE,
            f.context,
            EvidenceGrade.PORTABLE,
            (),
        )
    with pytest.raises(TypeError, match="approved closed contract Enum"):
        ResolutionResult(
            ResolutionStatus.RESOLVED,
            None,
            (EvidenceGrade.PORTABLE,),
            (),
        )


def test_epoch_reference_values_use_dedicated_envelopes_without_generic_freeze() -> None:
    f = foundation()
    frame = DomainHandle(f.context, HandleKind.FRAME, 1)
    scope = DomainHandle(f.context, HandleKind.SCOPE, 2)

    interned = HandleInternResult(InspectionStatus.COMPLETE, f.context, frame, ())
    scopes = ScopeQueryResult(
        InspectionStatus.COMPLETE,
        f.context,
        ScopeSet(frame, ()),
        (),
    )
    variables = VariableQueryResult(
        InspectionStatus.COMPLETE,
        f.context,
        VariablePage(scope, 0, 0, ()),
        (),
    )

    assert interned.handle is frame
    assert scopes.value.frame_handle is frame
    assert variables.value.scope_handle is scope


def test_epoch_reference_envelopes_reject_context_mismatch_and_failed_values() -> None:
    f = foundation()
    other = foundation(epoch_id="other", snapshot_token="other")
    other_frame = DomainHandle(other.context, HandleKind.FRAME, 1)
    other_scope = DomainHandle(other.context, HandleKind.SCOPE, 2)
    local_frame = DomainHandle(f.context, HandleKind.FRAME, 1)

    with pytest.raises(ValueError, match="exact result context"):
        HandleInternResult(InspectionStatus.COMPLETE, f.context, other_frame, ())
    with pytest.raises(ValueError, match="exact result context"):
        ScopeQueryResult(
            InspectionStatus.COMPLETE,
            f.context,
            ScopeSet(other_frame, ()),
            (),
        )
    with pytest.raises(ValueError, match="exact result context"):
        VariableQueryResult(
            InspectionStatus.COMPLETE,
            f.context,
            VariablePage(other_scope, 0, 0, ()),
            (),
        )

    diagnostic = Diagnostic("stale", "stale epoch", component="test")
    with pytest.raises(ValueError, match="publishes no handle"):
        HandleInternResult(
            InspectionStatus.STALE,
            f.context,
            local_frame,
            (diagnostic,),
        )
    with pytest.raises(ValueError, match="no value"):
        ScopeQueryResult(
            InspectionStatus.STALE,
            f.context,
            ScopeSet(local_frame, ()),
            (diagnostic,),
        )


def test_closed_service_precedes_stale_context_and_request_limit_classification() -> None:
    f = foundation()
    port = SnapshotPort(f)
    created = InspectionService.create(
        IndexDouble(f), port, f.architecture, f.abi,
        RecipeLimits(), StaticStack, LocationEvaluator
    )
    service = created.service
    opened = service.open_epoch(f.context, RecipeRequestLimits(64, 16))
    assert opened.status is InspectionOpenStatus.OPENED
    assert service.close("done").status is ServiceCloseStatus.CLOSED

    # Build a self-consistent but stale loaded-image context atomically. Constructing an
    # intermediate InspectionContext with mismatched image/epoch evidence is intentionally
    # forbidden by the DTO invariants.
    stale_image = replace(f.image, loaded_image_id="other-image")
    stale_stop = replace(f.context.epoch.stop_token, image=stale_image)
    stale_snapshot = replace(
        f.context.epoch.snapshot,
        image=stale_image,
        stop_token=stale_stop,
    )
    stale_epoch = replace(
        f.context.epoch,
        stop_token=stale_stop,
        snapshot=stale_snapshot,
    )
    stale_context = InspectionContext(f.target, stale_image, stale_epoch)

    stale = service.open_epoch(stale_context, RecipeRequestLimits(64, 16))
    oversized = service.open_epoch(f.context, RecipeRequestLimits(65, 16))
    for result in (stale, oversized):
        assert result.status is InspectionOpenStatus.UNAVAILABLE
        assert result.diagnostics[0].code == "inspection_service_closed"
