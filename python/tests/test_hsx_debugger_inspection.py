from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from threading import Event
from types import SimpleNamespace

from hsx_debugger import *
from hsx_debugger.handles import DomainHandle, HandleKind, ScopeKind
from hsx_debugger.inspection import (
    EpochInspectionSession,
    InspectionService,
    RegisterVariableRecord,
    SymbolVariableRecord,
)


ZERO = "0" * 64


def foundation(epoch_id="epoch", snapshot_token="snapshot") -> SimpleNamespace:
    artifact = ArtifactRef(
        "hsx.artifact-ref/1", "application/vnd.hsx.hxe", CanonicalUInt64(1),
        CanonicalUInt64(64), ContentDigest("sha256", ZERO)
    )
    target = TargetRef("target", ExecutiveInstanceRef("exec"), "opaque", 1, 7, 1)
    image = LoadedImageRef(
        "hsx.loaded-image-ref/1", target.executive, target, "image",
        CanonicalUInt64(1), artifact
    )
    bundle = ImageDebugBundleIdentityPayload(
        "hsx.image-debug-bundle/1", artifact,
        DescriptorDigestRef("hsx.arch.vm-byte16-gpr32/1", ZERO),
        DescriptorDigestRef("hsx.abi.llc-r7-word32/1", ZERO),
        ComponentDigestRef("hsx.debug-component.symbol-model/1", "1" * 64),
        ComponentDigestRef("hsx.unwind-recipe/1", "2" * 64),
        ComponentDigestRef("hsx.location-recipe/1", "3" * 64),
        StructuredDigest("sha256", "4" * 64), (), ()
    )
    bundle_ref = ImageDebugBundleRef(
        "hsx.image-debug-bundle-ref/1", artifact, "sha256", bundle.canonical_digest()
    )
    binding_payload = ImageDebugBindingPayload(
        "hsx.image-debug-binding/1", image, bundle_ref,
        "hsx.arch.vm-byte16-gpr32/1", "hsx.abi.llc-r7-word32/1",
        "hsx.portable-debug-runtime/1"
    )
    binding = ImageDebugBinding(binding_payload, binding_payload.canonical_digest())
    code, data = AddressSpaceId("code"), AddressSpaceId("data")
    architecture = ArchitectureDescriptor(
        ArchitectureDescriptorRef("hsx.arch.vm-byte16-gpr32/1", ZERO),
        CanonicalUInt64(1), "hsx.fixed32/1", ByteOrder.LITTLE, ByteOrder.LITTLE,
        32, ByteOrder.LITTLE, 3,
        (
            AddressSpaceDescriptor(
                code, "byte", 8, 16,
                (HsxAddressRange(HsxAddress(code, 0), 0x1000),),
                ByteOrder.LITTLE, 4, WrapPolicy.FORBIDDEN,
                frozenset({Permission.READ, Permission.EXECUTE})
            ),
            AddressSpaceDescriptor(
                data, "byte", 8, 16,
                (HsxAddressRange(HsxAddress(data, 0), 0x1000),),
                ByteOrder.LITTLE, 1, WrapPolicy.FORBIDDEN,
                frozenset({Permission.READ, Permission.WRITE})
            ),
        ),
        ("R0", "R1", "R7"), code, data, 8, 4
    )
    abi = AbiDescriptorRef("hsx.abi.llc-r7-word32/1", ZERO)
    generation = GenerationStamp("exec", 1, "opaque", 1, 1, 1, 7, EvidenceGrade.PORTABLE)
    stop = StopToken(target, image, "stop", 3)
    snapshot = InspectionSnapshotRef(
        target, image, stop, snapshot_token, 3, 4,
        frozenset({"registers", "memory", "disassembly"}),
        SnapshotStability.IMMUTABLE, EvidenceGrade.PORTABLE
    )
    context = InspectionContext(
        target, image,
        EpochBinding(StopEpochId(epoch_id), generation, stop, snapshot, EvidenceGrade.PORTABLE)
    )
    function = FunctionRecord(
        "fn", "function", None, HsxAddressRange(HsxAddress(code, 0x100), 0x40), None
    )
    scope = LexicalScopeRecord(
        "scope", "fn", None, HsxAddressRange(HsxAddress(code, 0x100), 0x40), 0
    )
    local = SymbolRecord("local", "dup", SymbolKind.LOCAL, None, 2, "fn", "scope", None, 1)
    global_ = SymbolRecord("global", "dup", SymbolKind.GLOBAL, None, 2, None, None, None, 2)
    label = SymbolRecord("label", "label", SymbolKind.LABEL, HsxAddress(code, 0x120), 0, None, None, None, 0)
    registers = RegisterSet((
        RegisterValue("R0", 32, 0x11111111, True),
        RegisterValue("R1", 32, 0x22222222, True),
        RegisterValue("R7", 32, None, False),
        RegisterValue("PC", 16, 0x100, True),
        RegisterValue("SP", 16, 0x200, True),
        RegisterValue("PSW", 8, 0xA5, True),
    ))
    frame_registers = RegisterSet(registers.registers[:3])
    frame = UnwindFrame(
        context, 0, HsxAddress(code, 0x100), HsxAddress(data, 0x200),
        HsxAddress(data, 0x204), frame_registers, RegisterValue("PSW", 8, 0xA5, True),
        HsxAddress(data, 0x200), None, None, function, None, True, ()
    )
    recipe_schema = RecipeSchemaRef("hsx.location-recipe/1", "3" * 64)
    local_row = LocationRow(
        "loc-local", binding, "local", "scope", "fn",
        HsxAddressRange(HsxAddress(code, 0x100), 0x40), None, 16, abi,
        ByteOrder.LITTLE, FrameBinding.SELECTED_FRAME, recipe_schema,
        LocationForm(
            LocationKind.VALUE,
            RecipeExpression(
                RecipeRole.LOCATION,
                (ConstUOp("const_u", 0x1234, 16),),
                RecipeResultKind.UNSIGNED_SCALAR, 16
            ), (), None
        )
    )
    global_row = LocationRow(
        "loc-global", binding, "global", None, None,
        HsxAddressRange(HsxAddress(code, 0x100), 0x40), None, 16, abi,
        ByteOrder.LITTLE, FrameBinding.SELECTED_FRAME, recipe_schema,
        LocationForm(
            LocationKind.VALUE,
            RecipeExpression(
                RecipeRole.LOCATION,
                (ConstUOp("const_u", 0xBEEF, 16),),
                RecipeResultKind.UNSIGNED_SCALAR, 16
            ), (), None
        )
    )
    instruction = InstructionRecord(
        "i0", HsxAddress(code, 0x100), 4, 0x01020304, "fn", None,
        InstructionClassification.USER
    )
    return SimpleNamespace(**locals())


