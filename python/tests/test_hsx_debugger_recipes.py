from __future__ import annotations

from dataclasses import FrozenInstanceError, fields as dataclass_fields, replace
from inspect import signature
from types import SimpleNamespace

import pytest

from hsx_debugger import *


ZERO = "0" * 64


def foundation() -> SimpleNamespace:
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
    code, data, bits = AddressSpaceId("code"), AddressSpaceId("data"), AddressSpaceId("bits")
    architecture = ArchitectureDescriptor(
        ArchitectureDescriptorRef("hsx.arch.vm-byte16-gpr32/1", ZERO),
        CanonicalUInt64(1), "hsx.fixed32/1", ByteOrder.LITTLE, ByteOrder.LITTLE,
        32, ByteOrder.LITTLE, 3,
        (
            AddressSpaceDescriptor(
                code, "byte", 8, 16, (HsxAddressRange(HsxAddress(code, 0), 0x10000),),
                ByteOrder.LITTLE, 4, WrapPolicy.FORBIDDEN,
                frozenset({Permission.READ, Permission.EXECUTE})
            ),
            AddressSpaceDescriptor(
                data, "byte", 8, 16, (HsxAddressRange(HsxAddress(data, 0), 0x10000),),
                ByteOrder.LITTLE, 1, WrapPolicy.FORBIDDEN,
                frozenset({Permission.READ, Permission.WRITE})
            ),
            AddressSpaceDescriptor(
                bits, "bit", 1, 16, (HsxAddressRange(HsxAddress(bits, 0), 0x10000),),
                ByteOrder.LITTLE, 1, WrapPolicy.FORBIDDEN, frozenset({Permission.READ})
            ),
        ),
        ("R0", "R1", "R7"), code, data, 8, 4
    )
    abi = AbiDescriptorRef("hsx.abi.llc-r7-word32/1", ZERO)
    generation = GenerationStamp("exec", 1, "opaque", 1, 1, 1, 7, EvidenceGrade.PORTABLE)
    stop = StopToken(target, image, "stop", 3)
    snapshot = InspectionSnapshotRef(
        target, image, stop, "snapshot", 3, 4,
        frozenset({"registers", "memory", "disassembly"}),
        SnapshotStability.IMMUTABLE, EvidenceGrade.PORTABLE
    )
    context = InspectionContext(
        target, image,
        EpochBinding(StopEpochId("epoch"), generation, stop, snapshot, EvidenceGrade.PORTABLE)
    )
    function = FunctionRecord(
        "fn", "fn", None, HsxAddressRange(HsxAddress(code, 0x20), 0x40), None
    )
    variable = SymbolRecord(
        "local", "local", SymbolKind.LOCAL, None, 2, "fn", "scope", None, 0
    )
    registers = RegisterSet((
        RegisterValue("R0", 32, 0x11223344, True),
        RegisterValue("R1", 32, 0x55667788, True),
        RegisterValue("R7", 32, None, False),
    ))
    frame = UnwindFrame(
        context, 0, HsxAddress(code, 0x20), HsxAddress(data, 0x100),
        HsxAddress(data, 0x108), registers, RegisterValue("PSW", 8, 0xA5, True),
        HsxAddress(data, 0x104), None, None, function, None, False, ()
    )
    evaluation = RecipeEvaluationContext(
        context, 0, binding, bundle, architecture, abi, frame.pc, frame.sp,
        RecipeScalar(False, 8, 0xA5), registers, frame.cfa, frame.frame_base
    )
    return SimpleNamespace(**locals())


class MemoryOnlyPort:
    def __init__(self, values=None):
        self.values = values or {}
        self.memory_reads = []
        self.register_reads = 0
        self.result_status = InspectionStatus.COMPLETE

    def read_registers(self, context, selection):
        self.register_reads += 1
        raise AssertionError("current-register fallback forbidden")

    def read_disassembly(self, context, address, instruction_count):
        raise AssertionError("disassembly read forbidden")

    def read_memory(self, context, address, byte_length):
        self.memory_reads.append((context, address, byte_length))
        if self.result_status is not InspectionStatus.COMPLETE:
            return InspectionResult(
                self.result_status, context, None,
                (Diagnostic("port_status", "injected", component="test"),)
            )
        raw = self.values.get((address.space.value, address.unsigned_value))
        if raw is None or len(raw) != byte_length:
            return InspectionResult(
                InspectionStatus.UNAVAILABLE, context, None,
                (Diagnostic("memory_missing", "missing", component="test"),)
            )
        block = MemoryBlock(
            address, byte_length,
            (MemorySegment(0, byte_length, raw, MemorySegmentStatus.COMPLETE),)
        )
        return InspectionResult(InspectionStatus.COMPLETE, context, block, ())


class IndexDouble:
    def __init__(self, f):
        self.f = f
        self.types = {}

    def binding(self):
        return self.f.binding

    def bundle_identity(self):
        return self.f.bundle

    def type_by_id(self, type_id):
        value = self.types.get(type_id)
        if value is None:
            return ResolutionResult(ResolutionStatus.UNAVAILABLE, self.f.binding, (), ())
        return ResolutionResult(ResolutionStatus.RESOLVED, self.f.binding, (value,), ())


def expr(role, ops, result, width):
    return RecipeExpression(role, tuple(ops), result, width)


