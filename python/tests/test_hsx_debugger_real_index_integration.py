from __future__ import annotations

from hsx_debugger import *
from hsx_debugger.inspection import InspectionService, ScopeQueryResult, VariableQueryResult
from hsx_debugger.stack import StackService
from test_hsx_debugger_artifacts import build, portable_fixture


class ExactSnapshotPort:
    def __init__(self, context, architecture, registers):
        self.context = context
        self.architecture = architecture
        self.registers = registers
        self.register_reads = 0
        self.memory_reads = 0
        self.disassembly_reads = 0

    def read_registers(self, context, selection):
        self.register_reads += 1
        assert context == self.context
        order = self.architecture.selected_register_order(selection)
        by_id = {item.register_id: item for item in self.registers.registers}
        return InspectionResult(
            InspectionStatus.COMPLETE,
            context,
            RegisterSet(tuple(by_id[register_id] for register_id in order)),
            (),
        )

    def read_memory(self, context, address, byte_length):
        self.memory_reads += 1
        return InspectionResult(
            InspectionStatus.UNAVAILABLE,
            context,
            None,
            (Diagnostic("integration_memory_unavailable", "not required", component="test"),),
        )

    def read_disassembly(self, context, address, instruction_count):
        self.disassembly_reads += 1
        return InspectionResult(
            InspectionStatus.UNAVAILABLE,
            context,
            None,
            (Diagnostic("integration_disassembly_unavailable", "not required", component="test"),),
        )


def _runtime():
    fixture = portable_fixture()
    built = build(fixture)
    assert built.status is ResolutionStatus.RESOLVED
    index = built.values[0]

    target = fixture.target
    image = fixture.image
    generation = GenerationStamp(
        target.executive.value,
        1,
        target.target_id,
        target.target_generation,
        1,
        1,
        target.display_pid,
        EvidenceGrade.PORTABLE,
    )
    stop = StopToken(target, image, "integration-stop", 1)
    snapshot = InspectionSnapshotRef(
        target,
        image,
        stop,
        "integration-snapshot",
        1,
        1,
        frozenset({"registers", "memory", "disassembly"}),
        SnapshotStability.IMMUTABLE,
        EvidenceGrade.PORTABLE,
    )
    context = InspectionContext(
        target,
        image,
        EpochBinding(
            StopEpochId("integration-epoch"),
            generation,
            stop,
            snapshot,
            EvidenceGrade.PORTABLE,
        ),
    )
    architecture = fixture.architecture
    registers = RegisterSet(
        (
            RegisterValue("R0", architecture.register_bit_width("R0"), 0x10, True),
            RegisterValue("R1", architecture.register_bit_width("R1"), 0x11, True),
            RegisterValue("R7", architecture.register_bit_width("R7"), 0x100, True),
            RegisterValue("PC", architecture.register_bit_width("PC"), 0x20, True),
            RegisterValue("SP", architecture.register_bit_width("SP"), 0x100, True),
            RegisterValue("PSW", architecture.register_bit_width("PSW"), 0, True),
        )
    )
    port = ExactSnapshotPort(context, architecture, registers)
    created = InspectionService.create(
        index,
        port,
        architecture,
        fixture.abi,
        RecipeLimits(),
        StackService,
        LocationEvaluator,
    )
    assert created.status is ResolutionStatus.RESOLVED
    opened = created.service.open_epoch(context, RecipeRequestLimits(1, 16))
    assert opened.status is InspectionOpenStatus.OPENED
    return fixture, index, port, opened.session


def test_real_index_bound_prefix_scope_variable_and_symbol_expression_chain() -> None:
    fixture, index, port, session = _runtime()

    # The portable fixture has an ordinary (nonterminal) unwind row. max_frames=1 therefore
    # proves one frame but must terminate UNSUPPORTED/limit_exceeded rather than fabricate
    # completeness. Slice006 may still allocate/use the proven prefix frame in this epoch.
    stack = session.stack(PageRequest(0, 8))
    assert stack.status is InspectionStatus.UNSUPPORTED
    assert stack.diagnostics[0].code == "limit_exceeded"
    assert stack.page.total_frames == 1
    frame = stack.page.frames[0]
    assert frame.unwind.function.function_id == "fn"
    assert frame.unwind.pc == HsxAddress(fixture.architecture.pc_space, 0x20)
    assert frame.unwind.terminal is False

    scopes = session.scopes(frame.handle)
    assert isinstance(scopes, ScopeQueryResult)
    assert scopes.status is InspectionStatus.COMPLETE
    assert [record.kind for record in scopes.value.scopes] == [
        ScopeKind.REGISTERS,
        ScopeKind.LOCALS,
        ScopeKind.GLOBALS,
    ]

    local_scope = next(record for record in scopes.value.scopes if record.kind is ScopeKind.LOCALS)
    local_page = session.variables(local_scope.handle, PageRequest(0, 16))
    assert isinstance(local_page, VariableQueryResult)
    assert local_page.status is InspectionStatus.COMPLETE
    assert [record.symbol_id for record in local_page.value.variables] == ["local"]
    assert local_page.value.variables[0].evaluated.location_status is ValueAvailability.UNAVAILABLE

    global_scope = next(record for record in scopes.value.scopes if record.kind is ScopeKind.GLOBALS)
    global_page = session.variables(global_scope.handle, PageRequest(0, 16))
    assert global_page.status is InspectionStatus.COMPLETE
    assert [record.symbol_id for record in global_page.value.variables] == ["global", "constant"]

    variable = session.evaluate_snapshot(
        frame.handle,
        VariableExpression("local", "fn", "scope"),
    )
    assert variable.status is InspectionStatus.COMPLETE
    assert variable.value.expression_kind is ExpressionKind.VARIABLE
    assert variable.value.source_id == "local"
    assert variable.value.status is ValueAvailability.UNAVAILABLE

    symbol = session.evaluate_snapshot(frame.handle, SymbolExpression("sym-label"))
    assert symbol.status is InspectionStatus.COMPLETE
    assert symbol.value.expression_kind is ExpressionKind.SYMBOL
    assert symbol.value.source_id == "sym-label"
    assert int.from_bytes(symbol.value.raw_bytes, "little") == 0x24

    assert index.symbol_by_id("sym-label").status is ResolutionStatus.RESOLVED
    assert port.register_reads >= 1
    assert port.memory_reads == 0
    assert port.disassembly_reads == 0
