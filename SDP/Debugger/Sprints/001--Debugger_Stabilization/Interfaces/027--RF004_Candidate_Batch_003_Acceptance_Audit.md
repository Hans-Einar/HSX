# RF-004 Candidate Batch 003 — Master acceptance audit

Status: **MASTER CANDIDATE ACCEPTANCE AUDIT / NOT REVIEW OR SIGN-OFF**

TESTER result: issue #38 comment `5380492183` at exact head `93ed5742434ef3512ee69beb43f39a57699b06ac`.
Master classification: issue #38 comment `5380526850` — `CANDIDATE_EXECUTION_PASS_WITH_KNOWN_BASELINES`.

## Batch003 execution classification

The TESTER's mechanical final FAIL label was rejected because the actual evidence satisfied the frozen acceptance rule:

- exact requested/remote/tested HEAD matched;
- syntax/import passed;
- all candidate must-pass suites passed;
- signed CS-IMM-103 passed;
- concurrency/stress passed 20/20;
- signed RF-004 oracle passed 159 tests with 3 accepted skips;
- full Python had only the two pre-existing accepted baselines: missing ignored demo `.sym` and optional-tabulate shell formatting;
- sole candidate XFAIL was known cosmetic P002 LocationRow TypeError wording;
- post-test tracked worktree remained clean.

## Post-batch003 acceptance audit findings

The green execution was necessary but not sufficient for Slice005/006 readiness. Master therefore audited the candidate against the frozen Slice contracts and portable HSX row semantics before asking for another test run.

### A. Row-aware top-frame frame-base evidence

Finding: top-frame snapshot R7 was interpreted as current frame base across the entire current ABI. Portable HSX row semantics show that R7 is caller state before `PUSH R7`/before `MOV R7,R15` and again after `POP R7`.

Disposition: Steering refreeze `dbg.resolver-inspection/1.8`, issue #38 comment `5380568339`. StackService now derives top-frame frame_base from snapshot R7 only after exact row selection and only on current-ABI `ORDINARY` rows. ENTRY/EPILOGUE/TERMINAL do not infer it. Added explicit current-profile phase matrix and LocationEvaluator frame-base tests.

### B. Stack dependency contract fencing

Finding: malformed/raising function and row-index dependencies could either leak exceptions or accidentally relax function-bound row selection. Optional instruction/call-site metadata also needed explicit typed classification.

Disposition: StackService now:
- treats function-index contract failure as `CORRUPT/function_index_contract` before row selection;
- requires `unwind_rows()` to return `ResolutionResult`;
- keeps optional source annotation failure diagnostic-only;
- classifies malformed call-site metadata as `call_site_index_contract` while preserving resume PC;
- continues to refuse fabricated call-site semantics without portable CALL evidence.

### C. Variable paging isolation

Finding: `variables()` evaluated every symbol before applying PageRequest. An off-page bad/unavailable variable could therefore fail a page that never requested it.

Disposition: candidate now builds the deterministic identity list, applies exact `[offset:min(offset+limit,total)]`, and evaluates/allocates handles only for the selected page. `total_variables` remains the full candidate count; repeated/out-of-order pages retain exact handles.

### D. PARTIAL disassembly

Finding: a legal `PARTIAL + tuple[InstructionBytes] + diagnostic` SnapshotReadPort result was converted to an invalid no-value PARTIAL envelope. Metadata/byte-size mismatch could also escape as a Python exception.

Disposition: candidate preserves the proven disassembly prefix in a `DisassemblyBlock` with the original PARTIAL status/diagnostics. Optional metadata failure remains diagnostic-only; exact metadata-vs-byte inconsistency is typed `CORRUPT/disassembly_metadata_mismatch`.

### E. Dependency result/type fencing in InspectionService

Disposition:
- exact LocationRow is required after location lookup;
- LocationEvaluator exceptions/non-InspectionResult/non-EvaluatedValue success are `CORRUPT/location_evaluator_contract`;
- exact SymbolRecord is required after symbol_by_id;
- index exceptions/malformed ResolutionResults remain `CORRUPT/artifact_index_contract`;
- no raw dependency exception is allowed to escape public inspection queries.

### F. Dedicated result/record invariants

The candidate now enforces constructor-level invariants for:
- lifecycle service/session/close envelopes;
- exact handle-resolution key shapes;
- FramePage offset/contiguous frame indices;
- ScopeSet unique/fixed Registers→Locals→Globals order;
- VariablePage unique handles and deterministic register/symbol ordering.

This is enforcement of already-frozen observable rules, not new frontend policy.

### G. Concurrency and no-I/O completion coverage

New tests cover:
- concurrent scope handle stability;
- concurrent variable handle stability;
- invalidated-session no-I/O/no-allocation across query surfaces;
- snapshot/index invalidation races;
- off-page variable non-evaluation.

## Remaining known candidate item

P002 is still intentionally retained as the sole strict XFAIL: `RecipeComponentValidator.validate_location_row(object(), ...)` says `row must be UnwindRow` instead of `LocationRow`. This is cosmetic wording only and is not permission to rewrite the large signed recipe foundation before an independent reviewer is available.

## Gate

The post-batch003 correction wave is candidate-only. It requires a new aggregate read-only execution (Batch004), then fresh independent Codex 5.6 interface/product review before any Slice005/006 sign-off or authoritative promotion.
