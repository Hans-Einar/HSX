# RF-004 Slice005 / Slice006 candidate completion matrix

Status: **CANDIDATE PRE-COMPLETION / BATCH005 EXECUTION PENDING / INDEPENDENT REVIEW PENDING**

Candidate branch: `master/rf004-v13-candidate`.
Authoritative RF-004 branch remains `codex/dbg-rf-004@46169516058aadf0e691a5981e29da4954b7444f`.

This matrix is a cold-start handoff. It maps every material Slice005/006 acceptance clause to
candidate implementation/evidence and states what still prevents sign-off. It does not promote
or sign any candidate work.

## Candidate interface chain

- base signed projection: `dbg.resolver-inspection/1.2`;
- candidate deltas: `1.3`, `1.4`, `1.5`, `1.6`, `1.7`, `1.8`, `1.9`;
- consolidated index: `026--RF004_Candidate_Interface_Delta_Index.md`.

## Slice005 — snapshot-bound StackService

### Candidate ownership/reconstruction set

Primary Slice005 candidate product:

- `python/hsx_debugger/stack.py`;
- `python/hsx_debugger/instruction_semantics.py`;
- additive package exports only where required.

Steering-authorized corrective seams in an earlier signed module:

- `python/hsx_debugger/recipes.py` — v1.3 register-row result binding only;
- final promotion cleanup P002 may correct the unrelated one-line `LocationRow` TypeError text,
  but that cosmetic fix must remain separately visible in review.

Primary Slice005 tests/evidence:

- `test_hsx_debugger_recipe_v13.py`;
- `test_hsx_debugger_stack.py`;
- `test_hsx_debugger_current_profile_rows_v18.py`;
- `test_hsx_debugger_frame_base_locations_v18.py`;
- `test_hsx_debugger_stack_dependency_contracts.py`;
- `test_hsx_debugger_instruction_semantics_v19.py`;
- `test_hsx_debugger_call_site_v19.py`;
- applicable candidate guards and signed recipe/artifact/legacy oracle tests.

### Acceptance matrix

| Frozen requirement / completion clause | Candidate implementation | Evidence | Candidate status |
|---|---|---|---|
| Validate exact binding/bundle/architecture/ABI before row evaluation | `_validate_binding`; row binding/ABI checks; no snapshot read before binding success | Stack binding mismatch + dependency tests; signed binding tests | **IMPLEMENTED; Batch005 re-execution required** |
| One exact top-frame snapshot register read | `_read_top_seed` requires register read-set then one all-declared read | Stack tests assert one read; no-fallback/shape tests | **IMPLEMENTED** |
| Exact descriptor register order/width, PC/SP typed validation | `_read_top_seed`, descriptor checks | shape/width/address tests | **IMPLEMENTED** |
| No fixed-R7 caller fallback | caller GPRs only row rules; missing rule unavailable; SAME explicit | v1.3 + Stack tests | **IMPLEMENTED** |
| v1.3 scalar caller-GPR row-key binding | exact-width unsigned RecipeScalar bound by row key; matching RecipeRegister still accepted | `test_hsx_debugger_recipe_v13.py`; feasibility probe evidence | **IMPLEMENTED; interface review pending** |
| Current ABI entry-before-PUSH | SP+4 CFA, caller PC from CFA-4, SP=CFA, R7 SAME; no current frame-base inference | v1.8 current-profile row matrix | **IMPLEMENTED** |
| Current ABI entry-after-PUSH | SP+8 CFA, caller PC CFA-4, R7 CFA-8; no current frame-base inference | v1.8 row matrix | **IMPLEMENTED** |
| Current ABI stable body | R7+8 CFA, caller PC CFA-4, saved R7 CFA-8, current frame_base from exact row-aware R7 | v1.8 row + local evaluation tests | **IMPLEMENTED** |
| Current ABI after POP at RET | SP+4 CFA, R7 SAME, no restored-caller-R7 current frame-base inference | v1.8 row matrix | **IMPLEMENTED** |
| Terminal top-level | explicit terminal row, no fabricated caller | Stack/v1.8 tests | **IMPLEMENTED** |
| Row-aware frame_base | only current ABI + selected ORDINARY row + valid snapshot R7; caller frame-base only explicit caller rule | v1.8 + frame-base location tests | **IMPLEMENTED; interface review pending** |
| Bounded recipe/evaluator budgets | signed RecipeEvaluator + `_AggregateBudget`; request/profile guards | recipe and Stack limit tests | **IMPLEMENTED** |
| Bound exhaustion exact `UNSUPPORTED/limit_exceeded` | nonterminal max_frames and recipe bounds preserve prefix under v1.6 | Stack/real-index tests | **IMPLEMENTED** |
| Trustworthy prefix with exact termination category | v1.6 `StackWalkResult` | CORRUPT/UNSUPPORTED/STALE/PARTIAL prefix tests | **IMPLEMENTED; interface review pending** |
| Cycle/non-progress protection | repeated PC/SP and CFA sets | Stack cycle tests | **IMPLEMENTED** |
| Artifact dependency failures never become fallback authority | function/unwind/instruction query type/exception fences | Stack dependency tests | **IMPLEMENTED** |
| `resume_pc` distinct from `call_site_pc` | separate frame fields retained | Stack/v1.9 tests | **IMPLEMENTED** |
| Caller continuation only at proven CALL | v1.9 `instruction_semantics.prove_call`, checked candidate, no resume fallback | fixed32/call-site tests including half-open caller-row discrimination | **IMPLEMENTED; Batch005 not yet executed; HIGH-ATTENTION REVIEW** |
| Missing CALL semantics | v1.9 terminates UNAVAILABLE -> PARTIAL with prefix before caller SP/GPR recovery | v1.9 negative tests | **IMPLEMENTED; Batch005 pending** |
| Proven non-CALL | v1.9 CORRUPT prefix | v1.9 negative tests | **IMPLEMENTED; Batch005 pending** |
| Unsupported instruction encoding | v1.9 UNSUPPORTED prefix | v1.9 semantic/call-site tests | **IMPLEMENTED; Batch005 pending** |
| Canonical fixed32 CALL constant does not drift | local pure-module constant + test against canonical `opcodes.OPCODES["CALL"]` and top-byte decode | `test_hsx_debugger_instruction_semantics_v19.py`, existing `test_opcode_table.py` | **TEST WRITTEN; Batch005 pending** |
| No stack cache/frontend IDs/runtime adapter | module boundary contains no such owner | static scope diff + module docstring | **SATISFIED candidate** |
| No Executive/VM/AVR/frontend edits | candidate diff scope audit | compare against authoritative head | **SATISFIED candidate** |

