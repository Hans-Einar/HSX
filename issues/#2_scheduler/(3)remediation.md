# REMEDIATION PLAN TEMPLATE

> File name: `(3)remediation.md` (retain the numeric prefix when copying).

> Turn the review findings into an actionable implementation plan.

## Overview
- Owner(s): Runtime/Executive team (Codex assisting)
- Target milestone / deadline: 2025-03-07
- Dependencies: None blocking, but coordinate with mailbox demo maintainers for regression validation.

## Objectives
- Implement the register-window model so context switches only update base pointers.
- Restore stack isolation and guard enforcement for every task.
- Enforce the scheduler contract: one instruction per step, robust wait/wake, instrumentation.
- Refresh tooling/tests/docs to reflect the new behaviour.

## Work Breakdown
| Task ID | Description | Owner | Status | Notes |
| --- | --- | --- | --- | --- |
| T1 | Provision per-task arenas (register + stack) and populate bases | Runtime | Not started | Update task spawn / load path |
| T2 | Refactor `MiniVM` to access registers via memory windows | Runtime | Not started | Ensure no Python list copies remain |
| T3 | Update scheduler & mailbox paths to honor base pointers and single-step contract | Executive | Not started | Includes invariants, wait queues |
| T4 | Instrumentation, tests, docs, CLI updates | Tooling/docs | Not started | Add coverage + doc refresh |

### Detailed Steps

#### T1 Provision per-task arenas
1. Update `VMController.load_from_path` to carve register banks and stack slices per PID.
2. Initialise `reg_base`, `stack_base`, `stack_limit`, and guest-visible `sp16`.
3. Ensure task snapshots persist these bases (no copying).

#### T2 Refactor MiniVM register access
1. Replace `self.regs` list usage with memory-backed getters/setters keyed by `reg_base`.
2. Update `set_context`/`save_context` to stop cloning register arrays.
3. Adjust debugger/register dump helpers to read through base-offset view.
4. Add assertions ensuring `reg_base`, `stack_base`, `stack_limit` are non-zero for active context.

#### T3 Scheduler & mailbox contract
1. Modify `_store_active_state` / `_activate_task` to operate via base pointers only.
2. Enforce one-instruction stepping in `MiniVM.step()` and executive loop (`python/execd.py`).
3. Rework wait/wake (`_prepare_mailbox_wait`, `_complete_mailbox_wait`) to avoid register copies and maintain ready queues.
4. Introduce invariant checks (non-zero bases, stack guard comparisons, SP masking).
5. Add scheduler trace counters (`STEP`, `TRAP`, `BLOCK`, `WAKE`, `HALT`) and expose CLI hooks (`clock step`, `sched stats`).

#### T4 Verification, instrumentation, docs
1. Implement unit tests covering register isolation, stack overflow, trap resume, mailbox wake.
2. Extend integration tests/demos (producer-consumer) to confirm behaviour under scheduler changes.
3. Update CLI help and `docs/hsx_spec-v2.md` to document the contract (steps vs cycles, register windows).
4. Capture before/after `mbox`, `dumpregs`, and scheduler stats in supporting docs.

## Verification Strategy
- **Unit tests:** add targeted cases under `python/tests/` for register window isolation, stack guard errors, scheduler fairness.
- **Integration tests:** rerun mailbox demo script; add deterministic stepping test for multiple tasks.
- **Manual validation:** verify CLI (`clock step`, `sched stats`), confirm `dumpregs` shows non-zero bases, run stack overflow demo.

## Rollout Plan
- Implement on feature branch `feature/scheduler-register-window`.
- Land tasks in order T1 → T2 → T3 → T4, with CI after each merge.
- Hold merges until unit/integration tests pass; tag release candidate once DoD met.
- Back-out plan: revert branch if regressions found; existing list-copy model still available via git history.

## Communication
- Weekly status ping to runtime/executive mailing list.
- Update `issues/INDEX.md` TL;DR once remediation underway.
- Notify documentation maintainers when spec/help updates are ready for review.
