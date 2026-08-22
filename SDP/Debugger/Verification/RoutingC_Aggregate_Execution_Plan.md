# RF-004 Routing-C Aggregate Execution Plan

Status: **READ-ONLY execution gate**

Parent: `DBG-RF-004`
Origin review: `DBG-RVW-001-005-037` / issue #38 comment `5381348250`
Review remediation: `DBG-CR-002` -> `DBG-GAP-002`
Corrective children: `DBG-RF-010`, `DBG-RF-011`
Bounded parent Low rework: `DBG-F-029`
Coordination: issues #54, #55, #56

## Purpose

Execute the complete Routing-C correction set in one fresh read-only checkout before any fresh
independent review. This plan verifies execution only; it does not sign either corrective child
or the parent RF-004.

## Authority and branch discipline

- frozen reviewed candidate: `514f7f1cdf8420ccaf6ae84d14b20e4d13931cdc`;
- test branch: `master/rf004-routing-c-remediation`;
- Draft PR #50 must remain on `codex/dbg-rf-004` and must not be retargeted or updated;
- `master/rf004-v13-candidate` must remain exactly at the frozen reviewed candidate;
- use a fresh temporary clone or detached clean checkout;
- do not modify tracked files, delete generated files, autofix, commit, push, rebase or merge;
- put any long logs in OS temp, not in the repository.

The exact test HEAD is the branch HEAD containing this plan. The MASTER -> TESTER issue comment
must name that SHA explicitly; a mismatch is `BLOCKED_HEAD_MISMATCH`.

## Expected remediation diff from the frozen candidate

Permitted product/test changes are only:

1. `python/hsx_debugger/stack.py` — F-027 exact checked CALL-site address fence;
2. `python/tests/test_hsx_debugger_rf010_call_site_fence.py` — adversarial F-027 evidence;
3. `python/hsx_debugger/inspection.py` — F-028 explicit factory dependencies;
4. `python/tests/test_hsx_debugger_rf011_factory_dependencies.py` — omitted-dependency/public-signature evidence;
5. `python/hsx_debugger/recipes.py` — F-029 diagnostic wording only;
6. `python/tests/test_hsx_debugger_candidate_guards.py` — remove only the now-closed P002 xfail wrapper.

Additional changed files may be SDP-only Routing-C evidence/current-state documents. No
Executive/VM/AVR/DAP/CLI/VS Code/frontend or RF-005..009 product path is permitted.

## Phase A — exact authority and integrity

Record:

```text
git rev-parse HEAD
git status --porcelain
git diff --exit-code
git diff --check
git rev-parse origin/master/rf004-routing-c-remediation
git rev-parse origin/master/rf004-v13-candidate
```

Require:

- local HEAD == remote remediation branch exact instructed SHA;
- frozen candidate remote == `514f7f1cdf8420ccaf6ae84d14b20e4d13931cdc`;
- clean worktree and diff-check PASS.

Also compare frozen candidate -> test HEAD and report every changed path.

## Phase B — Routing-C focused remediation

Set `PYTHONPATH=python` and run every command even if an earlier command fails:

```text
python -m pytest python/tests/test_hsx_debugger_rf010_call_site_fence.py -q --tb=short
python -m pytest python/tests/test_hsx_debugger_rf011_factory_dependencies.py -q --tb=short
python -m pytest python/tests/test_hsx_debugger_candidate_guards.py -q --tb=short
python -m pytest python/tests/test_hsx_debugger_call_site_v19.py python/tests/test_hsx_debugger_instruction_semantics_v19.py -q --tb=short
python -m pytest python/tests/test_hsx_debugger_stack.py python/tests/test_hsx_debugger_stack_dependency_contracts.py -q --tb=short
python -m pytest python/tests/test_hsx_debugger_inspection.py python/tests/test_hsx_debugger_service_precedence.py -q --tb=short
python -m pytest python/tests/test_hsx_debugger_recipe_v13.py python/tests/test_hsx_debugger_metadata.py -q --tb=short
```

Required candidate state:

- F-027 suite: 2 PASS;
- F-028 suite: 5 PASS;
- candidate guards: 5 PASS, **zero XFAIL**;
- no failure/error/unexpected skip in any focused command.

Specifically report that:

- wrong-address resolved CALL evidence returns `CORRUPT / call_site_index_contract`, preserves
  the trustworthy top-frame prefix and performs no saved-R7/post-proof caller-state read;
- exact-address CALL still succeeds;
- omitting either composition dependency independently, or both, fails at the Python call
  boundary;
