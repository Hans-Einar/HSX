# DBG-BLK-001-005-002 — RF-004 Location Frame Evidence Steering Blocker

- Status: **SUPERSEDED BY `dbg.resolver-inspection/1.2` / REVIEW PENDING**
- Refactor/Iteration/Slice: `DBG-RF-004` / `DBG-IT-001-005` / `DBG-SL-001-005-007`
- Frozen interface at discovery: `dbg.resolver-inspection/1.1`
- Steering resolution: `dbg.resolver-inspection/1.2`
- Last signed dependency: Slice 002 at `c7bc39057469f1aa62a78f409753ec0213631214`
- Discovery/coordination head: `269d0bb962f85241633e1af8489b459357f2ff77`
- Product changes during discovery: none
- Steering escalation: issue #38 comment `5369244294`
- Steering refreeze: issue #38 comment `5370574104`
- Published refreeze content head: `cb575ac0920bec8cc7ddd5565df9544b746f069b`

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

## Steering decision

Steering selected option 1 in comment `5370574104`:

1. add `recovered_registers: RegisterSet` and low-level `recovered_psw: RegisterValue` to
   UnwindFrame;
2. keep LocationEvaluator and SnapshotReadPort signatures unchanged;
3. require complete deterministic architecture-order availability evidence and exact
   snapshot/unwind/SAME provenance with no fallback.

Master refreezes only that public projection as `1.2` plus `DBG-CF-001-005-002`. Slice 007
worker made zero edits. Fresh interface review 031 must pass before restart. Review 011,
verification 007, artifact Slice 003 and all later RF-004 Slices are not started.
RF-005..009 and Executive/VM/AVR/frontend work remain blocked.
