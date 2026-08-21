# RF-004 candidate batch test plan

Status: **MASTER PREPARED / READ-ONLY TESTER PENDING**

Candidate branch: `master/rf004-v13-candidate`.
Authoritative RF-004 branch remains `codex/dbg-rf-004`; candidate results are not signed or
promotion authority.

## Candidate content under one batch

1. `dbg.resolver-inspection/1.3` register-rule scalar binding.
2. Snapshot-bound `StackService` candidate.
3. Epoch `DomainHandle` / `EpochHandleStore` candidate.
4. `dbg.resolver-inspection/1.4` dedicated lifecycle/control result envelopes.
5. `EpochInspectionSession` / `InspectionService` candidate.
6. `dbg.resolver-inspection/1.5` consumer seam for exact `symbol_by_id` lookup. The real
   `DebugArtifactIndex.symbol_by_id` additive implementation is intentionally still a
   promotion guard so the previously signed Slice003 file is not broadly rewritten.
7. Explicit schema-v1 `address(R7)` lowering evidence through full-width `bit_slice` +
   `to_address` with no new opcode.
8. Additive public package exports.

## Test strategy

The tester must not stop on the first failing command. Record every command and aggregate the
failure set so Master can correct the batch in one follow-up pass.

### Phase A — syntax/import integrity

Parse every candidate-owned Python module with `ast.parse`, then import `hsx_debugger`,
`hsx_debugger.stack`, `hsx_debugger.handles`, and `hsx_debugger.inspection` with bytecode writes
disabled.

### Phase B — new candidate contract tests

Run:

- `test_hsx_debugger_recipe_v13.py`
- `test_hsx_debugger_stack.py`
- `test_hsx_debugger_handles.py`
- `test_hsx_debugger_inspection.py`
- `test_hsx_debugger_candidate_guards.py`

The guard file is intentionally strict and may expose unfinished candidate/promotion seams;
those are failures to report, not permission for TESTER to edit anything.

### Phase C — unchanged RF-004 regression surface

Run the existing RF-004 foundation/oracle tests for addresses, identity, metadata, recipes,
artifacts, sources, snapshot behavior, and legacy oracles.

### Phase D — broad Python regression

Run `python/tests` as one final aggregate. Report candidate failures separately from any
previously-classified baseline failures/skips when possible.

## Integrity

All phases are read-only. Report exact candidate HEAD before and after, `git status --porcelain`,
`git diff --exit-code`, and whether any tracked file changed. Do not auto-fix, format, commit,
push, or alter GitHub state except the required `TESTER -> MASTER` result comment.
