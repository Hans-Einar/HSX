# Implementation Notes - VM Gap Closure

## 2025-11-01 - Codex (Session 1)

### Prep
- **DONE** Created `AGENTS.md` playbook describing the gap-analysis workflow so future agents can resume without context loss (`main/05--Implementation/01--GapAnalysis/01--VM/AGENTS.md`).

### Phase 1.1 - Shift Operations (survey)
- **Status:** DONE (discovery)
- **What was done:**
  - Audited `platforms/python/host_vm.py` opcode dispatcher (`op == 0x10`..`0x60`) and confirmed no shift opcodes existed between `MUL (0x12)` and `AND (0x14)`.
  - Checked `python/asm.py` and `python/disassemble.py`; no `LSL/LSR/ASR` mnemonics present, confirming assembler/disassembler gaps.
- **Next actions captured during survey:**
  1. Define opcode assignments for `LSL/LSR/ASR` (respect the "new opcodes >= 0x30" guidance).
  2. Implement execution semantics in `host_vm.py`, including PSW updates (Z now, N/C/V after plan item 1.3).
  3. Extend assembler/disassembler tables and add unit tests covering shift by 0/1/31/32 and greater-than-32 cases.
  4. Update ISA docs (`docs/abi_syscalls.md`, `docs/MVASM_SPEC.md`) once implementation exists.

## 2025-11-01 - Codex (Session 2)

### Phase 1.1 - Shift Operations (implementation)
- **Status:** DONE (feature landed; PSW still limited to Z-flag pending plan item 1.3).
- **What was done:**
  - Assigned opcodes `0x31`-`0x33` to `LSL`, `LSR`, and `ASR` (`python/asm.py:15`, `python/disasm_util.py:10`).
  - Implemented the execution paths in `platforms/python/host_vm.py:918`-`938`, using modulo-32 shift amounts and updating the zero flag via the existing helper.
  - Updated assembler/disassembler pipelines to understand the new mnemonics (`python/asm.py:488`, `python/disasm_util.py:129`-`136`).
  - Added regression coverage in `python/tests/test_vm_shift_ops.py`, validating shift-by-0/1/32/33, logical vs arithmetic semantics, and zero-flag behaviour.
  - Documented the instructions in `docs/MVASM_SPEC.md:33` and recorded the opcode IDs in `docs/abi_syscalls.md:23`.
- **Testing:** `python -m pytest python/tests/test_vm_shift_ops.py`
- **Follow-ups:** Full PSW implementation (carry/negative/overflow) remains open under plan item 1.3; revisit shift flag semantics once that work lands.

## 2025-11-01 - Codex (Session 3)

### Phase 1.3 - Complete PSW flag implementation
- **Status:** DONE (all core ALU instructions now update Z/C/N/V).
- **What was done:**
  - Defined flag bit constants (`FLAG_Z`, `FLAG_C`, `FLAG_N`, `FLAG_V`) and surfaced them via `MiniVM` for tests (`platforms/python/host_vm.py:60`, `platforms/python/host_vm.py:393`).
  - Replaced the old `set_flags` helper with a full updater that preserves unspecified bits and accepts carry/overflow inputs (`platforms/python/host_vm.py:776`-`803`).
  - Added local helpers `add_with_flags` / `sub_with_flags` and wired `ADD`, `SUB`, `CMP`, logical ops, shifts, and `MUL` to feed carry/overflow state (`platforms/python/host_vm.py:807`-`930`).
  - Extended shift instructions to emit carry when bits are shifted out and documented behaviour in `docs/MVASM_SPEC.md:43`.
  - Authored dedicated regression coverage for PSW semantics and branching (`python/tests/test_vm_psw_flags.py`).
- **Testing:** `python -m pytest python/tests/test_vm_psw_flags.py`
- **Follow-ups:** None for PSW; next plan item is to plumb ADC/SBC (Phase 1.2) atop the new flag infrastructure.

## 2025-11-01 - Codex (Session 4)

### Phase 1.2 - Carry-aware arithmetic (ADC/SBC)
- **Status:** DONE (Python VM + tooling support).
- **What was done:**
  - Assigned opcodes `0x34`/`0x35` to `ADC`/`SBC` and taught assembler/disassembler pipelines to encode/decode them (`python/asm.py:15`, `python/disasm_util.py:10`).
  - Implemented carry-in/borrow-in semantics in `platforms/python/host_vm.py:931`-`970`, reusing the PSW helpers to update Z/C/N/V.
  - Documented the new instructions in both `docs/MVASM_SPEC.md:50` and `docs/abi_syscalls.md:24`.
  - Expanded PSW regression coverage with ADC/SBC scenarios (`python/tests/test_vm_psw_flags.py`).
- **Testing:** `python -m pytest python/tests/test_vm_psw_flags.py`
- **Follow-ups:** Proceed to Phase 1.4 (DIV opcode) and trace API work per implementation plan.
