# RF-004 Candidate Batch 003 — Read-only aggregate execution plan

Status: candidate test plan only; no review/sign-off authority.
Candidate branch: `master/rf004-v13-candidate`.
The issue #38 `MASTER -> TESTER` task freezes the exact commit to execute.

## Goals

Batch003 validates the complete post-batch002 correction wave in one execution:

- `dbg.resolver-inspection/1.7` dedicated epoch-reference envelopes while CS-IMM-103 remains intact;
- exact Handle/Scope/Variable constructor invariants;
- real `DebugArtifactIndex` -> Stack -> Inspection integration;
- correct nonterminal `max_frames` exhaustion as `UNSUPPORTED/limit_exceeded` with trustworthy prefix;
- InspectionService create first-match precedence;
- invalidated-session no-I/O/no-allocation behavior;
- register/scope/variable/disassembly invalidation races;
- dependency exception classification;
- unchanged signed RF-004 regression oracle;
- broad Python baseline comparison.

## Tester constraints

Tester is read-only:
- no file edit, formatting, autofix or generated artifact repair;
- no commit/amend/rebase/merge/push;
- no PR/issue/SDP mutation except the one requested result comment;
- no cleanup of repository files to manufacture a clean result.

Use a new temporary clone outside the user's working repositories. Any log capture goes under OS temp, never inside the checkout.

Run every phase even when an earlier command fails. Capture each exit independently.

## Phase A — exact authority, syntax and import

1. fresh temporary clone of `Hans-Einar/HSX`;
2. checkout the exact task HEAD detached;
3. prove remote candidate branch head equals the requested HEAD;
4. `git status --porcelain` and `git diff --exit-code` must be clean;
5. AST-parse every `python/hsx_debugger/*.py` file without writing bytecode;
6. import `hsx_debugger`, `hsx_debugger.stack`, `handles`, `inspection_records`, `inspection`, `artifacts`, `recipes`.

## Phase B — candidate must-pass suites

Run each file separately:

- `python/tests/test_hsx_debugger_candidate_lifecycle_guards.py`
- `python/tests/test_hsx_debugger_recipe_v13.py`
- `python/tests/test_hsx_debugger_artifact_v15.py`
- `python/tests/test_hsx_debugger_stack.py`
- `python/tests/test_hsx_debugger_handles.py`
- `python/tests/test_hsx_debugger_inspection.py`
- `python/tests/test_hsx_debugger_reference_results_v17.py`
- `python/tests/test_hsx_debugger_reference_record_invariants.py`
- `python/tests/test_hsx_debugger_real_index_integration.py`
- `python/tests/test_hsx_debugger_query_races.py`
- `python/tests/test_hsx_debugger_service_precedence.py`
- `python/tests/test_hsx_debugger_stale_no_io.py`
- `python/tests/test_hsx_debugger_dependency_contracts.py`
- `python/tests/test_hsx_debugger_candidate_guards.py`

All candidate files must exit zero. `test_hsx_debugger_candidate_guards.py` is expected to report exactly one strict XFAIL: P002 LocationRow TypeError wording. No other xfail/skip/failure is expected in the candidate-specific set.

## Phase C — fresh-process immutability oracle

Run signed CS-IMM-103 explicitly in its own process before the combined signed oracle:

`python/tests/test_hsx_debugger_metadata.py::test_cs_imm_103_arbitrary_and_mutable_value_enums_are_not_approved`

It must PASS. This proves package import no longer broadens the generic Enum catalog.

## Phase D — concurrency repetition

Run 20 independent repetitions of:

- `python/tests/test_hsx_debugger_query_races.py`
- `python/tests/test_hsx_debugger_handles.py::test_concurrent_same_key_interns_one_serial`
- `python/tests/test_hsx_debugger_handles.py::test_concurrent_distinct_keys_get_unique_never_reused_serials`
- `python/tests/test_hsx_debugger_inspection.py::test_concurrent_repeated_stack_queries_intern_one_frame_handle`

Continue all repetitions after failures and report failing repetition/nodeid. Aggregate expectation: zero failures.

## Phase E — signed RF-004 regression oracle

Run this exact existing signed set in one pytest command:

- `python/tests/test_hsx_debugger_addresses.py`
- `python/tests/test_hsx_debugger_identity.py`
- `python/tests/test_hsx_debugger_metadata.py`
- `python/tests/test_hsx_debugger_recipes.py`
- `python/tests/test_hsx_debugger_artifacts.py`
- `python/tests/test_hsx_debugger_sources.py`
- `python/tests/test_hsx_debugger_rf004_legacy_oracles.py`

Expected: zero failures. Existing skips are acceptable and must be reported.

## Phase F — broad Python aggregate

Run `python -m pytest python/tests -q --tb=short`.

Only these previously accepted baseline failures are allowed:

1. `python/tests/test_hsx_dbg_commands.py::test_break_add_symbol_line` — ignored/generated demo symbol artifact absent;
2. `python/tests/test_shell_client.py::test_pretty_dmesg_assigns_session_numbers` — optional-tabulate formatting baseline.

The actual failure set may be a subset of those two if the local environment happens to satisfy one baseline. Any other failing/error nodeid is a candidate regression.

Expected candidate XFAIL: only the P002 LocationRow wording guard.

## Phase G — repository integrity

After every execution phase is complete:
- exact HEAD must still equal requested HEAD;
- `git status --porcelain` must remain clean;
- `git diff --exit-code` must pass;
- tracked mutation caused by testing must be NO.

If Python/pytest generates files despite `PYTHONDONTWRITEBYTECODE=1`, report them. Do not mutate the checkout to hide them.

## Report

One issue #38 comment only:

`HSX | TESTER -> MASTER | RF-004 candidate batch 003 result`

Report exact heads, Python/env, each command/exit/count, every failure/error/xfail, concurrency repetition summary, broad-baseline comparison, and final repository integrity.

Do not propose or implement fixes.
