from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

from hsx_debugger import *
from hsx_debugger.stack import StackService


ZERO = "0" * 64


def foundation() -> SimpleNamespace:
    artifact = ArtifactRef(
        "hsx.artifact-ref/1",
        "application/vnd.hsx.hxe",
        CanonicalUInt64(1),
        CanonicalUInt64(64),
        ContentDigest("sha256", ZERO),
    )
    target = TargetRef("target", ExecutiveInstanceRef("exec"), "opaque", 1, 7, 1)
    image = LoadedImageRef(
        "hsx.loaded-image-ref/1",
        target.executive,
        target,
        "image",
        CanonicalUInt64(1),
        artifact,
    )
    bundle = ImageDebugBundleIdentityPayload(
        "hsx.image-debug-bundle/1",
        artifact,
        DescriptorDigestRef("hsx.arch.vm-byte16-gpr32/1", ZERO),
        DescriptorDigestRef("hsx.abi.llc-r7-word32/1", ZERO),
        ComponentDigestRef("hsx.debug-component.symbol-model/1", "1" * 64),
        ComponentDigestRef("hsx.unwind-recipe/1", "2" * 64),
        ComponentDigestRef("hsx.location-recipe/1", "3" * 64),
        StructuredDigest("sha256", "4" * 64),
        (),
        (),
    )
    bundle_ref = ImageDebugBundleRef(
        "hsx.image-debug-bundle-ref/1",
        artifact,
        "sha256",
        bundle.canonical_digest(),
    )
    binding_payload = ImageDebugBindingPayload(
        "hsx.image-debug-binding/1",
        image,
        bundle_ref,
        "hsx.arch.vm-byte16-gpr32/1",
        "hsx.abi.llc-r7-word32/1",
        "hsx.portable-debug-runtime/1",
    )
    binding = ImageDebugBinding(binding_payload, binding_payload.canonical_digest())

    code, data = AddressSpaceId("code"), AddressSpaceId("data")
    architecture = ArchitectureDescriptor(
        ArchitectureDescriptorRef("hsx.arch.vm-byte16-gpr32/1", ZERO),
        CanonicalUInt64(1),
        "hsx.fixed32/1",
        ByteOrder.LITTLE,
        ByteOrder.LITTLE,
        32,
        ByteOrder.LITTLE,
        3,
        (
            AddressSpaceDescriptor(
                code,
                "byte",
                8,
                16,
                (HsxAddressRange(HsxAddress(code, 0), 0x1000),),
                ByteOrder.LITTLE,
                4,
                WrapPolicy.FORBIDDEN,
                frozenset({Permission.READ, Permission.EXECUTE}),
            ),
            AddressSpaceDescriptor(
                data,
                "byte",
                8,
                16,
                (HsxAddressRange(HsxAddress(data, 0), 0x1000),),
                ByteOrder.LITTLE,
                1,
                WrapPolicy.FORBIDDEN,
                frozenset({Permission.READ, Permission.WRITE}),
            ),
        ),
        ("R0", "R1", "R7"),
        code,
        data,
        8,
        4,
    )
    abi = AbiDescriptorRef("hsx.abi.llc-r7-word32/1", ZERO)
    generation = GenerationStamp("exec", 1, "opaque", 1, 1, 1, 7, EvidenceGrade.PORTABLE)
    stop = StopToken(target, image, "stop", 3)
    snapshot = InspectionSnapshotRef(
        target,
        image,
        stop,
        "snapshot",
        3,
        4,
        frozenset({"registers", "memory", "disassembly"}),
        SnapshotStability.IMMUTABLE,
        EvidenceGrade.PORTABLE,
    )
    context = InspectionContext(
        target,
        image,
        EpochBinding(StopEpochId("epoch"), generation, stop, snapshot, EvidenceGrade.PORTABLE),
    )

    registers = RegisterSet(
        (
            RegisterValue("R0", 32, 1, True),
            RegisterValue("R1", 32, 2, True),
            RegisterValue("R7", 32, 0x200, True),
            RegisterValue("PC", 16, 0x100, True),
            RegisterValue("SP", 16, 0x1E0, True),
            RegisterValue("PSW", 8, 0xA5, True),
        )
    )

    function0 = FunctionRecord(
        "callee", "callee", None, HsxAddressRange(HsxAddress(code, 0x100), 4), None
    )
    function1 = FunctionRecord(
        "caller", "caller", None, HsxAddressRange(HsxAddress(code, 0x120), 8), None
    )
    instruction = InstructionRecord(
        "call", HsxAddress(code, 0x120), 4, 0, "caller", None, InstructionClassification.USER
    )

    def expr(role, operations, result, width):
        return RecipeExpression(role, tuple(operations), result, width)

    schema = RecipeSchemaRef("hsx.unwind-recipe/1", "2" * 64)
    body = UnwindRow(
        "body",
        binding,
        HsxAddressRange(HsxAddress(code, 0x100), 4),
        abi,
        schema,
        expr(
            RecipeRole.CFA,
            (
                RegValueOp("reg_value", "R7"),
                ToAddressOp("to_address", data),
                AddSConstCheckedOp("add_sconst_checked", 8),
            ),
            RecipeResultKind.ADDRESS,
            None,
        ),
        RecipeRule(
            RecipeRuleKind.EXPRESSION,
            expr(
                RecipeRole.CALLER_PC,
                (
                    CfaOp("cfa"),
                    AddSConstCheckedOp("add_sconst_checked", -4),
                    DerefUOp("deref_u", 4, ByteOrder.LITTLE),
                    ToAddressOp("to_address", code),
                ),
                RecipeResultKind.ADDRESS,
                None,
            ),
            None,
        ),
        RecipeRule(
            RecipeRuleKind.EXPRESSION,
            expr(
                RecipeRole.CALLER_SP,
                (CfaOp("cfa"),),
                RecipeResultKind.ADDRESS,
                None,
            ),
            None,
        ),
        None,
        (
            (
                "R7",
                RecipeRule(
                    RecipeRuleKind.EXPRESSION,
                    expr(
                        RecipeRole.REGISTER,
                        (
                            CfaOp("cfa"),
                            AddSConstCheckedOp("add_sconst_checked", -8),
                            DerefUOp("deref_u", 4, ByteOrder.LITTLE),
                        ),
                        RecipeResultKind.UNSIGNED_SCALAR,
                        32,
                    ),
                    None,
                ),
            ),
        ),
        UnwindBoundary.ORDINARY,
        -4,
    )
    terminal = UnwindRow(
        "terminal",
        binding,
        HsxAddressRange(HsxAddress(code, 0x120), 8),
        abi,
        schema,
        expr(
            RecipeRole.CFA,
            (
                SpecialValueOp("special_value", RecipeSpecial.SP),
                AddSConstCheckedOp("add_sconst_checked", 4),
            ),
            RecipeResultKind.ADDRESS,
            None,
        ),
        RecipeRule(RecipeRuleKind.UNAVAILABLE, None, "terminal"),
        RecipeRule(RecipeRuleKind.UNAVAILABLE, None, "terminal"),
        None,
        (),
        UnwindBoundary.TERMINAL,
        None,
    )
    return SimpleNamespace(**locals())


