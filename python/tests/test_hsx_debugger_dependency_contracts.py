from __future__ import annotations

from dataclasses import replace

from hsx_debugger import *
from hsx_debugger.inspection import InspectionService
from test_hsx_debugger_inspection import (
    IndexDouble,
    SnapshotPort,
    StaticStack,
    open_session,
    first_frame,
    scope_by_kind,
    foundation,
)


class RaisingLocationIndex(IndexDouble):
    def location_rows(self, symbol_id, function_id, lexical_scope_id, frame_pc):
        raise RuntimeError("injected location index failure")


class WrongLocationRowIndex(IndexDouble):
    def location_rows(self, symbol_id, function_id, lexical_scope_id, frame_pc):
        return ResolutionResult(ResolutionStatus.RESOLVED, self.f.binding, (1,), ())


class RaisingSymbolIndex(IndexDouble):
    def symbol_by_id(self, symbol_id):
        raise RuntimeError("injected symbol index failure")


class WrongSymbolIndex(IndexDouble):
    def symbol_by_id(self, symbol_id):
        return ResolutionResult(ResolutionStatus.RESOLVED, self.f.binding, (1,), ())


class RaisingInstructionIndex(IndexDouble):
    def instruction_at(self, address):
        raise RuntimeError("injected instruction index failure")


class MalformedLocationEvaluator:
    @staticmethod
    def evaluate(*args, **kwargs):
        return object()


class RaisingStackService:
    @staticmethod
    def unwind(*args, **kwargs):
        raise RuntimeError("injected stack failure")


class MalformedStackService:
    @staticmethod
    def unwind(*args, **kwargs):
        return object()


class SwitchableMalformedFrameStack:
    malformed = False

    @classmethod
    def unwind(cls, context, index, *args, **kwargs):
        frame = index.f.frame
        if frame.context != context:
            frame = replace(frame, context=context)
        if cls.malformed:
            frame = replace(
                frame,
                recovered_registers=RegisterSet(frame.recovered_registers.registers[1:]),
            )
        return StackWalkResult(InspectionStatus.COMPLETE, context, (frame,), ())


class ForeignSymbolLocationEvaluator:
    @staticmethod
    def evaluate(context, frame, index, symbol, row, *args, **kwargs):
        value = EvaluatedValue(
            "global",
            "foreign-name",
            row.declared_type_id,
            "57005",
            b"\xad\xde",
            row.declared_bit_size,
            ValueAvailability.AVAILABLE,
            (),
        )
        return InspectionResult(InspectionStatus.COMPLETE, context, value, ())


class ForeignBindingSymbolIndex(IndexDouble):
    def __init__(self, f):
        super().__init__(f)
        self.foreign_binding = replace(f.binding, binding_digest="f" * 64)

    def symbol_by_id(self, symbol_id):
        value = self.symbols[symbol_id]
        return ResolutionResult(
            ResolutionStatus.RESOLVED,
            self.foreign_binding,
            (value,),
            (),
        )


def _foreign_context_stack(foreign_context):
    class ForeignContextStack:
        @staticmethod
        def unwind(context, index, *args, **kwargs):
            frame = replace(index.f.frame, context=foreign_context)
            return StackWalkResult(
                InspectionStatus.COMPLETE,
                foreign_context,
                (frame,),
                (),
            )

    return ForeignContextStack


def _local_then_foreign_stack(foreign_context):
    class LocalThenForeignStack:
        calls = 0

        @classmethod
        def unwind(cls, context, index, *args, **kwargs):
            cls.calls += 1
            result_context = context if cls.calls == 1 else foreign_context
            frame = replace(index.f.frame, context=result_context)
            return StackWalkResult(
                InspectionStatus.COMPLETE,
                result_context,
                (frame,),
                (),
            )

    return LocalThenForeignStack


def _foreign_context_evaluator(foreign_context):
    class ForeignContextEvaluator:
        @staticmethod
        def evaluate(*args, **kwargs):
            evaluated = LocationEvaluator.evaluate(*args, **kwargs)
            return InspectionResult(
                evaluated.status,
                foreign_context,
                evaluated.value,
                evaluated.diagnostics,
            )

    return ForeignContextEvaluator


def _open_with_location_evaluator(f, index, evaluator):
    port = SnapshotPort(f)
    created = InspectionService.create(
        index,
        port,
        f.architecture,
        f.abi,
        RecipeLimits(),
        StaticStack,
        evaluator,
    )
    assert created.status is ResolutionStatus.RESOLVED
    opened = created.service.open_epoch(f.context, RecipeRequestLimits(64, 16))
    assert opened.status is InspectionOpenStatus.OPENED
    return opened.session


def test_stack_query_classifies_stack_service_exception() -> None:
    f = foundation()
    _, _, _, _, session = open_session(f, stack_service=RaisingStackService)

    result = session.stack(PageRequest(0, 16))
    assert result.status is InspectionStatus.CORRUPT
    assert result.context == f.context
    assert result.page.frames == ()
    assert result.diagnostics[0].code == "stack_service_contract"


