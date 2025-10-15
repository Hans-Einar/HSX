# REVIEW TEMPLATE

> File name: `(2)review.md` (retain the numeric prefix when copying).

> Summarise the technical assessment that diagnoses the issue. Use this as the canonical gap analysis.

## Reviewer
- Name / role: Codex (assistant)
- Date: 2025-02-14
- Artifacts reviewed: `docs/hsx_spec-v2.md`, `platforms/python/host_vm.py`, `python/execd.py`, mailbox demo traces

## Spec & Contract References
- `docs/hsx_spec-v2.md` §5.2 “VM Context Model” and §5.3 “Scheduling Model”
- `docs/hsx_spec-v2.md` §5.4 “Mailboxes & Wait Semantics”

## Observed Divergence
| Area | Expected behaviour | Actual behaviour | Evidence (logs/files) |
| --- | --- | --- | --- |
| Register storage | GPRs addressed via `reg_base + N*4`; swapping base suffices. | `TaskContext.regs` is a Python list copied on each swap; `reg_base` stays `0`. | `platforms/python/host_vm.py` (`set_context`, `_activate_task`), `dumpregs` output |
| Stack relocation | Private stack per task with guard (`stack_base`, `stack_limit`). | Bases remain `0`; CALL/PUSH guard comparisons never trip. | `platforms/python/host_vm.py:760`, shell traces |
| Context hand-off | Scheduler updates `{pc, psw, reg_base, stack_base}` then steps once. | `_store_active_state`/`_activate_task` clone register arrays; bases ignored. | Same source files |
| Wait/wake bookkeeping | Waiters resume using base pointers; no register copies. | WAIT path still relies on copied register list (`state["context"]["regs"]`). | `_complete_mailbox_wait` |
| Debugger/register dump | Should reflect base-offset registers. | Debugger returns cached Python list, hiding divergence. | `platforms/python/host_vm.py:2334`, `python/shell_client.py` |

## Root Cause Analysis
- Register-window indirection never implemented in the Python VM; legacy list-copy scaffold persisted.
- Stack arenas were not carved per task, leaving guard values zero.
- Scheduler and mailbox resume logic were built around cloning `regs`, so base pointers fell out of sync.
- Tooling (`dumpregs`, debugger) reads cached lists, masking the missing base pointers.

## Suggested Direction
- Allocate per-task register/stack arenas in VM RAM.
- Rework `MiniVM` to operate directly on memory so context switches only update base pointers.
- Rewrite scheduler state transitions to stop cloning register arrays and enforce one-instruction steps via the contract.
- Update tooling and tests to assert non-zero bases and functional stack guards.

## Risks / Side Effects
- Refactor touches core VM state handling; regression risk for all runtime features.
- Need to confirm performance once indirection is introduced (Python overhead acceptable?).
- Stack arena sizing must consider legacy demos/tests to avoid regressions.

## Sign-off / Next Steps
- Approve remediation plan outlined in `(3)remediation.md`.
- Spin follow-up docs/tests as listed in Definition of Done once implementation lands.