def evaluate(f, recipe, port=None, budget=None, evaluation=None):
    return RecipeEvaluator.evaluate(
        evaluation or f.evaluation, recipe, port or MemoryOnlyPort(), RecipeLimits(),
        budget or RecipeBudget(64, 8, 128)
    )


def loc_row(f, form, bits=16, variable=None):
    variable = variable or f.variable
    return LocationRow(
        "loc", f.binding, variable.symbol_id, variable.lexical_scope_id,
        variable.function_id, HsxAddressRange(HsxAddress(f.code, 0x20), 4),
        variable.type_id, bits, f.abi, ByteOrder.LITTLE,
        FrameBinding.SELECTED_FRAME,
        RecipeSchemaRef("hsx.location-recipe/1", "3" * 64), form
    )


def loc_eval(f, row, *, frame=None, variable=None, port=None, index=None, request=None):
    return LocationEvaluator.evaluate(
        f.context, frame or f.frame, index or IndexDouble(f), variable or f.variable,
        row, port or MemoryOnlyPort(), f.architecture, f.abi, RecipeLimits(),
        request or RecipeRequestLimits(64, 16)
    )


def test_location_evaluator_keeps_exact_debug_artifact_index_annotation() -> None:
    parameter = signature(LocationEvaluator.evaluate).parameters["index"]
    assert parameter.annotation == "DebugArtifactIndex"


def test_dtos_enums_and_parser_are_frozen_exact_and_strict() -> None:
    parsed = RecipeParser.parse_expression({
        "role": "location",
        "opcodes": ({"opcode": "const_u", "value": 7, "bit_width": 8},),
        "required_result": "unsigned_scalar", "required_bit_width": 8,
    })
    with pytest.raises(FrozenInstanceError):
        parsed.required_bit_width = 16  # type: ignore[misc]
    assert ResolutionResult(
        ResolutionStatus.RESOLVED, None, (RecipeRole.CFA,), ()
    ).values == (RecipeRole.CFA,)
    for payload, status, code in (
        ({"opcode": "future"}, RecipeEvaluationStatus.UNSUPPORTED, "unsupported_opcode"),
        ({"opcode": "cfa", "future": 1}, RecipeEvaluationStatus.UNSUPPORTED, "unsupported_field"),
        ({"opcode": "const_u", "value": 1}, RecipeEvaluationStatus.CORRUPT, "missing_recipe_field"),
    ):
        with pytest.raises(RecipeParseError) as error:
            RecipeParser.parse_opcode(payload)
        assert (error.value.status, error.value.diagnostic.code) == (status, code)


def test_rule_and_form_cardinality_is_exact() -> None:
    value = expr(
        RecipeRole.LOCATION, (ConstUOp("const_u", 1, 8),),
        RecipeResultKind.UNSIGNED_SCALAR, 8
    )
    RecipeRule(RecipeRuleKind.EXPRESSION, value, None)
    RecipeRule(RecipeRuleKind.SAME, None, None)
    RecipeRule(RecipeRuleKind.UNAVAILABLE, None, "not saved")
    with pytest.raises(ValueError):
        RecipeRule(RecipeRuleKind.SAME, value, None)
    with pytest.raises(ValueError):
        RecipeRule(RecipeRuleKind.UNDEFINED, None, "unexpected")
    with pytest.raises(ValueError):
        RecipeRule(RecipeRuleKind.UNAVAILABLE, None, None)
    with pytest.raises(ValueError):
        RecipeRule(RecipeRuleKind.OPTIMIZED_OUT, None, None)
    with pytest.raises(ValueError):
        LocationForm(LocationKind.VALUE, value, (), "extra")
    with pytest.raises(ValueError):
        LocationForm(LocationKind.PIECES, None, (), None)


@pytest.mark.parametrize(
    "parser",
    (
        RecipeParser.parse_expression,
        RecipeParser.parse_rule,
        RecipeParser.parse_piece,
        RecipeParser.parse_location_form,
        RecipeParser.parse_unwind_row,
        RecipeParser.parse_location_row,
    ),
)
def test_every_parser_surface_rejects_unknown_fields_as_unsupported(parser) -> None:
    with pytest.raises(RecipeParseError) as error:
        parser({"future_mandatory_field": 1})
    assert (error.value.status, error.value.diagnostic.code) == (
        RecipeEvaluationStatus.UNSUPPORTED,
        "unsupported_field",
    )


def test_parser_unknown_enum_values_are_unsupported_and_terminals_round_trip() -> None:
    with pytest.raises(RecipeParseError) as special:
        RecipeParser.parse_opcode({"opcode": "special_value", "special": "FUTURE"})
    assert special.value.status is RecipeEvaluationStatus.UNSUPPORTED
    base = {
        "role": "future",
        "opcodes": (),
        "required_result": "unsigned_scalar",
        "required_bit_width": 8,
    }
    with pytest.raises(RecipeParseError) as role:
        RecipeParser.parse_expression(base)
    assert role.value.diagnostic.code == "unsupported_field_value"
    assert RecipeParser.parse_rule(
        {"kind": "unavailable", "expression": None, "reason": "not saved"}
    ) == RecipeRule(RecipeRuleKind.UNAVAILABLE, None, "not saved")
    assert RecipeParser.parse_location_form(
        {"kind": "optimized_out", "expression": None, "pieces": (), "reason": "folded"}
    ) == LocationForm(LocationKind.OPTIMIZED_OUT, None, (), "folded")


