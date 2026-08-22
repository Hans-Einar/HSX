# RF-004 candidate promotion and independent-review handoff

Status: **COLD-START HANDOFF / CANDIDATE ONLY / DO NOT PROMOTE WHOLE BRANCH**

Repository: `Hans-Einar/HSX`.
Candidate staging branch: `master/rf004-v13-candidate`.
Authoritative Draft PR #50 head remains `codex/dbg-rf-004@46169516058aadf0e691a5981e29da4954b7444f` until the review sequence below authorizes new heads.

This document exists because the temporary no-Codex-5.6 period intentionally batched Slice005
and Slice006 work on one staging branch. Commit chronology on that branch is development
evidence, **not the product dependency DAG**.

## Absolute promotion rule

Do not merge, rebase, squash, or cherry-pick the candidate branch wholesale into
`codex/dbg-rf-004`.

Reconstruct reviewed product state in dependency order:

1. complete interface review;
2. reconstruct and sign Slice005 only;
3. reconstruct and sign Slice006 only on the signed Slice005 head;
4. then perform RF-004 parent integration/review/verification/signoff.

This restores the original SDP sequence even though candidate development was interleaved.

## Cold-start reading order for fresh 5.6 reviewer

1. root `AGENTS.md`, SDP README and shared process;
2. Debugger track README / CurrentIndex / RF-004 iteration and Slice005/006 records;
3. authoritative PR #50 head and issue #38 durable Steering comments;
4. accepted `dbg.resolver-inspection/1.2` base;
5. `026--RF004_Candidate_Interface_Delta_Index.md` for 1.3..1.9;
6. each normative delta file 010, 015, 016, 020, 022, 025, 029;
7. `030--RF004_Candidate_Batch_004_Findings.md`;
8. `031--RF004_Slice005_006_Candidate_Completion_Matrix.md`;
9. latest Batch005 TESTER result and exact candidate head frozen by its issue comment;
10. exact candidate diff from authoritative `461695...` only after understanding the above.

## Interface review gate

Perform one fresh independent exact-head review of the complete candidate projection
`dbg.resolver-inspection/1.3..1.9` against:

- accepted 1.2 interface;
- accepted HSX-D-002 / HSX-ST-007 unwind/ABI/call-site semantics;
- signed RF-002 stop-epoch/controller evidence model;
- signed RF-004 Slice002/007 foundation;
- canonical fixed32 toolchain evidence for 1.9 (`docs/MVASM_SPEC.md`, `python/opcodes.py`,
  `python/disassemble.py`, `python/tests/test_opcode_table.py`).

The reviewer must not treat Batch PASS as proof that a contract choice is correct.

### High-attention interface questions

1. **1.3 row-key scalar binding:** does accepting exact-width unsigned scalar preserve all type,
   sign, width and register-identity invariants without creating an implicit general cast?
2. **1.6 trustworthy prefix:** are red termination status and already-proven frames represented
   without weakening generic `InspectionResult`?
3. **1.7 reference-bearing envelopes:** is generic immutability still strict, especially
   CS-IMM-103 and direct `EvidenceGrade` rejection?
4. **1.8 frame-base phase semantics:** is top snapshot R7 used as current frame base only where
   exact current-profile row evidence establishes it?
5. **1.9 caller PC:** does the minimal semantic-proof boundary prove CALL from authoritative
   fixed32 metadata without becoming a second general disassembler, and does every failure stop
   before resume-PC fallback or extra caller-state reads?
6. **No portable drift:** confirm none of 1.3..1.9 silently changes HSX-D-002, VM/runtime wire
   format or artifact digest schema.

Blocking/High/Medium finding => candidate rework and new exact-head interface review. Do not
proceed to Slice product review on a failed interface review.

## Slice005 reconstruction manifest

Reconstruct a clean Slice005 branch/head from the authoritative RF-004 head. Do not carry
Slice006 modules into this head.

### Include

- `python/hsx_debugger/stack.py` candidate behavior;
- `python/hsx_debugger/instruction_semantics.py` v1.9 bounded semantic proof;
- v1.3 corrective delta in `python/hsx_debugger/recipes.py` only;
- additive package exports required by Slice005, if any;
- Slice005 tests:
  - `test_hsx_debugger_recipe_v13.py`;
  - `test_hsx_debugger_stack.py`;
  - `test_hsx_debugger_current_profile_rows_v18.py`;
  - `test_hsx_debugger_frame_base_locations_v18.py`;
  - `test_hsx_debugger_stack_dependency_contracts.py`;
  - `test_hsx_debugger_instruction_semantics_v19.py`;
  - `test_hsx_debugger_call_site_v19.py`;
  - directly relevant candidate guards.