class IndexDouble:
    def __init__(self, f):
        self.f = f
        self.symbols = {item.symbol_id: item for item in (f.local, f.global_, f.label)}

    def binding(self):
        return self.f.binding

    def bundle_identity(self):
        return self.f.bundle

    def lexical_scopes(self, function_id, frame_pc):
        return (self.f.scope,) if function_id == "fn" and self.f.scope.pc_range.contains(frame_pc) else ()

    def variables_in_scope(self, lexical_scope_id, frame_pc):
        return (self.f.local,) if lexical_scope_id == "scope" else ()

    def global_variables(self):
        return (self.f.global_,)

    def location_rows(self, symbol_id, function_id, lexical_scope_id, frame_pc):
        row = {"local": self.f.local_row, "global": self.f.global_row}.get(symbol_id)
        if row is not None and row.function_id == function_id and row.lexical_scope_id == lexical_scope_id and row.pc_range.contains(frame_pc):
            return ResolutionResult(ResolutionStatus.RESOLVED, self.f.binding, (row,), ())
        return ResolutionResult(
            ResolutionStatus.UNAVAILABLE, self.f.binding, (),
            (Diagnostic("location_row_unavailable", "missing", component="test"),)
        )

    def symbol_by_id(self, symbol_id):
        value = self.symbols.get(symbol_id)
        if value is None:
            return ResolutionResult(
                ResolutionStatus.UNAVAILABLE, self.f.binding, (),
                (Diagnostic("symbol_id_unavailable", "missing", component="test"),)
            )
        return ResolutionResult(ResolutionStatus.RESOLVED, self.f.binding, (value,), ())

    def type_by_id(self, type_id):
        return ResolutionResult(
            ResolutionStatus.UNAVAILABLE, self.f.binding, (),
            (Diagnostic("type_unavailable", "missing", component="test"),)
        )

    def instruction_at(self, address):
        if address == self.f.instruction.address:
            return ResolutionResult(ResolutionStatus.RESOLVED, self.f.binding, (self.f.instruction,), ())
        return ResolutionResult(
            ResolutionStatus.UNAVAILABLE, self.f.binding, (),
            (Diagnostic("instruction_unavailable", "missing", component="test"),)
        )