def test_unknown_row_schemas_are_unsupported_but_malformed_schema_fields_are_corrupt() -> None:
    f = foundation()
    unwind = unwind_row(f)
    location = loc_row(
        f,
        LocationForm(
            LocationKind.VALUE,
            expr(
                RecipeRole.LOCATION,
                (ConstUOp("const_u", 1, 16),),
                RecipeResultKind.UNSIGNED_SCALAR,
                16,
            ),
            (),
            None,
        ),
    )

    def unknown_schema(value: str) -> RecipeSchemaRef:
        schema = object.__new__(RecipeSchemaRef)
        object.__setattr__(schema, "schema", value)
        object.__setattr__(schema, "digest", ZERO)
        return schema

    unwind_payload = {
        field.name: getattr(unwind, field.name) for field in dataclass_fields(unwind)
    }
    location_payload = {
        field.name: getattr(location, field.name) for field in dataclass_fields(location)
    }
    for parser, payload, schema_name in (
        (RecipeParser.parse_unwind_row, unwind_payload, "hsx.unwind-recipe/2"),
        (RecipeParser.parse_location_row, location_payload, "hsx.location-recipe/2"),
    ):
        candidate = dict(payload)
        candidate["schema"] = unknown_schema(schema_name)
        with pytest.raises(RecipeParseError) as unsupported:
            parser(candidate)
        assert (
            unsupported.value.status,
            unsupported.value.diagnostic.code,
        ) == (
            RecipeEvaluationStatus.UNSUPPORTED,
            "unsupported_recipe_schema",
        )

        candidate["schema"] = schema_name
        with pytest.raises(RecipeParseError) as corrupt:
            parser(candidate)
        assert (
            corrupt.value.status,
            corrupt.value.diagnostic.code,
        ) == (
            RecipeEvaluationStatus.CORRUPT,
            "malformed_recipe_field",
        )


def test_profile_and_request_limit_dtos_keep_profile_vs_request_classification_separate() -> None:
    assert RecipeRequestLimits(65, 17) == RecipeRequestLimits(65, 17)
    with pytest.raises(ValueError):
        RecipeRequestLimits(0, 1)
    with pytest.raises(ValueError, match="exact accepted profile"):
        RecipeLimits(opcodes_per_expression=31)


def test_every_recipe_integer_field_rejects_bool_and_float_exactly() -> None:
    f = foundation()
    scalar_expression = expr(
        RecipeRole.LOCATION,
        (ConstUOp("const_u", 1, 8),),
        RecipeResultKind.UNSIGNED_SCALAR,
        8,
    )
    piece = LocationPieceRule(0, 1, scalar_expression, 0)
    for bad in (True, 1.0):
        factories = (
            lambda: ConstUOp("const_u", bad, 8),
            lambda: ConstUOp("const_u", 1, bad),
            lambda: ConstSOp("const_s", bad, 8),
            lambda: ConstSOp("const_s", 1, bad),
            lambda: AddSConstCheckedOp("add_sconst_checked", bad),
            lambda: DerefUOp("deref_u", bad, ByteOrder.LITTLE),
            lambda: BitSliceOp("bit_slice", bad, 1),
            lambda: BitSliceOp("bit_slice", 0, bad),
            lambda: replace(scalar_expression, required_bit_width=bad),
            lambda: replace(piece, destination_bit_offset=bad),
            lambda: replace(piece, bit_size=bad),
            lambda: replace(piece, source_bit_offset=bad),
            lambda: RecipeScalar(False, bad, 0),
            lambda: RecipeScalar(False, 8, bad),
            lambda: RecipeRegister("R0", bad, 0),
            lambda: RecipeRegister("R0", 32, bad),
            lambda: replace(f.evaluation, frame_index=bad),
            lambda: RecipeBudget(bad, 1, 1),
            lambda: RecipeBudget(1, bad, 1),
            lambda: RecipeBudget(1, 1, bad),
            lambda: RecipeRequestLimits(bad, 1),
            lambda: RecipeRequestLimits(1, bad),
            lambda: replace(unwind_row(f), call_site_adjustment=bad),
            lambda: replace(
                loc_row(
                    f,
                    LocationForm(LocationKind.PIECES, None, (piece,), None),
                    bits=1,
                ),
                declared_bit_size=bad,
            ),
            lambda: replace(f.frame, frame_index=bad),
        )
        for factory in factories:
            with pytest.raises((TypeError, ValueError)):
                factory()

    accepted = RecipeLimits()
    accepted_values = {
        field.name: getattr(accepted, field.name) for field in dataclass_fields(accepted)
    }
    for field_name, value in accepted_values.items():
        for bad in (True, float(value)):
            candidate = dict(accepted_values)
            candidate[field_name] = bad
            with pytest.raises((TypeError, ValueError)):
                RecipeLimits(**candidate)


