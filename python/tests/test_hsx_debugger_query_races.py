from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Event

from hsx_debugger import *
from test_hsx_debugger_inspection import (
    IndexDouble,
    SnapshotPort,
    StaticStack,
    foundation,
    open_session,
    first_frame,
    scope_by_kind,
)


class BlockingRegisterPort(SnapshotPort):
    def __init__(self, f):
        super().__init__(f)
        self.started = Event()
        self.release = Event()

    def read_registers(self, context, selection):
        self.started.set()
        assert self.release.wait(timeout=5)
        return super().read_registers(context, selection)


class BlockingLexicalIndex(IndexDouble):
    def __init__(self, f):
        super().__init__(f)
        self.started = Event()
        self.release = Event()

    def lexical_scopes(self, function_id, frame_pc):
        self.started.set()
        assert self.release.wait(timeout=5)
        return super().lexical_scopes(function_id, frame_pc)


class BlockingLocationIndex(IndexDouble):
    def __init__(self, f):
        super().__init__(f)
        self.started = Event()
        self.release = Event()

    def location_rows(self, symbol_id, function_id, lexical_scope_id, frame_pc):
        self.started.set()
        assert self.release.wait(timeout=5)
        return super().location_rows(symbol_id, function_id, lexical_scope_id, frame_pc)


class BlockingInstructionIndex(IndexDouble):
    def __init__(self, f):
        super().__init__(f)
        self.started = Event()
        self.release = Event()

    def instruction_at(self, address):
        self.started.set()
        assert self.release.wait(timeout=5)
        return super().instruction_at(address)


def test_invalidation_wins_over_inflight_register_snapshot_read() -> None:
    f = foundation()
    port = BlockingRegisterPort(f)
    _, _, _, service, session = open_session(f, port)

    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(session.registers, RegisterSelection(False, ("R1",)))
        assert port.started.wait(timeout=5)
        service.invalidate_epoch(f.context.epoch.stop_epoch_id, "resume")
        port.release.set()
        result = future.result(timeout=5)

    assert result.status is InspectionStatus.STALE
    assert result.value is None


def test_invalidation_wins_over_inflight_scope_metadata_lookup() -> None:
    f = foundation()
    index = BlockingLexicalIndex(f)
    _, _, _, service, session = open_session(f, index=index)
    frame = first_frame(session)

    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(session.scopes, frame.handle)
        assert index.started.wait(timeout=5)
        service.invalidate_epoch(f.context.epoch.stop_epoch_id, "resume")
        index.release.set()
        result = future.result(timeout=5)

    assert result.status is InspectionStatus.STALE
    assert result.value is None
    assert result.diagnostics[0].code == "scope_lookup_invalidated"


def test_invalidation_wins_over_inflight_variable_location_lookup() -> None:
    f = foundation()
    index = BlockingLocationIndex(f)
    _, _, _, service, session = open_session(f, index=index)
    frame = first_frame(session)
    local_scope = scope_by_kind(session, frame.handle, ScopeKind.LOCALS)

    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(session.variables, local_scope.handle, PageRequest(0, 16))
        assert index.started.wait(timeout=5)
        service.invalidate_epoch(f.context.epoch.stop_epoch_id, "resume")
        index.release.set()
        result = future.result(timeout=5)

    assert result.status is InspectionStatus.STALE
    assert result.value is None
    assert result.diagnostics[0].code == "variable_evaluation_invalidated"


def test_invalidation_after_disassembly_snapshot_before_metadata_mapping_wins() -> None:
    f = foundation()
    index = BlockingInstructionIndex(f)
    _, _, _, service, session = open_session(f, index=index)

    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(
            session.disassemble,
            HsxAddress(f.code, 0x100),
            1,
        )
        assert index.started.wait(timeout=5)
        service.invalidate_epoch(f.context.epoch.stop_epoch_id, "resume")
        index.release.set()
        result = future.result(timeout=5)

    assert result.status is InspectionStatus.STALE
    assert result.value is None