### Exclude from Slice005 head

- `handles.py`, `inspection_records.py`, `inspection.py`;
- `artifacts.py::symbol_by_id` v1.5 seam;
- Slice006-only tests;
- any frontend/runtime/Executive/VM/AVR file.

### Promotion cleanup

P002 is one cosmetic one-line candidate XFAIL: `RecipeComponentValidator.validate_location_row`
currently says `row must be UnwindRow`. During clean Slice005 reconstruction change only that
message to `row must be LocationRow`, remove the strict XFAIL only after the exact test passes,
and keep the diff separately visible to reviewer.

The candidate `stack.py` full-file Contents-API rewrite also lost the final newline. Restore it
during reconstruction as hygiene; this is not semantic product evidence.

### Slice005 review/verification

Fresh independent exact-head product reviewer must inspect code, not only tests. Explicitly
review:

- one top snapshot-register read;
- all five current-profile PC phases;
- aggregate budgets and bound exhaustion;
- typed dependency failures;
- caller R7 exact scalar/key binding;
- no ABI-preservation inference;
- resume/call-site separation;
- no continuation unless 1.9 CALL proof passes;
- no call-site proof failure followed by caller-SP/GPR reads;
- trusted-prefix behavior for partial/corrupt/unsupported/stale;
- module boundary: semantic proof is not a disassembler/runtime adapter.

Then run formal Slice005 verification and Master exact-head signoff. Only that signed head may
become Slice006 base.

## Slice006 reconstruction manifest

Start only from signed Slice005 head.

### Include

- `python/hsx_debugger/handles.py`;
- `python/hsx_debugger/inspection_records.py`;
- `python/hsx_debugger/inspection.py`;
- required additive package exports;
- additive `DebugArtifactIndex.symbol_by_id()` seam from candidate `artifacts.py`, reviewed as
  an explicit exception to earlier Slice003 ownership;
- Slice006 tests listed in `031--RF004_Slice005_006_Candidate_Completion_Matrix.md`.

### Prior-slice additive seam rule

The real candidate diff for `artifacts.py` must remain the surgical `symbol_by_id` query only.
If reconstruction shows any parser/order/digest/index mutation beyond that method, stop and
review the drift rather than treating it as part of Slice006.

### Slice006 high-attention review

- lifecycle result envelopes and exact status/value algebra;
- factory first-match precedence;
- one active epoch / stale history / terminal close;
- no best-effort-live coherent context (consume signed EpochBinding gate);
- handle interning/foreign/stale/no-reuse semantics;
- no snapshot I/O while handle-map locks are held;
- invalidation/late-read linearization;
- page-before-evaluation and stable handles across pages/out-of-order queries;
- exact selected-frame variable evidence, including v1.8/v1.9 caller frames;
- partial memory/disassembly preservation;
- dependency exception/type fencing;
- anti-monolith boundary: `inspection_records` holds immutable public records, while artifacts,
  recipes, instruction semantics, stack and handles remain separate. `inspection.py` is large,
  but line count alone is not acceptance; reviewer must decide whether it actually owns more
  than the intended epoch service/session composition and frontend-neutral query orchestration.

Fresh product review -> formal verification -> Master exact-head signoff.

## Parent RF-004 closeout after both Slices are signed

Only after signed Slice005 and Slice006:

1. construct exact RF-004 integration head on `codex/dbg-rf-004`;
2. update Draft PR #50 body/state truthfully;
3. fresh independent parent review of the complete RF-004 diff;
4. formal parent verification including signed RF-004 oracle, RF-002/RF-003 regressions,
   protected paths, traceability and broad Python baseline comparison;
5. Master exact-head signoff;
6. publish remote history;
7. fresh checkout of final remote head and repeat required verification;
8. update CurrentIndex/Issues/Relations/Ledger/Handoff;
9. post FINAL RF-004 parent decision package to issue #38;
10. stop for Steering.

RF-005..009 remain blocked until Steering accepts that final package.