class StaticStack:
    @staticmethod
    def unwind(context, index, read_port, architecture, abi, profile_limits, request_limits):
        frame = index.f.frame
        if frame.context != context:
            frame = replace(frame, context=context)
        return InspectionResult(InspectionStatus.COMPLETE, context, (frame,), ())


class SnapshotPort:
    def __init__(self, f):
        self.f = f
        self.memory_values = {0x300: b"\x78\x56"}
        self.disassembly_values = {
            0x100: (InstructionBytes(HsxAddress(f.code, 0x100), b"\x04\x03\x02\x01"),)
        }
        self.register_reads = 0
        self.memory_reads = 0
        self.disassembly_reads = 0

    def read_registers(self, context, selection):
        self.register_reads += 1
        by_id = {item.register_id: item for item in self.f.registers.registers}
        order = self.f.architecture.selected_register_order(selection)
        return InspectionResult(
            InspectionStatus.COMPLETE, context,
            RegisterSet(tuple(by_id[item] for item in order)), ()
        )

    def read_memory(self, context, address, byte_length):
        self.memory_reads += 1
        raw = self.memory_values.get(address.unsigned_value)
        if raw is None or len(raw) != byte_length:
            return InspectionResult(
                InspectionStatus.UNAVAILABLE, context, None,
                (Diagnostic("memory_missing", "missing", component="test"),)
            )
        return InspectionResult(
            InspectionStatus.COMPLETE, context,
            MemoryBlock(address, byte_length, (
                MemorySegment(0, byte_length, raw, MemorySegmentStatus.COMPLETE),
            )), ()
        )

    def read_disassembly(self, context, address, instruction_count):
        self.disassembly_reads += 1
        values = self.disassembly_values.get(address.unsigned_value, ())[:instruction_count]
        return InspectionResult(InspectionStatus.COMPLETE, context, tuple(values), ())


class BlockingMemoryPort(SnapshotPort):
    def __init__(self, f):
        super().__init__(f)
        self.started = Event()
        self.release = Event()

    def read_memory(self, context, address, byte_length):
        self.started.set()
        assert self.release.wait(timeout=5)
        return super().read_memory(context, address, byte_length)


def make_service(f=None, port=None, index=None):
    f = f or foundation()
    port = port or SnapshotPort(f)
    index = index or IndexDouble(f)
    created = InspectionService.create(
        index, port, f.architecture, f.abi, RecipeLimits(), StaticStack, LocationEvaluator
    )
    assert created.status is ResolutionStatus.RESOLVED
    return f, index, port, created.service


def open_session(f=None, port=None, index=None):
    f, index, port, service = make_service(f, port, index)
    opened = service.open_epoch(f.context, RecipeRequestLimits(64, 16))
    assert opened.status is InspectionOpenStatus.OPENED
    return f, index, port, service, opened.session


def first_frame(session):
    page = session.stack(PageRequest(0, 16))
    assert page.status is InspectionStatus.COMPLETE
    return page.value.frames[0]


def scope_by_kind(session, frame_handle, kind):
    result = session.scopes(frame_handle)
    assert result.status is InspectionStatus.COMPLETE
    return next(item for item in result.value.scopes if item.kind is kind)


def test_factory_uses_dedicated_lifecycle_envelope_and_exact_profile() -> None:
    f = foundation()
    port = SnapshotPort(f)
    created = InspectionService.create(
        IndexDouble(f), port, f.architecture, f.abi, RecipeLimits(), StaticStack, LocationEvaluator
    )
    assert created.status is ResolutionStatus.RESOLVED
    assert isinstance(created.service, InspectionService)
    assert created.diagnostics == ()

    bad_payload = replace(
        f.binding.payload, accepted_image_debug_capability_profile="legacy"
    )
    bad_binding = ImageDebugBinding(bad_payload, bad_payload.canonical_digest())
    bad_index = IndexDouble(f)
    bad_index.f = SimpleNamespace(**{**vars(f), "binding": bad_binding})
    failed = InspectionService.create(
        bad_index, port, f.architecture, f.abi, RecipeLimits(), StaticStack, LocationEvaluator
    )
    assert (failed.status, failed.service, failed.diagnostics[0].code) == (
        ResolutionStatus.SCHEMA_UNSUPPORTED, None, "inspection_profile_unsupported"
    )


