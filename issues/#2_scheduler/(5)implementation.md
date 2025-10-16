# Implementation Playbook — Scheduler Register-Window Remediation

> File name: `(5)implementation.md`. Keep this document updated as work progresses.

## Overview
- Issue: Scheduler ignores register-window contract (`issues/#2_scheduler`).
- Current status: In progress (T1 active; next step migrate MiniVM to new reg_base/stack_base).
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

-### T2 MiniVM register access via base pointers (`active`)
- [x] Replace direct list usage (`self.regs`) with memory-backed getters/setters.
  - Implemented `RegisterFile` wrapper; instruction handlers now access register window via memory, keeping `ctx.regs` in sync.
- [x] Update `set_context`, `save_context`, and `snapshot_registers` to avoid cloning arrays.
  - Context transitions now sync register banks via `RegisterFile`; `save_context` captures values from memory.
- [x] Adjust debugger helpers (`read_regs`, shell `dumpregs`) to read via base offset.
  - `VMController.read_regs()` now exposes `reg_base`/`stack_base`/`sp_effective`; CLI `dumpregs` prints the new fields.
- [x] Add runtime assertions: active tasks must have non-zero `reg_base`, `stack_base`, `stack_limit`.
  - `_ensure_task_memory` verifies allocations and `_activate_task` raises if bases are missing.
- [ ] Run unit tests covering register read/write to ensure behaviour unchanged.

### T3 Scheduler & mailbox contract enforcement (`not started`)
- [ ] Simplify `_activate_task` / `_store_active_state` to use base pointers only.
- [ ] Guarantee `MiniVM.step()` retires exactly one instruction; remove implicit loops.
- [ ] Update executive loop (`python/execd.py`) to honour one-instruction steps and rotate READY queue.
- [ ] Rework mailbox wait/wake (`_prepare_mailbox_wait`, `_complete_mailbox_wait`) to stop copying registers, maintain wait queues, and enforce invariants.
- [ ] Add scheduler instrumentation: trace ring + per-task counters.
- [ ] Implement CLI hooks (`clock step`, `clock step -p`, `sched stats`) reflecting new metrics.

### T4 Tests, docs, demos (`not started`)
- [ ] Create/extend unit tests: register-window isolation, stack overflow, trap resume, RR fairness.
- [ ] Update integration tests/demos (mailbox producer/consumer) to assert behaviour under new scheduler.
- [ ] Refresh documentation (`docs/hsx_spec-v2.md`, CLI help) to reflect “one step = one instruction” and base-pointer model.
- [ ] Capture evidence: `dumpregs`, `mbox`, scheduler stats before/after refactor.
- [ ] Coordinate final review and stakeholder sign-off.

## Context & Artifacts
- Key source files: `platforms/python/host_vm.py`, `python/execd.py`, `python/mailbox.py`, `python/shell_client.py`, docs under `docs/`.
- Tests to touch: `python/tests/` suite (scheduler/mailbox), demo scripts under `examples/`.
- Useful commands: `python python/disassemble.py ...`, HSX shell `clock step`, `dumpregs`, `mbox`, CI test runners.

## Handover Notes
- Current status: T1 complete; T2 in progress (MiniVM now backed by register windows).
- Known blockers: None.
- Next action when resuming: Update debugger/CLI helpers to consume the register window and plan coverage (assertions/tests).

Update this document after every working session—note partial progress, open questions, and where to pick up next.
