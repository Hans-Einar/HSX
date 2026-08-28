# RF-004 v1.3 corrective patch plan

Status: **MASTER PREPARED / BLOCKED ON READ-ONLY TESTER FEASIBILITY**

Consumes:

- Steering decision: issue #38 comment `5374100772`
- v1.3 conformance: `010--RF004_Register_Rule_Result_Conformance_v1_3.md`
- read-only probe: `012--RF004_v1_3_ReadOnly_Feasibility_Probe.md`

## Intended product delta after tester PASS

The corrective implementation is deliberately narrow.

### `python/hsx_debugger/recipes.py`

Within `RecipeComponentValidator.validate_unwind_row` only:

1. For a keyed GPR `EXPRESSION`, call `_validate_postfix_expression(... required_register_id=register_id)` only when `expression.required_result is RecipeResultKind.REGISTER`.
2. When `expression.required_result is RecipeResultKind.UNSIGNED_SCALAR`, call the same pure validator without `required_register_id`; the row key supplies register identity.
3. Accept only `{REGISTER, UNSIGNED_SCALAR}` and require `expression.required_bit_width == architecture.register_width_bits`.
4. Preserve all existing role, opcode, address, budget, parser, and evaluator behavior.
5. Do not add or alter recipe opcodes.

Conceptual replacement:

```python
required_register_id = (
    register_id
    if expression.required_result is RecipeResultKind.REGISTER
    else None
)
validation = _validate_postfix_expression(
    expression,
    RecipeRole.REGISTER,
    architecture,
    limits,
    row_id=row.row_id,
    required_register_id=required_register_id,
)
...
if (
    expression.required_result
    not in {RecipeResultKind.REGISTER, RecipeResultKind.UNSIGNED_SCALAR}
    or expression.required_bit_width != architecture.register_width_bits
):
    return invalid_register_rule_result
```

### Tests

Add v1.3 focused cases proving:

- keyed `R7` + `cfa/-8/deref_u(4,little)` + `UNSIGNED_SCALAR/32` validates;
- runtime evaluator returns `RecipeScalar(False, 32, bits)`;
- existing `REGISTER`/matching-ID path stays valid;
- `REGISTER`/wrong-ID stays `invalid_register_rule_result`;
- `SIGNED_SCALAR`, ADDRESS and wrong width remain invalid GPR results;
- `to_register` remains unsupported;
- artifact index accepts a portable unwind component containing the current-profile scalar R7 rule after the validator correction.

## Slice005 consumption

After the corrective recipe projection is independently reviewed/verified, StackService may bind a COMPLETE exact-width unsigned scalar result to the `UnwindRow.register_rules` key when constructing caller `RegisterValue`. It must not perform any other scalar/register coercion.

No Slice005 product patch is authorized before the v1.3 corrective foundation is tested and reviewed.