def test_stack_query_rejects_non_stack_walk_result() -> None:
    f = foundation()
    _, _, _, _, session = open_session(f, stack_service=MalformedStackService)

    result = session.stack(PageRequest(0, 16))
    assert result.status is InspectionStatus.CORRUPT
    assert result.context == f.context
    assert result.page.frames == ()
    assert result.diagnostics[0].code == "stack_service_contract"


def test_stack_query_rejects_architecture_incomplete_frame_without_handle_publication() -> None:
    f = foundation()
    SwitchableMalformedFrameStack.malformed = True
    _, _, _, _, session = open_session(f, stack_service=SwitchableMalformedFrameStack)
    before_serial = session._store._next_serial
    before_handles = dict(session._store._by_serial)

    result = session.stack(PageRequest(0, 16))

    assert result.status is InspectionStatus.CORRUPT
    assert result.context == f.context
    assert result.page.frames == ()
    assert result.diagnostics[0].code == "invalid_recovered_register_order"
    assert session._store._next_serial == before_serial
    assert session._store._by_serial == before_handles


def test_repeated_selected_frame_consumers_reject_malformed_walk_without_new_handles() -> None:
    f = foundation()
    SwitchableMalformedFrameStack.malformed = False
    _, _, _, _, session = open_session(f, stack_service=SwitchableMalformedFrameStack)
    frame = first_frame(session)
    scope = scope_by_kind(session, frame.handle, ScopeKind.LOCALS)
    before_serial = session._store._next_serial
    before_handles = dict(session._store._by_serial)
    SwitchableMalformedFrameStack.malformed = True

    stack = session.stack(PageRequest(0, 16))
    scopes = session.scopes(frame.handle)
    variables = session.variables(scope.handle, PageRequest(0, 16))
    selected = session.evaluate_snapshot(frame.handle, RegisterExpression("R0"))

    assert stack.status is InspectionStatus.CORRUPT
    assert stack.page.frames == ()
    for result in (scopes, variables, selected):
        assert result.status is InspectionStatus.CORRUPT
        assert result.value is None
        assert result.diagnostics[0].code == "invalid_recovered_register_order"
    assert session._store._next_serial == before_serial
    assert session._store._by_serial == before_handles


def test_stack_query_rejects_foreign_context_before_frame_publication() -> None:
    f = foundation()
    foreign = foundation(epoch_id="foreign", snapshot_token="foreign")
    stack_service = _foreign_context_stack(foreign.context)
    _, _, _, _, session = open_session(f, stack_service=stack_service)

    result = session.stack(PageRequest(0, 16))
    assert result.status is InspectionStatus.STALE
    assert result.context == f.context
    assert result.page.frames == ()
    assert result.diagnostics[0].code == "stack_service_context_stale"


def test_foreign_repeated_walk_cannot_reuse_interned_frame() -> None:
    f = foundation()
    foreign = foundation(epoch_id="foreign", snapshot_token="foreign")
    stack_service = _local_then_foreign_stack(foreign.context)
    _, _, _, _, session = open_session(f, stack_service=stack_service)
    frame = first_frame(session)

    scopes = session.scopes(frame.handle)
    selected = session.evaluate_snapshot(frame.handle, RegisterExpression("R0"))

    assert scopes.status is InspectionStatus.STALE
    assert scopes.value is None
    assert scopes.diagnostics[0].code == "stack_service_context_stale"
    assert selected.status is InspectionStatus.STALE
    assert selected.value is None
    assert selected.diagnostics[0].code == "stack_service_context_stale"


def test_variable_query_rejects_foreign_location_evaluator_context() -> None:
    f = foundation()
    foreign = foundation(epoch_id="foreign", snapshot_token="foreign")
    session = _open_with_location_evaluator(
        f,
        IndexDouble(f),
        _foreign_context_evaluator(foreign.context),
    )
    frame = first_frame(session)
    scope = scope_by_kind(session, frame.handle, ScopeKind.LOCALS)

    result = session.variables(scope.handle, PageRequest(0, 16))
    assert result.status is InspectionStatus.STALE
    assert result.context == f.context
    assert result.value is None
    assert result.diagnostics[0].code == "snapshot_context_stale"


def test_variable_expression_rejects_foreign_location_evaluator_context() -> None:
    f = foundation()
    foreign = foundation(epoch_id="foreign", snapshot_token="foreign")
    session = _open_with_location_evaluator(
        f,
        IndexDouble(f),
        _foreign_context_evaluator(foreign.context),
    )
    frame = first_frame(session)

    result = session.evaluate_snapshot(
        frame.handle,
        VariableExpression("local", "fn", "scope"),
    )
    assert result.status is InspectionStatus.STALE
    assert result.context == f.context
    assert result.value is None
    assert result.diagnostics[0].code == "snapshot_context_stale"