### Slice005 remaining gates

Slice005 is **not signed**. Remaining mandatory gates:

1. Batch005 execution PASS on exact post-1.9 candidate head;
2. fresh independent 5.6 review of the complete relevant interface chain, with special focus
   on 1.3/1.6/1.8/1.9 and fixed32 semantic-proof scope;
3. reconstruct a clean Slice005 product head from authoritative RF-004 head rather than
   promoting the interleaved candidate branch;
4. fresh independent exact-head Slice005 product review;
5. formal verification;
6. Master exact-head sign-off.

## Slice006 — epoch-bound inspection integration

### Candidate ownership/reconstruction set

Primary Slice006 candidate product:

- `python/hsx_debugger/handles.py`;
- `python/hsx_debugger/inspection_records.py`;
- `python/hsx_debugger/inspection.py`;
- additive package exports.

Steering-authorized additive prior-slice seam:

- `python/hsx_debugger/artifacts.py::symbol_by_id()` only; surgical additive query.

Primary Slice006 tests/evidence:

- `test_hsx_debugger_handles.py`;
- `test_hsx_debugger_inspection.py`;
- `test_hsx_debugger_reference_results_v17.py`;
- `test_hsx_debugger_reference_record_invariants.py`;
- `test_hsx_debugger_real_index_integration.py`;
- `test_hsx_debugger_query_races.py`;
- `test_hsx_debugger_service_precedence.py`;
- `test_hsx_debugger_stale_no_io.py`;
- `test_hsx_debugger_dependency_contracts.py`;
- `test_hsx_debugger_inspection_paging_partial.py`;
- `test_hsx_debugger_lifecycle_result_invariants.py`;
- `test_hsx_debugger_disassembly_contracts.py`;
- `test_hsx_debugger_variable_page_isolation.py`;
- `test_hsx_debugger_scope_variable_concurrency.py`;
- cross-slice real-index and v1.8/v1.9 stack evidence.

### Acceptance matrix

