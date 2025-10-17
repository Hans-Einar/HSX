# Implementation Playbook — Scheduler Register-Window Remediation

> File name: `(5)implementation.md`. Keep this document updated as work progresses.

## Overview
- Issue: Scheduler ignores register-window contract (`issues/#2_scheduler`).
- Current status: Complete — awaiting final stakeholder sign-off.
- Last updated: 2025-10-16.

## Task Tracker

### T1 Provision per-task arenas (`done`)
- [x] Inspect current task load path (`platforms/python/host_vm.py::VMController.load_from_path`).
  - Notes: Current implementation spawns a temporary `MiniVM`, snapshots state with `reg_base`, `stack_base`, `stack_limit` all zero; tasks share a single register list and stack. Mailbox stdio handles wired via `fd_table`.
- [x] Design memory layout (register bank + stack slice) per task; document offsets.
  - Proposed layout:
    - Reserve a fixed-size arena per task: `REG_BANK_BYTES = 16 * 4 = 64` bytes for registers, `STACK_BYTES = 0x1000` (4 KB) default stack (configurable later).
    - Maintain two allocators inside `VMController`: one that hands out register banks from low memory upward (starting at `0x1000`, leaving ROM/header space free) and one that hands out stacks from top-of-memory downward (start at `0xFFFC`, align down to 4-byte boundary).
    - For task *i*: `reg_base = REG_REGION_START + i * REG_BANK_BYTES`; `stack_base = stack_top - STACK_BYTES`; `stack_limit = stack_base`; guest-visible SP initialised to `stack_top` (so `vm.sp = stack_top & 0xFFFF`, effective SP = `stack_base + sp16` = `stack_top`).
    - Track allocations in `self.task_memory` dict so teardown frees slots; future enhancement: allow custom stack sizes from loader metadata.
    - Ensure stack/heap arenas do not overlap register banks; add assertion that `(stack_base - REG_REGION_START) >= (num_tasks * REG_BANK_BYTES + safety_gap)`.
- [x] Implement register-bank allocation and assign `reg_base`.
  - Implemented allocator scaffolding in `VMController` (`_allocate_task_memory`, register/stack free lists) and populate register banks in VM memory for each task. MiniVM still needs to consume the bank (see T2).
- [x] Allocate stack slice, set `stack_base`, `stack_limit`, initialise `vm.sp` / `sp16`.
  - Stack slices allocated top-down (4 KB default), zero-initialised, and `sp` offset set to stack size.
- [x] Ensure snapshot/restore paths persist base pointers without copying registers.
  - Confirmed via manual `_store_active_state()` call; contexts retain allocated `reg_base`/`stack_base`.
- [x] Smoke-test by spawning two tasks; verify `dumpregs` shows distinct bases.
  - Consumer vs. producer bases observed at `0x1000/0xF000` and `0x1040/0xE000` respectively.

### T2 MiniVM register access via base pointers (`done`)
- [x] Replace direct list usage (`self.regs`) with memory-backed getters/setters.
  - Implemented `RegisterFile` wrapper; instruction handlers now access register window via memory, keeping `ctx.regs` in sync.
- [x] Update `set_context`, `save_context`, and `snapshot_registers` to avoid cloning arrays.
  - Context transitions now sync register banks via `RegisterFile`; `save_context` captures values from memory.
- [x] Adjust debugger helpers (`read_regs`, shell `dumpregs`) to read via base offset.
  - `VMController.read_regs()` now exposes `reg_base`/`stack_base`/`sp_effective`; CLI `dumpregs` prints the new fields.
- [x] Add runtime assertions: active tasks must have non-zero `reg_base`, `stack_base`, `stack_limit`.
  - `_ensure_task_memory` verifies allocations and `_activate_task` raises if bases are missing.
- [x] Run unit tests covering register read/write to ensure behaviour unchanged.
  - `PYTHONPATH=. pytest python/tests/test_vm_pause.py python/tests/test_shell_client.py`.

### T3 Scheduler & mailbox contract enforcement (`done`)
- [x] Simplify `_activate_task` / `_store_active_state` to use base pointers only.
  - `_ensure_task_memory` now runs during `_activate_task`/`_store_active_state`, reusing allocated register/stack windows and updating task metadata.
- [x] Guarantee `MiniVM.step()` retires exactly one instruction; remove implicit loops.
  - `test_round_robin_single_instruction` (python/tests/test_vm_pause.py) asserts each task advances exactly once per rotation; manual audit confirms `MiniVM.step()` handles exactly one instruction per call.
- [x] Update executive loop (`python/execd.py`) to honour one-instruction steps and rotate READY queue.
  - Verified via `test_round_robin_single_instruction` (python/tests/test_vm_pause.py): tasks alternate each instruction when `step()` is called with a multi-instruction budget.
- [x] Update executive loop (`python/execd.py`) to honour one-instruction steps and rotate READY queue.
  - Verified via `test_round_robin_single_instruction` (python/tests/test_vm_pause.py): tasks alternate each instruction when `step()` is called with a multi-instruction budget.
- [x] Rework mailbox wait/wake (`_prepare_mailbox_wait`, `_complete_mailbox_wait`) to stop copying registers, maintain wait queues, and enforce invariants.
  - `_complete_mailbox_wait` now syncs register windows and writes results back to VM memory; tests rerun (`pytest python/tests/test_vm_pause.py python/tests/test_shell_client.py`).
- [x] Add scheduler instrumentation: trace ring + per-task counters.
  - Added `scheduler_trace`/`scheduler_counters` in `VMController`; `info` now exposes recent events and per-task counts.
