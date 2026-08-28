from __future__ import annotations

from dataclasses import replace

from hsx_debugger import *
from hsx_debugger.stack import StackWalkResult
from test_hsx_debugger_inspection import (
    SnapshotPort,
    StaticStack,
    foundation,
    open_session,
    first_frame,
    scope_by_kind,
)


class CountingStack(StaticStack):
    calls = 0

    @staticmethod
    def unwind(context, index, read_port, architecture, abi, profile_limits, request_limits):
        CountingStack.calls += 1
        return StaticStack.unwind(
            context, index, read_port, architecture, abi, profile_limits, request_limits
        )


def test_invalidated_session_rejects_every_query_before_stack_or_snapshot_io() -> None:
    f = foundation()
    port = SnapshotPort(f)
    CountingStack.calls = 0
    _, _, _, service, session = open_session(f, port, stack_service=CountingStack)

    frame = first_frame(session)
    register_scope = scope_by_kind(session, frame.handle, ScopeKind.REGISTERS)

    # Ignore setup activity. Once invalidated, no query is allowed to consult StackService or
    # SnapshotReadPort and no new domain handle may be allocated.
    CountingStack.calls = 0
    port.register_reads = 0
    port.memory_reads = 0
    port.disassembly_reads = 0
    invalidated = service.invalidate_epoch(f.context.epoch.stop_epoch_id, "resume")
    assert invalidated.status is InvalidationStatus.INVALIDATED

    stack = session.stack(PageRequest(0, 16))
    scopes = session.scopes(frame.handle)
    variables = session.variables(register_scope.handle, PageRequest(0, 16))
    registers = session.registers(RegisterSelection(False, ("R1",)))
    expression = session.evaluate_snapshot(frame.handle, ConstantExpression(7, 8, ByteOrder.LITTLE))
    memory = session.memory(HsxAddress(f.data, 0x300), 2)
    disassembly = session.disassemble(HsxAddress(f.code, 0x100), 1)

    for result in (stack, scopes, variables, registers, expression, memory, disassembly):
        assert result.status is InspectionStatus.STALE

    assert stack.page.total_frames == 0
    assert scopes.value is None
    assert variables.value is None
    assert registers.value is None
    assert expression.value is None
    assert memory.value is None
    assert disassembly.value is None
    assert CountingStack.calls == 0
    assert (port.register_reads, port.memory_reads, port.disassembly_reads) == (0, 0, 0)