class IndexDouble:
    def __init__(self, f, rows=None, instructions=None, binding=None):
        self.f = f
        self.rows = tuple(rows if rows is not None else (f.body, f.terminal))
        self.instructions = dict(
            instructions if instructions is not None else {0x120: f.instruction}
        )
        self._binding = binding or f.binding

    def binding(self):
        return self._binding

    def bundle_identity(self):
        return self.f.bundle

    def functions(self):
        return (self.f.function0, self.f.function1)

    def instruction_at(self, address):
        value = self.instructions.get(address.unsigned_value)
        if value is None:
            return ResolutionResult(
                ResolutionStatus.UNAVAILABLE,
                self._binding,
                (),
                (Diagnostic("instruction_unavailable", "missing", component="test"),),
            )
        return ResolutionResult(ResolutionStatus.RESOLVED, self._binding, (value,), ())

    def unwind_rows(self, pc, function_id):
        matches = tuple(row for row in self.rows if row.pc_range.contains(pc))
        if len(matches) == 1:
            return ResolutionResult(ResolutionStatus.RESOLVED, self._binding, matches, ())
        if not matches:
            return ResolutionResult(
                ResolutionStatus.UNAVAILABLE,
                self._binding,
                (),
                (Diagnostic("unwind_row_unavailable", "missing", component="test"),),
            )
        return ResolutionResult(
            ResolutionStatus.CORRUPT,
            self._binding,
            (),
            (Diagnostic("unwind_row_overlap", "overlap", component="test"),),
        )


