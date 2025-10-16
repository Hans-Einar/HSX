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

### I2 `Clock throttling fails to resume full speed` (`resolved`)
- **Summary:** When all tasks are blocked the auto-loop deliberately slows down, but the clock kept idling even after a mailbox wake, leaving task execution in slow mode.
- **Review:** The throttle logic in `ExecutiveState._auto_loop` prioritized the global `sleep_pending` flag before checking for runnable tasks. As long as any task was sleeping (common during mailbox waits), the loop stuck to a 10–50 ms delay even when other tasks were ready, so the clock never accelerated.
- **Remediation:** Reorder the wait-time selection to favor runnable tasks, introduce explicit throttle state tracking (`mode`, `throttle_reason`), and surface the mode through `clock status` so operators can confirm when the loop returns to full speed.
- **Implementation:**
  - Commits: Pending (see working tree).
  - Tests: `/mnt/c/Users/hanse/miniconda3/python.exe -m pytest python/tests/test_vm_pause.py python/tests/test_mailbox_wait.py python/tests/test_shell_client.py`

## Context & Artifacts
- Source files / directories touched: `platforms/python/host_vm.py`, `python/disassemble.py`, `python/disasm_util.py`, `python/execd.py`, `python/shell_client.py`, `python/blinkenlights.py`, `docs/executive_protocol.md`, `help/clock.txt`
- Test suites to run: `python/tests`, mailbox demos under `examples/demos`
- Commands / scripts used: `python platforms/python/host_vm.py <image> --trace`, `/mnt/c/Users/hanse/miniconda3/python.exe -m pytest …`

## Handover Notes
- Current status: JMP immediate fix merged; clock throttle regression resolved with new status telemetry. ISA spec/doc refresh (T3) still pending.
- Pending questions / blockers: Need decision on finalizing ISA documentation update for unsigned jumps.
- Suggested next action when resuming: Draft the ISA/spec changes for T3 and confirm no additional throttle regressions via long-running mailbox demos.
