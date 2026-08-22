# RF-004 Candidate Batch005 — full completion execution plan

Status: **CANDIDATE TEST PLAN ONLY / READ-ONLY EXECUTION REQUIRED / NO REVIEW OR SIGN-OFF AUTHORITY**

Candidate branch: `master/rf004-v13-candidate`.
Authoritative RF-004 Draft PR #50 branch is `codex/dbg-rf-004` and MUST NOT be changed.
The `MASTER -> TESTER` issue comment freezes the exact candidate commit to execute.

## Purpose

Batch005 is the first full candidate-completion execution after the post-Batch004 acceptance
audit and `dbg.resolver-inspection/1.9` caller CALL-semantic correction.

It must validate in one read-only run:

- all candidate interface/product behavior 1.3..1.9;
- canonical fixed32 CALL opcode/decode evidence;
- no resume-PC caller continuation when CALL proof is absent;
- current-profile entry/body/epilogue/terminal frame behavior;
- Stack/Inspection dependency, lifecycle, paging, partial-result and race invariants;
- unchanged signed RF-004 foundation/oracle;
- unchanged signed RF-002/RF-003 controller/gateway foundation;
- complete debugger-core aggregate;
- broad Python baseline comparison;
- protected-path and repository-integrity evidence.

A PASS is candidate execution evidence only. It does not replace fresh independent 5.6
interface/product review, formal Slice verification or exact-head Master sign-off.

## Absolute TESTER rules

TESTER is read-only.

Forbidden:

- no editing code/tests/docs/SDP/fixtures/config;
- no formatter/autofix that writes files;
- no generated artifact repair;
- no commit/amend/rebase/merge/cherry-pick/push/ref update;
- no PR #50 mutation;
- no issue mutation except the one final requested TESTER -> MASTER result comment;
- no deleting generated files to manufacture a clean checkout;
- no diagnosis or fix implementation.

Use a new temporary clone outside all user working repositories. Write long logs only under OS
temp, never inside the checkout. Continue through **every phase even after failure** and report
each exit independently.

## Common environment

Use:

```powershell
$python = 'C:/Users/hanse/miniconda3/python.exe'
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:PYTHONPATH = "$PWD/python;$PWD/python/tests"
```

Report exact Python version and resolved executable.

## Phase A — exact authority, clean checkout, syntax and imports

1. Fresh temporary clone of `Hans-Einar/HSX`.
2. Fetch `master/rf004-v13-candidate` and checkout the exact task SHA detached.
3. Prove:
   - requested SHA == `git rev-parse HEAD`;
   - remote `origin/master/rf004-v13-candidate` == requested SHA;
   - `git status --porcelain` empty;
   - `git diff --exit-code` == 0;
   - `git diff --check` == 0.
4. Record authoritative PR #50 state read-only and prove its head remains
   `codex/dbg-rf-004@46169516058aadf0e691a5981e29da4954b7444f`, Draft/open. If the PR head differs,
   report `AUTHORITY_DRIFT`; do not mutate it.
5. AST-parse every `python/hsx_debugger/*.py` file without writing bytecode.
6. Import at least:
   - `hsx_debugger`;
   - `hsx_debugger.artifacts`;
   - `hsx_debugger.recipes`;
   - `hsx_debugger.instruction_semantics`;
   - `hsx_debugger.stack`;
   - `hsx_debugger.handles`;
   - `hsx_debugger.inspection_records`;
   - `hsx_debugger.inspection`.

## Phase B — canonical fixed32 semantic authority

Run separately:

```powershell
& $python -m pytest python/tests/test_opcode_table.py -q --tb=short
& $python -m pytest python/tests/test_hsx_debugger_instruction_semantics_v19.py -q --tb=short
& $python -m pytest python/tests/test_hsx_debugger_call_site_v19.py -q --tb=short
```

Additionally run one fresh-process assertion:

```powershell
& $python -c "import opcodes; from hsx_debugger.instruction_semantics import FIXED32_CALL_OPCODE; assert FIXED32_CALL_OPCODE == opcodes.OPCODES['CALL'] == 0x24; print('CALL_OPCODE_AUTHORITY_PASS')"
```

All commands must exit zero.

The 1.9 call-site suite must prove at least these outcomes:

