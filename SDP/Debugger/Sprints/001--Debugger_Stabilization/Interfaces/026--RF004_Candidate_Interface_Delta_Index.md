# RF-004 candidate interface delta index — `dbg.resolver-inspection/1.3..1.9`

Status: **CANDIDATE ONLY / NOT SIGNED / INDEPENDENT REVIEW PENDING**

Authoritative signed/public baseline remains `dbg.resolver-inspection/1.2` on `codex/dbg-rf-004` / Draft PR #50. This document indexes the bounded candidate-only refreezes developed on `master/rf004-v13-candidate` while fresh Codex 5.6 independent review is unavailable.

No delta below authorizes RF-005..009 or Executive/VM/AVR/DAP/VS Code/frontend changes.

## Delta chain

| Version | Problem | Normative delta | Portable HSX change? | Durable authority/evidence |
|---|---|---|---|---|
| `1.3` | current-profile caller R7 recovery `deref_u(CFA-8,4,little)` produces exact-width `RecipeScalar`, while 1.2 required `RecipeRegister` | `UnwindRow.register_rules` key is authoritative GPR identity; EXPRESSION may produce exact-width `REGISTER` or unsigned scalar; REGISTER still requires exact ID match | **No** | Steering #38 `5374100772`; `010--RF004_Register_Rule_Result_Conformance_v1_3.md` |
| `1.4` | generic immutable `ResolutionResult[T]` cannot legitimately contain mutable lifecycle service/session refs | dedicated lifecycle/control result envelopes for service/session refs; generic result immutability remains strict | **No** | Steering #38 `5375130207`; `015--RF004_Lifecycle_Result_Conformance_v1_4.md` |
| `1.5` | `SnapshotExpression.SymbolExpression` requires exact `symbol_id` lookup but public artifact index exposed only name candidates | additive `DebugArtifactIndex.symbol_by_id(symbol_id)` exact-cardinality query | **No** | Steering #38 `5375145347`; `016--RF004_Exact_Symbol_Lookup_Conformance_v1_5.md` |
| `1.6` | generic `InspectionResult` cannot preserve a trustworthy frame prefix while retaining exact terminating `CORRUPT/UNSUPPORTED/STALE` status | dedicated `StackWalkResult` / `StackPageResult` preserve proven prefix plus exact termination category | **No** | Steering #38 `5375603250`; `020--RF004_Stack_Prefix_Result_Conformance_v1_6.md` |
| `1.7` | epoch-reference DTOs contain full `InspectionContext`/controller evidence and must not widen the generic-result Enum payload catalog | dedicated `HandleInternResult`, `ScopeQueryResult`, `VariableQueryResult`; direct `EvidenceGrade` remains forbidden as generic payload | **No** | Steering #38 `5380356912`; `022--RF004_Epoch_Reference_Result_Conformance_v1_7.md` |
| `1.8` | top-frame R7 was incorrectly treated as current frame base across ENTRY/EPILOGUE phases | snapshot R7 is current `frame_base` only for exact current ABI + exact selected `ORDINARY` row + valid R7; ENTRY/EPILOGUE/TERMINAL do not infer it | **No** | Steering #38 `5380568339`; `025--RF004_Row_Aware_Frame_Base_Conformance_v1_8.md` |
| `1.9` | when CALL semantics were unproven, StackService kept `call_site_pc=None` but still used `resume_pc` as caller-frame `pc`, reproducing the legacy return-PC lookup defect called out by HSX-ST-007 | minimal fixed32 semantic-proof boundary: exact 4-byte InstructionRecord + `encoded_word` proves CALL only when primary opcode `(word >> 24) & 0xff == 0x24`; caller continuation stops typed on missing/non-CALL/unsupported/corrupt evidence and never falls back to resume PC | **No** | Steering #38 `5380763854`; `029--RF004_Call_Semantic_Proof_Conformance_v1_9.md`; canonical opcode/disassembler evidence |

## Stable principles across every delta

The following remain unchanged from the accepted 1.2 architecture:

