# DEFINITION OF DONE TEMPLATE

> File name: `(4)dod.md` (retain the numeric prefix when copying).

> Provide a concise status board for the issue. Keep this document up to date as work progresses.

## TL;DR
- Issue summary: Scheduler ignores register-window contract; context switches copy registers and disable stack guards.
- Review summary: See `(2)review.md` for spec references and divergence table.
- Remediation summary: `(3)remediation.md` outlines tasks T1–T4 to implement base-pointer switching, enforce the scheduler contract, and refresh tooling/tests.

## Quick Links
- Issue description: `./(1)issue.md`
- Review: `./(2)review.md`
- Remediation plan: `./(3)remediation.md`
- Implementation playbook: `./(5)implementation.md`
- Git log: `./(6)git.md`

## Completion Checklist
- [x] Review approved (`(2)review.md`)
- [x] Remediation plan approved (`(3)remediation.md`)
- [x] Implementation tasks complete (see below)
- [x] Tests updated/passing (unit + integration)
- [x] Documentation updated (`docs/hsx_spec-v2.md`, CLI help)
- [x] Implementation playbook current (`(5)implementation.md`)
- [x] Git log updated (`(6)git.md`)
- [ ] Stakeholders signed off (runtime/executive leads)

## Implementation Tasks
- [x] T1: Provision per-task register/stack arenas
  - [x] Allocate memory slices during task load/spawn (register/stack allocators in `VMController`)
  - [x] Populate `reg_base`, `stack_base`, `stack_limit`, `sp16` (load path assigns non-zero bases)
  - [x] Persist bases in snapshots/resume (`_store_active_state` / `_activate_task` reuse allocations)
- [x] T2: MiniVM register access via base pointers
  - [x] Replace Python list register storage (`RegisterFile` wrapper)
  - [x] Update context save/restore & debugger views (register window sync; CLI `dumpregs` updated)
  - [x] Add runtime assertions for non-zero bases (`_ensure_task_memory`, activation checks)
- [x] T3: Scheduler & mailbox contract enforcement
  - [x] Remove register cloning in `_store_active_state` / `_activate_task` (pointer reuse)
  - [x] Ensure one-instruction stepping & wait queues (unit test + instrumentation)
  - [x] Implement scheduler instrumentation + CLI hooks (`sched` command reports counters/trace)
- [x] T4: Tests, docs, demos
  - [x] Add unit/integration tests from verification plan (register isolation, stack guard, scheduler stats)
  - [x] Update documentation/help text
  - [x] Capture evidence (stdout/mbox dumps, scheduler stats) — see `issues/#2_scheduler/evidence.md`

## Verification
- [x] Unit tests added/updated: register isolation, stack guard, trap resume, fairness
- [x] Integration tests updated: mailbox demo, deterministic clock stepping (scheduler stats integration test)
- [x] Manual validation complete: CLI commands, dumpregs showing non-zero bases (`issues/#2_scheduler/evidence.md`)

## Notes / Follow-ups
- Track potential performance regressions post-refactor; create new issue if profiling reveals hotspots.
- Consider creating a “new features” folder for scheduler instrumentation enhancements once core remediation lands.