- explicit dependency injection is retained unchanged;
- LocationRow diagnostic guard is ordinary PASS, not XFAIL.

## Phase C — concurrency/stress

Run 20 iterations. In every iteration execute together:

```text
python -m pytest \
  python/tests/test_hsx_debugger_handles.py \
  python/tests/test_hsx_debugger_query_races.py \
  python/tests/test_hsx_debugger_scope_variable_concurrency.py \
  python/tests/test_hsx_debugger_stale_no_io.py \
  python/tests/test_hsx_debugger_rf010_call_site_fence.py \
  python/tests/test_hsx_debugger_rf011_factory_dependencies.py \
  -q --tb=short
```

All 20 iterations must exit 0. Report aggregate pass count and any failure/skip/xfail.

## Phase D — signed RF-004 regression oracle

Run the same signed RF-004 oracle used by Batch005. If the exact command is recorded in
`SDP/Debugger/Sprints/001--Debugger_Stabilization/Interfaces/033--RF004_Batch005_Completion_Execution_Plan.md`, use it verbatim. Expected historical signal from Batch005 is `159 passed, 3 skipped`, with no failure/error.

## Phase E — signed RF-002/RF-003 first-wave signal

Run:

```text
python -m pytest \
  python/tests/test_hsx_debugger_contracts.py \
  python/tests/test_hsx_debugger_controller.py \
  python/tests/test_hsx_debugger_gateway.py \
  python/tests/test_hsx_debugger_controller_gateway.py \
  -q --tb=short
```

Expected signal: `81 passed`, no failure/error.

## Phase F — complete debugger-core aggregate

In PowerShell enumerate the files rather than passing an unexpanded wildcard to pytest:

```powershell
$files = Get-ChildItem python/tests/test_hsx_debugger_*.py | ForEach-Object { $_.FullName }
& $python -m pytest @files -q --tb=short
```

Equivalent shell enumeration is acceptable on other platforms.

Expected after Routing-C fixes: approximately `403 passed, 3 skipped`, **zero xfail**, no
failure/error. Exact count may differ only if file discovery legitimately differs; list every
skip/xfail/failure/error explicitly. Any XFAIL is candidate-specific and is a failure of this
gate unless independently explained as an already frozen environment skip.

## Phase G — broad Python baseline

Run all `python/tests` and continue even if exit is non-zero. Expected historical failures are
only:

1. `python/tests/test_hsx_dbg_commands.py::test_break_add_symbol_line` — ignored/generated demo
   `main.sym` absent;
2. `python/tests/test_shell_client.py::test_pretty_dmesg_assigns_session_numbers` —
   optional-tabulate formatting baseline.

Batch005 had `929 passed, 5 skipped, 1 xfailed, 2 failed`. Because P002 is now fixed and seven
new RF-010/RF-011 tests exist, an equivalent environment is expected near `937 passed, 5 skipped,
0 xfailed, 2 failed`. Counts are secondary to node IDs: **any failure/error other than the two
listed historical baselines is a Routing-C regression**.

## Phase H — scope audit

Confirm frozen candidate -> test HEAD changes no protected product path:

- no Executive/session/runtime adapter product change;
- no VM/platform product change;
- no AVR product change;
- no DAP/CLI/VS Code/frontend product change;
- no RF-005..009 product implementation.

Confirm the frozen candidate ref itself did not move.

## Phase I — final integrity

After every test phase:

```text
git rev-parse HEAD
git status --porcelain
git diff --exit-code
git diff --check
```

Require exact unchanged HEAD, empty tracked status and no tracked mutation.

## Mechanical classification

Use `ROUTING_C_EXECUTION_PASS_WITH_KNOWN_BASELINES` only if:

- exact-head/frozen-ref checks pass;
- all focused Routing-C tests pass with zero XFAIL;
- all 20 stress iterations pass;
- signed RF-004 and RF-002/RF-003 signals have no failure/error;
- debugger-core aggregate has no failure/error and no candidate XFAIL;
- broad Python failures are only a subset of the two explicitly accepted historical baselines;
- scope audit and final repository integrity pass.

Otherwise use `ROUTING_C_EXECUTION_FAIL` or `BLOCKED` and report exact evidence. Do not fix.

## After execution

A PASS permits Master to append final traceability/evidence and prepare fresh independent review.
It does **not** itself complete or sign `DBG-RF-010`, `DBG-RF-011` or parent `DBG-RF-004`.
