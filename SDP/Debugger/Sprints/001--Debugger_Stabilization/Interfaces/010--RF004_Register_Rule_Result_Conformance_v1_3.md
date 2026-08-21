# `dbg.resolver-inspection/1.3` — Register-rule result binding conformance

Status: **STEERING REFROZEN / EXECUTION EVIDENCE PENDING**

Steering authority: issue #38 comment `5374100772`.
Blocker superseded by this refreeze: `DBG-BLK-001-005-003`.
Parent interface: `dbg.resolver-inspection/1.2`.
HSX portable target baseline remains unchanged: `HSX-D-002`, `hsx.unwind-recipe/1`, and `hsx.location-recipe/1` are not version-bumped by this Debugger projection refreeze.

## 1. Normative delta

All `dbg.resolver-inspection/1.2` clauses remain unchanged except the result contract for `UnwindRow.register_rules` GPR `EXPRESSION` rules.

`UnwindRow.register_rules` is keyed by exact architecture `RegisterId`. That row key is the authoritative identity of the caller GPR being recovered. An `EXPRESSION` rule for a GPR therefore has two conforming exact-width result forms:

1. `REGISTER`: the expression returns `RecipeRegister`; its `register_id` MUST exactly equal the `register_rules` key and its width MUST equal `ArchitectureDescriptor.register_width_bits`.
2. `UNSIGNED_SCALAR`: the expression returns an unsigned `RecipeScalar`; its width MUST exactly equal `ArchitectureDescriptor.register_width_bits`. The `register_rules` key binds those scalar bits to the recovered caller GPR identity.

No other result kind is conforming for a GPR expression. In particular `SIGNED_SCALAR` and `ADDRESS` are rejected.

There is no implicit numeric conversion: the accepted scalar already has the exact GPR bit width and unsigned bit interpretation. The row key supplies identity only; it does not widen, truncate, mask, endian-convert, sign-convert, or reinterpret the scalar.

## 2. Current ABI consequence

For `hsx.abi.llc-r7-word32/1` after the saved-R7 prologue, the portable HSX rule remains exactly the accepted schema-v1 expression:

```text
cfa
add_sconst_checked(-8)
deref_u(4, little)
```

with `role=REGISTER`, `required_result=UNSIGNED_SCALAR`, and `required_bit_width=32`, stored under the exact `register_rules` key `R7`.

`deref_u` continues to return `RecipeScalar(False, 32, bits)`. StackService publishes recovered `RegisterValue("R7", 32, bits, available=True)` only after the rule key, result kind, width, snapshot fencing, and recipe evaluation all conform.

## 3. Preserved REGISTER form

The existing register-preserving expression form remains valid. For example a rule keyed `R7` may use `reg_value("R7")` with `required_result=REGISTER` and width 32. A rule keyed `R7` that returns `RecipeRegister("R0", ...)` remains `CORRUPT` / `invalid_register_rule_result`.

## 4. Explicit non-changes

This refreeze does NOT:

- add `to_register`, scalar-to-register, cast, mask, or wrap opcodes;
- change the closed `hsx.unwind-recipe/1` opcode set;
- change `HSX-D-002` or `HSX-ST-007` caller-R7 semantics;
- permit scalar binding outside keyed `UnwindRow.register_rules` GPR recovery;
- change location-recipe `reg_value` semantics;
- infer register identity from expression position, ABI defaults, or a hidden cache;
- allow a missing/failed GPR rule to fall back to a younger/current frame value.

## 5. Required validator/evaluator behavior

`RecipeComponentValidator.validate_unwind_row` MUST:

- validate the expression with `role=REGISTER`;
- accept exact-width `REGISTER` or `UNSIGNED_SCALAR` only;
- apply `required_register_id` equality only to `REGISTER` results;
- reject wrong-width scalar/register results;
- reject `SIGNED_SCALAR`/`ADDRESS` GPR results;
- continue counting opcode/dereference budgets identically.

`RecipeEvaluator` is unchanged: it returns the value declared by the expression. `StackService` owns the row-key binding when building caller `RegisterValue` evidence.

## 6. Required conformance evidence

Before Slice005 may resume, read-only execution must prove on one exact remote head:

- current-profile `R7` memory recovery evaluates to an exact unsigned 32-bit `RecipeScalar`;
- the row key is exact `R7` and is sufficient to bind the scalar result without a new opcode;
- the legacy `REGISTER` result form still validates only when returned `register_id` equals the row key;
- `SIGNED_SCALAR`, wrong width, and ADDRESS remain rejected for GPR rules;
- parser still rejects a hypothetical `to_register` opcode as unsupported;
- existing focused recipe/artifact regression tests remain unchanged until the corrective implementation patch is deliberately applied.

After implementation, repeat the same evidence plus the new v1.3 conformance tests, independent review, formal verification, and exact-head sign-off before Slice005 product work resumes.
