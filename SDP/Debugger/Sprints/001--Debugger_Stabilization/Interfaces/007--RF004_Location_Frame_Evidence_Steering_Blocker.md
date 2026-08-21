# DBG-BLK-001-005-002 — RF-004 Location Frame Evidence Steering Blocker

- Status: **AWAITING STEERING DECISION**
- Refactor/Iteration/Slice: `DBG-RF-004` / `DBG-IT-001-005` / `DBG-SL-001-005-007`
- Frozen interface: `dbg.resolver-inspection/1.1`
- Last signed dependency: Slice 002 at `c7bc39057469f1aa62a78f409753ec0213631214`
- Discovery/coordination head: `269d0bb962f85241633e1af8489b459357f2ff77`
- Product changes during discovery: none

## Frozen contradiction

Interface 004 simultaneously freezes:

1. `UnwindFrame` without recovered-register or PSW evidence;
2. `RecipeEvaluationContext` with mandatory `recovered_registers` and optional `psw`;
3. `LocationEvaluator.evaluate(context, frame, index, variable, row, read_port, architecture,
   abi, limits...)` without a RecipeEvaluationContext or frame-evidence parameter;
4. `SnapshotReadPort` reads by `InspectionContext` only, with no frame-index/recovered-frame
   register operation;
5. `reg_value` from the selected frame's recovered register set and non-top-frame location
   evaluation that never substitutes current live/top-frame registers.

HSX-ST-007 additionally states that a non-top register not recovered by unwind is unavailable
and must never fall back to the current register snapshot.

The frozen inputs therefore cannot supply the evidence needed to implement the frozen result.

## Rejected private alternatives

- `SnapshotReadPort.read_registers(context, ...)` supplies current snapshot registers, not a
  selected non-top frame's recovered state.
- ABI/row/index/CFA/fixed-R7 derivation invents evidence and violates no-fallback/no-guess rules.
- A hidden cache or shared side channel adds an unfrozen dependency and makes the standalone
  public method non-deterministic/incomplete.
- A subclass or hidden extra `UnwindFrame` field violates the exact frozen public DTO schema.

## Steering decision required

Steering must refreeze an explicit evidence seam. Minimal directions are:

1. add exact recovered-register evidence to `UnwindFrame` (and PSW evidence if recovered
   `special_value PSW` is required);
2. pass `RecipeEvaluationContext` or another exact frozen frame-evidence DTO to
   `LocationEvaluator.evaluate`;
3. add a frame-aware immutable recovered-state operation to `SnapshotReadPort`.

Master makes no choice and changes no frozen interface. Slice 007 worker made zero edits.
Review 011, verification 007, artifact Slice 003 and all later RF-004 Slices are not started.
RF-005..009 and Executive/VM/AVR/frontend work remain blocked.