def test_all_opcode_success_paths_preserve_exact_kind_width_and_signedness() -> None:
    f = foundation()
    port = MemoryOnlyPort({("data", 0x120): b"\x34\x12"})
    cases = (
        (expr(RecipeRole.LOCATION, (RegValueOp("reg_value", "R0"),), RecipeResultKind.REGISTER, 32), RecipeRegister("R0", 32, 0x11223344)),
        (expr(RecipeRole.LOCATION, (SpecialValueOp("special_value", RecipeSpecial.PC),), RecipeResultKind.ADDRESS, None), RecipeAddress(f.frame.pc)),
        (expr(RecipeRole.LOCATION, (SpecialValueOp("special_value", RecipeSpecial.SP),), RecipeResultKind.ADDRESS, None), RecipeAddress(f.frame.sp)),
        (expr(RecipeRole.LOCATION, (SpecialValueOp("special_value", RecipeSpecial.PSW),), RecipeResultKind.UNSIGNED_SCALAR, 8), RecipeScalar(False, 8, 0xA5)),
        (expr(RecipeRole.LOCATION, (ConstUOp("const_u", 255, 8),), RecipeResultKind.UNSIGNED_SCALAR, 8), RecipeScalar(False, 8, 255)),
        (expr(RecipeRole.LOCATION, (ConstSOp("const_s", -2, 8),), RecipeResultKind.SIGNED_SCALAR, 8), RecipeScalar(True, 8, -2)),
        (expr(RecipeRole.LOCATION, (StaticAddressOp("static_address", HsxAddress(f.data, 0x120)),), RecipeResultKind.ADDRESS, None), RecipeAddress(HsxAddress(f.data, 0x120))),
        (expr(RecipeRole.LOCATION, (ConstUOp("const_u", 0x120, 16), ToAddressOp("to_address", f.data)), RecipeResultKind.ADDRESS, None), RecipeAddress(HsxAddress(f.data, 0x120))),
        (expr(RecipeRole.LOCATION, (CfaOp("cfa"),), RecipeResultKind.ADDRESS, None), RecipeAddress(f.frame.cfa)),
        (expr(RecipeRole.LOCATION, (FrameBaseOp("frame_base"),), RecipeResultKind.ADDRESS, None), RecipeAddress(f.frame.frame_base)),
        (expr(RecipeRole.LOCATION, (StaticAddressOp("static_address", HsxAddress(f.data, 0x120)), AddSConstCheckedOp("add_sconst_checked", -0x20)), RecipeResultKind.ADDRESS, None), RecipeAddress(HsxAddress(f.data, 0x100))),
        (expr(RecipeRole.LOCATION, (ConstSOp("const_s", -4, 8), AddSConstCheckedOp("add_sconst_checked", 2)), RecipeResultKind.SIGNED_SCALAR, 8), RecipeScalar(True, 8, -2)),
        (expr(RecipeRole.LOCATION, (StaticAddressOp("static_address", HsxAddress(f.data, 0x120)), DerefUOp("deref_u", 2, ByteOrder.LITTLE)), RecipeResultKind.UNSIGNED_SCALAR, 16), RecipeScalar(False, 16, 0x1234)),
        (expr(RecipeRole.LOCATION, (ConstSOp("const_s", -1, 8), BitSliceOp("bit_slice", 4, 4)), RecipeResultKind.UNSIGNED_SCALAR, 4), RecipeScalar(False, 4, 15)),
    )
    for recipe, expected in cases:
        result = evaluate(f, recipe, port)
        assert (result.status, result.value) == (RecipeEvaluationStatus.COMPLETE, expected)
    assert port.register_reads == 0


@pytest.mark.parametrize("recipe,code", (
    (expr(RecipeRole.LOCATION, (), RecipeResultKind.UNSIGNED_SCALAR, 8), "invalid_final_stack"),
    (expr(RecipeRole.LOCATION, (ConstUOp("const_u", 1, 8), ConstUOp("const_u", 2, 8)), RecipeResultKind.UNSIGNED_SCALAR, 8), "invalid_final_stack"),
    (expr(RecipeRole.LOCATION, (AddSConstCheckedOp("add_sconst_checked", 1),), RecipeResultKind.UNSIGNED_SCALAR, 8), "recipe_stack_underflow"),
    (expr(RecipeRole.LOCATION, (SpecialValueOp("special_value", RecipeSpecial.PC), BitSliceOp("bit_slice", 0, 1)), RecipeResultKind.UNSIGNED_SCALAR, 1), "recipe_type_mismatch"),
    (expr(RecipeRole.LOCATION, (ConstUOp("const_u", 256, 8),), RecipeResultKind.UNSIGNED_SCALAR, 8), "invalid_scalar"),
    (expr(RecipeRole.LOCATION, (ConstSOp("const_s", -1, 8), ToAddressOp("to_address", AddressSpaceId("data"))), RecipeResultKind.ADDRESS, None), "negative_address"),
    (expr(RecipeRole.LOCATION, (ConstUOp("const_u", 1, 8), BitSliceOp("bit_slice", 7, 2)), RecipeResultKind.UNSIGNED_SCALAR, 2), "invalid_bit_slice"),
    (expr(RecipeRole.LOCATION, (ConstUOp("const_u", 1, 8),), RecipeResultKind.SIGNED_SCALAR, 8), "recipe_result_mismatch"),
    (expr(RecipeRole.CFA, (CfaOp("cfa"),), RecipeResultKind.ADDRESS, None), "cyclic_cfa"),
))
def test_stack_type_width_address_role_failures_are_corrupt(recipe, code) -> None:
    result = evaluate(foundation(), recipe)
    assert (result.status, result.diagnostics[0].code) == (RecipeEvaluationStatus.CORRUPT, code)


