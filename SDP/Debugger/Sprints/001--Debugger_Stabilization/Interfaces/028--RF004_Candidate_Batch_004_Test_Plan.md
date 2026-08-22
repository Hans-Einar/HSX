# RF-004 Candidate Batch 004 — Read-only aggregate execution plan

Status: **CANDIDATE TEST PLAN ONLY / NO REVIEW OR SIGN-OFF AUTHORITY**

Candidate branch: `master/rf004-v13-candidate`.
The issue #38 `MASTER -> TESTER` task freezes the exact commit to execute.

## Purpose

Batch004 is the first aggregate execution after the full post-batch003 Slice005/Slice006 acceptance audit. It must validate both the existing candidate chain and all newly added/fixed semantics in one fresh checkout.

New post-batch003 evidence includes:

- `dbg.resolver-inspection/1.8` row-aware current-frame `frame_base`;
- explicit current ABI ENTRY / after-PUSH / ORDINARY / after-POP EPILOGUE / TERMINAL row matrix;
- frame-base LocationEvaluator behavior across those row phases;
- StackService dependency result/type fencing;
- variable page-before-evaluation isolation;
- PARTIAL memory/disassembly preservation;
- lifecycle/control envelope invariants;
- exact handle/page/scope/variable constructor invariants;
- disassembly metadata/byte mismatch classification;
- concurrent repeated scope/variable handle stability;
- all earlier 1.3..1.7 candidate evidence.

## Tester role and repository safety

The TESTER is strictly read-only.

Forbidden:
- editing source/tests/docs/SDP;
- formatter/autofix commands that write files;
- commit/amend/rebase/merge/push;
- PR changes;
- issue comments other than the one final result comment requested by the dispatch;
- generating/repairing the known missing demo `.sym` inside the checkout;
- deleting generated files to manufacture a clean result.

Use a brand-new temporary clone outside all user working repositories. Put any captured logs under OS temp, never inside the repository checkout.

Set:

```powershell
$env:PYTHONDONTWRITEBYTECODE = "1"
$env:PYTHONPATH = "$root\python;$root\python\tests"
```

Use `C:/Users/hanse/miniconda3/python.exe` if present; otherwise use the repository-configured Python and report the exact executable.

**Do not fail-fast across phases or files.** Execute every phase and capture every exit code unless the repository cannot be imported/executed at all.

## Phase A — exact authority / fresh-process integrity

1. Fresh temporary clone of `Hans-Einar/HSX`.
2. Fetch and checkout the exact requested candidate HEAD detached.
3. Prove `origin/master/rf004-v13-candidate` resolves to the same SHA.
4. Report `git rev-parse HEAD`, `git status --porcelain`, `git diff --exit-code`, and `git diff --check`.
5. AST-parse every `python/hsx_debugger/*.py` file without writing bytecode.
6. Import in one fresh process:
   - `hsx_debugger`
   - `hsx_debugger.recipes`
   - `hsx_debugger.artifacts`
   - `hsx_debugger.stack`
   - `hsx_debugger.handles`
   - `hsx_debugger.inspection_records`
   - `hsx_debugger.inspection`
7. Fresh-process direct CS-IMM guard:

```python
from hsx_debugger import EvidenceGrade
from hsx_debugger.results import _deep_freeze
try:
    _deep_freeze(EvidenceGrade.PORTABLE, "evidence")
except TypeError:
    pass
else:
    raise AssertionError("EvidenceGrade must not be admitted as a direct generic payload")
```

All Phase A commands must exit zero.

## Phase B — complete candidate must-pass suite

Run **each file separately** with `-q --tb=short`; capture exit code/counts/failing nodeids and continue after failures:

1. `python/tests/test_hsx_debugger_candidate_lifecycle_guards.py`
2. `python/tests/test_hsx_debugger_recipe_v13.py`
3. `python/tests/test_hsx_debugger_artifact_v15.py`
4. `python/tests/test_hsx_debugger_stack.py`
5. `python/tests/test_hsx_debugger_handles.py`
6. `python/tests/test_hsx_debugger_inspection.py`
7. `python/tests/test_hsx_debugger_reference_results_v17.py`
8. `python/tests/test_hsx_debugger_reference_record_invariants.py`
9. `python/tests/test_hsx_debugger_real_index_integration.py`
10. `python/tests/test_hsx_debugger_query_races.py`
11. `python/tests/test_hsx_debugger_service_precedence.py`
12. `python/tests/test_hsx_debugger_stale_no_io.py`
13. `python/tests/test_hsx_debugger_dependency_contracts.py`
14. `python/tests/test_hsx_debugger_candidate_guards.py`
15. `python/tests/test_hsx_debugger_current_profile_rows_v18.py`
16. `python/tests/test_hsx_debugger_frame_base_locations_v18.py`
17. `python/tests/test_hsx_debugger_stack_dependency_contracts.py`
18. `python/tests/test_hsx_debugger_inspection_paging_partial.py`
19. `python/tests/test_hsx_debugger_lifecycle_result_invariants.py`
20. `python/tests/test_hsx_debugger_disassembly_contracts.py`
21. `python/tests/test_hsx_debugger_variable_page_isolation.py`
22. `python/tests/test_hsx_debugger_scope_variable_concurrency.py`

