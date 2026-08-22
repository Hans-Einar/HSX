from __future__ import annotations

import inspect

import pytest

from hsx_debugger import LocationEvaluator, RecipeLimits, ResolutionStatus
from hsx_debugger.inspection import InspectionService
from test_hsx_debugger_inspection import (
    IndexDouble,
    SnapshotPort,
    StaticStack,
    foundation,
)


def _args():
    f = foundation()
    return f, (
        IndexDouble(f),
        SnapshotPort(f),
        f.architecture,
        f.abi,
        RecipeLimits(),
    )


def test_factory_signature_requires_both_composition_dependencies() -> None:
    signature = inspect.signature(InspectionService.create)
    assert signature.parameters["stack_service"].default is inspect.Parameter.empty
    assert signature.parameters["location_evaluator"].default is inspect.Parameter.empty


def test_omitting_both_composition_dependencies_fails_at_python_call_boundary() -> None:
    _, args = _args()
    with pytest.raises(TypeError):
        InspectionService.create(*args)


def test_omitting_location_evaluator_fails_at_python_call_boundary() -> None:
    _, args = _args()
    with pytest.raises(TypeError):
        InspectionService.create(*args, StaticStack)


def test_explicit_dependencies_are_retained_unchanged() -> None:
    _, args = _args()
    created = InspectionService.create(*args, StaticStack, LocationEvaluator)
    assert created.status is ResolutionStatus.RESOLVED
    assert created.service._stack_service is StaticStack
    assert created.service._location_evaluator is LocationEvaluator
