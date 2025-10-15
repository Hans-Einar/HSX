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
+ [x] Review approved (`(2)review.md`)
+ [x] Remediation plan approved (`(3)remediation.md`)
- [ ] Implementation tasks complete (see below)
- [ ] Tests updated/passing (unit + integration)
- [ ] Documentation updated (`docs/hsx_spec-v2.md`, CLI help)
- [ ] Implementation playbook current (`(5)implementation.md`)
- [ ] Git log updated (`(6)git.md`)
- [ ] Stakeholders signed off (runtime/executive leads)

## Implementation Tasks
- [ ] T1: Provision per-task register/stack arenas
  - [ ] Allocate memory slices during task load/spawn
  - [ ] Populate `reg_base`, `stack_base`, `stack_limit`, `sp16`
  - [ ] Persist bases in snapshots/resume
- [ ] T2: MiniVM register access via base pointers
  - [ ] Replace Python list register storage
  - [ ] Update context save/restore & debugger views
  - [ ] Add runtime assertions for non-zero bases
- [ ] T3: Scheduler & mailbox contract enforcement
  - [ ] Remove register cloning in `_store_active_state` / `_activate_task`
  - [ ] Ensure one-instruction stepping & wait queues
  - [ ] Implement scheduler instrumentation + CLI hooks
- [ ] T4: Tests, docs, demos
  - [ ] Add unit/integration tests from verification plan
  - [ ] Update documentation/help text
  - [ ] Capture evidence (stdout/mbox dumps, scheduler stats)

## Verification
- [ ] Unit tests added/updated: register isolation, stack guard, trap resume, fairness
- [ ] Integration tests updated: mailbox demo, deterministic clock stepping
- [ ] Manual validation complete: CLI commands, dumpregs showing non-zero bases

## Notes / Follow-ups
- Track potential performance regressions post-refactor; create new issue if profiling reveals hotspots.
- Consider creating a “new features” folder for scheduler instrumentation enhancements once core remediation lands.
