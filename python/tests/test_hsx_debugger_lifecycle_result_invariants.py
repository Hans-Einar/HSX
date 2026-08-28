from __future__ import annotations

import pytest

from hsx_debugger import *
from hsx_debugger.inspection import (
    EpochInspectionSession,
    InspectionOpenResult,
    InspectionService,
    InspectionServiceCreateResult,
    ServiceCloseResult,
)
from test_hsx_debugger_inspection import make_service, open_session


def test_service_create_result_rejects_ambiguous_status_and_non_service_reference() -> None:
    diagnostic = Diagnostic("bad", "bad factory result", component="test")
    with pytest.raises(ValueError, match="AMBIGUOUS"):
        InspectionServiceCreateResult(ResolutionStatus.AMBIGUOUS, None, (diagnostic,))
    with pytest.raises(TypeError, match="InspectionService"):
        InspectionServiceCreateResult(ResolutionStatus.RESOLVED, object(), ())

    _, _, _, service = make_service()
    accepted = InspectionServiceCreateResult(ResolutionStatus.RESOLVED, service, ())
    assert accepted.service is service
    assert isinstance(accepted.service, InspectionService)


def test_open_result_requires_exact_session_reference_for_opened() -> None:
    with pytest.raises(TypeError, match="EpochInspectionSession"):
        InspectionOpenResult(InspectionOpenStatus.OPENED, object(), ())

    _, _, _, _, session = open_session()
    accepted = InspectionOpenResult(InspectionOpenStatus.OPENED, session, ())
    assert accepted.session is session
    assert isinstance(accepted.session, EpochInspectionSession)


def test_service_close_result_enforces_terminal_algebra() -> None:
    _, _, _, service, _ = open_session()
    closed = service.close("done")
    assert closed.status is ServiceCloseStatus.CLOSED
    assert closed.diagnostics == ()
    assert closed.invalidation is not None
    assert closed.invalidation.status is InvalidationStatus.INVALIDATED

    repeated = service.close("again")
    assert repeated.status is ServiceCloseStatus.ALREADY_CLOSED
    assert repeated.invalidation is None
    assert repeated.diagnostics

    diagnostic = Diagnostic("closed", "already closed", component="test")
    with pytest.raises(ValueError, match="CLOSED"):
        ServiceCloseResult(ServiceCloseStatus.CLOSED, None, (diagnostic,))
    with pytest.raises(ValueError, match="ALREADY_CLOSED"):
        ServiceCloseResult(ServiceCloseStatus.ALREADY_CLOSED, closed.invalidation, (diagnostic,))
