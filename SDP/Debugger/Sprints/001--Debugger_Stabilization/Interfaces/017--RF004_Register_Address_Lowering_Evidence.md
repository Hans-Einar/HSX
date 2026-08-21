# RF-004 explicit register-to-address lowering evidence

Status: **CANDIDATE CONFORMANCE EVIDENCE / NO CONTRACT CHANGE**

The stable-body ABI description uses the semantic shorthand `CFA = address(R7) + 8`.
`hsx.unwind-recipe/1` deliberately has no implicit Register→Address cast, and `to_address`
accepts a scalar only. No new opcode or refreeze is required because the closed v1 recipe
set already provides an explicit lossless lowering for a full-width GPR:

```text
reg_value("R7")             # RecipeRegister("R7", 32, bits)
bit_slice(0, 32)            # RecipeScalar(unsigned, 32, same bits)
to_address(data_space)      # typed data-space address after descriptor validation
add_sconst_checked(+8)      # CFA
```

The full-width `bit_slice` changes only the recipe value kind from recovered-register evidence
to an explicit unsigned scalar; it does not mask away bits, widen, truncate, change endian,
or infer an address space. `to_address` remains the sole explicit address-space conversion.

This preserves the frozen `hsx.unwind-recipe/1` opcode set, the no-implicit-cast rule, and the
accepted ABI semantics. Candidate StackService tests must use this explicit lowering rather
than teaching `to_address` to consume RecipeRegister.
