from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from hsx_debugger import *
from test_hsx_debugger_inspection import first_frame, open_session, scope_by_kind


def test_concurrent_scope_queries_reuse_one_handle_per_scope_kind() -> None:
    _, _, _, _, session = open_session()
    frame = first_frame(session)

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = tuple(pool.map(lambda _: session.scopes(frame.handle), range(32)))

    assert all(result.status is InspectionStatus.COMPLETE for result in results)
    expected_kinds = (ScopeKind.REGISTERS, ScopeKind.LOCALS, ScopeKind.GLOBALS)
    for result in results:
        assert tuple(record.kind for record in result.value.scopes) == expected_kinds

    for kind in expected_kinds:
        serials = {
            next(record.handle.serial for record in result.value.scopes if record.kind is kind)
            for result in results
        }
        assert len(serials) == 1


def test_concurrent_variable_queries_reuse_exact_page_handles() -> None:
    _, _, _, _, session = open_session()
    frame = first_frame(session)
    register_scope = scope_by_kind(session, frame.handle, ScopeKind.REGISTERS)

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = tuple(
            pool.map(
                lambda _: session.variables(register_scope.handle, PageRequest(1, 3)),
                range(32),
            )
        )

    assert all(result.status is InspectionStatus.COMPLETE for result in results)
    assert all(
        [record.register_id for record in result.value.variables] == ["R1", "R7", "PC"]
        for result in results
    )

    for register_id in ("R1", "R7", "PC"):
        serials = {
            next(
                record.handle.serial
                for record in result.value.variables
                if record.register_id == register_id
            )
            for result in results
        }
        assert len(serials) == 1