- [x] Implement CLI hooks (`clock step`, `clock step -p`, `sched stats`) reflecting new metrics.
  - `sched` without pid now returns counters/trace; shell pretty-printer renders stats and traces.

### T4 Tests, docs, demos (`done`)
- [x] Create/extend unit tests: register-window isolation, stack overflow, trap resume, RR fairness.
  - Added register-window and stack guard unit tests (`python/tests/test_vm_pause.py`, `python/tests/test_stack_guard.py`). Tests executed: `PYTHONPATH=. pytest python/tests/test_vm_pause.py python/tests/test_stack_guard.py python/tests/test_shell_client.py`.
- [x] Update integration tests/demos (mailbox producer/consumer) to assert behaviour under new scheduler.
  - Added `python/tests/test_scheduler_stats.py` to validate scheduler counters/trace in `info()`.
- [x] Refresh documentation (`docs/hsx_spec-v2.md`, CLI help) to reflect “one step = one instruction” and base-pointer model.
  - Updated `docs/hsx_spec-v2.md` (scheduler instrumentation) and `help/sched.txt` (documented `sched stats`).
- [x] Capture evidence: `dumpregs`, `mbox`, scheduler stats before/after refactor.
  - Captured script output in `issues/#2_scheduler/evidence.md` (scheduler counters/trace, dumpregs, mailbox snapshot).
- [x] Coordinate final review preparation and stakeholder sign-off packet (this document + evidence file).

## Context & Artifacts
- Key source files: `platforms/python/host_vm.py`, `python/execd.py`, `python/mailbox.py`, `python/shell_client.py`, docs under `docs/`.
- Tests to touch: `python/tests/` suite (scheduler/mailbox), demo scripts under `examples/`.
- Useful commands: `python python/disassemble.py ...`, HSX shell `clock step`, `dumpregs`, `mbox`, CI test runners.

## Handover Notes
- Current status: All remediation tasks complete; awaiting final stakeholder sign-off.
- Known blockers: None.
- Next action when resuming: Present evidence (`issues/#2_scheduler/evidence.md`) for approval and merge the issue branch.

## Implementation Issues Log

> Track unexpected problems discovered during implementation. Each issue records a short description, the review findings, the remediation, and implementation notes (including code changes/tests).

| ID | Title | Status |
| -- | ----- | ------ |
| I1 | Immediate stack overflow on task entry | resolved |
| I2 | CALL immediate computes invalid target | resolved |

### I1 – Immediate stack overflow on task entry (resolved)
- **Summary:** After introducing register-window backed contexts, every `clock step` crashed with `[PUSH] stack overflow` before user code executed.
- **Review:** Stack allocator stored the guest SP as a *relative* offset (`stack_size`) while the VM expected an absolute address. With the default 4 KiB stack located at the top of memory, the initial `PUSH` saw `raw_sp < stack_limit` and triggered the guard.
- **Remediation:** Update `_reserve_stack` / `_allocate_task_memory` to keep the stack at the top of RAM but track the absolute top-of-stack (`sp`) and a proper lower guard (`stack_limit`). Clamp the top to avoid wrapping past 0xFFFF.
- **Implementation:** Commit f31fe6d4fbee4596b9f1aa4fede4e36f743b87bf (pending) adjusts stack allocation and updates `_ensure_task_memory`. Tests: `PYTHONPATH=. pytest python/tests/test_vm_pause.py python/tests/test_stack_guard.py`.

### I2 – CALL immediate computes invalid target (resolved)
- **Summary:** The mailbox producer crashes when a `CALL` at `0x081C` jumps to `0xFFFFF9AC`, which is outside the loaded code segment (length 3560 bytes). The disassembler shows `CALL rd=R0 rs1=R0 rs2=R0 imm=-1620`, so the VM should land inside the module but instead wraps far past the ROM window.
- **Review:** Live trace captured via the Python VM (`[TRACE] pc=0x081C op=0x24 …`) confirms the decoder sign-extends the 16-bit immediate to `-1620` and the current implementation stores `target = imm & 0xFFFFFFFF` before assigning it to `pc`. Because `rs1` is ignored and the PC-relative adjustment is never applied, the VM treats the signed offset as an absolute address (`platforms/python/host_vm.py:902`). Per `docs/hsx_spec-v2.md` §3, `CALL` is defined as a PC-relative control transfer that pushes the return address; compiled code expects the offset to be added to `pc + 4` and masked to the architectural address width. The missing PC-relative addition (and lack of 16-bit masking) causes any backward call to underflow into the guard path.
- **Remediation:** Restore the intended semantics in `MiniVM`: compute the call target as `(pc + imm)` when using the immediate form, fall back to `(regs[rs1] + imm)` when the register operand is used, and mask to the VM's address space (`0xFFFF`). Extend the range/limit checks to operate on the masked target so legal backward jumps survive. Add regression coverage that disassembles a short program containing backward calls and verifies the VM updates `pc` to `0x01C8` for this sample instruction. Update CLI/disassembler helpers if they assume absolute immediates.
- **Implementation:** `MiniVM` now derives the `CALL` target via PC-relative math with 16-bit masking, the assembler/linker emit matching offsets, and regression tests cover backward calls plus relocation math (`PYTHONPATH=. pytest python/tests/test_vm_callret.py python/tests/test_asm_local_relocs.py python/tests/test_reloc_patch_unit.py`).

Update this document after every working session—note partial progress, open questions, and where to pick up next.