class SnapshotPort:
    def __init__(self, f, memory=None, registers=None):
        self.f = f
        self.memory = dict(memory if memory is not None else {
            0x204: (0x124).to_bytes(4, "little"),
            0x200: (0x180).to_bytes(4, "little"),
        })
        self.registers = registers or f.registers
        self.register_reads = 0
        self.memory_reads = []

    def read_registers(self, context, selection):
        self.register_reads += 1
        assert context == self.f.context
        assert selection == RegisterSelection(True, ())
        return InspectionResult(InspectionStatus.COMPLETE, context, self.registers, ())

    def read_memory(self, context, address, byte_length):
        self.memory_reads.append((address, byte_length))
        raw = self.memory.get(address.unsigned_value)
        if raw is None or len(raw) != byte_length:
            return InspectionResult(
                InspectionStatus.UNAVAILABLE,
                context,
                None,
                (Diagnostic("memory_missing", "missing", component="test"),),
            )
        return InspectionResult(
            InspectionStatus.COMPLETE,
            context,
            MemoryBlock(
                address,
                byte_length,
                (MemorySegment(0, byte_length, raw, MemorySegmentStatus.COMPLETE),),
            ),
            (),
        )

    def read_disassembly(self, context, address, instruction_count):
        raise AssertionError("stack service must not read disassembly")


def unwind(f, *, index=None, port=None, request=None):
    return StackService.unwind(
        f.context,
        index or IndexDouble(f),
        port or SnapshotPort(f),
        f.architecture,
        f.abi,
        RecipeLimits(),
        request or RecipeRequestLimits(64, 16),
    )


def rvalue(frame, register_id):
    return next(item for item in frame.recovered_registers.registers if item.register_id == register_id)


def test_current_body_unwinds_scalar_bound_r7_into_terminal_caller() -> None:
    f = foundation()
    port = SnapshotPort(f)
    result = unwind(f, port=port)
    assert result.status is InspectionStatus.COMPLETE
    assert len(result.value) == 2
    top, caller = result.value
    assert (top.pc.unsigned_value, top.sp.unsigned_value, top.cfa.unsigned_value) == (
        0x100, 0x1E0, 0x208
    )
    assert top.frame_base == HsxAddress(f.data, 0x200)
    assert not top.terminal
    assert (caller.pc.unsigned_value, caller.sp.unsigned_value, caller.cfa.unsigned_value) == (
        0x120, 0x208, 0x20C
    )
    assert caller.resume_pc == HsxAddress(f.code, 0x124)
    assert caller.call_site_pc == HsxAddress(f.code, 0x120)
    assert caller.terminal
    assert rvalue(caller, "R7") == RegisterValue("R7", 32, 0x180, True)
    assert not caller.recovered_psw.available
    assert port.register_reads == 1
    assert [(address.unsigned_value, length) for address, length in port.memory_reads] == [
        (0x204, 4),
        (0x200, 4),
    ]


def test_missing_required_caller_memory_returns_trustworthy_partial_prefix() -> None:
    f = foundation()
    port = SnapshotPort(f, memory={})
    result = unwind(f, port=port)
    assert result.status is InspectionStatus.PARTIAL
    assert len(result.value) == 1
    assert result.value[0].pc == HsxAddress(f.code, 0x100)
    assert result.diagnostics[0].code == "memory_missing"
    assert port.register_reads == 1


def test_missing_gpr_rule_never_infers_current_abi_r7() -> None:
    f = foundation()
    body = replace(f.body, register_rules=())
    result = unwind(f, index=IndexDouble(f, rows=(body, f.terminal)))
    assert result.status is InspectionStatus.COMPLETE
    caller = result.value[1]
    assert rvalue(caller, "R7") == RegisterValue("R7", 32, None, False)


