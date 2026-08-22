# RF-004 candidate interface delta index — `dbg.resolver-inspection/1.3..1.8`

Status: **CANDIDATE ONLY / NOT SIGNED / INDEPENDENT REVIEW PENDING**

Authoritative signed/public baseline remains `dbg.resolver-inspection/1.2` on `codex/dbg-rf-004` / Draft PR #50. This document indexes the bounded candidate-only refreezes developed on `master/rf004-v13-candidate` while fresh Codex 5.6 independent review is unavailable.

No delta below authorizes RF-005..009 or Executive/VM/AVR/DAP/VS Code/frontend changes.

## Delta chain

| Version | Problem | Normative delta | Portable HSX change? | Durable authority/evidence |
|---|---|---|---|---|
| `1.3` | current-profile caller R7 recovery `deref_u(CFA-8,4,little)` produces exact-width `RecipeScalar`, while 1.2 required `RecipeRegister` | `UnwindRow.register_rules` key is authoritative GPR identity; EXPRESSION may produce exact-width `REGISTER` or unsigned scalar; REGISTER still requires exact ID match | **No** | Steering #38 `5374100772`; `010--RF004_Register_Rule_Result_Conformance_v1_3.md` |
| `1.4` | generic immutable `ResolutionResult[T]` cannot legitimately contain mutable lifecycle service/session refs | dedicated lifecycle/control result envelopes for service/session refs; generic result immutability remains strict | **No** | `015--RF004_Lifecycle_Result_Conformance_v1_4.md` |
| `1.5` | `SnapshotExpression.SymbolExpression` requires exact `symbol_id` lookup but public artifact index exposed only name candidates | additive `DebugArtifactIndex.symbol_by_id(symbol_id)` exact-cardinality query | **No** | `016--RF004_Exact_Symbol_Lookup_Conformance_v1_5.md` |
| `1.6` | generic `InspectionResult` cannot preserve a trustworthy frame prefix while retaining exact terminating `CORRUPT/UNSUPPORTED/STALE` status | dedicated `StackWalkResult` / `StackPageResult` preserve proven prefix plus exact termination category | **No** | `020--RF004_Stack_Prefix_Result_Conformance_v1_6.md` |
| `1.7` | epoch-reference DTOs contain full `InspectionContext`/controller evidence and must not widen the generic-result Enum payload catalog | dedicated `HandleInternResult`, `ScopeQueryResult`, `VariableQueryResult`; direct `EvidenceGrade` remains forbidden as generic payload | **No** | Steering #38 `5380356912`; `022--RF004_Epoch_Reference_Result_Conformance_v1_7.md` |
| `1.8` | top-frame R7 was incorrectly treated as current frame base across ENTRY/EPILOGUE phases | snapshot R7 is current `frame_base` only for exact current ABI + exact selected `ORDINARY` row + valid R7; ENTRY/EPILOGUE/TERMINAL do not infer it | **No** | Steering #38 `5380568339`; `025--RF004_Row_Aware_Frame_Base_Conformance_v1_8.md` |

## Stable principles across every delta

The following remain unchanged from the accepted 1.2 architecture:

- exact `InspectionContext {target,image,epoch}` coherence and immutable snapshot identity;
- typed address spaces and checked arithmetic; no implicit masks, modulo, wrap or host-endian conversion;
- exact-case/content-bound source identity; no lowercase/basename fallback;
- artifact parsing/indexing, source filesystem resolution, recipe evaluation, stack reconstruction, epoch inspection and frontend mapping remain separate responsibilities;
- `SnapshotReadPort` stays snapshot/context-oriented and has no frame-aware/live-current side channel;
- StackService performs one top-frame snapshot register read and reconstructs callers only from explicit row recipes;
- no fixed-R7 caller fallback; `SAME` is explicit evidence, missing rules remain unavailable;
- `resume_pc` and `call_site_pc` remain distinct; no call-site is fabricated without portable CALL evidence;
- lifecycle/control, stack-prefix and epoch-reference dedicated envelopes are narrow exceptions to generic immutable result payloads, not a weakening of the generic algebra;
- no public DAP/CLI/VS Code or Executive/VM/AVR integration is implemented in RF-004.

## Candidate execution evidence to date

Batch003 at exact candidate head `93ed5742434ef3512ee69beb43f39a57699b06ac` was independently executed read-only by TESTER and Master-classified `CANDIDATE_EXECUTION_PASS_WITH_KNOWN_BASELINES` in issue #38 comment `5380526850`:

- all candidate must-pass suites passed;
- sole expected candidate strict XFAIL was cosmetic P002 (`LocationRow` TypeError wording);
- signed CS-IMM-103 passed;
- concurrency/stress passed 20/20;
- signed RF-004 regression oracle passed `159` with `3` accepted skips;
- full Python suite had only the two previously documented unrelated baselines (missing ignored demo `.sym`; optional-tabulate shell formatting);
- tested worktree remained clean and exact HEAD unchanged.

Post-batch003 acceptance audit added further candidate-only changes/tests for 1.8 current-profile PC phases, constructor invariants, page-before-evaluation, PARTIAL memory/disassembly, dependency contract fencing and lifecycle envelope algebra. These are not yet execution-signed and belong to the next aggregate TESTER batch.

## Required future 5.6 review/promotion sequence

When fresh independent Codex 5.6 capacity returns:

1. Review the complete `1.3..1.8` candidate interface chain against accepted 1.2 + HSX-D-002/HSX-ST-007. The reviewer must be independent of the Master implementation work.
2. Any Blocking/High/Medium finding requires rework on the candidate branch and a new exact-head review.
3. After interface PASS, independently review the exact Slice005 product head (StackService/tests) and Slice006 product head (handles/inspection/tests), not merely this documentation.
4. Run formal verification for each Slice and obtain Master exact-head sign-off.
5. Only then promote/replay the reviewed candidate product onto authoritative `codex/dbg-rf-004`, update PR #50/SDP traceability, and perform RF-004 parent integration/review/verification/sign-off.
6. RF-005 remains blocked until the final RF-004 parent decision package is accepted by Steering.