- proven CALL selects caller using checked call-site PC while preserving resume PC separately;
- half-open caller row containing call-site but excluding resume still resolves;
- missing encoded semantics stops PARTIAL with only proven prefix;
- non-CALL stops CORRUPT with prefix;
- unsupported encoding stops UNSUPPORTED with prefix;
- missing instruction evidence stops PARTIAL with prefix;
- malformed fixed32 CALL evidence stops CORRUPT;
- no failure path continues to caller SP/GPR reads after call-site proof has already failed.

## Phase C — every candidate-specific RF-004 suite

Run each file **separately** with `-q --tb=short` and record count/exit for each:

1. `python/tests/test_hsx_debugger_artifact_v15.py`
2. `python/tests/test_hsx_debugger_call_site_v19.py`
3. `python/tests/test_hsx_debugger_candidate_guards.py`
4. `python/tests/test_hsx_debugger_candidate_lifecycle_guards.py`
5. `python/tests/test_hsx_debugger_current_profile_rows_v18.py`
6. `python/tests/test_hsx_debugger_dependency_contracts.py`
7. `python/tests/test_hsx_debugger_disassembly_contracts.py`
8. `python/tests/test_hsx_debugger_frame_base_locations_v18.py`
9. `python/tests/test_hsx_debugger_handles.py`
10. `python/tests/test_hsx_debugger_inspection.py`
11. `python/tests/test_hsx_debugger_inspection_paging_partial.py`
12. `python/tests/test_hsx_debugger_instruction_semantics_v19.py`
13. `python/tests/test_hsx_debugger_lifecycle_result_invariants.py`
14. `python/tests/test_hsx_debugger_query_races.py`
15. `python/tests/test_hsx_debugger_real_index_integration.py`
16. `python/tests/test_hsx_debugger_recipe_v13.py`
17. `python/tests/test_hsx_debugger_reference_record_invariants.py`
18. `python/tests/test_hsx_debugger_reference_results_v17.py`
19. `python/tests/test_hsx_debugger_scope_variable_concurrency.py`
20. `python/tests/test_hsx_debugger_service_precedence.py`
21. `python/tests/test_hsx_debugger_stack.py`
22. `python/tests/test_hsx_debugger_stack_dependency_contracts.py`
23. `python/tests/test_hsx_debugger_stale_no_io.py`
24. `python/tests/test_hsx_debugger_variable_page_isolation.py`

Expected candidate-only exceptional outcome:

- exactly one strict XFAIL is still permitted:
  `test_hsx_debugger_candidate_guards.py::test_location_validator_type_error_names_location_row`
  (P002 cosmetic promotion cleanup).

No other failure, error, xfail or unexpected skip is allowed in this phase.

## Phase D — signed generic immutability oracle in fresh process

Run:

```powershell
& $python -m pytest python/tests/test_hsx_debugger_metadata.py::test_cs_imm_103_arbitrary_and_mutable_value_enums_are_not_approved -q --tb=short
```

Must PASS. This remains an explicit regression guard against broadening generic result payloads.

## Phase E — 20× concurrency / invalidation stress

For iterations `1..20`, run one pytest command containing:

- `python/tests/test_hsx_debugger_query_races.py`
- `python/tests/test_hsx_debugger_handles.py::test_concurrent_same_key_interns_one_serial`
- `python/tests/test_hsx_debugger_handles.py::test_concurrent_distinct_keys_get_unique_never_reused_serials`
- `python/tests/test_hsx_debugger_inspection.py::test_concurrent_repeated_stack_queries_intern_one_frame_handle`
- complete `python/tests/test_hsx_debugger_scope_variable_concurrency.py`

Use `-q --tb=short`.

Report every iteration number/exit and failing nodeid if any. Expected aggregate: `20/20 PASS`.
Continue all 20 rounds after any failure.

## Phase F — signed RF-004 regression oracle

Run the exact existing signed set in one command:

```powershell
& $python -m pytest `
  python/tests/test_hsx_debugger_addresses.py `
  python/tests/test_hsx_debugger_identity.py `
  python/tests/test_hsx_debugger_metadata.py `
  python/tests/test_hsx_debugger_recipes.py `
  python/tests/test_hsx_debugger_artifacts.py `
  python/tests/test_hsx_debugger_sources.py `
  python/tests/test_hsx_debugger_rf004_legacy_oracles.py `
  -q --tb=short
```