def test_explicit_same_is_the_only_younger_register_propagation() -> None:
    f = foundation()
    same = replace(
        f.body,
        register_rules=(("R7", RecipeRule(RecipeRuleKind.SAME, None, None)),),
    )
    result = unwind(f, index=IndexDouble(f, rows=(same, f.terminal)))
    assert result.status is InspectionStatus.COMPLETE
    assert rvalue(result.value[1], "R7") == RegisterValue("R7", 32, 0x200, True)


def test_requesting_one_frame_does_not_recover_or_read_the_caller() -> None:
    f = foundation()
    port = SnapshotPort(f)
    result = unwind(f, port=port, request=RecipeRequestLimits(1, 16))
    assert (result.status, len(result.value)) == (InspectionStatus.COMPLETE, 1)
    assert port.register_reads == 1
    assert port.memory_reads == []


def test_call_site_is_optional_and_resume_pc_remains_exact() -> None:
    f = foundation()
    terminal_at_resume = replace(
        f.terminal,
        pc_range=HsxAddressRange(HsxAddress(f.code, 0x124), 4),
    )
    result = unwind(
        f,
        index=IndexDouble(f, rows=(f.body, terminal_at_resume), instructions={}),
    )
    assert result.status is InspectionStatus.COMPLETE
    caller = result.value[1]
    assert caller.pc == HsxAddress(f.code, 0x124)
    assert caller.resume_pc == HsxAddress(f.code, 0x124)
    assert caller.call_site_pc is None


def test_repeated_pc_sp_is_corrupt_not_a_fallback_walk() -> None:
    f = foundation()
    cyclic = replace(
        f.body,
        caller_pc_rule=RecipeRule(RecipeRuleKind.SAME, None, None),
        caller_sp_rule=RecipeRule(RecipeRuleKind.SAME, None, None),
        register_rules=(),
        call_site_adjustment=None,
    )
    result = unwind(f, index=IndexDouble(f, rows=(cyclic,)))
    assert (result.status, result.diagnostics[0].code) == (
        InspectionStatus.CORRUPT,
        "unwind_cycle",
    )


def test_profile_limit_rejection_happens_before_snapshot_read() -> None:
    f = foundation()
    port = SnapshotPort(f)
    result = unwind(f, port=port, request=RecipeRequestLimits(65, 16))
    assert (result.status, result.diagnostics[0].code) == (
        InspectionStatus.UNSUPPORTED,
        "limit_exceeded",
    )
    assert port.register_reads == 0


def test_binding_mismatch_happens_before_snapshot_read() -> None:
    f = foundation()
    port = SnapshotPort(f)
    bad_binding = replace(f.binding, binding_digest="f" * 64)
    result = unwind(f, index=IndexDouble(f, binding=bad_binding), port=port)
    assert result.status is InspectionStatus.ARTIFACT_MISMATCH
    assert port.register_reads == 0


def test_all_declared_register_shape_is_exact() -> None:
    f = foundation()
    port = SnapshotPort(f, registers=RegisterSet(tuple(reversed(f.registers.registers))))
    result = unwind(f, port=port)
    assert (result.status, result.diagnostics[0].code) == (
        InspectionStatus.CORRUPT,
        "snapshot_register_shape_mismatch",
    )


def test_unavailable_gpr_expression_does_not_abort_an_otherwise_valid_caller() -> None:
    f = foundation()
    port = SnapshotPort(f, memory={0x204: (0x124).to_bytes(4, "little")})
    result = unwind(f, port=port)
    assert result.status is InspectionStatus.COMPLETE
    assert rvalue(result.value[1], "R7").available is False


def test_explicit_unsupported_boundary_is_not_silently_walked() -> None:
    f = foundation()
    unsupported = replace(f.body, boundary=UnwindBoundary.UNSUPPORTED)
    port = SnapshotPort(f)
    result = unwind(f, index=IndexDouble(f, rows=(unsupported,)), port=port)
    assert (result.status, result.diagnostics[0].code) == (
        InspectionStatus.UNSUPPORTED,
        "unwind_boundary_unsupported",
    )
    assert port.memory_reads == []
