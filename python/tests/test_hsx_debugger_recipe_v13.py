from __future__ import annotations

import pytest

from hsx_debugger import (
    AbiDescriptorRef,
    AddSConstCheckedOp,
    AddressSpaceDescriptor,
    AddressSpaceId,
    ArchitectureDescriptor,
    ArchitectureDescriptorRef,
    ByteOrder,
    CanonicalUInt64,
    CfaOp,
    ConstSOp,
    ConstUOp,
    DerefUOp,
    HsxAddress,
    HsxAddressRange,
    ImageDebugBinding,
    Permission,
    RecipeComponentValidator,
    RecipeExpression,
    RecipeLimits,
    RecipeParseError,
    RecipeParser,
    RecipeResultKind,
    RecipeRole,
    RecipeRule,
    RecipeRuleKind,
    RecipeSchemaRef,
    RegValueOp,
    SpecialValueOp,
    RecipeSpecial,
    UnwindBoundary,
    UnwindRow,
    WrapPolicy,
)


ZERO = "0" * 64


def _architecture() -> ArchitectureDescriptor:
    code = AddressSpaceId("code")
    data = AddressSpaceId("data")
    return ArchitectureDescriptor(
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
                (HsxAddressRange(HsxAddress(code, 0), 0x10000),),
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
                (HsxAddressRange(HsxAddress(data, 0), 0x10000),),
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


def _expression(
    role: RecipeRole,
    opcodes: tuple,
    result: RecipeResultKind,
    width: int | None,
) -> RecipeExpression:
    return RecipeExpression(role, opcodes, result, width)


def _row(register_id: str, expression: RecipeExpression) -> tuple[UnwindRow, ArchitectureDescriptor, AbiDescriptorRef]:
    architecture = _architecture()
    abi = AbiDescriptorRef("hsx.abi.llc-r7-word32/1", ZERO)
    binding = object.__new__(ImageDebugBinding)
    cfa = _expression(
        RecipeRole.CFA,
        (SpecialValueOp("special_value", RecipeSpecial.SP),),
        RecipeResultKind.ADDRESS,
        None,
    )
    caller_pc = _expression(
        RecipeRole.CALLER_PC,
        (SpecialValueOp("special_value", RecipeSpecial.PC),),
        RecipeResultKind.ADDRESS,
        None,
    )
    caller_sp = _expression(
        RecipeRole.CALLER_SP,
        (SpecialValueOp("special_value", RecipeSpecial.SP),),
        RecipeResultKind.ADDRESS,
        None,
    )
    row = UnwindRow(
        "uw-v13",
        binding,
        HsxAddressRange(HsxAddress(architecture.pc_space, 0x20), 4),
        abi,
        RecipeSchemaRef("hsx.unwind-recipe/1", "2" * 64),
        cfa,
        RecipeRule(RecipeRuleKind.EXPRESSION, caller_pc, None),
        RecipeRule(RecipeRuleKind.EXPRESSION, caller_sp, None),
        None,
        ((register_id, RecipeRule(RecipeRuleKind.EXPRESSION, expression, None)),),
        UnwindBoundary.ORDINARY,
        -4,
    )
    return row, architecture, abi


def _validate(register_id: str, expression: RecipeExpression):
    row, architecture, abi = _row(register_id, expression)
    return RecipeComponentValidator.validate_unwind_row(
        row, architecture, abi, RecipeLimits()
    )


def test_v13_accepts_exact_width_unsigned_scalar_bound_by_row_key() -> None:
    expression = _expression(
        RecipeRole.REGISTER,
        (
            CfaOp("cfa"),
            AddSConstCheckedOp("add_sconst_checked", -8),
            DerefUOp("deref_u", 4, ByteOrder.LITTLE),
        ),
        RecipeResultKind.UNSIGNED_SCALAR,
        32,
    )
    assert _validate("R7", expression) == ()


def test_v13_preserves_exact_register_identity_for_register_results() -> None:
    matching = _expression(
        RecipeRole.REGISTER,
        (RegValueOp("reg_value", "R7"),),
        RecipeResultKind.REGISTER,
        32,
    )
    assert _validate("R7", matching) == ()

    mismatched = _expression(
        RecipeRole.REGISTER,
        (RegValueOp("reg_value", "R0"),),
        RecipeResultKind.REGISTER,
        32,
    )
    diagnostics = _validate("R7", mismatched)
    assert diagnostics[0].code == "invalid_register_rule_result"


@pytest.mark.parametrize(
    "expression",
    (
        _expression(
            RecipeRole.REGISTER,
            (ConstSOp("const_s", 1, 32),),
            RecipeResultKind.SIGNED_SCALAR,
            32,
        ),
        _expression(
            RecipeRole.REGISTER,
            (ConstUOp("const_u", 1, 16),),
            RecipeResultKind.UNSIGNED_SCALAR,
            16,
        ),
        _expression(
            RecipeRole.REGISTER,
            (CfaOp("cfa"),),
            RecipeResultKind.ADDRESS,
            None,
        ),
    ),
)
def test_v13_rejects_signed_wrong_width_and_address_gpr_results(expression) -> None:
    diagnostics = _validate("R7", expression)
    assert diagnostics[0].code == "invalid_register_rule_result"


def test_v13_does_not_add_to_register_opcode() -> None:
    with pytest.raises(RecipeParseError) as error:
        RecipeParser.parse_opcode({"opcode": "to_register", "register_id": "R7"})
    assert error.value.diagnostic.code == "unsupported_opcode"
