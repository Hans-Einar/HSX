from __future__ import annotations

from dataclasses import replace

from hsx_debugger import *
from test_hsx_debugger_inspection import IndexDouble, first_frame, foundation, open_session, scope_by_kind


class PagedGlobalsIndex(IndexDouble):
    def __init__(self, f):
        super().__init__(f)
        self.bad = replace(
            f.global_,
            symbol_id="bad-global",
            name="bad-global",
            declaration_order=1,
        )
        self.good = replace(
            f.global_,
            symbol_id="good-global",
            name="good-global",
            declaration_order=2,
        )
        self.good_row = replace(
            f.global_row,
            row_id="loc-good-global",
            symbol_id="good-global",
        )
        self.bad_location_calls = 0
        self.good_location_calls = 0

    def global_variables(self):
        return (self.bad, self.good)

    def location_rows(self, symbol_id, function_id, lexical_scope_id, frame_pc):
        if symbol_id == self.bad.symbol_id:
            self.bad_location_calls += 1
            raise AssertionError("off-page variable must not be evaluated")
        if symbol_id == self.good.symbol_id:
            self.good_location_calls += 1
            return ResolutionResult(
                ResolutionStatus.RESOLVED,
                self.f.binding,
                (self.good_row,),
                (),
            )
        return super().location_rows(symbol_id, function_id, lexical_scope_id, frame_pc)


def test_variable_page_evaluates_only_requested_symbol_slice() -> None:
    f = foundation()
    index = PagedGlobalsIndex(f)
    _, _, _, _, session = open_session(f, index=index)
    frame = first_frame(session)
    scope = scope_by_kind(session, frame.handle, ScopeKind.GLOBALS)

    page = session.variables(scope.handle, PageRequest(1, 1))

    assert page.status is InspectionStatus.COMPLETE
    assert page.value.total_variables == 2
    assert page.value.offset == 1
    assert [item.symbol_id for item in page.value.variables] == ["good-global"]
    assert index.bad_location_calls == 0
    assert index.good_location_calls == 1

    repeated = session.variables(scope.handle, PageRequest(1, 1))
    assert repeated.value.variables[0].handle == page.value.variables[0].handle
    assert index.bad_location_calls == 0
