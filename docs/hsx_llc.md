# hsx-llc - LLVM IR to MVASM

> SDP Reference: 2025-10 Main Run (Design Playbook #11)

## Purpose
`python/hsx-llc.py` lowers LLVM IR (text form) into MVASM so the assembler/linker can produce `.hxe` images. This document describes the CLI, lowering pipeline, and current capability set so front-end owners and tooling engineers share the same expectations.

## CLI Summary

| Flag | Description |
|------|-------------|
| `input.ll` | Required positional argument (LLVM IR in textual form). |
| `-o/--output <path>` | Required. Destination `.mvasm` file. |
| `--trace` | Emit verbose lowering diagnostics (per-instruction commentary) to stdout. |
| `--no-opt` | Disable the post-pass that folds redundant `MOV` chains. Useful during debugging. |

The script always writes UTF-8 MVASM compliant with `docs/MVASM_SPEC.md`.

## Pipeline Overview
1. **IR Preprocessing**
   - Sanitises quoted global names (`@"foo.bar"` → backend-safe symbols).
   - Reserves bare names to avoid collisions during sanitation.
2. **Parsing**
   - Builds simple representations for globals, functions, and basic blocks.
   - Records attributes but drops LLVM modifiers we intentionally ignore (`nsw`, `nuw`, `noundef`, `dso_local`, etc.).
3. **Global Rendering**
   - Emits `.data` directives for global scalars, strings (`c"..."`), and spill slots.
   - Align clauses are honoured when present.
4. **Function Lowering**
   - Assigns MVASM labels per function and block.
   - Legalises instructions into HSX opcodes (`ADD`, `LD`, `ST`, `SVC`, etc.).
   - Handles GEP patterns (including struct offsets), pointer arithmetic, loads/stores for i8/i16/i32/half/ptr, integer and half-precision math, conditional branches, PHI nodes, calls, and returns.
   - Tracks register lifetimes so virtual registers recycle physical ones. When the allocator runs out, spills land in the per-function `.data` section (using `R7` as the frame pointer).
5. **Imports/Exports**
   - Declares `.export` for every defined function and `.import` for unresolved callees.
   - Marks `_start` if a function named `main` exists (default entry label).
6. **Optimisation (optional)**
   - Removes redundant `MOV` chains when `--no-opt` is not set.

## Supported IR Patterns
- Integer arithmetic (`add`, `sub`, `mul`, `udiv`, `sdiv`, `icmp` with equality/ordering predicates).
- Floating helpers lowered to f16 ops (`fadd`, `fmul`, `fptrunc`, `fpext`).
- Branches (`br`), PHI nodes (lowered via move sequences in predecessor blocks), `call`, `ret`.
- Memory ops: `alloca` (stack slots), `load`/`store` for i8/i16/i32/ptr/half/float, `getelementptr` with static and dynamic indices.
- Intrinsics used by the mailbox/value pipeline (e.g., CRC helpers) when backed by runtime shims.

## Limitations / TODO
- Arguments beyond the first three spill to the caller stack but the canonical ABI (stack layout, varargs) is still evolving.
- Vector types, atomics, and inline assembly are not supported.
- Only minimal optimisation exists (MOV folding). Register allocation is linear-scan; no live-range splitting yet.
- Diagnostics bubble up as `ISelError` with the offending LLVM line for easier triage.

## Output Structure
- Generated MVASM starts with `.entry`, `.export`, and `.import` declarations followed by `.data` (if needed) and `.text`.
- Spill slots appear under `.data` with deterministic labels (`__spill_<fn>_<n>`).
- All emitted assembly follows the syntax documented in `docs/MVASM_SPEC.md` and feeds directly into `python/asm.py`.

## Integration Points
- **Assembler:** consumes the MVASM and produces `.hxo/.hxe` artefacts (`docs/asm.md`).
- **Toolchain tests:** `python/tests/test_ir2asm.py` and related suites compile C/LLVM snippets through hsx-llc, ensuring regressions are caught.
- **Packaging:** future `make package` targets should include both the `.mvasm` output and the original `.ll` file when distributing samples for debugging.

Maintain this document alongside functional changes so the CLI/feature list remains accurate for the SDP trail.