def test_pure_postfix_validator_matches_runtime_failure_classification() -> None:
    f = foundation()
    cases = (
        expr(RecipeRole.LOCATION, (), RecipeResultKind.UNSIGNED_SCALAR, 8),
        expr(
            RecipeRole.LOCATION,
            (ConstUOp("const_u", 1, 8), ConstUOp("const_u", 2, 8)),
            RecipeResultKind.UNSIGNED_SCALAR,
            8,
        ),
        expr(
            RecipeRole.LOCATION,
            (AddSConstCheckedOp("add_sconst_checked", 1),),
            RecipeResultKind.UNSIGNED_SCALAR,
            8,
        ),
        expr(
            RecipeRole.LOCATION,
            (
                SpecialValueOp("special_value", RecipeSpecial.PC),
                BitSliceOp("bit_slice", 0, 1),
            ),
            RecipeResultKind.UNSIGNED_SCALAR,
            1,
        ),
        expr(
            RecipeRole.LOCATION,
            (ConstUOp("const_u", 256, 8),),
            RecipeResultKind.UNSIGNED_SCALAR,
            8,
        ),
        expr(
            RecipeRole.LOCATION,
            (
                ConstSOp("const_s", -1, 8),
                ToAddressOp("to_address", f.data),
            ),
            RecipeResultKind.ADDRESS,
            None,
        ),
        expr(
            RecipeRole.LOCATION,
            (ConstUOp("const_u", 1, 8), BitSliceOp("bit_slice", 7, 2)),
            RecipeResultKind.UNSIGNED_SCALAR,
            2,
        ),
        expr(
            RecipeRole.LOCATION,
            (ConstUOp("const_u", 1, 8),),
            RecipeResultKind.SIGNED_SCALAR,
            8,
        ),
        expr(
            RecipeRole.LOCATION,
            (ConstUOp("const_u", 1, 8),) * 9,
            RecipeResultKind.UNSIGNED_SCALAR,
            8,
        ),
    )
    for recipe in cases:
        diagnostics = RecipeComponentValidator.validate_expression(
            recipe, RecipeRole.LOCATION, f.architecture
        )
        runtime = evaluate(f, recipe)
        assert diagnostics
        assert (
            runtime.status,
            runtime.diagnostics[0].code,
        ) == (
            RecipeEvaluationStatus.CORRUPT,
            diagnostics[0].code,
        )

    wrong_role_space = expr(
        RecipeRole.CALLER_PC,
        (SpecialValueOp("special_value", RecipeSpecial.SP),),
        RecipeResultKind.ADDRESS,
        None,
    )
    diagnostics = RecipeComponentValidator.validate_expression(
        wrong_role_space, RecipeRole.CALLER_PC, f.architecture
    )
    runtime = evaluate(f, wrong_role_space)
    assert (
        diagnostics[0].code,
        runtime.status,
        runtime.diagnostics[0].code,
    ) == (
        "recipe_result_mismatch",
        RecipeEvaluationStatus.CORRUPT,
        "recipe_result_mismatch",
    )


def test_pure_validator_enforces_dereference_and_aggregate_location_limits() -> None:
    f = foundation()

    def dereference_chain(count: int) -> RecipeExpression:
        operations = [StaticAddressOp("static_address", HsxAddress(f.data, 0x120))]
        for index in range(count):
            operations.append(DerefUOp("deref_u", 16, ByteOrder.LITTLE))
            if index + 1 < count:
                operations.append(ToAddressOp("to_address", f.data))
        return expr(
            RecipeRole.LOCATION,
            operations,
            RecipeResultKind.UNSIGNED_SCALAR,
            128,
        )

    over_dereferenced = dereference_chain(5)
    pure = RecipeComponentValidator.validate_expression(
        over_dereferenced, RecipeRole.LOCATION, f.architecture
    )
    port = MemoryOnlyPort(
        {
            ("data", 0x120): bytes(16),
            ("data", 0): bytes(16),
        }
    )
    runtime = evaluate(f, over_dereferenced, port)
    assert (pure[0].code, runtime.status, runtime.diagnostics[0].code) == (
        "limit_exceeded",
        RecipeEvaluationStatus.UNSUPPORTED,
        "limit_exceeded",
    )
    assert len(port.memory_reads) == 4

    pieces = tuple(
        LocationPieceRule(index, 1, dereference_chain(4), 0) for index in range(9)
    )
    aggregate_row = loc_row(
        f, LocationForm(LocationKind.PIECES, None, pieces, None), bits=9
    )
    aggregate = RecipeComponentValidator.validate_location_row(
        aggregate_row, f.variable, f.architecture, f.abi
    )
    assert aggregate[0].code == "limit_exceeded"
    aggregate_port = MemoryOnlyPort()
    aggregate_runtime = loc_eval(
        f,
        aggregate_row,
        port=aggregate_port,
        request=RecipeRequestLimits(64, 9),
    )
    assert (
        aggregate_runtime.status,
        aggregate_runtime.diagnostics[0].code,
        aggregate_port.memory_reads,
    ) == (InspectionStatus.UNSUPPORTED, "limit_exceeded", [])

    address_operations = [
        StaticAddressOp("static_address", HsxAddress(f.data, 0x120))
    ]
    for _ in range(4):
        address_operations.extend(
            (
                DerefUOp("deref_u", 16, ByteOrder.LITTLE),
                ToAddressOp("to_address", f.data),
            )
        )
    address_row = loc_row(
        f,
        LocationForm(
            LocationKind.ADDRESS,
            expr(
                RecipeRole.LOCATION,
                address_operations,
                RecipeResultKind.ADDRESS,
                None,
            ),
            (),
            None,
        ),
        bits=4096,
    )
    assert RecipeComponentValidator.validate_location_row(
        address_row, f.variable, f.architecture, f.abi
    )[0].code == "limit_exceeded"

    seventeen = tuple(
        LocationPieceRule(
            index,
            1,
            expr(
                RecipeRole.LOCATION,
                (ConstUOp("const_u", index & 1, 1),),
                RecipeResultKind.UNSIGNED_SCALAR,
                1,
            ),
            0,
        )
        for index in range(17)
    )
    piece_row = loc_row(
        f, LocationForm(LocationKind.PIECES, None, seventeen, None), bits=17
    )
    assert RecipeComponentValidator.validate_location_row(
        piece_row, f.variable, f.architecture, f.abi
    )[0].code == "limit_exceeded"


