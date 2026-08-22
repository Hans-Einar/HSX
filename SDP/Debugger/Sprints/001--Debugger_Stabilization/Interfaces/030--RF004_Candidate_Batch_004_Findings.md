# RF-004 candidate Batch004 — execution result and post-execution acceptance findings

Status: **CANDIDATE EVIDENCE / PASS WITH KNOWN BASELINES / POST-PASS 1.9 REWORK STAGED**

Test authority: issue #38 `MASTER -> TESTER` comment `5380682574`.
Tester result: issue #38 comment `5380705374`.
Exact tested candidate head: `786b318d76d2dffba58152657122bbeea8975979`.
Authoritative RF-004 branch remained `codex/dbg-rf-004@46169516058aadf0e691a5981e29da4954b7444f` and was not mutated.

## Mechanical execution result

The read-only TESTER correctly classified Batch004 as
`CANDIDATE_EXECUTION_PASS_WITH_KNOWN_BASELINES`.

Evidence:

- exact requested, remote and tested candidate head matched;
- fresh temporary checkout and final checkout were clean;
- syntax/import phase passed;
- all 22 candidate-specific test files exited zero;
- candidate aggregate: `103 passed` plus exactly one expected strict XFAIL P002;
- direct signed CS-IMM-103 passed in a fresh process;
- concurrency/race set: seven tests repeated `20/20`, no failing iteration;
- signed RF-004 oracle: `159 passed, 3 skipped`;
- debugger-core aggregate after the plan-authorized shell wildcard correction:
  `383 passed, 3 skipped, 1 xfailed`;
- full Python aggregate: `917 passed, 5 skipped, 1 xfailed` plus exactly the two already
  accepted historical baseline failures:
  - `python/tests/test_hsx_dbg_commands.py::test_break_add_symbol_line`;
  - `python/tests/test_shell_client.py::test_pretty_dmesg_assigns_session_numbers`;
- final `git status --porcelain` empty, `git diff --exit-code` zero, `git diff --check` zero;
- test execution caused no tracked mutation.

The one candidate XFAIL was P002: the `validate_location_row` type-error text still says
`UnwindRow` rather than `LocationRow`. It is cosmetic but remains an explicit promotion cleanup.

## What Batch004 proved

Batch004 independently executed the candidate state through interface 1.8, including:

- v1.3 row-key scalar caller-GPR binding;
- v1.4 lifecycle result envelopes;
- v1.5 exact `symbol_by_id` query;
- v1.6 trustworthy stack-prefix result envelopes;
- v1.7 dedicated epoch-reference result envelopes with unchanged CS-IMM-103;
- v1.8 row-aware top-frame frame-base semantics;
- current ABI entry-before-PUSH / entry-after-PUSH / ordinary-body / epilogue-after-POP /
  terminal row fixtures;
- frame-base-dependent local evaluation only when frame-base evidence exists;
- StackService and InspectionService dependency contract fencing;
- page-before-evaluation variable behavior;
- partial memory/disassembly preservation;
- lifecycle/constructor invariants;
- exact stale/no-I/O behavior and revision fences;
- real DebugArtifactIndex -> Stack -> Inspection integration;
- concurrent frame/scope/variable handle interning.

No Executive, VM, AVR, DAP, CLI, VS Code or RF-005+ product surface was involved.

## Post-Batch004 acceptance audit

A green batch was not treated as completion authority. Master re-read Slice005/006 completion
criteria and accepted HSX-D-002 / HSX-ST-007 after execution.

### Finding A — caller continuation still used legacy resume-PC fallback

Pre-1.9 StackService correctly refused to publish `call_site_pc` without CALL proof, but then
used `resume_pc` as the next caller `UnwindFrame.pc`. Accepted HSX-ST-007 explicitly identifies
using return/resume PC directly for caller lookup as legacy/degraded behavior. This could select
source/location/unwind rows at the instruction after CALL rather than at the suspended caller
instruction.

Disposition: **REAL semantic gap; refrozen as `dbg.resolver-inspection/1.9`.**

Steering authority: issue #38 `5380763854`.
Conformance: `029--RF004_Call_Semantic_Proof_Conformance_v1_9.md`.

The post-Batch004 candidate now has:

- bounded `instruction_semantics.py` for exact `hsx.fixed32/1` CALL proof;
- canonical toolchain cross-check against stable `python/opcodes.py` CALL=`0x24` and existing
  fixed32 primary-opcode decode;
- StackService continuation only after exact checked CALL proof;
- missing semantics => UNAVAILABLE/PARTIAL prefix;
- non-CALL => CORRUPT prefix;
- unsupported encoding => UNSUPPORTED prefix;
- metadata contract faults => CORRUPT prefix;
- no resume-PC fallback and no caller-SP/GPR reads after call-site proof already failed;
- a half-open caller row fixture that contains call-site PC but excludes resume PC, proving
  subsequent row selection uses the correct address.

These 1.9 changes are **post-Batch004 and not yet independently executed**. Batch005 must cover
them before candidate-complete status is considered.

### Finding B — explicit unsupported boundary

Master considered whether `UnwindBoundary.UNSUPPORTED` should still publish the current frame.
No change was made. 1.6 permits only frames whose required PC/SP/CFA evidence was completed
before termination, while an explicitly unsupported row is authority not to interpret that
machine state further. The existing fail-before-CFA behavior remains conservative and the
current test remains valid pending independent review.

### Finding C — best-effort live evidence gate

No Slice006 fix was required. Signed identity/epoch foundation already requires
`EvidenceGrade.PORTABLE` for coherent `EpochBinding`, rejects `BEST_EFFORT_LIVE`, and
`ControllerEpochAdapter` performs the same portable-evidence gate. InspectionService therefore
cannot legitimately receive a coherent best-effort-live context through the public typed
construction path.

## Completion implication

Batch004 is a strong green baseline but is superseded as candidate-completion evidence by the
post-pass 1.9 semantic correction. No Slice005/006 review/sign-off or promotion may cite
Batch004 alone as the final candidate head.

Next execution gate: Batch005 on the exact post-1.9 candidate head, followed by the frozen fresh
5.6 independent review/promotion sequence. RF-005..009 remain blocked.