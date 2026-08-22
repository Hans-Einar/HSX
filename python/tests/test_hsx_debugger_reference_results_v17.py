from __future__ import annotations

import pytest

from hsx_debugger import *
from hsx_debugger.handles import DomainHandle, HandleInternResult, HandleKind
from hsx_debugger.inspection import (
    ScopeQueryResult,
    ScopeSet,
    VariablePage,
    VariableQueryResult,
)
from test_hsx_debugger_inspection import foundation, open_session, first_frame, scope_by_kind


def test_direct_controller_evidence_enum_remains_outside_generic_payload_catalog() -> None:
    f = foundation()
    for constructor in (
        lambda: InspectionResult(
            InspectionStatus.COMPLETE, f.context, EvidenceGrade.PORTABLE, ()
        ),
        lambda: ResolutionResult(
            ResolutionStatus.RESOLVED, None, (EvidenceGrade.PORTABLE,), ()
        ),
    ):
        with pytest.raises(TypeError, match="approved closed contract Enum"):
            constructor()


def test_real_session_uses_dedicated_scope_and_variable_envelopes() -> None:
    _, _, _, _, session = open_session()
    frame = first_frame(session)
    scopes = session.scopes(frame.handle)
    assert isinstance(scopes, ScopeQueryResult)
    assert scopes.status is InspectionStatus.COMPLETE
    assert scopes.context == frame.context

    register_scope = scope_by_kind(session, frame.handle, ScopeKind.REGISTERS)
    variables = session.variables(register_scope.handle, PageRequest(0, 32))
    assert isinstance(variables, VariableQueryResult)
    assert variables.status is InspectionStatus.COMPLETE
    assert variables.context == frame.context
    assert variables.value.scope_handle == register_scope.handle
    assert all(item.context == frame.context for item in variables.value.variables)


def test_dedicated_reference_envelopes_reject_cross_epoch_payloads() -> None:
    left = foundation()
    right = foundation(epoch_id="other", snapshot_token="other")
    right_frame = DomainHandle(right.context, HandleKind.FRAME, 1)
    right_scope = DomainHandle(right.context, HandleKind.SCOPE, 2)

    with pytest.raises(ValueError, match="exact result context"):
        HandleInternResult(InspectionStatus.COMPLETE, left.context, right_frame, ())
    with pytest.raises(ValueError, match="exact result context"):
        ScopeQueryResult(
            InspectionStatus.COMPLETE,
            left.context,
            ScopeSet(right_frame, ()),
            (),
        )
    with pytest.raises(ValueError, match="exact result context"):
        VariableQueryResult(
            InspectionStatus.COMPLETE,
            left.context,
            VariablePage(right_scope, 0, 0, ()),
            (),
        )


def test_failed_reference_envelopes_never_publish_reference_values() -> None:
    f = foundation()
    frame = DomainHandle(f.context, HandleKind.FRAME, 1)
    diagnostic = Diagnostic("stale", "epoch invalidated", component="test")

    with pytest.raises(ValueError, match="publishes no handle"):
        HandleInternResult(
            InspectionStatus.STALE, f.context, frame, (diagnostic,)
        )
    with pytest.raises(ValueError, match="no value"):
        ScopeQueryResult(
            InspectionStatus.CORRUPT,
            f.context,
            ScopeSet(frame, ()),
            (diagnostic,),
        )


def test_partial_reference_envelopes_require_value_and_diagnostics() -> None:
    f = foundation()
    frame = DomainHandle(f.context, HandleKind.FRAME, 1)
    value = ScopeSet(frame, ())
    diagnostic = Diagnostic("partial", "some scopes unavailable", component="test")

    accepted = ScopeQueryResult(
        InspectionStatus.PARTIAL, f.context, value, (diagnostic,)
    )
    assert accepted.value is value
    with pytest.raises(ValueError, match="PARTIAL"):
        ScopeQueryResult(InspectionStatus.PARTIAL, f.context, value, ())
    with pytest.raises(ValueError, match="PARTIAL"):
        ScopeQueryResult(
            InspectionStatus.PARTIAL, f.context, None, (diagnostic,)
        )