def test_unavailable_evidence_never_falls_back_and_cfa_absence_is_corrupt() -> None:
    f, port = foundation(), MemoryOnlyPort()
    unavailable = expr(RecipeRole.LOCATION, (RegValueOp("reg_value", "R7"),), RecipeResultKind.REGISTER, 32)
    assert evaluate(f, unavailable, port).status is RecipeEvaluationStatus.UNAVAILABLE
    psw = expr(RecipeRole.LOCATION, (SpecialValueOp("special_value", RecipeSpecial.PSW),), RecipeResultKind.UNSIGNED_SCALAR, 8)
    assert evaluate(f, psw, port, evaluation=replace(f.evaluation, frame_index=1, psw=None)).status is RecipeEvaluationStatus.UNAVAILABLE
    base = expr(RecipeRole.LOCATION, (FrameBaseOp("frame_base"),), RecipeResultKind.ADDRESS, None)
    assert evaluate(f, base, port, evaluation=replace(f.evaluation, frame_base=None)).status is RecipeEvaluationStatus.UNAVAILABLE
    cfa = expr(RecipeRole.LOCATION, (CfaOp("cfa"),), RecipeResultKind.ADDRESS, None)
    result = evaluate(f, cfa, port, evaluation=replace(f.evaluation, cfa=None))
    assert (result.status, result.diagnostics[0].code) == (RecipeEvaluationStatus.CORRUPT, "cfa_not_computed")
    assert port.register_reads == 0


def test_all_bound_exhaustion_is_unsupported_limit_exceeded() -> None:
    f = foundation()
    const = expr(RecipeRole.LOCATION, (ConstUOp("const_u", 1, 8),), RecipeResultKind.UNSIGNED_SCALAR, 8)
    results = [evaluate(f, const, budget=RecipeBudget(0, 1, 4))]
    results.append(evaluate(f, expr(RecipeRole.LOCATION, (ConstUOp("const_u", 1, 8),) * 33, RecipeResultKind.UNSIGNED_SCALAR, 8)))
    deref = expr(
        RecipeRole.LOCATION,
        (StaticAddressOp("static_address", HsxAddress(f.data, 0x120)), DerefUOp("deref_u", 2, ByteOrder.LITTLE)),
        RecipeResultKind.UNSIGNED_SCALAR, 16
    )
    port = MemoryOnlyPort({("data", 0x120): b"\0\0"})
    results.extend((
        evaluate(f, deref, port, RecipeBudget(8, 0, 8)),
        evaluate(f, deref, port, RecipeBudget(8, 1, 1)),
    ))
    assert all((item.status, item.diagnostics[0].code) == (RecipeEvaluationStatus.UNSUPPORTED, "limit_exceeded") for item in results)


@pytest.mark.parametrize("port_status,expected", (
    (InspectionStatus.UNAVAILABLE, RecipeEvaluationStatus.UNAVAILABLE),
    (InspectionStatus.STALE, RecipeEvaluationStatus.STALE),
    (InspectionStatus.ARTIFACT_MISMATCH, RecipeEvaluationStatus.ARTIFACT_MISMATCH),
    (InspectionStatus.UNSUPPORTED, RecipeEvaluationStatus.UNSUPPORTED),
    (InspectionStatus.CORRUPT, RecipeEvaluationStatus.CORRUPT),
))
def test_snapshot_outcomes_are_preserved_and_only_memory_is_called(port_status, expected) -> None:
    f, port = foundation(), MemoryOnlyPort()
    port.result_status = port_status
    recipe = expr(
        RecipeRole.LOCATION,
        (StaticAddressOp("static_address", HsxAddress(f.data, 0x120)), DerefUOp("deref_u", 1, ByteOrder.LITTLE)),
        RecipeResultKind.UNSIGNED_SCALAR, 8
    )
    assert evaluate(f, recipe, port).status is expected
    assert (len(port.memory_reads), port.register_reads) == (1, 0)


def test_binding_is_validated_before_opcode_read_or_budget_consumption() -> None:
    f = foundation()
    bad = replace(f.evaluation, binding=replace(f.binding, binding_digest="f" * 64))
    port = MemoryOnlyPort({("data", 0x120): b"\0"})
    recipe = expr(
        RecipeRole.LOCATION,
        (StaticAddressOp("static_address", HsxAddress(f.data, 0x120)), DerefUOp("deref_u", 1, ByteOrder.LITTLE)),
        RecipeResultKind.UNSIGNED_SCALAR, 8
    )
    budget = RecipeBudget(7, 3, 9)
    result = RecipeEvaluator.evaluate(bad, recipe, port, RecipeLimits(), budget)
    assert (result.status, result.budget_after, port.memory_reads) == (
        RecipeEvaluationStatus.ARTIFACT_MISMATCH, budget, []
    )


