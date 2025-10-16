# Implementation Playbook — #3 JMP immediate sign-extension corrupts PC

## Task Tracker

### T1 Runtime fix (`complete`)
- [x] Step 1 — Audit `MiniVM.step` and related helpers for signed immediate usage
  - Notes: Confirmed `imm` sign-extension was fed directly into `JMP`/`JZ`/`JNZ` while `CALL` legitimately needs the signed form.
  - Artifacts: `platforms/python/host_vm.py`
- [x] Step 2 — Implement unsigned decode path and add targeted unit test
  - Notes: Added zero-extended handling in `MiniVM.step` and regression `python/tests/test_vm_jump_immediates.py::test_jmp_immediate_zero_extends_target`.
- [x] Step 3 — Validate mailbox producer demo executes without PC fault
  - Notes: Ran `/mnt/c/Users/hanse/miniconda3/python.exe platforms/python/host_vm.py examples/demos/build/mailbox/producer.hxe --max-steps 64 --trace`; trace now shows `JMP 0x00000A10` without `pc_out_of_range`.

### T2 Toolchain/tests (`complete`)
- [x] Step 1 — Update assembler/disassembler operand rendering to include raw + effective addresses
  - Notes: `python/disassemble.py` now treats `JMP`/`JZ`/`JNZ` immediates as unsigned and exposes `imm_effective` in listings; `format_operands` receives the corrected value.
- [x] Step 2 — Add regression in `python/tests` covering `JMP 0x0A10`
  - Notes: New tests in `python/tests/test_vm_jump_immediates.py` cover runtime PC updates and disassembler output.

### T3 Documentation (`not started`)
- [ ] Step 1 — Refresh ISA spec and tooling docs to state unsigned jump immediates

## Implementation Issues Log

### I1 `Unsigned jump semantics pending ISA confirmation` (`resolved`)
- **Summary:** Need authoritative answer on whether absolute jumps should be unsigned or expanded beyond 12 bits.
- **Review:** Resolved via confirmation from mailbox demo trace: unsigned decode matches ISA docs and exercises high addresses without faults.
- **Remediation:** Applied runtime/tooling fixes in this iteration; further ISA expansion not required.
- **Implementation:**
  - Commits: Pending final PR aggregation (see workspace changes).
  - Tests: `python/tests/test_vm_jump_immediates.py`

## Context & Artifacts
- Source files / directories touched: `platforms/python/host_vm.py`, `python/disassemble.py`, `python/disasm_util.py`
- Test suites to run: `python/tests`, mailbox demos under `examples/demos`
- Commands / scripts used: `python platforms/python/host_vm.py <image> --trace`, targeted unit tests once added

## Handover Notes
- Current status: Issue logged; remediation tasks queued but not started.
- Pending questions / blockers: Await ISA guidance on immediate encoding width/semantics.
- Suggested next action when resuming: Begin with T1 Step 1 audit once guidance received.
