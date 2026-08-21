from __future__ import annotations

from dataclasses import replace

from hsx_debugger import *
from hsx_debugger.inspection import InspectionService
from hsx_debugger.results import _deep_freeze
from test_hsx_debugger_inspection import IndexDouble, SnapshotPort, StaticStack, foundation


def test_evidence_grade_is_contract_safe_immediately_after_package_import() -> None:
    # This intentionally exercises the generic-result registry directly. It must not rely on
    # another test module having imported/registered controller enums first.
    assert _deep_freeze(EvidenceGrade.PORTABLE, "evidence") is EvidenceGrade.PORTABLE


def test_nested_inspection_context_is_contract_safe_without_prior_test_side_effects() -> None:
    f = foundation()
    wrapped = InspectionResult(
        InspectionStatus.COMPLETE,
        f.context,
        (f.context,),
        (),
    )
    assert wrapped.value == (f.context,)


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