def test_open_same_context_is_idempotent_and_limits_conflict_is_non_destructive() -> None:
    f, _, _, service = make_service()
    first = service.open_epoch(f.context, RecipeRequestLimits(64, 16))
    again = service.open_epoch(f.context, RecipeRequestLimits(64, 16))
    conflict = service.open_epoch(f.context, RecipeRequestLimits(32, 16))
    assert first.session is again.session
    assert conflict.status is InspectionOpenStatus.UNAVAILABLE
    assert conflict.diagnostics[0].code == "epoch_request_limits_conflict"
    assert service.active_epoch_id() == f.context.epoch.stop_epoch_id


def test_new_epoch_invalidates_old_and_old_context_handle_becomes_stale() -> None:
    f, _, _, service, old = open_session()
    frame = first_frame(old)
    new_f = foundation(epoch_id="epoch2", snapshot_token="snapshot2")
    new_context = replace(
        new_f.context,
        target=f.target,
        image=f.image,
        epoch=replace(
            new_f.context.epoch,
            controller_generation=f.context.epoch.controller_generation,
            stop_token=f.context.epoch.stop_token,
            snapshot=replace(
                f.context.epoch.snapshot,
                snapshot_token="snapshot2"
            ),
        ),
    )
    opened = service.open_epoch(new_context, RecipeRequestLimits(64, 16))
    assert opened.status is InspectionOpenStatus.OPENED
    assert old.is_active() is False
    assert old.stack(PageRequest(0, 1)).status is InspectionStatus.STALE
    assert opened.session.scopes(frame.handle).status is InspectionStatus.STALE


def test_same_epoch_id_different_context_is_stale_not_rebound() -> None:
    f, _, _, service, _ = open_session()
    other = replace(
        f.context,
        epoch=replace(
            f.context.epoch,
            snapshot=replace(f.context.epoch.snapshot, snapshot_token="other")
        ),
    )
    result = service.open_epoch(other, RecipeRequestLimits(64, 16))
    assert result.status is InspectionOpenStatus.STALE
    assert result.diagnostics[0].code == "active_epoch_context_mismatch"


def test_registers_follow_exact_selection_and_snapshot_order() -> None:
    f, _, port, _, session = open_session()
    selected = session.registers(RegisterSelection(False, ("PSW", "R1")))
    assert selected.status is InspectionStatus.COMPLETE
    assert tuple(item.register_id for item in selected.value.registers) == ("PSW", "R1")
    assert port.register_reads == 1


def test_stack_pagination_reuses_exact_frame_handle() -> None:
    _, _, _, _, session = open_session()
    first = session.stack(PageRequest(0, 1))
    again = session.stack(PageRequest(0, 1))
    empty = session.stack(PageRequest(1, 1))
    assert first.value.total_frames == again.value.total_frames == empty.value.total_frames == 1
    assert first.value.frames[0].handle == again.value.frames[0].handle
    assert empty.value.frames == ()


def test_scopes_are_fixed_order_and_handles_are_stable() -> None:
    _, _, _, _, session = open_session()
    frame = first_frame(session)
    first = session.scopes(frame.handle)
    again = session.scopes(frame.handle)
    assert [item.kind for item in first.value.scopes] == [
        ScopeKind.REGISTERS, ScopeKind.LOCALS, ScopeKind.GLOBALS
    ]
    assert [item.handle for item in first.value.scopes] == [item.handle for item in again.value.scopes]


def test_register_variables_are_architecture_ordered_and_keep_unavailable_r7() -> None:
    _, _, _, _, session = open_session()
    frame = first_frame(session)
    scope = scope_by_kind(session, frame.handle, ScopeKind.REGISTERS)
    result = session.variables(scope.handle, PageRequest(0, 32))
    assert result.status is InspectionStatus.COMPLETE
    assert result.value.total_variables == 6
    assert all(isinstance(item, RegisterVariableRecord) for item in result.value.variables)
    assert [item.register_id for item in result.value.variables] == ["R0", "R1", "R7", "PC", "SP", "PSW"]
    r7 = result.value.variables[2]
    assert r7.evaluated.status is ValueAvailability.UNAVAILABLE
    assert r7.evaluated.raw_bytes is None


