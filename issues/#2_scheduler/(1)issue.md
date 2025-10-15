# ISSUE TEMPLATE

> File name: `(1)issue.md` (retain the numeric prefix when copying).

> Copy this file into a new issue directory and replace placeholders.

## Title
- Working title: `Scheduler register-window divergence`
- Tracking ID: `#2`
- Reported by: Runtime team (user feedback via HSX shell investigation)
- Date opened: `2025-02-14`

## Summary
- The Python host VM/executive ignores the register-window model described in `hsx_spec-v2.md`.
- Context switches copy Python lists instead of swapping `reg_base`/`stack_base`, leaving stack guards inactive and bloating the scheduler.

## Context
- **Expected behaviour:** per spec §5.2, tasks own disjoint register/stack arenas; context switch updates `{pc, psw, reg_base, stack_base, stack_limit}` and executes one instruction per turn.
- **Current behaviour:** all tasks share a single register list and stack; `dumpregs` shows `reg_base`, `stack_base`, `stack_limit` fixed at zero; scheduler copies registers on every swap.
- **Environment:** HSX repository `HEAD` (2025-02-14), Python VM (`platforms/python/host_vm.py`), executive (`python/execd.py`).
- **Reproduction steps:**
  1. Launch HSX manager, load `examples/demos/build/mailbox/consumer.hxe` and producer.
  2. Run `ps` / `dumpregs` for each PID.
  3. Observe zero bases and identical register dumps across tasks.
  4. Inspect scheduler code to confirm list copies and missing base enforcement.

## Evidence
- `issues/#2_scheduler/hsx_scheduler_implementation_review.md` — analysis of spec vs. implementation.
- Shell transcript (`dumpregs`) showing zero bases (see user logs).
- Source references: `platforms/python/host_vm.py` (context handling), `python/execd.py` (scheduler loop).

## Impact
- **Severity:** High — blocks AVR port and undermines isolation/stack safety.
- **Affected components:** Python VM scheduler, mailbox wait handling, debugger tooling, documentation.
- **Dependencies:** Mailbox workstream uses scheduler guarantees; future hardware ports depend on this fix.

## Stakeholders
- Owner: Runtime / Executive team (Codex assisting)
- Reviewer(s): Firmware architecture lead, VM maintainers
- Notified teams: Demo/app owners (producer/consumer), tooling/docs maintainers

## Initial Notes / Hypotheses
- Register windows never migrated from prototype to production VM.
- Stack-guard checks compare against zero and therefore never fire.
- Scheduler still steps one instruction, but state bookkeeping violates the contract.