def unwind_row(f, rules=None):
    cfa = expr(RecipeRole.CFA, (SpecialValueOp("special_value", RecipeSpecial.SP),), RecipeResultKind.ADDRESS, None)
    pc = expr(RecipeRole.CALLER_PC, (SpecialValueOp("special_value", RecipeSpecial.PC),), RecipeResultKind.ADDRESS, None)
    sp = expr(RecipeRole.CALLER_SP, (SpecialValueOp("special_value", RecipeSpecial.SP),), RecipeResultKind.ADDRESS, None)
    return UnwindRow(
        "uw", f.binding, HsxAddressRange(HsxAddress(f.code, 0x20), 4), f.abi,
        RecipeSchemaRef("hsx.unwind-recipe/1", "2" * 64), cfa,
        RecipeRule(RecipeRuleKind.EXPRESSION, pc, None),
        RecipeRule(RecipeRuleKind.EXPRESSION, sp, None), None,
        rules if rules is not None else (("R7", RecipeRule(RecipeRuleKind.SAME, None, None)),),
        UnwindBoundary.ORDINARY, -4
    )


def test_row_validator_accepts_explicit_unavailable_gpr_evidence_and_rejects_psw_key() -> None:
    f = foundation()
    assert RecipeComponentValidator.validate_unwind_row(unwind_row(f), f.architecture, f.abi) == ()
    wrong = replace(unwind_row(f), cfa_expression=replace(unwind_row(f).cfa_expression, role=RecipeRole.LOCATION))
    assert RecipeComponentValidator.validate_unwind_row(wrong, f.architecture, f.abi)[0].code == "recipe_role_mismatch"
    wrong_pc_space = replace(
        unwind_row(f),
        caller_pc_rule=RecipeRule(
            RecipeRuleKind.EXPRESSION,
            expr(
                RecipeRole.CALLER_PC,
                (SpecialValueOp("special_value", RecipeSpecial.SP),),
                RecipeResultKind.ADDRESS,
                None,
            ),
            None,
        ),
    )
    assert RecipeComponentValidator.validate_unwind_row(
        wrong_pc_space, f.architecture, f.abi
    )[0].code == "recipe_result_mismatch"
    wrong_register = unwind_row(
        f,
        (
            (
                "R7",
                RecipeRule(
                    RecipeRuleKind.EXPRESSION,
                    expr(
                        RecipeRole.REGISTER,
                        (RegValueOp("reg_value", "R0"),),
                        RecipeResultKind.REGISTER,
                        32,
                    ),
                    None,
                ),
            ),
        ),
    )
    assert RecipeComponentValidator.validate_unwind_row(
        wrong_register, f.architecture, f.abi
    )[0].code == "invalid_register_rule_result"
    for rule in (
        RecipeRule(RecipeRuleKind.UNDEFINED, None, None),
        RecipeRule(RecipeRuleKind.UNAVAILABLE, None, "not recoverable"),
        RecipeRule(RecipeRuleKind.OPTIMIZED_OUT, None, "not materialized"),
    ):
        unavailable = unwind_row(f, (("R7", rule),))
        assert RecipeComponentValidator.validate_unwind_row(
            unavailable, f.architecture, f.abi
        ) == ()
    psw = unwind_row(f, (("PSW", RecipeRule(RecipeRuleKind.SAME, None, None)),))
    assert RecipeComponentValidator.validate_unwind_row(psw, f.architecture, f.abi)[0].code == "psw_rule_unsupported"
    pc = unwind_row(f, (("PC", RecipeRule(RecipeRuleKind.SAME, None, None)),))
    assert RecipeComponentValidator.validate_unwind_row(pc, f.architecture, f.abi)[0].code == "special_register_rule_forbidden"


def test_recovered_frame_validation_matrix_is_architecture_complete() -> None:
    f = foundation()
    assert RecipeComponentValidator.validate_unwind_frame(f.frame, f.architecture) == ()
    cases = (
        (replace(f.frame, recovered_registers=RegisterSet(tuple(reversed(f.registers.registers)))), "invalid_recovered_register_order"),
        (replace(f.frame, recovered_registers=RegisterSet((RegisterValue("R0", 16, 1, True), *f.registers.registers[1:]))), "invalid_recovered_register_width"),
        (replace(f.frame, recovered_registers=RegisterSet((*f.registers.registers, RegisterValue("PSW", 8, 1, True)))), "invalid_recovered_register_order"),
        (replace(f.frame, recovered_psw=RegisterValue("FLAGS", 8, 1, True)), "invalid_recovered_psw"),
        (replace(f.frame, frame_index=1), "psw_rule_unsupported"),
    )
    for candidate, code in cases:
        assert RecipeComponentValidator.validate_unwind_frame(candidate, f.architecture)[0].code == code
    non_top = replace(f.frame, frame_index=1, recovered_psw=RegisterValue("PSW", 8, None, False))
    assert RecipeComponentValidator.validate_unwind_frame(non_top, f.architecture) == ()


