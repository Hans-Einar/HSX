# HSX Scheduler & Context Switching — Implementation Review

Reviewer: Codex (assistant)  

This note compares the intended behaviour from `docs/hsx_spec-v2.md` with the current Python prototype (`platforms/python/host_vm.py`, `python/execd.py`, `python/mailbox.py`). The goal is to highlight divergences that matter for a lightweight scheduler and to anchor the remediation work.

## 1. Spec Reference

Relevant excerpts (see `docs/hsx_spec-v2.md:125-158`):

- **Register window indirection:** `R0..R15` must be addressed as `reg_base + N*4`. Context switching only updates `reg_base`.
- **Stack relocation:** guest SP = `stack_base + (vm.sp & 0xFFFF)`. Swapping `stack_base` yields an O(1) switch, with `stack_limit` guarding overflows.
- **Context switch contract:** executive updates `{pc, psw, reg_base, stack_base}` (and `stack_limit`) then runs `vm.step()`. No register copies.
- **Isolation & guards:** each task has disjoint arenas; `stack_limit` is mandatory for overflow detection.

## 2. Observed Behaviour

| Area | Spec expectation | Current Python implementation | Impact |
| --- | --- | --- | --- |
| Register storage | Registers live in VM RAM behind `reg_base`. | `TaskContext.regs` is a Python list copied during `snapshot_state` / `_activate_task`. `reg_base` is always `0`. | Context switch cost is O(16) assignments + GC pressure; violates “repointer only” design; makes AVR port harder. |
| Stack relocation | `stack_base`/`stack_limit` define a private stack window. | Both values remain `0`; CALL/PUSH guards compare against zero and never trip. Guest SP is the raw VM `sp`. | No overflow protection, tasks share the same physical stack space, spec guard rails missing. |
| Context hand-off | Scheduler writes bases and PC then steps the VM. | `_store_active_state` clones the full register array into the task record; `_activate_task` copies it back. Bases are ignored. | Round-robin still works, but switches are copy-heavy and state snapshots diverge from spec. |
| Mailbox wait wake | WAIT transitions recorded, but guard uses context bases. | WAIT bookkeeping works, yet because bases are zero, reactivation continues to rely on the copied register array. | No direct failure, but once bases are honoured this logic must stop copying `regs`. |
| Debugger/read-regs | Access via base pointers. | `read_regs` returns the cached Python list; dumping registers never shows base offsets. | Tooling conceals the missing register windows, hiding bugs. |

## 3. Why This Matters

1. **Portability:** The AVR target assumes switching means “load two pointers”. The current code can’t be down-ported without a rewrite.
2. **Correctness:** Stack guards never fire; any runaway recursion corrupts shared state silently.
3. **Performance:** Even in Python the copy-based approach costs more than pointer swaps. On small MCUs it would be prohibitive.

## 4. Recommended Remediation (High Level)

1. **Allocate per-task arenas** in VM RAM at spawn time (`VMController.load_from_path`):
   - Reserve N×16×4 bytes for registers (one bank per task).
   - Reserve stack slices; set `stack_base`, `stack_limit`, and initialise `vm.sp`.
2. **Teach `MiniVM`** to read/write registers through `reg_base`:
   - Replace the Python list with lightweight accessors into the memory window.
   - If a cache is kept for performance, it must stay coherent without “flushes” during context switch—ideally the VM operates directly on memory so no flush step is needed.
3. **Rework scheduler hand-off**:
   - `_store_active_state` should capture PC/flags and any mailbox wait metadata, **not** duplicate registers.
   - `_activate_task` updates bases, PC, PSW, and stack/SP, then calls `set_context`.
4. **Stack guard enforcement**:
   - Ensure CALL/PUSH/POP and RET checks compare against `stack_limit`.
   - Add unit tests that deliberately overflow a small stack and expect `HSX_ERR_STACK_OVERFLOW`.
5. **Tooling updates**:
   - `dumpregs`, debugger, and shell output must read registers via base pointers so divergence cannot hide.
   - Document the memory layout in the developer docs once implemented.

## 5. Tracking & Next Steps

- Add remediation tasks to `mailbox_update_implementation.md` (or a dedicated scheduler plan) so they stay visible.
- Gate new runtime work until the register-window model is in place; otherwise further fixes risk compounding the divergence.
- When refactoring, keep the “no flush” requirement front and centre: operate directly on VM RAM so swapping the base pointers rebinds the register window with no extra copies.

Once these items are addressed, we should re-run the mailbox demo and the scheduler regression tests to confirm both behaviour and performance match the spec.