def test_local_and_global_duplicate_names_remain_distinct_symbol_ids() -> None:
    _, _, _, _, session = open_session()
    frame = first_frame(session)
    local_scope = scope_by_kind(session, frame.handle, ScopeKind.LOCALS)
    global_scope = scope_by_kind(session, frame.handle, ScopeKind.GLOBALS)
    locals_page = session.variables(local_scope.handle, PageRequest(0, 16))
    globals_page = session.variables(global_scope.handle, PageRequest(0, 16))
    local = locals_page.value.variables[0]
    global_ = globals_page.value.variables[0]
    assert isinstance(local, SymbolVariableRecord)
    assert isinstance(global_, SymbolVariableRecord)
    assert (local.symbol_id, global_.symbol_id) == ("local", "global")
    assert local.evaluated.raw_bytes == b"\x34\x12"
    assert global_.evaluated.raw_bytes == b"\xef\xbe"
    assert local.handle != global_.handle


def test_snapshot_expression_matrix_is_typed_and_side_effect_free() -> None:
    f, _, port, _, session = open_session()
    frame = first_frame(session)
    register = session.evaluate_snapshot(frame.handle, RegisterExpression("R1"))
    variable = session.evaluate_snapshot(frame.handle, VariableExpression("local", "fn", "scope"))
    symbol = session.evaluate_snapshot(frame.handle, SymbolExpression("label"))
    constant = session.evaluate_snapshot(frame.handle, ConstantExpression(0x3456, 16, ByteOrder.LITTLE))
    memory = session.evaluate_snapshot(frame.handle, MemoryExpression(HsxAddress(f.data, 0x300), 16, ByteOrder.LITTLE))
    assert register.value.raw_bytes == b"\x22\x22\x22\x22"
    assert variable.value.raw_bytes == b"\x34\x12"
    assert symbol.value.raw_bytes == b"\x20\x01"
    assert constant.value.raw_bytes == b"\x56\x34"
    assert memory.value.raw_bytes == b"\x78\x56"
    assert port.memory_reads == 1


def test_memory_and_disassembly_use_exact_snapshot_evidence() -> None:
    f, _, port, _, session = open_session()
    memory = session.memory(HsxAddress(f.data, 0x300), 2)
    disassembly = session.disassemble(HsxAddress(f.code, 0x100), 1)
    assert memory.value.segments[0].data == b"\x78\x56"
    assert disassembly.value.instructions[0].instruction == f.instruction
    assert disassembly.value.instructions[0].encoded == b"\x04\x03\x02\x01"
    assert (port.memory_reads, port.disassembly_reads) == (1, 1)


def test_unknown_foreign_handle_stays_unknown() -> None:
    f, _, _, _, session = open_session()
    foreign_f = foundation(epoch_id="other", snapshot_token="other")
    foreign = DomainHandle(foreign_f.context, HandleKind.FRAME, 1)
    assert session.scopes(foreign).status is InspectionStatus.UNKNOWN_HANDLE


def test_invalidate_and_close_are_exact_and_idempotent() -> None:
    f, _, _, service, session = open_session()
    invalidated = service.invalidate_epoch(f.context.epoch.stop_epoch_id, "resume")
    repeated = service.invalidate_epoch(f.context.epoch.stop_epoch_id, "again")
    unknown = service.invalidate_epoch(StopEpochId("never"), "unknown")
    assert invalidated.status is InvalidationStatus.INVALIDATED
    assert repeated.status is InvalidationStatus.ALREADY_STALE
    assert unknown.status is InvalidationStatus.UNKNOWN_EPOCH
    assert session.is_active() is False
    closed = service.close("done")
    again = service.close("again")
    assert closed.status is ServiceCloseStatus.CLOSED
    assert again.status is ServiceCloseStatus.ALREADY_CLOSED
    assert service.open_epoch(f.context, RecipeRequestLimits(64, 16)).status is InspectionOpenStatus.STALE


def test_invalidation_wins_over_late_snapshot_read() -> None:
    f = foundation()
    port = BlockingMemoryPort(f)
    _, _, _, service, session = open_session(f, port)
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(session.memory, HsxAddress(f.data, 0x300), 2)
        assert port.started.wait(timeout=5)
        service.invalidate_epoch(f.context.epoch.stop_epoch_id, "resume")
        port.release.set()
        result = future.result(timeout=5)
    assert result.status is InspectionStatus.STALE


def test_concurrent_repeated_stack_queries_intern_one_frame_handle() -> None:
    _, _, _, _, session = open_session()
    with ThreadPoolExecutor(max_workers=8) as pool:
        pages = tuple(pool.map(lambda _: session.stack(PageRequest(0, 1)), range(32)))
    assert all(item.status is InspectionStatus.COMPLETE for item in pages)
    handles = {item.value.frames[0].handle.serial for item in pages}
    assert len(handles) == 1
