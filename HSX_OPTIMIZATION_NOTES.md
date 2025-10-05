# HSX Optimization Notes

---

## Philosophy
HSX bytecode targets small embedded devices (e.g. AVR128DA28), so we optimise for:
1. Minimal instruction count
2. Low register pressure
3. Deterministic timing (no hidden work)

We prefer clarity, speed, and size, but never at the expense of determinism.

---

## Implemented Optimisations

### 1. MOV Elimination (Codex stage)
Goal: remove redundant register copies emitted during LLVM -> HSX lowering.

Rules:
- Fold `LDI` followed immediately by `MOV` into a single `LDI dst, imm`
- Drop self copies (`MOV Rx, Rx`)
- Break MOV chains when the intermediate register is dead
- Preserve the return transfer (`MOV R0, Rx` before `RET`)

Example:
```asm
LDI R12, 99
MOV R6, R12
RET
```
becomes
```asm
LDI R6, 99
RET
```

CLI control: `--no-opt` disables the post-pass optimisation for debugging.

---

## Planned Optimisations

### 2. Copy propagation
If a register is only used as a copy source, rewrite consumers to use the original value directly.

### 3. Constant folding
Evaluate trivial constant expressions at compile time (e.g. add/sub/mul/icmp on immediates).

### 4. Dead code elimination
Remove code that is unreachable after unconditional branches or that precedes `RET`.

### 5. Branch shortening
Use short-form branch opcodes (`JMP8`, `JNZ8`, etc.) when targets fit in the smaller displacement.

### 6. Register reuse / linear-scan allocator
Replace the current static temp allocation with a simple allocator to reclaim registers once their
live range ends. Target outcome:
- 20-40% fewer temporaries
- Fewer MOV clean-up instructions
- Clearer path to stack-frame generation on AVR

---

## Testing and Verification
Every optimisation pass must include:
- Before/after assembly diff review
- Byte-size comparison (expecting reduction)
- Functional equivalence via host VM run
- Unit tests under `python/tests/test_opt_*.py`

Optimisations should be independent and toggleable.

---

## Metrics and Targets
| Metric | Current | Goal |
| --- | --- | --- |
| MOV count per 100 instructions | 18 | < 5 |
| Registers per function | 12 | < 6 |
| File size reduction | - | >= 20% |
| VM execution cycles | Baseline | <= 80% of baseline |

---

### Additional Ideas
- Peephole arithmetic simplifications (remove identity ops such as `ADD rd, rs, R0`).
- Track live ranges during lowering to free temporaries sooner (foundation for linear scan allocator).
- Introduce a small pass manager with flags (`--opt=mov,copy,...`) so we can enable/disable passes individually.
