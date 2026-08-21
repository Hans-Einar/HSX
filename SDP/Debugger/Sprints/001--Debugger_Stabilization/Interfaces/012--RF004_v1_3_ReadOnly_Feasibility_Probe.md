# RF-004 v1.3 read-only feasibility probe

Status: **MASTER PREPARED / TESTER EXECUTION PENDING**

Exact branch/head for this probe: `codex/dbg-rf-004@c402d2c30cd0c56219e9b028ff01e36c38c2b02e`.
Consumes Steering decision: issue #38 comment `5374100772`.
Consumes conformance delta: `010--RF004_Register_Rule_Result_Conformance_v1_3.md`.

This probe is intentionally pre-implementation and read-only. It must establish that the selected v1.3 semantics can be implemented without changing HSX recipe opcodes.

Required observations:

1. Existing focused recipe/artifact tests pass at the exact pre-implementation head.
2. A current-profile caller-R7 expression using `cfa`, checked `-8`, and `deref_u(4,little)` evaluates successfully to `RecipeScalar(signed=False, bit_width=32, value=<exact bytes>)` with no register fallback.
3. The corresponding `UnwindRow.register_rules` key is exactly `R7`.
4. The current 1.2 validator rejects that scalar form, proving the corrective delta is localized to the Debugger projection rather than the recipe evaluator.
5. A hypothetical `to_register` opcode remains unsupported.
6. Repository tracked state is unchanged by the probe.

No product or test file is to be edited during this probe.