def test_location_value_address_terminals_and_non_top_register_use_frame_only() -> None:
    f = foundation()
    port = MemoryOnlyPort({("data", 0x120): b"\x34\x12"})
    signed = expr(RecipeRole.LOCATION, (ConstSOp("const_s", -2, 16),), RecipeResultKind.SIGNED_SCALAR, 16)
    result = loc_eval(f, loc_row(f, LocationForm(LocationKind.VALUE, signed, (), None)), port=port)
    assert result.value.raw_bytes == b"\xfe\xff"
    address = expr(RecipeRole.LOCATION, (StaticAddressOp("static_address", HsxAddress(f.data, 0x120)),), RecipeResultKind.ADDRESS, None)
    result = loc_eval(f, loc_row(f, LocationForm(LocationKind.ADDRESS, address, (), None)), port=port)
    assert result.value.raw_bytes == b"\x34\x12"
    non_top = replace(f.frame, frame_index=1, recovered_psw=RegisterValue("PSW", 8, None, False))
    register = expr(RecipeRole.LOCATION, (RegValueOp("reg_value", "R1"),), RecipeResultKind.REGISTER, 32)
    result = loc_eval(f, loc_row(f, LocationForm(LocationKind.VALUE, register, (), None), 32), frame=non_top, port=port)
    assert result.value.raw_bytes == b"\x88\x77\x66\x55"
    assert port.register_reads == 0
    optimized = loc_eval(f, loc_row(f, LocationForm(LocationKind.OPTIMIZED_OUT, None, (), "folded")))
    unavailable = loc_eval(f, loc_row(f, LocationForm(LocationKind.UNAVAILABLE, None, (), "not saved")))
    assert optimized.value.location_status is ValueAvailability.OPTIMIZED_OUT
    assert unavailable.value.location_status is ValueAvailability.UNAVAILABLE


def test_location_pieces_assemble_or_expose_exact_missing_ranges() -> None:
    f = foundation()
    low = LocationPieceRule(
        0, 8, expr(RecipeRole.LOCATION, (ConstUOp("const_u", 0x12, 8),), RecipeResultKind.UNSIGNED_SCALAR, 8), 0
    )
    high = LocationPieceRule(
        8, 8, expr(RecipeRole.LOCATION, (ConstUOp("const_u", 0x34, 8),), RecipeResultKind.UNSIGNED_SCALAR, 8), 0
    )
    complete = loc_eval(f, loc_row(f, LocationForm(LocationKind.PIECES, None, (low, high), None)))
    assert (complete.status, complete.value.raw_bytes, complete.value.pieces) == (
        InspectionStatus.COMPLETE, b"\x12\x34", ()
    )
    partial = loc_eval(f, loc_row(f, LocationForm(LocationKind.PIECES, None, (low,), None)))
    assert (partial.status, partial.value.location_status) == (
        InspectionStatus.PARTIAL, ValueAvailability.PARTIAL
    )
    assert [(p.destination_bit_offset, p.bit_size, p.status) for p in partial.value.pieces] == [
        (0, 8, ValuePieceStatus.AVAILABLE), (8, 8, ValuePieceStatus.UNAVAILABLE)
    ]


def test_location_piece_request_and_profile_exhaustion_are_unsupported_limit_exceeded() -> None:
    f = foundation()
    pieces = tuple(
        LocationPieceRule(
            offset,
            1,
            expr(
                RecipeRole.LOCATION,
                (ConstUOp("const_u", offset & 1, 1),),
                RecipeResultKind.UNSIGNED_SCALAR,
                1,
            ),
            0,
        )
        for offset in range(17)
    )
    two_piece_row = loc_row(
        f, LocationForm(LocationKind.PIECES, None, pieces[:2], None), bits=2
    )
    request_result = loc_eval(
        f, two_piece_row, request=RecipeRequestLimits(64, 1)
    )
    profile_row = loc_row(
        f, LocationForm(LocationKind.PIECES, None, pieces, None), bits=17
    )
    profile_result = loc_eval(
        f, profile_row, request=RecipeRequestLimits(64, 17)
    )
    for result in (request_result, profile_result):
        assert (result.status, result.diagnostics[0].code) == (
            InspectionStatus.UNSUPPORTED,
            "limit_exceeded",
        )


def test_location_context_binding_frame_and_request_fail_before_read() -> None:
    f = foundation()
    port = MemoryOnlyPort()
    value = expr(RecipeRole.LOCATION, (ConstUOp("const_u", 1, 16),), RecipeResultKind.UNSIGNED_SCALAR, 16)
    row = loc_row(f, LocationForm(LocationKind.VALUE, value, (), None))
    other_snapshot = replace(f.context.epoch.snapshot, snapshot_token="other")
    other_context = replace(f.context, epoch=replace(f.context.epoch, snapshot=other_snapshot))
    stale = LocationEvaluator.evaluate(
        other_context, f.frame, IndexDouble(f), f.variable, row, port,
        f.architecture, f.abi, RecipeLimits(), RecipeRequestLimits(64, 16)
    )
    assert stale.status is InspectionStatus.STALE
    bad_frame = replace(f.frame, recovered_registers=RegisterSet(tuple(reversed(f.registers.registers))))
    assert loc_eval(f, row, frame=bad_frame, port=port).status is InspectionStatus.CORRUPT
    assert loc_eval(f, row, port=port, request=RecipeRequestLimits(65, 16)).status is InspectionStatus.UNSUPPORTED
    bad_index = IndexDouble(f)
    bad_index.f = SimpleNamespace(binding=replace(f.binding, binding_digest="f" * 64), bundle=f.bundle)
    assert loc_eval(f, row, index=bad_index, port=port).status is InspectionStatus.ARTIFACT_MISMATCH
    assert port.memory_reads == []