| Frozen requirement / completion clause | Candidate implementation | Evidence | Candidate status |
|---|---|---|---|
| Dedicated lifecycle/control result refs without weakening generic immutability | v1.4 `InspectionServiceCreateResult`, `InspectionOpenResult`, close result invariants | lifecycle tests + CS-IMM-103 | **IMPLEMENTED; interface review pending** |
| Exact factory precedence binding -> capability -> limits | `InspectionService.create` | precedence tests | **IMPLEMENTED** |
| Coherent portable epoch only | signed `EpochBinding`/`ControllerEpochAdapter` reject non-PORTABLE and BEST_EFFORT_LIVE before service | signed identity tests + static audit | **CONSUMES SIGNED FOUNDATION** |
| One active epoch, idempotent exact reopen | service lock/state | Inspection tests | **IMPLEMENTED** |
| Same epoch/different context stale | service state | Inspection tests | **IMPLEMENTED** |
| Previously invalidated epoch ID never rebinds | stale history | lifecycle tests | **IMPLEMENTED** |
| New valid epoch invalidates old before publish | locked lifecycle transition | tests + race audit | **IMPLEMENTED** |
| Close terminal | double checked closed gate; exact close result | lifecycle/precedence tests | **IMPLEMENTED** |
| EpochHandleStore monotone/no reuse/exact interning | dedicated store lock/object keys | handle tests + 20x stress | **IMPLEMENTED** |
| Exact stale/unknown handle classification | complete context + service stale history | handle/inspection tests | **IMPLEMENTED** |
| v1.7 reference-bearing results do not widen generic Enum payload | dedicated Handle/Scope/Variable envelopes | v1.7 tests + CS-IMM-103 | **IMPLEMENTED; interface review pending** |
| v1.5 exact symbol lookup | additive `DebugArtifactIndex.symbol_by_id` | real index v1.5 + integration | **IMPLEMENTED; prior-slice additive seam review pending** |
| Stack page preserves v1.6 exact termination and proven prefix | `StackPageResult`, handles intern only proven prefix | corrupt/unsupported prefix integration | **IMPLEMENTED** |
| Fixed scope composition/order | REGISTERS/LOCALS/GLOBALS; DTO constructor order/uniqueness enforcement | inspection + record invariant tests | **IMPLEMENTED** |
| Variable exact identity/order | symbol_id/declaration order; register descriptor order; exact handle object keys | variables + invariants | **IMPLEMENTED** |
| Paging exact slice and stable handles | page candidates before evaluation; intern selected slice; total preserved | pagination/isolation tests | **IMPLEMENTED** |
| Off-page variable cannot poison requested page | evaluate only selected page | poison-page test | **IMPLEMENTED** |
| Selected-frame variable evidence | LocationEvaluator receives exact UnwindFrame; no top-frame register substitution | inspection + v1.8 frame-base local tests | **IMPLEMENTED** |
| Snapshot expressions typed/side-effect free | closed expression union, no strings/calls/mutation/watch persistence | expression matrix | **IMPLEMENTED** |
| Memory typed range/unit/permission checks | descriptor conversion/range before read | memory tests | **IMPLEMENTED** |
| PARTIAL memory preserves explicit segments | generic result + MemoryBlock invariants | paging/partial tests | **IMPLEMENTED** |
| Disassembly exact bytes and optional annotations | snapshot bytes authoritative; artifact metadata optional typed annotation | disassembly/dependency tests | **IMPLEMENTED** |
| PARTIAL disassembly preserves proven bytes | accepts COMPLETE/PARTIAL snapshot result and preserves exact status/value | paging/partial tests | **IMPLEMENTED** |
| Disassembly bytes/metadata mismatch typed CORRUPT | constructor fence caught and classified | disassembly contract test | **IMPLEMENTED** |
| Dependency exceptions/types never escape public query surface | location/symbol/instruction/stack fences | dependency tests | **IMPLEMENTED** |
| Invalidation wins over late reads | begin/finish revision fences before publication | memory/register/scope/variable/disassembly race tests | **IMPLEMENTED** |
| Invalidated session performs no I/O/no handle allocation | early active gate | stale-no-I/O test | **IMPLEMENTED** |
| Bounded concurrency deterministic | separate lifecycle/session/store locks; no snapshot I/O under handle lock | stack/frame/scope/variable stress tests | **IMPLEMENTED** |
| Anti-monolith boundary | immutable records split to `inspection_records`; artifacts/recipes/stack/handles remain separate; inspection owns only epoch service/session composition/query workflows | static module/diff audit | **SATISFIED candidate; independent reviewer must reassess size/ownership** |
| No run control/resources/frontends/runtime adapters | absent from candidate modules/diff | scope audit | **SATISFIED candidate** |

### Slice006 remaining gates

Slice006 is **not signed**. Remaining mandatory gates:

1. Batch005 execution PASS after 1.9 changes because Slice006 consumes StackService;
2. fresh independent 5.6 interface review for 1.4/1.5/1.7 and cross-slice 1.6/1.8/1.9 effects;
3. only after signed Slice005, reconstruct clean Slice006 head on top of that signed head;
4. separately review the additive signed-artifact seam (`symbol_by_id`) and ensure no other
   Slice003 product drift;
5. fresh independent exact-head Slice006 product review;
6. formal verification;
7. Master exact-head sign-off.

## Cross-slice / parent implications

The staging branch interleaves commits from Slice005 and Slice006. Green execution does not
change dependency authority. Required promotion DAG is still:

```text
accepted authoritative RF004 head
          |
          v
 reconstruct Slice005
          |
 interface review -> product review -> verification -> signoff
          |
          v
 reconstruct Slice006 on signed Slice005
          |
 product review -> verification -> signoff
          |
          v
 RF004 parent integration/review/verification/signoff/fresh checkout
          |
          v
 Steering decision package
```

No candidate commit or test result authorizes RF-005..009.