- exact `InspectionContext {target,image,epoch}` coherence and immutable snapshot identity;
- typed address spaces and checked arithmetic; no implicit masks, modulo, wrap or host-endian conversion;
- exact-case/content-bound source identity; no lowercase/basename fallback;
- artifact parsing/indexing, source filesystem resolution, recipe evaluation, instruction semantic proof, stack reconstruction, epoch inspection and frontend mapping remain separate responsibilities;
- `SnapshotReadPort` stays snapshot/context-oriented and has no frame-aware/live-current side channel;
- StackService performs one top-frame snapshot register read and reconstructs callers only from explicit row recipes plus exact immutable instruction metadata required for call-site proof;
- no fixed-R7 caller fallback; `SAME` is explicit evidence, missing rules remain unavailable;
- `resume_pc` and `call_site_pc` remain distinct; no caller frame is created from `resume_pc` when exact CALL proof fails;
- the 1.9 semantic module is not a general disassembler and owns no artifact parsing, runtime I/O or frontend formatting;
- lifecycle/control, stack-prefix and epoch-reference dedicated envelopes are narrow exceptions to generic immutable result payloads, not a weakening of the generic algebra;
- no public DAP/CLI/VS Code or Executive/VM/AVR integration is implemented in RF-004.

## Candidate execution evidence

### Batch003

Exact candidate head `93ed5742434ef3512ee69beb43f39a57699b06ac` was independently executed read-only by TESTER and Master-classified `CANDIDATE_EXECUTION_PASS_WITH_KNOWN_BASELINES` in issue #38 comment `5380526850`:

- all then-current candidate must-pass suites passed;
- sole expected candidate strict XFAIL was cosmetic P002 (`LocationRow` TypeError wording);
- signed CS-IMM-103 passed;
- concurrency/stress passed 20/20;
- signed RF-004 regression oracle passed `159` with `3` accepted skips;
- full Python suite had only the two previously documented unrelated baselines;
- tested worktree remained clean and exact HEAD unchanged.

### Batch004

Exact candidate head `786b318d76d2dffba58152657122bbeea8975979` was independently executed read-only by TESTER in issue #38 comment `5380705374` with classification `CANDIDATE_EXECUTION_PASS_WITH_KNOWN_BASELINES`:

- all 22 candidate files exited zero: `103 passed` plus exactly one expected strict XFAIL P002;
- direct CS-IMM-103 passed;
- seven concurrency/race cases repeated `20/20` with no failure;
- signed RF-004 oracle: `159 passed, 3 skipped`;
- complete debugger-core aggregate: `383 passed, 3 skipped, 1 xfailed` after correcting a shell wildcard invocation exactly as the plan allowed;
- full Python aggregate: `917 passed, 5 skipped, 1 xfailed`, with only the two accepted historical baseline failures (`break_add_symbol_line`, `pretty_dmesg_assigns_session_numbers`);
- exact remote/tested head matched, final status/diff/diff-check were clean and execution caused no tracked mutation.

Batch004 therefore establishes a strong green baseline for 1.3..1.8 and the pre-1.9 Slice005/006 candidate. The subsequent completion audit found the resume-PC caller-continuation semantic seam; 1.9 and its tests are post-Batch004 candidate work and require the next aggregate execution batch before candidate-complete status may be claimed.

## Required future 5.6 review/promotion sequence

The candidate branch intentionally interleaves Slice005 and Slice006 commits because the no-review week used long staging batches. It MUST NOT be merged/cherry-picked wholesale as product authority.

When fresh independent Codex 5.6 capacity returns:

1. Review the complete `1.3..1.9` interface chain against accepted 1.2 + HSX-D-002/HSX-ST-007 and canonical fixed32 toolchain evidence. Reviewer must be independent of this Master implementation work.
2. Any Blocking/High/Medium finding requires candidate rework and a new exact-head interface review.
3. Reconstruct **Slice005 first** on top of the authoritative signed RF-004 head, using only the reviewed Slice005-owned/corrective files and tests. Review exact Slice005 product head independently, run formal verification and obtain Master exact-head sign-off.
4. Only after signed Slice005, reconstruct **Slice006** on top of that signed head, including its separately reviewed additive prior-slice seams (`symbol_by_id` etc.). Review/verify/sign exact Slice006 head.
5. Then perform RF-004 parent integration, fresh independent parent review, formal parent verification, exact-head Master sign-off, remote publication and fresh-checkout verification.
6. Only the final RF-004 parent decision package may return to Steering for RF-005 authorization.

RF-005 remains blocked throughout.