def test_same_context_foreign_symbol_value_is_corrupt_before_variable_publication() -> None:
    f = foundation()
    session = _open_with_location_evaluator(
        f,
        IndexDouble(f),
        ForeignSymbolLocationEvaluator,
    )
    frame = first_frame(session)
    scope = scope_by_kind(session, frame.handle, ScopeKind.LOCALS)
    before_serial = session._store._next_serial
    before_handles = dict(session._store._by_serial)

    variables = session.variables(scope.handle, PageRequest(0, 16))
    selected = session.evaluate_snapshot(
        frame.handle,
        VariableExpression("local", "fn", "scope"),
    )

    for result in (variables, selected):
        assert result.status is InspectionStatus.CORRUPT
        assert result.context == f.context
        assert result.value is None
        assert result.diagnostics[0].code == "location_evaluator_identity_mismatch"
    assert session._store._next_serial == before_serial
    assert session._store._by_serial == before_handles


def test_symbol_queries_reject_foreign_result_binding() -> None:
    f = foundation()
    index = ForeignBindingSymbolIndex(f)
    _, _, _, _, session = open_session(f, index=index)
    frame = first_frame(session)

    symbol = session.evaluate_snapshot(frame.handle, SymbolExpression("label"))
    variable = session.evaluate_snapshot(
        frame.handle,
        VariableExpression("local", "fn", "scope"),
    )

    for result in (symbol, variable):
        assert result.status is InspectionStatus.ARTIFACT_MISMATCH
        assert result.context == f.context
        assert result.value is None
        assert result.diagnostics[0].code == "artifact_binding_mismatch"


def test_symbol_queries_accept_exact_service_validated_binding() -> None:
    f = foundation()
    _, _, _, _, session = open_session(f, index=IndexDouble(f))
    frame = first_frame(session)

    symbol = session.evaluate_snapshot(frame.handle, SymbolExpression("label"))
    variable = session.evaluate_snapshot(
        frame.handle,
        VariableExpression("local", "fn", "scope"),
    )

    assert symbol.status is InspectionStatus.COMPLETE
    assert symbol.value.display_value == "288"
    assert variable.status is InspectionStatus.COMPLETE
    assert variable.value.display_value == "4660"


def test_variable_query_classifies_location_index_exception() -> None:
    f = foundation()
    index = RaisingLocationIndex(f)
    _, _, _, _, session = open_session(f, index=index)
    frame = first_frame(session)
    scope = scope_by_kind(session, frame.handle, ScopeKind.LOCALS)

    result = session.variables(scope.handle, PageRequest(0, 16))
    assert result.status is InspectionStatus.CORRUPT
    assert result.value is None
    assert result.diagnostics[0].code == "artifact_index_contract"


def test_variable_query_rejects_non_location_row_resolution_value() -> None:
    f = foundation()
    index = WrongLocationRowIndex(f)
    _, _, _, _, session = open_session(f, index=index)
    frame = first_frame(session)
    scope = scope_by_kind(session, frame.handle, ScopeKind.LOCALS)

    result = session.variables(scope.handle, PageRequest(0, 16))
    assert result.status is InspectionStatus.CORRUPT
    assert result.value is None
    assert result.diagnostics[0].code == "artifact_index_contract"


def test_variable_query_rejects_malformed_location_evaluator_result() -> None:
    f = foundation()
    index = IndexDouble(f)
    session = _open_with_location_evaluator(f, index, MalformedLocationEvaluator)
    frame = first_frame(session)
    scope = scope_by_kind(session, frame.handle, ScopeKind.LOCALS)

    result = session.variables(scope.handle, PageRequest(0, 16))
    assert result.status is InspectionStatus.CORRUPT
    assert result.value is None
    assert result.diagnostics[0].code == "location_evaluator_contract"


def test_snapshot_expression_classifies_symbol_index_exception() -> None:
    f = foundation()
    index = RaisingSymbolIndex(f)
    _, _, _, _, session = open_session(f, index=index)
    frame = first_frame(session)

    result = session.evaluate_snapshot(
        frame.handle,
        SymbolExpression("label"),
    )
    assert result.status is InspectionStatus.CORRUPT
    assert result.value is None
    assert result.diagnostics[0].code == "artifact_index_contract"


def test_snapshot_expression_rejects_non_symbol_resolution_value() -> None:
    f = foundation()
    index = WrongSymbolIndex(f)
    _, _, _, _, session = open_session(f, index=index)
    frame = first_frame(session)

    result = session.evaluate_snapshot(frame.handle, SymbolExpression("label"))
    assert result.status is InspectionStatus.CORRUPT
    assert result.value is None
    assert result.diagnostics[0].code == "artifact_index_contract"


def test_disassembly_keeps_exact_bytes_and_reports_optional_annotation_failure() -> None:
    f = foundation()
    index = RaisingInstructionIndex(f)
    _, _, _, _, session = open_session(f, index=index)

    result = session.disassemble(HsxAddress(f.code, 0x100), 1)
    assert result.status is InspectionStatus.COMPLETE
    assert result.value.instructions[0].encoded == b"\x04\x03\x02\x01"
    assert result.value.instructions[0].instruction is None
    assert any(
        diagnostic.code == "instruction_index_contract"
        for diagnostic in result.diagnostics
    )
