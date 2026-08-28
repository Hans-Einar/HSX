# DBG-BLK-001-005-003 — Stack Caller-Register Recipe Result Conflict

- Status: **PUBLISHED / AWAITING STEERING**
- Refactor: `DBG-RF-004`
- Slice: `DBG-SL-001-005-005`
- Discovery head: `943b8d4d111304638989e429863bece8323b4b08`
- Product changes: **none**
- Published blocker head: `43c9cfaa8bd75a3bd098c3be5df8647612b3f51a`
- Steering issue: #38 comment `5373731599`

## Minimal conflict

The frozen current ABI profile requires exact caller R7 recovery from memory after the prologue:

- `HSX-D-002` lines 181–184 require post-PUSH/body caller R7 = `[CFA-8]`;
- `HSX-ST-007` lines 352–355 expresses that value as `deref_u(CFA-8,4,little)`.

The frozen Debugger projection simultaneously requires:

- Interface1.2 lines 686–687: a GPR EXPRESSION has `required_result=REGISTER` and may publish
  only a matching exact-width `RecipeRegister`;
- the signed RecipeComponentValidator enforces that final result class.

The closed `hsx.unwind-recipe/1` opcode/value model provides:

- `deref_u` -> unsigned `RecipeScalar`;
- `RecipeScalar`, `RecipeAddress`, `RecipeRegister` as distinct result classes;
- no scalar-to-named-register constructor or cast opcode.

Executable evaluation of the required expression
`[cfa, add_sconst_checked(-8), deref_u(4,little)]` for caller R7 therefore returns
`recipe_result_mismatch`: the exact memory value is a scalar, not a RecipeRegister.

`SAME` is false after the saved-R7 prologue, and making R7 unavailable contradicts the frozen
current-profile row coverage. StackService cannot conform without changing a frozen contract.

## Minimal Steering options

1. **A — HSX scalar-to-register constructor (recommended).** Refreeze the HSX recipe schema and
   Debugger projection with one bounded exact-width scalar-to-named-register operation/result.
2. **B — Row-key register binding.** Refreeze GPR EXPRESSION to accept an exact-width unsigned
   scalar, with the `register_rules` row key supplying the exact RegisterId.
3. **C — Degraded profile.** Refreeze current-profile post-PUSH/body caller R7 as unavailable and
   revise the required recovery coverage/profile claim.

Option A keeps result typing explicit inside the recipe. Option B is smaller but makes result
identity partly contextual. Option C loses required current ABI recovery fidelity.

## Stop decision

All uncommitted StackService drafts were removed. Worktree is clean at the discovery head.
Review005, verification005, Slice006, parent integration and RF-005..009 remain stopped. No
speculative workaround, Executive/VM/AVR/frontend work or portable-contract edit was made.
