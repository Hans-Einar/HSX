from __future__ import annotations

from dataclasses import replace

from hsx_debugger import *
from hsx_debugger.inspection import InspectionService
from test_hsx_debugger_inspection import (
    IndexDouble,
    LocationEvaluator,
    SnapshotPort,
    StaticStack,
    foundation,
)


class BindingIndex(IndexDouble):
    def __init__(self, f, binding):
        super().__init__(f)
        self._binding_override = binding

    def binding(self):
        return self._binding_override


def test_factory_binding_validation_precedes_profile_limit_rejection() -> None:
    f = foundation()
    malformed_binding = replace(f.binding, binding_digest="f" * 64)
    result = InspectionService.create(
        BindingIndex(f, malformed_binding),
        SnapshotPort(f),
        f.architecture,
        f.abi,
        object(),
        StaticStack,
        LocationEvaluator,
    )
    assert result.status is ResolutionStatus.ARTIFACT_MISMATCH
    assert result.diagnostics[0].code == "binding_digest_mismatch"


def test_factory_capability_profile_precedes_profile_limit_rejection() -> None:
    f = foundation()
    payload = replace(
        f.binding.payload,
        accepted_image_debug_capability_profile="legacy-profile",
    )
    legacy_binding = ImageDebugBinding(payload, payload.canonical_digest())
    result = InspectionService.create(
        BindingIndex(f, legacy_binding),
        SnapshotPort(f),
        f.architecture,
        f.abi,
        object(),
        StaticStack,
        LocationEvaluator,
    )
    assert result.status is ResolutionStatus.SCHEMA_UNSUPPORTED
    assert result.diagnostics[0].code == "inspection_profile_unsupported"


def test_factory_profile_limit_rejection_is_used_only_after_binding_and_capability_pass() -> None:
    f = foundation()
    result = InspectionService.create(
        IndexDouble(f),
        SnapshotPort(f),
        f.architecture,
        f.abi,
        object(),
        StaticStack,
        LocationEvaluator,
    )
    assert result.status is ResolutionStatus.SCHEMA_UNSUPPORTED
    assert result.diagnostics[0].code == "recipe_profile_limits_mismatch"