Expected historical reference from Batch004: `159 passed, 3 skipped`, zero failures. Report
actual counts; any failure/error is candidate regression.

## Phase G — signed RF-002/RF-003 first-wave core signal

Run in one command:

```powershell
& $python -m pytest `
  python/tests/test_hsx_debugger_contracts.py `
  python/tests/test_hsx_debugger_controller.py `
  python/tests/test_hsx_debugger_gateway.py `
  python/tests/test_hsx_debugger_controller_gateway.py `
  -q --tb=short
```

All must pass. Report exact counts. This is not a replacement for the historical RF-002/RF-003
formal matrices; it is a direct candidate-branch regression signal for the signed controller/
gateway foundation that RF-004 consumes.

## Phase H — complete debugger-core aggregate

Do **not** pass a literal wildcard to pytest. Expand the file list in PowerShell:

```powershell
$core = Get-ChildItem -Path python/tests -Filter 'test_hsx_debugger_*.py' -File |
  Sort-Object FullName |
  ForEach-Object { $_.FullName }
& $python -m pytest @core -q --tb=short
```

Expected:

- zero failures/errors;
- P002 is the only xfail;
- only already accepted environment-dependent skips are permitted and must be listed.

Report expanded file count and pytest counts.

## Phase I — full Python aggregate / baseline comparison

Run:

```powershell
$log = Join-Path $env:TEMP ("hsx-b005-broad-" + [guid]::NewGuid().ToString('N') + '.txt')
& $python -m pytest python/tests -q --tb=short *> $log
$code = $LASTEXITCODE
Get-Content $log
```

Only these two already accepted historical failures are allowed:

1. `python/tests/test_hsx_dbg_commands.py::test_break_add_symbol_line`
   — ignored/generated demo symbol artifact absent;
2. `python/tests/test_shell_client.py::test_pretty_dmesg_assigns_session_numbers`
   — optional-tabulate formatting baseline.

P002 may remain the one candidate XFAIL. Existing accepted skips are permitted and must be
reported. Any other failure/error is a candidate regression.

Do not copy the broad log into the checkout. Report the OS-temp path.

## Phase J — scope / protected-path audit

Compare authoritative head to tested candidate:

```powershell
$changed = git diff --name-only 46169516058aadf0e691a5981e29da4954b7444f HEAD
$changed
```

Every changed path must be under one of:

- `SDP/Debugger/`
- `python/hsx_debugger/`
- `python/tests/`

Explicitly report whether any path touches:

- Executive/session/runtime adapter product;
- VM/platform implementation;
- AVR;
- DAP/CLI frontend;
- VS Code extension;
- RF-005..009 product files.

Expected: no protected/out-of-scope product path.

Also report `git diff --check 46169516058aadf0e691a5981e29da4954b7444f..HEAD`.

## Phase K — final repository integrity

After every previous phase, report:

```powershell
git rev-parse HEAD
git status --porcelain
git diff --exit-code
git diff --check
```

The exact tested HEAD must remain unchanged; status must be clean; diff exit zero; tracked
mutation from testing must be `NO`. Report any generated/untracked path rather than deleting it.

## Mechanical result classification

Use `CANDIDATE_COMPLETION_EXECUTION_PASS_WITH_KNOWN_BASELINES` only when all are true:

- exact authority/head/PR checks pass;
- Phases A-H have zero failure/error;
- Phase C has exactly the one permitted P002 strict XFAIL and no other candidate exception;
- Phase E is 20/20 PASS;
- Phase I failures are a subset of only the two explicitly accepted historical baseline nodeids;
- Phase J has no protected/out-of-scope path;
- Phase K is clean/no mutation.

Otherwise report `CANDIDATE_COMPLETION_EXECUTION_FAIL` or `BLOCKED` with exact evidence.
Do not diagnose or fix.

## Report back

Post exactly one new issue #38 comment beginning:

`HSX | TESTER -> MASTER | RF-004 candidate batch 005 completion result`

Include:

- exact requested/remote/tested/authoritative PR heads;
- Python/env;
- every phase command/exit/count;
- every failure/error/xfail/skip;
- 20-iteration stress summary;
- signed RF-004 and first-wave counts;
- debugger-core aggregate;
- broad baseline comparison;
- scope audit;
- final repository integrity;
- mechanical classification.

Stop after that one comment.