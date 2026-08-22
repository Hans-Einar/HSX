# RF-004 candidate batch 002 — read-only execution plan

Status: **MASTER CANDIDATE TEST GATE / NOT SIGN-OFF**

Parent: `DBG-RF-004`
Candidate branch: `master/rf004-v13-candidate`
Authoritative PR #50 branch remains `codex/dbg-rf-004` and MUST NOT be mutated by this test gate.

Batch002 validates the correction/refreeze work accumulated after batch001. The TESTER is
strictly read-only and must continue through every phase even when an earlier phase fails.
The complete failure set is more valuable than fail-fast behavior in this candidate gate.

## Expected known classifications before execution

- `python/tests/test_hsx_debugger_candidate_guards.py::test_location_validator_type_error_names_location_row`
  is one intentional **strict xfail** for promotion cleanup P002 only. An XPASS is a failure
  because the recorded promotion state would then be stale.
- `python/tests/test_shell_client.py::test_pretty_dmesg_assigns_session_numbers` is a known
  unrelated broad-suite baseline failure and is not RF-004 repair authority.
- No other RF-004 candidate failure/xfail is expected.

## Phase A — fresh-process syntax/import/bootstrap

From repository root with `PYTHONPATH=<repo>/python`:

```powershell
C:\Users\hanse\miniconda3\python.exe -m compileall -q python\hsx_debugger
C:\Users\hanse\miniconda3\python.exe -c "import hsx_debugger; from hsx_debugger import EvidenceGrade; from hsx_debugger.results import _deep_freeze; assert _deep_freeze(EvidenceGrade.PORTABLE, 'evidence') is EvidenceGrade.PORTABLE"
```

Both commands must run in a fresh process. Record exit codes separately.

## Phase B — candidate-focused matrices

Run each command independently and continue after failures:

```powershell
C:\Users\hanse\miniconda3\python.exe -m pytest python/tests/test_hsx_debugger_candidate_lifecycle_guards.py -q
C:\Users\hanse\miniconda3\python.exe -m pytest python/tests/test_hsx_debugger_recipe_v13.py -q
C:\Users\hanse\miniconda3\python.exe -m pytest python/tests/test_hsx_debugger_artifact_v15.py -q
C:\Users\hanse\miniconda3\python.exe -m pytest python/tests/test_hsx_debugger_stack.py -q
C:\Users\hanse\miniconda3\python.exe -m pytest python/tests/test_hsx_debugger_handles.py -q
C:\Users\hanse\miniconda3\python.exe -m pytest python/tests/test_hsx_debugger_inspection.py -q
C:\Users\hanse\miniconda3\python.exe -m pytest python/tests/test_hsx_debugger_candidate_guards.py -q
```

Required semantic evidence includes:

- deterministic contract Enum bootstrap independent of pytest import order;
- v1.3 exact row-key binding for unsigned scalar GPR recovery;
- real `DebugArtifactIndex.symbol_by_id()` exact identity/cardinality behavior;
- StackService read-set fencing before register I/O;
- exact selection validation before Inspection register I/O;
- `StackWalkResult` preserves already-proven frames while retaining exact
  CORRUPT/UNSUPPORTED/STALE termination;
- unavailable continuation maps to PARTIAL only when a trustworthy prefix exists;
- no fixed-R7 or younger-frame inference without explicit recipe evidence;
- no call-site publication without accepted portable CALL-semantic evidence;
- `StackPageResult` preserves stack termination while exposing/interning only proven prefix frames;
- a handle for a proven prefix frame remains usable while the exact epoch is active even if
  continuation is corrupt;
- actual epoch invalidation wins over late snapshot reads/handle publication;
- same-key concurrent handle interning is deterministic;
- close is terminal and wins over later stale-context/limit classification.

## Phase C — signed RF-004 regression oracle

Run the signed RF-004 regression set unchanged:

```powershell
C:\Users\hanse\miniconda3\python.exe -m pytest \
  python/tests/test_hsx_debugger_addresses.py \
  python/tests/test_hsx_debugger_identity.py \
  python/tests/test_hsx_debugger_results.py \
  python/tests/test_hsx_debugger_metadata.py \
  python/tests/test_hsx_debugger_snapshot.py \
  python/tests/test_hsx_debugger_recipes.py \
  python/tests/test_hsx_debugger_artifacts.py \
  python/tests/test_hsx_debugger_legacy_symbols.py \
  python/tests/test_hsx_debugger_sources.py -q
```

If PowerShell line continuation is inconvenient, run the same file list on one command line.
Record exact PASS/FAIL/XFAIL/SKIP counts and every failing nodeid.

## Phase D — broad Python regression

```powershell
C:\Users\hanse\miniconda3\python.exe -m pytest python/tests -q
```

Do not stop at the known shell-client baseline failure. Report every failing nodeid and whether
any failure is new relative to batch001.

## Phase E — repository integrity and exact diff

After all tests:

```powershell
git status --porcelain
git diff --exit-code
git diff --stat 46169516058aadf0e691a5981e29da4954b7444f..HEAD
git diff --name-only 46169516058aadf0e691a5981e29da4954b7444f..HEAD
```

Test execution must not mutate tracked repository state. Generated/untracked files must be
reported and must not be committed, deleted, formatted, or otherwise repaired by TESTER.

## Required TESTER report

Post one issue #38 comment beginning exactly:

`HSX | TESTER -> MASTER | RF-004 candidate batch 002 result`

Include:

- requested candidate HEAD and exact tested HEAD;
- observed remote candidate branch HEAD;
- pre-test worktree status;
- every exact command and exit code;
- Phase A fresh-process result;
- Phase B result per test file including PASS/FAIL/XFAIL/SKIP counts and failing nodeids;
- whether the sole expected P002 strict xfail remained XFAIL or became XPASS;
- Phase C exact counts/failures;
- Phase D exact counts/failures and explicit classification of the known shell-client baseline;
- post-test status/diff integrity;
- diff stat/name-only against authoritative `461695...`;
- conclusion `PASS`, `FAIL`, or `BLOCKED` for candidate execution only.

Do not propose fixes. Do not edit any file. Do not commit, push, update PR #50, or modify SDP.
Stop after posting the report.