Expectation:
- every file exits zero;
- the **only** expected XFAIL is P002 in `test_hsx_debugger_candidate_guards.py::test_location_validator_type_error_names_location_row`;
- no other XFAIL, XPASS, skip, failure or error is expected in Phase B.

## Phase C — signed immutability oracle

Run separately in a fresh Python/pytest process:

`python/tests/test_hsx_debugger_metadata.py::test_cs_imm_103_arbitrary_and_mutable_value_enums_are_not_approved`

Expectation: PASS.

## Phase D — concurrency/stress repetition

Run this complete set **20 independent repetitions**; continue all repetitions after any failure:

- `python/tests/test_hsx_debugger_query_races.py`
- `python/tests/test_hsx_debugger_scope_variable_concurrency.py`
- `python/tests/test_hsx_debugger_handles.py::test_concurrent_same_key_interns_one_serial`
- `python/tests/test_hsx_debugger_handles.py::test_concurrent_distinct_keys_get_unique_never_reused_serials`
- `python/tests/test_hsx_debugger_inspection.py::test_concurrent_repeated_stack_queries_intern_one_frame_handle`
- `python/tests/test_hsx_debugger_variable_page_isolation.py`

Expectation: 20/20 repetitions with zero failing/error nodeids and stable handle assertions.

## Phase E — signed RF-004 regression oracle

Run this exact signed set in one pytest command:

- `python/tests/test_hsx_debugger_addresses.py`
- `python/tests/test_hsx_debugger_identity.py`
- `python/tests/test_hsx_debugger_metadata.py`
- `python/tests/test_hsx_debugger_recipes.py`
- `python/tests/test_hsx_debugger_artifacts.py`
- `python/tests/test_hsx_debugger_sources.py`
- `python/tests/test_hsx_debugger_rf004_legacy_oracles.py`

Expectation: zero failures. Report exact PASS/SKIP counts; previously accepted environment-dependent skips remain allowed only when individually named.

## Phase F — complete debugger/core regression aggregate

Run:

```powershell
& $python -m pytest python/tests/test_hsx_debugger_*.py -q --tb=short
```

This intentionally includes the earlier RF-002/RF-003 controller/gateway/core regression surface together with RF-004 and the new candidate tests. Report exact counts and every non-pass. The only expected candidate XFAIL remains P002. No other failure/error is accepted here.

If PowerShell does not expand the wildcard for pytest as intended, enumerate the matching files with Python/Pathlib and pass that exact list to pytest; report the exact command/list used.

## Phase G — broad Python aggregate

Run:

```powershell
& $python -m pytest python/tests -q --tb=short
```

Only these two previously accepted baseline failures are allowed:

1. `python/tests/test_hsx_dbg_commands.py::test_break_add_symbol_line` — ignored/generated demo symbol artifact absent;
2. `python/tests/test_shell_client.py::test_pretty_dmesg_assigns_session_numbers` — optional-tabulate formatting baseline.

The actual failure set may be a subset if the local environment satisfies either baseline. Any additional failing/error nodeid is a candidate regression.

Expected candidate XFAIL: only P002 LocationRow wording.

## Phase H — final repository integrity and authority

After all execution:

- `git rev-parse HEAD` equals requested exact HEAD;
- `git status --porcelain` is empty;
- `git diff --exit-code` exits zero;
- `git diff --check` exits zero;
- origin candidate branch still resolves to requested exact HEAD;
- no tracked/untracked repository file was created by testing;
- candidate comparison to authoritative `46169516058aadf0e691a5981e29da4954b7444f` changes no Executive/VM/AVR/DAP/CLI/VS Code/frontend product file.

Do not clean the checkout to hide an integrity failure. Report it.

## Mechanical classification rule

`CANDIDATE_EXECUTION_PASS_WITH_KNOWN_BASELINES` iff:

- Phases A–F have no unexpected failure/error/skip/xfail/xpass;
- concurrency is 20/20;
- Phase G failure set is a subset of the two named historical baselines;
- P002 is the sole expected candidate XFAIL;
- Phase H is clean.

Otherwise classify `CANDIDATE_EXECUTION_FAIL` and enumerate the exact reasons. Do not infer fixes.

## Final report

Post exactly one issue #38 comment beginning:

`HSX | TESTER -> MASTER | RF-004 candidate batch 004 result`

Include:
- requested, remote and tested exact SHAs;
- Python executable/environment;
- each Phase A command/result;
- per-file Phase B counts/exit codes;
- Phase C result;
- all 20 Phase D repetition results or concise aggregate plus every failed repetition;
- Phase E/F/G exact counts and nodeids;
- Phase H integrity evidence;
- final mechanical classification.

Stop immediately after posting. Do not modify product/test/SDP/PR state.
