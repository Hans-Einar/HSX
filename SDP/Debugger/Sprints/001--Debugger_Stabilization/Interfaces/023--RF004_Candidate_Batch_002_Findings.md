# RF-004 Candidate Batch 002 — Findings and Master disposition

Status: candidate evidence only; no review/sign-off/promotion authority.
Tester report: issue #38 comment `5380007638`.
Tested exact head: `f568fd6e5c77a3b9469674f323a3f6ab347656e2`.

## Aggregate result

Batch002 proved the new candidate surface was already broadly coherent:

- syntax/import bootstrap PASS;
- candidate lifecycle/import guards: 3 PASS;
- recipe 1.3: 6 PASS;
- artifact 1.5: 2 PASS;
- Stack 1.6: 15 PASS;
- Handles: 8 PASS;
- Inspection: 16 PASS;
- candidate guards: 4 PASS + exactly one expected strict XFAIL (P002 LocationRow error text).

The signed RF-004 regression oracle exposed one real candidate regression. Broad Python exposed that same regression plus two pre-existing accepted baseline failures.

## F-002-01 — broad generic Enum admission — REAL CANDIDATE DEFECT

The candidate package bootstrap globally called `_register_contract_enums(EvidenceGrade)`. That made controller `EvidenceGrade.PORTABLE` legal as a direct arbitrary generic `InspectionResult[T]` / `ResolutionResult[T]` payload, violating signed CS-IMM-103.

Disposition: accepted. Steering refroze `dbg.resolver-inspection/1.7` in issue #38 comment `5380356912`.

Resolution direction:
- generic result Enum catalog remains unchanged;
- package-level `EvidenceGrade` approval removed;
- epoch-reference-bearing Handle/Scope/Variable values use dedicated exact-context result envelopes.

## F-002-02 — generated demo symbol artifact absent — PRE-EXISTING BASELINE

Broad failure:
`test_hsx_dbg_commands.py::test_break_add_symbol_line`.

This is the same accepted RF-001 baseline: ignored/generated demo `.sym` artifact absent. It is outside RF-004 candidate scope and must not be repaired opportunistically here.

## F-002-03 — optional tabulate shell formatting — PRE-EXISTING BASELINE

Broad failure:
`test_shell_client.py::test_pretty_dmesg_assigns_session_numbers`.

Known unrelated baseline; outside RF-004 scope.

## Additional Master static findings after batch002

### M-002-A — nonterminal request max_frames was misclassified COMPLETE

Frozen interface 1.2 says every bound exhaustion is `UNSUPPORTED/limit_exceeded`, never a truncated/complete result. Candidate StackService returned COMPLETE when `request_limits.max_frames` was reached on a nonterminal row.

Corrected on candidate:
- preserve already proven frames;
- return `UNSUPPORTED` + `limit_exceeded`;
- perform no caller recovery beyond the request bound.

Real-index integration now consumes the proven prefix under that exact terminating status.

### M-002-B — InspectionService.create first-match precedence drift

Frozen order is:
1. DebugBindingValidator;
2. accepted capability profile;
3. exact profile limits.

Candidate checked profile limits first. Corrected so multiple simultaneous failures classify by the frozen first-match table.

### M-002-C — dependency exceptions could escape query surface

Location-row lookup and exact symbol lookup could propagate Python exceptions; disassembly metadata annotation could also raise after exact snapshot bytes had already been read.

Corrected:
- location/symbol dependency contract failures -> typed CORRUPT/artifact_index_contract;
- optional disassembly annotation failure preserves exact bytes, sets metadata None and emits instruction_index_contract diagnostic.

### M-002-D — invalidation fencing needed broader concurrency evidence

Added deterministic race tests for:
- register snapshot read;
- scope metadata lookup;
- variable location lookup;
- disassembly metadata lookup after snapshot bytes return.

Invalidation must win and no stale value may publish.

### M-002-E — constructor invariants were under-specified in candidate implementation

Added/strengthened exact invariants for:
- HandleResolution object-key shape;
- FramePage offset/contiguous frame index;
- ScopeSet unique fixed scope order;
- VariablePage unique variable handles;
- dedicated 1.7 context/value algebra.

### M-002-F — real-index integration coverage was missing

Added an end-to-end candidate fixture using real `DebugArtifactIndex.build()` through StackService and InspectionService. Only target snapshot access is a deterministic test port. It covers exact symbol-id lookup, stack prefix, domain handle allocation, scopes, variable queries and snapshot expressions in one object graph.

## Known candidate-only remaining item

P002 remains intentionally strict-xfailed:
`RecipeComponentValidator.validate_location_row()` says `row must be UnwindRow` instead of `row must be LocationRow` for its TypeError text.

This is cosmetic and does not alter accepted recipe semantics. It remains visible as one strict XFAIL until surgically cleaned up before promotion.

## Gate

Candidate remains non-authoritative. Passing execution makes it review-ready only; it does not replace fresh independent interface/product review, formal verification or Master exact-head sign-off.
